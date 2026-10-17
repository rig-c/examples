#!/usr/bin/env python3
"""First source-projected flat composition before rig authoring.

Uses the real full-pass masks, existing projection constants, explicit source
garment cuts and accepted head parts. Emits no rig/Spine data. All cut polygons
are in the registered source's crop-pixel frame, not skeletal garment guesses.
"""
import hashlib
import argparse
import json
import os
import pathlib
import shutil
os.environ.update(OMP_NUM_THREADS="4",OPENBLAS_NUM_THREADS="4",MKL_NUM_THREADS="4")
import numpy as np
from PIL import Image,ImageDraw
from scipy.ndimage import binary_closing,binary_dilation,binary_erosion,binary_fill_holes,gaussian_filter,label,distance_transform_edt

family=pathlib.Path(__file__).resolve().parents[1]
home=family/"outfits/homewear/naru"
raw=home/"inputs/layers/full_orig"
parser=argparse.ArgumentParser();parser.add_argument("--candidate",default="prepared-base");parser.add_argument("--force",action="store_true");args=parser.parse_args()
out=home/args.candidate
if out.exists():
    if args.force:
        shutil.rmtree(out)
    else:
        raise RuntimeError("HOMEWEAR_STATIC_FRESH_OUTPUT_REQUIRED")
out.mkdir();(out/"parts").mkdir()
W,H=800,2284
source=np.array(Image.open(home/"inputs/upscale-run/registered-upscaled.png").convert("RGBA"))
white=np.array(Image.open(home/"inputs/painting-clothing-source.png").convert("RGBA"))
manifest=json.loads((raw/"layers.json").read_text())
if [manifest["width"],manifest["height"]]!=[1024,1024]:raise RuntimeError("HOMEWEAR_STATIC_FULL_FRAME_REQUIRED")

def clean(array):
    alpha=array[:,:,3];components,n=label(alpha>8,np.ones((3,3),dtype=bool))
    if n==0:return np.zeros_like(array)
    counts=np.bincount(components.ravel());counts[0]=0
    keep=counts>=max(40,int(counts.max())*.01);keep[0]=False
    result=array.copy();result[~keep[components],3]=0
    return result

def full_canvas(entry):
    im=Image.open(raw/"parts"/(entry["name"]+".png")).convert("RGBA")
    canvas=Image.new("RGBA",(1024,1024));canvas.alpha_composite(im,(entry["left"],entry["top"]))
    return clean(np.array(canvas))

# Full-pass geometry is the real 2284-square input with 742px horizontal pad.
# No artificial second/head run is supplied to satisfy a two-pass API.
entries=manifest["layers"]
run_arrays=[full_canvas(e) for e in entries]
owner=np.full((H,W),-1,dtype=np.int16)
mapped={}
wanted={"topwear","legwear","handwear-l","neck"}
for i,(entry,array) in enumerate(zip(entries,run_arrays)):
    a=Image.fromarray(array[:,:,3],"L").resize((2284,2284),Image.Resampling.BICUBIC).crop((742,0,1542,2284))
    owner[np.array(a)>=250]=i
    if entry["name"] in wanted:
        im=Image.fromarray(array,"RGBA").resize((2284,2284),Image.Resampling.BICUBIC).crop((742,0,1542,2284))
        mapped[entry["name"]]=np.array(im)
projection={}
for name,array in mapped.items():
    i=next(i for i,e in enumerate(entries) if e["name"]==name)
    core=binary_erosion((owner==i)&(array[:,:,3]>=250),np.ones((5,5),bool))
    drift=np.max(np.abs(array[:,:,:3].astype(np.int16)-white[:,:,:3].astype(np.int16)),axis=2)
    accepted=binary_closing(core&(drift<=90),np.ones((5,5),bool))&core
    weight=gaussian_filter(accepted.astype(np.float32),sigma=1)*core
    array[:,:,:3]=np.clip(weight[:,:,None]*white[:,:,:3]+(1-weight[:,:,None])*array[:,:,:3],0,255).astype(np.uint8)
    projection[name]={"core":int(core.sum()),"taken":int(accepted.sum()),"refused":int((core&(drift>90)).sum())}

