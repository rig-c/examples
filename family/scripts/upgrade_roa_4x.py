#!/usr/bin/env python3
"""
upgrade_roa_4x.py
Refines Roa's 4x-AnimeSharp (800x2284) rig layers and builds config.json:
  1. Fills occluded dark hair inside hoop earrings & under right jaw in `head:back hair`
  2. Cleanly separates `head:neck` from `full:topwear` V-neck collar with generous under-tuck & 4x RGB pre-fill
  3. Merges `full:objects` (coffee cup) into `full:handwear-r` so hand and cup move as one seamless unit
  4. Trims shirt-chest bleed from `full:handwear-l` while preserving Qwen's inpainted white shirt under the fingers on `full:topwear`
  5. Pre-fills visible 4x source RGB across internal part boundaries so `CORE_ERODE (2px)` leaves zero dotted seams
  6. Adds wavy bob hair physics (`hairback_r`, `hairback_l`), wide-pants physics, stops, and 2D breast jiggle (`boob_r`, `boob_l`)
"""
import os
import json
from PIL import Image
import numpy as np
from scipy.ndimage import distance_transform_edt, binary_dilation, binary_erosion, gaussian_filter

FAMILY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROA_DIR = os.path.join(FAMILY_DIR, "roa")
os.chdir(ROA_DIR)

rgba = np.array(Image.open("inputs/painting_rgba.png"))
painting = np.array(Image.open("inputs/painting.png"))
H, W = rgba.shape[:2]  # 2284, 800
alpha_4x = rgba[:, :, 3]

# Bleed interior RGB outward so sampling near silhouette edges never picks up [255, 255, 255] background!
solid_4x = binary_erosion(alpha_4x >= 240, iterations=2)
_, solid_idx = distance_transform_edt(~solid_4x, return_indices=True)
bled_painting = rgba[:, :, :3].copy()
for c in range(3):
    bled_painting[:, :, c] = rgba[:, :, c][solid_idx[0], solid_idx[1]]

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
    core = core_mask if (core_mask is not None and np.any(core_mask)) else binary_erosion(arr[:, :, 3] > 210, iterations=2)
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
full_src_rgb = bled_painting[full_ry_clamped, full_rx_clamped]
full_src_a = np.where(full_in_bounds, alpha_4x[full_ry_clamped, full_rx_clamped], 0)
full_src_luma = (
    0.299 * full_src_rgb[:, :, 0].astype(np.float32) +
    0.587 * full_src_rgb[:, :, 1].astype(np.float32) +
    0.114 * full_src_rgb[:, :, 2].astype(np.float32)
)

hy_grid, hx_grid = np.mgrid[0:1024, 0:1024]
head_rx = 120.0 + (hx_grid + 0.5) * (440.0 / 1024.0)
head_ry = 110.0 + (hy_grid + 0.5) * (440.0 / 1024.0)
head_rx_clamped = np.clip(np.round(head_rx).astype(int), 0, W - 1)
head_ry_clamped = np.clip(np.round(head_ry).astype(int), 0, H - 1)
head_src_rgb = bled_painting[head_ry_clamped, head_rx_clamped]
head_src_a = alpha_4x[head_ry_clamped, head_rx_clamped]
head_src_luma = (
    0.299 * head_src_rgb[:, :, 0].astype(np.float32) +
    0.587 * head_src_rgb[:, :, 1].astype(np.float32) +
    0.114 * head_src_rgb[:, :, 2].astype(np.float32)
)
head_rb = head_src_rgb[:, :, 0].astype(np.int32) - head_src_rgb[:, :, 2].astype(np.int32)

os.system("rm -rf inputs/layers/full inputs/layers/head && cp -r inputs/layers/full_orig inputs/layers/full && cp -r inputs/layers/head_orig inputs/layers/head")

# ---------------------------------------------------------
# 1. HEAD:BACK HAIR — Preserve all brown hair curls on both sides of neck while stripping skin/collar
# ---------------------------------------------------------
from scipy.ndimage import label

h_bh = load_layer_canvas("inputs/layers/head_orig", head_meta, "back hair")
f_bh = load_layer_canvas("inputs/layers/full_orig", full_meta, "back hair")
h_face = load_layer_canvas("inputs/layers/head_orig", head_meta, "face")
h_earw = load_layer_canvas("inputs/layers/head_orig", head_meta, "earwear")

full_rb = full_src_rgb[:, :, 0].astype(np.int32) - full_src_rgb[:, :, 2].astype(np.int32)
full_rg = full_src_rgb[:, :, 0].astype(np.int32) - full_src_rgb[:, :, 1].astype(np.int32)

