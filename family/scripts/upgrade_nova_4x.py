#!/usr/bin/env python3
"""
upgrade_nova_4x.py
Refines Nova's 4x-AnimeSharp (800x2284) rig layers and builds config.json:
  1. Cleans unused ghost layers in `full` and `head` runs
  2. Strips white V-neck inner shirt and dark navy blazer shoulders from `head:back hair` so moving hair never tears the torso, and restores the full V-neck shirt onto `full:topwear`
  3. Decontaminates `painting.png`, `topwear`, and `bottomwear` (trousers) edges — removing the bright pocket near the right arm/hip `(518, 1323)` and inner-leg seam so zero white dots appear
  4. Extends `head:neck` with a 14px under-tuck under the blazer collar
  5. Removes trousers physics (`bottomwear` -> `hip`) and adds subtle physics chains (`hem_r`, `hem_l`) to the lower blazer hem (`topwear`)
  6. Configures 3D-like dome contour falloff on `bust_r`/`bust_l` and desynchronized eye blink timing
"""
import os
import json
from PIL import Image
import numpy as np
from scipy.ndimage import distance_transform_edt, binary_dilation, binary_erosion, gaussian_filter

FAMILY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOVA_DIR = os.path.join(FAMILY_DIR, "nova")
os.chdir(NOVA_DIR)

# 1. Load clean 4x RGBA crop of Nova from group_4096x2284_animesharp_rgba.png (x = 3296..4096)
group_im = Image.open("../group_4096x2284_animesharp_rgba.png").convert("RGBA").crop((3296, 0, 4096, 2284))
rgba = np.array(group_im)
H, W = rgba.shape[:2]  # 2284, 800
yy, xx = np.mgrid[0:H, 0:W]

alpha_4x = rgba[:, :, 3].copy()
luma_4x = (
    0.299 * rgba[:, :, 0].astype(np.float32) +
    0.587 * rgba[:, :, 1].astype(np.float32) +
    0.114 * rgba[:, :, 2].astype(np.float32)
)
rb_4x = rgba[:, :, 0].astype(int) - rgba[:, :, 2].astype(int)
rg_4x = rgba[:, :, 0].astype(int) - rgba[:, :, 1].astype(int)

# Trim bright background pockets along the dark blazer & trousers silhouette (e.g., (518, 1323) and inner-leg gap)
rim_4x = (alpha_4x > 0) & (~binary_erosion(alpha_4x >= 240, iterations=5))
inner_shirt_or_neck = (xx >= 285) & (xx <= 495) & (yy >= 480) & (yy <= 710)
peeking_hands = ((xx >= 230) & (xx <= 285) & (yy >= 990) & (yy <= 1075)) | ((xx >= 475) & (xx <= 555) & (yy >= 940) & (yy <= 1045))
ankles_zone = (yy >= 2035)
orange_hair_4x = (yy <= 760) & (rgba[:, :, 0] >= 125) & (rb_4x >= 42) & (rg_4x >= 18)

bright_garment_rim = (
    rim_4x & (yy >= 540) &
    (~inner_shirt_or_neck) & (~peeking_hands) & (~ankles_zone) & (~orange_hair_4x) &
    (luma_4x > 84)
)
rgba[bright_garment_rim, 3] = 0
alpha_4x = rgba[:, :, 3].copy()

# Build decontaminated `bled_painting`: preserve 100% of interior opaque pixels (`interior_opaque`)
# so Nova's white shirt, purple vest, brooch, and left hand on her waist are never altered!
interior_opaque = binary_erosion(alpha_4x >= 240, iterations=3)
dark_garment_band = (yy >= 540) & (~inner_shirt_or_neck) & (~peeking_hands) & (~ankles_zone) & (~orange_hair_4x)
core_4x = interior_opaque | (binary_erosion(alpha_4x >= 235, iterations=1) & ((~dark_garment_band) | (luma_4x < 75)))
_, core_idx = distance_transform_edt(~core_4x, return_indices=True)
bled_painting = rgba[:, :, :3].copy()
for c in range(3):
    bled_painting[:, :, c] = np.where(core_4x, rgba[:, :, c], rgba[:, :, c][core_idx[0], core_idx[1]])
    rgba[:, :, c] = np.where(alpha_4x >= 230, rgba[:, :, c], np.where(alpha_4x > 0, bled_painting[:, :, c], 255))

# IMPORTANT: Keep interior holes (the enclosed arm hole at x=505..595, y=740..925 and the narrow leg gap at x=340..390, y=1360..2045)
# filled with `bled_painting` (dark navy) in `painting.png` instead of `[255, 255, 255]`, because `figureSilhouette` flood-fills from
# the outer canvas border and treats enclosed holes as interior — setting `[255, 255, 255]` inside interior holes causes `projectSource`
# to stamp white specks onto the inner hole edges!
interior_hole_zone = (
    ((xx >= 505) & (xx <= 595) & (yy >= 740) & (yy <= 925)) |
    ((xx >= 340) & (xx <= 390) & (yy >= 1360) & (yy <= 2045))
)
painting = bled_painting.copy()
painting[(alpha_4x < 210) & (~interior_hole_zone)] = [255, 255, 255]
Image.fromarray(rgba, "RGBA").save("inputs/painting_rgba.png")
Image.fromarray(painting, "RGB").save("inputs/painting.png")

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
        l, t, r, b = 0, 0, 1, 1
        crop = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    else:
        l, t, r, b = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
        crop = Image.fromarray(canvas_arr[t:b, l:r], "RGBA")
    entry["left"], entry["top"], entry["right"], entry["bottom"] = l, t, r, b
    crop.save(f"{run_dir}/parts/{name}.png")

