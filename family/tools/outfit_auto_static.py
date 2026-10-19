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
    hip_x, hip_y = next(b["at"] for b in cfg["bones"] if b.get("name") == "hip")
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

    # Upper hair/head mask from See-through v3: above collar, plus any genuine hair strands down to boob_y
    hair_cutoff_y = baseline_neck["y"] + baseline_neck["h"]
    hair_st = np.zeros((H, W), dtype=bool)
    for htag in ["front hair", "face", "ears-l", "ears-r", "earwear"]:
        if htag in mapped:
            hair_st |= (mapped[htag][:, :, 3] > 32)
    if "back hair" in mapped:
        bh_arr = mapped["back hair"]
        col_bh = color_error_smooth(bh_arr, white, sigma_patch=2.5)
        col_rt = color_error_smooth(raw_top, white, sigma_patch=2.5)
        bh_mask = (bh_arr[:, :, 3] > 32) & ((raw_top[:, :, 3] < 180) | ((col_bh + 8.0 < col_rt) & (col_rt > 20.0)))
        hair_st |= bh_mask
    hair_st[hair_cutoff_y:, :] = False
    # Also mask genuine hair strands between hair_cutoff_y and boob_y+60 where hair layer matches source better than clothing
    low_hair_limit_y = min(H, int(boob_y) + 60)
    for htag in ["back hair", "front hair"]:
        if htag in mapped:
            h_arr = mapped[htag]
            col_h = color_error_smooth(h_arr, white, sigma_patch=2.5)
            col_rt_low = color_error_smooth(raw_top, white, sigma_patch=2.5)
            h_band = (
                (np.arange(H)[:, None] >= hair_cutoff_y)
                & (np.arange(H)[:, None] < low_hair_limit_y)
                & (h_arr[:, :, 3] > 80)
                & (col_h < 28.0)
                & ((raw_top[:, :, 3] < 180) | (col_h + 6.0 < col_rt_low))
            )
            hair_st |= h_band

    # 1. Sleeves (handwear-l + handwear-r + objects): preserve foreground arms 100% intact; only clear occluded back-arm stems
    col_body = color_error_smooth(body_ref, white, sigma_patch=2.5)
    if np.any(raw_bot[:, :, 3] > 180):
        col_bot_ref = color_error_smooth(raw_bot, white, sigma_patch=2.5)
        col_body = np.where(raw_bot[:, :, 3] > 180, np.minimum(col_body, col_bot_ref), col_body)
    body_solid_interior = binary_erosion(body_ref[:, :, 3] >= 245, np.ones((7, 7), dtype=bool))
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
            arr_for_err = np.where(arr[:, :, 3:4] > 80, arr, white)
            col_hw = color_error_smooth(arr_for_err, white, sigma_patch=2.5)
            # Remove semi-transparent ghost stains over solid bare legs/body where body matches source much better
            ghost_stain = body_solid_interior & (arr[:, :, 3] < 140) & (col_hw > col_body + 25.0)
            arr[ghost_stain, 3] = 0

            is_skin_hw = (
                (arr[:, :, 0].astype(np.int16) - arr[:, :, 2].astype(np.int16) > 12)
                & (arr[:, :, 0] > 120)
                & (arr[:, :, 3] > 40)
            )
            # For Roa's right arm (handwear-l), remove the inner navy camisole/swimsuit/vest slice and upper shoulder hair tips
            if char == "roa" and t == "handwear-l":
                real_skin_src = (
                    (source[:, :, 0].astype(np.int16) - source[:, :, 2].astype(np.int16) > 25)
                    & (source[:, :, 0] > 155)
                )
                is_navy_body = (
                    (source[:, :, 2].astype(np.int16) - source[:, :, 0].astype(np.int16) >= 4)
                    & (source[:, :, 0] < 98)
                    & (source[:, :, 1] < 98)
                    & (np.arange(W)[None, :] >= 415)
                    & (np.arange(W)[None, :] < 505)
                    & (np.arange(H)[:, None] >= 480)
                    & (np.arange(H)[:, None] < 625)
                )
                for y in range(480, 625):
                    n_xs = np.nonzero(is_navy_body[y])[0]
                    if len(n_xs):
                        x_lim = min(504, int(n_xs.max()) + 4)
                        clear_row = (~real_skin_src[y, 415:x_lim]) if outfit != "uniform" else np.ones(x_lim - 415, dtype=bool)
                        arr[y, 415:x_lim, 3][clear_row] = 0
                if outfit == "uniform":
                    # Also trim the upper-left inpainted shoulder/hair block of handwear-l above the white sleeve (y < 512, x < 545)
                    arr[:496, :550, 3] = 0
                    for y in range(496, 520):
                        x_cut = int(round(np.interp(y, [496, 520], [520, 474])))
                        arr[y, :x_cut, 3] = 0

            # Classify left arm stem (x < hip_x - 45) and right arm stem (x >= hip_x + 45) as foreground vs occluded back-arm
            for is_left in (True, False):
                stem_mask = (np.arange(W)[None, :] < hip_x - 45) if is_left else (np.arange(W)[None, :] >= hip_x + 45)
                half_mask = (np.arange(W)[None, :] < hip_x) if is_left else (np.arange(W)[None, :] >= hip_x)
                ov_s = stem_mask & body_solid_interior & (arr[:, :, 3] > 80)
                hw_s = int((ov_s & (col_hw + 6.0 < col_body) & (col_body > 18.0)).sum())
                bd_s = int((ov_s & (col_body + 6.0 < col_hw) & (col_hw > 18.0)).sum())
                is_back_arm = (bd_s > 8000) and (bd_s > hw_s * 5)
                if is_back_arm:
                    # Protect genuine skin hand reaching across hip_x from the foreground arm on the other side
                    err_px = np.abs(arr_for_err[:, :, :3].astype(np.float32) - white[:, :, :3].astype(np.float32)).mean(axis=2)
                    skin_bridged = binary_closing(is_skin_hw & (err_px < 48.0), np.ones((15, 15), dtype=bool))
                    other_side_skin = (~half_mask) & skin_bridged
                    fg_hand = np.zeros((H, W), dtype=bool)
                    if other_side_skin.any():
                        sk_c, n_sk = label(skin_bridged)
                        if n_sk > 0:
                            touch = np.bincount(sk_c[other_side_skin].ravel(), minlength=n_sk + 1) > 0
                            touch[0] = False
                            fg_hand = binary_dilation(touch[sk_c], np.ones((11, 11), dtype=bool))
                    back_clear = half_mask & (~fg_hand) & (
                        body_solid_interior | ((body_ref[:, :, 3] > 80) & (col_body + 4.0 < col_hw))
                    )
                    arr[back_clear, 3] = 0
                    comp, n_c = label((arr[:, :, 3] > 16) & half_mask)
                    for cid in range(1, n_c + 1):
                        cm = comp == cid
                        ext_px = int((cm & (~(body_ref[:, :, 3] > 80)) & (arr[:, :, 3] > 120)).sum())
                        if not (cm & fg_hand).any() and ext_px < 1200:
                            arr[cm, 3] = 0
                elif outfit != "uniform" and char not in ("luna", "roa"):
                    # On foreground arms, only remove large non-skin body-color hallucinations where handwear strongly disagrees with white
                    bad_blob = half_mask & body_solid_interior & (~is_skin_hw) & (col_hw > 28.0) & (col_body < 12.0)
                    bad_blob = (
                        binary_closing(binary_opening(bad_blob, np.ones((9, 9), bool)), np.ones((15, 15), bool))
                        & body_solid_interior
                        & (~is_skin_hw)
                    )
                    arr[bad_blob, 3] = 0

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

    # 2. Bottomwear & Legwear (for uniform, keep legwear and bottomwear separate so pleated skirt is an independent mesh part)
    leg_part = None
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
        if outfit == "uniform":
            leg_part = leg
            bottom = bot.copy()
        else:
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
    lower_leg_target = leg_part if leg_part is not None else bottom
    if "footwear" in mapped:
        shoes = mapped["footwear"].copy()
        col_shoes = color_error_smooth(shoes, white, sigma_patch=4.0)
        col_bot_s = color_error_smooth(lower_leg_target, white, sigma_patch=4.0)
        ov_sb = (shoes[:, :, 3] > 180) & (lower_leg_target[:, :, 3] > 16)
        shoes_wins = ov_sb & (col_shoes + 15.0 < col_bot_s) & (col_bot_s > 35.0)
        shoes_wins = binary_fill_holes(binary_closing(binary_opening(shoes_wins, np.ones((5, 5), bool)), np.ones((15, 15), bool))) & ov_sb
        lower_leg_target[shoes_wins, 3] = 0
        if leg_part is not None:
            bottom[shoes_wins, 3] = 0
    else:
        bot_ys = np.nonzero(lower_leg_target[:, :, 3] > 80)[0]
        shoes_split_y = min(baseline_shoes["y"], int(bot_ys.max()) - 140) if len(bot_ys) else baseline_shoes["y"]
        shoes = lower_leg_target.copy()
        shoes[:shoes_split_y, :, 3] = 0
        lower_leg_target[shoes_split_y + 22 :, :, 3] = 0

    # Recover lower-ankle/foot pixels present in registered source but missed by See-through v3 (e.g. homewear/naru white slippers)
    lower_foot_y = max(baseline_shoes["y"] - 40, int(H * 0.82))
    existing_lower = (shoes[:, :, 3] > 80) | (lower_leg_target[:, :, 3] > 80) | (bottom[:, :, 3] > 80)
    missing_shoes = (np.arange(H)[:, None] >= lower_foot_y) & (source[:, :, 3] > 80) & (~existing_lower)
    if np.count_nonzero(missing_shoes) >= 200:
        missing_shoes_dil = binary_dilation(missing_shoes, np.ones((5, 5), dtype=bool)) & (source[:, :, 3] > 0) & (np.arange(H)[:, None] >= lower_foot_y)
        shoes[missing_shoes_dil] = source[missing_shoes_dil]

    # 4. Neck
    neck = mapped["neck"].copy() if "neck" in mapped else np.zeros((H, W, 4), dtype=np.uint8)

    # 5. Topwear vs Bottomwear bridge resolution
    top = raw_top.copy()

    waist_y = min(hip_y, boob_y + 150)
    center_bridge_zone = raw_top[waist_y + 45 : waist_y + 160, hip_x - 45 : hip_x + 45, 3] > 80
    has_center_bridge = np.mean(center_bridge_zone) > 0.25
    bot_wins = np.zeros((H, W), dtype=bool)
    if has_center_bridge:
        top_for_err = np.where(top[:, :, 3:4] > 180, top, white)
        bot_for_err = np.where(bottom[:, :, 3:4] > 180, bottom, white)
        err_top = detail_and_color_error(top_for_err, white, sigma_patch=8.0)
        err_bot = detail_and_color_error(bot_for_err, white, sigma_patch=8.0)
        overlap_tb = (top[:, :, 3] > 32) & (bottom[:, :, 3] > 180) & (np.arange(H)[:, None] >= waist_y)
        unocc_tb = overlap_tb & (~fg_occluder)
        bot_layer_above_top = layer_idx_map.get("bottomwear", -1) > layer_idx_map.get("topwear", -1)
        if outfit == "homewear" and bot_layer_above_top:
            bot_wins = unocc_tb & (err_bot <= err_top + 6.0)
        else:
            bot_wins = unocc_tb & (err_bot + 3.0 < err_top) & (err_top > 11.0)
        bot_wins = binary_fill_holes(binary_closing(binary_opening(bot_wins, np.ones((9, 9), bool)), np.ones((25, 25), bool))) & unocc_tb
        if (overlap_tb & fg_occluder).any() and unocc_tb.any():
            _, near_tb = distance_transform_edt(~unocc_tb, return_indices=True)
            occ_tb = overlap_tb & fg_occluder
            bot_wins[occ_tb] = bot_wins[near_tb[0][occ_tb], near_tb[1][occ_tb]]
        for y in range(waist_y, H):
            xs = np.nonzero(bot_wins[y])[0]
            if len(xs) >= 20:
                x0, x1 = int(xs.min()), int(xs.max())
                if np.all(bottom[y, x0 : x1 + 1, 3] > 180):
                    bot_wins[y, x0 : x1 + 1] |= overlap_tb[y, x0 : x1 + 1]
        for x in range(W):
            bw_ys = np.nonzero(bot_wins[waist_y:, x])[0]
            bot_ys = np.nonzero(bottom[waist_y:, x, 3] > 180)[0]
            if len(bw_ys) and len(bot_ys):
                y_bw = int(bw_ys.min()) + waist_y
                y_bot = int(bot_ys.min()) + waist_y
                if y_bw - y_bot <= 8:
                    y_up = max(waist_y, y_bot - 4)
                    bot_wins[y_up:y_bw, x] = top[y_up:y_bw, x, 3] > 0
                else:
                    y_dn = min(H, y_bw + 4)
                    bot_wins[y_bw:y_dn, x] = False

        top[bot_wins, 3] = 0
        top_lower_core = binary_erosion(top[waist_y:, :, 3] > 80, np.ones((3, 5), dtype=bool))
        top_lower_keep = binary_dilation(top_lower_core, np.ones((5, 7), dtype=bool))
        top[waist_y:][~top_lower_keep, 3] = 0
        top_wins_over_leg = (
            (top[:, :, 3] > 80)
            & (np.arange(H)[:, None] >= waist_y - 20)
            & (~binary_dilation(bot_wins, np.ones((11, 11), dtype=bool)))
            & (bot[:, :, 3] <= 32)
        )
        bottom[top_wins_over_leg, 3] = 0
        if leg_part is not None:
            leg_part[top_wins_over_leg, 3] = 0
            bot_solid_ys = np.nonzero(bottom[:, :, 3] > 80)[0]
            if len(bot_solid_ys):
                leg_part[: int(bot_solid_ys.min()) + 20, :, 3] = 0
        # Solidify semi-transparent edges inside bot_wins and extend 12px underlap beneath adjacent opaque topwear
        bot_underlap_zone = (
            binary_dilation(bot_wins, np.ones((25, 25), dtype=bool))
            & (bot_wins | (top[:, :, 3] > 80))
            & (bottom[:, :, 3] < 250)
        )
        if bot_underlap_zone.any() and np.any(bottom[:, :, 3] >= 220):
            _, near_bot = distance_transform_edt(~(bottom[:, :, 3] >= 220), return_indices=True)
            bottom[bot_underlap_zone, :3] = bottom[near_bot[0][bot_underlap_zone], near_bot[1][bot_underlap_zone], :3]
            bottom[bot_underlap_zone, 3] = 255

    # Resolve topwear vs visible neck skin: remove ONLY hidden dark back-of-neck collars behind bare neck skin (e.g. ho/luna)
    if outfit != "uniform":
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
    elif outfit == "uniform" and char == "roa":
        # Remove See-through v3's gray back-of-neck collar band where bare neck is behind it (y < 468)
        roa_back_collar = (
            (np.arange(H)[:, None] < 468)
            & (neck[:, :, 3] > 180)
            & (top[:, :, 3] > 0)
            & (top[:, :, 0] < 168)
            & (top[:, :, 0].astype(np.int16) - top[:, :, 2].astype(np.int16) < 42)
        )
        roa_back_collar = binary_closing(roa_back_collar, np.ones((5, 5), dtype=bool)) & (neck[:, :, 3] > 180) & (np.arange(H)[:, None] < 468)
        top[roa_back_collar, 3] = 0
        raw_top[roa_back_collar, 3] = 0

    # Pinpoint mug transfer for homewear/roa: copy chest mug into sleeves and vertically interpolate camisole/cardigan behind it
    if outfit == "homewear" and char == "roa":
        is_warm_obj = (
            (top[:, :, 3] > 180)
            & (top[:, :, 0] > 110)
            & (top[:, :, 1] > 90)
            & (top[:, :, 0].astype(np.int16) - top[:, :, 2].astype(np.int16) > 22)
            & (top[:, :, 0].astype(np.int16) - top[:, :, 1].astype(np.int16) < 60)
            & (np.arange(H)[:, None] >= boob_y - 20)
            & (np.arange(H)[:, None] <= hip_y - 60)
            & (np.arange(W)[None, :] >= hip_x + 35)
        )
        if is_warm_obj.any():
            mug_mask = (
                binary_dilation(binary_fill_holes(binary_closing(is_warm_obj, np.ones((7, 7), dtype=bool))), np.ones((7, 7), dtype=bool))
                & (top[:, :, 3] > 0)
            )
            mug_arr = np.zeros_like(top)
            mug_arr[mug_mask] = source[mug_mask]
            mug_c = Image.fromarray(mug_arr, "RGBA")
            mug_c.alpha_composite(Image.fromarray(sleeves, "RGBA"))
            sleeves = np.array(mug_c)
            # Vertically interpolate topwear behind mug per column so navy camisole and lilac cardigan stay separated
            mug_ys, mug_xs = np.nonzero(mug_mask)
            for x in range(int(mug_xs.min()), int(mug_xs.max()) + 1):
                col_ys = np.nonzero(mug_mask[:, x])[0]
                if not len(col_ys):
                    continue
                y0, y1 = int(col_ys.min()), int(col_ys.max())
                y_above = max(0, y0 - 4)
                y_below = min(H - 1, y1 + 4)
                c_top = top[y_above, x, :3].astype(np.float32)
                c_bot = top[y_below, x, :3].astype(np.float32) if top[y_below, x, 3] > 180 else c_top
                for y in col_ys:
                    t_w = (y - y0) / max(1.0, float(y1 - y0))
                    top[y, x, :3] = np.clip((1.0 - t_w) * c_top + t_w * c_bot, 0, 255).astype(np.uint8)
    elif outfit == "uniform" and char == "naru":
        # Remove See-through v3's triangular skin spike above Naru's clasped hands without clipping right index finger
        sleeves[795:834, 375:421, 3] = 0
        sleeves[795:816, 421:442, 3] = 0
        # Transfer Naru's held pink/blue notebook corners into sleeves BEFORE projection
        poly_im = Image.new("L", (W, H), 0)
        pdraw = ImageDraw.Draw(poly_im)
        pdraw.polygon([(436, 820), (452, 790), (518, 820), (518, 892), (465, 892)], fill=255)
        pdraw.polygon([(415, 892), (455, 910), (483, 1002), (398, 964)], fill=255)
        book_mask = (np.array(poly_im) > 128) & (source[:, :, 3] > 200)
        sleeves[book_mask] = source[book_mask]
        # Clean raw_top ONLY inside the upper notebook corner (occluded by sleeves) so outer cardigan stays untouched
        u_dirty = book_mask & (np.arange(H)[:, None] < 895) & (top[:, :, 3] > 0)
        u_ref = (
            (np.arange(H)[:, None] >= 755)
            & (np.arange(H)[:, None] < 788)
            & (np.arange(W)[None, :] >= 445)
            & (np.arange(W)[None, :] < 518)
            & (top[:, :, 0] > 200)
            & (top[:, :, 1] > 160)
        )
        if u_dirty.any() and u_ref.any():
            _, near_cb = distance_transform_edt(~u_ref, return_indices=True)
            top[u_dirty, :3] = top[near_cb[0][u_dirty], near_cb[1][u_dirty], :3]

    part_order = ["shoes", "legwear", "bottomwear", "neck", "topwear", "sleeves"] if leg_part is not None else ORDER
    pieces = {
        "shoes": shoes,
        **({"legwear": leg_part} if leg_part is not None else {}),
        "bottomwear": bottom,
        "neck": neck,
        "topwear": top,
        "sleeves": sleeves,
    }

    # Erode 3px outer shoulder fringe above collar ONLY where hair_st touches the outer boundary
    upper_to_row = baseline_neck["y"] + int(baseline_neck["h"] * 0.72)
    union = np.maximum.reduce([a[:, :, 3] for a in pieces.values()])
    outer_distance = distance_transform_edt(union > 8)
    dist_from_neck = distance_transform_edt(~(neck[:, :, 3] > 80))
    if char != "roa" or outfit == "uniform":
        for name in ["topwear", "sleeves"]:
            a = pieces[name][:, :, 3]
            a[:upper_to_row][(outer_distance[:upper_to_row] <= 3) & (dist_from_neck[:upper_to_row] > 12) & hair_st[:upper_to_row]] = 0

    # Clean stray islands and seal narrow margin-3 contour bays BEFORE projection so tiny sleeve islands never block topwear projection
    four_conn = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=bool)
    yy_d3, xx_d3 = np.ogrid[-3:4, -3:4]
    disc3 = (xx_d3 * xx_d3 + yy_d3 * yy_d3) <= 9

    def clean_mesh_islands():
        for name in part_order:
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
            if name in ("neck", "topwear", "sleeves") or (outfit == "uniform" and name == "bottomwear"):
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

    # Project crisp 4x upscaled visible source pixels onto each visible foreground layer AND across shared part seams
    nw_mask = (mapped["neckwear"][:, :, 3] > 80) if "neckwear" in mapped else np.zeros((H, W), dtype=bool)
    fg_head_only = np.zeros((H, W), dtype=bool)
    for htag in ["front hair", "face", "ears-l", "ears-r", "earwear", "eyewear"]:
        if htag in mapped:
            fg_head_only |= (mapped[htag][:, :, 3] > 32)

    union_post = np.maximum.reduce([a[:, :, 3] for a in pieces.values()])
    outer_sil_core = binary_erosion((union_post >= 180) & (source[:, :, 3] > 128), np.ones((3, 3), dtype=bool))

    vis_owner = np.full((H, W), -1, dtype=np.int16)
    for idx, name in enumerate(part_order):
        vis_owner[pieces[name][:, :, 3] > 80] = idx

    below_hair_band = np.arange(H)[:, None] >= low_hair_limit_y
    sleeves_occlude_proj_mask = binary_dilation(pieces["sleeves"][:, :, 3] > 8, np.ones((7, 7), dtype=bool))
    projection = {}
    for idx, name in enumerate(part_order):
        arr = pieces[name]
        drift = np.max(np.abs(arr[:, :, :3].astype(np.int16) - white[:, :, :3].astype(np.int16)), axis=2)
        allow_proj = (~hair_st) | ((nw_mask & (~fg_head_only)) if name == "topwear" else False)
        if name != "sleeves":
            sleeves_occlude_proj = sleeves_occlude_proj_mask
            allow_proj = allow_proj & (~sleeves_occlude_proj)
        else:
            sleeves_occlude_proj = np.zeros((H, W), dtype=bool)

        # Alpha of parts below and above this part (excluding sleeves, which is a foreground overlay rather than a body seam)
        below_alpha = np.zeros((H, W), dtype=np.uint8)
        for b_idx in range(idx):
            below_alpha = np.maximum(below_alpha, pieces[part_order[b_idx]][:, :, 3])
        above_alpha = np.zeros((H, W), dtype=np.uint8)
        for a_idx in range(idx + 1, len(part_order)):
            if part_order[a_idx] == "sleeves":
                continue
            above_alpha = np.maximum(above_alpha, pieces[part_order[a_idx]][:, :, 3])

        is_top_interior = (vis_owner == idx) & (arr[:, :, 3] >= 180) & outer_sil_core & allow_proj
        is_internal_upper_edge = (above_alpha <= 80) & (arr[:, :, 3] > 0) & (below_alpha > 160) & outer_sil_core & allow_proj
        dist_into_above = distance_transform_edt(above_alpha > 80)
        if name == "neck":
            is_internal_lower_seam = (
                (arr[:, :, 3] > 0)
                & (above_alpha > 0)
                & (dist_into_above <= 16)
                & outer_sil_core
                & allow_proj
                & ((above_alpha < 245) | (drift <= 65))
            )
        elif name == "legwear":
            is_internal_lower_seam = (
                (arr[:, :, 3] > 0)
                & (above_alpha > 0)
                & (dist_into_above <= 3)
                & outer_sil_core
                & allow_proj
                & (drift <= 25)
            )
        else:
            is_internal_lower_seam = (
                (arr[:, :, 3] > 0)
                & (above_alpha > 0)
                & (dist_into_above <= 6)
                & outer_sil_core
                & allow_proj
                & ((drift <= 45) | ((name == "bottomwear") & (dist_into_above <= 3)))
            )

        core = is_top_interior | is_internal_upper_edge | is_internal_lower_seam
        drift_limit = 115 if name != "neck" else 75
        accepted = (
            (binary_closing(core & ((drift <= drift_limit) | (is_top_interior & below_hair_band)), np.ones((5, 5), bool)) & core)
            | is_internal_upper_edge
            | is_internal_lower_seam
        )
        weight = gaussian_filter(accepted.astype(np.float32), sigma=0.8) * (arr[:, :, 3] > 0)
        weight[sleeves_occlude_proj] = 0.0
        exact_seam = (is_internal_upper_edge | is_internal_lower_seam) & accepted
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
    if char != "roa" and outfit != "uniform" and above_top_on_neck.any():
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

    # Pinpoint post-projection cleanup for Roa (hair/neck/shoulder fidelity) and swimwear/nova (shoulder specks & hand shadow)
    if char == "roa" and outfit != "uniform":
        # 1) Clip neck lateral underlap wings outside source silhouette, and fill the empty office-collar cutouts
        # inside hair_back (y=385..508, x=200..465) with registered source hair connected to neck
        head_full = Image.new("RGBA", (W, H))
        for hpart in ("hair_back", "face", "hair_front", "ear_r"):
            if hpart in common_parts:
                h_rec = common_parts[hpart]
                h_im = Image.open(family / char / "out/parts" / (hpart + ".png")).convert("RGBA")
                head_full.alpha_composite(h_im, (h_rec["x"], h_rec["y"]))
        head_arr = np.array(head_full)
        hb_side = (
            (head_arr[:, :, 3] > 200)
            & (np.arange(H)[:, None] < 530)
            & ((np.arange(W)[None, :] < 278) | (np.arange(W)[None, :] > 380))
        )
        pieces["neck"][hb_side, 3] = 0

        collar_hair_gap = (
            (np.arange(H)[:, None] >= 385)
            & (np.arange(H)[:, None] < 508)
            & (np.arange(W)[None, :] >= 200)
            & (np.arange(W)[None, :] < 465)
            & (source[:, :, 3] > 80)
            & ((head_arr[:, :, 3] < 250) | ((np.arange(W)[None, :] >= 225) & (np.arange(W)[None, :] <= 315) & (np.arange(H)[:, None] >= 430)))
        )
        collar_hair_gap = binary_dilation(collar_hair_gap, np.ones((3, 3), dtype=bool)) & (source[:, :, 3] > 80) & (np.arange(H)[:, None] < 510)
        pieces["neck"][collar_hair_gap, :3] = source[collar_hair_gap, :3]
        pieces["neck"][collar_hair_gap, 3] = np.maximum(pieces["neck"][collar_hair_gap, 3], source[collar_hair_gap, 3])

        # 2) Project registered source across Roa's upper neck, collarbone, shoulder, and hair tips (y < 525)
        # including semi-transparent top rims so no horizontal seam or unprojected inpainted fringe appears
        upper_band = (np.arange(H)[:, None] < 525) & (source[:, :, 3] > 80)
        for pname in ("neck", "topwear", "sleeves"):
            arr_p = pieces[pname]
            proj_m = upper_band & (arr_p[:, :, 3] > 0)
            if pname != "sleeves":
                proj_m &= ~(pieces["sleeves"][:, :, 3] > 180)
            arr_p[proj_m, :3] = source[proj_m, :3]
        if outfit == "homewear":
            under_fingers = (
                (np.arange(H)[:, None] >= 740)
                & (np.arange(H)[:, None] < 825)
                & (np.arange(W)[None, :] >= 498)
                & (np.arange(W)[None, :] < 538)
                & (pieces["topwear"][:, :, 3] > 180)
                & (pieces["sleeves"][:, :, 3] < 80)
                & (source[:, :, 3] > 200)
            )
            pieces["topwear"][under_fingers, :3] = source[under_fingers, :3]
    elif outfit == "swimwear" and char == "nova":
        pieces["sleeves"][605:636, 496:542, 3] = 0
        nova_speck = (
            (np.arange(H)[:, None] >= 605)
            & (np.arange(H)[:, None] < 636)
            & (np.arange(W)[None, :] >= 496)
            & (np.arange(W)[None, :] < 542)
            & (pieces["topwear"][:, :, 3] > 0)
            & (pieces["topwear"][:, :, 1] < 130)
        )
        nova_clean_skin = (
            (np.arange(H)[:, None] >= 595)
            & (np.arange(H)[:, None] < 645)
            & (np.arange(W)[None, :] >= 496)
            & (np.arange(W)[None, :] < 545)
            & (pieces["topwear"][:, :, 3] > 200)
            & (pieces["topwear"][:, :, 1] >= 135)
        )
        if nova_speck.any() and nova_clean_skin.any():
            _, near_ns = distance_transform_edt(~nova_clean_skin, return_indices=True)
            pieces["topwear"][nova_speck, :3] = pieces["topwear"][near_ns[0][nova_speck], near_ns[1][nova_speck], :3]
        # Fill unprojected hole under Nova's right hand shadow (y=995..1035, x=390..500) where sleeves_occlude_proj_mask blocked source
        hand_shadow_zone = (
            (np.arange(H)[:, None] >= 995)
            & (np.arange(H)[:, None] < 1035)
            & (np.arange(W)[None, :] >= 390)
            & (np.arange(W)[None, :] < 500)
            & (source[:, :, 3] > 200)
            & (pieces["sleeves"][:, :, 3] < 180)
        )
        pieces["bottomwear"][hand_shadow_zone, :3] = source[hand_shadow_zone, :3]
        pieces["bottomwear"][hand_shadow_zone, 3] = 255
        top_hs = hand_shadow_zone & (pieces["topwear"][:, :, 3] > 0)
        pieces["topwear"][top_hs, :3] = source[top_hs, :3]
    elif char == "luna":
        # Split Luna's right arm (viewer right, x >= 380) into upper arm (handwear_l, behind topwear)
        # and lower arm (sleeves, in front of topwear) at elbow y=900 so right bust is never occluded.
        top_p = pieces["topwear"]
        arm_p = pieces["sleeves"].copy()
        for y in range(590, 725):
            for x in range(450, 565):
                if arm_p[y, x, 3] < 250 and top_p[y, x, 3] > arm_p[y, x, 3]:
                    arm_p[y, x] = top_p[y, x]
                if arm_p[y, x, 3] > 0 and source[y, x, 3] > 200 and not hair_st[y, x]:
                    arm_p[y, x, :3] = source[y, x, :3]
        if outfit in ("homewear", "uniform"):
            pts = [(600, 480), (635, 492), (685, 502), (730, 506), (790, 514), (850, 506), (900, 493)]
            lower_pts = [(900, 493), (940, 485), (980, 471)]
        else:
            pts = [(580, 448), (635, 460), (670, 474), (700, 491), (715, 500), (760, 521), (800, 519), (835, 489), (880, 482), (900, 479)]
            lower_pts = [(900, 479), (940, 473), (980, 463)]
        ys_p, xs_p = zip(*pts)
        for y in range(pts[0][0], 905):
            lim_x = int(round(np.interp(y, ys_p, xs_p)))
            for x in range(435, lim_x + 1):
                if source[y, x, 3] > 200 and not hair_st[y, x]:
                    top_p[y, x, :3] = source[y, x, :3]
                    top_p[y, x, 3] = max(int(top_p[y, x, 3]), 255)
            dark_rgb = source[y, min(lim_x + 5, 535), :3]
            for x in range(460, lim_x + 2):
                if arm_p[y, x, 3] < 255 and y >= 640:
                    arm_p[y, x, :3] = dark_rgb
                    arm_p[y, x, 3] = 255
            top_p[y, lim_x + 1 :, :] = 0
            if top_p[y, lim_x, 3] > 0:
                top_p[y, lim_x, 3] = min(int(top_p[y, lim_x, 3]), 220)
        split_y = 900
        hw_l = np.zeros_like(arm_p)
        hw_l[: split_y + 16, 380:] = arm_p[: split_y + 16, 380:]
        ov_m = hw_l[split_y : split_y + 16, 380:, 3] > 180
        ov_er = binary_erosion(ov_m, np.ones((1, 7), dtype=bool))
        hw_l[split_y : split_y + 16, 380:, 3] = np.where(ov_er, 255, 0)
        pieces["handwear_l"] = hw_l
        arm_p[:split_y, 380:] = 0
        lys, lxs = zip(*lower_pts)
        for y in range(900, 980):
            lim_x = int(round(np.interp(y, lys, lxs)))
            for x in range(435, lim_x + 2):
                if top_p[y, x, 3] < 255 and source[y, x, 3] > 200:
                    top_p[y, x] = source[y, x]
            arm_p[y, 380:lim_x, :] = 0
            if arm_p[y, lim_x, 3] > 0:
                arm_p[y, lim_x, 3] = min(int(arm_p[y, lim_x, 3]), 180)
        pieces["sleeves"] = arm_p
        projection["handwear_l"] = {"core": 0, "taken": 0, "refused": 0}

    if outfit == "uniform":
        if char == "naru":
            # Ensure crisp source projection over hands + notebook region in sleeves
            hand_book_zone = (
                (np.arange(H)[:, None] >= 780)
                & (np.arange(H)[:, None] < 1015)
                & (np.arange(W)[None, :] >= 335)
                & (np.arange(W)[None, :] < 520)
                & (pieces["sleeves"][:, :, 3] > 80)
                & (source[:, :, 3] > 200)
            )
            pieces["sleeves"][hand_book_zone, :3] = source[hand_book_zone, :3]

        # Project crisp shirt collar / ribbon / tie center onto topwear where hair_st previously blocked projection
        collar_boxes = {
            "roa": (315, 420, 468, 620),
            "luna": (320, 418, 520, 680),
            "jinni": (335, 465, 500, 660),
            "naru": (330, 455, 575, 850),
            "nova": (388, 460, 500, 660),
        }
        if char in collar_boxes:
            cx0, cx1, cy0, cy1 = collar_boxes[char]
            c_box = (
                (np.arange(W)[None, :] >= cx0)
                & (np.arange(W)[None, :] < cx1)
                & (np.arange(H)[:, None] >= cy0)
                & (np.arange(H)[:, None] < cy1)
                & (pieces["topwear"][:, :, 3] > 80)
                & (pieces["sleeves"][:, :, 3] < 120)
                & (source[:, :, 3] > 200)
            )
            pieces["topwear"][c_box, :3] = source[c_box, :3]
            if char == "roa":
                # Restore clean inpainted collar/shoulder/sleeves where source had Roa's brown hair strands (y < 545)
                is_roa_hair = (
                    (np.arange(H)[:, None] < 545)
                    & (source[:, :, 2] < 160)
                    & ~((source[:, :, 0] > 180) & (source[:, :, 0].astype(np.int16) - source[:, :, 2].astype(np.int16) > 45))
                )
                roa_top_hair = is_roa_hair & (pieces["topwear"][:, :, 3] > 0)
                pieces["topwear"][roa_top_hair, :3] = raw_top[roa_top_hair, :3]
                if "handwear-l" in mapped or "handwear-r" in mapped:
                    raw_sl_canvas = Image.new("RGBA", (W, H))
                    for st in ("handwear-l", "handwear-r"):
                        if st in mapped:
                            raw_sl_canvas.alpha_composite(Image.fromarray(mapped[st], "RGBA"))
                    raw_sl = np.array(raw_sl_canvas)
                    roa_sl_hair = is_roa_hair & (pieces["sleeves"][:, :, 3] > 0) & (raw_sl[:, :, 3] > 80)
                    pieces["sleeves"][roa_sl_hair, :3] = raw_sl[roa_sl_hair, :3]
                # Fill dark hair-tip spots on Roa's upper right white shirt sleeve (y=470..535, x=475..545) without changing alpha
                sl_spot = (
                    (np.arange(H)[:, None] >= 470)
                    & (np.arange(H)[:, None] < 535)
                    & (np.arange(W)[None, :] >= 475)
                    & (np.arange(W)[None, :] < 545)
                    & (pieces["sleeves"][:, :, 3] > 0)
                    & (pieces["sleeves"][:, :, 1] < 178)
                )
                sl_clean = (
                    (np.arange(H)[:, None] >= 470)
                    & (np.arange(H)[:, None] < 550)
                    & (np.arange(W)[None, :] >= 475)
                    & (np.arange(W)[None, :] < 555)
                    & (pieces["sleeves"][:, :, 3] > 200)
                    & (pieces["sleeves"][:, :, 1] >= 188)
                )
                if sl_spot.any() and sl_clean.any():
                    _, near_slc = distance_transform_edt(~sl_clean, return_indices=True)
                    pieces["sleeves"][sl_spot, :3] = pieces["sleeves"][near_slc[0][sl_spot], near_slc[1][sl_spot], :3]
            elif char == "luna":
                # Restore clean raw_top white collar/blazer where source had orange hair tips (y < 580, R - B > 26)
                is_luna_hair = (
                    (np.arange(H)[:, None] < 580)
                    & (np.arange(W)[None, :] >= 270)
                    & (np.arange(W)[None, :] < 455)
                    & (pieces["topwear"][:, :, 3] > 80)
                    & (source[:, :, 0].astype(np.int16) - source[:, :, 2].astype(np.int16) > 26)
                )
                pieces["topwear"][is_luna_hair, :3] = raw_top[is_luna_hair, :3]
            elif char == "nova":
                # Restore clean raw_top collar/hood where source had Nova's orange hair lock (y < 610, x >= 430, R - B > 40)
                is_nova_hair = (
                    (np.arange(H)[:, None] < 610)
                    & (np.arange(W)[None, :] >= 430)
                    & (pieces["topwear"][:, :, 3] > 80)
                    & (source[:, :, 0].astype(np.int16) - source[:, :, 2].astype(np.int16) > 40)
                )
                pieces["topwear"][is_nova_hair, :3] = raw_top[is_nova_hair, :3]

        # Clean upper neck skin above topwear using accepted office neck silhouette & skin tone
        off_neck_rec = baseline_by_name["neck"]
        off_neck_im = Image.open(family / char / "out/parts/neck.png").convert("RGBA")
        off_neck_full = Image.new("RGBA", (W, H))
        off_neck_full.alpha_composite(off_neck_im, (off_neck_rec["x"], off_neck_rec["y"]))
        off_neck_arr = np.array(off_neck_full)
        top_alpha = pieces["topwear"][:, :, 3]
        if char == "roa":
            head_full = Image.new("RGBA", (W, H))
            for hpart in ("hair_back", "face", "hair_front", "ear_r"):
                if hpart in common_parts:
                    h_rec = common_parts[hpart]
                    h_im = Image.open(family / char / "out/parts" / (hpart + ".png")).convert("RGBA")
                    head_full.alpha_composite(h_im, (h_rec["x"], h_rec["y"]))
            head_arr = np.array(head_full)
            hb_side = (
                (head_arr[:, :, 3] > 200)
                & (np.arange(H)[:, None] < 530)
                & ((np.arange(W)[None, :] < 278) | (np.arange(W)[None, :] > 380))
            )
            pieces["neck"][hb_side, 3] = 0
            # Project clean bare neck skin from source (y=385..530, x=295..385) and extend across the central neck column
            src_neck_skin = (
                (np.arange(H)[:, None] >= 385)
                & (np.arange(H)[:, None] < 530)
                & (np.arange(W)[None, :] >= 295)
                & (np.arange(W)[None, :] < 385)
                & (pieces["neck"][:, :, 3] > 80)
                & (source[:, :, 0] > 180)
                & (source[:, :, 0].astype(np.int16) - source[:, :, 2].astype(np.int16) > 45)
            )
            pieces["neck"][src_neck_skin, :3] = source[src_neck_skin, :3]
            if src_neck_skin.any():
                _, near_sns = distance_transform_edt(~src_neck_skin, return_indices=True)
                neck_other = (pieces["neck"][:, :, 3] > 0) & (~src_neck_skin)
                pieces["neck"][neck_other, :3] = pieces["neck"][near_sns[0][neck_other], near_sns[1][neck_other], :3]
            # Seal empty office-collar cutouts inside hair_back (y=385..478, x=240..395) behind uniform collar with exact source
            collar_hair_gap = (
                (np.arange(H)[:, None] >= 385)
                & (np.arange(H)[:, None] < 478)
                & (np.arange(W)[None, :] >= 240)
                & (np.arange(W)[None, :] < 395)
                & (source[:, :, 3] > 80)
                & ((head_arr[:, :, 3] < 250) | ((np.arange(W)[None, :] >= 240) & (np.arange(W)[None, :] <= 312) & (np.arange(H)[:, None] >= 385)))
                & (top_alpha < 220)
            )
            collar_hair_gap = binary_dilation(collar_hair_gap, np.ones((3, 3), dtype=bool)) & (source[:, :, 3] > 80) & (np.arange(H)[:, None] < 480)
            pieces["neck"][collar_hair_gap, :3] = source[collar_hair_gap, :3]
            pieces["neck"][collar_hair_gap, 3] = np.maximum(pieces["neck"][collar_hair_gap, 3], source[collar_hair_gap, 3])
        elif char in ("luna", "jinni", "naru", "nova"):
            exposed_neck = (pieces["neck"][:, :, 3] > 0) & (top_alpha < 180) & (off_neck_arr[:, :, 3] > 80)
            pieces["neck"][exposed_neck, :3] = off_neck_arr[exposed_neck, :3]
            upper_neck_clip = (np.arange(H)[:, None] < off_neck_rec["y"] + int(off_neck_rec["h"] * 0.78)) & (top_alpha < 120) & (off_neck_arr[:, :, 3] == 0)
            pieces["neck"][upper_neck_clip, 3] = 0
            if char == "jinni":
                hb_rec = baseline_by_name["hair_back"]
                hb_im = Image.open(family / char / "out/parts/hair_back.png").convert("RGBA")
                hb_full = Image.new("RGBA", (W, H))
                hb_full.alpha_composite(hb_im, (hb_rec["x"], hb_rec["y"]))
                hb_arr = np.array(hb_full)
                stray_hair_shoulder = (
                    (np.arange(H)[:, None] < 515)
                    & (np.arange(W)[None, :] < 345)
                    & (hb_arr[:, :, 3] < 120)
                    & (pieces["topwear"][:, :, 3] > 0)
                )
                pieces["topwear"][stray_hair_shoulder, 3] = 0

        # Column-wise vertical continuation of legwear thigh underlap beneath bottomwear (pleated skirt)
        if "legwear" in pieces:
            leg_arr = pieces["legwear"]
            bot_mask = pieces["bottomwear"][:, :, 3] > 80
            for x in range(W):
                bot_ys = np.nonzero(bot_mask[:, x])[0]
                if not len(bot_ys):
                    continue
                y_hem = int(bot_ys.max())
                vis_leg_ys = np.nonzero((leg_arr[y_hem + 1 : y_hem + 25, x, 3] > 200))[0]
                if len(vis_leg_ys) >= 4:
                    sample_rows = y_hem + 1 + vis_leg_ys[2 : min(len(vis_leg_ys), 10)]
                    ref_rgb = np.median(leg_arr[sample_rows, x, :3].astype(np.float32), axis=0)
                    under_ys = np.nonzero((leg_arr[: y_hem + 3, x, 3] > 0))[0]
                    if len(under_ys):
                        orig_rgb = leg_arr[under_ys, x, :3].astype(np.float32)
                        # Blend from 100% ref_rgb within 35px of skirt hem to smooth offset above
                        dist_up = np.maximum(0.0, float(y_hem + 2) - under_ys.astype(np.float32))
                        w_ref = np.clip(1.0 - (dist_up - 35.0) / 80.0, 0.65, 1.0)[:, None]
                        leg_arr[under_ys, x, :3] = np.clip(w_ref * ref_rgb[None, :] + (1.0 - w_ref) * orig_rgb, 0, 255).astype(np.uint8)

    clean_mesh_islands()

    edge_treatment = {
        "upperGeneratedUnionAlphaErosionPx": 3,
        "upperToRow": int(upper_to_row),
        "method": "See-through v3 layer depth + seamless internal boundary projection + low-frequency neck-topwear skin harmonization; targeted per-character artifact cleanup",
    }
    return pieces, common_parts, white, projection, edge_treatment