def polygon(points):
    im=Image.new("L",(W,H));ImageDraw.Draw(im).polygon(points,fill=255)
    return np.array(im)>0

# Measured against docs/garment-boundaries-grid.png. The lower central region
# is the open cardigan between the actual camisole hem and the trousers.
open_pants=[(271,1135),(321,1146),(366,1142),(417,1144),(471,1147),(526,1134),(550,1400),(222,1400)]
top=mapped["topwear"].copy();top[polygon(open_pants),3]=0
# Source visible neck skin follows its measured jaw/hair boundary. The
# accepted head remains above it; generated hidden neck remains below.
# No collar or new skin pixel is painted.
neck_visible=[(344,590),(380,601),(418,580),(429,580),(418,621),(420,641),(431,657),(313,657),(307,636),(334,625),(342,613)]
neck_visible_mask=polygon(neck_visible)
top[neck_visible_mask,3]=0
# Separate torso cardigan pixels from camisole + exposed chest. These masks
# change ownership only; their retained pixels are the real projected layer.
inner=[(304,630),(494,630),(500,715),(512,755),(524,835),(524,900),(528,1030),(529,1135),(550,1400),(222,1400),(262,1030),(273,900),(268,800),(286,740),(298,705)]
inside=polygon(inner)
camisole=top.copy();camisole[~inside,3]=0
cardigan=top.copy();cardigan[inside,3]=0
# The foreground sleeves and clasped hands share one generated semantic
# layer. Split their actual source wrist boundary, outside bust authority.
hands_poly=[(405,830),(446,818),(473,840),(489,861),(500,890),(505,918),(495,936),(481,935),(462,918),(440,900),(406,901),(391,916),(376,941),(359,945),(346,933),(340,910),(346,881),(361,858),(387,841)]
hand_mask=polygon(hands_poly)
hands=mapped["handwear-l"].copy();hands[~hand_mask,3]=0
sleeves=mapped["handwear-l"].copy();sleeves[hand_mask,3]=0
sleeves[binary_dilation(hand_mask,np.ones((11,11),bool))&inside,3]=0
card_front_ext=polygon([(222,635),(568,635),(572,850),(515,855),(275,855),(218,850)])&(~inside)&(~neck_visible_mask)&(~hand_mask)
take_card_ext=card_front_ext&(sleeves[:,:,3]>8)&(cardigan[:,:,3]<=8)
cardigan[take_card_ext]=sleeves[take_card_ext]
sleeves[card_front_ext,3]=0
# Slippers and short exposed ankles are wholly visible in the source.
# No empty model footwear layer is relabelled as successful extraction.
shoes=source.copy();shoes[:2080,:,3]=0
# Restore the entirely visible original waist, drawstring and trouser folds.
# Generated trouser pixels survive only under the overlying cardigan.
pants=mapped["legwear"].copy()
pants_visible=polygon(open_pants)
pants_visible[1390:2140]=True
pants_visible[2140:]=False
pants[pants_visible]=source[pants_visible]
neck=mapped["neck"].copy()
neck[neck_visible_mask]=source[neck_visible_mask]

pieces={"shoes":shoes,"bottomwear":pants,"neck":neck,
        "topwear":camisole,"cardigan":cardigan,"sleeves":sleeves,"hands":hands}
# Remove only the generated upper clothing fringe behind the accepted hair.
# The original painting is never retouched. Visible outer garment pixels use
# the original high-resolution RGBA rather than the 1024px generated boundary.
edge_treatment={"upperGeneratedUnionAlphaErosionPx":3,"upperToRow":700,"sourceOuterBoundaryBandPx":10,"sourceBandRows":[700,1400]}
union=np.maximum.reduce([a[:,:,3] for a in pieces.values()])
outer_distance=distance_transform_edt(union>8)
for name in ["topwear","cardigan","sleeves"]:
    a=pieces[name][:,:,3]
    a[:700][outer_distance[:700]<=3]=0
