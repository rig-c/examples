#!/usr/bin/env python3
"""
upgrade_jinni_4x.py
Upgrades Jinni's 1x See-through / Qwen-Image-Layered rig (400x1142) to 4x-AnimeSharp (800x2284),
resolving 6 production rigging artifacts:
  1. Right ear / temple hair-to-skin transition & dark fringe unmixing (`head:front hair`, `head:ears-r`, `full:face`)
  2. Bare right shoulder pink/black jagged noise & shoulder-to-sleeve seam (`full:topwear`, `full:handwear-r`)
  3. Neck-to-shoulder skin hole & dark hair stamping under the neckline hair curl (`head:neck`, `full:topwear`, `head:front hair`)
  4. Hand/arm silhouette stamped onto `bottomwear` & torso remnant on `handwear_l` (`full:bottomwear`, `full:neck` shield, `full:handwear-l`)
  5. Ankle step, high-heel shoe split, calf silhouette & earring core (`full:legwear`, `full:footwear`, `full:earwear`)
  6. Physics range limits (`stops`) & independent 2D breast jiggle (`boob_r`, `boob_l`, `bust_r`, `bust_l` contour circle regions)
"""
import os
import json
from PIL import Image
import numpy as np
from scipy.ndimage import distance_transform_edt, binary_dilation, binary_erosion, gaussian_filter

FAMILY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JINNI_DIR = os.path.join(FAMILY_DIR, "jinni")
os.chdir(JINNI_DIR)

# 1. Load 800x2284 config.json (or 1x config_400x1142.json if present) and update physics limits, stops & breast jiggle
if os.path.exists("config_400x1142.json"):
    with open("config_400x1142.json") as f:
        orig_cfg = json.load(f)
    cfg = json.loads(json.dumps(orig_cfg))
    cfg["seethrough"]["head_box"] = [x * 2 for x in cfg["seethrough"]["head_box"]]
    for b in cfg["bones"]:
        if "at" in b:
            b["at"] = [x * 2 for x in b["at"]]
        if "points" in b:
            b["points"] = [[p[0] * 2, p[1] * 2] for p in b["points"]]
        if "tip" in b:
            b["tip"] = [x * 2 for x in b["tip"]]
    for mname, m in cfg["meshes"].items():
        if "grid" in m:
            m["grid"] = m["grid"] * 2
        if "r" in m:
            m["r"] = m["r"] * 2
        if "segments" in m:
            new_segs = []
            for s in m["segments"]:
                if isinstance(s, list):
                    new_segs.append([s[0], [s[1][0] * 2, s[1][1] * 2], [s[2][0] * 2, s[2][1] * 2]])
                else:
                    new_segs.append(s)
            m["segments"] = new_segs
    for t in cfg["motion"]["tracks"]:
        if t.get("prop") in ("translatex", "translatey"):
            if "amp" in t:
                t["amp"] = round(t["amp"] * 2, 4)
            if "base" in t:
                t["base"] = round(t["base"] * 2, 4)
else:
    with open("config.json") as f:
        cfg = json.load(f)

cfg["meshes"]["hair_front"]["segments"] = [
    s for s in cfg["meshes"]["hair_front"]["segments"] if s != "hairback_r"
]

for t in cfg["motion"]["tracks"]:
    if t.get("chain") in ("hairback_r", "hairback_l"):
        t["amps"] = [0.35, 0.8, 1.4]
    elif t.get("chain") in ("bang_r", "bang_c", "bang_l"):
        t["amps"] = [0.6, 1.3]
    elif t.get("chain") in ("skirt_r", "skirt_c", "skirt_l"):
        t["amps"] = [0.25, 0.6, 1.1]

cfg["bones"] = [b for b in cfg["bones"] if b.get("name") not in ("boob_r", "boob_l")]
cfg["bones"].extend([
    {"name": "boob_r", "parent": "chest", "at": [384, 724]},
    {"name": "boob_l", "parent": "chest", "at": [514, 720]}
])

cfg["meshes"]["topwear"] = {
    "contour": {
        "tolerance": 2,
        "margin": 2,
        "spacing": 36,
        "maxEdge": 64,
        "stray": 400,
        "bridges": True,
        "regions": [
            {"name": "bust_r", "shape": "circle", "cx": 384, "cy": 724, "r": 24, "bone": "boob_r", "spacing": 14, "band": 38},
            {"name": "bust_l", "shape": "circle", "cx": 514, "cy": 720, "r": 25, "bone": "boob_l", "spacing": 14, "band": 39}
        ]
    },
    "r": 16,
    "segments": [
        ["chest", [440, 552], [440, 866]],
        ["hip", [440, 866], [440, 1106]]
    ]
}

cfg["motion"]["tracks"] = [t for t in cfg["motion"]["tracks"] if t.get("bone") not in ("boob_r", "boob_l")]

if "blink" in cfg.get("motion", {}):
    cfg["motion"]["blink"]["t"] = 2.05