def prefill_rgb(arr, core_mask=None):
    if core_mask is None:
        core = binary_erosion(arr[:, :, 3] > 215, iterations=2)
    else:
        core = core_mask
    if not np.any(core):
        core = arr[:, :, 3] > 180
    if not np.any(core):
        core = arr[:, :, 3] > 16
    if not np.any(core):
        return arr
    _, idx = distance_transform_edt(~core, return_indices=True)
    for c in range(3):
        arr[:, :, c] = np.where(core, arr[:, :, c], arr[:, :, c][idx[0], idx[1]])
    return arr

# Coordinate grids between 1024x1024 runs and 800x2284 rig space
fy_grid, fx_grid = np.mgrid[0:1024, 0:1024]
full_rx = (fx_grid + 0.5) * (2284.0 / 1024.0) - 742.0
full_ry = (fy_grid + 0.5) * (2284.0 / 1024.0)

full_rx_clamped = np.clip(np.round(full_rx).astype(int), 0, W - 1)
full_ry_clamped = np.clip(np.round(full_ry).astype(int), 0, H - 1)
full_in_bounds = (full_rx >= 0) & (full_rx < W) & (full_ry >= 0) & (full_ry < H)
full_src_rgb = rgba[full_ry_clamped, full_rx_clamped, :3]
full_src_a = np.where(full_in_bounds, alpha_4x[full_ry_clamped, full_rx_clamped], 0)
full_src_luma = (
    0.299 * full_src_rgb[:, :, 0].astype(np.float32) +
    0.587 * full_src_rgb[:, :, 1].astype(np.float32) +
    0.114 * full_src_rgb[:, :, 2].astype(np.float32)
)

# head_box = [200, 230, 730, 760] (530x530)
hy_grid, hx_grid = np.mgrid[0:1024, 0:1024]
head_rx = 200.0 + (hx_grid + 0.5) * (530.0 / 1024.0)
head_ry = 230.0 + (hy_grid + 0.5) * (530.0 / 1024.0)
head_rx_clamped = np.clip(np.round(head_rx).astype(int), 0, W - 1)
head_ry_clamped = np.clip(np.round(head_ry).astype(int), 0, H - 1)
head_src_rgb = rgba[head_ry_clamped, head_rx_clamped, :3]
head_src_a = alpha_4x[head_ry_clamped, head_rx_clamped]
head_src_luma = (
    0.299 * head_src_rgb[:, :, 0].astype(np.float32) +
    0.587 * head_src_rgb[:, :, 1].astype(np.float32) +
    0.114 * head_src_rgb[:, :, 2].astype(np.float32)
)

os.system("rm -rf inputs/layers/full inputs/layers/head && cp -r inputs/layers/full_orig inputs/layers/full && cp -r inputs/layers/head_orig inputs/layers/head")

# ---------------------------------------------------------
# 1. Clear unused layers in both runs
# ---------------------------------------------------------
used_full = {"footwear", "bottomwear", "topwear", "handwear-l", "front hair"}
for l in full_meta["layers"]:
    if l["name"] not in used_full:
        save_layer_canvas("inputs/layers/full", full_meta, l["name"], np.zeros((1024, 1024, 4), dtype=np.uint8))

used_head = {
    "back hair", "neck", "ears", "face", "irides-r", "mouth",
    "eyebrow-r", "eyelash-r", "nose", "eyewhite-r", "eyewhite-l",
    "irides-l", "eyelash-l", "front hair", "eyebrow-l"
}
for l in head_meta["layers"]:
    if l["name"] not in used_head:
        save_layer_canvas("inputs/layers/head", head_meta, l["name"], np.zeros((1024, 1024, 4), dtype=np.uint8))

# ---------------------------------------------------------
# 2. HEAD:BACK HAIR & HEAD:FRONT HAIR & HEAD:NECK
# ---------------------------------------------------------
h_bh = load_layer_canvas("inputs/layers/head_orig", head_meta, "back hair")
h_fh = load_layer_canvas("inputs/layers/head_orig", head_meta, "front hair")
h_neck = load_layer_canvas("inputs/layers/head_orig", head_meta, "neck")
h_face = load_layer_canvas("inputs/layers/head_orig", head_meta, "face")

# Strip ALL torso pixels (cream/white V-neck shirt and dark navy blazer shoulders) from `head:back hair` and `head:front hair`,
# while keeping 100% of Nova's vibrant orange-red hair curls!
head_rb = head_src_rgb[:, :, 0].astype(int) - head_src_rgb[:, :, 2].astype(int)
head_rg = head_src_rgb[:, :, 0].astype(int) - head_src_rgb[:, :, 1].astype(int)

cream_vneck_in_head = (head_ry >= 525) & (head_src_rgb[:, :, 1] > 140) & (head_src_rgb[:, :, 2] > 125)
neck_skin_center_in_head = (
    (head_ry >= 495) & (head_ry <= 605) & (head_rx >= 398) & (head_rx <= 478) &
    (head_src_rgb[:, :, 1] > 105) & (head_src_rgb[:, :, 2] > 82)
)
is_true_orange_hair = (
    (head_src_a > 96) &
    (head_src_rgb[:, :, 0] >= 118) &
    (head_rb >= 38) &
    (head_rg >= 16) &
    (~cream_vneck_in_head) &
    (~neck_skin_center_in_head)
)