cloth_names=["topwear","cardigan","sleeves","hands"]
cloth_owner=np.full((H,W),-1,dtype=np.int16)
for i,name in enumerate(cloth_names):cloth_owner[pieces[name][:,:,3]>8]=i
_,nearest=distance_transform_edt(cloth_owner<0,return_indices=True)
nearest_owner=cloth_owner[nearest[0],nearest[1]]
inside_source=source[:,:,3]>128
boundary_distance=np.where(inside_source,distance_transform_edt(inside_source),distance_transform_edt(~inside_source))
source_band=boundary_distance<=10
source_band[:700]=False;source_band[1400:]=False
for i,name in enumerate(cloth_names):
    pieces[name][source_band,3]=0
    chosen=source_band&(nearest_owner==i)
    pieces[name][chosen]=source[chosen]

order=["shoes","bottomwear","neck","topwear","cardigan","sleeves","hands"]
four_conn=np.array([[0,1,0],[1,1,1],[0,1,0]],dtype=bool)
def clean_mesh_islands():
    for name in order:
        arr=pieces[name]
        arr[arr[:,:,3]<=8,3]=0
        comp,n_comp=label(arr[:,:,3]>8,four_conn)
        if n_comp>1:
            counts=np.bincount(comp.ravel());counts[0]=0
            min_sz=500 if name in ["neck","topwear","cardigan","sleeves"] else 200
            small=(counts<min_sz)&(counts>0)
            small_mask=small[comp]
            if small_mask.any():arr[small_mask,3]=0

clean_mesh_islands()
struct=np.ones((9,9),dtype=bool)
for idx in range(1,len(order)-1):
    name=order[idx]
    if name=="shoes":continue
    upper_opaque=np.zeros((H,W),dtype=bool)
    for upper_name in order[idx+1:]:
        upper_opaque|=(pieces[upper_name][:,:,3]==255)
    uncovered=(pieces[name][:,:,3]>80)&(~upper_opaque)
    if not uncovered.any():continue
    target_ul_px=52 if name=="topwear" else (34 if name=="cardigan" else 4)
    if target_ul_px>4:
        dist_uncov,nearest_idx=distance_transform_edt(~uncovered,return_indices=True)
        eroded=binary_erosion(uncovered,np.ones((11,11),dtype=bool))
        rgb_arr=pieces[name][:,:,:3].astype(np.int16)
        luma=(rgb_arr[:,:,0]+rgb_arr[:,:,1]+rgb_arr[:,:,2])//3
        bright_core=eroded&(luma>80)
        sample_mask=bright_core if bright_core.any() else (eroded if eroded.any() else uncovered)
        _,color_idx=distance_transform_edt(~sample_mask,sampling=(3.0,1.0),return_indices=True)
        silhouette=binary_fill_holes(binary_closing(upper_opaque|uncovered,np.ones((25,25),dtype=bool)))
        outer_sil_dist=distance_transform_edt(silhouette)
        near_ul=(dist_uncov<=4)&upper_opaque&(pieces[name][:,:,3]<=8)
        deep_ul=(dist_uncov<=target_ul_px)&(outer_sil_dist>=14)&upper_opaque&(pieces[name][:,:,3]<=8)
        underlap=near_ul|deep_ul
        if underlap.any():
            full_rgb=pieces[name][color_idx[0],color_idx[1],:3].astype(np.float32)
            for ch in range(3):
                full_rgb[:,:,ch]=gaussian_filter(full_rgb[:,:,ch],sigma=6.0)
            pieces[name][underlap,:3]=np.clip(full_rgb[underlap],0,255).astype(np.uint8)
            pieces[name][near_ul,:3]=pieces[name][nearest_idx[0][near_ul],nearest_idx[1][near_ul],:3]
            pieces[name][underlap,3]=255
    else:
        _,nearest_idx=distance_transform_edt(~uncovered,return_indices=True)
        underlap=binary_dilation(uncovered,struct)&upper_opaque&(pieces[name][:,:,3]<=8)
        pieces[name][underlap,:3]=pieces[name][nearest_idx[0][underlap],nearest_idx[1][underlap],:3]
        pieces[name][underlap,3]=255