# Include dark hair under jaw/earrings ONLY where source is true dark brown hair (never warm skin or lavender shirt!)
is_warm_skin_or_gold = (
    ((head_src_rgb[:, :, 1] > 88) & (head_src_rgb[:, :, 0] > 130)) |
    ((head_src_rgb[:, :, 0] > 135) & (head_rb > 36))
)
is_true_brown_hair = (
    (head_src_a > 200) &
    (head_src_luma < 118) &
    (head_src_rgb[:, :, 2] < 102) &
    (head_rb >= 6) &
    (~is_warm_skin_or_gold)
)
is_collar_hair_edge = (
    (head_ry >= 395) &
    (head_src_a > 200) &
    (head_src_luma < 134) &
    (head_src_rgb[:, :, 2] < 112) &
    (head_rb >= 10) &
    (~is_warm_skin_or_gold)
)
valid_brown_hair = is_true_brown_hair | (is_collar_hair_edge & binary_dilation(is_true_brown_hair, iterations=2))

jaw_hair_zone = (head_rx >= 225) & (head_rx <= 465) & (head_ry >= 325) & (head_ry <= 495)
# Narrow neck/chin center mask so left hair curls (x <= 307) and right hair curls (x >= 353) are 100% preserved!
face_neck_center = (
    ((head_rx >= 302) & (head_rx <= 400) & (head_ry >= 325) & (head_ry <= 352)) |
    ((head_rx >= 308) & (head_rx <= 368) & (head_ry > 352) & (head_ry <= 405)) |
    ((head_rx >= 308) & (head_rx <= 352) & (head_ry > 405) & (head_ry <= 448)) |
    ((head_rx >= 308) & (head_rx <= 380) & (head_ry > 448) & (head_ry <= 505))
)
dark_hair_fill = jaw_hair_zone & valid_brown_hair & (~face_neck_center)
h_bh[:, :, 3] = np.where(dark_hair_fill, 255, h_bh[:, :, 3])

# Strictly strip non-brown-hair pixels (face cheek, mouth, gold earrings, neck skin, and lavender/white shirt collar!) from h_bh for y >= 315
h_bh[(head_ry >= 315) & (~valid_brown_hair), 3] = 0
h_bh[face_neck_center, 3] = 0
h_bh[head_src_a < 48, 3] = 0
h_bh[(head_ry >= 315) & (h_bh[:, :, 3] < 140), 3] = 0

# Remove small disconnected islands (< 180 px)
lbl_bh, n_bh = label(h_bh[:, :, 3] > 0)
for cid in range(1, n_bh + 1):
    comp = lbl_bh == cid
    if comp.sum() < 180:
        h_bh[comp, 3] = 0

# Solidify lower curls and the area behind the right hoop earring in `h_bh` with dark brown hair so there is zero hole behind `face`!
right_hoop_patch = (head_rx >= 388) & (head_rx <= 432) & (head_ry >= 342) & (head_ry <= 416) & (head_src_a > 200)
lower_curls_1px = binary_dilation((head_ry >= 360) & (h_bh[:, :, 3] >= 140), iterations=1) & (~face_neck_center) & (~is_warm_skin_or_gold) & (head_src_luma < 140)
h_bh[lower_curls_1px | right_hoop_patch, 3] = 255
h_bh[(head_ry >= 340) & (h_bh[:, :, 3] > 0), 3] = 255

# Inject 4x brown hair RGB and decontaminate from pure dark-brown interior core
vis_bh = (h_bh[:, :, 3] > 0) & valid_brown_hair & (~right_hoop_patch)
for c in range(3):
    h_bh[:, :, c] = np.where(vis_bh, head_src_rgb[:, :, c], h_bh[:, :, c])
bh_core = binary_erosion(is_true_brown_hair & (h_bh[:, :, 3] > 200) & (~right_hoop_patch), iterations=1) & (head_src_luma < 105) & (head_src_rgb[:, :, 2] < 92)
h_bh = prefill_rgb(h_bh, core_mask=bh_core)
save_layer_canvas("inputs/layers/head", head_meta, "back hair", h_bh)

# Keep only the left-side earring (head_rx < 340) in `earwear` (driven by `earring` chain),
# and place the entire right-side gold hoop earring + inner shadow patch onto `face` (driven by `head`) so no thin gold crescent boundary exists between `hair_back` and `face`!
h_face = prefill_rgb(h_face)
right_hoop_zone = (head_rx >= 390) & (head_rx <= 430) & (head_ry >= 345) & (head_ry <= 414) & (head_src_a > 200)
right_hoop_rgb_zone = binary_dilation(right_hoop_zone, iterations=4)
h_face[:, :, 3] = np.where(right_hoop_zone, 255, h_face[:, :, 3])
for c in range(3):
    h_face[:, :, c] = np.where(right_hoop_rgb_zone, head_src_rgb[:, :, c], h_face[:, :, c])
save_layer_canvas("inputs/layers/head", head_meta, "face", h_face)

h_earw[head_rx >= 340, 3] = 0
h_earw = prefill_rgb(h_earw)
save_layer_canvas("inputs/layers/head", head_meta, "earwear", h_earw)

# ---------------------------------------------------------
# 2. HEAD:NECK — Generous under-tuck under earring/hair on left and under V-neck collar
# ---------------------------------------------------------
h_neck = load_layer_canvas("inputs/layers/head_orig", head_meta, "neck")
neck_left_x = np.interp(head_ry, [345, 385, 420, 460, 472, 498, 528, 545], [270, 272, 294, 290, 284, 318, 346, 348])
neck_right_x = np.interp(head_ry, [345, 400, 435, 475, 505, 528, 545], [378, 368, 354, 366, 364, 360, 360])