cfg["constraints"] = [
    {"type": "physics", "name": "hairback_r0_phys", "bone": "hairback_r0", "rotate": 1, "inertia": 0.45, "strength": 220.0, "damping": 0.9, "mass": 1, "wind": 0.2, "gravity": 0.15, "mix": 1},
    {"type": "physics", "name": "hairback_r1_phys", "bone": "hairback_r1", "rotate": 1, "inertia": 0.55, "strength": 170.0, "damping": 0.88, "mass": 1, "wind": 0.45, "gravity": 0.3, "mix": 1},
    {"type": "physics", "name": "hairback_r2_phys", "bone": "hairback_r2", "rotate": 1, "inertia": 0.65, "strength": 130.0, "damping": 0.86, "mass": 1, "wind": 0.75, "gravity": 0.5, "mix": 1},
    {"type": "physics", "name": "hairback_l0_phys", "bone": "hairback_l0", "rotate": 1, "inertia": 0.45, "strength": 220.0, "damping": 0.9, "mass": 1, "wind": 0.2, "gravity": 0.15, "mix": 1},
    {"type": "physics", "name": "hairback_l1_phys", "bone": "hairback_l1", "rotate": 1, "inertia": 0.55, "strength": 170.0, "damping": 0.88, "mass": 1, "wind": 0.45, "gravity": 0.3, "mix": 1},
    {"type": "physics", "name": "hairback_l2_phys", "bone": "hairback_l2", "rotate": 1, "inertia": 0.65, "strength": 130.0, "damping": 0.86, "mass": 1, "wind": 0.75, "gravity": 0.5, "mix": 1},
    {"type": "physics", "name": "bang_r0_phys", "bone": "bang_r0", "rotate": 1, "inertia": 0.25, "strength": 240.0, "damping": 0.9, "mass": 1, "wind": 0.15, "gravity": 0.1, "mix": 1},
    {"type": "physics", "name": "bang_r1_phys", "bone": "bang_r1", "rotate": 1, "inertia": 0.35, "strength": 180.0, "damping": 0.88, "mass": 1, "wind": 0.35, "gravity": 0.2, "mix": 1},
    {"type": "physics", "name": "bang_c0_phys", "bone": "bang_c0", "rotate": 1, "inertia": 0.25, "strength": 240.0, "damping": 0.9, "mass": 1, "wind": 0.15, "gravity": 0.1, "mix": 1},
    {"type": "physics", "name": "bang_c1_phys", "bone": "bang_c1", "rotate": 1, "inertia": 0.35, "strength": 180.0, "damping": 0.88, "mass": 1, "wind": 0.35, "gravity": 0.2, "mix": 1},
    {"type": "physics", "name": "bang_l0_phys", "bone": "bang_l0", "rotate": 1, "inertia": 0.25, "strength": 240.0, "damping": 0.9, "mass": 1, "wind": 0.15, "gravity": 0.1, "mix": 1},
    {"type": "physics", "name": "bang_l1_phys", "bone": "bang_l1", "rotate": 1, "inertia": 0.35, "strength": 180.0, "damping": 0.88, "mass": 1, "wind": 0.35, "gravity": 0.2, "mix": 1},
    {"type": "physics", "name": "skirt_r0_phys", "bone": "skirt_r0", "rotate": 1, "inertia": 0.35, "strength": 240.0, "damping": 0.9, "mass": 1, "wind": 0.2, "gravity": 0.15, "mix": 1},
    {"type": "physics", "name": "skirt_r1_phys", "bone": "skirt_r1", "rotate": 1, "inertia": 0.45, "strength": 190.0, "damping": 0.88, "mass": 1, "wind": 0.4, "gravity": 0.3, "mix": 1},
    {"type": "physics", "name": "skirt_r2_phys", "bone": "skirt_r2", "rotate": 1, "inertia": 0.55, "strength": 145.0, "damping": 0.86, "mass": 1, "wind": 0.65, "gravity": 0.45, "mix": 1},
    {"type": "physics", "name": "skirt_c0_phys", "bone": "skirt_c0", "rotate": 1, "inertia": 0.35, "strength": 240.0, "damping": 0.9, "mass": 1, "wind": 0.2, "gravity": 0.15, "mix": 1},
    {"type": "physics", "name": "skirt_c1_phys", "bone": "skirt_c1", "rotate": 1, "inertia": 0.45, "strength": 190.0, "damping": 0.88, "mass": 1, "wind": 0.4, "gravity": 0.3, "mix": 1},
    {"type": "physics", "name": "skirt_c2_phys", "bone": "skirt_c2", "rotate": 1, "inertia": 0.55, "strength": 145.0, "damping": 0.86, "mass": 1, "wind": 0.65, "gravity": 0.45, "mix": 1},
    {"type": "physics", "name": "skirt_l0_phys", "bone": "skirt_l0", "rotate": 1, "inertia": 0.35, "strength": 240.0, "damping": 0.9, "mass": 1, "wind": 0.2, "gravity": 0.15, "mix": 1},
    {"type": "physics", "name": "skirt_l1_phys", "bone": "skirt_l1", "rotate": 1, "inertia": 0.45, "strength": 190.0, "damping": 0.88, "mass": 1, "wind": 0.4, "gravity": 0.3, "mix": 1},
    {"type": "physics", "name": "skirt_l2_phys", "bone": "skirt_l2", "rotate": 1, "inertia": 0.55, "strength": 145.0, "damping": 0.86, "mass": 1, "wind": 0.65, "gravity": 0.45, "mix": 1},
    {"type": "physics", "name": "earring_phys", "bone": "earring", "x": 0.4, "y": 0.8, "inertia": 0.3, "strength": 200.0, "damping": 0.9, "mass": 1, "wind": 0.25, "gravity": 0.2, "mix": 1},
    {"type": "physics", "name": "boob_r_phys", "bone": "boob_r", "x": 0.32, "y": 1.0, "inertia": 0.41, "strength": 325.0, "damping": 0.88, "mass": 1.24, "wind": 0.21, "gravity": 0.12, "mix": 1.0},
    {"type": "physics", "name": "boob_l_phys", "bone": "boob_l", "x": 0.34, "y": 1.0, "inertia": 0.43, "strength": 318.0, "damping": 0.88, "mass": 1.27, "wind": 0.23, "gravity": 0.12, "mix": 1.0}
]