torso_in_hbh = (head_ry >= 510) & (~is_true_orange_hair)
h_bh[torso_in_hbh, 3] = 0
h_bh[head_src_a < 24, 3] = 0
h_bh[(head_rx >= 342) & (head_rx <= 422) & (head_ry >= 582), 3] = 0

orange_hair_zone = is_true_orange_hair & (head_ry >= 250) & (head_ry <= 758) & (~((head_rx >= 342) & (head_rx <= 422) & (head_ry >= 582)))
near_hbh = binary_dilation(h_bh[:, :, 3] > 24, iterations=4) & orange_hair_zone
h_bh[:, :, 3] = np.where(near_hbh, np.maximum(h_bh[:, :, 3], head_src_a), h_bh[:, :, 3])
h_bh[:, :, 3] = np.minimum(h_bh[:, :, 3], head_src_a)
h_bh[(head_ry >= 520) & (h_bh[:, :, 3] < 110), 3] = 0

from scipy.ndimage import label
lbl_nbh, n_nbh = label(h_bh[:, :, 3] > 0)
for cid in range(1, n_nbh + 1):
    comp = lbl_nbh == cid
    if comp.sum() < 350:
        h_bh[comp, 3] = 0

lower_orange_solid = binary_dilation((head_ry >= 515) & (h_bh[:, :, 3] >= 110), iterations=3) & (head_src_a > 200) & (~cream_vneck_in_head) & (~neck_skin_center_in_head)
h_bh[lower_orange_solid, 3] = 255
h_bh[(head_ry >= 515) & (h_bh[:, :, 3] > 0), 3] = 255

bh_occ = binary_dilation((h_fh[:, :, 3] > 64) | (h_face[:, :, 3] > 64), iterations=2)
orange_core = (h_bh[:, :, 3] > 210) & (~bh_occ) & is_true_orange_hair
_, orange_idx = distance_transform_edt(~orange_core, return_indices=True)
for c in range(3):
    h_bh[:, :, c] = np.where(
        (h_bh[:, :, 3] > 0) & (~bh_occ) & is_true_orange_hair,
        head_src_rgb[:, :, c],
        head_src_rgb[:, :, c][orange_idx[0], orange_idx[1]]
    )
h_bh = prefill_rgb(h_bh, core_mask=orange_core)
save_layer_canvas("inputs/layers/head", head_meta, "back hair", h_bh)

h_fh[head_src_a < 16, 3] = 0
h_fh[torso_in_hbh, 3] = 0
h_fh[(head_rx >= 342) & (head_rx <= 422) & (head_ry >= 582), 3] = 0
h_fh[:, :, 3] = np.minimum(h_fh[:, :, 3], head_src_a)
hfh_orange_core = (h_fh[:, :, 3] > 210) & is_true_orange_hair
for c in range(3):
    h_fh[:, :, c] = np.where(
        (h_fh[:, :, 3] > 0) & is_true_orange_hair,
        head_src_rgb[:, :, c],
        head_src_rgb[:, :, c][orange_idx[0], orange_idx[1]]
    )
h_fh = prefill_rgb(h_fh, core_mask=hfh_orange_core)
save_layer_canvas("inputs/layers/head", head_meta, "front hair", h_fh)

# HEAD:NECK — Clean separation & 14px under-tuck under blazer/shirt collar
neck_skin = (
    (head_rx >= 390) & (head_rx <= 495) & (head_ry >= 500) & (head_ry <= 610) &
    (head_src_a > 200) &
    (head_src_rgb[:, :, 0] > 140) & (head_rb > 35)
)
h_neck[(head_ry > 615) | (head_rx < 375), 3] = 0
h_neck[:, :, 3] = np.where(neck_skin, np.maximum(h_neck[:, :, 3], 255), h_neck[:, :, 3])
for c in range(3):
    h_neck[:, :, c] = np.where(neck_skin, head_src_rgb[:, :, c], h_neck[:, :, c])

neck_core = h_neck[:, :, 3] > 200
_, nearest_idx = distance_transform_edt(~neck_core, return_indices=True)
neck_dilated = binary_dilation(neck_core, iterations=12)
under_tuck = neck_dilated & (~neck_core) & (head_ry >= 515) & (head_ry <= 635) & (head_rx >= 380) & (head_rx <= 505)
h_neck[:, :, 3] = np.where(under_tuck, np.maximum(h_neck[:, :, 3], 255), h_neck[:, :, 3])
for c in range(3):
    h_neck[:, :, c] = np.where(under_tuck, h_neck[:, :, c][nearest_idx[0], nearest_idx[1]], h_neck[:, :, c])
h_neck = prefill_rgb(h_neck)
save_layer_canvas("inputs/layers/head", head_meta, "neck", h_neck)

# Facial features & face 4x RGB injection
face_occ = (h_fh[:, :, 3] > 64)
for enm in ["ears", "irides-r", "mouth", "eyebrow-r", "eyelash-r", "nose", "eyewhite-r", "eyewhite-l", "irides-l", "eyelash-l", "eyebrow-l"]:
    el = load_layer_canvas("inputs/layers/head_orig", head_meta, enm)
    face_occ = face_occ | (el[:, :, 3] > 64)
    el_vis = (el[:, :, 3] > 0) & (h_fh[:, :, 3] < 64) & (head_src_a > 96)
    for c in range(3):
        el[:, :, c] = np.where(el_vis, head_src_rgb[:, :, c], el[:, :, c])
    el = prefill_rgb(el)
    save_layer_canvas("inputs/layers/head", head_meta, "ears" if enm == "ears" else enm, el)