in_neck_bounds = (
    (head_ry >= 345) & (head_ry <= 538) &
    (head_rx >= neck_left_x - 22.0) &
    (head_rx <= neck_right_x + 22.0)
)
vis_neck = (
    (head_ry >= 350) & (head_ry <= 528) &
    (head_rx >= neck_left_x) & (head_rx <= neck_right_x) &
    (head_src_rgb[:, :, 0] > 145) & (head_rb > 35)
)
h_neck[~in_neck_bounds, 3] = 0
h_neck[in_neck_bounds, 3] = 255
for c in range(3):
    h_neck[:, :, c] = np.where(vis_neck, head_src_rgb[:, :, c], h_neck[:, :, c])

_, neck_idx = distance_transform_edt(~vis_neck, return_indices=True)
tuck_only = in_neck_bounds & (~vis_neck)
for c in range(3):
    h_neck[:, :, c] = np.where(tuck_only, h_neck[:, :, c][neck_idx[0], neck_idx[1]], h_neck[:, :, c])

h_neck = prefill_rgb(h_neck, core_mask=vis_neck)
save_layer_canvas("inputs/layers/head", head_meta, "neck", h_neck)

# Clear unused `8 full:neck` so it cannot interfere with full run's pixelOwners
f_neck_unused = np.zeros((1024, 1024, 4), dtype=np.uint8)
save_layer_canvas("inputs/layers/full", full_meta, "neck", f_neck_unused)

# ---------------------------------------------------------
# 3. FULL:TOPWEAR (Unified with resting left arm `handwear-l` so hand & shirt never tear!)
# ---------------------------------------------------------
f_tw_orig = load_layer_canvas("inputs/layers/full_orig", full_meta, "topwear")
f_hwl_orig = load_layer_canvas("inputs/layers/full_orig", full_meta, "handwear-l")

# Clear unused `handwear-l` layer
save_layer_canvas("inputs/layers/full", full_meta, "handwear-l", np.zeros((1024, 1024, 4), dtype=np.uint8))

# Map cleaned `h_bh` into full space
h_bh_hx = np.clip(np.round((full_rx - 120.0) * (1024.0 / 440.0)).astype(int), 0, 1023)
h_bh_hy = np.clip(np.round((full_ry - 110.0) * (1024.0 / 440.0)).astype(int), 0, 1023)
in_head_box_full = (full_rx >= 120) & (full_rx < 560) & (full_ry >= 110) & (full_ry < 550)
h_bh_in_full_a = np.where(in_head_box_full, h_bh[h_bh_hy, h_bh_hx, 3], 0)

# Build unified `full:topwear` from `f_tw_orig` + `f_hwl_orig`
f_tw = f_tw_orig.copy()
combined_tw_a = np.maximum(f_tw_orig[:, :, 3], f_hwl_orig[:, :, 3])
tw_outer_zone = (full_rx >= 160) & (full_rx <= 755) & (full_ry >= 398) & (full_ry <= 965)
near_tw = binary_dilation(combined_tw_a > 24, iterations=4) & tw_outer_zone & (full_src_a > 96)
f_tw[:, :, 3] = np.where(near_tw, np.maximum(combined_tw_a, full_src_a), combined_tw_a)
f_tw[:, :, 3] = np.minimum(f_tw[:, :, 3], full_src_a)

# Ensure shirt collar & shoulders under hair curls (y=410..520, x=210..480) are 100% solid where figure exists (and not neck skin)
collar_under_hair = (
    (full_rx >= 210) & (full_rx <= 485) & (full_ry >= 412) & (full_ry <= 520) &
    (full_src_a > 200)
)
f_tw[:, :, 3] = np.where(collar_under_hair, 255, f_tw[:, :, 3])

# Trim boxy Qwen ghost blocks floating above the natural sloping shoulder lines!
left_sh_y_lim = np.interp(full_rx, [160, 215, 260, 295], [492, 468, 412, 398])
right_sh_y_lim = np.interp(full_rx, [375, 410, 465, 535], [398, 412, 462, 488])
above_shoulders = ((full_rx <= 295) & (full_ry < left_sh_y_lim)) | ((full_rx >= 375) & (full_rx <= 535) & (full_ry < right_sh_y_lim))
f_tw[above_shoulders, 3] = 0

left_torso_edge = (full_rx >= 165) & (full_rx <= 228) & (full_ry >= 460) & (full_ry <= 845) & (f_tw[:, :, 3] > 96)
f_tw[left_torso_edge, 3] = 255

# Clean dark hair pixels at top of `f_tw` (y < 525) ONLY where `h_bh_in_full_a` covers `topwear`, keeping 100% crisp 4x RGB everywhere visible!
occluded_by_hair = (h_bh_in_full_a >= 64) & (full_ry < 525)

