#!/usr/bin/env python3
"""Universal zero-polygon automatic 5-part clothing decomposition from See-through v3 layers.

Derives shoes, bottomwear, neck, topwear, and sleeves 100% automatically from:
  1. Full-pass See-through v3 semantic layers (inputs/layers/full_orig)
  2. Registered 4x upscaled clothing source (inputs/upscale-run/registered-upscaled.png)
  3. Accepted office character bone/part metadata (family/<char>/config.json, out/parts.json)

Zero manual polygons or hardcoded coordinate arrays are used.
"""
import json
import os
import pathlib
import shutil

os.environ.update(OMP_NUM_THREADS="4", OPENBLAS_NUM_THREADS="4", MKL_NUM_THREADS="4")
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import (
    binary_closing,
    binary_dilation,
    binary_erosion,
    binary_fill_holes,
    binary_opening,
    distance_transform_edt,
    gaussian_filter,
    label,
)

W, H = 800, 2284
OFFICE_CLOTHING = {
    "shoes",
    "legwear",
    "bottomwear",
    "neck",
    "neckwear",
    "topwear",
    "handwear_r",
    "handwear_l",
}
ORDER = ["shoes", "bottomwear", "neck", "topwear", "sleeves"]


def clean_1024(array: np.ndarray, min_px: int = 60) -> np.ndarray:
    alpha = array[:, :, 3].copy()
    # Clear See-through v3 bottom-right corner watermark artifact at (1000:, 1000:)
    alpha[1000:, 1000:] = 0
    components, n = label(alpha > 8, np.ones((3, 3), dtype=bool))
    if n == 0:
        return np.zeros_like(array)
    counts = np.bincount(components.ravel())
    counts[0] = 0
    keep = counts >= max(min_px, int(counts.max()) * 0.005)
    keep[0] = False
    result = array.copy()
    result[~keep[components], 3] = 0
    return result


def detail_and_color_error(arr_rgb: np.ndarray, ref_rgb: np.ndarray, sigma_patch: float = 10.0) -> np.ndarray:
    arr_f = arr_rgb[:, :, :3].astype(np.float32)
    ref_f = ref_rgb[:, :, :3].astype(np.float32)
    col_diff = np.max(np.abs(arr_f - ref_f), axis=2)
    arr_hp = arr_f - gaussian_filter(arr_f, sigma=(3.5, 3.5, 0.0))
    ref_hp = ref_f - gaussian_filter(ref_f, sigma=(3.5, 3.5, 0.0))
    hp_diff = np.max(np.abs(arr_hp - ref_hp), axis=2)
    total = col_diff + 3.0 * hp_diff
    return gaussian_filter(total, sigma=sigma_patch)


def color_error_smooth(arr_rgb: np.ndarray, ref_rgb: np.ndarray, sigma_patch: float = 8.0) -> np.ndarray:
    col_diff = np.max(np.abs(arr_rgb[:, :, :3].astype(np.float32) - ref_rgb[:, :, :3].astype(np.float32)), axis=2)
    return gaussian_filter(col_diff, sigma=sigma_patch)