occ_face = binary_dilation(face_occ, iterations=2)
w_occ_face = np.where(occ_face, 1.0, gaussian_filter(occ_face.astype(np.float32), sigma=2.0))
for c in range(3):
    qwen_c = h_face[:, :, c].astype(np.float32)
    src_c = head_src_rgb[:, :, c].astype(np.float32)
    h_face[:, :, c] = np.clip(np.round(w_occ_face * qwen_c + (1.0 - w_occ_face) * src_c), 0, 255).astype(np.uint8)
h_face = prefill_rgb(h_face)
save_layer_canvas("inputs/layers/head", head_meta, "face", h_face)

# ---------------------------------------------------------
# 3. FULL LAYERS: TOPWEAR (+HANDWEAR-R & HANDWEAR-L), BOTTOMWEAR (+LEGWEAR), FOOTWEAR
# ---------------------------------------------------------
f_top = load_layer_canvas("inputs/layers/full_orig", full_meta, "topwear")
f_hwr = load_layer_canvas("inputs/layers/full_orig", full_meta, "handwear-r")
f_hwl = load_layer_canvas("inputs/layers/full_orig", full_meta, "handwear-l")
f_bw = load_layer_canvas("inputs/layers/full_orig", full_meta, "bottomwear")
f_lw = load_layer_canvas("inputs/layers/full_orig", full_meta, "legwear")
f_fw = load_layer_canvas("inputs/layers/full_orig", full_meta, "footwear")

# Trim stray red fragments on f_hwr below y=1100
f_hwr[full_ry > 1100, 3] = 0
save_layer_canvas("inputs/layers/full", full_meta, "handwear-l", np.zeros((1024, 1024, 4), dtype=np.uint8))

# Combine alpha of topwear + handwear-r + handwear-l
combined_top_a = np.maximum(np.maximum(f_top[:, :, 3], f_hwr[:, :, 3]), f_hwl[:, :, 3])

# Map cleaned head hair and head neck into full space
h_hair_union = np.maximum(h_fh[:, :, 3], h_bh[:, :, 3])
hair_hx = np.round((full_rx - 200.0) * (1024.0 / 530.0)).astype(int)
hair_hy = np.round((full_ry - 230.0) * (1024.0 / 530.0)).astype(int)
in_head_box = (hair_hx >= 0) & (hair_hx < 1024) & (hair_hy >= 0) & (hair_hy < 1024)
hair_hx_c = np.clip(hair_hx, 0, 1023)
hair_hy_c = np.clip(hair_hy, 0, 1023)
head_hair_in_full_a = np.where(in_head_box, h_hair_union[hair_hy_c, hair_hx_c], 0)
head_neck_in_full_a = np.where(in_head_box, h_neck[hair_hy_c, hair_hx_c, 3], 0)

# Remove warm neck skin at top of f_top ONLY where head:neck is opaque underneath (x = 395..485, y < 608)
neck_in_top = (
    (full_rx >= 395) & (full_rx <= 485) & (full_ry < 608) &
    (head_neck_in_full_a > 220) &
    (full_src_rgb[:, :, 0] > 170) & (full_src_rgb[:, :, 1] > 85) &
    ((full_src_rgb[:, :, 0].astype(int) - full_src_rgb[:, :, 2].astype(int)) > 40)
)

# Refine `topwear` — Trim above the natural sloping blazer shoulder line & fill V-neck + collar cleanly under hair!
blazer_top_y = np.interp(full_rx, [265, 315, 355, 395, 480, 520, 585, 640], [685, 645, 616, 590, 558, 562, 605, 665])

vneck_and_collar = (
    (full_rx >= 285) & (full_rx <= 535) & (full_ry >= blazer_top_y) & (full_ry <= 715) &
    (~neck_in_top) & (full_src_a > 180)
)

top_zone = (full_rx >= 230) & (full_rx <= 695) & (full_ry >= blazer_top_y) & (full_ry <= 1300) & (~neck_in_top)
near_top = binary_dilation(combined_top_a > 16, iterations=4) & top_zone & (full_src_a > 160) & (head_hair_in_full_a < 64)
f_top[:, :, 3] = np.where(near_top, np.maximum(combined_top_a, full_src_a), combined_top_a)
f_top[full_ry < blazer_top_y, 3] = 0
f_top[neck_in_top, 3] = 0
f_top[:, :, 3] = np.where(vneck_and_collar, 255, f_top[:, :, 3])
f_top[:, :, 3] = np.where(head_hair_in_full_a < 64, np.minimum(f_top[:, :, 3], full_src_a), f_top[:, :, 3])
# Tighten arm-hole inner edge (x=505..595, y=740..925) to alpha_4x >= 242 so zero fringe extends into the hole!
in_arm_hole_full = (full_rx >= 505) & (full_rx <= 595) & (full_ry >= 740) & (full_ry <= 925)
f_top[in_arm_hole_full & (full_src_a < 242), 3] = 0

# Inpaint orange hair curls over `f_top` ONLY where `head_hair_in_full_a` covers `topwear`!
# Everywhere outside `head_hair_in_full_a`, preserve 100% of the crisp 4x source RGB!
top_occ = (head_hair_in_full_a >= 64) & (full_ry <= 765)

dark_blazer_ref = binary_erosion(f_top[:, :, 3] > 220, iterations=2) & (~top_occ) & (full_src_a > 220) & (full_src_luma < 72) & (full_ry <= 920)
_, dark_blazer_idx = distance_transform_edt(~dark_blazer_ref, return_indices=True)