shirt_clean_ref = (
    (f_tw[:, :, 3] > 220) & (~occluded_by_hair) &
    (full_ry >= 415) & (full_ry <= 650) &
    (full_src_luma > 180) & (full_src_rgb[:, :, 2] > 165) & (full_rb < 45)
)
_, shirt_idx = distance_transform_edt(~shirt_clean_ref, return_indices=True)
inpainted_shirt_rgb = full_src_rgb[shirt_idx[0], shirt_idx[1]].copy()
for c in range(3):
    inpainted_shirt_rgb[:, :, c] = np.clip(
        np.round(gaussian_filter(inpainted_shirt_rgb[:, :, c].astype(np.float32), sigma=2.5)), 0, 255
    ).astype(np.uint8)

blend_w = gaussian_filter(occluded_by_hair.astype(np.float32), sigma=1.5)
blend_w = np.where(occluded_by_hair, 1.0, blend_w)
blend_w = np.where((full_ry >= 525) | (h_bh_in_full_a < 16), 0.0, blend_w)
for c in range(3):
    f_tw[:, :, c] = np.clip(
        np.round(inpainted_shirt_rgb[:, :, c] * blend_w + full_src_rgb[:, :, c] * (1.0 - blend_w)),
        0, 255
    ).astype(np.uint8)

# Clean V-neck opening on `full:topwear`: remove warm neck skin inside V-neck with a smooth 2.5px ramp
f_neck_left_x = np.interp(full_ry, [350, 385, 420, 460, 472, 498, 526], [272, 276, 298, 294, 288, 325, 351])
f_neck_right_x = np.interp(full_ry, [350, 400, 435, 475, 505, 526], [375, 365, 350, 358, 356, 353])
in_vneck_box = (full_ry >= 345) & (full_ry <= 525) & (full_rx >= f_neck_left_x + 1.0) & (full_rx <= f_neck_right_x - 1.0)
skin_score = (full_src_rgb[:, :, 0].astype(np.float32) - full_src_rgb[:, :, 2].astype(np.float32)) - 38.0
vneck_keep_factor = np.where(in_vneck_box & (~occluded_by_hair), np.clip(1.0 - (skin_score / 14.0), 0.0, 1.0), 1.0)
clear_neck_skin = in_vneck_box & ((full_src_rgb[:, :, 0].astype(int) - full_src_rgb[:, :, 2].astype(int)) > 42)
f_tw[:, :, 3] = np.round(f_tw[:, :, 3].astype(np.float32) * vneck_keep_factor).astype(np.uint8)
f_tw[clear_neck_skin, 3] = 0

vneck_fringe = in_vneck_box & (f_tw[:, :, 3] > 0) & (f_tw[:, :, 3] < 250)
for c in range(3):
    f_tw[:, :, c] = np.where(vneck_fringe, inpainted_shirt_rgb[:, :, c], f_tw[:, :, c])

f_tw = prefill_rgb(f_tw)
save_layer_canvas("inputs/layers/full", full_meta, "topwear", f_tw)

# ---------------------------------------------------------
# 4. FULL:HANDWEAR-R + FULL:OBJECTS (Coffee cup merged into right arm)
# ---------------------------------------------------------
f_hwr = load_layer_canvas("inputs/layers/full_orig", full_meta, "handwear-r")
f_obj = load_layer_canvas("inputs/layers/full_orig", full_meta, "objects")

a_o = f_obj[:, :, 3:4].astype(np.float32) / 255.0
a_h = f_hwr[:, :, 3:4].astype(np.float32) / 255.0
out_a = a_o + a_h * (1.0 - a_o)
out_rgb = np.where(out_a > 1e-5, (f_obj[:, :, :3] * a_o + f_hwr[:, :, :3] * a_h * (1.0 - a_o)) / np.maximum(out_a, 1e-5), 0)
f_hwr_merged = np.zeros_like(f_hwr)
f_hwr_merged[:, :, :3] = np.clip(np.round(out_rgb), 0, 255).astype(np.uint8)
f_hwr_merged[:, :, 3] = np.clip(np.round(out_a[:, :, 0] * 255.0), 0, 255).astype(np.uint8)

arm_cup_outer = (full_rx >= 50) & (full_rx <= 215) & (full_ry >= 490) & (full_ry <= 1430)
near_hwr = binary_dilation(f_hwr_merged[:, :, 3] > 32, iterations=4) & arm_cup_outer & (full_src_a > 96)
f_hwr_merged[:, :, 3] = np.where(near_hwr, np.maximum(f_hwr_merged[:, :, 3], full_src_a), f_hwr_merged[:, :, 3])
for c in range(3):
    f_hwr_merged[:, :, c] = np.where(near_hwr, full_src_rgb[:, :, c], f_hwr_merged[:, :, c])

f_hwr_merged = prefill_rgb(f_hwr_merged)
save_layer_canvas("inputs/layers/full", full_meta, "handwear-r", f_hwr_merged)

