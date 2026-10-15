#!/usr/bin/env python3
"""
upgrade_luna_4x.py
Refines Luna's 4x-AnimeSharp (800x2284) rig layers and builds config.json:
  1. Cleans unused ghost layers in `full` and `head` runs (including `headwear` lace hallucination)
  2. Separates `head:neck` cleanly from `full:topwear` collar with generous under-tuck
  3. Removes the white triangle hallucination between blazer lapels (`y >= 974`) on `full:topwear` so the high-waisted black skirt shows through
  4. Merges `full:objects` (documents) and the black tablet/diary into `full:handwear-r` so both arms, hands, diary, and papers move as a single unit, while smoothing the occluded skirt surface on `full:bottomwear`
  5. Sharpens `head:eyewear` (glasses) and pre-fills 4x source RGB on all visible part surfaces to eliminate `CORE_ERODE (2px)` seams
  6. Configures blonde wavy bob physics (`hair_r`, `hair_l`, `hairback_r`, `hairback_l`), H-line skirt physics (`skirt_r`, `skirt_c`, `skirt_l`), stops, and 2D breast jiggle (`boob_r`, `boob_l`)
"""
import os
import json
from PIL import Image, ImageDraw
import numpy as np
from scipy.ndimage import distance_transform_edt, binary_dilation, binary_erosion, gaussian_filter

FAMILY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LUNA_DIR = os.path.join(FAMILY_DIR, "luna")
os.chdir(LUNA_DIR)

rgba = np.array(Image.open("inputs/painting_rgba.png"))
H, W = rgba.shape[:2]  # 2284, 800
alpha_4x = rgba[:, :, 3].copy()
luma_4x = (
    0.299 * rgba[:, :, 0].astype(np.float32) +
    0.587 * rgba[:, :, 1].astype(np.float32) +
    0.114 * rgba[:, :, 2].astype(np.float32)
)
yy_4x, xx_4x = np.mgrid[0:H, 0:W]

# Trim any light-grey rembg fringe on outer dark blazer/skirt rim (y=580..1615) so painting.png has zero white dots!
rim_4x = (alpha_4x > 0) & (~binary_erosion(alpha_4x >= 220, iterations=4))
inner_blouse_4x = (xx_4x >= 320) & (xx_4x <= 455) & (yy_4x >= 555) & (yy_4x <= 890)
hands_papers_4x = (xx_4x >= 240) & (xx_4x <= 515) & (yy_4x >= 1010) & (yy_4x <= 1435)
dark_suit_outer_rim = rim_4x & (yy_4x >= 580) & (yy_4x <= 1615) & (~inner_blouse_4x) & (~hands_papers_4x)
alpha_4x[dark_suit_outer_rim & (luma_4x > 95)] = 0

solid_4x = binary_erosion(alpha_4x >= 235, iterations=3) & (~( (yy_4x >= 580) & (yy_4x <= 1615) & (~inner_blouse_4x) & (~hands_papers_4x) & (luma_4x > 85) ))
_, solid_idx = distance_transform_edt(~solid_4x, return_indices=True)
bled_painting = rgba[:, :, :3].copy()
for c in range(3):
    bled_painting[:, :, c] = rgba[:, :, c][solid_idx[0], solid_idx[1]]

# Save binary-masked painting.png (no white alpha blending!) so --seam silhouette never stamps grey/white rim pixels!
painting = bled_painting.copy()
painting[alpha_4x < 210] = [255, 255, 255]
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
    core = core_mask if (core_mask is not None and np.any(core_mask)) else binary_erosion(arr[:, :, 3] > 215, iterations=2)
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

