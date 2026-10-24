"""Cut the jacket body (topwear minus the sleeves) and the bare-midriff band from a hold painting, in rig px, with world placement.
usage: cut_jacket.py <set dir> <key json> <out prefix>   -> <prefix>_jacket.png/.json and <prefix>_midriff.png/.json
Spaces as cut_piece.py: canvas 1024 -> 2432 square -> crop x 384..2048 -> /2 = rig px; world wx = rx - 416, wy = 1216 - ry."""
import sys, json, numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
SET, KEY, PFX = sys.argv[1], sys.argv[2], sys.argv[3]; RW, RH = 832, 1216
L = {l["name"]: l for l in json.load(open(f"{SET}/layers_full/layers.json"))["layers"]}
def layer(tag):
    if tag not in L: return np.zeros((RH, RW), np.float32)
    l = L[tag]; im = Image.open(f"{SET}/layers_full/parts/{tag}.png").convert("RGBA")
    c = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0)); c.paste(im, (l["left"], l["top"]))
    return np.asarray(c.resize((2432, 2432), Image.LANCZOS).crop((384, 0, 2048, 2432)).resize((RW, RH), Image.LANCZOS), np.float32)[..., 3] / 255.0
P = np.asarray(Image.open(f"{SET}/st_input_full.png").convert("RGB").crop((384, 0, 2048, 2432)).resize((RW, RH), Image.LANCZOS), np.float32)
kp = json.load(open(KEY))["points"]
def capsule(segs, w):
    m = Image.new("L", (RW, RH), 0); d = ImageDraw.Draw(m)
    for a, b in segs:
        d.line([tuple(a), tuple(b)], fill=255, width=w)
        for p in (a, b): d.ellipse([p[0] - w / 2, p[1] - w / 2, p[0] + w / 2, p[1] + w / 2], fill=255)
    return np.asarray(m, np.float32) / 255.0
segs = []
for sd in "lr":
    S_, E, Wr = np.array(kp[f"{sd}_shoulder"]), np.array(kp[f"{sd}_elbow"]), np.array(kp[f"{sd}_wrist"]); S2 = S_ + (E - S_) * 0.22; segs += [(S2, E), (E, Wr)]
arm_zone = ndimage.gaussian_filter(capsule(segs, 84), 3)
top = layer("topwear"); hands = np.maximum(layer("handwear-r"), layer("handwear-l"))
front = np.zeros((RH, RW), np.float32)
for t in ("face", "front hair", "back hair", "headwear", "neck"): front = np.maximum(front, layer(t))
jacket = top * (1 - np.clip(arm_zone * 1.2, 0, 1)) * (1 - np.clip(hands * 1.5, 0, 1)) * (1 - np.clip(front * 1.5, 0, 1))
lab, n = ndimage.label(jacket > 0.3); sizes = ndimage.sum(jacket > 0.3, lab, range(1, n + 1)); keep = (lab == 1 + int(np.argmax(sizes)))
jacket = jacket * ndimage.maximum_filter(keep.astype(np.float32), 5)
def save(mask, name):
    ys, xs = np.nonzero(mask > 0.02); x0, x1, y0, y1 = xs.min() - 2, xs.max() + 3, ys.min() - 2, ys.max() + 3
    rgba = np.zeros((RH, RW, 4), np.float32); rgba[..., :3] = P; rgba[..., 3] = mask * 255
    Image.fromarray(np.clip(rgba[y0:y1, x0:x1], 0, 255).astype(np.uint8), "RGBA").save(f"{PFX}_{name}.png")
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2; wx, wy = cx - 416, 1216 - cy
    json.dump({"set": SET, "cropRigPx": [int(x0), int(y0), int(x1), int(y1)], "worldCentre": [wx, wy], "opaquePx": int((mask > 0.5).sum())}, open(f"{PFX}_{name}.json", "w"), indent=1)
    print(name, "crop", [int(x0), int(y0), int(x1), int(y1)], "world centre", round(wx, 1), round(wy, 1), "opaque", int((mask > 0.5).sum()))
save(jacket, "jacket")
# the midriff: skin-coloured painting pixels between the jacket's hem and the skirt's top, inside the waist columns, not covered by any layer
skirt = layer("bottomwear"); rgb = P
skin = (rgb[..., 0] > 180) & (rgb[..., 0] - rgb[..., 2] > 12) & (rgb[..., 1] - rgb[..., 2] > 0) & (rgb[..., 0] < 256)
hipy = int((kp["r_hip"][1] + kp["l_hip"][1]) / 2); band = np.zeros((RH, RW), bool); band[hipy - 120:hipy + 20, :] = True
hx0, hx1 = int(min(kp["r_hip"][0], kp["l_hip"][0]) - 60), int(max(kp["r_hip"][0], kp["l_hip"][0]) + 60); band[:, :hx0] = False; band[:, hx1:] = False
mid = skin & band & (hands < 0.3)   # the layers are amodal (the skirt runs on up under the jacket), so only the painting's own colour decides
mid = ndimage.binary_opening(mid, iterations=1); lab, n = ndimage.label(mid)
if n: sizes = ndimage.sum(mid, lab, range(1, n + 1)); mid = lab == 1 + int(np.argmax(sizes))
mid = ndimage.binary_dilation(mid, iterations=2).astype(np.float32); mid = ndimage.gaussian_filter(mid, 0.7)
if (mid > 0.5).sum() > 50: save(mid, "midriff")
else: print("midriff: no bare skin found between hem and skirt")
