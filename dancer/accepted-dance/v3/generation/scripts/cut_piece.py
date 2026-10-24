"""Cut the arms of a hold painting into ONE piece, visible pixels only, in rig px (832x1216 = painting/2), with its world placement.
usage: cut_piece.py <set dir> <key json> <out.png> [--hide-head]
  set dir   : keys*/set_<K> with st_input_full.png (2432 square) and layers_full/{layers.json,parts/*.png} (See-through)
  key json  : keys*/<K>.json, latent 832x1216 = rig px; its shoulders bound the jacket body column
arms = handwear-r U handwear-l U (topwear outside the shoulder column); minus the head layers when --hide-head
(the forearms pass behind the head: what the painting hides stays hidden, nothing amodal is kept).
Spaces: canvas 1024 -> 2432 square -> crop x 384..2048 -> /2 = rig px (y down); world wx = rx - 416, wy = 1216 - ry."""
import sys, os, json, numpy as np
from PIL import Image
from scipy import ndimage
SET, KEY, OUT = sys.argv[1], sys.argv[2], sys.argv[3]; HIDE_HEAD = "--hide-head" in sys.argv
RW, RH = 832, 1216
L = {l["name"]: l for l in json.load(open(f"{SET}/layers_full/layers.json"))["layers"]}
def layer(tag):
    if tag not in L: return np.zeros((RH, RW), np.float32)
    l = L[tag]; im = Image.open(f"{SET}/layers_full/parts/{tag}.png").convert("RGBA")
    c = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0)); c.paste(im, (l["left"], l["top"]))
    big = c.resize((2432, 2432), Image.LANCZOS).crop((384, 0, 2048, 2432)).resize((RW, RH), Image.LANCZOS)
    return np.asarray(big, np.float32)[..., 3] / 255.0
P = np.asarray(Image.open(f"{SET}/st_input_full.png").convert("RGB").crop((384, 0, 2048, 2432)).resize((RW, RH), Image.LANCZOS), np.float32)
kp = json.load(open(KEY))["points"]
from PIL import ImageDraw
def capsule(segs, w):
    m = Image.new("L", (RW, RH), 0); d = ImageDraw.Draw(m)
    for a, b in segs:
        d.line([tuple(a), tuple(b)], fill=255, width=w)
        for p in (a, b): d.ellipse([p[0] - w / 2, p[1] - w / 2, p[0] + w / 2, p[1] + w / 2], fill=255)
    return np.asarray(m, np.float32) / 255.0
segs = []
for sd in "lr":
    S_, E, Wr = np.array(kp[f"{sd}_shoulder"]), np.array(kp[f"{sd}_elbow"]), np.array(kp[f"{sd}_wrist"])
    S2 = S_ + (E - S_) * float(os.environ.get('SLEEVE_START', '0.22'))   # 0.22: the shoulder cap stays with the jacket; 0: the cap comes with the sleeve
    segs += [(S2, E), (E, Wr)]
arm_zone = ndimage.gaussian_filter(capsule(segs, 84), 3)
hands = np.maximum(layer("handwear-r"), layer("handwear-l"))
sleeves = layer("topwear") * np.clip(arm_zone * 1.2, 0, 1)
# See-through folds a strip of the jacket front (the badge) into handwear: inside the shoulder column, below the shoulder
# line and away from the forearms, nothing is an arm
rs, ls = kp["r_shoulder"][0], kp["l_shoulder"][0]; sy = min(kp["r_shoulder"][1], kp["l_shoulder"][1])
xx = np.arange(RW)[None, :]; yy = np.arange(RH)[:, None]
fore_zone = ndimage.gaussian_filter(capsule([(np.array(kp[f"{sd}_elbow"]), np.array(kp[f"{sd}_wrist"]) + (np.array(kp[f"{sd}_wrist"]) - np.array(kp[f"{sd}_elbow"])) * 0.45) for sd in "lr"], 120), 3)
strip = (xx > rs + 12) & (xx < ls - 12) & (yy > sy - 10) & (fore_zone < 0.2)
hands = hands * (~strip); sleeves = sleeves * (~strip)
arms = np.maximum(hands, sleeves)
if HIDE_HEAD:
    head = np.zeros((RH, RW), np.float32)
    for t in ("face", "front hair", "back hair", "headwear", "ears-l", "ears-r", "eyewhite-l", "eyewhite-r", "irides-l", "irides-r", "eyelash-l", "eyelash-r", "eyebrow-l", "eyebrow-r", "nose", "mouth", "neck"):
        head = np.maximum(head, layer(t))
    arms = arms * (1 - np.clip(head * 1.5, 0, 1))
# keep the two largest connected blobs (the two arms, or one if they join), drop specks
lab, n = ndimage.label(arms > 0.3); sizes = ndimage.sum(arms > 0.3, lab, range(1, n + 1)); keep = np.zeros_like(arms)
for i in np.argsort(sizes)[::-1][:3]:
    if sizes[i] > 400: keep[lab == i + 1] = 1
arms = arms * ndimage.maximum_filter(keep, 5)
ys, xs = np.nonzero(arms > 0.02); x0, x1, y0, y1 = xs.min() - 2, xs.max() + 3, ys.min() - 2, ys.max() + 3
rgba = np.zeros((RH, RW, 4), np.float32); rgba[..., :3] = P; rgba[..., 3] = arms * 255
piece = rgba[y0:y1, x0:x1]; Image.fromarray(np.clip(piece, 0, 255).astype(np.uint8), "RGBA").save(OUT)
cx, cy = (x0 + x1) / 2, (y0 + y1) / 2; wx, wy = cx - 416, 1216 - cy
json.dump({"set": SET, "key": KEY, "hideHead": HIDE_HEAD, "cropRigPx": [int(x0), int(y0), int(x1), int(y1)], "size": [int(x1 - x0), int(y1 - y0)], "worldCentre": [wx, wy],
           "chestLocalAtSetup": {"x": wx, "y": wy - 775.51, "rotation": 0}, "opaquePx": int((arms > 0.5).sum())}, open(OUT.replace(".png", ".json"), "w"), indent=1)
print(OUT, "crop", [int(x0), int(y0), int(x1), int(y1)], "world centre", round(wx, 1), round(wy, 1), "opaque px", int((arms > 0.5).sum()))