# head_box = [150, 270, 590, 710] (440x440)
hy_grid, hx_grid = np.mgrid[0:1024, 0:1024]
head_rx = 150.0 + (hx_grid + 0.5) * (440.0 / 1024.0)
head_ry = 270.0 + (hy_grid + 0.5) * (440.0 / 1024.0)
head_rx_clamped = np.clip(np.round(head_rx).astype(int), 0, W - 1)
head_ry_clamped = np.clip(np.round(head_ry).astype(int), 0, H - 1)
head_src_rgb = bled_painting[head_ry_clamped, head_rx_clamped]
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
used_full = {"footwear", "legwear", "bottomwear", "topwear", "handwear-r", "objects", "front hair"}
for l in full_meta["layers"]:
    if l["name"] not in used_full:
        save_layer_canvas("inputs/layers/full", full_meta, l["name"], np.zeros((1024, 1024, 4), dtype=np.uint8))

used_head = {
    "back hair", "neck", "face", "eyewhite-r", "eyewhite-l",
    "irides-r", "irides-l", "eyelash-r", "eyelash-l",
    "eyebrow-r", "eyebrow-l", "nose", "mouth", "eyewear", "front hair"
}
for l in head_meta["layers"]:
    if l["name"] not in used_head:
        save_layer_canvas("inputs/layers/head", head_meta, l["name"], np.zeros((1024, 1024, 4), dtype=np.uint8))

# ---------------------------------------------------------
# 2. HEAD:BACK HAIR & HEAD:FRONT HAIR
# ---------------------------------------------------------
h_bh = load_layer_canvas("inputs/layers/head_orig", head_meta, "back hair")
h_fh = load_layer_canvas("inputs/layers/head_orig", head_meta, "front hair")

dark_blazer_in_head = (head_ry >= 575) & (head_src_luma < 90)
h_bh[dark_blazer_in_head, 3] = 0
h_bh[(head_ry < 610) & (head_src_a < 24), 3] = 0
h_bh = prefill_rgb(h_bh)
save_layer_canvas("inputs/layers/head", head_meta, "back hair", h_bh)

h_fh[head_src_a < 16, 3] = 0
fh_vis = (h_fh[:, :, 3] > 32) & (head_src_a > 200)
for c in range(3):
    h_fh[:, :, c] = np.where(fh_vis, head_src_rgb[:, :, c], h_fh[:, :, c])
h_fh = prefill_rgb(h_fh)
save_layer_canvas("inputs/layers/head", head_meta, "front hair", h_fh)

# ---------------------------------------------------------
# 3. HEAD:NECK — Clean separation & under-tuck under white inner shirt collar
# ---------------------------------------------------------
h_neck = load_layer_canvas("inputs/layers/head_orig", head_meta, "neck")
h_face = load_layer_canvas("inputs/layers/head_orig", head_meta, "face")

neck_skin = (
    (head_rx >= 312) & (head_rx <= 425) & (head_ry >= 540) & (head_ry <= 662) &
    (head_src_a > 200) &
    (head_src_rgb[:, :, 0] > 155) &
    ((head_src_rgb[:, :, 0].astype(int) - head_src_rgb[:, :, 2].astype(int)) > 35)
)
h_neck[:, :, 3] = np.where(neck_skin, np.maximum(h_neck[:, :, 3], 255), h_neck[:, :, 3])
for c in range(3):
    h_neck[:, :, c] = np.where(neck_skin, head_src_rgb[:, :, c], h_neck[:, :, c])

blazer_on_neck = (head_ry >= 575) & (head_src_luma < 85) & ((head_rx < 322) | (head_rx > 416))
h_neck[blazer_on_neck, 3] = 0

neck_core = h_neck[:, :, 3] > 200
_, nearest_idx = distance_transform_edt(~neck_core, return_indices=True)
neck_dilated = binary_dilation(neck_core, iterations=14)
under_tuck = neck_dilated & (~neck_core) & (head_ry >= 565) & (head_ry <= 685) & (head_rx >= 308) & (head_rx <= 430)
h_neck[:, :, 3] = np.where(under_tuck, np.maximum(h_neck[:, :, 3], 255), h_neck[:, :, 3])
for c in range(3):
    h_neck[:, :, c] = np.where(under_tuck, h_neck[:, :, c][nearest_idx[0], nearest_idx[1]], h_neck[:, :, c])

h_neck = prefill_rgb(h_neck)
save_layer_canvas("inputs/layers/head", head_meta, "neck", h_neck)