# ---------------------------------------------------------
# 5. FULL:BOTTOMWEAR & FULL:FOOTWEAR — Preserve See-through's exact separation of pants and both shoes
# ---------------------------------------------------------
f_bw = load_layer_canvas("inputs/layers/full_orig", full_meta, "bottomwear")
f_fw = load_layer_canvas("inputs/layers/full_orig", full_meta, "footwear")

# Keep See-through's exact bottomwear alpha, stripping semi-transparent ghosting or warm shoe-vamp skin at the hem (`y >= 2045`)!
bw_upper_zone = (full_rx >= 160) & (full_rx <= 565) & (full_ry >= 830) & (full_ry <= 2000)
near_bw_upper = binary_dilation(f_bw[:, :, 3] > 24, iterations=2) & bw_upper_zone & (full_src_a > 96) & (f_fw[:, :, 3] == 0)
f_bw[:, :, 3] = np.where(near_bw_upper, np.maximum(f_bw[:, :, 3], full_src_a), f_bw[:, :, 3])
f_bw[:, :, 3] = np.minimum(f_bw[:, :, 3], full_src_a)

shoe_vamp_or_sole = (full_ry >= 2045) & ((full_rb > 22) | (full_src_luma > 62) | (f_bw[:, :, 3] < 140))
f_bw[shoe_vamp_or_sole, 3] = 0
f_bw[(full_ry >= 2000) & (f_bw[:, :, 3] >= 140) & (full_src_a > 200), 3] = 255

bw_fw_overlap = (f_bw[:, :, 3] > 0) & (f_fw[:, :, 3] > 0)
bw_dark_core = binary_erosion((f_bw[:, :, 3] > 210) & (full_src_luma < 56) & (full_rb < 18), iterations=1)
_, bw_dark_idx = distance_transform_edt(~bw_dark_core, return_indices=True)
for c in range(3):
    f_bw[:, :, c] = np.where(
        (f_bw[:, :, 3] > 0) & (~bw_fw_overlap) & (full_src_luma < 60) & (full_rb < 20),
        full_src_rgb[:, :, c],
        full_src_rgb[:, :, c][bw_dark_idx[0], bw_dark_idx[1]]
    )
f_bw = prefill_rgb(f_bw, core_mask=bw_dark_core)
save_layer_canvas("inputs/layers/full", full_meta, "bottomwear", f_bw)

# For footwear (`f_fw`), preserve BOTH shoes and See-through's hidden upper-foot inpainting under the pants hem!
fw_vis_below_pants = (full_ry >= 2030) & (full_src_a > 32) & (f_bw[:, :, 3] < 128)
f_fw[:, :, 3] = np.where(fw_vis_below_pants, np.maximum(f_fw[:, :, 3], full_src_a), f_fw[:, :, 3])
f_fw[f_bw[:, :, 3] == 0, 3] = np.minimum(f_fw[f_bw[:, :, 3] == 0, 3], full_src_a[f_bw[:, :, 3] == 0])
for c in range(3):
    f_fw[:, :, c] = np.where(fw_vis_below_pants, full_src_rgb[:, :, c], f_fw[:, :, c])
# Cap the hidden under-tuck of footwear (where covered by bottomwear) at alpha=248 (< CORE_ALPHA 250)
f_fw[bw_fw_overlap & (f_fw[:, :, 3] > 248), 3] = 248
f_fw = prefill_rgb(f_fw)
save_layer_canvas("inputs/layers/full", full_meta, "footwear", f_fw)

# Build clean occlusion shield on unused `19 full:front hair` strictly inside opaque hair_back AND pants-to-shoe overlap!
f_fh_shield = np.zeros((1024, 1024, 4), dtype=np.uint8)
shield_mask_tw = binary_erosion(h_bh_in_full_a >= 220, iterations=1) | bw_fw_overlap
f_fh_shield[shield_mask_tw, 3] = 255
save_layer_canvas("inputs/layers/full", full_meta, "front hair", f_fh_shield)

# ---------------------------------------------------------
# 6. CRISP FACIAL FEATURES
# ---------------------------------------------------------
f_ebr = load_layer_canvas("inputs/layers/full_orig", full_meta, "eyebrow-r")
f_ebr[:, :, 3] = np.where(f_ebr[:, :, 3] > 80, 255, f_ebr[:, :, 3])
f_ebr = prefill_rgb(f_ebr)
save_layer_canvas("inputs/layers/full", full_meta, "eyebrow-r", f_ebr)

h_ebl = load_layer_canvas("inputs/layers/head_orig", head_meta, "eyebrow")
h_ebl[:, :, 3] = np.where(h_ebl[:, :, 3] > 90, 255, h_ebl[:, :, 3])
h_ebl = prefill_rgb(h_ebl)
save_layer_canvas("inputs/layers/head", head_meta, "eyebrow", h_ebl)

with open("inputs/layers/full/layers.json", "w") as f:
    json.dump(full_meta, f, indent=2)
with open("inputs/layers/head/layers.json", "w") as f:
    json.dump(head_meta, f, indent=2)