cream_shirt_ref = (
    (f_top[:, :, 3] > 220) & (~top_occ) & (full_src_a > 220) &
    (full_rx >= 250) & (full_rx <= 405) & (full_ry >= 575) & (full_ry <= 780) &
    (full_src_rgb[:, :, 1] > 140) & (full_src_rgb[:, :, 2] > 130)
)
_, cream_shirt_idx = distance_transform_edt(~cream_shirt_ref, return_indices=True)

in_vneck_shirt_zone = (
    (full_rx >= 250) & (full_rx <= 398) & (full_ry >= 572) & (full_ry <= 760) &
    (full_ry >= 575 + (355 - full_rx) * 0.7) &
    (full_ry <= 735 + (full_rx - 300) * 1.6)
)

w_occ_top = np.where(top_occ, 1.0, gaussian_filter(top_occ.astype(np.float32), sigma=1.5))
w_occ_top = np.where((full_ry > 765) | (head_hair_in_full_a < 16), 0.0, w_occ_top)
for c in range(3):
    blazer_c = gaussian_filter(full_src_rgb[:, :, c][dark_blazer_idx[0], dark_blazer_idx[1]].astype(np.float32), sigma=2.0)
    cream_c = gaussian_filter(full_src_rgb[:, :, c][cream_shirt_idx[0], cream_shirt_idx[1]].astype(np.float32), sigma=2.0)
    inpaint_c = np.where(in_vneck_shirt_zone, cream_c, blazer_c)
    src_c = full_src_rgb[:, :, c].astype(np.float32)
    f_top[:, :, c] = np.clip(np.round(w_occ_top * inpaint_c + (1.0 - w_occ_top) * src_c), 0, 255).astype(np.uint8)
f_top = prefill_rgb(f_top)
save_layer_canvas("inputs/layers/full", full_meta, "topwear", f_top)

# Shield full:topwear strictly inside opaque head hair (`head_hair_in_full_a >= 220`)
shield_canvas = np.zeros((1024, 1024, 4), dtype=np.uint8)
shield_mask = binary_erosion(head_hair_in_full_a >= 220, iterations=1) & (full_ry <= 765)
shield_canvas[:, :, 3] = np.where(shield_mask, 255, 0)
save_layer_canvas("inputs/layers/full", full_meta, "front hair", shield_canvas)

# (d) Merge `bottomwear` + `legwear` into unified dark trousers (`bottomwear`) with ZERO white dots!
f_trousers = np.zeros((1024, 1024, 4), dtype=np.uint8)
f_trousers[:, :, 3] = np.maximum(f_bw[:, :, 3], f_lw[:, :, 3])
ankle_in_fw = (full_ry >= 2045) & (
    ((full_src_rgb[:, :, 0].astype(int) - full_src_rgb[:, :, 2].astype(int) > 32) & (full_src_luma > 85)) |
    (full_ry >= 2100)
)
f_trousers[ankle_in_fw, 3] = 0
f_trousers[(full_src_luma > 80) & (f_top[:, :, 3] < 32), 3] = 0

cuff_dark = (full_rx >= 260) & (full_rx <= 495) & (full_ry >= 1980) & (full_ry <= 2100) & (~ankle_in_fw) & (full_src_a > 96) & (full_src_luma < 78)
f_trousers[:, :, 3] = np.where(cuff_dark, np.maximum(f_trousers[:, :, 3], full_src_a), f_trousers[:, :, 3])

trouser_zone = (full_rx >= 180) & (full_rx <= 555) & (full_ry >= 1000) & (full_ry <= 2105) & (~ankle_in_fw) & (full_src_luma < 78)
near_tr = binary_dilation(f_trousers[:, :, 3] > 24, iterations=4) & trouser_zone & (full_src_a > 120)
f_trousers[:, :, 3] = np.where(near_tr, np.maximum(f_trousers[:, :, 3], full_src_a), f_trousers[:, :, 3])
f_trousers[:, :, 3] = np.minimum(f_trousers[:, :, 3], full_src_a)
# Tighten leg-gap inner edge (x=340..390, y=1360..2045) to alpha_4x >= 242 so zero fringe extends into the leg gap!
in_leg_gap_full = (full_rx >= 340) & (full_rx <= 390) & (full_ry >= 1360) & (full_ry <= 2045)
f_trousers[in_leg_gap_full & (full_src_a < 242), 3] = 0

tr_occ = binary_dilation(f_top[:, :, 3] > 32, iterations=2)
tr_clean_ref = binary_erosion(f_trousers[:, :, 3] > 220, iterations=3) & (~tr_occ) & (full_src_a > 220) & (full_src_luma < 72)
_, tr_idx = distance_transform_edt(~tr_clean_ref, return_indices=True)

w_occ_tr = np.where(tr_occ, 1.0, gaussian_filter(tr_occ.astype(np.float32), sigma=2.0))
for c in range(3):
    inpaint_c = gaussian_filter(full_src_rgb[:, :, c][tr_idx[0], tr_idx[1]].astype(np.float32), sigma=2.0)
    src_c = np.where(full_src_luma < 74, full_src_rgb[:, :, c], full_src_rgb[:, :, c][tr_idx[0], tr_idx[1]]).astype(np.float32)
    f_trousers[:, :, c] = np.clip(np.round(w_occ_tr * inpaint_c + (1.0 - w_occ_tr) * src_c), 0, 255).astype(np.uint8)
