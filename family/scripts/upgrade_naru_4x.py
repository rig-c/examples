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
# 2. HEAD:BACK HAIR, FRONT HAIR, NECK — Preserve 100% of See-through's hidden regions!
# ---------------------------------------------------------
h_bh = load_layer_canvas("inputs/layers/head_orig", head_meta, "back hair")
h_fh = load_layer_canvas("inputs/layers/head_orig", head_meta, "front hair")
h_neck = load_layer_canvas("inputs/layers/head_orig", head_meta, "neck")
h_face = load_layer_canvas("inputs/layers/head_orig", head_meta, "face")
h_tp = load_layer_canvas("inputs/layers/head_orig", head_meta, "topwear")

head_rb = head_src_rgb[:, :, 0].astype(int) - head_src_rgb[:, :, 2].astype(int)

# Keep See-through's full hidden interior behind face, neck, and front hair on `h_bh`!
# Only trim below y=662 (where shirt body / cat badge start) and restore the right outer brown hair strands (x=515..565, y=440..658)
bh_interior_occluded = (h_face[:, :, 3] > 32) | (h_neck[:, :, 3] > 32) | (h_fh[:, :, 3] > 32)
true_brown_hair_outer = (
    (head_ry >= 440) & (head_ry <= 658) & (~bh_interior_occluded) &
    (head_src_a > 80) & (head_src_rgb[:, :, 2] < 122) & (head_rb >= 16) & (head_src_luma < 142)
)
h_bh[:, :, 3] = np.where(true_brown_hair_outer, np.maximum(h_bh[:, :, 3], head_src_a), h_bh[:, :, 3])
# Clear white shirt / background outside the occluded interior
not_hair_outer = (~bh_interior_occluded) & (head_ry >= 525) & (~true_brown_hair_outer) & ((head_src_rgb[:, :, 2] >= 120) | (head_src_luma >= 145) | (head_src_a < 32))
h_bh[not_hair_outer, 3] = 0
h_bh[head_ry > 662, 3] = 0
h_bh[(~bh_interior_occluded) & (head_src_a < 24), 3] = 0

# Ensure the hidden region behind face/neck/front-hair is 100% solid so physics motion NEVER tears or shows a hole!
bh_hidden_fill = binary_erosion(h_bh[:, :, 3] > 128, iterations=2) & bh_interior_occluded & (head_ry <= 655)
h_bh[bh_hidden_fill, 3] = 255

lbl_bh, n_bh = label(h_bh[:, :, 3] > 0)
for cid in range(1, n_bh + 1):
    comp = lbl_bh == cid
    if comp.sum() < 250:
        h_bh[comp, 3] = 0

# Blend 4x brown hair RGB ONLY where `h_bh` is genuinely visible (NOT occluded by face, neck, front hair, or shirt)!
bh_occ_dil = binary_dilation(bh_interior_occluded | (h_tp[:, :, 3] > 128), iterations=3)
bh_vis_only = (h_bh[:, :, 3] > 0) & (~bh_occ_dil) & (head_src_a > 160) & (head_src_rgb[:, :, 2] < 115) & (head_rb >= 18)
w_bh_vis = gaussian_filter(bh_vis_only.astype(np.float32), sigma=1.5)
for c in range(3):
    orig_c = h_bh[:, :, c].astype(np.float32)
    src_c = head_src_rgb[:, :, c].astype(np.float32)
    h_bh[:, :, c] = np.clip(np.round(w_bh_vis * src_c + (1.0 - w_bh_vis) * orig_c), 0, 255).astype(np.uint8)
h_bh = prefill_rgb(h_bh, core_mask=(h_bh[:, :, 3] > 200))
save_layer_canvas("inputs/layers/head", head_meta, "back hair", h_bh)