def build_auto_parts(family: pathlib.Path, outfit: str, char: str):
    home = family / "outfits" / outfit / char
    raw = home / "inputs/layers/full_orig"
    source = np.array(Image.open(home / "inputs/upscale-run/registered-upscaled.png").convert("RGBA"))
    white = np.array(Image.open(home / "inputs/painting-clothing-source.png").convert("RGBA"))
    manifest = json.loads((raw / "layers.json").read_text())
    if [manifest["width"], manifest["height"]] != [1024, 1024]:
        raise RuntimeError(f"{outfit.upper()}_STATIC_FULL_FRAME_REQUIRED")

    cfg = json.loads((family / char / "config.json").read_text())
    hip_y = next(b["at"][1] for b in cfg["bones"] if b.get("name") == "hip")
    boob_y = max(b["at"][1] for b in cfg["bones"] if b.get("name") in ("boob_r", "boob_l"))

    baseline_parts = json.loads((family / char / "out/parts.json").read_text())["parts"]
    baseline_by_name = {p["name"]: p for p in baseline_parts}
    common_parts = {p["name"]: p for p in baseline_parts if p["name"] not in OFFICE_CLOTHING}
    baseline_neck = baseline_by_name["neck"]
    baseline_shoes = baseline_by_name["shoes"]

    mapped = {}
    layer_order = []
    layer_idx_map = {}
    for i, e in enumerate(manifest["layers"]):
        tag = e["name"]
        p = raw / "parts" / (tag + ".png")
        if not p.is_file():
            continue
        im = Image.open(p).convert("RGBA")
        c1024 = Image.new("RGBA", (1024, 1024))
        c1024.alpha_composite(im, (e["left"], e["top"]))
        cleaned = clean_1024(np.array(c1024))
        if np.count_nonzero(cleaned[:, :, 3] > 8) == 0:
            continue
        # Resize in premultiplied alpha space so transparent [0,0,0,0] pixels never bleed dark halos into edges
        a_f = cleaned[:, :, 3:4].astype(np.float32) / 255.0
        pre = np.concatenate([np.round(cleaned[:, :, :3].astype(np.float32) * a_f).astype(np.uint8), cleaned[:, :, 3:4]], axis=2)
        pre800 = np.array(
            Image.fromarray(pre, "RGBA").resize((2284, 2284), Image.Resampling.BICUBIC).crop((742, 0, 1542, 2284))
        )
        a800 = pre800[:, :, 3:4].astype(np.float32) / 255.0
        rgb800 = np.where(a800 > 1e-3, np.clip(np.round(pre800[:, :, :3].astype(np.float32) / np.maximum(a800, 1e-3)), 0, 255), 0).astype(np.uint8)
        arr800 = np.concatenate([rgb800, pre800[:, :, 3:4]], axis=2)
        if np.count_nonzero(arr800[:, :, 3] > 16) < 200:
            continue
        mapped[tag] = arr800
        layer_order.append(tag)
        layer_idx_map[tag] = i

    # Upper hair/head mask from See-through v3: above collar, plus any genuine hair strands down to boob_y
    hair_cutoff_y = baseline_neck["y"] + baseline_neck["h"]
    hair_st = np.zeros((H, W), dtype=bool)
    for htag in ["back hair", "front hair", "face", "ears-l", "ears-r", "earwear"]:
        if htag in mapped:
            hair_st |= (mapped[htag][:, :, 3] > 32)
    hair_st[hair_cutoff_y:, :] = False
    # Also mask genuine hair strands between hair_cutoff_y and boob_y+60 where hair layer matches source better than clothing
    low_hair_limit_y = min(H, int(boob_y) + 60)
    for htag in ["back hair", "front hair"]:
        if htag in mapped:
            h_arr = mapped[htag]
            col_h = color_error_smooth(h_arr, white, sigma_patch=2.5)
            h_band = (np.arange(H)[:, None] >= hair_cutoff_y) & (np.arange(H)[:, None] < low_hair_limit_y) & (h_arr[:, :, 3] > 80) & (col_h < 28.0)
            hair_st |= h_band

    # Raw topwear (+ neckwear) before bridge cuts
    top_canvas = Image.new("RGBA", (W, H))
    for t in layer_order:
        if t in ("topwear", "neckwear") and t in mapped:
            top_canvas.alpha_composite(Image.fromarray(mapped[t], "RGBA"))
    raw_top = np.array(top_canvas)

    # Raw bottom reference (legwear + bottomwear) for full-body occlusion checks
    raw_bot_canvas = Image.new("RGBA", (W, H))
    for t in layer_order:
        if t in ("legwear", "bottomwear") and t in mapped:
            raw_bot_canvas.alpha_composite(Image.fromarray(mapped[t], "RGBA"))
    raw_bot = np.array(raw_bot_canvas)

    body_ref_canvas = Image.fromarray(raw_bot, "RGBA")
    body_ref_canvas.alpha_composite(Image.fromarray(raw_top, "RGBA"))
    body_ref = np.array(body_ref_canvas)

    # 1. Sleeves (handwear-l + handwear-r + objects) with visible-surface priority and body-hallucination trimming
    top_idx = layer_idx_map.get("topwear", 999)
    err_body = detail_and_color_error(body_ref, white, sigma_patch=6.0)
    col_body = color_error_smooth(body_ref, white, sigma_patch=2.0)
    # Use solid body interior (alpha >= 245 eroded by 5x5) so trimming handwear never creates semi-transparent alpha valleys on shared outer outlines
    body_solid_interior = binary_erosion(body_ref[:, :, 3] >= 245, np.ones((5, 5), dtype=bool))
    sleeves = np.zeros((H, W, 4), dtype=np.uint8)
    for t in layer_order:
        if t not in ("handwear-l", "handwear-r", "objects") or t not in mapped:
            continue
        arr = mapped[t].copy()
        if t == "objects":
            # Fill interior holes of translucent objects (e.g. clear beach bag) from registered source
            obj_solid = binary_fill_holes(binary_closing(arr[:, :, 3] > 16, np.ones((5, 5), dtype=bool)))
            obj_holes = obj_solid & (arr[:, :, 3] < 200) & (source[:, :, 3] > 128)
            if obj_holes.any():
                arr[obj_holes] = source[obj_holes]
        if t in ("handwear-l", "handwear-r"):
            err_hw = detail_and_color_error(arr, white, sigma_patch=6.0)
            col_hw = color_error_smooth(arr, white, sigma_patch=2.0)
            # Remove semi-transparent ghost stains over solid bare legs/body where body matches source much better
            ghost_stain = body_solid_interior & (arr[:, :, 3] < 140) & (col_hw > col_body + 25.0)
            arr[ghost_stain, 3] = 0
            # Remove inpainted body hallucinations where body_ref clearly matches visible source and handwear does not
            body_wins_clearly = (
                body_solid_interior
                & (arr[:, :, 3] > 0)
                & (
                    ((err_body + 6.0 < err_hw) & (err_hw > 18.0))
                    | ((col_body + 12.0 < col_hw) & (col_hw > 28.0))
                )
            )
            body_wins_clearly = binary_closing(
                binary_opening(body_wins_clearly, np.ones((5, 5), bool)),
                np.ones((11, 11), bool),
            ) & body_solid_interior
            arr[body_wins_clearly, 3] = 0
            if layer_idx_map[t] < top_idx:
                fg_seed = body_solid_interior & (arr[:, :, 3] > 80) & (
                    ((err_hw + 5.0 < err_body) & (err_body > 16.0))
                    | ((col_hw + 12.0 < col_body) & (col_body > 28.0))
                )
                fg_seed = binary_closing(binary_opening(fg_seed, np.ones((5, 5), bool)), np.ones((15, 15), bool))
                comp, n_c = label(fg_seed)
                keep_fg = np.zeros((H, W), dtype=bool)
                if n_c > 0:
                    cnts = np.bincount(comp.ravel())
                    cnts[0] = 0
                    valid = cnts >= 600
                    valid[0] = False
                    keep_fg = valid[comp]
                keep_fg = binary_dilation(keep_fg, np.ones((9, 9), bool))
                clear_behind = body_solid_interior & (~keep_fg)
                arr[clear_behind, 3] = 0

        # Merge into sleeves: where both existing sleeves and new sub-layer are opaque, keep foreground RGB without dropping alpha!
        both_opaque = (sleeves[:, :, 3] > 40) & (arr[:, :, 3] > 40)
        if both_opaque.any():
            col_prev = color_error_smooth(sleeves, white, sigma_patch=2.0)
            col_curr = color_error_smooth(arr, white, sigma_patch=2.0)
            keep_prev = both_opaque & (col_prev + 6.0 < col_curr) & (col_curr > 18.0)
            keep_prev = binary_closing(binary_opening(keep_prev, np.ones((3, 3), bool)), np.ones((7, 7), bool)) & both_opaque
            if keep_prev.any():
                arr[keep_prev, :3] = sleeves[keep_prev, :3]
        sl_canvas = Image.fromarray(sleeves, "RGBA")
        sl_canvas.alpha_composite(Image.fromarray(arr, "RGBA"))
        sleeves = np.array(sl_canvas)

    # Fill missing foreground object bridges held between both hands (e.g. sleep mask in homewear/luna)
    sl_mask_raw = sleeves[:, :, 3] > 80
    if sl_mask_raw.any():
        closed_sl = binary_fill_holes(binary_closing(sl_mask_raw, np.ones((25, 65), dtype=bool)))
        min_body_col = np.full((H, W), 999.0, dtype=np.float32)
        for b_arr in (raw_top, raw_bot):
            b_err = np.max(np.abs(b_arr[:, :, :3].astype(np.float32) - white[:, :, :3].astype(np.float32)), axis=2)
            min_body_col = np.where(b_arr[:, :, 3] > 80, np.minimum(min_body_col, b_err), min_body_col)
        sl_bridge = closed_sl & (~sl_mask_raw) & (source[:, :, 3] > 200) & (min_body_col > 45.0)
        sl_bridge[:hair_cutoff_y, :] = False
        sl_bridge = binary_closing(binary_opening(sl_bridge, np.ones((3, 3), bool)), np.ones((7, 7), bool))
        if sl_bridge.any():
            sleeves[sl_bridge] = source[sl_bridge]

    fg_occluder = binary_dilation(sleeves[:, :, 3] > 80, np.ones((9, 9), dtype=bool))

    # 2. Bottomwear (legwear + bottomwear)
    if "legwear" in mapped and "bottomwear" in mapped:
        leg = mapped["legwear"].copy()
        bot = mapped["bottomwear"].copy()
        col_leg = color_error_smooth(leg, white, sigma_patch=8.0)
        col_bw = color_error_smooth(bot, white, sigma_patch=8.0)
        ov_lb = (leg[:, :, 3] > 180) & (bot[:, :, 3] > 32)
        unocc_ov = ov_lb & (~fg_occluder)
        leg_wins = unocc_ov & (col_leg + 25.0 < col_bw) & (col_bw > 45.0)
        leg_wins = binary_fill_holes(binary_closing(binary_opening(leg_wins, np.ones((9, 9), bool)), np.ones((19, 19), bool))) & unocc_ov
        if (ov_lb & fg_occluder).any() and unocc_ov.any():
            _, nearest_idx = distance_transform_edt(~unocc_ov, return_indices=True)
            occ_mask = ov_lb & fg_occluder
            leg_wins[occ_mask] = leg_wins[nearest_idx[0][occ_mask], nearest_idx[1][occ_mask]]
        bot[leg_wins, 3] = 0
        bottom_canvas = Image.fromarray(leg, "RGBA")
        bottom_canvas.alpha_composite(Image.fromarray(bot, "RGBA"))
        bottom = np.array(bottom_canvas)
    elif "legwear" in mapped:
        bottom = mapped["legwear"].copy()
        bot = np.zeros_like(bottom)
    else:
        bottom = mapped["bottomwear"].copy()
        bot = bottom.copy()

    # 3. Shoes (footwear or lower ankle/slipper split from bottomwear, plus recovery of white slippers omitted by See-through)
    if "footwear" in mapped:
        shoes = mapped["footwear"].copy()
        col_shoes = color_error_smooth(shoes, white, sigma_patch=4.0)
        col_bot_s = color_error_smooth(bottom, white, sigma_patch=4.0)
        ov_sb = (shoes[:, :, 3] > 180) & (bottom[:, :, 3] > 16)
        shoes_wins = ov_sb & (col_shoes + 15.0 < col_bot_s) & (col_bot_s > 35.0)
        shoes_wins = binary_fill_holes(binary_closing(binary_opening(shoes_wins, np.ones((5, 5), bool)), np.ones((15, 15), bool))) & ov_sb
        bottom[shoes_wins, 3] = 0
    else:
        bot_ys = np.nonzero(bottom[:, :, 3] > 80)[0]
        shoes_split_y = min(baseline_shoes["y"], int(bot_ys.max()) - 140) if len(bot_ys) else baseline_shoes["y"]
        shoes = bottom.copy()
        shoes[:shoes_split_y, :, 3] = 0
        bottom[shoes_split_y + 22 :, :, 3] = 0

    # Recover lower-ankle/foot pixels present in registered source but missed by See-through v3 (e.g. homewear/naru white slippers)
    lower_foot_y = max(baseline_shoes["y"] - 40, int(H * 0.82))
    existing_lower = (shoes[:, :, 3] > 80) | (bottom[:, :, 3] > 80)
    missing_shoes = (np.arange(H)[:, None] >= lower_foot_y) & (source[:, :, 3] > 80) & (~existing_lower)
    if np.count_nonzero(missing_shoes) >= 200:
        missing_shoes_dil = binary_dilation(missing_shoes, np.ones((5, 5), dtype=bool)) & (source[:, :, 3] > 0) & (np.arange(H)[:, None] >= lower_foot_y)
        shoes[missing_shoes_dil] = source[missing_shoes_dil]

    # 4. Neck
    neck = mapped["neck"].copy() if "neck" in mapped else np.zeros((H, W, 4), dtype=np.uint8)

    # 5. Topwear vs Bottomwear bridge resolution
    top = raw_top.copy()
    err_top = detail_and_color_error(top, white, sigma_patch=10.0)
    err_bot = detail_and_color_error(bottom, white, sigma_patch=10.0)
    waist_y = max(hip_y, boob_y + 170)
    overlap_tb = (top[:, :, 3] > 32) & (bottom[:, :, 3] > 180) & (np.arange(H)[:, None] >= waist_y)
    bot_layer_above_top = layer_idx_map.get("bottomwear", -1) > layer_idx_map.get("topwear", -1)
    if outfit == "homewear" and bot_layer_above_top:
        bot_wins = overlap_tb & (err_bot <= err_top + 6.0)
    else:
        bot_wins = overlap_tb & (err_bot + 3.0 < err_top) & (err_top > 11.0)
    bot_wins = binary_fill_holes(binary_closing(binary_opening(bot_wins, np.ones((9, 9), bool)), np.ones((25, 25), bool))) & overlap_tb
    for y in range(waist_y, H):
        xs = np.nonzero(bot_wins[y])[0]
        if len(xs) >= 20:
            span = slice(int(xs.min()), int(xs.max()) + 1)
            bot_wins[y, span] |= overlap_tb[y, span]
    top[bot_wins, 3] = 0

    # Trim bare legwear bleed under sheer robes where topwear genuinely wins (leaving 5px underlap around bot_wins)
    top_wins_over_leg = overlap_tb & (~binary_dilation(bot_wins, np.ones((11, 11), dtype=bool))) & (bot[:, :, 3] <= 32)
    bottom[top_wins_over_leg, 3] = 0

    take_bot_src = bot_wins & (source[:, :, 3] > 128) & (err_bot <= 35.0) & (~fg_occluder)
    bottom[take_bot_src] = source[take_bot_src]

    # Ensure 4px opaque underlap of bottomwear beneath opaque topwear along the bot_wins boundary (prevents 0-overlap butt-joint seams)
    if bot_wins.any():
        underlap_tb = (
            binary_dilation(bot_wins, np.ones((9, 9), dtype=bool))
            & (~bot_wins)
            & (top[:, :, 3] >= 240)
            & (source[:, :, 3] > 200)
        )
        bottom[underlap_tb] = source[underlap_tb]

    # Resolve topwear vs visible neck skin: remove ONLY hidden dark back-of-neck collars behind bare neck skin (e.g. ho/luna)
    col_neck = color_error_smooth(neck, white, sigma_patch=3.0)
    col_top = color_error_smooth(top, white, sigma_patch=3.0)
    ov_tn = (top[:, :, 3] > 16) & (neck[:, :, 3] > 180)
    neck_lum = np.mean(neck[:, :, :3].astype(np.float32), axis=2)
    top_lum = np.mean(top[:, :, :3].astype(np.float32), axis=2)
    white_lum = np.mean(white[:, :, :3].astype(np.float32), axis=2)
    back_collar = ov_tn & (col_neck + 30.0 < col_top) & (col_top > 60.0) & (neck_lum - top_lum > 45.0)
    if back_collar.any():
        bc_ys = np.nonzero(back_collar)[0]
        y_min_bc, y_max_bc = int(bc_ys.min()), int(bc_ys.max()) + 6
        band_bc = ov_tn & (np.arange(H)[:, None] >= y_min_bc) & (np.arange(H)[:, None] <= y_max_bc) & (neck_lum - top_lum > 35.0)
        vis_dark_collar = (white_lum < neck_lum - 30.0) & (col_top + 15.0 < col_neck)
        back_collar = binary_dilation(binary_closing(back_collar | band_bc, np.ones((7, 7), bool)), np.ones((7, 7), bool)) & ov_tn & (~vis_dark_collar)
        top[back_collar, 3] = 0

    pieces = {
        "shoes": shoes,
        "bottomwear": bottom,
        "neck": neck,
        "topwear": top,
        "sleeves": sleeves,
    }

    # Erode 3px outer shoulder fringe above collar (away from the neck seam so neck-topwear overlap is never clipped)
    upper_to_row = baseline_neck["y"] + int(baseline_neck["h"] * 0.72)
    union = np.maximum.reduce([a[:, :, 3] for a in pieces.values()])
    outer_distance = distance_transform_edt(union > 8)
    dist_from_neck = distance_transform_edt(~(neck[:, :, 3] > 80))
    for name in ["topwear", "sleeves"]:
        a = pieces[name][:, :, 3]
        a[:upper_to_row][(outer_distance[:upper_to_row] <= 3) & (dist_from_neck[:upper_to_row] > 12)] = 0

    # Project crisp 4x upscaled visible source pixels onto each visible foreground layer AND across all internal part seams
    nw_mask = (mapped["neckwear"][:, :, 3] > 80) if "neckwear" in mapped else np.zeros((H, W), dtype=bool)
    fg_head_only = np.zeros((H, W), dtype=bool)
    for htag in ["front hair", "face", "ears-l", "ears-r", "earwear", "eyewear"]:
        if htag in mapped:
            fg_head_only |= (mapped[htag][:, :, 3] > 32)

    union_post = np.maximum.reduce([a[:, :, 3] for a in pieces.values()])
    # Only erode the outer silhouette of the clothing union — NEVER erode internal boundaries between clothing parts!
    outer_sil_core = binary_erosion((union_post >= 180) & (source[:, :, 3] > 128), np.ones((3, 3), dtype=bool))

    vis_owner = np.full((H, W), -1, dtype=np.int16)
    for idx, name in enumerate(ORDER):
        vis_owner[pieces[name][:, :, 3] > 80] = idx

    below_hair_band = np.arange(H)[:, None] >= low_hair_limit_y
    projection = {}
    for idx, name in enumerate(ORDER):
        arr = pieces[name]
        drift = np.max(np.abs(arr[:, :, :3].astype(np.int16) - white[:, :, :3].astype(np.int16)), axis=2)
        allow_proj = (~hair_st) | ((nw_mask & (~fg_head_only)) if name == "topwear" else False)

        # Alpha of parts below and above this part
        below_alpha = np.zeros((H, W), dtype=np.uint8)
        for b_idx in range(idx):
            below_alpha = np.maximum(below_alpha, pieces[ORDER[b_idx]][:, :, 3])
        above_alpha = np.zeros((H, W), dtype=np.uint8)
        for a_idx in range(idx + 1, len(ORDER)):
            above_alpha = np.maximum(above_alpha, pieces[ORDER[a_idx]][:, :, 3])

        # 1) Topmost visible region of this part: include full alpha>0 over internal seams (where below_alpha > 180)
        is_top_interior = (vis_owner == idx) & (arr[:, :, 3] >= 180) & outer_sil_core & allow_proj
        is_internal_upper_edge = (above_alpha <= 80) & (arr[:, :, 3] > 0) & (below_alpha > 160) & outer_sil_core & allow_proj
        # 2) Underlap region just beneath an upper part's boundary edge (outer 4px always projected; up to 16px when continuous)
        dist_into_above = distance_transform_edt(above_alpha > 80)
        is_internal_lower_edge4 = (arr[:, :, 3] > 0) & (above_alpha > 0) & (dist_into_above <= 4) & outer_sil_core & allow_proj
        is_internal_lower_seam = (
            (arr[:, :, 3] > 0)
            & (above_alpha > 0)
            & (dist_into_above <= 16)
            & outer_sil_core
            & allow_proj
            & ((dist_into_above <= 4) | (above_alpha < 245) | (drift <= 65))
        )

        core = is_top_interior | is_internal_upper_edge | is_internal_lower_seam
        drift_limit = 115 if name != "neck" else 75
        accepted = (
            (binary_closing(core & ((drift <= drift_limit) | (is_top_interior & below_hair_band)), np.ones((5, 5), bool)) & core)
            | is_internal_upper_edge
            | is_internal_lower_edge4
            | ((is_internal_lower_seam) & (above_alpha < 245))
        )
        weight = gaussian_filter(accepted.astype(np.float32), sigma=0.8) * (arr[:, :, 3] > 0)
        # Snap weight to 1.0 right on internal seam edges so alpha-compositing upper over lower is mathematically exact
        exact_seam = (is_internal_upper_edge | is_internal_lower_edge4 | (is_internal_lower_seam & (above_alpha < 245))) & accepted
        weight[exact_seam] = 1.0
        arr[:, :, :3] = np.clip(
            weight[:, :, None] * source[:, :, :3] + (1.0 - weight[:, :, None]) * arr[:, :, :3],
            0,
            255,
        ).astype(np.uint8)

        projection[name] = {
            "core": int(core.sum()),
            "taken": int(accepted.sum()),
            "refused": int((core & (~accepted)).sum()),
        }

    # Clean stray islands, seal narrow margin-3 contour bays, extend neck 45px under topwear/sleeves, and harmonize skin tone
    four_conn = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=bool)
    yy_d3, xx_d3 = np.ogrid[-3:4, -3:4]
    disc3 = (xx_d3 * xx_d3 + yy_d3 * yy_d3) <= 9

    def clean_mesh_islands():
        for name in ORDER:
            arr = pieces[name]
            arr[arr[:, :, 3] <= 8, 3] = 0
            comp, n_comp = label(arr[:, :, 3] > 8, four_conn)
            if n_comp > 1:
                counts = np.bincount(comp.ravel())
                counts[0] = 0
                min_sz = 900 if name in ["neck", "topwear", "sleeves"] else (60 if name == "shoes" else 250)
                small = (counts < min_sz) & (counts > 0)
                if name == "sleeves":
                    # Also remove isolated small (<5000px) shoulder/collarbone remnants sitting entirely above boob_y+40
                    for cid in range(1, n_comp + 1):
                        if 0 < counts[cid] < 5000:
                            c_ys = np.nonzero(comp == cid)[0]
                            if len(c_ys) and int(c_ys.max()) < int(boob_y) + 40:
                                small[cid] = True
                if small.any():
                    arr[small[comp], 3] = 0
            if name in ("neck", "topwear", "sleeves"):
                m = arr[:, :, 3] > 8
                if m.any():
                    pad_m = np.pad(m, 1, constant_values=False)
                    bg_comp, _ = label(~pad_m, np.ones((3, 3), dtype=bool))
                    ext_bg = (bg_comp == bg_comp[0, 0])[1:-1, 1:-1]
                    dil = binary_dilation(m, disc3)
                    sealed_holes = binary_fill_holes(dil) & (~dil) & ext_bg
                    if sealed_holes.any():
                        bay_fill = binary_dilation(sealed_holes, disc3) & ext_bg
                        _, near_m = distance_transform_edt(~m, return_indices=True)
                        arr[bay_fill, :3] = arr[near_m[0][bay_fill], near_m[1][bay_fill], :3]
                        arr[bay_fill, 3] = np.maximum(arr[bay_fill, 3], 9)

    clean_mesh_islands()
    upper_opaque = (pieces["topwear"][:, :, 3] > 180) | (pieces["sleeves"][:, :, 3] > 180)
    uncov_neck = pieces["neck"][:, :, 3] > 200
    if uncov_neck.any():
        interior_neck = binary_erosion(uncov_neck, np.ones((7, 7), dtype=bool))
        sample_neck = interior_neck if interior_neck.any() else uncov_neck
        dist_neck, _ = distance_transform_edt(~uncov_neck, return_indices=True)
        _, near_neck = distance_transform_edt(~sample_neck, return_indices=True)
        silhouette = binary_fill_holes(binary_closing(upper_opaque | uncov_neck, np.ones((25, 25), dtype=bool)))
        outer_sil_dist = distance_transform_edt(silhouette)
        near_ul = (dist_neck <= 45) & (outer_sil_dist >= 6) & upper_opaque & (pieces["neck"][:, :, 3] <= 200)
        if near_ul.any():
            pieces["neck"][near_ul, :3] = pieces["neck"][near_neck[0][near_ul], near_neck[1][near_ul], :3]
            pieces["neck"][near_ul, 3] = 255
        semi_neck = (pieces["neck"][:, :, 3] > 8) & (pieces["neck"][:, :, 3] < 255) & upper_opaque & (outer_sil_dist >= 6)
        if semi_neck.any():
            pieces["neck"][semi_neck, :3] = pieces["neck"][near_neck[0][semi_neck], near_neck[1][semi_neck], :3]
            pieces["neck"][semi_neck, 3] = 255

    # Harmonize low-frequency skin tone and feather the upper skin edge of topwear over solid neck
    neck_solid = binary_erosion(pieces["neck"][:, :, 3] == 255, np.ones((5, 5), dtype=bool))
    above_top_on_neck = neck_solid & (pieces["topwear"][:, :, 3] <= 16)
    if above_top_on_neck.any():
        dist_into_top = distance_transform_edt(~above_top_on_neck)
        dist_into_neck = distance_transform_edt(above_top_on_neck)
        diff_tn = np.max(np.abs(pieces["topwear"][:, :, :3].astype(np.int16) - pieces["neck"][:, :, :3].astype(np.int16)), axis=2)
        top_f = pieces["topwear"][:, :, :3].astype(np.float32)
        top_hp = np.max(np.abs(top_f - gaussian_filter(top_f, sigma=(2.5, 2.5, 0.0))), axis=2)
        clean_top_skin = (
            neck_solid
            & (pieces["topwear"][:, :, 3] > 220)
            & (dist_into_top >= 10)
            & (dist_into_top <= 28)
            & (diff_tn <= 65)
            & (top_hp <= 16.0)
            & (~nw_mask)
        )
        if clean_top_skin.any():
            _, near_top_skin = distance_transform_edt(~clean_top_skin, return_indices=True)
            dist_to_clean_skin = distance_transform_edt(~clean_top_skin)
            top_skin_rim = (
                neck_solid
                & (pieces["topwear"][:, :, 3] > 0)
                & (dist_into_top < 10)
                & (diff_tn <= 75)
                & (top_hp <= 18.0)
                & (dist_to_clean_skin <= 16)
                & (~nw_mask)
            )
            if top_skin_rim.any():
                pieces["topwear"][top_skin_rim, :3] = pieces["topwear"][
                    near_top_skin[0][top_skin_rim], near_top_skin[1][top_skin_rim], :3
                ]
            target_top_rgb = pieces["topwear"][near_top_skin[0], near_top_skin[1], :3].astype(np.float32)
            delta_rgb = target_top_rgb - pieces["neck"][:, :, :3].astype(np.float32)
            delta_smooth = gaussian_filter(delta_rgb, sigma=(10.0, 10.0, 0.0))
            horiz_reach = np.clip(1.0 - (dist_to_clean_skin - 12.0) / 45.0, 0.0, 1.0)
            up_fade = np.clip(1.0 - dist_into_neck / 45.0, 0.0, 1.0)
            w_harm = (up_fade * horiz_reach) * (pieces["neck"][:, :, 3] > 0)
            pieces["neck"][:, :, :3] = np.clip(
                pieces["neck"][:, :, :3].astype(np.float32) + w_harm[:, :, None] * delta_smooth,
                0,
                255,
            ).astype(np.uint8)
            skin_feather_zone = (
                neck_solid
                & (pieces["topwear"][:, :, 3] > 0)
                & (dist_into_top <= 4)
                & (dist_to_clean_skin <= 16)
                & (~nw_mask)
            )
            ramp = np.clip((dist_into_top + 1.0) / 5.0, 0.25, 1.0)
            pieces["topwear"][skin_feather_zone, 3] = (
                pieces["topwear"][skin_feather_zone, 3].astype(np.float32) * ramp[skin_feather_zone]
            ).astype(np.uint8)

    clean_mesh_islands()

    edge_treatment = {
        "upperGeneratedUnionAlphaErosionPx": 3,
        "upperToRow": int(upper_to_row),
        "method": "See-through v3 layer depth + seamless internal boundary projection + low-frequency neck-topwear skin harmonization; zero manual polygons",
    }
    return pieces, common_parts, white, projection, edge_treatment


