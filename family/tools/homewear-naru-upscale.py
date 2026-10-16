#!/usr/bin/env python3
"""Run an explicitly supplied 4x RGB/alpha model on one copied outfit crop.

The retained homewear source run used AnimeSharp. Record the supplied checkpoint's
actual basename and hash; this tool requires a 4x image model, not a fixed model.

Windows GPU asset preparation only. Uses canonical model paths, never edits
ComfyUI configuration or the office group assets. GPU queue must be idle.
"""
import argparse
import ctypes
import hashlib
import json
import os
import pathlib
import sys
import threading
import time
import urllib.request


def model_provenance(path):
    return {"model": path.name,
            "modelSHA256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=pathlib.Path, required=True)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--model", type=pathlib.Path, required=True)
    parser.add_argument("--comfy-root", type=pathlib.Path, required=True)
    parser.add_argument("--rmbg-cache", type=pathlib.Path, required=True)
    parser.add_argument("--target-width", type=int, default=800)
    parser.add_argument("--target-height", type=int, default=2284)
    args = parser.parse_args()
    if os.name != "nt":
        raise RuntimeError("HOMEWEAR_UPSCALE_REQUIRES_EXISTING_WINDOWS_GPU_ENVIRONMENT")
    queue = json.loads(urllib.request.urlopen("http://127.0.0.1:8188/queue", timeout=10).read())
    if queue.get("queue_running") or queue.get("queue_pending"):
        raise RuntimeError("HOMEWEAR_UPSCALE_COMFY_QUEUE_BUSY")
    if args.out.exists():
        raise RuntimeError("HOMEWEAR_UPSCALE_OUTPUT_MUST_BE_FRESH")
    args.out.mkdir(parents=True)
    # Python owns the log streams: PowerShell's Stop preference can otherwise
    # mistake a harmless native stderr warning for command failure.
    sys.stdout=(args.out/"stdout.log").open("w",encoding="utf-8",buffering=1)
    sys.stderr=(args.out/"stderr.log").open("w",encoding="utf-8",buffering=1)
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.GetCurrentProcess.restype = ctypes.c_void_p
    process = k32.GetCurrentProcess()
    current, system = ctypes.c_size_t(), ctypes.c_size_t()
    if not k32.GetProcessAffinityMask(ctypes.c_void_p(process), ctypes.byref(current), ctypes.byref(system)):
        raise ctypes.WinError(ctypes.get_last_error())
    cpus = [i for i in range(ctypes.sizeof(current)*8) if current.value & (1 << i)][:4]
    if not cpus or not k32.SetProcessAffinityMask(ctypes.c_void_p(process), ctypes.c_size_t(sum(1<<i for i in cpus))):
        raise RuntimeError("HOMEWEAR_UPSCALE_CPU_AFFINITY_GUARD_FAILED")
    os.environ.update(OMP_NUM_THREADS="4", MKL_NUM_THREADS="4", OPENBLAS_NUM_THREADS="4",
                      HF_HUB_OFFLINE="1",TRANSFORMERS_OFFLINE="1")
    class Counters(ctypes.Structure):
        _fields_ = [("cb",ctypes.c_ulong),("PageFaultCount",ctypes.c_ulong),
                    ("PeakWorkingSetSize",ctypes.c_size_t),("WorkingSetSize",ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage",ctypes.c_size_t),("QuotaPagedPoolUsage",ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage",ctypes.c_size_t),("QuotaNonPagedPoolUsage",ctypes.c_size_t),
                    ("PagefileUsage",ctypes.c_size_t),("PeakPagefileUsage",ctypes.c_size_t),
                    ("PrivateUsage",ctypes.c_size_t)]
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    budget = {"cpuAffinity":cpus,"rssLimitBytes":4*1024**3,"peakRssBytes":0,
              "sampleSeconds":0.1,"guardRejected":False,"childProcesses":"none: this image script creates no subprocesses"}
    done = threading.Event()
    def monitor():
        while not done.is_set():
            info= Counters();info.cb=ctypes.sizeof(info)
            if not psapi.GetProcessMemoryInfo(ctypes.c_void_p(process),ctypes.byref(info),ctypes.sizeof(info)):
                budget["guardRejected"]=True
                (args.out/"budget.json").write_text(json.dumps(budget,indent=2))
                os._exit(75)
            budget["peakRssBytes"]=max(budget["peakRssBytes"],info.WorkingSetSize)
            if info.WorkingSetSize>budget["rssLimitBytes"]:
                budget["guardRejected"]=True
                (args.out/"budget.json").write_text(json.dumps(budget,indent=2))
                os._exit(75)
            done.wait(budget["sampleSeconds"])
    thread=threading.Thread(target=monitor,daemon=True);thread.start()
    started=time.monotonic()
    try:
        import numpy as np
        import torch
        import gc
        import importlib.util
        from PIL import Image
        from spandrel import ModelLoader, ImageModelDescriptor
        sys.path.insert(0,str(args.comfy_root))
        import comfy.utils
        torch.set_num_threads(4);torch.set_num_interop_threads(1)
        image=Image.open(args.input).convert("RGBA")
        rgba=np.array(image)
        if image.width*image.height>2_000_000:
            raise RuntimeError("HOMEWEAR_UPSCALE_SINGLE_CROP_PIXEL_LIMIT")
        required=["birefnet.py","BiRefNet_config.py","config.json","model.safetensors"]
        for name in required:
            if not (args.rmbg_cache/"RMBG-2.0"/name).is_file():
                raise RuntimeError("HOMEWEAR_RMBG_LOCAL_MODEL_FILE_REQUIRED "+name)
        installed=args.comfy_root/"custom_nodes/comfyui-rmbg/AILab_RMBG.py"
        spec=importlib.util.spec_from_file_location("homewear_asset_rmbg",installed)
        module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
        node=module.RMBG()
        node.models["RMBG-2.0"].base_cache_dir=str(args.rmbg_cache)
        source_tensor=torch.from_numpy(rgba[:,:,:3].astype(np.float32)/255).unsqueeze(0)
        matte, mask, _=node.process_image(image=source_tensor,model="RMBG-2.0",sensitivity=1.0,
            process_res=1024,mask_blur=0,mask_offset=0,invert_output=False,
            refine_foreground=False,background="Alpha",background_color="#222222")
        if matte.ndim!=4 or matte.shape[-1]!=4 or list(matte.shape[1:3])!=[image.height,image.width]:
            raise RuntimeError("HOMEWEAR_RMBG_RGBA_RESULT_REQUIRED")
        rgba=np.clip(np.rint(matte[0].cpu().numpy()*255),0,255).astype(np.uint8)
        a=rgba[:,:,3]
        alpha_stats={"transparent":int(np.count_nonzero(a==0)),"opaque":int(np.count_nonzero(a==255)),
            "positive":int(np.count_nonzero(a>0)),"intermediate":int(np.count_nonzero((a>0)&(a<255)))}
        ys,xs=np.nonzero(a>128)
        if len(xs)==0 or alpha_stats["transparent"]==0 or alpha_stats["intermediate"]==0 or alpha_stats["positive"]==a.size:
            raise RuntimeError("HOMEWEAR_RMBG_SILENT_FALLBACK_OR_INVALID_ALPHA "+json.dumps(alpha_stats))
        alpha_stats["bboxAbove128"]=[int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)]
        Image.fromarray(rgba,"RGBA").save(args.out/"matte-source.png")
        Image.fromarray(a,"L").save(args.out/"matte-source-alpha.png")
        (args.out/"matte.json").write_text(json.dumps(alpha_stats,indent=2)+"\n")
        print("RMBG_ALPHA",json.dumps(alpha_stats),flush=True)
        del node,source_tensor,matte,mask;gc.collect();torch.cuda.empty_cache()
        descriptor=ModelLoader(device="cpu").load_from_file(str(args.model))
        if not isinstance(descriptor,ImageModelDescriptor) or descriptor.scale!=4:
            raise RuntimeError("HOMEWEAR_UPSCALE_EXPECTED_FOUR_TIMES_IMAGE_MODEL")
        descriptor=descriptor.eval().to("cuda:0")
        def upscale(rgb):
            tensor=torch.from_numpy(rgb.astype(np.float32)/255).permute(2,0,1).unsqueeze(0)
            tensor=tensor.to("cuda:0")
            with torch.inference_mode():
                result=comfy.utils.tiled_scale(tensor,lambda tile:descriptor(tile.float()),
                    tile_x=512,tile_y=512,overlap=32,upscale_amount=descriptor.scale,output_device="cpu")
            return np.clip(np.rint(result[0].permute(1,2,0).numpy()*255),0,255).astype(np.uint8)
        rgb=upscale(rgba[:,:,:3])
        if np.all(rgba[:,:,3]==255):
            alpha=np.full(rgb.shape[:2],255,dtype=np.uint8)
            alpha_route="opaque source: alpha remains 255; no transparency inferred"
        else:
            alpha=upscale(np.repeat(rgba[:,:,3:4],3,axis=2))[:,:,0]
            alpha_route="existing Jinni method: alpha repeated RGB, same supplied 4x model, output red channel"
        enlarged=Image.fromarray(np.dstack([rgb,alpha]),"RGBA")
        enlarged.save(args.out/"animesharp-4x.png")
        enlarged.resize((args.target_width,args.target_height),Image.Resampling.LANCZOS).save(args.out/"registered-upscaled.png")
        metadata={"spec":"family-homewear-animesharp/1","sourceSHA256":hashlib.sha256(args.input.read_bytes()).hexdigest(),
                  **model_provenance(args.model),
                  "inputSize":list(image.size),"upscaledSize":list(enlarged.size),
                  "registeredSize":[args.target_width,args.target_height],"tile":512,"overlap":32,
                  "alphaRoute":alpha_route,"matting":"Installed RMBG-2.0 node, canonical instance cache, offline; no shared server changes",
                  "alphaStats":alpha_stats,"retouch":False,"torch":torch.__version__,"seconds":time.monotonic()-started}
        (args.out/"upscale.json").write_text(json.dumps(metadata,indent=2)+"\n")
        print(json.dumps(metadata),flush=True)
    finally:
        done.set();thread.join()
        (args.out/"budget.json").write_text(json.dumps(budget,indent=2)+"\n")


if __name__=="__main__":
    main()
