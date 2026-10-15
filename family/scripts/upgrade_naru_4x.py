#!/usr/bin/env python3
"""
upgrade_naru_4x.py
Refines Naru's 4x-AnimeSharp (800x2284) rig layers and builds config.json:
  1. Removes the floating rembg shadow droplet between Naru's calves and detached white sliver on left shoulder
  2. Restores washed-out left hair tip and strips lavender-white shirt collar from `head:back hair`
  3. Decontaminates `painting.png` and `bottomwear` edges so zero white dots appear along the dark skirt silhouette
  4. Extends `head:neck` with a 14px under-tuck under the white shirt V-collar
  5. Binds waist-to-knee (`y = 960..1460`) of the tight pencil skirt rigidly to `hip` and applies skirt physics only below the knee (`y = 1500..1825`)
  6. Configures 3D-like dome contour falloff on `bust_r`/`bust_l` and desynchronized eye blink timing
"""
import os
import json
from PIL import Image
import numpy as np
from scipy.ndimage import distance_transform_edt, binary_dilation, binary_erosion, gaussian_filter

FAMILY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NARU_DIR = os.path.join(FAMILY_DIR, "naru")
os.chdir(NARU_DIR)

# 1. Load 4x RGBA crop directly from clean group image and clean all background alpha dust & floating artifacts
from scipy.ndimage import label

group_im = Image.open("../group_4096x2284_animesharp_rgba.png").convert("RGBA").crop((2496, 0, 3296, 2284))
rgba = np.array(group_im)
H, W = rgba.shape[:2]  # 2284, 800

yy, xx = np.mgrid[0:H, 0:W]
# Clear sub-threshold rembg background dust (alpha < 24) and keep only the main figure component!
rgba[rgba[:, :, 3] < 24] = [255, 255, 255, 0]
lbl_main, n_main = label(rgba[:, :, 3] > 0)
if n_main > 1:
    counts = np.bincount(lbl_main.ravel())
    counts[0] = 0
    main_cid = int(np.argmax(counts))
    rgba[lbl_main != main_cid] = [255, 255, 255, 0]

alpha_4x = rgba[:, :, 3].copy()
luma_4x = (
    0.299 * rgba[:, :, 0].astype(np.float32) +
    0.587 * rgba[:, :, 1].astype(np.float32) +
    0.114 * rgba[:, :, 2].astype(np.float32)
)
rb_4x = rgba[:, :, 0].astype(int) - rgba[:, :, 2].astype(int)

# (b) Detached vertical white sliver on upper-left shoulder crop boundary (x < 218, y = 610..690)
# and white spikes protruding above the natural sloping left shoulder curve (x = 218..244, y = 626..668)
left_sh_curve_4x = np.interp(xx, [215, 228, 242, 260, 280], [668, 657, 648, 642, 636])
shoulder_sliver = (
    ((xx < 218) & (yy >= 575) & (yy <= 690)) |
    ((xx >= 218) & (xx <= 244) & (yy >= 626) & (yy < left_sh_curve_4x) & ((luma_4x > 105) | (rb_4x < 20)))
)
rgba[shoulder_sliver, 3] = 0
alpha_4x = rgba[:, :, 3].copy()

# (c) Restore washed-out left hair tip (x = 204..248, y = 570..650) with rich brown hair color
brown_hair_core_4x = (
    (xx >= 220) & (xx <= 290) & (yy >= 470) & (yy <= 580) &
    (alpha_4x > 235) & (luma_4x < 92) & (rb_4x > 22)
)
_, bh_4x_idx = distance_transform_edt(~brown_hair_core_4x, return_indices=True)
washed_hair_tip = (
    (xx >= 204) & (xx <= 248) & (yy >= 570) & (yy <= 650) &
    (alpha_4x > 0) & ((luma_4x > 98) | (rb_4x < 22))
)
for c in range(3):
    rgba[:, :, c] = np.where(washed_hair_tip, rgba[:, :, c][bh_4x_idx[0], bh_4x_idx[1]], rgba[:, :, c])

# (d) Clean dark skirt rim (y = 1030..1835, strictly below cuffs!)
rim_4x = (alpha_4x > 0) & (~binary_erosion(alpha_4x >= 235, iterations=3))
bright_skirt_rim = rim_4x & (yy >= 1030) & (yy <= 1835) & (luma_4x > 85)
rgba[bright_skirt_rim, 3] = 0
alpha_4x = rgba[:, :, 3].copy()