h_ew = load_layer_canvas("inputs/layers/head_orig", head_meta, "eyewear")
face_occ = (h_fh[:, :, 3] > 80) | (h_ew[:, :, 3] > 80)
for enm in ["eyewhite-r", "eyewhite-l", "irides-r", "irides-l", "eyelash-r", "eyelash-l", "eyebrow-r", "eyebrow-l", "nose", "mouth"]:
    el = load_layer_canvas("inputs/layers/head_orig", head_meta, enm)
    face_occ = face_occ | (el[:, :, 3] > 80)
    el_vis = (el[:, :, 3] > 64) & (h_fh[:, :, 3] < 64) & (h_ew[:, :, 3] < 80) & (head_src_a > 200)
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

ew_vis = (h_ew[:, :, 3] > 0) & (head_src_a > 96)
for c in range(3):
    h_ew[:, :, c] = np.where(ew_vis, head_src_rgb[:, :, c], h_ew[:, :, c])
dark_frame = (h_ew[:, :, 3] > 48) & (head_src_luma < 85) & (h_fh[:, :, 3] < 128)
h_ew[:, :, 3] = np.where(dark_frame, np.maximum(h_ew[:, :, 3], 255), h_ew[:, :, 3])
h_ew = prefill_rgb(h_ew)
save_layer_canvas("inputs/layers/head", head_meta, "eyewear", h_ew)

# ---------------------------------------------------------
# 4. FULL:TOPWEAR — Remove neck skin bleed at top & white triangle at bottom center
# ---------------------------------------------------------
f_top = load_layer_canvas("inputs/layers/full_orig", full_meta, "topwear")
f_hw_r = load_layer_canvas("inputs/layers/full_orig", full_meta, "handwear-r")
f_obj = load_layer_canvas("inputs/layers/full_orig", full_meta, "objects")
f_bw = load_layer_canvas("inputs/layers/full_orig", full_meta, "bottomwear")
f_lw = load_layer_canvas("inputs/layers/full_orig", full_meta, "legwear")
f_fw = load_layer_canvas("inputs/layers/full_orig", full_meta, "footwear")

neck_in_top = (
    (full_rx >= 320) & (full_rx <= 418) & (full_ry < 658) &
    (f_top[:, :, 0].astype(int) - f_top[:, :, 2].astype(int) > 35) &
    (full_src_rgb[:, :, 0].astype(int) - full_src_rgb[:, :, 2].astype(int) > 35)
)
f_top[neck_in_top, 3] = 0

collar_rim = (
    (full_rx >= 320) & (full_rx <= 418) & (full_ry >= 640) & (full_ry <= 666) &
    (full_src_a > 200) & (f_top[:, :, 3] > 0)
)
rb_diff = (full_src_rgb[:, :, 0].astype(np.float32) - full_src_rgb[:, :, 2].astype(np.float32))
shirt_t = np.clip((42.0 - rb_diff) / 28.0, 0.0, 1.0)
f_top[:, :, 3] = np.where(collar_rim, np.round(255.0 * shirt_t).astype(np.uint8), f_top[:, :, 3])

top_luma = (
    0.299 * f_top[:, :, 0].astype(np.float32) +
    0.587 * f_top[:, :, 1].astype(np.float32) +
    0.114 * f_top[:, :, 2].astype(np.float32)
)
white_triangle = (full_rx >= 344) & (full_rx <= 436) & (full_ry >= 972) & (top_luma > 110)
f_top[white_triangle, 3] = 0
tri_dil = binary_dilation(white_triangle, iterations=2) & (~white_triangle) & (full_ry >= 972)
f_top[tri_dil, 3] = np.minimum(f_top[tri_dil, 3], 64)

# ---------------------------------------------------------
# 5. FULL:HANDWEAR-R + OBJECTS + DIARY -> Unified `handwear-r`
# ---------------------------------------------------------
def rig_to_full_pt(rx, ry):
    return ((rx + 742.0) * (1024.0 / 2284.0), ry * (1024.0 / 2284.0))