# `head:front hair` (`h_fh`): keep See-through's full front hair + side locks intact!
h_fh[head_src_a < 24, 3] = 0
fh_vis = (h_fh[:, :, 3] > 128) & (head_src_a > 180) & (head_src_rgb[:, :, 2] < 120) & (head_rb >= 18)
w_fh_vis = gaussian_filter(fh_vis.astype(np.float32), sigma=1.2)
for c in range(3):
    orig_c = h_fh[:, :, c].astype(np.float32)
    src_c = head_src_rgb[:, :, c].astype(np.float32)
    h_fh[:, :, c] = np.clip(np.round(w_fh_vis * src_c + (1.0 - w_fh_vis) * orig_c), 0, 255).astype(np.uint8)
h_fh = prefill_rgb(h_fh, core_mask=(h_fh[:, :, 3] > 200))
save_layer_canvas("inputs/layers/head", head_meta, "front hair", h_fh)

# HEAD:NECK — Keep See-through's clean inpainted neck cylinder + smooth under-tuck beneath shirt V-neck!
vis_neck_skin = (
    (head_rx >= 345) & (head_rx <= 438) & (head_ry >= 555) & (head_ry <= 715) &
    (h_face[:, :, 3] < 64) & (h_fh[:, :, 3] < 64) &
    (head_src_a > 200) & (head_src_rgb[:, :, 0] > 165) & (head_rb > 38) & (head_src_rgb[:, :, 2] < 145)
)
h_neck[:, :, 3] = np.where(vis_neck_skin, np.maximum(h_neck[:, :, 3], 255), h_neck[:, :, 3])
neck_under_tuck = binary_dilation(h_neck[:, :, 3] > 128, iterations=14) & (head_ry >= 585) & (head_ry <= 730) & (head_rx >= 338) & (head_rx <= 445)
h_neck[neck_under_tuck, 3] = np.maximum(h_neck[neck_under_tuck, 3], 248)

w_neck_vis = gaussian_filter(vis_neck_skin.astype(np.float32), sigma=1.5)
for c in range(3):
    orig_c = h_neck[:, :, c].astype(np.float32)
    src_c = head_src_rgb[:, :, c].astype(np.float32)
    h_neck[:, :, c] = np.clip(np.round(w_neck_vis * src_c + (1.0 - w_neck_vis) * orig_c), 0, 255).astype(np.uint8)
h_neck = prefill_rgb(h_neck, core_mask=(h_neck[:, :, 3] > 180))
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
# 3. FULL LAYERS: TOPWEAR (with hidden collar/shoulders under hair), BOTTOMWEAR, LEGWEAR, FOOTWEAR
# ---------------------------------------------------------
f_top = load_layer_canvas("inputs/layers/full_orig", full_meta, "topwear")
f_hw = load_layer_canvas("inputs/layers/full_orig", full_meta, "handwear-l")
f_bw = load_layer_canvas("inputs/layers/full_orig", full_meta, "bottomwear")
f_lw = load_layer_canvas("inputs/layers/full_orig", full_meta, "legwear")
f_fw = load_layer_canvas("inputs/layers/full_orig", full_meta, "footwear")

save_layer_canvas("inputs/layers/full", full_meta, "back hair", np.zeros((1024, 1024, 4), dtype=np.uint8))

# Map `h_fh`, `h_bh`, `h_neck`, and `h_tp` (`head_orig:topwear`) into `full` 1024 space
hair_hx = np.round((full_rx - 160.0) * (1024.0 / 440.0)).astype(int)
hair_hy = np.round((full_ry - 300.0) * (1024.0 / 440.0)).astype(int)
in_head_box_full = (hair_hx >= 0) & (hair_hx < 1024) & (hair_hy >= 0) & (hair_hy < 1024)
hair_hx_c = np.clip(hair_hx, 0, 1023)
hair_hy_c = np.clip(hair_hy, 0, 1023)
h_fh_in_full_a = np.where(in_head_box_full, h_fh[:, :, 3][hair_hy_c, hair_hx_c], 0)
h_neck_in_full_a = np.where(in_head_box_full, h_neck[:, :, 3][hair_hy_c, hair_hx_c], 0)
h_tp_in_full_a = np.where(in_head_box_full, h_tp[:, :, 3][hair_hy_c, hair_hx_c], 0)
h_tp_in_full_rgb = np.zeros_like(full_src_rgb)
for c in range(3):
    h_tp_in_full_rgb[:, :, c] = np.where(in_head_box_full, h_tp[:, :, c][hair_hy_c, hair_hx_c], 0)