# (e) Build decontaminated `bled_painting`: preserve 100% of interior opaque pixels (`interior_opaque`)
# so Naru's hands, cuffs, and shirt are never altered in `painting.png`!
interior_opaque = binary_erosion(alpha_4x >= 240, iterations=3)
skirt_only_band = (yy >= 1030) & (yy <= 1820)
core_4x = interior_opaque | (binary_erosion(alpha_4x >= 235, iterations=1) & ((~skirt_only_band) | (luma_4x < 72)))
_, core_idx = distance_transform_edt(~core_4x, return_indices=True)
bled_painting = rgba[:, :, :3].copy()
for c in range(3):
    bled_painting[:, :, c] = np.where(core_4x, rgba[:, :, c], rgba[:, :, c][core_idx[0], core_idx[1]])
    rgba[:, :, c] = np.where(alpha_4x >= 230, rgba[:, :, c], np.where(alpha_4x > 0, bled_painting[:, :, c], 255))

painting = bled_painting.copy()
painting[alpha_4x < 210] = [255, 255, 255]
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
# 2px eroded 4x alpha (Equals ~1px in 1024 space) so 1024->2284 bilinear upsampling never balloons outside the 4x silhouette!
alpha_4x_eroded2 = np.where(binary_erosion(alpha_4x >= 220, iterations=2), 255, 0).astype(np.uint8)
full_src_a_tight = np.where(full_in_bounds, alpha_4x_eroded2[full_ry_clamped, full_rx_clamped], 0)
full_src_luma = (
    0.299 * full_src_rgb[:, :, 0].astype(np.float32) +
    0.587 * full_src_rgb[:, :, 1].astype(np.float32) +
    0.114 * full_src_rgb[:, :, 2].astype(np.float32)
)

# head_box = [160, 300, 600, 740] (440x440)
hy_grid, hx_grid = np.mgrid[0:1024, 0:1024]
head_rx = 160.0 + (hx_grid + 0.5) * (440.0 / 1024.0)
head_ry = 300.0 + (hy_grid + 0.5) * (440.0 / 1024.0)
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
used_full = {"back hair", "footwear", "legwear", "handwear-l", "bottomwear", "topwear", "front hair"}
for l in full_meta["layers"]:
    if l["name"] not in used_full:
        save_layer_canvas("inputs/layers/full", full_meta, l["name"], np.zeros((1024, 1024, 4), dtype=np.uint8))