cfg["stops"] = [
    {"chain": "skirt_r", "against": "hip", "at": [10, -240], "inward": -1.5, "outward": 8.0, "lower": {"inward": -2.0, "outward": 10.0}},
    {"chain": "skirt_c", "against": "hip", "at": [-40, -240], "inward": -5.0, "outward": 5.0, "lower": {"inward": -6.0, "outward": 6.0}},
    {"chain": "skirt_l", "against": "hip", "at": [-10, -240], "inward": -1.5, "outward": 8.0, "lower": {"inward": -2.0, "outward": 10.0}},
    {"chain": "hairback_r", "against": "chest", "at": [0, 120], "inward": -1.5, "outward": 7.0, "lower": {"inward": -2.0, "outward": 9.0}},
    {"chain": "hairback_l", "against": "chest", "at": [0, 120], "inward": -1.5, "outward": 7.0, "lower": {"inward": -2.0, "outward": 9.0}}
]

with open("config.json", "w") as f:
    json.dump(cfg, f, indent=2)
print("Saved updated 800x2284 config.json with bust jiggle, stops, and physics limits!")

# 2. Load 4x-AnimeSharp RGBA for Jinni (800x2284) from group_4096x2284_animesharp_rgba.png
grp4_path = os.path.join(FAMILY_DIR, "group_4096x2284_animesharp_rgba.png")
grp4 = np.array(Image.open(grp4_path))
jinni_rgba = grp4[:, 1688:2488, :].copy()
H, W = jinni_rgba.shape[:2]  # 2284, 800

y2_grid, x2_grid = np.mgrid[0:H, 0:W]
rx_2x = x2_grid / 2.0
ry_2x = y2_grid / 2.0

# Analytical smooth top-of-shoulder curve in 1x rig coords (rx -> ry):
shoulder_ctrl_rx = np.array([105.0, 109.5, 111.5, 113.5, 116.0, 119.5, 124.0, 130.0, 138.0, 145.0, 152.0, 159.0, 168.0, 204.0])
shoulder_ctrl_ry = np.array([322.0, 317.5, 312.0, 305.0, 298.0, 292.0, 288.2, 287.5, 287.5, 286.2, 282.5, 278.0, 276.8, 276.8])
smooth_sh_ry_2x = np.interp(rx_2x, shoulder_ctrl_rx, shoulder_ctrl_ry)

dark_hair_ref_2x = (rx_2x >= 115) & (rx_2x <= 165) & (ry_2x >= 240) & (ry_2x <= 290) & (jinni_rgba[:, :, 3] > 220) & (jinni_rgba[:, :, 0] < 75)
_, dh2_idx = distance_transform_edt(~dark_hair_ref_2x, return_indices=True)
above_sh_wisp_2x = (rx_2x >= 112) & (rx_2x <= 158) & (ry_2x >= 265) & (ry_2x < smooth_sh_ry_2x - 0.3) & (jinni_rgba[:, :, 3] > 0) & (jinni_rgba[:, :, 0] > 75)
for c in range(3):
    jinni_rgba[:, :, c] = np.where(above_sh_wisp_2x, jinni_rgba[:, :, c][dh2_idx[0], dh2_idx[1]], jinni_rgba[:, :, c])

outside_sh_left_2x = (rx_2x < 126) & (ry_2x >= 280) & (ry_2x <= 314.5) & (ry_2x < smooth_sh_ry_2x - 0.6)
jinni_rgba[outside_sh_left_2x, 3] = 0

alpha = jinni_rgba[:, :, 3]
solid = alpha > 230
dist, indices = distance_transform_edt(~solid, return_indices=True)
bled_rgb = jinni_rgba[:, :, :3].copy()
for c in range(3):
    bled_rgb[:, :, c] = jinni_rgba[:, :, c][indices[0], indices[1]]

painting = np.full((H, W, 3), 255, dtype=np.uint8)
fig_mask = alpha > 96
painting[fig_mask] = bled_rgb[fig_mask]
Image.fromarray(painting, "RGB").save("inputs/painting.png")
print("Saved cleaned 800x2284 4x-AnimeSharp inputs/painting.png!")

os.system("rm -rf inputs/layers/full inputs/layers/head && cp -r inputs/layers/full_orig inputs/layers/full && cp -r inputs/layers/head_orig inputs/layers/head")

with open("inputs/layers/full_orig/layers.json") as f:
    full_meta = json.load(f)
with open("inputs/layers/head_orig/layers.json") as f:
    head_meta = json.load(f)

def load_layer_canvas(run_dir, meta, name):
    entry = [l for l in meta["layers"] if l["name"] == name][0]
    im = Image.open(f"{run_dir}/parts/{name}.png").convert("RGBA")
    canvas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    canvas.paste(im, (entry["left"], entry["top"]))
    return np.array(canvas)

def save_layer_canvas(run_dir, meta, name, canvas_arr):
    entry = [l for l in meta["layers"] if l["name"] == name][0]
    ys, xs = np.where(canvas_arr[:, :, 3] > 0)
    if len(xs) == 0:
        l, t, r, b = entry["left"], entry["top"], entry["right"], entry["bottom"]
    else:
        l, t, r, b = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
    entry["left"], entry["top"], entry["right"], entry["bottom"] = l, t, r, b
    crop = Image.fromarray(canvas_arr[t:b, l:r], "RGBA")
    crop.save(f"{run_dir}/parts/{name}.png")
    root_f = os.path.join(run_dir, entry["filename"])
    if os.path.exists(root_f):
        crop.save(root_f)

