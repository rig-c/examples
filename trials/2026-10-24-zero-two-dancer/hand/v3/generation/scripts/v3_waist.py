"""v3: the waist as a permanent part behind the jacket, exposed by the chest's own lift.
usage: v3_waist.py <base dir (altH5-style assembled: hold arm pieces, no jacket swap)> <out dir> <midriff.png> <midriff.json> <lift units> <ramp-in f0 f1> <ramp-out f0 f1>
- midriff piece: the painting's skin band extended straight up under the jacket (opaque; the jacket covers it), region on `hip`, slot after `neck` (behind skirt and jacket), shown every frame.
- chest lift: chest_ctl.translatey += L over the head hold (ramped), head_ctl.translatey -= L so the head stays (the reference's shoulders shrug toward the ears; the lift is the reference's measured shoulder lift at the character's scale)."""
import sys, json, os, shutil, numpy as np
from PIL import Image
B, D, MP, MJ = sys.argv[1:5]; L = float(sys.argv[5]); a0, a1, b0, b1 = [int(x) for x in sys.argv[6:10]]; FPS = 30
shutil.copytree(B, D, symlinks=True)
m = np.array(Image.open(MP).convert("RGBA")); EXT = 70   # rig px of skin added above the band
top = m[2:6].mean(axis=0, keepdims=True).astype(np.uint8); top[..., 3] = 255
ext = np.repeat(top, EXT, axis=0); mask = ext[..., 3] > 0; cols = m[2:6, :, 3].mean(axis=0) > 128; ext[:, ~cols] = 0
piece = np.concatenate([ext, m], axis=0); Image.fromarray(piece, "RGBA").save(f"{D}/work/corpus/dancer/accepted/images/waist.png")
wc = json.load(open(MJ))["worldCentre"]; wc_y = wc[1] + EXT / 2   # the crop grew upward by EXT: its centre moves up by EXT/2 (world y up)
rig = json.load(open(f"{D}/hand/r3/rig.json")); mo = json.load(open(f"{D}/hand/r3/motion.json"))
bones = {b["name"]: b for b in rig["bones"]}
def setup_world(name):
    x = y = 0.0; b = bones[name]
    while b is not None: x += b.get("x", 0); y += b.get("y", 0); b = bones.get(b.get("parent")) if b.get("parent") else None
    return x, y
hx, hy = setup_world("hip"); i = [s["name"] for s in rig["slots"]].index("neck"); rig["slots"].insert(i + 1, {"name": "waist", "bone": "hip", "attachment": "waist"})
rig["skins"]["default"]["waist"] = {"waist": {"image": "waist.png", "x": round(wc[0] - hx, 3), "y": round(wc_y - hy, 3), "rotation": 0}}
an = mo["animations"]["zero-two-r3-hand"]
def lift(f):
    if f <= a0 or f >= b1: return 0.0
    if f < a1: z = (f - a0) / (a1 - a0); return L * z * z * (3 - 2 * z)
    if f <= b0: return L
    z = (b1 - f) / (b1 - b0); return L * z * z * (3 - 2 * z)
def t(f): return round(f / FPS, 8)
def sample(track, tt):
    ks = track["keys"]; v = ks[0]["v"][0]
    for j in range(len(ks)):
        if ks[j]["t"] <= tt + 1e-9: v = ks[j]["v"][0]
        if j + 1 < len(ks) and ks[j]["t"] <= tt < ks[j + 1]["t"]:
            A, Bk = ks[j], ks[j + 1]; return A["v"][0] + (Bk["v"][0] - A["v"][0]) * (tt - A["t"]) / (Bk["t"] - A["t"])
    return v
def add_lift(bone, sign):
    tr = next((x for x in an["tracks"] if x.get("bone") == bone and x["property"] == "translatey"), None)
    if tr is None: tr = {"bone": bone, "property": "translatey", "keys": [{"t": 0, "v": [0.0]}]}; an["tracks"].append(tr)
    times = sorted({k["t"] for k in tr["keys"]} | {t(f) for f in range(a0, a1 + 1)} | {t(f) for f in range(b0, b1 + 1)})
    tr["keys"] = [{"t": tt, "v": [round(sample(tr, tt) + sign * lift(tt * FPS), 4)]} for tt in times]
add_lift("chest_ctl", +1.0); add_lift("head_ctl", -1.0)
json.dump(rig, open(f"{D}/hand/r3/rig.json", "w"), indent=2); json.dump(mo, open(f"{D}/hand/r3/motion.json", "w"), indent=2)
print("v3 waist piece", piece.shape, "placed", rig["skins"]["default"]["waist"]["waist"], "lift", L, "ramps", (a0, a1), (b0, b1))