vneck_left_x = np.interp(full_ry, [600, 645, 685, 712], [352, 360, 382, 401])
vneck_right_x = np.interp(full_ry, [600, 645, 685, 712], [436, 426, 412, 401])
in_vneck_opening = (full_ry >= 600) & (full_ry <= 712) & (full_rx >= vneck_left_x) & (full_rx <= vneck_right_x)

full_rb = full_src_rgb[:, :, 0].astype(int) - full_src_rgb[:, :, 2].astype(int)
# Cut ONLY the exposed V-neck skin out of `f_top` — keep 100% of the shirt collar and shoulders behind the hair!
neck_skin_on_top = in_vneck_opening & (h_neck_in_full_a >= 180) & (full_rb > 38)
neck_in_top = (full_ry < 602) | neck_skin_on_top

# Merge HANDWEAR-L (Both sleeves + clasped hands) into TOPWEAR using the 2px-eroded 4x silhouette (`full_src_a_tight`) on outer edges!
save_layer_canvas("inputs/layers/full", full_meta, "handwear-l", np.zeros((1024, 1024, 4), dtype=np.uint8))
combined_top_a = np.maximum(f_top[:, :, 3], f_hw[:, :, 3])
combined_top_a = np.where(in_head_box_full & (full_ry <= 725) & (~neck_in_top), np.maximum(combined_top_a, h_tp_in_full_a), combined_top_a)
combined_top_a[neck_in_top] = 0

upper_shirt_body = (full_ry >= 602) & (full_ry <= 955) & (~neck_in_top) & (combined_top_a > 24) & (full_src_a_tight > 0)
lower_cuffs_hands = (full_ry > 955) & (full_ry <= 1022) & (combined_top_a > 24) & (full_src_a_tight > 0)

f_top[:, :, 3] = np.where(upper_shirt_body, full_src_a_tight, np.where(lower_cuffs_hands, np.minimum(combined_top_a, full_src_a_tight), 0))
f_top[neck_in_top, 3] = 0

# Where `topwear` is hidden behind brown hair (`h_fh` or brown pixels above y=662), use See-through's clean white shirt collar/shoulder inpainting (`h_tp_in_full_rgb`)!
hair_over_collar = (full_ry <= 665) & ((h_fh_in_full_a > 24) | ((full_src_rgb[:, :, 2] < 130) & (full_rb > 18))) & (~in_vneck_opening)
w_hair_collar = np.where(hair_over_collar, 1.0, gaussian_filter(hair_over_collar.astype(np.float32), sigma=1.5))
w_hair_collar = np.where(full_ry > 670, 0.0, w_hair_collar)
for c in range(3):
    src_c = full_src_rgb[:, :, c].astype(np.float32)
    htp_c = np.where(h_tp_in_full_a > 64, h_tp_in_full_rgb[:, :, c].astype(np.float32), f_top[:, :, c].astype(np.float32))
    f_top[:, :, c] = np.clip(np.round(w_hair_collar * htp_c + (1.0 - w_hair_collar) * src_c), 0, 255).astype(np.uint8)

f_top = prefill_rgb(f_top, core_mask=binary_erosion(f_top[:, :, 3] > 215, iterations=1))
save_layer_canvas("inputs/layers/full", full_meta, "topwear", f_top)

# Shield on `full:front hair` so `projectSource` never stamps hair onto `topwear` collar!
f_fh_shield = np.zeros((1024, 1024, 4), dtype=np.uint8)
f_fh_shield[hair_over_collar & (f_top[:, :, 3] > 0), 3] = 255
save_layer_canvas("inputs/layers/full", full_meta, "front hair", f_fh_shield)

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

# (e) LEGWEAR & FOOTWEAR — Preserve See-through's continuous leg contour and clean skin shading across the skirt hem!
is_leg_skin = ((full_src_rgb[:, :, 0].astype(int) - full_src_rgb[:, :, 2].astype(int)) > 24) & (full_src_luma > 74)

