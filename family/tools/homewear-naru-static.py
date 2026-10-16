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
from scipy.ndimage import binary_closing,binary_erosion,gaussian_filter,label,distance_transform_edt

family=pathlib.Path(__file__).resolve().parents[1]
home=family/"outfits/homewear/naru"
raw=home/"inputs/layers/full_orig"
parser=argparse.ArgumentParser();parser.add_argument("--candidate",default="prepared-base");args=parser.parse_args()
out=home/args.candidate
if out.exists():raise RuntimeError("HOMEWEAR_STATIC_FRESH_OUTPUT_REQUIRED")
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
inner=[(295,630),(505,630),(516,740),(526,835),(526,900),(530,1030),(529,1135),(550,1400),(222,1400),(262,1030),(273,900),(267,800),(284,700)]
inside=polygon(inner)
camisole=top.copy();camisole[~inside,3]=0
cardigan=top.copy();cardigan[inside,3]=0
# The foreground sleeves and clasped hands share one generated semantic
# layer. Split their actual source wrist boundary, outside bust authority.
hands_poly=[(405,830),(446,818),(473,840),(489,861),(500,890),(505,918),(495,936),(481,935),(462,918),(440,900),(406,901),(391,916),(376,941),(359,945),(346,933),(340,910),(346,881),(361,858),(387,841)]
hand_mask=polygon(hands_poly)
hands=mapped["handwear-l"].copy();hands[~hand_mask,3]=0
sleeves=mapped["handwear-l"].copy();sleeves[hand_mask,3]=0
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