f_trousers = prefill_rgb(f_trousers, core_mask=tr_clean_ref)
save_layer_canvas("inputs/layers/full", full_meta, "bottomwear", f_trousers)

# (e) FOOTWEAR (Heels + ankles, tucked up to y=2020 behind dark trouser cuffs)
fw_zone = (full_rx >= 230) & (full_rx <= 515) & (full_ry >= 2020) & (full_ry <= 2240)
f_fw[:, :, 3] = np.where(fw_zone & (full_src_a > 96), np.maximum(f_fw[:, :, 3], full_src_a), f_fw[:, :, 3])
f_fw[:, :, 3] = np.minimum(f_fw[:, :, 3], full_src_a)

fw_occ = binary_dilation(f_trousers[:, :, 3] > 128, iterations=2)
fw_clean_ref = (f_fw[:, :, 3] > 200) & (~fw_occ) & (full_src_a > 200) & ((full_src_rgb[:, :, 0].astype(int) - full_src_rgb[:, :, 2].astype(int)) > 32)
_, fw_idx = distance_transform_edt(~fw_clean_ref, return_indices=True)
w_occ_fw = np.where(fw_occ, 1.0, gaussian_filter(fw_occ.astype(np.float32), sigma=2.0))
for c in range(3):
    inpaint_c = full_src_rgb[:, :, c][fw_idx[0], fw_idx[1]].astype(np.float32)
    src_c = full_src_rgb[:, :, c].astype(np.float32)
    f_fw[:, :, c] = np.clip(np.round(w_occ_fw * inpaint_c + (1.0 - w_occ_fw) * src_c), 0, 255).astype(np.uint8)
f_fw = prefill_rgb(f_fw)
save_layer_canvas("inputs/layers/full", full_meta, "footwear", f_fw)

with open("inputs/layers/full/layers.json", "w") as f:
    json.dump(full_meta, f, indent=2)
with open("inputs/layers/head/layers.json", "w") as f:
    json.dump(head_meta, f, indent=2)

