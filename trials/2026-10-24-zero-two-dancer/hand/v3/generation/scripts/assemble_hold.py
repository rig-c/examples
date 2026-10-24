"""Put two hold pieces into the accepted hand rig: arms_hold_head (behind the head, on the chest) for frames IN_A..OUT_A and
arms_hold_front (in front of the jacket, on BONE_B) for IN_B..OUT_B; the articulated K1/K2 parts are hidden only inside those spans.
usage: assemble_hold.py <base dir with hand/r3 + work> <out dir> <head piece.png> <head piece.json> <front piece.png> <front piece.json> [IN_A OUT_A IN_B OUT_B] [BONE_B]"""
import sys, json, os, shutil
B, D, HP, HJ, FP, FJ = sys.argv[1:7]; FR = [int(x) for x in sys.argv[7:11]] if len(sys.argv) >= 11 else [124, 219, 234, 329]
BONE_B = sys.argv[11] if len(sys.argv) >= 12 else "hip"
IN_A, OUT_A, IN_B, OUT_B = FR; FPS = 30
os.makedirs(f"{D}/hand/r3", exist_ok=True); os.makedirs(f"{D}/work/corpus/dancer/accepted/images", exist_ok=True)
src = f"{B}/work/corpus/dancer/accepted/images"
for n in os.listdir(src):
    dst = f"{D}/work/corpus/dancer/accepted/images/{n}"
    if not os.path.exists(dst): os.symlink(os.path.realpath(f"{src}/{n}"), dst)
shutil.copy(HP, f"{D}/work/corpus/dancer/accepted/images/arms_hold_head.png"); shutil.copy(FP, f"{D}/work/corpus/dancer/accepted/images/arms_hold_front.png")
rig = json.load(open(f"{B}/hand/r3/rig.json")); mo = json.load(open(f"{B}/hand/r3/motion.json"))
bones = {b["name"]: b for b in rig["bones"]}
def setup_world(name):  # this rig has no rotation on hip/chest_ctl/chest at setup; y only
    x = y = 0.0; b = bones[name]
    while b is not None:
        x += b.get("x", 0); y += b.get("y", 0); b = bones.get(b.get("parent")) if b.get("parent") else None
    return x, y
def insert_slot(after, name, bone):
    i = [s["name"] for s in rig["slots"]].index(after); rig["slots"].insert(i + 1, {"name": name, "bone": bone, "attachment": None})
insert_slot("forearm_l_back", "arms_hold_head", "chest"); insert_slot("sleevefront_l", "arms_hold_front", BONE_B)
sk = rig["skins"]["default"]
for name, pj, bone in (("arms_hold_head", HJ, "chest"), ("arms_hold_front", FJ, BONE_B)):
    wc = json.load(open(pj))["worldCentre"]; bx, by = setup_world(bone)
    sk[name] = {name: {"image": f"{name}.png", "x": round(wc[0] - bx, 3), "y": round(wc[1] - by, 3), "rotation": 0}}
an = mo["animations"]["zero-two-r3-hand"]
def t(fr): return round(fr / FPS, 8)
setsA = {"upperarm_r_under": "K1_upperarm_r", "forearm_r_back": "K1_forearm_r", "upperarm_l_under": "K1_upperarm_l", "forearm_l_back": "K1_forearm_l"}
setsB = {"forearm_r": "K2_forearm_r", "upperarm_r": "K2_upperarm_r", "forearm_l_mid": "base_full_forearm_l", "upperarm_l_mid": "K2_upperarm_l"}
def punch(slot, att, fin, fout):
    tr = next(x for x in an["tracks"] if x["property"] == "attachment" and x["slot"] == slot)
    keys = [k for k in tr["keys"] if not (t(fin) - 1e-9 < k["t"] < t(fout) + 1e-9)]
    keys += [{"t": t(fin), "v": None}, {"t": t(fout), "v": att}]; tr["keys"] = sorted(keys, key=lambda k: k["t"])