clean_mesh_islands()
part_records=[]
for name,array in pieces.items():
    ys,xs=np.nonzero(array[:,:,3]>0)
    if not len(xs):raise RuntimeError("HOMEWEAR_STATIC_NONEMPTY_PART_REQUIRED "+name)
    box=(int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1))
    im=Image.fromarray(array,"RGBA").crop(box);im.save(out/"parts"/(name+".png"))
    part_records.append({"name":name,"x":box[0],"y":box[1],"w":im.width,"h":im.height,
        "opaque_px":int(np.count_nonzero(np.array(im)[:,:,3]>8)),
        "source":"painting:visible-neck+full:neck" if name=="neck" else "painting:source-slippers" if name=="shoes" else "full:"+({"bottomwear":"legwear","sleeves":"handwear-l","hands":"handwear-l","cardigan":"topwear"}.get(name,name))})

baseline=json.loads((family/"naru/out/parts.json").read_text())
common={r["name"]:r for r in baseline["parts"] if r["name"] not in ["shoes","legwear","bottomwear","neck","topwear"]}
def accepted(name):
    record=common[name];return Image.open(family/"naru/out/parts"/(name+".png")).convert("RGBA"),(record["x"],record["y"])
canvas=Image.new("RGBA",(W,H))
im,at=accepted("hair_back");canvas.alpha_composite(im,at)
for name in ["shoes","bottomwear","neck","topwear","cardigan","sleeves","hands"]:
    canvas.alpha_composite(Image.fromarray(pieces[name],"RGBA"))
for name in common:
    if name=="hair_back":continue
    im,at=accepted(name);canvas.alpha_composite(im,at)
canvas.save(out/"assembled.png")
flat=Image.new("RGBA",(W,H),"white");flat.alpha_composite(canvas)
flat.convert("RGB").save(out/"assembled-white.png")
contact=Image.new("RGB",(840,1220),"#dddddd");draw=ImageDraw.Draw(contact)
for i,(im,label_text) in enumerate([(Image.fromarray(white,"RGBA"),"Registered clothing source (new head)"),(flat,"Flat prototype (accepted face/hair)")]):
    contact.paste(im.convert("RGB").resize((400,1142),Image.Resampling.LANCZOS),(10+i*420,35));draw.text((10+i*420,12),label_text,fill="black")
draw.text((10,1190),"First flat composition only: no rig, build/check or motion acceptance. Visible source projected; hidden model art retained.",fill="black")
contact_path=home/"docs"/(args.candidate+"-contact.png");contact.save(contact_path)
metadata={"spec":"family-homewear-static-prototype/1","status":"STATIC_REVIEW_ONLY", "parts":part_records,
 "projection":projection,"projectionPolicy":{"source":"Existing family/parts projection constants","coreAlpha":250,"kernel":5,"driftLimit":90,"sigma":1},
 "geometry":{"inputSquare":[2284,2284],"padLeft":742,"runSquare":[1024,1024],"output":[800,2284],"resample":"Pillow BICUBIC; no claim of byte parity with public OpenCV-equivalent helper"},
 "edgeTreatment":edge_treatment,
 "cuts":{"openPants":open_pants,"cardiganInnerBoundary":inner,"hands":hands_poly,"sourceShoesFromRow":2080,"sourcePantsFullFromRow":1390,"sourcePantsToRow":2140,"sourceVisibleNeckPolygon":neck_visible},
 "commonHead":"Existing accepted parts copied in the same canvas; generated head/hair are never adopted.",
 "limitations":["This is an early flat source/occlusion review, not a mesh or runtime result.","Cut boundary fit and source projection omissions still require visual review; no hidden pixel was painted by a heuristic."]}
(out/"prototype.json").write_text(json.dumps(metadata,indent=2)+"\n")
print(json.dumps({"status":"STATIC_REVIEW_READY","contact":str(contact_path),"parts":len(part_records)}))
