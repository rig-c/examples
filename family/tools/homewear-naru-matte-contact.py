#!/usr/bin/env python3
"""Review real segmentation on white/checker; prepare an explicit white matte."""
import json
import pathlib
from PIL import Image, ImageDraw

family=pathlib.Path(__file__).resolve().parents[1]
home=family/"outfits/homewear/naru"
run=home/"inputs/upscale-run"
image=Image.open(run/"registered-upscaled.png").convert("RGBA")
if image.size!=(800,2284):
    raise RuntimeError("HOMEWEAR_REGISTERED_CANVAS_REQUIRED")
alpha=image.getchannel("A")
if alpha.getextrema()!=(0,255):
    raise RuntimeError("HOMEWEAR_REGISTERED_ALPHA_RANGE_REQUIRED")
white=Image.new("RGBA",image.size,"white");white.alpha_composite(image)
white.convert("RGB").save(home/"inputs/painting-clothing-source.png")
checker=Image.new("RGBA",image.size,"#bbbbbb");d=ImageDraw.Draw(checker)
for y in range(0,image.height,24):
    for x in range(0,image.width,24):
        if (x//24+y//24)%2:d.rectangle((x,y,x+23,y+23),fill="#eeeeee")
checker.alpha_composite(image)
source=Image.open(home/"inputs/naru-source-crop.png").convert("RGB")
contact=Image.new("RGB",(1260,1220),"#dddddd");draw=ImageDraw.Draw(contact)
for i,(im,label) in enumerate([(source,"Copied source crop"),(white,"RMBG + AnimeSharp on white"),(checker,"Same RGBA on checker")]):
    contact.paste(im.convert("RGB").resize((400,1142),Image.Resampling.LANCZOS),(10+i*420,35))
    draw.text((10+i*420,12),label,fill="black")
draw.text((10,1190),"Actual GPU model output. Existing face/hair replacement and garment splitting remain pending.",fill="black")
contact.save(home/"docs/matte-upscale-contact.png")
(home/"config-inputs.json").write_text(json.dumps({"key":"naru_homewear","seethrough":{"resolution":1024,"steps":30,"seed":42,"offload":True},"assemble":{"rig_scale":1}},indent=2)+"\n")
print(home/"docs/matte-upscale-contact.png")