diary_poly_img = Image.new("L", (1024, 1024), 0)
ImageDraw.Draw(diary_poly_img).polygon([
    rig_to_full_pt(275, 1215),
    rig_to_full_pt(416, 1234),
    rig_to_full_pt(412, 1320),
    rig_to_full_pt(260, 1298),
], fill=255)
diary_mask = (np.array(diary_poly_img) > 128) & (full_src_a > 200)

combined_hw = f_hw_r.copy()
obj_a = f_obj[:, :, 3].astype(np.float32) / 255.0
hw_a = combined_hw[:, :, 3].astype(np.float32) / 255.0
out_a = obj_a + hw_a * (1.0 - obj_a)
safe_a = np.where(out_a > 1e-5, out_a, 1.0)
for c in range(3):
    combined_hw[:, :, c] = np.clip(
        np.round((f_obj[:, :, c].astype(np.float32) * obj_a + combined_hw[:, :, c].astype(np.float32) * hw_a * (1.0 - obj_a)) / safe_a),
        0, 255
    ).astype(np.uint8)
combined_hw[:, :, 3] = np.clip(np.round(out_a * 255.0), 0, 255).astype(np.uint8)
combined_hw[:, :, 3] = np.where(diary_mask, 255, combined_hw[:, :, 3])

hw_outer_zone = (
    ((full_rx <= 215) | (full_rx >= 490)) & (full_ry >= 600) & (full_ry <= 1225)
) | (
    (full_rx >= 245) & (full_rx <= 515) & (full_ry >= 1150) & (full_ry <= 1435)
)
near_hw = binary_dilation(combined_hw[:, :, 3] > 24, iterations=5) & hw_outer_zone & (full_src_a > 200)
combined_hw[:, :, 3] = np.where(near_hw & ((full_rx <= 190) | (full_rx >= 520)), np.maximum(combined_hw[:, :, 3], full_src_a), combined_hw[:, :, 3])
# Clamp combined_hw strictly inside 4x figure silhouette so outer sleeve edges never pick up background!
combined_hw[:, :, 3] = np.minimum(combined_hw[:, :, 3], full_src_a)

for c in range(3):
    combined_hw[:, :, c] = np.where(combined_hw[:, :, 3] > 0, full_src_rgb[:, :, c], combined_hw[:, :, c])
# Decontaminate outer sleeve edges (y <= 1050) strictly from dark sleeve core
hw_core = binary_erosion(combined_hw[:, :, 3] > 220, iterations=3) & (~((full_ry <= 1040) & (full_src_luma > 85)))
combined_hw = prefill_rgb(combined_hw, core_mask=hw_core)
save_layer_canvas("inputs/layers/full", full_meta, "handwear-r", combined_hw)
save_layer_canvas("inputs/layers/full", full_meta, "objects", np.zeros((1024, 1024, 4), dtype=np.uint8))

# ---------------------------------------------------------
# 6. FULL:BOTTOMWEAR — Smooth occluded diary/hand region & remove all edge white dots / pink hem skin
# ---------------------------------------------------------
bw_zone = (full_rx >= 145) & (full_rx <= 585) & (full_ry >= 950) & (full_ry <= 1608)
near_bw = binary_dilation(f_bw[:, :, 3] > 16, iterations=6) & bw_zone & (full_src_a > 200)
f_bw[:, :, 3] = np.where(near_bw, np.maximum(f_bw[:, :, 3], full_src_a), f_bw[:, :, 3])
f_bw[:, :, 3] = np.minimum(f_bw[:, :, 3], full_src_a)

# Trim pink leg skin at the bottom skirt hem (full_ry >= 1580)
hem_pink_skin = (full_ry >= 1580) & (
    ((full_src_rgb[:, :, 0].astype(int) - full_src_rgb[:, :, 2].astype(int)) > 16) |
    (full_src_luma > 78)
)
f_bw[hem_pink_skin, 3] = 0
f_bw[full_ry > 1608, 3] = 0