fy_grid, fx_grid = np.mgrid[0:1024, 0:1024]
full_rx = fx_grid * (1142.0 / 1024.0) - 371.0
full_ry = fy_grid * (1142.0 / 1024.0)

hy_grid, hx_grid = np.mgrid[0:1024, 0:1024]
head_rx = hx_grid * (205.0 / 1024.0) + 95.0
head_ry = hy_grid * (205.0 / 1024.0) + 114.0

pad_src = Image.new("RGBA", (2284, 2284), (255, 255, 255, 0))
jinni_clean_rgba = jinni_rgba.copy()
jinni_clean_rgba[:, :, :3] = bled_rgb
jinni_clean_rgba[:, :, 3] = np.where(alpha > 64, np.clip((alpha.astype(np.int32) - 48) * 255 // 180, 0, 255), 0).astype(np.uint8)
pad_src.paste(Image.fromarray(jinni_clean_rgba, "RGBA"), (742, 0))
src_full_1024 = np.array(pad_src.resize((1024, 1024), Image.LANCZOS))

head_crop_src = Image.fromarray(jinni_clean_rgba[228:638, 190:600], "RGBA").resize((1024, 1024), Image.LANCZOS)
src_head_1024 = np.array(head_crop_src)

# =========================================================================
# FIX 1, 2 & 3: Ear/Temple, Right Shoulder Noise, and Neck-to-Topwear Hole
# =========================================================================
head_fh = load_layer_canvas("inputs/layers/head_orig", head_meta, "front hair")
full_fh = load_layer_canvas("inputs/layers/full_orig", full_meta, "front hair")
full_face = load_layer_canvas("inputs/layers/full_orig", full_meta, "face")
head_ear_r = load_layer_canvas("inputs/layers/head_orig", head_meta, "ears-r")
full_tw = load_layer_canvas("inputs/layers/full_orig", full_meta, "topwear")
full_hwr = load_layer_canvas("inputs/layers/full_orig", full_meta, "handwear-r")
full_hwr_orig = full_hwr.copy()
full_bh = load_layer_canvas("inputs/layers/full_orig", full_meta, "back hair")
head_neck = load_layer_canvas("inputs/layers/head_orig", head_meta, "neck")
full_nw = load_layer_canvas("inputs/layers/full_orig", full_meta, "neckwear")

src_h_rgb = src_head_1024[:, :, :3].astype(np.float32)
src_f_rgb = src_full_1024[:, :, :3].astype(np.float32)
luma_h = 0.299 * src_h_rgb[:, :, 0] + 0.587 * src_h_rgb[:, :, 1] + 0.114 * src_h_rgb[:, :, 2]
luma_f = 0.299 * src_f_rgb[:, :, 0] + 0.587 * src_f_rgb[:, :, 1] + 0.114 * src_f_rgb[:, :, 2]

is_pure_skin_h = (src_h_rgb[:, :, 0] > 145) & ((src_h_rgb[:, :, 0] - src_h_rgb[:, :, 2]) > 20) & (src_head_1024[:, :, 3] > 200)
is_pure_skin_h = binary_erosion(is_pure_skin_h, iterations=2)
_, idx_skin_h = distance_transform_edt(~is_pure_skin_h, return_indices=True)
clean_skin_h = src_h_rgb[idx_skin_h[0], idx_skin_h[1]].copy()
for c in range(3):
    blurred_c = gaussian_filter(clean_skin_h[:, :, c], sigma=4.5)
    clean_skin_h[:, :, c] = np.where(is_pure_skin_h, src_h_rgb[:, :, c], blurred_c)

is_pure_skin_f = (src_f_rgb[:, :, 0] > 145) & ((src_f_rgb[:, :, 0] - src_f_rgb[:, :, 2]) > 20) & (src_full_1024[:, :, 3] > 200) & (full_ry < 322)
is_pure_skin_f = binary_erosion(is_pure_skin_f, iterations=1)
_, idx_skin_f = distance_transform_edt(~is_pure_skin_f, return_indices=True)
clean_skin_f = src_f_rgb[idx_skin_f[0], idx_skin_f[1]].copy()
for c in range(3):
    blurred_c = gaussian_filter(clean_skin_f[:, :, c], sigma=2.2)
    clean_skin_f[:, :, c] = np.where(is_pure_skin_f, src_f_rgb[:, :, c], blurred_c)

face_ear_zone = (full_rx >= 150) & (full_rx <= 185) & (full_ry >= 175) & (full_ry <= 245) & (full_face[:, :, 3] > 0)
for c in range(3):
    full_face[:, :, c] = np.where(face_ear_zone, np.clip(np.round(clean_skin_f[:, :, c]), 0, 255).astype(np.uint8), full_face[:, :, c])

ear_inner_zone = (head_ear_r[:, :, 3] > 0) & (head_rx >= 161.5)
for c in range(3):
    head_ear_r[:, :, c] = np.where(ear_inner_zone, np.clip(np.round(clean_skin_h[:, :, c]), 0, 255).astype(np.uint8), head_ear_r[:, :, c])
ear_trim = (head_rx >= 166.5) & (head_ry <= 205)
head_ear_r[ear_trim, 3] = 0

# =========================================================================
# FILL NECK-TO-SHOULDER SKIN BRIDGE WITHOUT CROSSING INTO BACK HAIR (LEFT OR RIGHT)!
# =========================================================================
true_neck_left_x_h = np.interp(head_ry, [215.0, 240.0, 260.0, 275.0, 284.0, 292.0], [170.0, 167.0, 165.0, 162.5, 158.0, 154.0])
true_neck_right_x_h = np.interp(head_ry, [215.0, 250.0, 262.0, 268.0, 276.0, 284.0, 292.0], [204.0, 202.5, 199.5, 197.2, 196.6, 197.2, 198.5])
neck_bridge_h = (head_ry >= 230.0) & (head_ry <= 292.0) & (head_rx >= true_neck_left_x_h) & (head_rx <= true_neck_right_x_h)
head_neck[:, :, 3] = np.where(neck_bridge_h, np.maximum(head_neck[:, :, 3], 255), head_neck[:, :, 3])
head_neck[head_rx < (true_neck_left_x_h - 0.3), 3] = 0
head_neck[(head_ry >= 245.0) & (head_rx > true_neck_right_x_h), 3] = 0
for c in range(3):
    head_neck[:, :, c] = np.where(head_neck[:, :, 3] > 0, np.clip(np.round(clean_skin_h[:, :, c]), 0, 255).astype(np.uint8), head_neck[:, :, c])

# Smooth bare right shoulder & neck-base on `full:topwear` (`full_tw`):
shoulder_ctrl_rx_tw = np.array([105.0, 109.5, 111.5, 113.5, 116.0, 119.5, 124.0, 130.0, 138.0, 145.0, 152.0, 159.0, 166.0, 204.0])
shoulder_ctrl_ry_tw = np.array([322.0, 317.5, 312.0, 305.0, 298.0, 292.0, 288.2, 287.5, 287.5, 286.2, 283.5, 283.0, 283.0, 283.0])
smooth_sh_ry_f = gaussian_filter(np.interp(full_rx, shoulder_ctrl_rx_tw, shoulder_ctrl_ry_tw), sigma=1.2)

erase_hwr_skin = (full_ry < 318.0) & ((full_hwr[:, :, 0] > 95) | (full_ry < 314.5))
full_hwr[erase_hwr_skin] = 0

sh_signed_dist = full_ry - smooth_sh_ry_f
left_edge_rx = np.interp(full_ry, [285.0, 300.0, 310.0, 318.0], [116.0, 114.0, 111.8, 109.5])
left_signed_dist = (full_rx - left_edge_rx) * 2.2
combined_inside = np.minimum(sh_signed_dist, left_signed_dist)
ramp_width = np.where(full_rx >= 160.0, 4.0, 1.4)
smooth_sh_alpha = np.clip((combined_inside + 0.5 * ramp_width) / ramp_width, 0.0, 1.0)
smooth_sh_alpha_u8 = np.round(smooth_sh_alpha * 255.0).astype(np.uint8)

full_tw[full_ry < 279.0, 3] = 0
sh_apply_mask = (full_rx >= 105.0) & (full_rx <= 198.5) & (full_ry >= 279.0) & (full_ry <= 318.0)
full_tw[:, :, 3] = np.where(sh_apply_mask, smooth_sh_alpha_u8, full_tw[:, :, 3])

tw_skin_zone = (full_rx >= 108.0) & (full_rx <= 215.0) & (full_ry >= 272.0) & (full_ry <= 318.0)
is_real_necklace = (full_nw[:, :, 3] > 40) & (full_rx >= 170.0) & (full_ry >= 280.0) & ((src_f_rgb[:, :, 0] - src_f_rgb[:, :, 2]) <= 22)
for c in range(3):
    target_tw_c = np.where(is_real_necklace, src_f_rgb[:, :, c], clean_skin_f[:, :, c])
    full_tw[:, :, c] = np.where(tw_skin_zone, np.clip(np.round(target_tw_c), 0, 255).astype(np.uint8), full_tw[:, :, c])

# =========================================================================
# INCLUDE THE COMPLETE NECKLINE HAIR CURL IN `head:front hair` WITH DEFRINGED DARK HAIR RGB!
# =========================================================================
ear_helix_protect = (head_rx >= 153) & (head_rx <= 166.5) & (head_ry >= 195) & (head_ry <= 230) & (head_ear_r[:, :, 3] > 180) & (luma_h > 95)
temple_zone_h = (head_rx >= 163) & (head_rx <= 176.5) & (head_ry >= 188) & (head_ry <= 215) & (~ear_helix_protect)

smooth_sh_ry_h = np.interp(head_rx, shoulder_ctrl_rx, shoulder_ctrl_ry)
upper_strand_h = (head_ry >= 215.0) & (head_ry <= 278.0) & (head_rx >= (true_neck_left_x_h - 1.2)) & (head_rx <= 172.0)
lower_curl_h = (head_ry >= 274.0) & (head_ry <= 292.0) & (head_rx >= 138.0) & (head_rx <= 171.0) & (head_ry >= (smooth_sh_ry_h - 1.5))
strand_zone_h = upper_strand_h | lower_curl_h

unmix_zone_h = (temple_zone_h | strand_zone_h) & (src_head_1024[:, :, 3] > 128)

skin_luma_h = 0.299 * clean_skin_h[:, :, 0] + 0.587 * clean_skin_h[:, :, 1] + 0.114 * clean_skin_h[:, :, 2]
hair_ref_luma = 36.0
raw_alpha = np.clip((skin_luma_h - luma_h) / np.maximum(skin_luma_h - hair_ref_luma, 25.0), 0.0, 1.0)
raw_alpha = np.where(raw_alpha < 0.06, 0.0, raw_alpha)

diff_from_skin_h = np.max(np.abs(src_h_rgb - clean_skin_h), axis=2)
already_solid_bang = (head_fh[:, :, 3] >= 250) & (luma_h < 65) & (head_ry < 196)
is_solid_strand = already_solid_bang | (unmix_zone_h & (diff_from_skin_h > 48.0))
unmix_alpha_u8 = np.where(is_solid_strand, 252, np.clip(np.round(raw_alpha * 245.0), 0, 245)).astype(np.uint8)

alpha_f = np.maximum(raw_alpha, 0.25)
for c in range(3):
    c_unmix = (src_h_rgb[:, :, c] - (1.0 - alpha_f) * clean_skin_h[:, :, c]) / alpha_f
    c_core = np.maximum(src_h_rgb[:, :, c] - 32.0, np.clip(c_unmix, 24.0, 75.0))
    c_hair = np.where(unmix_alpha_u8 >= 250, c_core, np.clip(c_unmix, 24.0, 70.0))
    c_hair_u8 = np.clip(np.round(c_hair), 0, 255).astype(np.uint8)
    head_fh[:, :, c] = np.where(unmix_zone_h & (unmix_alpha_u8 > 0), c_hair_u8, head_fh[:, :, c])

head_fh[:, :, 3] = np.where(unmix_zone_h, unmix_alpha_u8, head_fh[:, :, 3])

clear_outside_strand = (head_rx < 172.0) & (head_ry > 212.0) & (~unmix_zone_h)
head_fh[clear_outside_strand, 3] = 0

shield_f = (full_rx >= 136.0) & (full_rx <= 174.0) & (full_ry >= 258.0) & (full_ry <= 295.0) & (luma_f < 165.0)
full_fh[:, :, 3] = np.where(shield_f, 255, full_fh[:, :, 3])

pink_fh_cleanup = (head_rx >= 152) & (head_rx <= 185) & (head_ry >= 175) & (head_ry <= 225) & (~unmix_zone_h) & (head_fh[:, :, 3] > 0) & (head_fh[:, :, 0] > 85)
pure_dark_h = (src_head_1024[:, :, 0] < 70) & (src_head_1024[:, :, 3] > 200)
_, dh_idx = distance_transform_edt(~pure_dark_h, return_indices=True)
for c in range(3):
    nearest_dark = src_head_1024[:, :, c][dh_idx[0], dh_idx[1]]
    head_fh[:, :, c] = np.where(pink_fh_cleanup, nearest_dark, head_fh[:, :, c])
head_fh[pink_fh_cleanup, 3] = np.minimum(head_fh[pink_fh_cleanup, 3], 240)

bh_clean_zone = (full_rx >= 110) & (full_rx <= 175) & (full_ry >= 180) & (full_ry <= 300)
core_bh_dark = bh_clean_zone & (src_full_1024[:, :, 0] < 70) & (src_full_1024[:, :, 3] > 200)
_, bh_idx = distance_transform_edt(~core_bh_dark, return_indices=True)
for c in range(3):
    nearest_dark_c = src_full_1024[:, :, c][bh_idx[0], bh_idx[1]]
    full_bh[:, :, c] = np.where(bh_clean_zone & (full_bh[:, :, 3] > 0) & (full_bh[:, :, 0] > 80), nearest_dark_c, full_bh[:, :, c])

for h_tag in ["nose", "mouth", "eyewhite-r", "eyewhite-l", "irides-r", "irides-l", "eyelash-r", "eyelash-l", "ears-l", "earwear"]:
    arr = load_layer_canvas("inputs/layers/head_orig", head_meta, h_tag)
    if h_tag != "earwear":
        vis_px = (arr[:, :, 3] > 0) & (head_fh[:, :, 3] < 120)
        for c in range(3):
            arr[:, :, c] = np.where(vis_px, src_head_1024[:, :, c], arr[:, :, c])
    save_layer_canvas("inputs/layers/head", head_meta, h_tag, arr)

for f_tag in ["eyebrow-r", "eyebrow-l", "neckwear"]:
    arr = load_layer_canvas("inputs/layers/full_orig", full_meta, f_tag)
    vis_px = (arr[:, :, 3] > 0) & (src_full_1024[:, :, 3] > 64)
    for c in range(3):
        arr[:, :, c] = np.where(vis_px, src_full_1024[:, :, c], arr[:, :, c])
    arr[:, :, 3] = np.minimum(arr[:, :, 3], src_full_1024[:, :, 3])
    save_layer_canvas("inputs/layers/full", full_meta, f_tag, arr)

# =========================================================================
# FIX ISSUE #1 COMPLETELY: Preserve Qwen's clean diagonal skirt pleats under `handwear_r` & prevent `seamOverride` from stamping the hand border!
# =========================================================================
full_bw = load_layer_canvas("inputs/layers/full_orig", full_meta, "bottomwear")
bw_orig_rgb = full_bw[:, :, :3].astype(np.float32)

hwr_arm_zone = binary_dilation(full_hwr_orig[:, :, 3] > 4, iterations=8)
tw_occ = binary_dilation(full_tw[:, :, 3] > 128, iterations=3)
keep_orig_pleats = hwr_arm_zone | tw_occ
pleat_blend_w = gaussian_filter((~keep_orig_pleats).astype(np.float32), sigma=3.5)

for c in range(3):
    blended_bw_c = pleat_blend_w * src_f_rgb[:, :, c] + (1.0 - pleat_blend_w) * bw_orig_rgb[:, :, c]
    full_bw[:, :, c] = np.where(full_bw[:, :, 3] > 0, np.clip(np.round(blended_bw_c), 0, 255).astype(np.uint8), full_bw[:, :, c])

full_bw[:, :, 3] = np.minimum(full_bw[:, :, 3], src_full_1024[:, :, 3])

diff_bw_paint = np.max(np.abs(full_bw[:, :, :3].astype(np.float32) - src_f_rgb), axis=2)
hwr_solid_core = (full_ry >= 375.0) & ((full_hwr_orig[:, :, 3] >= 110) | ((full_hwr_orig[:, :, 3] >= 36) & (diff_bw_paint > 52.0)))
full_hwr[:, :, 3] = np.where(hwr_solid_core, 252, full_hwr[:, :, 3])
full_hwr[(full_ry >= 375.0) & (full_hwr_orig[:, :, 3] < 36)] = 0

full_neck = load_layer_canvas("inputs/layers/full_orig", full_meta, "neck")
full_neck[:, :, 3] = np.where(hwr_arm_zone & (full_ry >= 375.0), 255, full_neck[:, :, 3])
save_layer_canvas("inputs/layers/full", full_meta, "neck", full_neck)
save_layer_canvas("inputs/layers/full", full_meta, "bottomwear", full_bw)

full_hwl = load_layer_canvas("inputs/layers/full_orig", full_meta, "handwear-l")
full_hwl[full_rx < 246.0] = 0
cuff_cut_ry = np.interp(full_rx, [246.0, 255.0, 262.5, 266.0], [322.0, 315.0, 311.5, 305.0])
full_hwl[(full_rx < 265.0) & (full_ry < cuff_cut_ry)] = 0
hwl_vis = (full_hwl[:, :, 3] > 0) & (~tw_occ) & (full_bw[:, :, 3] < 128) & (src_full_1024[:, :, 3] > 64)
for c in range(3):
    full_hwl[:, :, c] = np.where(hwl_vis, src_full_1024[:, :, c], full_hwl[:, :, c])
full_hwl[:, :, 3] = np.minimum(full_hwl[:, :, 3], src_full_1024[:, :, 3])
save_layer_canvas("inputs/layers/full", full_meta, "handwear-l", full_hwl)

# =========================================================================
# FIX 3, 4 & 5: Ankle step, High-heel shoe, Calf silhouette & Earring
# =========================================================================
full_leg = load_layer_canvas("inputs/layers/full_orig", full_meta, "legwear")
full_shoe = load_layer_canvas("inputs/layers/full_orig", full_meta, "footwear")

foot_zone = (full_ry >= 900)
is_skin_src = foot_zone & (src_full_1024[:, :, 3] > 64) & (src_full_1024[:, :, 0] > 150) & ((src_full_1024[:, :, 0].astype(int) - src_full_1024[:, :, 2].astype(int)) > 28)
is_shoe_src = foot_zone & (src_full_1024[:, :, 3] > 64) & (~is_skin_src)

skin_overlap_into_shoe = binary_dilation(is_skin_src, iterations=2) & binary_erosion(is_shoe_src, iterations=1)
leg_foot_mask = is_skin_src | skin_overlap_into_shoe

skin_dist, skin_idx = distance_transform_edt(~is_skin_src, return_indices=True)
full_leg[foot_zone] = 0
for c in range(3):
    nearest_skin_c = src_full_1024[:, :, c][skin_idx[0], skin_idx[1]]
    full_leg[:, :, c] = np.where(leg_foot_mask, nearest_skin_c, full_leg[:, :, c])
full_leg[:, :, 3] = np.where(leg_foot_mask, src_full_1024[:, :, 3], full_leg[:, :, 3])
full_leg[:, :, 3] = np.minimum(full_leg[:, :, 3], src_full_1024[:, :, 3])

calf_zone = (full_ry >= 690) & (full_ry < 900)
is_calf_skin = calf_zone & (src_full_1024[:, :, 3] > 64) & (src_full_1024[:, :, 0] > 140)
_, calf_idx = distance_transform_edt(~is_calf_skin, return_indices=True)
for c in range(3):
    nearest_calf_c = src_full_1024[:, :, c][calf_idx[0], calf_idx[1]]
    full_leg[:, :, c] = np.where(calf_zone & (full_leg[:, :, 3] > 0), nearest_calf_c, full_leg[:, :, c])
full_leg[:, :, 3] = np.where(calf_zone, np.minimum(full_leg[:, :, 3], src_full_1024[:, :, 3]), full_leg[:, :, 3])

full_shoe[:, :, :] = 0
for c in range(3):
    full_shoe[:, :, c] = np.where(is_shoe_src, src_full_1024[:, :, c], 0)
full_shoe[:, :, 3] = np.where(is_shoe_src, src_full_1024[:, :, 3], 0)

save_layer_canvas("inputs/layers/full", full_meta, "legwear", full_leg)
save_layer_canvas("inputs/layers/full", full_meta, "footwear", full_shoe)

full_earwear = load_layer_canvas("inputs/layers/full_orig", full_meta, "earwear")
ew_mask = full_earwear[:, :, 3] > 16
for c in range(3):
    full_earwear[:, :, c] = np.where(ew_mask, src_full_1024[:, :, c], 0)
bead_core = (full_earwear[:, :, 3] > 90) & (luma_f > 52)
full_earwear[:, :, 3] = np.where(bead_core, 252, full_earwear[:, :, 3])
save_layer_canvas("inputs/layers/full", full_meta, "earwear", full_earwear)

# =========================================================================
# FIX 6: Full 4x-AnimeSharp edge sharpness across Bangs, Jawline, Collar & Topwear
# =========================================================================
fh_in_full_1142 = Image.new("L", (2284, 2284), 0)
fh_rig_crop = Image.fromarray(head_fh[:, :, 3], "L").resize((410, 410), Image.BILINEAR)
fh_in_full_1142.paste(fh_rig_crop, (742 + 190, 228))
fh_in_full_1024 = np.array(fh_in_full_1142.resize((1024, 1024), Image.BILINEAR))

forehead_under_bangs = (full_rx >= 150) & (full_rx <= 268) & (full_ry >= 165) & (full_ry <= 242) & (full_face[:, :, 3] > 0) & (fh_in_full_1024 > 24)
for c in range(3):
    full_face[:, :, c] = np.where(forehead_under_bangs, np.clip(np.round(clean_skin_f[:, :, c]), 0, 255).astype(np.uint8), full_face[:, :, c])

jaw_zone = (full_ry >= 215) & (full_face[:, :, 3] > 0) & (fh_in_full_1024 <= 24)
for c in range(3):
    full_face[:, :, c] = np.where(jaw_zone, src_full_1024[:, :, c], full_face[:, :, c])
jaw_rim_dark = (full_ry >= 225) & (full_face[:, :, 3] > 0) & (full_face[:, :, 3] < 250) & (luma_f < 125)
jaw_scale = np.clip((luma_f - 45.0) / 80.0, 0.0, 1.0)
full_face[:, :, 3] = np.where(jaw_rim_dark, np.round(full_face[:, :, 3] * jaw_scale).astype(np.uint8), full_face[:, :, 3])

bangs_fringe_zone = (head_rx >= 165) & (head_rx <= 268) & (head_ry >= 170) & (head_ry <= 240) & (head_fh[:, :, 3] > 0) & (~unmix_zone_h)
bangs_solid = bangs_fringe_zone & (head_fh[:, :, 3] >= 245) & (luma_h < 95)
for c in range(3):
    head_fh[:, :, c] = np.where(bangs_solid, src_head_1024[:, :, c], head_fh[:, :, c])

bangs_rim = bangs_fringe_zone & (~bangs_solid)
bang_raw_a = np.clip((skin_luma_h - luma_h) / np.maximum(skin_luma_h - 38.0, 25.0), 0.0, 1.0)
bang_raw_a = np.where(bang_raw_a < 0.08, 0.0, bang_raw_a)
bang_new_a = np.minimum(head_fh[:, :, 3], np.clip(np.round(bang_raw_a * 248.0), 0, 248).astype(np.uint8))
for c in range(3):
    nearest_dark = src_head_1024[:, :, c][dh_idx[0], dh_idx[1]]
    c_val = np.where(luma_h < 85, src_head_1024[:, :, c], nearest_dark)
    head_fh[:, :, c] = np.where(bangs_rim, c_val, head_fh[:, :, c])
head_fh[:, :, 3] = np.where(bangs_rim, bang_new_a, head_fh[:, :, 3])

hwr_pure_interior = (full_hwr_orig[:, :, 3] >= 205) & (src_full_1024[:, :, 3] > 200)
_, hwr_int_idx = distance_transform_edt(~hwr_pure_interior, return_indices=True)
hwr_over_bw_fringe = (full_hwr[:, :, 3] > 0) & (full_bw[:, :, 3] > 32) & (full_hwr_orig[:, :, 3] < 205)

for c in range(3):
    tw_cloth_vis = (full_tw[:, :, 3] > 0) & (full_ry >= 316.0) & (~hwr_arm_zone)
    full_tw[:, :, c] = np.where(tw_cloth_vis & (src_full_1024[:, :, 3] > 128), src_full_1024[:, :, c], full_tw[:, :, c])
    nearest_hwr_c = src_full_1024[:, :, c].astype(np.float32)[hwr_int_idx[0], hwr_int_idx[1]]
    src_c_f = src_full_1024[:, :, c].astype(np.float32)
    decontam_c = np.clip(nearest_hwr_c, src_c_f - 42.0, src_c_f + 42.0).astype(np.uint8)
    target_hwr_c = np.where(hwr_over_bw_fringe, decontam_c, src_full_1024[:, :, c])
    full_hwr[:, :, c] = np.where((full_hwr[:, :, 3] > 0) & (src_full_1024[:, :, 3] > 128), target_hwr_c, full_hwr[:, :, c])

for arr in [full_hwr, full_bh]:
    arr[:, :, 3] = np.minimum(arr[:, :, 3], src_full_1024[:, :, 3])
tw_clamp_zone = ~((full_rx >= 109.0) & (full_rx <= 198.5) & (full_ry >= 274.0) & (full_ry <= 318.0))
full_tw[:, :, 3] = np.where(tw_clamp_zone, np.minimum(full_tw[:, :, 3], src_full_1024[:, :, 3]), full_tw[:, :, 3])
head_fh[:, :, 3] = np.minimum(head_fh[:, :, 3], src_head_1024[:, :, 3])

save_layer_canvas("inputs/layers/head", head_meta, "front hair", head_fh)
save_layer_canvas("inputs/layers/full", full_meta, "front hair", full_fh)
save_layer_canvas("inputs/layers/full", full_meta, "face", full_face)
save_layer_canvas("inputs/layers/head", head_meta, "ears-r", head_ear_r)
save_layer_canvas("inputs/layers/full", full_meta, "topwear", full_tw)
save_layer_canvas("inputs/layers/full", full_meta, "handwear-r", full_hwr)
save_layer_canvas("inputs/layers/full", full_meta, "back hair", full_bh)
save_layer_canvas("inputs/layers/head", head_meta, "neck", head_neck)

with open("inputs/layers/full/layers.json", "w") as f:
    json.dump(full_meta, f, indent=2)
with open("inputs/layers/head/layers.json", "w") as f:
    json.dump(head_meta, f, indent=2)
print("All fixes & breast jiggle applied to 4x-AnimeSharp layers!")