# the lowering (OUT_A..IN_B) draws the base art in the FRONT slots (forearm_r/upperarm_r/forearm_l/upperarm_l): the back/under
# slots the raise uses put a lowering arm behind the torso and the skirt (owner, 2026-10-24)
for s, a in setsA.items():
    punch(s, None, IN_A, OUT_A)
    tr = next(x for x in an["tracks"] if x["property"] == "attachment" and x["slot"] == s)
    tr["keys"] = sorted([k for k in tr["keys"] if not (t(OUT_A) - 1e-9 < k["t"] < t(IN_B) + 1e-9)] + [{"t": t(OUT_A), "v": None}, {"t": t(IN_B), "v": None}], key=lambda k: k["t"])
frontBase = {"forearm_r": "forearm_r", "upperarm_r": "upperarm_r", "forearm_l": "forearm_l", "upperarm_l": "upperarm_l"}
for s, a in frontBase.items():
    tr = next((x for x in an["tracks"] if x["property"] == "attachment" and x["slot"] == s), None)
    if tr is None: tr = {"slot": s, "property": "attachment", "keys": [{"t": 0, "v": None}]}; an["tracks"].append(tr)
    keys = [k for k in tr["keys"] if not (t(OUT_A) - 1e-9 < k["t"] < t(IN_B) + 1e-9)]
    keys += [{"t": t(OUT_A), "v": a}, {"t": t(IN_B), "v": None}]; tr["keys"] = sorted(keys, key=lambda k: k["t"])
for s, a in setsB.items():
    tr = next(x for x in an["tracks"] if x["property"] == "attachment" and x["slot"] == s)
    for k in tr["keys"]:
        if abs(k["t"] - 7.4375) < 1e-6: k["v"] = None   # K2 parts no longer enter at 7.4375; the hold piece enters at IN_B
    punch(s, a, IN_B, OUT_B)
an["tracks"].append({"slot": "arms_hold_head", "property": "attachment", "keys": [{"t": 0, "v": None}, {"t": t(IN_A), "v": "arms_hold_head"}, {"t": t(OUT_A), "v": None}]})
an["tracks"].append({"slot": "arms_hold_front", "property": "attachment", "keys": [{"t": 0, "v": None}, {"t": t(IN_B), "v": "arms_hold_front"}, {"t": t(OUT_B), "v": None}]})
import os
if os.environ.get("JACKET"):
    jp, jj = os.environ["JACKET"].split(":"); shutil.copy(jp, f"{D}/work/corpus/dancer/accepted/images/hold_jacket.png")
    wc = json.load(open(jj))["worldCentre"]; bx, by = setup_world("chest")
    sk["topwear"]["hold_jacket"] = {"image": "hold_jacket.png", "x": round(wc[0] - bx, 3), "y": round(wc[1] - by, 3), "rotation": 0}
    tr = next(x for x in an["tracks"] if x["property"] == "attachment" and x["slot"] == "topwear")
    prev = None
    for k in sorted(tr["keys"], key=lambda k: k["t"]):
        if k["t"] <= t(IN_A) + 1e-9: prev = k["v"]
    keys = [k for k in tr["keys"] if not (t(IN_A) - 1e-9 < k["t"] < t(OUT_A) + 1e-9)]
    keys += [{"t": t(IN_A), "v": "hold_jacket"}, {"t": t(OUT_A), "v": prev}]; tr["keys"] = sorted(keys, key=lambda k: k["t"])
    print("jacket swapped over the head hold; restores", prev)
if os.environ.get("MIDRIFF"):
    mp, mj = os.environ["MIDRIFF"].split(":"); shutil.copy(mp, f"{D}/work/corpus/dancer/accepted/images/hold_midriff.png")
    wc = json.load(open(mj))["worldCentre"]; bx, by = setup_world("hip")
    insert_slot("neck", "midriff", "hip")
    sk["midriff"] = {"hold_midriff": {"image": "hold_midriff.png", "x": round(wc[0] - bx, 3), "y": round(wc[1] - by, 3), "rotation": 0}}
    an["tracks"].append({"slot": "midriff", "property": "attachment", "keys": [{"t": 0, "v": None}, {"t": t(IN_A), "v": "hold_midriff"}, {"t": t(OUT_A), "v": None}]})
json.dump(rig, open(f"{D}/hand/r3/rig.json", "w"), indent=2); json.dump(mo, open(f"{D}/hand/r3/motion.json", "w"), indent=2)
print("assembled", D, "spans", FR, "front bone", BONE_B, {n: sk[n][n] for n in ("arms_hold_head", "arms_hold_front")})