skirt_occ = binary_dilation(combined_hw[:, :, 3] > 24, iterations=4) | binary_dilation(f_top[:, :, 3] > 32, iterations=2)
# Only allow dark skirt pixels (full_src_luma < 72) in skirt_clean_core so bright paper edges or leg skin never bleed onto the skirt!
skirt_clean_core = binary_erosion(f_bw[:, :, 3] > 220, iterations=3) & (~skirt_occ) & (full_src_a > 230) & (full_src_luma < 72)
_, sk_idx = distance_transform_edt(~skirt_clean_core, return_indices=True)

occ_or_bright_on_skirt = ((f_bw[:, :, 3] > 0) & skirt_occ) | ((f_bw[:, :, 3] > 0) & (full_src_luma > 78))
w_occ_bw = np.where(occ_or_bright_on_skirt, 1.0, gaussian_filter(occ_or_bright_on_skirt.astype(np.float32), sigma=2.0))
for c in range(3):
    nearest_skirt_c = gaussian_filter(full_src_rgb[:, :, c][sk_idx[0], sk_idx[1]].astype(np.float32), sigma=2.5)
    src_c = full_src_rgb[:, :, c].astype(np.float32)
    f_bw[:, :, c] = np.clip(np.round(w_occ_bw * nearest_skirt_c + (1.0 - w_occ_bw) * src_c), 0, 255).astype(np.uint8)

f_bw = prefill_rgb(f_bw, core_mask=skirt_clean_core)
save_layer_canvas("inputs/layers/full", full_meta, "bottomwear", f_bw)

# ---------------------------------------------------------
# 7. FULL:TOPWEAR, LEGWEAR, FOOTWEAR — 100% 4x RGB on unoccluded & claim shield
# ---------------------------------------------------------
h_hair_union = np.maximum(h_fh[:, :, 3], h_bh[:, :, 3])
hair_hx = np.round((full_rx - 150.0) * (1024.0 / 440.0)).astype(int)
hair_hy = np.round((full_ry - 270.0) * (1024.0 / 440.0)).astype(int)
in_head_box = (hair_hx >= 0) & (hair_hx < 1024) & (hair_hy >= 0) & (hair_hy < 1024)
hair_hx_c = np.clip(hair_hx, 0, 1023)
hair_hy_c = np.clip(hair_hy, 0, 1023)
head_hair_in_full_a = np.where(in_head_box, h_hair_union[hair_hy_c, hair_hx_c], 0)

top_zone = (full_rx >= 115) & (full_rx <= 585) & (full_ry >= 575) & (full_ry <= 1225) & (~white_triangle) & (~neck_in_top) & (~collar_rim)
near_top = binary_dilation(f_top[:, :, 3] > 16, iterations=6) & top_zone & (full_src_a > 200) & (head_hair_in_full_a < 64)
f_top[:, :, 3] = np.where(near_top, np.maximum(f_top[:, :, 3], full_src_a), f_top[:, :, 3])
f_top[:, :, 3] = np.minimum(f_top[:, :, 3], full_src_a)

top_occ = binary_dilation((combined_hw[:, :, 3] > 32) | (head_hair_in_full_a > 64), iterations=2)
w_occ_top = np.where(top_occ, 1.0, gaussian_filter(top_occ.astype(np.float32), sigma=2.0))
for c in range(3):
    qwen_c = f_top[:, :, c].astype(np.float32)
    src_c = full_src_rgb[:, :, c].astype(np.float32)
    f_top[:, :, c] = np.clip(np.round(w_occ_top * qwen_c + (1.0 - w_occ_top) * src_c), 0, 255).astype(np.uint8)

inner_blouse_full = (full_rx >= 320) & (full_rx <= 455) & (full_ry >= 555) & (full_ry <= 890)
top_core = binary_erosion(f_top[:, :, 3] > 220, iterations=3) & (~((~inner_blouse_full) & (full_src_luma > 82)))
f_top = prefill_rgb(f_top, core_mask=top_core)
save_layer_canvas("inputs/layers/full", full_meta, "topwear", f_top)

shield_canvas = np.zeros((1024, 1024, 4), dtype=np.uint8)
shield_mask = binary_dilation(head_hair_in_full_a > 64, iterations=3)
shield_canvas[:, :, 3] = np.where(shield_mask, 255, 0)
save_layer_canvas("inputs/layers/full", full_meta, "front hair", shield_canvas)