# ---------------------------------------------------------
# 4. Write Nova's 4x config.json
# ---------------------------------------------------------
config = {
  "key": "nova",
  "seethrough": {
    "resolution": 1024,
    "steps": 30,
    "seed": 42,
    "offload": True,
    "head_box": [200, 230, 730, 760]
  },
  "assemble": {
    "rig_scale": 1.0,
    "plan": [
      ["shoes", "full", "footwear"],
      ["bottomwear", "full", "bottomwear"],
      ["neck", "head", "neck"],
      ["topwear", "full", "topwear"],
      ["hair_back", "head", "back hair"],
      ["ear_l", "head", "ears"],
      ["face", "head", "face"],
      ["eyewhite_r", "head", "eyewhite-r"],
      ["eyewhite_l", "head", "eyewhite-l"],
      ["iris_r", "head", "irides-r"],
      ["iris_l", "head", "irides-l"],
      ["nose", "head", "nose"],
      ["mouth", "head", "mouth"],
      ["lash_r", "head", "eyelash-r"],
      ["lash_l", "head", "eyelash-l"],
      ["brow_r", "head", "eyebrow-r"],
      ["brow_l", "head", "eyebrow-l"],
      ["hair_front", "head", "front hair"]
    ]
  },
  "bones": [
    {"name": "hip", "parent": "root", "at": [400, 1020]},
    {"name": "chest", "parent": "hip", "at": [410, 780]},
    {"name": "neck", "parent": "chest", "at": [435, 585]},
    {"name": "head", "parent": "neck", "at": [435, 510]},
    {"name": "eye_r", "parent": "head", "at": [368, 425]},
    {"name": "eye_l", "parent": "head", "at": [442, 414]},
    {"name": "brow_r", "parent": "head", "at": [360, 404]},
    {"name": "brow_l", "parent": "head", "at": [437, 392]},
    {"name": "mouth", "parent": "head", "at": [402, 488]},
    {"name": "boob_r", "parent": "chest", "at": [312, 775]},
    {"name": "boob_l", "parent": "chest", "at": [435, 785]},
    {
      "chain": "hairback_r",
      "parent": "head",
      "points": [[335, 420], [315, 515], [295, 600]],
      "tip": [285, 685]
    },
    {
      "chain": "hairback_l",
      "parent": "head",
      "points": [[545, 410], [585, 525], [625, 625]],
      "tip": [665, 735]
    },
    {
      "chain": "hair_l",
      "parent": "head",
      "points": [[510, 420], [535, 530], [560, 625]],
      "tip": [595, 715]
    },
    {
      "chain": "bang_r",
      "parent": "head",
      "points": [[355, 330], [345, 375]],
      "tip": [340, 415]
    },
    {
      "chain": "bang_c",
      "parent": "head",
      "points": [[405, 325], [400, 370]],
      "tip": [395, 410]
    },
    {
      "chain": "bang_l",
      "parent": "head",
      "points": [[460, 325], [460, 368]],
      "tip": [458, 408]
    },
    {
      "chain": "hem_r",
      "parent": "chest",
      "points": [[290, 980], [272, 1110]],
      "tip": [260, 1235]
    },
    {
      "chain": "hem_l",
      "parent": "chest",
      "points": [[490, 980], [492, 1115]],
      "tip": [495, 1245]
    }
  ],
  "meshes": {
    "hair_back": {
      "grid": 57,
      "r": 15,
      "segments": [
        ["head", [435, 510], [435, 265]],
        "hairback_r",
        "hairback_l"
      ]
    },
    "hair_front": {
      "grid": 57,
      "r": 10,
      "segments": [
        ["head", [435, 510], [435, 265]],
        "bang_r",
        "bang_c",
        "bang_l",
        "hair_l"
      ]
    },
    "neck": {
      "grid": 57,
      "r": 5,
      "segments": [
        ["chest", [435, 595], [410, 780]],
        ["head", [435, 510], [435, 450]]
      ]
    },
    "topwear": {
      "contour": {
        "tolerance": 2,
        "margin": 2,
        "spacing": 36,
        "maxEdge": 64,
        "stray": 400,
        "bridges": True,
        "regions": [
          {"name": "bust_r", "shape": "circle", "cx": 312, "cy": 775, "r": 17, "bone": "boob_r", "spacing": 14, "band": 34},
          {"name": "bust_l", "shape": "circle", "cx": 435, "cy": 785, "r": 17, "bone": "boob_l", "spacing": 14, "band": 34}
        ]
      },
      "r": 15,
      "segments": [
        ["chest", [410, 560], [410, 960]],
        ["chest", [280, 620], [560, 660]],
        ["chest", [490, 650], [640, 880]],
        "hem_r",
        "hem_l"
      ]
    }
  },
  "regions": {
    "shoes": "root",
    "bottomwear": "hip",
    "ear_l": "head",
    "face": "head",
    "eyewhite_r": "eye_r",
    "eyewhite_l": "eye_l",
    "iris_r": "eye_r",
    "iris_l": "eye_l",
    "nose": "head",
    "mouth": "mouth",
    "lash_r": "eye_r",
    "lash_l": "eye_l",
    "brow_r": "brow_r",
    "brow_l": "brow_l"
  },
  "motion": {
    "duration": 3.3333333333333335,
    "tracks": [
      {"bone": "chest", "prop": "translatey", "amp": 5.0, "period": 3.3333333333333335, "phase": 0, "base": 5.0},
      {"bone": "chest", "prop": "scalex", "amp": 0.004, "period": 3.3333333333333335, "phase": 0, "base": 1.004},
      {"bone": "head", "prop": "rotate", "amp": 0.85, "period": 3.3333333333333335, "phase": 0.12},
      {"bone": "neck", "prop": "rotate", "amp": 0.35, "period": 3.3333333333333335, "phase": 0.08},
      {"bone": "boob_r", "prop": "translatey", "amp": 2.2, "period": 3.3333333333333335, "phase": 0.12},
      {"bone": "boob_r", "prop": "translatex", "amp": 0.7, "period": 3.3333333333333335, "phase": 0.12},
      {"bone": "boob_l", "prop": "translatey", "amp": 2.0, "period": 3.3333333333333335, "phase": 0.18},
      {"bone": "boob_l", "prop": "translatex", "amp": 0.65, "period": 3.3333333333333335, "phase": 0.18},
      {"chain": "hairback_r", "amps": [0.35, 0.8, 1.4], "period": 3.3333333333333335, "phase": 0.2, "lag": 0.08},
      {"chain": "hairback_l", "amps": [0.4, 0.95, 1.6], "period": 3.3333333333333335, "phase": 0.24, "lag": 0.08},
      {"chain": "hair_l", "amps": [0.4, 0.9, 1.5], "period": 3.3333333333333335, "phase": 0.25, "lag": 0.08},
      {"chain": "bang_r", "amps": [0.5, 1.1], "period": 3.3333333333333335, "phase": 0.18, "lag": 0.1},
      {"chain": "bang_c", "amps": [0.45, 1.0], "period": 3.3333333333333335, "phase": 0.18, "lag": 0.1},
      {"chain": "bang_l", "amps": [0.5, 1.1], "period": 3.3333333333333335, "phase": 0.18, "lag": 0.1},
      {"chain": "hem_r", "amps": [0.15, 0.35], "period": 3.3333333333333335, "phase": 0.28, "lag": 0.08},
      {"chain": "hem_l", "amps": [0.15, 0.35], "period": 3.3333333333333335, "phase": 0.32, "lag": 0.08}
    ],
    "blink": {
      "t": 2.75,
      "eyes": ["eye_r", "eye_l"],
      "brows": ["brow_r", "brow_l"],
      "squash": 0.12,
      "brow_drop": 1.2
    }
  },
  "constraints": [
    {"type": "physics", "name": "hairback_r0_phys", "bone": "hairback_r0", "rotate": 1, "inertia": 0.45, "strength": 220.0, "damping": 0.9, "mass": 1, "wind": 0.2, "gravity": 0.15, "mix": 1},
    {"type": "physics", "name": "hairback_r1_phys", "bone": "hairback_r1", "rotate": 1, "inertia": 0.55, "strength": 170.0, "damping": 0.88, "mass": 1, "wind": 0.45, "gravity": 0.3, "mix": 1},
    {"type": "physics", "name": "hairback_r2_phys", "bone": "hairback_r2", "rotate": 1, "inertia": 0.65, "strength": 130.0, "damping": 0.86, "mass": 1, "wind": 0.75, "gravity": 0.5, "mix": 1},
    {"type": "physics", "name": "hairback_l0_phys", "bone": "hairback_l0", "rotate": 1, "inertia": 0.45, "strength": 220.0, "damping": 0.9, "mass": 1, "wind": 0.2, "gravity": 0.15, "mix": 1},
    {"type": "physics", "name": "hairback_l1_phys", "bone": "hairback_l1", "rotate": 1, "inertia": 0.55, "strength": 170.0, "damping": 0.88, "mass": 1, "wind": 0.45, "gravity": 0.3, "mix": 1},
    {"type": "physics", "name": "hairback_l2_phys", "bone": "hairback_l2", "rotate": 1, "inertia": 0.65, "strength": 130.0, "damping": 0.86, "mass": 1, "wind": 0.75, "gravity": 0.5, "mix": 1},
    {"type": "physics", "name": "hair_l0_phys", "bone": "hair_l0", "rotate": 1, "inertia": 0.45, "strength": 220.0, "damping": 0.9, "mass": 1, "wind": 0.2, "gravity": 0.15, "mix": 1},
    {"type": "physics", "name": "hair_l1_phys", "bone": "hair_l1", "rotate": 1, "inertia": 0.55, "strength": 170.0, "damping": 0.88, "mass": 1, "wind": 0.45, "gravity": 0.3, "mix": 1},
    {"type": "physics", "name": "hair_l2_phys", "bone": "hair_l2", "rotate": 1, "inertia": 0.65, "strength": 130.0, "damping": 0.86, "mass": 1, "wind": 0.75, "gravity": 0.5, "mix": 1},
    {"type": "physics", "name": "bang_r0_phys", "bone": "bang_r0", "rotate": 1, "inertia": 0.25, "strength": 240.0, "damping": 0.9, "mass": 1, "wind": 0.15, "gravity": 0.1, "mix": 1},
    {"type": "physics", "name": "bang_r1_phys", "bone": "bang_r1", "rotate": 1, "inertia": 0.35, "strength": 180.0, "damping": 0.88, "mass": 1, "wind": 0.35, "gravity": 0.2, "mix": 1},
    {"type": "physics", "name": "bang_c0_phys", "bone": "bang_c0", "rotate": 1, "inertia": 0.25, "strength": 240.0, "damping": 0.9, "mass": 1, "wind": 0.15, "gravity": 0.1, "mix": 1},
    {"type": "physics", "name": "bang_c1_phys", "bone": "bang_c1", "rotate": 1, "inertia": 0.35, "strength": 180.0, "damping": 0.88, "mass": 1, "wind": 0.35, "gravity": 0.2, "mix": 1},
    {"type": "physics", "name": "bang_l0_phys", "bone": "bang_l0", "rotate": 1, "inertia": 0.25, "strength": 240.0, "damping": 0.9, "mass": 1, "wind": 0.15, "gravity": 0.1, "mix": 1},
    {"type": "physics", "name": "bang_l1_phys", "bone": "bang_l1", "rotate": 1, "inertia": 0.35, "strength": 180.0, "damping": 0.88, "mass": 1, "wind": 0.35, "gravity": 0.2, "mix": 1},
    {"type": "physics", "name": "hem_r0_phys", "bone": "hem_r0", "rotate": 1, "inertia": 0.25, "strength": 250.0, "damping": 0.9, "mass": 1, "wind": 0.15, "gravity": 0.12, "mix": 1},
    {"type": "physics", "name": "hem_r1_phys", "bone": "hem_r1", "rotate": 1, "inertia": 0.35, "strength": 200.0, "damping": 0.88, "mass": 1, "wind": 0.28, "gravity": 0.2, "mix": 1},
    {"type": "physics", "name": "hem_l0_phys", "bone": "hem_l0", "rotate": 1, "inertia": 0.25, "strength": 250.0, "damping": 0.9, "mass": 1, "wind": 0.15, "gravity": 0.12, "mix": 1},
    {"type": "physics", "name": "hem_l1_phys", "bone": "hem_l1", "rotate": 1, "inertia": 0.35, "strength": 200.0, "damping": 0.88, "mass": 1, "wind": 0.28, "gravity": 0.2, "mix": 1},
    {"type": "physics", "name": "boob_r_phys", "bone": "boob_r", "x": 0.45, "y": 1.0, "inertia": 0.55, "strength": 120.0, "damping": 0.82, "mass": 1.1, "wind": 0.25, "gravity": 0.35, "mix": 1.0},
    {"type": "physics", "name": "boob_l_phys", "bone": "boob_l", "x": 0.5, "y": 1.0, "inertia": 0.58, "strength": 115.0, "damping": 0.8, "mass": 1.15, "wind": 0.28, "gravity": 0.38, "mix": 1.0}
  ],
  "stops": [
    {"chain": "hem_r", "against": "hip", "at": [-40, 0], "inward": -1.0, "outward": 3.5, "lower": {"inward": -1.5, "outward": 4.5}},
    {"chain": "hem_l", "against": "hip", "at": [40, 0], "inward": -1.0, "outward": 3.5, "lower": {"inward": -1.5, "outward": 4.5}},
    {"chain": "hairback_r", "against": "chest", "at": [-40, 0], "inward": -1.5, "outward": 7.0, "lower": {"inward": -2.0, "outward": 9.0}},
    {"chain": "hairback_l", "against": "chest", "at": [60, 0], "inward": -1.5, "outward": 7.0, "lower": {"inward": -2.0, "outward": 9.0}},
    {"chain": "hair_l", "against": "chest", "at": [50, 0], "inward": -1.5, "outward": 7.0, "lower": {"inward": -2.0, "outward": 9.0}}
  ]
}

with open("config.json", "w") as f:
    json.dump(config, f, indent=2)

with open("requirements.json", "w") as f:
    json.dump({
        "spec": "spine-parts-requirements/1",
        "fps": 12,
        "not_swinging": ["bottomwear"],
        "requirements": []
    }, f, indent=2)

print("Successfully upgraded Nova 4x layers, config.json, and requirements.json!")