used_head = {
    "back hair", "neck", "ears-r", "ears-l", "face", "nose", "mouth",
    "eyewhite-r", "eyewhite-l", "irides-r", "irides-l",
    "eyelash-r", "eyelash-l", "eyebrow-r", "eyebrow-l", "front hair"
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

head_rb = head_src_rgb[:, :, 0].astype(int) - head_src_rgb[:, :, 2].astype(int)

# Unify lower side hair (outside forehead bangs box) from `front hair` into `back hair`
in_bang_box = (head_ry <= 500) & (head_rx >= 282) & (head_rx <= 468)
h_bh_combined_a = np.maximum(h_bh[:, :, 3], np.where(~in_bang_box, h_fh[:, :, 3], 0))
h_fh[~in_bang_box, 3] = 0

# In `head:back hair`:
# 1) Strictly clear everything below y=658 (removes all shirt body & yellow cat badge remnants!)
# 2) Keep 100% of true brown hair (`B < 122` and `R-B >= 16`) all the way across `x = 204..565` (including the right outer hair strands at x=520..560!)
#    plus a 6px brown under-tuck behind the shirt collar!
center_neck_gap = (head_ry >= 595) & (head_rx >= 362) & (head_rx <= 420)
true_brown_hair = (head_src_a > 80) & (head_src_rgb[:, :, 2] < 122) & (head_rb >= 16) & (head_src_luma < 142) & (~center_neck_gap) & (head_ry <= 658)
# Only allow the 6px collar under-tuck inside the collar width (`x = 235..518`), while keeping outer hair tips (`x > 518` or `x < 235`) crisp!
collar_tuck_zone = (head_rx >= 235) & (head_rx <= 518) & (head_ry >= 585) & (head_ry <= 658) & (~center_neck_gap) & (head_src_a > 200)
brown_hair_with_tuck = true_brown_hair | (binary_dilation(true_brown_hair, iterations=7) & collar_tuck_zone)

h_bh[:, :, 3] = h_bh_combined_a
h_bh[:, :, 3] = np.where((head_ry >= 440) & true_brown_hair, np.maximum(h_bh[:, :, 3], head_src_a), h_bh[:, :, 3])
h_bh[:, :, 3] = np.where((head_ry >= 500) & brown_hair_with_tuck, np.maximum(h_bh[:, :, 3], np.minimum(head_src_a, 255)), h_bh[:, :, 3])
h_bh[(head_ry >= 525) & (~brown_hair_with_tuck), 3] = 0
h_bh[head_ry > 658, 3] = 0
h_bh[head_src_a < 32, 3] = 0
h_bh[(head_ry >= 520) & (h_bh[:, :, 3] < 96), 3] = 0

lbl_bh, n_bh = label(h_bh[:, :, 3] > 0)
for cid in range(1, n_bh + 1):
    comp = lbl_bh == cid
    if comp.sum() < 250:
        h_bh[comp, 3] = 0

# Fill any non-brown collar overlap inside `brown_hair_with_tuck` with rich brown hair color (`hbh_brown_core`)
hbh_brown_core = binary_erosion((h_bh[:, :, 3] > 200) & (head_src_luma < 110) & (head_rb >= 22) & (head_src_rgb[:, :, 2] < 95), iterations=1)
_, hbh_idx = distance_transform_edt(~hbh_brown_core, return_indices=True)
is_non_brown_on_bh = (head_ry >= 540) & ((head_src_rgb[:, :, 2] >= 98) | (head_src_luma >= 118) | (head_rb < 20))
for c in range(3):
    clean_bh_rgb = np.where(is_non_brown_on_bh, head_src_rgb[:, :, c][hbh_idx[0], hbh_idx[1]], head_src_rgb[:, :, c])
    h_bh[:, :, c] = np.where(h_bh[:, :, 3] > 0, clean_bh_rgb, h_bh[:, :, c])
h_bh = prefill_rgb(h_bh, core_mask=hbh_brown_core)
save_layer_canvas("inputs/layers/head", head_meta, "back hair", h_bh)

# Clean front hair (forehead bangs)
h_fh[head_src_a < 24, 3] = 0
for c in range(3):
    h_fh[:, :, c] = np.where(h_fh[:, :, 3] > 0, head_src_rgb[:, :, c], h_fh[:, :, c])
h_fh = prefill_rgb(h_fh)
save_layer_canvas("inputs/layers/head", head_meta, "front hair", h_fh)

# HEAD:NECK — Clean separation & 16px under-tuck under white shirt collar (overlaps seamlessly with h_bh and f_top!)
is_dark_hair_on_neck = (head_ry >= 555) & (head_ry <= 640) & ((head_rx <= 348) | (head_rx >= 434)) & (head_src_luma < 95)
h_neck[is_dark_hair_on_neck | (head_rx < 334) | (head_rx > 448), 3] = 0
neck_skin = (
    (head_rx >= 340) & (head_rx <= 442) & (head_ry >= 550) & (head_ry <= 725) &
    (head_src_a > 200) & (~is_dark_hair_on_neck) &
    (head_src_rgb[:, :, 0] > 160) &
    (head_rb > 34)
)
h_neck[:, :, 3] = np.where(neck_skin, np.maximum(h_neck[:, :, 3], 255), h_neck[:, :, 3])
for c in range(3):
    h_neck[:, :, c] = np.where(neck_skin, head_src_rgb[:, :, c], h_neck[:, :, c])

white_collar_on_neck = (head_ry >= 615) & (head_src_rgb[:, :, 2] >= 125) & (head_rb < 42)
h_neck[white_collar_on_neck, 3] = 0

neck_core = (h_neck[:, :, 3] > 200) & (head_src_rgb[:, :, 0] > 180) & (head_rb > 45)
_, nearest_idx = distance_transform_edt(~neck_core, return_indices=True)
neck_dilated = binary_dilation(neck_core, iterations=18)
under_tuck = neck_dilated & (~neck_core) & (head_ry >= 595) & (head_ry <= 738) & (head_rx >= 328) & (head_rx <= 452)
h_neck[:, :, 3] = np.where(under_tuck, np.maximum(h_neck[:, :, 3], 255), h_neck[:, :, 3])
for c in range(3):
    h_neck[:, :, c] = np.where(under_tuck | (h_neck[:, :, 3] > 0), np.where(neck_core, head_src_rgb[:, :, c], head_src_rgb[:, :, c][nearest_idx[0], nearest_idx[1]]), h_neck[:, :, c])

h_neck = prefill_rgb(h_neck, core_mask=neck_core)
save_layer_canvas("inputs/layers/head", head_meta, "neck", h_neck)

# Facial features & face 4x RGB injection
face_occ = (h_fh[:, :, 3] > 64)
for enm in ["ears-r", "ears-l", "eyewhite-r", "eyewhite-l", "irides-r", "irides-l", "eyelash-r", "eyelash-l", "eyebrow-r", "eyebrow-l", "nose", "mouth"]:
    el = load_layer_canvas("inputs/layers/head_orig", head_meta, enm)
    face_occ = face_occ | (el[:, :, 3] > 64)
    el_vis = (el[:, :, 3] > 0) & (h_fh[:, :, 3] < 64) & (head_src_a > 96)
    for c in range(3):
        el[:, :, c] = np.where(el_vis, head_src_rgb[:, :, c], el[:, :, c])
    el = prefill_rgb(el)
    save_layer_canvas("inputs/layers/head", head_meta, enm, el)

occ_face = binary_dilation(face_occ, iterations=2)
w_occ_face = np.where(occ_face, 1.0, gaussian_filter(occ_face.astype(np.float32), sigma=2.0))
for c in range(3):
    qwen_c = h_face[:, :, c].astype(np.float32)
    src_c = head_src_rgb[:, :, c].astype(np.float32)
    h_face[:, :, c] = np.clip(np.round(w_occ_face * qwen_c + (1.0 - w_occ_face) * src_c), 0, 255).astype(np.uint8)
h_face = prefill_rgb(h_face)
save_layer_canvas("inputs/layers/head", head_meta, "face", h_face)

# ---------------------------------------------------------
# 3. FULL LAYERS: TOPWEAR, HANDWEAR-L, BOTTOMWEAR, LEGWEAR, FOOTWEAR
# ---------------------------------------------------------
f_top = load_layer_canvas("inputs/layers/full_orig", full_meta, "topwear")
f_hw = load_layer_canvas("inputs/layers/full_orig", full_meta, "handwear-l")
f_bw = load_layer_canvas("inputs/layers/full_orig", full_meta, "bottomwear")
f_lw = load_layer_canvas("inputs/layers/full_orig", full_meta, "legwear")
f_fw = load_layer_canvas("inputs/layers/full_orig", full_meta, "footwear")

save_layer_canvas("inputs/layers/full", full_meta, "back hair", np.zeros((1024, 1024, 4), dtype=np.uint8))

# Map `h_bh` and `h_neck` into `full` 1024 space so `f_top` ONLY cuts out where `hair_back` or `neck` is 100% opaque behind it!
hair_hx = np.round((full_rx - 160.0) * (1024.0 / 440.0)).astype(int)
hair_hy = np.round((full_ry - 300.0) * (1024.0 / 440.0)).astype(int)
in_head_box_full = (hair_hx >= 0) & (hair_hx < 1024) & (hair_hy >= 0) & (hair_hy < 1024)
hair_hx_c = np.clip(hair_hx, 0, 1023)
hair_hy_c = np.clip(hair_hy, 0, 1023)
h_bh_in_full_a = np.where(in_head_box_full, h_bh[:, :, 3][hair_hy_c, hair_hx_c], 0)
h_neck_in_full_a = np.where(in_head_box_full, h_neck[:, :, 3][hair_hy_c, hair_hx_c], 0)

vneck_left_x = np.interp(full_ry, [615, 645, 685, 712], [354, 360, 382, 401])
vneck_right_x = np.interp(full_ry, [615, 645, 685, 712], [434, 426, 412, 401])
in_vneck_opening = (full_ry >= 615) & (full_ry <= 712) & (full_rx >= vneck_left_x) & (full_rx <= vneck_right_x)

full_rb = full_src_rgb[:, :, 0].astype(int) - full_src_rgb[:, :, 2].astype(int)
# Cut brown hair out of `f_top` ONLY where `h_bh_in_full_a >= 200` backs it, and cut V-neck skin ONLY where `h_neck_in_full_a >= 200` backs it!
brown_hair_on_top = (full_ry <= 658) & (h_bh_in_full_a >= 200) & ((full_src_rgb[:, :, 2] < 115) | (full_rb > 52))
neck_skin_on_top = in_vneck_opening & (h_neck_in_full_a >= 200) & (full_rb > 40)

neck_in_top = (
    (full_ry < 616) |
    brown_hair_on_top |
    neck_skin_on_top |
    ((full_rx < 218) & (full_ry < 670))
)

# Merge HANDWEAR-L (Both sleeves + clasped hands) into TOPWEAR using the 2px-eroded 4x silhouette (`full_src_a_tight`) on outer edges!
save_layer_canvas("inputs/layers/full", full_meta, "handwear-l", np.zeros((1024, 1024, 4), dtype=np.uint8))
combined_top_a = np.maximum(f_top[:, :, 3], f_hw[:, :, 3])
combined_top_a[neck_in_top] = 0

# Above the skirt waist (`y <= 955`), the entire figure width (outside `neck_in_top`) belongs to `topwear`!
# Using `full_src_a_tight` directly for the upper-body outer silhouette prevents 1024->2284 bilinear upsampling from ballooning 2px outside!
upper_shirt_body = (full_ry >= 616) & (full_ry <= 955) & (~neck_in_top) & (full_src_a_tight > 0)
lower_cuffs_hands = (full_ry > 955) & (full_ry <= 1022) & (combined_top_a > 24) & (full_src_a_tight > 0)

f_top[:, :, 3] = np.where(upper_shirt_body, full_src_a_tight, np.where(lower_cuffs_hands, np.minimum(combined_top_a, full_src_a_tight), 0))
f_top[neck_in_top, 3] = 0

# Ensure the lavender-white collar on both left and right sides of the V-neck is 100% solid!
collar_solid = (
    (full_rx >= 230) & (full_rx <= 555) & (full_ry >= 616) & (full_ry <= 720) &
    (~neck_in_top) & (full_src_a_tight >= 220)
)
f_top[collar_solid, 3] = 255

# Inject 100% crisp 4x RGB directly, and use 1px erosion for `prefill_rgb` so dark inner sleeve creases never bleed onto the outer rim!
for c in range(3):
    f_top[:, :, c] = np.where(f_top[:, :, 3] > 0, full_src_rgb[:, :, c], f_top[:, :, c])
f_top = prefill_rgb(f_top, core_mask=binary_erosion(f_top[:, :, 3] > 215, iterations=1))
save_layer_canvas("inputs/layers/full", full_meta, "topwear", f_top)
save_layer_canvas("inputs/layers/full", full_meta, "front hair", np.zeros((1024, 1024, 4), dtype=np.uint8))

# (d) BOTTOMWEAR (Long black pencil skirt — zero white dots & no pink leg skin at hem!)
leg_skin_at_hem = (full_ry >= 1808) & (
    ((full_src_rgb[:, :, 0].astype(int) - full_src_rgb[:, :, 2].astype(int)) > 26) |
    (full_src_luma > 74)
)
f_bw[leg_skin_at_hem, 3] = 0
f_bw[(full_ry < 1815) & (full_src_luma > 82) & (f_top[:, :, 3] < 32), 3] = 0

bw_zone = (full_rx >= 210) & (full_rx <= 565) & (full_ry >= 940) & (full_ry <= 1835) & (~leg_skin_at_hem) & (full_src_luma < 80)
near_bw = binary_dilation(f_bw[:, :, 3] > 24, iterations=4) & bw_zone & (full_src_a > 120)
f_bw[:, :, 3] = np.where(near_bw, np.maximum(f_bw[:, :, 3], full_src_a), f_bw[:, :, 3])
f_bw[:, :, 3] = np.minimum(f_bw[:, :, 3], full_src_a)

bw_occ = binary_dilation((f_hw[:, :, 3] > 32) | (f_top[:, :, 3] > 32), iterations=2)
skirt_dark_core = binary_erosion(f_bw[:, :, 3] > 220, iterations=3) & (~bw_occ) & (full_src_luma < 70)
_, bw_dark_idx = distance_transform_edt(~skirt_dark_core, return_indices=True)

for c in range(3):
    dark_c = full_src_rgb[:, :, c][bw_dark_idx[0], bw_dark_idx[1]]
    f_bw[:, :, c] = np.where(
        (f_bw[:, :, 3] > 0) & (~bw_occ) & (full_src_luma < 72),
        full_src_rgb[:, :, c],
        dark_c
    )
f_bw = prefill_rgb(f_bw, core_mask=skirt_dark_core)
save_layer_canvas("inputs/layers/full", full_meta, "bottomwear", f_bw)

# (e) LEGWEAR & FOOTWEAR
f_lw[(full_ry >= 1815) & (full_src_a < 128), 3] = 0

lw_zone = (full_rx >= 240) & (full_rx <= 520) & (full_ry >= 1790) & (full_ry <= 2230) & (~((full_ry >= 1815) & (full_src_a < 128)))
near_lw = binary_dilation(f_lw[:, :, 3] > 16, iterations=6) & lw_zone & (full_src_a > 128)
f_lw[:, :, 3] = np.where(near_lw, np.maximum(f_lw[:, :, 3], full_src_a), f_lw[:, :, 3])
f_lw[:, :, 3] = np.minimum(f_lw[:, :, 3], full_src_a)

lw_occ = binary_dilation((f_bw[:, :, 3] > 32) | (f_fw[:, :, 3] > 32), iterations=2)
w_occ_lw = np.where(lw_occ, 1.0, gaussian_filter(lw_occ.astype(np.float32), sigma=2.0))
for c in range(3):
    qwen_c = f_lw[:, :, c].astype(np.float32)
    src_c = full_src_rgb[:, :, c].astype(np.float32)
    f_lw[:, :, c] = np.clip(np.round(w_occ_lw * qwen_c + (1.0 - w_occ_lw) * src_c), 0, 255).astype(np.uint8)
f_lw = prefill_rgb(f_lw)
save_layer_canvas("inputs/layers/full", full_meta, "legwear", f_lw)

fw_zone = (full_rx >= 300) & (full_rx <= 490) & (full_ry >= 2030) & (full_ry <= 2265)
near_fw = binary_dilation(f_fw[:, :, 3] > 16, iterations=6) & fw_zone & (full_src_a > 96)
f_fw[:, :, 3] = np.where(near_fw, np.maximum(f_fw[:, :, 3], full_src_a), f_fw[:, :, 3])
f_fw[:, :, 3] = np.minimum(f_fw[:, :, 3], full_src_a)
for c in range(3):
    f_fw[:, :, c] = np.where(f_fw[:, :, 3] > 0, full_src_rgb[:, :, c], f_fw[:, :, c])
f_fw = prefill_rgb(f_fw)
save_layer_canvas("inputs/layers/full", full_meta, "footwear", f_fw)

with open("inputs/layers/full/layers.json", "w") as f:
    json.dump(full_meta, f, indent=2)
with open("inputs/layers/head/layers.json", "w") as f:
    json.dump(head_meta, f, indent=2)

# ---------------------------------------------------------
# 4. Write Naru's 4x config.json
# ---------------------------------------------------------
config = {
  "key": "naru",
  "seethrough": {
    "resolution": 1024,
    "steps": 30,
    "seed": 42,
    "offload": True,
    "head_box": [160, 300, 600, 740]
  },
  "assemble": {
    "rig_scale": 1.0,
    "plan": [
      ["hair_back", "head", "back hair"],
      ["shoes", "full", "footwear"],
      ["legwear", "full", "legwear"],
      ["bottomwear", "full", "bottomwear"],
      ["neck", "head", "neck"],
      ["topwear", "full", "topwear"],
      ["ear_r", "head", "ears-r"],
      ["ear_l", "head", "ears-l"],
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
    {"name": "hip", "parent": "root", "at": [380, 960]},
    {"name": "chest", "parent": "hip", "at": [380, 780]},
    {"name": "neck", "parent": "chest", "at": [380, 645]},
    {"name": "head", "parent": "neck", "at": [380, 575]},
    {"name": "eye_r", "parent": "head", "at": [326, 520]},
    {"name": "eye_l", "parent": "head", "at": [409, 496]},
    {"name": "brow_r", "parent": "head", "at": [305, 491]},
    {"name": "brow_l", "parent": "head", "at": [401, 466]},
    {"name": "mouth", "parent": "head", "at": [383, 565]},
    {"name": "boob_r", "parent": "chest", "at": [312, 785]},
    {"name": "boob_l", "parent": "chest", "at": [448, 785]},
    {
      "chain": "hairback_r",
      "parent": "head",
      "points": [[265, 440], [250, 535], [240, 605]],
      "tip": [235, 665]
    },
    {
      "chain": "hairback_l",
      "parent": "head",
      "points": [[485, 430], [500, 525], [515, 600]],
      "tip": [525, 665]
    },
    {
      "chain": "hair_r",
      "parent": "head",
      "points": [[280, 460], [285, 550], [295, 625]],
      "tip": [305, 695]
    },
    {
      "chain": "hair_l",
      "parent": "head",
      "points": [[460, 440], [465, 535], [465, 615]],
      "tip": [455, 695]
    },
    {
      "chain": "bang_r",
      "parent": "head",
      "points": [[315, 395], [310, 445]],
      "tip": [308, 495]
    },
    {
      "chain": "bang_c",
      "parent": "head",
      "points": [[368, 385], [365, 435]],
      "tip": [362, 485]
    },
    {
      "chain": "bang_l",
      "parent": "head",
      "points": [[425, 380], [430, 430]],
      "tip": [435, 475]
    },
    {
      "chain": "skirt_r",
      "parent": "hip",
      "points": [[265, 1500], [270, 1610], [273, 1720]],
      "tip": [275, 1825]
    },
    {
      "chain": "skirt_c",
      "parent": "hip",
      "points": [[380, 1500], [382, 1610], [384, 1720]],
      "tip": [386, 1825]
    },
    {
      "chain": "skirt_l",
      "parent": "hip",
      "points": [[495, 1500], [492, 1610], [490, 1720]],
      "tip": [488, 1825]
    }
  ],
  "meshes": {
    "hair_back": {
      "grid": 57,
      "r": 15,
      "segments": [
        ["head", [380, 575], [380, 330]],
        "hairback_r",
        "hairback_l",
        "hair_r",
        "hair_l"
      ]
    },
    "hair_front": {
      "grid": 57,
      "r": 10,
      "segments": [
        ["head", [380, 575], [380, 330]],
        "bang_r",
        "bang_c",
        "bang_l"
      ]
    },
    "neck": {
      "grid": 57,
      "r": 5,
      "segments": [
        ["chest", [380, 650], [380, 780]],
        ["head", [380, 575], [380, 510]]
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
          {"name": "bust_r", "shape": "circle", "cx": 312, "cy": 785, "r": 17, "bone": "boob_r", "spacing": 14, "band": 34},
          {"name": "bust_l", "shape": "circle", "cx": 448, "cy": 785, "r": 17, "bone": "boob_l", "spacing": 14, "band": 34}
        ]
      },
      "r": 15,
      "segments": [
        ["chest", [380, 630], [380, 910]],
        ["hip", [380, 910], [380, 990]]
      ]
    },
    "bottomwear": {
      "grid": 57,
      "r": 15,
      "segments": [
        ["hip", [240, 960], [520, 960]],
        ["hip", [260, 960], [265, 1460]],
        ["hip", [380, 960], [380, 1460]],
        ["hip", [500, 960], [495, 1460]],
        ["hip", [262, 1450], [498, 1450]],
        "skirt_r",
        "skirt_c",
        "skirt_l"
      ]
    }
  },
  "regions": {
    "shoes": "root",
    "legwear": "hip",
    "ear_r": "head",
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
      {"bone": "boob_r", "prop": "translatey", "amp": 2.1, "period": 3.3333333333333335, "phase": 0.12},
      {"bone": "boob_r", "prop": "translatex", "amp": 0.65, "period": 3.3333333333333335, "phase": 0.12},
      {"bone": "boob_l", "prop": "translatey", "amp": 2.3, "period": 3.3333333333333335, "phase": 0.18},
      {"bone": "boob_l", "prop": "translatex", "amp": 0.7, "period": 3.3333333333333335, "phase": 0.18},
      {"chain": "hairback_r", "amps": [0.35, 0.8, 1.4], "period": 3.3333333333333335, "phase": 0.2, "lag": 0.08},
      {"chain": "hairback_l", "amps": [0.35, 0.8, 1.4], "period": 3.3333333333333335, "phase": 0.24, "lag": 0.08},
      {"chain": "hair_r", "amps": [0.4, 0.9, 1.5], "period": 3.3333333333333335, "phase": 0.21, "lag": 0.08},
      {"chain": "hair_l", "amps": [0.4, 0.9, 1.5], "period": 3.3333333333333335, "phase": 0.25, "lag": 0.08},
      {"chain": "bang_r", "amps": [0.5, 1.1], "period": 3.3333333333333335, "phase": 0.18, "lag": 0.1},
      {"chain": "bang_c", "amps": [0.45, 1.0], "period": 3.3333333333333335, "phase": 0.18, "lag": 0.1},
      {"chain": "bang_l", "amps": [0.5, 1.1], "period": 3.3333333333333335, "phase": 0.18, "lag": 0.1},
      {"chain": "skirt_r", "amps": [0.12, 0.28, 0.5], "period": 3.3333333333333335, "phase": 0.3, "lag": 0.07},
      {"chain": "skirt_c", "amps": [0.12, 0.28, 0.5], "period": 3.3333333333333335, "phase": 0.34, "lag": 0.07},
      {"chain": "skirt_l", "amps": [0.12, 0.28, 0.5], "period": 3.3333333333333335, "phase": 0.38, "lag": 0.07}
    ],
    "blink": {
      "t": 1.45,
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
    {"type": "physics", "name": "hair_r0_phys", "bone": "hair_r0", "rotate": 1, "inertia": 0.45, "strength": 220.0, "damping": 0.9, "mass": 1, "wind": 0.2, "gravity": 0.15, "mix": 1},
    {"type": "physics", "name": "hair_r1_phys", "bone": "hair_r1", "rotate": 1, "inertia": 0.55, "strength": 170.0, "damping": 0.88, "mass": 1, "wind": 0.45, "gravity": 0.3, "mix": 1},
    {"type": "physics", "name": "hair_r2_phys", "bone": "hair_r2", "rotate": 1, "inertia": 0.65, "strength": 130.0, "damping": 0.86, "mass": 1, "wind": 0.75, "gravity": 0.5, "mix": 1},
    {"type": "physics", "name": "hair_l0_phys", "bone": "hair_l0", "rotate": 1, "inertia": 0.45, "strength": 220.0, "damping": 0.9, "mass": 1, "wind": 0.2, "gravity": 0.15, "mix": 1},
    {"type": "physics", "name": "hair_l1_phys", "bone": "hair_l1", "rotate": 1, "inertia": 0.55, "strength": 170.0, "damping": 0.88, "mass": 1, "wind": 0.45, "gravity": 0.3, "mix": 1},
    {"type": "physics", "name": "hair_l2_phys", "bone": "hair_l2", "rotate": 1, "inertia": 0.65, "strength": 130.0, "damping": 0.86, "mass": 1, "wind": 0.75, "gravity": 0.5, "mix": 1},
    {"type": "physics", "name": "bang_r0_phys", "bone": "bang_r0", "rotate": 1, "inertia": 0.25, "strength": 240.0, "damping": 0.9, "mass": 1, "wind": 0.15, "gravity": 0.1, "mix": 1},
    {"type": "physics", "name": "bang_r1_phys", "bone": "bang_r1", "rotate": 1, "inertia": 0.35, "strength": 180.0, "damping": 0.88, "mass": 1, "wind": 0.35, "gravity": 0.2, "mix": 1},
    {"type": "physics", "name": "bang_c0_phys", "bone": "bang_c0", "rotate": 1, "inertia": 0.25, "strength": 240.0, "damping": 0.9, "mass": 1, "wind": 0.15, "gravity": 0.1, "mix": 1},
    {"type": "physics", "name": "bang_c1_phys", "bone": "bang_c1", "rotate": 1, "inertia": 0.35, "strength": 180.0, "damping": 0.88, "mass": 1, "wind": 0.35, "gravity": 0.2, "mix": 1},
    {"type": "physics", "name": "bang_l0_phys", "bone": "bang_l0", "rotate": 1, "inertia": 0.25, "strength": 240.0, "damping": 0.9, "mass": 1, "wind": 0.15, "gravity": 0.1, "mix": 1},
    {"type": "physics", "name": "bang_l1_phys", "bone": "bang_l1", "rotate": 1, "inertia": 0.35, "strength": 180.0, "damping": 0.88, "mass": 1, "wind": 0.35, "gravity": 0.2, "mix": 1},
    {"type": "physics", "name": "skirt_r0_phys", "bone": "skirt_r0", "rotate": 1, "inertia": 0.25, "strength": 260.0, "damping": 0.91, "mass": 1, "wind": 0.12, "gravity": 0.12, "mix": 1},
    {"type": "physics", "name": "skirt_r1_phys", "bone": "skirt_r1", "rotate": 1, "inertia": 0.32, "strength": 220.0, "damping": 0.89, "mass": 1, "wind": 0.22, "gravity": 0.18, "mix": 1},
    {"type": "physics", "name": "skirt_r2_phys", "bone": "skirt_r2", "rotate": 1, "inertia": 0.38, "strength": 180.0, "damping": 0.87, "mass": 1, "wind": 0.35, "gravity": 0.25, "mix": 1},
    {"type": "physics", "name": "skirt_c0_phys", "bone": "skirt_c0", "rotate": 1, "inertia": 0.25, "strength": 260.0, "damping": 0.91, "mass": 1, "wind": 0.12, "gravity": 0.12, "mix": 1},
    {"type": "physics", "name": "skirt_c1_phys", "bone": "skirt_c1", "rotate": 1, "inertia": 0.32, "strength": 220.0, "damping": 0.89, "mass": 1, "wind": 0.22, "gravity": 0.18, "mix": 1},
    {"type": "physics", "name": "skirt_c2_phys", "bone": "skirt_c2", "rotate": 1, "inertia": 0.38, "strength": 180.0, "damping": 0.87, "mass": 1, "wind": 0.35, "gravity": 0.25, "mix": 1},
    {"type": "physics", "name": "skirt_l0_phys", "bone": "skirt_l0", "rotate": 1, "inertia": 0.25, "strength": 260.0, "damping": 0.91, "mass": 1, "wind": 0.12, "gravity": 0.12, "mix": 1},
    {"type": "physics", "name": "skirt_l1_phys", "bone": "skirt_l1", "rotate": 1, "inertia": 0.32, "strength": 220.0, "damping": 0.89, "mass": 1, "wind": 0.22, "gravity": 0.18, "mix": 1},
    {"type": "physics", "name": "skirt_l2_phys", "bone": "skirt_l2", "rotate": 1, "inertia": 0.38, "strength": 180.0, "damping": 0.87, "mass": 1, "wind": 0.35, "gravity": 0.25, "mix": 1},
    {"type": "physics", "name": "boob_r_phys", "bone": "boob_r", "x": 0.45, "y": 1.0, "inertia": 0.55, "strength": 120.0, "damping": 0.82, "mass": 1.1, "wind": 0.25, "gravity": 0.35, "mix": 1.0},
    {"type": "physics", "name": "boob_l_phys", "bone": "boob_l", "x": 0.5, "y": 1.0, "inertia": 0.58, "strength": 115.0, "damping": 0.8, "mass": 1.15, "wind": 0.28, "gravity": 0.38, "mix": 1.0}
  ],
  "stops": [
    {"chain": "skirt_r", "against": "hip", "at": [-60, 0], "inward": -1.0, "outward": 3.5, "lower": {"inward": -1.5, "outward": 4.5}},
    {"chain": "skirt_l", "against": "hip", "at": [60, 0], "inward": -1.0, "outward": 3.5, "lower": {"inward": -1.5, "outward": 4.5}},
    {"chain": "hairback_r", "against": "chest", "at": [-80, 0], "inward": -1.5, "outward": 7.0, "lower": {"inward": -2.0, "outward": 9.0}},
    {"chain": "hairback_l", "against": "chest", "at": [80, 0], "inward": -1.5, "outward": 7.0, "lower": {"inward": -2.0, "outward": 9.0}},
    {"chain": "hair_r", "against": "chest", "at": [-75, 0], "inward": -1.5, "outward": 7.0, "lower": {"inward": -2.0, "outward": 9.0}},
    {"chain": "hair_l", "against": "chest", "at": [75, 0], "inward": -1.5, "outward": 7.0, "lower": {"inward": -2.0, "outward": 9.0}}
  ]
}

with open("config.json", "w") as f:
    json.dump(config, f, indent=2)

print("Successfully upgraded Naru 4x layers and config.json!")