# Extend legwear up to y=1565 strictly within the exact leg widths (x=204..292 and x=444..532) so there is zero gap and zero protruding pink tab!
in_leg_cols = ((full_rx >= 204) & (full_rx <= 292)) | ((full_rx >= 444) & (full_rx <= 532))
f_lw[(full_ry <= 1615) & (~in_leg_cols), 3] = 0
lw_tuck = in_leg_cols & (full_ry >= 1565) & (full_ry <= 1615) & (full_src_a > 200)
f_lw[:, :, 3] = np.where(lw_tuck, 255, f_lw[:, :, 3])
lw_zone = (full_rx >= 165) & (full_rx <= 680) & (full_ry >= 1565) & (full_ry <= 2245) & ((full_ry > 1615) | in_leg_cols)
near_lw = binary_dilation(f_lw[:, :, 3] > 16, iterations=5) & lw_zone & (full_src_a > 120)
f_lw[:, :, 3] = np.where(near_lw, np.maximum(f_lw[:, :, 3], full_src_a), f_lw[:, :, 3])
f_lw[:, :, 3] = np.minimum(f_lw[:, :, 3], full_src_a)

lw_occ = binary_dilation((f_bw[:, :, 3] > 32) | (f_fw[:, :, 3] > 32), iterations=2)
lw_skin_core = (f_lw[:, :, 3] > 220) & (~lw_occ) & (full_src_luma > 95)
_, lw_idx = distance_transform_edt(~lw_skin_core, return_indices=True)
w_occ_lw = np.where(lw_occ, 1.0, gaussian_filter(lw_occ.astype(np.float32), sigma=2.0))
for c in range(3):
    skin_c = full_src_rgb[:, :, c][lw_idx[0], lw_idx[1]].astype(np.float32)
    src_c = full_src_rgb[:, :, c].astype(np.float32)
    f_lw[:, :, c] = np.clip(np.round(w_occ_lw * skin_c + (1.0 - w_occ_lw) * src_c), 0, 255).astype(np.uint8)
f_lw = prefill_rgb(f_lw, core_mask=lw_skin_core)
save_layer_canvas("inputs/layers/full", full_meta, "legwear", f_lw)