# Smoothly taper only the hidden upper-left leg edge inside the skirt (`y = 1550..1834`) so it meets the real calf edge (`x = 276` at `y = 1834`) with ZERO step/notch and never pokes out when the skirt swings right!
leg_left_bound = np.interp(full_ry, [1550, 1720, 1805, 1834, 1900], [310, 300, 286, 276, 282])
leg_right_bound = np.interp(full_ry, [1550, 1720, 1805, 1834, 1900], [450, 458, 464, 464, 450])
f_lw[(full_ry <= 1834) & ((full_rx < leg_left_bound) | (full_rx > leg_right_bound)), 3] = 0

# Tighten exposed calf silhouette below the skirt to the clean 4x alpha (never cutting holes along the skirt hem!)
lw_below_skirt_zone = (full_rx >= 274) & (full_rx <= 466) & (full_ry >= 1830) & (full_ry <= 2230) & (f_bw[:, :, 3] < 64) & is_leg_skin
near_lw_below = binary_dilation(f_lw[:, :, 3] > 16, iterations=4) & lw_below_skirt_zone & (full_src_a > 128)
f_lw[:, :, 3] = np.where(near_lw_below, np.maximum(f_lw[:, :, 3], full_src_a), f_lw[:, :, 3])
f_lw[:, :, 3] = np.minimum(f_lw[:, :, 3], full_src_a)

# CRITICAL: Cap hidden upper leg + 2px skirt-hem border at alpha=248 (< CORE_ALPHA 250) so `projectSource` and `seamOverride` NEVER stamp the dark skirt hem outline onto `legwear`!
skirt_plus_rim = binary_dilation(f_bw[:, :, 3] > 4, iterations=2)
f_lw[skirt_plus_rim & (f_lw[:, :, 3] > 248), 3] = 248

# Use 4x skin detail where true unoccluded leg skin is visible; under the skirt and along the dark skirt hem border, use See-through's clean inpainted leg RGB!
exposed_leg_skin = is_leg_skin & (~skirt_plus_rim) & (full_ry >= 1825) & (~binary_dilation(f_fw[:, :, 3] > 32, iterations=2))
w_exposed_lw = gaussian_filter(exposed_leg_skin.astype(np.float32), sigma=1.5)
for c in range(3):
    qwen_c = f_lw[:, :, c].astype(np.float32)
    src_c = full_src_rgb[:, :, c].astype(np.float32)
    f_lw[:, :, c] = np.clip(np.round((1.0 - w_exposed_lw) * qwen_c + w_exposed_lw * src_c), 0, 255).astype(np.uint8)
f_lw = prefill_rgb(f_lw, core_mask=(f_lw[:, :, 3] > 180) & (exposed_leg_skin | (f_bw[:, :, 3] > 64)))
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
# 4. Write Naru's 4x config.json (Light-Medium Perky bust jiggle + full hidden hair/collar regions)
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
        "hairback_l"
      ]
    },
    "hair_front": {
      "grid": 57,
      "r": 12,
      "segments": [
        ["head", [380, 575], [380, 330]],
        "bang_r",
        "bang_c",
        "bang_l",
        "hair_r",
        "hair_l"
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
          {"name": "bust_r", "shape": "circle", "cx": 312, "cy": 785, "r": 24, "bone": "boob_r", "spacing": 14, "band": 38},
          {"name": "bust_l", "shape": "circle", "cx": 448, "cy": 785, "r": 24, "bone": "boob_l", "spacing": 14, "band": 38}
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
    {"type": "physics", "name": "boob_r_phys", "bone": "boob_r", "x": 0.29, "y": 1.0, "inertia": 0.4995, "strength": 375.0, "damping": 0.87, "mass": 1.10, "wind": 0.19, "gravity": 0.11, "mix": 1.0},
    {"type": "physics", "name": "boob_l_phys", "bone": "boob_l", "x": 0.31, "y": 1.0, "inertia": 0.5265, "strength": 368.0, "damping": 0.87, "mass": 1.13, "wind": 0.21, "gravity": 0.11, "mix": 1.0}
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
