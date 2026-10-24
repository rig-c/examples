"""After prewarp: the strip the lifted jacket vacated becomes bare skin in the start image and is repainted at full strength.
usage: midriff_prep.py <K>   (reads keys3/inpaint_<K>/{warped,softmask,compmask}.png + prewarp.json; writes them back, keeps *_orig.png)"""
import sys, json, numpy as np
from PIL import Image
K=sys.argv[1]; D=f"keys3/inpaint_{K}"; pj=json.load(open(f"{D}/prewarp.json"))
hem=pj["hem_y"]; lift=max(pj["lift_r"],pj["lift_l"])*pj["hem_ride"]; top=int(hem-lift)-2; bot=int(hem)+6     # painting px rows the jacket left
cj=json.load(open("char_keypoints.json"))["joints"]
L={l["name"]:l for l in json.load(open("sheet/layers/full/layers.json"))["layers"]}["bottomwear"]
c=Image.new("L",(1024,1024),0); c.paste(Image.open("sheet/layers/full/parts/bottomwear.png").split()[-1],(L["left"],L["top"]))
bw=np.array(c.resize((2432,2432),Image.BILINEAR).crop((384,0,384+1664,2432)))   # the skirt layer in painting px
row=bw[int(hem)+12]; cols=np.nonzero(row>127)[0]; x0=int(cols.min())+4; x1=int(cols.max())-4   # the waistband's own width
base=np.array(Image.open("sheet/painting.png").convert("RGB")); skin=np.median(base[1450:1500, int(cj["r_knee"][0])-15:int(cj["r_knee"][0])+15].reshape(-1,3),axis=0)  # thigh colour
import os
for n in ("warped","softmask","compmask"):
    if not os.path.exists(f"{D}/{n}_orig.png"): Image.open(f"{D}/{n}.png").save(f"{D}/{n}_orig.png")
w=np.array(Image.open(f"{D}/warped_orig.png").convert("RGB")); w[top:bot, x0:x1]=skin; Image.fromarray(w).save(f"{D}/warped.png")
LW,LH=832,1216
for n in ("softmask","compmask"):
    m=np.array(Image.open(f"{D}/{n}_orig.png").convert("L")); m[top//2:bot//2, x0//2:x1//2]=255; Image.fromarray(m).save(f"{D}/{n}.png")
print(K,"skin band painting px rows",top,bot,"cols",x0,x1,"skin",skin.astype(int).tolist(),"lift px",round(lift,1))