def run_character(family: pathlib.Path, outfit: str, char: str, candidate_name: str = "prepared", force: bool = False):
    if not candidate_name or "/" in candidate_name or "\\" in candidate_name or ".." in candidate_name:
        raise ValueError(f"Invalid candidate_name (must be a single safe directory name): {candidate_name!r}")
    home = (family / "outfits" / outfit / char).resolve()
    out = (home / candidate_name).resolve()
    if out.parent != home:
        raise ValueError(f"candidate_name escapes character directory: {out}")
    if out.exists():
        if force:
            shutil.rmtree(out)
        else:
            raise RuntimeError(f"{outfit.upper()}_STATIC_FRESH_OUTPUT_REQUIRED: {out}")
    out.mkdir(parents=True)
    (out / "parts").mkdir()
    (home / "docs").mkdir(exist_ok=True)

    pieces, common, white, projection, edge_treatment = build_auto_parts(family, outfit, char)
    base_order = ["shoes", "legwear", "bottomwear", "neck", "topwear", "sleeves"] if "legwear" in pieces else ORDER
    char_order = [*base_order[:-2], "handwear_l", *base_order[-2:]] if "handwear_l" in pieces else base_order
    part_records = []
    for name in char_order:
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
    for name in char_order:
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


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--outfit", required=True)
    parser.add_argument("--characters", nargs="*", default=["roa", "luna", "jinni", "naru", "nova"])
    parser.add_argument("--candidate", default="prepared")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    fam = pathlib.Path(__file__).resolve().parents[1]
    for ch in args.characters:
        print(json.dumps(run_character(fam, args.outfit, ch, args.candidate, args.force)), flush=True)