fw_zone = (full_rx >= 280) & (full_rx <= 685) & (full_ry >= 2000) & (full_ry <= 2265)
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
# 8. Write Luna's 4x config.json (No skirt physics; jacket hem physics + dome bust jiggle)
# ---------------------------------------------------------
config = {
  "key": "luna",
  "seethrough": {
    "resolution": 1024,
    "steps": 30,
    "seed": 42,
    "offload": True,
    "head_box": [150, 270, 590, 710]
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
      ["handwear_r", "full", "handwear-r"],
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
      ["eyewear", "head", "eyewear"],
      ["hair_front", "head", "front hair"]
    ]
  },
  "bones": [
    {"name": "hip", "parent": "root", "at": [368, 1020]},
    {"name": "chest", "parent": "hip", "at": [368, 790]},
    {"name": "neck", "parent": "chest", "at": [370, 625]},
    {"name": "head", "parent": "neck", "at": [370, 555]},
    {"name": "eye_r", "parent": "head", "at": [365, 456]},
    {"name": "eye_l", "parent": "head", "at": [445, 474]},
    {"name": "brow_r", "parent": "head", "at": [376, 432]},
    {"name": "brow_l", "parent": "head", "at": [457, 449]},
    {"name": "mouth", "parent": "head", "at": [400, 524]},
    {"name": "boob_r", "parent": "chest", "at": [315, 785]},
    {"name": "boob_l", "parent": "chest", "at": [430, 785]},
    {
      "chain": "hairback_r",
      "parent": "head",
      "points": [[260, 420], [235, 510], [220, 585]],
      "tip": [220, 650]
    },
    {
      "chain": "hairback_l",
      "parent": "head",
      "points": [[465, 440], [480, 525], [485, 595]],
      "tip": [475, 660]
    },
    {
      "chain": "hair_r",
      "parent": "head",
      "points": [[275, 430], [250, 520], [235, 595]],
      "tip": [245, 675]
    },
    {
      "chain": "hair_l",
      "parent": "head",
      "points": [[475, 445], [485, 535], [485, 610]],
      "tip": [468, 690]
    },
    {
      "chain": "bang_r",
      "parent": "head",
      "points": [[345, 360], [340, 405]],
      "tip": [335, 445]
    },
    {
      "chain": "bang_c",
      "parent": "head",
      "points": [[400, 360], [405, 410]],
      "tip": [410, 455]
    },
    {
      "chain": "bang_l",
      "parent": "head",
      "points": [[455, 375], [460, 420]],
      "tip": [465, 465]
    },
    {
      "chain": "arms_hold",
      "parent": "chest",
      "points": [[368, 610], [368, 920], [368, 1180]],
      "tip": [368, 1410]
    },
    {
      "chain": "hem_r",
      "parent": "chest",
      "points": [[235, 965], [220, 1065]],
      "tip": [210, 1170]
    },
    {
      "chain": "hem_l",
      "parent": "chest",
      "points": [[485, 965], [505, 1065]],
      "tip": [525, 1165]
    }
  ],
  "meshes": {
    "hair_back": {
      "grid": 57,
      "r": 15,
      "segments": [
        ["head", [370, 555], [370, 310]],
        "hairback_r",
        "hairback_l"
      ]
    },
    "hair_front": {
      "grid": 57,
      "r": 10,
      "segments": [
        ["head", [370, 555], [370, 310]],
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
        ["chest", [370, 635], [368, 790]],
        ["head", [370, 555], [370, 490]]
      ]
    },
    "handwear_r": {
      "grid": 57,
      "r": 12,
      "segments": ["arms_hold"]
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
          {"name": "bust_r", "shape": "circle", "cx": 308, "cy": 785, "r": 16, "bone": "boob_r", "spacing": 14, "band": 32},
          {"name": "bust_l", "shape": "circle", "cx": 436, "cy": 785, "r": 16, "bone": "boob_l", "spacing": 14, "band": 32}
        ]
      },
      "r": 15,
      "segments": [
        ["chest", [368, 630], [368, 960]],
        "hem_r",
        "hem_l"
      ]
    }
  },
  "regions": {
    "shoes": "root",
    "legwear": "hip",
    "bottomwear": "hip",
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
    "brow_l": "brow_l",
    "eyewear": "head"
  },
  "motion": {
    "duration": 3.3333333333333335,
    "tracks": [
      {"bone": "chest", "prop": "translatey", "amp": 5.0, "period": 3.3333333333333335, "phase": 0, "base": 5.0},
      {"bone": "chest", "prop": "scalex", "amp": 0.004, "period": 3.3333333333333335, "phase": 0, "base": 1.004},
      {"bone": "head", "prop": "rotate", "amp": 0.85, "period": 3.3333333333333335, "phase": 0.12},
      {"bone": "neck", "prop": "rotate", "amp": 0.35, "period": 3.3333333333333335, "phase": 0.08},
      {"bone": "boob_r", "prop": "translatey", "amp": 2.0, "period": 3.3333333333333335, "phase": 0.12},
      {"bone": "boob_r", "prop": "translatex", "amp": 0.6, "period": 3.3333333333333335, "phase": 0.12},
      {"bone": "boob_l", "prop": "translatey", "amp": 2.2, "period": 3.3333333333333335, "phase": 0.18},
      {"bone": "boob_l", "prop": "translatex", "amp": 0.7, "period": 3.3333333333333335, "phase": 0.18},
      {"chain": "hairback_r", "amps": [0.35, 0.8, 1.4], "period": 3.3333333333333335, "phase": 0.2, "lag": 0.08},
      {"chain": "hairback_l", "amps": [0.35, 0.8, 1.4], "period": 3.3333333333333335, "phase": 0.24, "lag": 0.08},
      {"chain": "hair_r", "amps": [0.4, 0.9, 1.5], "period": 3.3333333333333335, "phase": 0.21, "lag": 0.08},
      {"chain": "hair_l", "amps": [0.4, 0.9, 1.5], "period": 3.3333333333333335, "phase": 0.25, "lag": 0.08},
      {"chain": "bang_r", "amps": [0.5, 1.1], "period": 3.3333333333333335, "phase": 0.18, "lag": 0.1},
      {"chain": "bang_c", "amps": [0.45, 1.0], "period": 3.3333333333333335, "phase": 0.18, "lag": 0.1},
      {"chain": "bang_l", "amps": [0.5, 1.1], "period": 3.3333333333333335, "phase": 0.18, "lag": 0.1},
      {"chain": "arms_hold", "amps": [0.15, 0.55, 1.1], "period": 3.3333333333333335, "phase": 0.22, "lag": 0.08},
      {"chain": "hem_r", "amps": [0.2, 0.45], "period": 3.3333333333333335, "phase": 0.28, "lag": 0.08},
      {"chain": "hem_l", "amps": [0.2, 0.45], "period": 3.3333333333333335, "phase": 0.32, "lag": 0.08}
    ],
    "blink": {
      "t": 0.85,
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
    {"type": "physics", "name": "hem_r0_phys", "bone": "hem_r0", "rotate": 1, "inertia": 0.3, "strength": 240.0, "damping": 0.9, "mass": 1, "wind": 0.15, "gravity": 0.15, "mix": 1},
    {"type": "physics", "name": "hem_r1_phys", "bone": "hem_r1", "rotate": 1, "inertia": 0.4, "strength": 190.0, "damping": 0.88, "mass": 1, "wind": 0.3, "gravity": 0.25, "mix": 1},
    {"type": "physics", "name": "hem_l0_phys", "bone": "hem_l0", "rotate": 1, "inertia": 0.3, "strength": 240.0, "damping": 0.9, "mass": 1, "wind": 0.15, "gravity": 0.15, "mix": 1},
    {"type": "physics", "name": "hem_l1_phys", "bone": "hem_l1", "rotate": 1, "inertia": 0.4, "strength": 190.0, "damping": 0.88, "mass": 1, "wind": 0.3, "gravity": 0.25, "mix": 1},
    {"type": "physics", "name": "boob_r_phys", "bone": "boob_r", "x": 0.55, "y": 1.0, "inertia": 0.65, "strength": 90.0, "damping": 0.74, "mass": 1.2, "wind": 0.35, "gravity": 0.45, "mix": 1.0},
    {"type": "physics", "name": "boob_l_phys", "bone": "boob_l", "x": 0.6, "y": 1.0, "inertia": 0.72, "strength": 85.0, "damping": 0.72, "mass": 1.25, "wind": 0.4, "gravity": 0.5, "mix": 1.0}
  ],
  "stops": [
    {"chain": "hem_r", "against": "hip", "at": [-60, 0], "inward": -1.0, "outward": 3.5, "lower": {"inward": -1.5, "outward": 4.5}},
    {"chain": "hem_l", "against": "hip", "at": [60, 0], "inward": -1.0, "outward": 3.5, "lower": {"inward": -1.5, "outward": 4.5}},
    {"chain": "hairback_r", "against": "chest", "at": [-80, 0], "inward": -1.5, "outward": 7.0, "lower": {"inward": -2.0, "outward": 9.0}},
    {"chain": "hairback_l", "against": "chest", "at": [80, 0], "inward": -1.5, "outward": 7.0, "lower": {"inward": -2.0, "outward": 9.0}},
    {"chain": "hair_r", "against": "chest", "at": [-75, 0], "inward": -1.5, "outward": 7.0, "lower": {"inward": -2.0, "outward": 9.0}},
    {"chain": "hair_l", "against": "chest", "at": [75, 0], "inward": -1.5, "outward": 7.0, "lower": {"inward": -2.0, "outward": 9.0}}
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

print("Successfully upgraded Luna 4x layers, config.json, and requirements.json!")