# ---------------------------------------------------------
# 7. GENERATE FULL 4X CONFIG.JSON WITH PHYSICS, STOPS & BREAST JIGGLE
# ---------------------------------------------------------
cfg = {
  "key": "roa",
  "seethrough": {
    "resolution": 1024,
    "steps": 30,
    "seed": 42,
    "offload": True,
    "head_box": [120, 110, 560, 550]
  },
  "assemble": {
    "rig_scale": 1.0,
    "plan": [
      ["shoes", "full", "footwear"],
      ["bottomwear", "full", "bottomwear"],
      ["handwear_r", "full", "handwear-r"],
      ["neck", "head", "neck"],
      ["topwear", "full", "topwear"],
      ["hair_back", "head", "back hair"],
      ["ear_l", "head", "ears-l"],
      ["earring", "head", "earwear"],
      ["face", "head", "face"],
      ["nose", "head", "nose"],
      ["mouth", "head", "mouth"],
      ["lash_r", "head", "eyelash-r"],
      ["lash_l", "head", "eyelash-l"],
      ["brow_r", "full", "eyebrow-r"],
      ["brow_l", "head", "eyebrow"],
      ["ear_r", "head", "ears-r"],
      ["hair_front", "head", "front hair"]
    ]
  },
  "bones": [
    {"name": "hip", "parent": "root", "at": [360, 863]},
    {"name": "chest", "parent": "hip", "at": [360, 657]},
    {"name": "neck", "parent": "chest", "at": [365, 450]},
    {"name": "head", "parent": "neck", "at": [365, 394]},
    {"name": "brow_r", "parent": "head", "at": [342, 273]},
    {"name": "mouth", "parent": "head", "at": [357, 372]},
    {"name": "boob_r", "parent": "chest", "at": [296, 650]},
    {"name": "boob_l", "parent": "chest", "at": [438, 650]},
    {
      "chain": "hairback_r",
      "parent": "head",
      "points": [[245, 290], [235, 375], [225, 445]],
      "tip": [235, 502]
    },
    {
      "chain": "hairback_l",
      "parent": "head",
      "points": [[455, 305], [468, 385], [465, 448]],
      "tip": [458, 495]
    },
    {
      "chain": "bang_r",
      "parent": "head",
      "points": [[321, 190], [311, 233]],
      "tip": [303, 283]
    },
    {
      "chain": "bang_c",
      "parent": "head",
      "points": [[365, 181], [365, 228]],
      "tip": [365, 283]
    },
    {
      "chain": "bang_l",
      "parent": "head",
      "points": [[409, 190], [419, 233]],
      "tip": [427, 283]
    },
    {
      "chain": "earring",
      "parent": "head",
      "points": [[274, 331]],
      "tip": [274, 415]
    },
    {
      "chain": "sleeve_r",
      "parent": "chest",
      "points": [[125, 510], [135, 777], [133, 1080]],
      "tip": [145, 1415]
    },
    {
      "chain": "skirt_r",
      "parent": "hip",
      "points": [[295, 1580], [312, 1780], [330, 1980]],
      "tip": [350, 2180]
    },
    {
      "chain": "skirt_c",
      "parent": "hip",
      "points": [[366, 1580], [368, 1780], [370, 1980]],
      "tip": [372, 2180]
    },
    {
      "chain": "skirt_l",
      "parent": "hip",
      "points": [[415, 1580], [410, 1780], [404, 1980]],
      "tip": [398, 2180]
    }
  ],
  "meshes": {
    "hair_back": {
      "grid": 57,
      "r": 15,
      "segments": [
        ["head", [365, 430], [365, 164]],
        "hairback_r",
        "hairback_l"
      ]
    },
    "hair_front": {
      "grid": 57,
      "r": 7,
      "segments": [
        ["head", [365, 394], [365, 167]],
        "bang_r",
        "bang_c",
        "bang_l"
      ]
    },
    "earring": {
      "grid": 57,
      "r": 4,
      "segments": [
        ["head", [274, 321], [274, 329]],
        "earring"
      ]
    },
    "neck": {
      "grid": 57,
      "r": 5,
      "segments": [
        ["chest", [365, 468], [365, 657]],
        ["head", [365, 394], [365, 344]]
      ]
    },
    "handwear_r": {
      "grid": 57,
      "r": 6,
      "segments": ["sleeve_r"]
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
          {"name": "bust_r", "shape": "circle", "cx": 296, "cy": 650, "r": 26, "bone": "boob_r", "spacing": 14, "band": 42},
          {"name": "bust_l", "shape": "circle", "cx": 438, "cy": 650, "r": 28, "bone": "boob_l", "spacing": 14, "band": 44}
        ]
      },
      "r": 15,
      "segments": [
        ["chest", [360, 427], [360, 843]],
        ["hip", [360, 843], [360, 963]]
      ]
    },
    "bottomwear": {
      "grid": 57,
      "r": 15,
      "segments": [
        ["hip", [201, 868], [519, 868]],
        ["hip", [295, 880], [295, 1520]],
        ["hip", [352, 880], [352, 1520]],
        ["hip", [415, 880], [415, 1520]],
        "skirt_r",
        "skirt_c",
        "skirt_l"
      ]
    }
  },
  "regions": {
    "shoes": "root",
    "ear_l": "head",
    "face": "head",
    "nose": "head",
    "mouth": "mouth",
    "lash_r": "head",
    "lash_l": "head",
    "brow_r": "brow_r",
    "ear_r": "head",
    "brow_l": "head"
  },
  "motion": {
    "duration": 3.3333333333333335,
    "tracks": [
      {"bone": "chest", "prop": "translatey", "amp": 5.16, "period": 3.3333333333333335, "phase": 0, "base": 5.16},
      {"bone": "chest", "prop": "scalex", "amp": 0.004, "period": 3.3333333333333335, "phase": 0, "base": 1.004},
      {"bone": "head", "prop": "rotate", "amp": 0.9, "period": 3.3333333333333335, "phase": 0.12},
      {"bone": "neck", "prop": "rotate", "amp": 0.35, "period": 3.3333333333333335, "phase": 0.08},
      {"bone": "boob_r", "prop": "translatey", "amp": 3.4, "period": 3.3333333333333335, "phase": 0.14},
      {"bone": "boob_r", "prop": "translatex", "amp": 1.0, "period": 3.3333333333333335, "phase": 0.14},
      {"bone": "boob_l", "prop": "translatey", "amp": 3.7, "period": 3.3333333333333335, "phase": 0.20},
      {"bone": "boob_l", "prop": "translatex", "amp": 1.15, "period": 3.3333333333333335, "phase": 0.20},
      {"chain": "hairback_r", "amps": [0.15, 0.45, 0.85], "period": 3.3333333333333335, "phase": 0.2, "lag": 0.08},
      {"chain": "hairback_l", "amps": [0.15, 0.45, 0.85], "period": 3.3333333333333335, "phase": 0.24, "lag": 0.08},
      {"chain": "bang_r", "amps": [0.6, 1.3], "period": 3.3333333333333335, "phase": 0.18, "lag": 0.1},
      {"chain": "bang_c", "amps": [0.5, 1.1], "period": 3.3333333333333335, "phase": 0.18, "lag": 0.1},
      {"chain": "bang_l", "amps": [0.6, 1.3], "period": 3.3333333333333335, "phase": 0.18, "lag": 0.1},
      {"chain": "earring", "amps": [2.2], "period": 1.6666666666666667, "phase": 0.25, "lag": 0},
      {"chain": "sleeve_r", "amps": [0.2, 0.5, 0.9], "period": 3.3333333333333335, "phase": 0.22, "lag": 0.08},
      {"chain": "skirt_r", "amps": [0.06, 0.15, 0.3], "period": 3.3333333333333335, "phase": 0.3, "lag": 0.07},
      {"chain": "skirt_c", "amps": [0.06, 0.15, 0.3], "period": 3.3333333333333335, "phase": 0.34, "lag": 0.07},
      {"chain": "skirt_l", "amps": [0.06, 0.15, 0.3], "period": 3.3333333333333335, "phase": 0.38, "lag": 0.07}
    ]
  },
  "constraints": [
    {"type": "physics", "name": "hairback_r0_phys", "bone": "hairback_r0", "rotate": 1, "inertia": 0.25, "strength": 260.0, "damping": 0.92, "mass": 1, "wind": 0.1, "gravity": 0.1, "mix": 1},
    {"type": "physics", "name": "hairback_r1_phys", "bone": "hairback_r1", "rotate": 1, "inertia": 0.4, "strength": 200.0, "damping": 0.9, "mass": 1, "wind": 0.25, "gravity": 0.2, "mix": 1},
    {"type": "physics", "name": "hairback_r2_phys", "bone": "hairback_r2", "rotate": 1, "inertia": 0.5, "strength": 160.0, "damping": 0.88, "mass": 1, "wind": 0.45, "gravity": 0.35, "mix": 1},
    {"type": "physics", "name": "hairback_l0_phys", "bone": "hairback_l0", "rotate": 1, "inertia": 0.25, "strength": 260.0, "damping": 0.92, "mass": 1, "wind": 0.1, "gravity": 0.1, "mix": 1},
    {"type": "physics", "name": "hairback_l1_phys", "bone": "hairback_l1", "rotate": 1, "inertia": 0.4, "strength": 200.0, "damping": 0.9, "mass": 1, "wind": 0.25, "gravity": 0.2, "mix": 1},
    {"type": "physics", "name": "hairback_l2_phys", "bone": "hairback_l2", "rotate": 1, "inertia": 0.5, "strength": 160.0, "damping": 0.88, "mass": 1, "wind": 0.45, "gravity": 0.35, "mix": 1},
    {"type": "physics", "name": "bang_r0_phys", "bone": "bang_r0", "rotate": 1, "inertia": 0.25, "strength": 240.0, "damping": 0.9, "mass": 1, "wind": 0.15, "gravity": 0.1, "mix": 1},
    {"type": "physics", "name": "bang_r1_phys", "bone": "bang_r1", "rotate": 1, "inertia": 0.35, "strength": 180.0, "damping": 0.88, "mass": 1, "wind": 0.35, "gravity": 0.2, "mix": 1},
    {"type": "physics", "name": "bang_c0_phys", "bone": "bang_c0", "rotate": 1, "inertia": 0.25, "strength": 240.0, "damping": 0.9, "mass": 1, "wind": 0.15, "gravity": 0.1, "mix": 1},
    {"type": "physics", "name": "bang_c1_phys", "bone": "bang_c1", "rotate": 1, "inertia": 0.35, "strength": 180.0, "damping": 0.88, "mass": 1, "wind": 0.35, "gravity": 0.2, "mix": 1},
    {"type": "physics", "name": "bang_l0_phys", "bone": "bang_l0", "rotate": 1, "inertia": 0.25, "strength": 240.0, "damping": 0.9, "mass": 1, "wind": 0.15, "gravity": 0.1, "mix": 1},
    {"type": "physics", "name": "bang_l1_phys", "bone": "bang_l1", "rotate": 1, "inertia": 0.35, "strength": 180.0, "damping": 0.88, "mass": 1, "wind": 0.35, "gravity": 0.2, "mix": 1},
    {"type": "physics", "name": "skirt_r0_phys", "bone": "skirt_r0", "rotate": 1, "inertia": 0.2, "strength": 280.0, "damping": 0.92, "mass": 1, "wind": 0.08, "gravity": 0.1, "mix": 1},
    {"type": "physics", "name": "skirt_r1_phys", "bone": "skirt_r1", "rotate": 1, "inertia": 0.25, "strength": 240.0, "damping": 0.9, "mass": 1, "wind": 0.15, "gravity": 0.15, "mix": 1},
    {"type": "physics", "name": "skirt_r2_phys", "bone": "skirt_r2", "rotate": 1, "inertia": 0.3, "strength": 200.0, "damping": 0.88, "mass": 1, "wind": 0.25, "gravity": 0.2, "mix": 1},
    {"type": "physics", "name": "skirt_c0_phys", "bone": "skirt_c0", "rotate": 1, "inertia": 0.2, "strength": 280.0, "damping": 0.92, "mass": 1, "wind": 0.08, "gravity": 0.1, "mix": 1},
    {"type": "physics", "name": "skirt_c1_phys", "bone": "skirt_c1", "rotate": 1, "inertia": 0.25, "strength": 240.0, "damping": 0.9, "mass": 1, "wind": 0.15, "gravity": 0.15, "mix": 1},
    {"type": "physics", "name": "skirt_c2_phys", "bone": "skirt_c2", "rotate": 1, "inertia": 0.3, "strength": 200.0, "damping": 0.88, "mass": 1, "wind": 0.25, "gravity": 0.2, "mix": 1},
    {"type": "physics", "name": "skirt_l0_phys", "bone": "skirt_l0", "rotate": 1, "inertia": 0.2, "strength": 280.0, "damping": 0.92, "mass": 1, "wind": 0.08, "gravity": 0.1, "mix": 1},
    {"type": "physics", "name": "skirt_l1_phys", "bone": "skirt_l1", "rotate": 1, "inertia": 0.25, "strength": 240.0, "damping": 0.9, "mass": 1, "wind": 0.15, "gravity": 0.15, "mix": 1},
    {"type": "physics", "name": "skirt_l2_phys", "bone": "skirt_l2", "rotate": 1, "inertia": 0.3, "strength": 200.0, "damping": 0.88, "mass": 1, "wind": 0.25, "gravity": 0.2, "mix": 1},
    {"type": "physics", "name": "boob_r_phys", "bone": "boob_r", "x": 0.75, "y": 1.0, "inertia": 1.12, "strength": 58.0, "damping": 0.46, "mass": 1.45, "wind": 0.55, "gravity": 0.65, "mix": 1.0},
    {"type": "physics", "name": "boob_l_phys", "bone": "boob_l", "x": 0.80, "y": 1.0, "inertia": 1.18, "strength": 54.0, "damping": 0.45, "mass": 1.50, "wind": 0.60, "gravity": 0.70, "mix": 1.0}
  ],
  "stops": [
    {"chain": "skirt_r", "against": "hip", "at": [-20, 0], "inward": -1.0, "outward": 3.5, "lower": {"inward": -1.5, "outward": 4.5}},
    {"chain": "skirt_l", "against": "hip", "at": [20, 0], "inward": -1.0, "outward": 3.5, "lower": {"inward": -1.5, "outward": 4.5}},
    {"chain": "hairback_r", "against": "chest", "at": [-80, 0], "inward": -1.5, "outward": 7.0, "lower": {"inward": -2.0, "outward": 9.0}},
    {"chain": "hairback_l", "against": "chest", "at": [80, 0], "inward": -1.5, "outward": 7.0, "lower": {"inward": -2.0, "outward": 9.0}}
  ]
}

with open("config.json", "w") as f:
    json.dump(cfg, f, indent=2)
print("Saved polished Roa 800x2284 config.json & layers!")