def run_character(family: pathlib.Path, outfit: str, char: str, candidate_name: str = "prepared", force: bool = False):
    home = family / "outfits" / outfit / char
    out = home / candidate_name
    if out.exists():
        if force:
            shutil.rmtree(out)
        else:
            raise RuntimeError(f"{outfit.upper()}_STATIC_FRESH_OUTPUT_REQUIRED: {out}")
    out.mkdir(parents=True)
    (out / "parts").mkdir()
    (home / "docs").mkdir(exist_ok=True)

    pieces, common, white, projection, edge_treatment = build_auto_parts(family, outfit, char)
    part_records = []
    for name in ORDER:
        array = pieces[name]
        ys, xs = np.nonzero(array[:, :, 3] > 0)
        if not len(xs):
            raise RuntimeError(f"{outfit.upper()}_STATIC_NONEMPTY_PART_REQUIRED {char}:{name}")
        box = (int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1))
        im = Image.fromarray(array, "RGBA").crop(box)
        im.save(out / "parts" / (name + ".png"))
        part_records.append({
            "name": name,
            "x": box[0],
            "y": box[1],
            "w": im.width,
            "h": im.height,
            "opaque_px": int(np.count_nonzero(np.array(im)[:, :, 3] > 8)),
            "source": f"full:seethrough-v3:{name}",
        })

    def accepted(part_name: str):
        record = common[part_name]
        return Image.open(family / char / "out/parts" / (part_name + ".png")).convert("RGBA"), (record["x"], record["y"])

    canvas = Image.new("RGBA", (W, H))
    im_hb, at_hb = accepted("hair_back")
    canvas.alpha_composite(im_hb, at_hb)
    for name in ORDER:
        canvas.alpha_composite(Image.fromarray(pieces[name], "RGBA"))
    for name in common:
        if name == "hair_back":
            continue
        im_c, at_c = accepted(name)
        canvas.alpha_composite(im_c, at_c)
    flat = Image.new("RGBA", (W, H), "white")
    flat.alpha_composite(canvas)
    flat.convert("RGB").save(out / "assembled-white.png")

    contact = Image.new("RGB", (840, 1220), "#dddddd")
    draw = ImageDraw.Draw(contact)
    for i, (im_panel, label_text) in enumerate([
        (Image.fromarray(white, "RGBA"), f"Registered {outfit} source (new head)"),
        (flat, "Flat prototype (accepted face/hair)"),
    ]):
        contact.paste(im_panel.convert("RGB").resize((400, 1142), Image.Resampling.LANCZOS), (10 + i * 420, 35))
        draw.text((10 + i * 420, 12), label_text, fill="black")
    draw.text(
        (10, 1190),
        "Automatic See-through v3 5-part composition: zero manual polygons. Visible source projected; hidden model art retained.",
        fill="black",
    )
    contact_path = home / "docs" / (candidate_name + "-contact.png")
    contact.save(contact_path)

    metadata = {
        "spec": f"family-{outfit}-static-prototype/2",
        "character": char,
        "status": "STATIC_REVIEW_ONLY",
        "parts": part_records,
        "projection": projection,
        "projectionPolicy": {
            "source": "See-through v3 semantic layers + registered 4x upscaled visible source projection",
            "coreAlpha": 200,
            "kernel": 3,
            "driftLimit": 75,
            "sigma": 1.0,
        },
        "geometry": {
            "inputSquare": [2284, 2284],
            "padLeft": 742,
            "runSquare": [1024, 1024],
            "output": [800, 2284],
            "resample": "Pillow BICUBIC",
        },
        "edgeTreatment": edge_treatment,
        "commonHead": "Existing accepted parts copied in the same canvas; generated head/hair are never adopted.",
    }
    (out / "prototype.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return {
        "character": char,
        "status": "STATIC_REVIEW_READY",
        "contact": str(contact_path),
        "parts": len(part_records),
    }
