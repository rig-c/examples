#!/usr/bin/env python3
"""Call the installed See-through nodes with canonical local models.

Keeps the installed tag/version behavior. Writes returned arrays and the
wrapper manifest contract into a fresh consumer directory, avoiding the shared
SavePSD output path. No service/global-directory mutation and no model download.
"""
import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
import pathlib
import sys
import subprocess
import threading
import time
import urllib.request


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",type=pathlib.Path,required=True)
    parser.add_argument("--out",type=pathlib.Path,required=True)
    parser.add_argument("--comfy-root",type=pathlib.Path,required=True)
    parser.add_argument("--model-root",type=pathlib.Path,required=True)
    parser.add_argument("--rss-limit-gib",type=int,required=True)
    parser.add_argument("--initial-bf16",action="store_true",
                        help="Construct the same stored BF16 model directly in its final dtype; avoids default FP32 expansion.")
    parser.add_argument("--cuda-device-name",required=True,
                        help="Select exactly one verified physical GPU by name, then pin this process by its UUID.")
    args=parser.parse_args()
    if os.name!="nt" or not 4<=args.rss_limit_gib<=24:
        raise RuntimeError("HOMEWEAR_SEETHROUGH_WINDOWS_AND_BOUNDED_BUDGET_REQUIRED")
    queue=json.loads(urllib.request.urlopen("http://127.0.0.1:8188/queue",timeout=10).read())
    if queue.get("queue_running") or queue.get("queue_pending"):
        raise RuntimeError("HOMEWEAR_SEETHROUGH_QUEUE_BUSY")
    if args.out.exists():
        raise RuntimeError("HOMEWEAR_SEETHROUGH_FRESH_OUTPUT_REQUIRED")
    for folder in ["seethroughv0.0.2_layerdiff3d","seethroughv0.0.1_marigold"]:
        if not (args.model_root/folder/"model_index.json").is_file():
            raise RuntimeError("HOMEWEAR_SEETHROUGH_LOCAL_MODEL_REQUIRED "+folder)
    args.out.mkdir(parents=True)
    sys.stdout=(args.out/"stdout.log").open("w",encoding="utf-8",buffering=1)
    sys.stderr=(args.out/"stderr.log").open("w",encoding="utf-8",buffering=1)
    class MemoryStatus(ctypes.Structure):
        _fields_=[("length",ctypes.c_ulong),("load",ctypes.c_ulong),
                  ("totalPhys",ctypes.c_ulonglong),("availPhys",ctypes.c_ulonglong),
                  ("totalPage",ctypes.c_ulonglong),("availPage",ctypes.c_ulonglong),
                  ("totalVirtual",ctypes.c_ulonglong),("availVirtual",ctypes.c_ulonglong),
                  ("availExtendedVirtual",ctypes.c_ulonglong)]
    memory=MemoryStatus();memory.length=ctypes.sizeof(memory)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
        raise RuntimeError("HOMEWEAR_SEETHROUGH_MEMORY_ADMISSION_UNMEASURED")
    if memory.availPhys<(args.rss_limit_gib+8)*1024**3:
        raise RuntimeError("HOMEWEAR_SEETHROUGH_MEMORY_ADMISSION_REFUSED")
    os.environ.update(OMP_NUM_THREADS="4",MKL_NUM_THREADS="4",OPENBLAS_NUM_THREADS="4",
                      HF_HUB_OFFLINE="1",TRANSFORMERS_OFFLINE="1")
    k32=ctypes.WinDLL("kernel32",use_last_error=True)
    k32.GetCurrentProcess.restype=ctypes.c_void_p
    process=k32.GetCurrentProcess();current,system=ctypes.c_size_t(),ctypes.c_size_t()
    if not k32.GetProcessAffinityMask(ctypes.c_void_p(process),ctypes.byref(current),ctypes.byref(system)):
        raise ctypes.WinError(ctypes.get_last_error())
    cpus=[i for i in range(ctypes.sizeof(current)*8) if current.value&(1<<i)][:4]
    if not cpus or not k32.SetProcessAffinityMask(ctypes.c_void_p(process),ctypes.c_size_t(sum(1<<i for i in cpus))):
        raise RuntimeError("HOMEWEAR_SEETHROUGH_AFFINITY_GUARD_FAILED")
    class Counters(ctypes.Structure):
        _fields_=[("cb",ctypes.c_ulong),("PageFaultCount",ctypes.c_ulong),
            ("PeakWorkingSetSize",ctypes.c_size_t),("WorkingSetSize",ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage",ctypes.c_size_t),("QuotaPagedPoolUsage",ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage",ctypes.c_size_t),("QuotaNonPagedPoolUsage",ctypes.c_size_t),
            ("PagefileUsage",ctypes.c_size_t),("PeakPagefileUsage",ctypes.c_size_t),("PrivateUsage",ctypes.c_size_t)]
    psapi=ctypes.WinDLL("psapi",use_last_error=True)
    budget={"cpuAffinity":cpus,"rssLimitBytes":args.rss_limit_gib*1024**3,"peakRssBytes":0,
            "guardRejected":False,"sampleSeconds":0.1,"wallLimitSeconds":2700,
            "processScope":"single inference process, no subprocesses"}
    started=time.monotonic();done=threading.Event()
    def monitor():
        while not done.is_set():
            info=Counters();info.cb=ctypes.sizeof(info)
            measured=psapi.GetProcessMemoryInfo(ctypes.c_void_p(process),ctypes.byref(info),ctypes.sizeof(info))
            budget["peakRssBytes"]=max(budget["peakRssBytes"],info.WorkingSetSize)
            budget["seconds"]=time.monotonic()-started
            if not measured or info.WorkingSetSize>budget["rssLimitBytes"] or budget["seconds"]>budget["wallLimitSeconds"]:
                budget["guardRejected"]=True
                (args.out/"budget.json").write_text(json.dumps(budget,indent=2)+"\n")
                os._exit(75)
            done.wait(0.1)
    thread=threading.Thread(target=monitor,daemon=True);thread.start()
    def stage(name):
        (args.out/"stage.json").write_text(json.dumps({"stage":name,"seconds":time.monotonic()-started},indent=2)+"\n")
        print("STAGE",name,flush=True)
    try:
        stage("imports")
        devices=subprocess.check_output(["nvidia-smi","--query-gpu=name,uuid","--format=csv,noheader"],text=True)
        matches=[line.split(",",1)[1].strip() for line in devices.splitlines()
                 if line.split(",",1)[0].strip()==args.cuda_device_name]
        if len(matches)!=1:raise RuntimeError("HOMEWEAR_SEETHROUGH_ONE_PHYSICAL_DEVICE_REQUIRED")
        os.environ["CUDA_VISIBLE_DEVICES"]=matches[0]
        import gc
        import numpy as np
        import torch
        from PIL import Image
        sys.path.insert(0,str(args.comfy_root))
        torch.set_num_threads(4);torch.set_num_interop_threads(1)
        gpu_free,gpu_total=torch.cuda.mem_get_info(0)
        physical_name=torch.cuda.get_device_name(0)
        if physical_name!=args.cuda_device_name:
            raise RuntimeError("HOMEWEAR_SEETHROUGH_PINNED_DEVICE_NAME_MISMATCH")
        preflight={"availablePhysicalBytes":memory.availPhys,"rssLimitBytes":args.rss_limit_gib*1024**3,
                   "physicalReserveBytes":8*1024**3,"cudaDevice":0,"cudaFreeBytes":gpu_free,"cudaTotalBytes":gpu_total,
                   "physicalDeviceName":physical_name,"pinnedByVerifiedUUID":True,"queueRunning":0,"queuePending":0}
        (args.out/"resource-admission.json").write_text(json.dumps(preflight,indent=2)+"\n")
        if gpu_free<12*1024**3:raise RuntimeError("HOMEWEAR_SEETHROUGH_CUDA_ADMISSION_REFUSED")
        installed=args.comfy_root/"custom_nodes/ComfyUI-See-through/nodes.py"
        spec=importlib.util.spec_from_file_location("homewear_installed_seethrough",installed)
        module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
        # The installed node sets BF16 only after constructing the whole model.
        # Stored weights are already BF16. These public loader kwargs remove
        # that temporary FP32 expansion without changing weights/sampling.
        load_kwargs={"torch_dtype":torch.bfloat16,"low_cpu_mem_usage":True,
                     "local_files_only":True,"use_safetensors":True}
        def bounded_layer_model():
            path=str(args.model_root/"seethroughv0.0.2_layerdiff3d")
            transparent=module.TransparentVAE.from_pretrained(path,subfolder="trans_vae",**load_kwargs)
            unet=module.UNetFrameConditionModel.from_pretrained(path,subfolder="unet",**load_kwargs)
            pipeline=module.KDiffusionStableDiffusionXLPipeline.from_pretrained(
                path,trans_vae=transparent,unet=unet,scheduler=None,**load_kwargs)
            for name in ["vae","trans_vae","unet","text_encoder","text_encoder_2"]:
                getattr(pipeline,name).to(dtype=torch.bfloat16)
            pipeline._st_group_offload=False
            if hasattr(pipeline,"enable_group_offload"):
                pipeline.enable_group_offload("cuda",num_blocks_per_group=1)
                pipeline._st_group_offload=True
            else:
                print("Installed pipeline has no group offload; following original node's skip branch",flush=True)
            if not pipeline._st_group_offload:
                pipeline.text_encoder.to(module.mm.get_torch_device())
                pipeline.text_encoder_2.to(module.mm.get_torch_device())
            pipeline.cache_tag_embeds(unload_textencoders=True)
            return pipeline
        def bounded_depth_model():
            path=str(args.model_root/"seethroughv0.0.1_marigold")
            unet=module.UNetFrameConditionModel.from_pretrained(path,subfolder="unet",**load_kwargs)
            pipeline=module.MarigoldDepthPipeline.from_pretrained(path,unet=unet,**load_kwargs)
            pipeline.to(dtype=torch.bfloat16)
            pipeline._st_group_offload=False
            if hasattr(pipeline,"enable_group_offload"):
                pipeline.enable_group_offload("cuda",num_blocks_per_group=1)
                pipeline._st_group_offload=True
            if not pipeline._st_group_offload:pipeline.text_encoder.to(module.mm.get_torch_device())
            pipeline.cache_tag_embeds(unload_textencoders=True)
            return pipeline
        image=Image.open(args.input).convert("RGB")
        tensor=torch.from_numpy(np.array(image).astype(np.float32)/255).unsqueeze(0)
        (args.out/"previews").mkdir()
        def preview(tensor,name):
            array=tensor.detach().cpu().numpy()
            if array.ndim==4:array=array[0]
            array=np.clip(np.rint(array*255),0,255).astype(np.uint8)
            Image.fromarray(array).save(args.out/"previews"/(name+".png"))
        stage("load_layerdiff_local_offloaded")
        layer_model=bounded_layer_model() if args.initial_bf16 else module.SeeThrough_LoadLayerDiffModel().load_model(
            model=str(args.model_root/"seethroughv0.0.2_layerdiff3d"),quant_mode="none",
            cache_tag_embeds=True,group_offload=True,auto_download=False)[0]
        actual_group_offload=bool(getattr(layer_model,"_st_group_offload",False))
        free,total=torch.cuda.mem_get_info(0)
        admission={"cudaDevice":0,"freeBytes":free,"totalBytes":total,
            "allocatedBytes":torch.cuda.memory_allocated(0),"reservedBytes":torch.cuda.memory_reserved(0),
            "unetParameterBytes":sum(p.numel()*p.element_size() for p in layer_model.unet.parameters()),
            "effectiveGroupOffload":actual_group_offload,
            "scope":"Actual state after loading and tag caching, before layer inference; not a claim about unmeasured activation peak."}
        (args.out/"load-admission.json").write_text(json.dumps(admission,indent=2)+"\n")
        print("LOAD_ADMISSION",json.dumps(admission),flush=True)
        stage("generate_installed_v3_layers_1024_seed42_steps30")
        layers,layers_preview=module.SeeThrough_GenerateLayers().generate(
            image=tensor,layerdiff_model=layer_model,seed=42,resolution=1024,num_inference_steps=30)
        preview(layers_preview,"layers")
        (args.out/"raw_layers").mkdir()
        raw_inventory=[]
        for tag,array in layers.layer_dict.items():
            array=np.asarray(array)
            Image.fromarray(array).save(args.out/"raw_layers"/(tag+".png"))
            raw_inventory.append({"tag":tag,"shape":list(array.shape),"dtype":str(array.dtype)})
        (args.out/"raw-inventory.json").write_text(json.dumps(raw_inventory,indent=2)+"\n")
        del layer_model;gc.collect();torch.cuda.empty_cache()
        stage("load_depth_local_offloaded")
        depth_model=bounded_depth_model() if args.initial_bf16 else module.SeeThrough_LoadDepthModel().load_model(
            model=str(args.model_root/"seethroughv0.0.1_marigold"),quant_mode="none",
            cache_tag_embeds=True,group_offload=True,auto_download=False)[0]
        stage("generate_depth")
        depths,depth_preview=module.SeeThrough_GenerateDepth().generate(layers=layers,depth_model=depth_model,seed=42,resolution_depth=-1)
        preview(depth_preview,"depth")
        del depth_model;gc.collect();torch.cuda.empty_cache()
        stage("postprocess_original_split_no_lama")
        parts,parts_preview=module.SeeThrough_PostProcess().process(layers_depth=depths,tblr_split=True,use_lama=False)
        preview(parts_preview,"parts")
        (args.out/"parts").mkdir();(args.out/"raw_depth").mkdir()
        entries=[]
        for tag in sorted(parts["tag2pinfo"],key=lambda t:parts["tag2pinfo"][t].get("depth_median",1),reverse=True):
            pinfo=parts["tag2pinfo"][tag];array=pinfo.get("img")
            if array is None:continue
            array=np.asarray(array);filename=tag+".png"
            Image.fromarray(array).save(args.out/"parts"/filename)
            x1,y1,x2,y2=map(int,pinfo.get("xyxy",[0,0,array.shape[1],array.shape[0]]))
            entry={"name":tag,"filename":filename,"left":x1,"top":y1,"right":x2,"bottom":y2,
                   "depth_median":float(pinfo.get("depth_median",1))}
            if pinfo.get("depth") is not None:np.save(args.out/"raw_depth"/(tag+".npy"),pinfo["depth"])
            entries.append(entry)
        height,width=map(int,parts["frame_size"])
        manifest={"prefix":"homewear_naru","timestamp":"seed42","layers":entries,"width":width,"height":height}
        (args.out/"layers.json").write_text(json.dumps(manifest,indent=2)+"\n")
        metadata={"spec":"family-homewear-seethrough/1","sourceSHA256":hashlib.sha256(args.input.read_bytes()).hexdigest(),
            "installedNodeSHA256":hashlib.sha256(installed.read_bytes()).hexdigest(),"seed":42,"resolution":1024,"steps":30,
            "quant":"none","groupOffloadRequested":True,"groupOffloadActive":actual_group_offload,"lama":False,"downloads":False,
            "initialBF16":args.initial_bf16,"finalModelDtype":"bfloat16",
            "behavior":"Installed model/tag version unchanged, including its internal head pass when selected by the installed node.",
            "rawLayerCount":len(raw_inventory),"postprocessLayerCount":len(entries),"canvas":[width,height],
            "export":"Original node postprocess arrays and equivalent SavePSD wrapper metadata, fresh consumer directory; no shared output directory mutation.",
            "seconds":time.monotonic()-started}
        (args.out/"meta.json").write_text(json.dumps(metadata,indent=2)+"\n")
        stage("raw_export_complete")
        print(json.dumps(metadata),flush=True)
    finally:
        done.set();thread.join()
        (args.out/"budget.json").write_text(json.dumps(budget,indent=2)+"\n")


if __name__=="__main__":
    main()
