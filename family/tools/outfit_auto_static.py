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
        im800 = Image.fromarray(cleaned, "RGBA").resize((2284, 2284), Image.Resampling.BICUBIC).crop((742, 0, 1542, 2284))
        arr800 = np.array(im800)
        if np.count_nonzero(arr800[:, :, 3] > 16) < 200:
            continue
        mapped[tag] = arr800
        layer_order.append(tag)
        layer_idx_map[tag] = i

    # Upper hair/head mask from See-through v3 above the collar/neck base
    hair_cutoff_y = baseline_neck["y"] + baseline_neck["h"]
    hair_st = np.zeros((H, W), dtype=bool)
    for htag in ["back hair", "front hair", "face", "ears-l", "ears-r", "earwear"]:
        if htag in mapped:
            hair_st |= (mapped[htag][:, :, 3] > 32)
    hair_st[hair_cutoff_y:, :] = False

    # Raw topwear (+ neckwear) before bridge cuts, used as body reference for background handwear filtering
    top_canvas = Image.new("RGBA", (W, H))
    for t in layer_order:
        if t in ("topwear", "neckwear") and t in mapped:
            top_canvas.alpha_composite(Image.fromarray(mapped[t], "RGBA"))
    raw_top = np.array(top_canvas)

    # 1. Sleeves (handwear-l + handwear-r + objects)
    top_idx = layer_idx_map.get("topwear", 999)
    err_raw_top = detail_and_color_error(raw_top, white, sigma_patch=8.0)
    raw_top_interior = binary_erosion(raw_top[:, :, 3] > 180, np.ones((9, 9), dtype=bool))
    sleeves_canvas = Image.new("RGBA", (W, H))
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
        if layer_idx_map[t] < top_idx:
            err_hw = detail_and_color_error(arr, white, sigma_patch=8.0)
            fg_seed = raw_top_interior & (arr[:, :, 3] > 80) & (err_hw + 5.0 < err_raw_top) & (err_raw_top > 16.0)
            fg_seed = binary_closing(binary_opening(fg_seed, np.ones((7, 7), bool)), np.ones((15, 15), bool))
            comp, n_c = label(fg_seed)
            keep_fg = np.zeros((H, W), dtype=bool)
            if n_c > 0:
                cnts = np.bincount(comp.ravel())
                cnts[0] = 0
                valid = cnts >= 1500
                valid[0] = False
                keep_fg = valid[comp]
            keep_fg = binary_dilation(keep_fg, np.ones((9, 9), bool))
            clear_behind = (raw_top[:, :, 3] > 120) & (~keep_fg)
            arr[clear_behind, 3] = 0
        sleeves_canvas.alpha_composite(Image.fromarray(arr, "RGBA"))
    sleeves = np.array(sleeves_canvas)
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

    # 3. Shoes (footwear or lower ankle/slipper split from bottomwear)
    if "footwear" in mapped:
        shoes = mapped["footwear"].copy()
        shoes_ys = np.nonzero(shoes[:, :, 3] > 80)[0]
        if len(shoes_ys):
            clear_bot_y = max(baseline_shoes["y"], int(shoes_ys.min()) + 28)
            bottom[clear_bot_y:, :, 3] = 0
    else:
        bot_ys = np.nonzero(bottom[:, :, 3] > 80)[0]
        shoes_split_y = min(baseline_shoes["y"], int(bot_ys.max()) - 140) if len(bot_ys) else baseline_shoes["y"]
        shoes = bottom.copy()
        shoes[:shoes_split_y, :, 3] = 0
        bottom[shoes_split_y + 22 :, :, 3] = 0

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

    # Trim bare legwear bleed under sheer robes where topwear genuinely wins
    top_wins_over_leg = overlap_tb & (~bot_wins) & (bot[:, :, 3] <= 32)
    bottom[top_wins_over_leg, 3] = 0

    take_bot_src = bot_wins & (source[:, :, 3] > 128) & (err_bot <= 35.0) & (~fg_occluder)
    bottom[take_bot_src] = source[take_bot_src]

    # Resolve topwear vs visible neck skin above shoulder/collar
    col_neck = color_error_smooth(neck, white, sigma_patch=4.0)
    col_top = color_error_smooth(top, white, sigma_patch=4.0)
    neck_box_y = baseline_neck["y"] + int(baseline_neck["h"] * 0.85)
    ov_tn = (top[:, :, 3] > 16) & (neck[:, :, 3] > 180) & (np.arange(H)[:, None] <= neck_box_y)
    neck_wins = binary_closing(ov_tn & (col_neck + 12.0 < col_top) & (col_top > 25.0), np.ones((5, 5), bool))
    top[neck_wins, 3] = 0

    pieces = {
        "shoes": shoes,
        "bottomwear": bottom,
        "neck": neck,
        "topwear": top,
        "sleeves": sleeves,
    }

    # Erode 3px upper generated union fringe above shoulder where See-through hair was removed
    upper_to_row = baseline_neck["y"] + int(baseline_neck["h"] * 0.72)
    for name in ["topwear", "sleeves"]:
        pieces[name][:upper_to_row][hair_st[:upper_to_row], 3] = 0
    union = np.maximum.reduce([a[:, :, 3] for a in pieces.values()])
    outer_distance = distance_transform_edt(union > 8)
    for name in ["topwear", "sleeves"]:
        a = pieces[name][:, :, 3]
        a[:upper_to_row][outer_distance[:upper_to_row] <= 3] = 0

    # Project crisp 4x upscaled visible source pixels onto each visible foreground layer
    vis_owner = np.full((H, W), -1, dtype=np.int16)
    for idx, name in enumerate(ORDER):
        vis_owner[pieces[name][:, :, 3] > 80] = idx
    projection = {}
    for idx, name in enumerate(ORDER):
        arr = pieces[name]
        drift = np.max(np.abs(arr[:, :, :3].astype(np.int16) - white[:, :, :3].astype(np.int16)), axis=2)
        core = binary_erosion((vis_owner == idx) & (arr[:, :, 3] >= 200) & (source[:, :, 3] > 128) & (~hair_st), np.ones((3, 3), bool))
        accepted = binary_closing(core & (drift <= 75), np.ones((5, 5), bool)) & core
        weight = gaussian_filter(accepted.astype(np.float32), sigma=1.0) * (arr[:, :, 3] > 0)
        arr[:, :, :3] = np.clip(
            weight[:, :, None] * source[:, :, :3] + (1.0 - weight[:, :, None]) * arr[:, :, :3],
            0,
            255,
        ).astype(np.uint8)
        projection[name] = {
            "core": int(core.sum()),
            "taken": int(accepted.sum()),
            "refused": int((core & (drift > 75)).sum()),
        }

    # Clean stray islands and add interior-sampled EDT underlap for neck under topwear/sleeves
    four_conn = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=bool)

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
                if small.any():
                    arr[small[comp], 3] = 0

    clean_mesh_islands()
    for idx in [2]:  # neck under topwear/sleeves
        name = ORDER[idx]
        upper_opaque = np.zeros((H, W), dtype=bool)
        for upper_name in ORDER[idx + 1 :]:
            upper_opaque |= (pieces[upper_name][:, :, 3] == 255)
        uncovered = (pieces[name][:, :, 3] > 180) & (~upper_opaque)
        if not uncovered.any():
            continue
        interior = binary_erosion(uncovered, np.ones((7, 7), dtype=bool))
        sample_mask = interior if interior.any() else uncovered
        dist_uncov, _ = distance_transform_edt(~uncovered, return_indices=True)
        _, nearest_idx = distance_transform_edt(~sample_mask, return_indices=True)
        silhouette = binary_fill_holes(binary_closing(upper_opaque | uncovered, np.ones((25, 25), dtype=bool)))
        outer_sil_dist = distance_transform_edt(silhouette)
        near_ul = (dist_uncov <= 22) & (outer_sil_dist >= 6) & upper_opaque & (pieces[name][:, :, 3] <= 8)
        if near_ul.any():
            pieces[name][near_ul, :3] = pieces[name][nearest_idx[0][near_ul], nearest_idx[1][near_ul], :3]
            pieces[name][near_ul, 3] = 255
    clean_mesh_islands()

    edge_treatment = {
        "upperGeneratedUnionAlphaErosionPx": 3,
        "upperToRow": int(upper_to_row),
        "method": "See-through v3 layer depth + local color/DoG detail error; zero manual polygons",
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
