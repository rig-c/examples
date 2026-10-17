#!/usr/bin/env python3
"""Static 7-part clothing decomposition for all 5 Family swimwear characters.

Uses each character's full-pass See-through v3 masks, registered 4x upscaled
clothing source, explicit garment boundary polygons, and accepted office head
parts. Emits no rig/Spine data into prepared/.
"""
import argparse
import json
import os
import pathlib
import shutil

os.environ.update(OMP_NUM_THREADS="4", OPENBLAS_NUM_THREADS="4", MKL_NUM_THREADS="4")
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import binary_closing, binary_dilation, binary_erosion, distance_transform_edt, gaussian_filter, label

W, H = 800, 2284
OFFICE_CLOTHING = {"shoes", "legwear", "bottomwear", "neck", "neckwear", "topwear", "handwear_r", "handwear_l"}


def clean(array):
    alpha = array[:, :, 3]
    components, n = label(alpha > 8, np.ones((3, 3), dtype=bool))
    if n == 0:
        return np.zeros_like(array)
    counts = np.bincount(components.ravel())
    counts[0] = 0
    keep = counts >= max(40, int(counts.max()) * 0.01)
    keep[0] = False
    result = array.copy()
    result[~keep[components], 3] = 0
    return result


def polygon(points):
    im = Image.new("L", (W, H))
    ImageDraw.Draw(im).polygon(points, fill=255)
    return np.array(im) > 0


def composite_layers(*arrays):
    canvas = Image.new("RGBA", (W, H))
    for arr in arrays:
        if arr is not None and np.any(arr[:, :, 3] > 0):
            canvas.alpha_composite(Image.fromarray(arr, "RGBA"))
    return np.array(canvas)


def fill_occluded_from_nearest(arr, visible_mask, occluded_mask):
    """Fill occluded_mask pixels in arr using nearest RGB from visible_mask pixels."""
    valid = visible_mask & (arr[:, :, 3] > 128)
    if not valid.any() or not occluded_mask.any():
        return
    _, nearest_idx = distance_transform_edt(~valid, return_indices=True)
    arr[occluded_mask, :3] = arr[nearest_idx[0][occluded_mask], nearest_idx[1][occluded_mask], :3]
    arr[occluded_mask, 3] = 255


def accepted_head_alpha(family, char):
    baseline = json.loads((family / char / "out/parts.json").read_text())
    common = [r for r in baseline["parts"] if r["name"] not in OFFICE_CLOTHING and r["name"] != "hair_back"]
    canvas = Image.new("RGBA", (W, H))
    for r in common:
        im = Image.open(family / char / "out/parts" / (r["name"] + ".png")).convert("RGBA")
        canvas.alpha_composite(im, (r["x"], r["y"]))
    return np.array(canvas)[:, :, 3]


def load_character_layers(home, wanted, hair_max_y):
    raw = home / "inputs/layers/full_orig"
    source = np.array(Image.open(home / "inputs/upscale-run/registered-upscaled.png").convert("RGBA"))
    white = np.array(Image.open(home / "inputs/painting-clothing-source.png").convert("RGBA"))
    manifest = json.loads((raw / "layers.json").read_text())
    if [manifest["width"], manifest["height"]] != [1024, 1024]:
        raise RuntimeError("SWIMWEAR_STATIC_FULL_FRAME_REQUIRED")
    entries = manifest["layers"]
    run_arrays = []
    for e in entries:
        im = Image.open(raw / "parts" / (e["name"] + ".png")).convert("RGBA")
        canvas = Image.new("RGBA", (1024, 1024))
        canvas.alpha_composite(im, (e["left"], e["top"]))
        run_arrays.append(clean(np.array(canvas)))

    owner = np.full((H, W), -1, dtype=np.int16)
    mapped = {}
    for i, (entry, array) in enumerate(zip(entries, run_arrays)):
        a = Image.fromarray(array[:, :, 3], "L").resize((2284, 2284), Image.Resampling.BICUBIC).crop((742, 0, 1542, 2284))
        owner[np.array(a) >= 250] = i
        if entry["name"] in wanted:
            im = Image.fromarray(array, "RGBA").resize((2284, 2284), Image.Resampling.BICUBIC).crop((742, 0, 1542, 2284))
            mapped[entry["name"]] = np.array(im)

    hair_st = np.zeros((H, W), dtype=bool)
    for hname in ["back hair", "front hair"]:
        e = next((e for e in entries if e["name"] == hname), None)
        if e is None:
            continue
        im = Image.open(raw / "parts" / (hname + ".png")).convert("RGBA")
        c1024 = Image.new("RGBA", (1024, 1024))
        c1024.alpha_composite(im, (e["left"], e["top"]))
        a800 = np.array(c1024.resize((2284, 2284), Image.Resampling.BICUBIC).crop((742, 0, 1542, 2284)))[:, :, 3]
        hair_st |= (a800 > 24)
    hair_st[hair_max_y:, :] = False

    projection = {}
    inside_swimwear = source[:, :, 3] > 8
    for name, array in mapped.items():
        i = next(i for i, e in enumerate(entries) if e["name"] == name)
        if name == "neck":
            projection[name] = {"core": 0, "taken": 0, "refused": 0}
            continue
        outside = (~inside_swimwear) & (np.arange(H)[:, None] >= hair_max_y)
        array[outside, 3] = 0
        core = binary_erosion((owner == i) & (array[:, :, 3] >= 250) & (~hair_st), np.ones((5, 5), bool))
        drift = np.max(np.abs(array[:, :, :3].astype(np.int16) - white[:, :, :3].astype(np.int16)), axis=2)
        accepted = binary_closing(core & (drift <= 90), np.ones((5, 5), bool)) & core
        weight = gaussian_filter(accepted.astype(np.float32), sigma=1) * core
        array[:, :, :3] = np.clip(
            weight[:, :, None] * white[:, :, :3] + (1 - weight[:, :, None]) * array[:, :, :3],
            0,
            255,
        ).astype(np.uint8)
        projection[name] = {
            "core": int(core.sum()),
            "taken": int(accepted.sum()),
            "refused": int((core & (drift > 90)).sum()),
        }
    return source, white, mapped, projection


def apply_edge_treatment(pieces, source, upper_to_row, band_to_row, topwear_underlap_px=4, cardigan_underlap_px=4):
    edge_treatment = {
        "upperGeneratedUnionAlphaErosionPx": 3,
        "upperToRow": upper_to_row,
        "sourceOuterBoundaryBandPx": 10,
        "sourceBandRows": [upper_to_row, band_to_row],
    }
    union = np.maximum.reduce([a[:, :, 3] for a in pieces.values()])
    outer_distance = distance_transform_edt(union > 8)
    for name in ["topwear", "cardigan", "sleeves"]:
        a = pieces[name][:, :, 3]
        a[:upper_to_row][outer_distance[:upper_to_row] <= 3] = 0

    cloth_names = ["bottomwear", "topwear", "cardigan", "sleeves", "hands"]
    cloth_owner = np.full((H, W), -1, dtype=np.int16)
    for i, name in enumerate(cloth_names):
        cloth_owner[pieces[name][:, :, 3] > 8] = i
    _, nearest = distance_transform_edt(cloth_owner < 0, return_indices=True)
    nearest_owner = cloth_owner[nearest[0], nearest[1]]
    inside_source = source[:, :, 3] > 128
    boundary_distance = np.where(
        inside_source,
        distance_transform_edt(inside_source),
        distance_transform_edt(~inside_source),
    )
    source_band = boundary_distance <= 10
    source_band[:upper_to_row] = False
    source_band[band_to_row:] = False
    for i, name in enumerate(cloth_names):
        pieces[name][source_band, 3] = 0
        chosen = source_band & (nearest_owner == i)
        pieces[name][chosen] = source[chosen]

    order = ["shoes", "bottomwear", "neck", "topwear", "cardigan", "sleeves", "hands"]
    from scipy.ndimage import binary_fill_holes
    four_conn = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=bool)

    def clean_mesh_islands():
        for name in order:
            arr = pieces[name]
            arr[arr[:, :, 3] <= 8, 3] = 0
            if name in ["neck", "topwear", "cardigan", "sleeves"]:
                mask = arr[:, :, 3] > 8
                if mask.any():
                    closed = binary_fill_holes(binary_closing(mask, np.ones((7, 7), dtype=bool)))
                    fill_px = closed & (~mask)
                    if fill_px.any():
                        _, near = distance_transform_edt(~mask, return_indices=True)
                        arr[fill_px, :3] = arr[near[0][fill_px], near[1][fill_px], :3]
                        arr[fill_px, 3] = 255
            comp, n_comp = label(arr[:, :, 3] > 8, four_conn)
            if n_comp > 1:
                counts = np.bincount(comp.ravel())
                counts[0] = 0
                min_sz = 500 if name in ["neck", "topwear", "cardigan", "sleeves"] else 200
                small = (counts < min_sz) & (counts > 0)
                small_mask = small[comp]
                if small_mask.any():
                    arr[small_mask, 3] = 0

    clean_mesh_islands()

    for idx in range(1, len(order) - 1):
        name = order[idx]
        if name == "shoes":
            continue
        upper_opaque = np.zeros((H, W), dtype=bool)
        for upper_name in order[idx + 1 :]:
            upper_opaque |= (pieces[upper_name][:, :, 3] == 255)
        uncovered = (pieces[name][:, :, 3] > 80) & (~upper_opaque)
        if not uncovered.any():
            continue
        target_ul_px = topwear_underlap_px if name == "topwear" else (cardigan_underlap_px if name == "cardigan" else 22)
        dist_uncov, nearest_idx = distance_transform_edt(~uncovered, return_indices=True)
        silhouette = binary_fill_holes(binary_closing(upper_opaque | uncovered, np.ones((25, 25), dtype=bool)))
        outer_sil_dist = distance_transform_edt(silhouette)
        near_px = min(22, target_ul_px)
        near_ul = (dist_uncov <= near_px) & (outer_sil_dist >= 2) & upper_opaque & (pieces[name][:, :, 3] <= 8)
        if target_ul_px > near_px:
            eroded = binary_erosion(uncovered, np.ones((11, 11), dtype=bool))
            rgb_arr = pieces[name][:, :, :3].astype(np.int16)
            luma = (rgb_arr[:, :, 0] + rgb_arr[:, :, 1] + rgb_arr[:, :, 2]) // 3
            bright_core = eroded & (luma > 38)
            sample_mask = bright_core if bright_core.any() else (eroded if eroded.any() else uncovered)
            _, color_idx = distance_transform_edt(~sample_mask, sampling=(3.0, 1.0), return_indices=True)
            deep_ul = (dist_uncov <= target_ul_px) & (outer_sil_dist >= 12) & upper_opaque & (pieces[name][:, :, 3] <= 8)
            underlap = near_ul | deep_ul
            if underlap.any():
                full_rgb = pieces[name][color_idx[0], color_idx[1], :3].astype(np.float32)
                for ch in range(3):
                    full_rgb[:, :, ch] = gaussian_filter(full_rgb[:, :, ch], sigma=6.0)
                pieces[name][underlap, :3] = np.clip(full_rgb[underlap], 0, 255).astype(np.uint8)
                pieces[name][near_ul, :3] = pieces[name][nearest_idx[0][near_ul], nearest_idx[1][near_ul], :3]
                pieces[name][underlap, 3] = 255
        elif near_ul.any():
            pieces[name][near_ul, :3] = pieces[name][nearest_idx[0][near_ul], nearest_idx[1][near_ul], :3]
            pieces[name][near_ul, 3] = 255

    clean_mesh_islands()
    return edge_treatment


def blend_visible_neck(neck_arr, source, neck_visible_poly, min_r=135, min_diff=35):
    source_is_skin = (source[:, :, 0].astype(int) > min_r) & (
        (source[:, :, 0].astype(int) - source[:, :, 2].astype(int)) > min_diff
    )
    neck_vis_mask = binary_erosion(polygon(neck_visible_poly) & source_is_skin, np.ones((3, 3), bool))
    neck = neck_arr.copy()
    w_neck = gaussian_filter(neck_vis_mask.astype(np.float32), sigma=2.0) * (neck[:, :, 3] > 0)
    neck[:, :, :3] = np.clip(
        w_neck[:, :, None] * source[:, :, :3] + (1.0 - w_neck[:, :, None]) * neck[:, :, :3],
        0,
        255,
    ).astype(np.uint8)
    return neck


def build_roa(home):
    source, white, mapped, projection = load_character_layers(
        home,
        {"footwear", "legwear", "bottomwear", "topwear", "handwear-l", "handwear-r", "neck", "objects"},
        hair_max_y=515,
    )
    shoes = source.copy()
    shoes[:2000, :, 3] = 0

    r_hand_poly = [(60, 1080), (195, 1080), (205, 1385), (60, 1385)]
    l_hand_poly = [
        (476, 665), (486, 635), (496, 608), (508, 582), (534, 554),
        (555, 542), (600, 538), (642, 522), (670, 512), (710, 524),
        (710, 602), (660, 616), (608, 602), (582, 592), (576, 635),
        (572, 680), (564, 706), (550, 712), (545, 724), (480, 724),
        (476, 690),
    ]
    l_hand_raw = polygon(l_hand_poly)
    is_navy_swimsuit = (source[:, :, 2].astype(int) - source[:, :, 0].astype(int)) > 6
    is_finger_robe_gap = (
        (np.arange(H)[:, None] > 645)
        & (np.arange(W)[None, :] >= 498)
        & (np.arange(W)[None, :] <= 558)
        & ((source[:, :, 0].astype(int) - source[:, :, 2].astype(int)) < 10)
        & ((source[:, :, 0].astype(int) - source[:, :, 1].astype(int)) < 12)
        & (source[:, :, 0].astype(int) < 140)
    )
    l_hand_mask = binary_closing(l_hand_raw & (~is_navy_swimsuit) & (~is_finger_robe_gap), np.ones((3, 3), dtype=bool))
    hands_mask = polygon(r_hand_poly) | l_hand_mask

    inner = [
        (218, 430), (382, 430), (416, 480), (450, 530), (474, 582),
        (512, 620), (524, 675), (508, 725), (468, 765), (468, 805),
        (482, 865), (502, 920), (522, 965), (382, 1105), (205, 960),
        (224, 900), (238, 835), (242, 775), (240, 710), (234, 635),
        (226, 550),
    ]
    inside = polygon(inner)

    outer_robe_l = polygon([(15, 950), (202, 950), (265, 1450), (265, 1615), (15, 1615)])
    outer_robe_r = polygon([(532, 950), (710, 950), (710, 1615), (545, 1615)])
    robe_left_tail = polygon([(15, 435), (245, 435), (245, 840), (205, 955), (265, 1450), (265, 1615), (15, 1615)]) & (~inside)
    robe_right_tail = polygon([(380, 435), (585, 435), (610, 865), (710, 950), (710, 1615), (545, 1615), (522, 965), (468, 805)]) & (~inside)
    r_forearm_poly = polygon([(90, 910), (190, 910), (190, 1085), (90, 1085)])

    open_pants = [
        (195, 950), (382, 1095), (535, 950), (555, 1460), (495, 2035), (235, 2035), (195, 1300),
    ]
    pants_vis = polygon(open_pants) & (~hands_mask) & (~outer_robe_l) & (~outer_robe_r)
    pants = np.zeros((H, W, 4), dtype=np.uint8)
    take_src = pants_vis & (source[:, :, 3] > 8)
    pants[take_src] = source[take_src]
    pants_occluded = polygon(open_pants) & (~take_src) & (source[:, :, 3] > 128)
    fill_occluded_from_nearest(pants, take_src, pants_occluded)
    pants[2035:, :, 3] = 0

    neck_visible = [(302, 370), (362, 405), (350, 444), (375, 476), (290, 476), (304, 438)]
    neck = blend_visible_neck(mapped["neck"], source, neck_visible, min_r=140, min_diff=45)
    neck[:410, :285, 3] = 0

    hand_occ_dilated = binary_dilation(l_hand_mask, np.ones((5, 5), dtype=bool))
    camisole = np.zeros((H, W, 4), dtype=np.uint8)
    cam_vis = inside & (~hand_occ_dilated) & (np.arange(H)[:, None] >= 440) & (source[:, :, 3] > 8)
    camisole[cam_vis] = source[cam_vis]
    for y in range(440, 458):
        fade = (y - 440) / 18.0
        mask_row = neck[y, 285:395, 3] > 200
        camisole[y, 285:395, 3][mask_row] = (camisole[y, 285:395, 3][mask_row].astype(np.float32) * fade).astype(np.uint8)
    cam_interior = binary_erosion(cam_vis, np.ones((11, 11), dtype=bool)) & (camisole[:, :, 2] > camisole[:, :, 0])
    fill_occluded_from_nearest(camisole, cam_interior if cam_interior.any() else cam_vis, inside & hand_occ_dilated & (source[:, :, 3] > 128))

    sleeve_upper_l = polygon([(15, 450), (150, 450), (150, 915), (15, 915)])
    sleeve_upper_r = polygon([(532, 475), (730, 475), (730, 865), (602, 865), (586, 598), (545, 545)])
    sleeves_raw = (r_forearm_poly | sleeve_upper_l | sleeve_upper_r) & (~inside)
    sleeves_mask = sleeves_raw & (~hands_mask)

    card_mask = (robe_left_tail | robe_right_tail | outer_robe_l | outer_robe_r) & (~sleeves_raw) & (~pants_vis)
    cardigan = np.zeros((H, W, 4), dtype=np.uint8)
    card_vis = card_mask & (~hand_occ_dilated) & (np.arange(H)[:, None] >= 445) & (source[:, :, 3] > 8)
    cardigan[card_vis] = source[card_vis]
    card_occ = card_mask & hand_occ_dilated & (source[:, :, 3] > 128)
    card_interior = binary_erosion(card_vis, np.ones((9, 9), dtype=bool)) & (cardigan[:, :, 0] > 95)
    fill_occluded_from_nearest(cardigan, card_interior if card_interior.any() else card_vis, card_occ)
    if card_occ.any():
        for ch in range(3):
            sm = gaussian_filter(cardigan[:, :, ch].astype(np.float32), sigma=4.0)
            cardigan[card_occ, ch] = np.clip(sm[card_occ], 0, 255).astype(np.uint8)

    sleeves = np.zeros((H, W, 4), dtype=np.uint8)
    sl_vis = sleeves_mask & (np.arange(H)[:, None] >= 450) & (source[:, :, 3] > 8)
    sleeves[sl_vis] = source[sl_vis]
    sl_occ = sleeves_raw & hands_mask & (np.arange(H)[:, None] >= 450) & (source[:, :, 3] > 128) & (np.arange(W)[None, :] < 595)
    sl_interior = binary_erosion(sl_vis, np.ones((9, 9), dtype=bool)) & (sleeves[:, :, 0] > 55)
    fill_occluded_from_nearest(sleeves, sl_interior if sl_interior.any() else sl_vis, sl_occ)

    hands = np.zeros((H, W, 4), dtype=np.uint8)
    hands_src = hands_mask & (source[:, :, 3] > 8)
    hands[hands_src] = source[hands_src]

    pieces = {
        "shoes": shoes,
        "bottomwear": pants,
        "neck": neck,
        "topwear": camisole,
        "cardigan": cardigan,
        "sleeves": sleeves,
        "hands": hands,
    }
    edge_treatment = apply_edge_treatment(pieces, source, upper_to_row=485, band_to_row=1615, topwear_underlap_px=52, cardigan_underlap_px=34)
    cuts = {
        "openPants": open_pants,
        "cardiganInnerBoundary": inner,
        "rightHand": r_hand_poly,
        "leftHand": l_hand_poly,
        "sourceShoesFromRow": 2000,
        "sourcePantsFullFromRow": 1100,
        "sourcePantsToRow": 2035,
        "sourceVisibleNeckPolygon": neck_visible,
    }
    return pieces, white, projection, edge_treatment, cuts


def build_luna(home):
    source, white, mapped, projection = load_character_layers(
        home,
        {"footwear", "legwear", "bottomwear", "topwear", "handwear-l", "handwear-r", "neck"},
        hair_max_y=640,
    )
    shoes = source.copy()
    shoes[:2020, :, 3] = 0

    hands_poly = [
        (280, 1110), (490, 1110), (555, 1200), (555, 1475), (215, 1475), (215, 1200),
    ]
    hands_mask = polygon(hands_poly)

    open_pants = [
        (165, 1020), (600, 1020), (600, 2050), (165, 2050),
    ]
    pants_vis = polygon(open_pants) & (~hands_mask)
    pants = np.zeros((H, W, 4), dtype=np.uint8)
    take_src = pants_vis & (source[:, :, 3] > 8)
    pants[take_src] = source[take_src]
    pants_occluded = polygon(open_pants) & hands_mask & (source[:, :, 3] > 128)
    fill_occluded_from_nearest(pants, take_src, pants_occluded)
    pants[2050:, :, 3] = 0

    neck_visible = [(315, 505), (398, 505), (398, 595), (315, 595)]
    neck = blend_visible_neck(mapped["neck"], source, neck_visible, min_r=150, min_diff=40)

    inner = [
        (266, 568), (452, 568), (478, 610), (498, 665), (520, 715),
        (532, 760), (530, 798), (514, 835), (492, 875), (484, 925),
        (478, 980), (472, 1032), (310, 1032), (304, 980), (295, 925),
        (282, 875), (268, 830), (254, 780), (248, 725), (248, 665),
        (254, 610),
    ]
    inside = polygon(inner)

    # Exclude pink hair strands on upper shoulders outside the neck opening
    shoulder_zone = (np.arange(H)[:, None] < 640) & ((np.arange(W)[None, :] < 312) | (np.arange(W)[None, :] > 398))
    is_pink_hair = shoulder_zone & (source[:, :, 0].astype(int) > 130) & ((source[:, :, 0].astype(int) - source[:, :, 2].astype(int)) > 20)

    card_poly = (
        polygon([
            (232, 580), (482, 580), (522, 650), (538, 760), (528, 860),
            (512, 950), (502, 1035), (266, 1035), (255, 950), (235, 860),
            (218, 760), (222, 650),
        ])
        & (~inside)
        & (~hands_mask)
    )
    sleeve_l_poly = polygon([(165, 580), (315, 580), (335, 1135), (185, 1135)]) & (~inside) & (~card_poly)
    sleeve_r_poly = polygon([(445, 580), (575, 580), (555, 1135), (445, 1135)]) & (~inside) & (~card_poly)
    sleeves_mask = (sleeve_l_poly | sleeve_r_poly) & (~hands_mask)

    camisole = np.zeros((H, W, 4), dtype=np.uint8)
    cam_vis = inside & (~hands_mask) & (~is_pink_hair) & (np.arange(H)[:, None] >= 568) & (source[:, :, 3] > 8)
    camisole[cam_vis] = source[cam_vis]
    cam_hair_occ = inside & is_pink_hair & (np.arange(H)[:, None] >= 580) & (source[:, :, 3] > 128)
    cam_interior = binary_erosion(cam_vis, np.ones((7, 7), dtype=bool))
    fill_occluded_from_nearest(camisole, cam_interior if cam_interior.any() else cam_vis, cam_hair_occ)
    for y in range(568, 584):
        fade = (y - 568) / 16.0
        camisole[y, 310:405, 3] = (camisole[y, 310:405, 3].astype(np.float32) * fade).astype(np.uint8)

    cardigan = np.zeros((H, W, 4), dtype=np.uint8)
    card_vis = card_poly & (~is_pink_hair) & (np.arange(H)[:, None] >= 580) & (source[:, :, 3] > 8)
    cardigan[card_vis] = source[card_vis]
    card_hair_occ = card_poly & is_pink_hair & (np.arange(H)[:, None] >= 590) & (source[:, :, 3] > 128)
    card_interior = binary_erosion(card_vis, np.ones((5, 5), dtype=bool))
    fill_occluded_from_nearest(cardigan, card_interior if card_interior.any() else card_vis, card_hair_occ)

    sleeves = np.zeros((H, W, 4), dtype=np.uint8)
    sl_vis = sleeves_mask & (~is_pink_hair) & (np.arange(H)[:, None] >= 580) & (source[:, :, 3] > 8)
    sleeves[sl_vis] = source[sl_vis]
    sl_hair_occ = sleeves_mask & is_pink_hair & (np.arange(H)[:, None] >= 590) & (source[:, :, 3] > 128)
    sl_interior = binary_erosion(sl_vis, np.ones((5, 5), dtype=bool))
    fill_occluded_from_nearest(sleeves, sl_interior if sl_interior.any() else sl_vis, sl_hair_occ)

    hands = np.zeros((H, W, 4), dtype=np.uint8)
    hands_src = hands_mask & (source[:, :, 3] > 8)
    hands[hands_src] = source[hands_src]

    pieces = {
        "shoes": shoes,
        "bottomwear": pants,
        "neck": neck,
        "topwear": camisole,
        "cardigan": cardigan,
        "sleeves": sleeves,
        "hands": hands,
    }
    edge_treatment = apply_edge_treatment(pieces, source, upper_to_row=600, band_to_row=1480, topwear_underlap_px=45, cardigan_underlap_px=34)
    cuts = {
        "openPants": open_pants,
        "cardiganInnerBoundary": inner,
        "hands": hands_poly,
        "sourceShoesFromRow": 2020,
        "sourcePantsFullFromRow": 1475,
        "sourcePantsToRow": 2050,
        "sourceVisibleNeckPolygon": neck_visible,
    }
    return pieces, white, projection, edge_treatment, cuts


def build_jinni(home):
    source, white, mapped, projection = load_character_layers(
        home,
        {"footwear", "legwear", "bottomwear", "topwear", "handwear-l", "handwear-r", "neck"},
        hair_max_y=585,
    )
    shoes = source.copy()
    shoes[:2000, :, 3] = 0

    hand_r_poly = [(295, 1060), (355, 1060), (398, 1200), (398, 1300), (315, 1300), (295, 1160)]
    hand_l_poly = [(525, 875), (610, 875), (675, 960), (675, 1065), (585, 1065), (525, 930)]
    hands_mask = polygon(hand_r_poly) | polygon(hand_l_poly)

    # In the right thigh slit region (x>=415, y=1180..1460), separate dark burgundy pareo fabric from bright thigh skin
    slit_zone = polygon([(480, 1180), (575, 1180), (575, 1460), (368, 1460), (435, 1340)])
    is_thigh_skin = binary_closing(
        slit_zone
        & (source[:, :, 0].astype(int) > 175)
        & (source[:, :, 1].astype(int) > 95)
        & ((source[:, :, 0].astype(int) - source[:, :, 1].astype(int)) > 40),
        np.ones((9, 9), dtype=bool),
    )
    pareo_region = polygon([
        (170, 925), (580, 925), (665, 1150), (665, 1420), (368, 1458), (170, 1445),
    ])
    pareo_fabric_mask = pareo_region & (~is_thigh_skin) & (~hands_mask)

    open_pants = [
        (150, 1150), (600, 1150), (600, 2035), (150, 2035),
    ]
    pants_vis = polygon(open_pants) & (~pareo_fabric_mask) & (~hands_mask)
    pants = np.zeros((H, W, 4), dtype=np.uint8)
    take_src = pants_vis & (source[:, :, 3] > 8)
    pants[take_src] = source[take_src]
    # Fill occluded thigh under the pareo skirt with nearest thigh skin RGB so swaying pareo reveals skin, not dark trousers
    pants_occluded = polygon([(250, 1150), (575, 1150), (575, 1465), (250, 1465)]) & (~take_src) & (source[:, :, 3] > 128)
    fill_occluded_from_nearest(pants, take_src, pants_occluded)
    pants[2035:, :, 3] = 0

    neck_visible = [(322, 470), (410, 470), (410, 565), (322, 565)]
    neck = blend_visible_neck(mapped["neck"], source, neck_visible, min_r=135, min_diff=35)
    neck[:560, :305, 3] = 0

    inner = [
        (300, 540), (495, 540), (575, 680), (580, 780),
        (548, 880), (545, 935), (335, 935), (335, 860), (315, 720),
    ]
    inside = polygon(inner)

    sleeve_r_poly = polygon([(180, 580), (318, 580), (345, 1065), (180, 1065)]) & (~inside) & (~pareo_region)
    sleeve_l_poly = polygon([(515, 840), (615, 840), (615, 950), (515, 950)]) & (~inside) & (~pareo_region)
    sleeves_mask = (sleeve_r_poly | sleeve_l_poly) & (~hands_mask)

    camisole = np.zeros((H, W, 4), dtype=np.uint8)
    cam_vis = inside & (~hands_mask) & (np.arange(H)[:, None] >= 548) & (source[:, :, 3] > 8)
    camisole[cam_vis] = source[cam_vis]
    for y in range(548, 566):
        fade = (y - 548) / 18.0
        camisole[y, 315:420, 3] = (camisole[y, 315:420, 3].astype(np.float32) * fade).astype(np.uint8)

    upper_side_mask = polygon([(265, 555), (565, 555), (575, 935), (265, 935)]) & (~inside) & (~sleeves_mask) & (~hands_mask)
    card_mask = pareo_fabric_mask | upper_side_mask
    cardigan = np.zeros((H, W, 4), dtype=np.uint8)
    card_vis = card_mask & (np.arange(H)[:, None] >= 565) & (source[:, :, 3] > 8)
    cardigan[card_vis] = source[card_vis]
    fill_occluded_from_nearest(cardigan, card_vis, pareo_region & hands_mask & (source[:, :, 3] > 128))

    sleeves = np.zeros((H, W, 4), dtype=np.uint8)
    sl_vis = sleeves_mask & (np.arange(H)[:, None] >= 580) & (source[:, :, 3] > 8)
    sleeves[sl_vis] = source[sl_vis]

    hands = np.zeros((H, W, 4), dtype=np.uint8)
    hands_src = hands_mask & (source[:, :, 3] > 8)
    hands[hands_src] = source[hands_src]

    pieces = {
        "shoes": shoes,
        "bottomwear": pants,
        "neck": neck,
        "topwear": camisole,
        "cardigan": cardigan,
        "sleeves": sleeves,
        "hands": hands,
    }
    edge_treatment = apply_edge_treatment(pieces, source, upper_to_row=585, band_to_row=1460, topwear_underlap_px=45, cardigan_underlap_px=34)
    cuts = {
        "openPants": open_pants,
        "cardiganInnerBoundary": inner,
        "rightHand": hand_r_poly,
        "leftHand": hand_l_poly,
        "sourceShoesFromRow": 2000,
        "sourcePantsFullFromRow": 1455,
        "sourcePantsToRow": 2035,
        "sourceVisibleNeckPolygon": neck_visible,
    }
    return pieces, white, projection, edge_treatment, cuts


def build_naru(home):
    source, white, mapped, projection = load_character_layers(
        home,
        {"footwear", "legwear", "bottomwear", "topwear", "handwear-l", "handwear-r", "neck"},
        hair_max_y=690,
    )
    shoes = source.copy()
    shoes[:2030, :, 3] = 0

    hands_poly = [
        (348, 882), (368, 858), (395, 838), (425, 824), (458, 814),
        (462, 824), (488, 840), (500, 875), (512, 912), (492, 938),
        (468, 916), (445, 902), (405, 902), (382, 922), (368, 942),
        (352, 938), (344, 915),
    ]
    hands_raw = polygon(hands_poly)
    is_cloth_gap = (source[:, :, 0].astype(int) > 188) & ((source[:, :, 0].astype(int) - source[:, :, 2].astype(int)) < 32)
    hands_mask = binary_closing(hands_raw & (~is_cloth_gap), np.ones((3, 3), dtype=bool))

    forearm_r_poly = [
        (238, 955), (275, 924), (318, 900), (355, 872), (372, 888),
        (368, 942), (325, 966), (262, 1000), (238, 992),
    ]
    forearm_l_poly = [
        (485, 858), (518, 898), (552, 928), (572, 950), (545, 995),
        (518, 972), (492, 952), (465, 920),
    ]
    forearms_raw = polygon(forearm_r_poly) | polygon(forearm_l_poly)
    forearms_mask = binary_closing(forearms_raw & (~is_cloth_gap), np.ones((3, 3), dtype=bool)) & (~hands_mask)

    open_pants = [
        (215, 1345), (585, 1345), (565, 2065), (235, 2065),
    ]
    pants_vis = polygon(open_pants)
    pants = np.zeros((H, W, 4), dtype=np.uint8)
    take_src = pants_vis & (source[:, :, 3] > 8)
    pants[take_src] = source[take_src]
    pants_occluded = polygon([(235, 1180), (565, 1180), (565, 1350), (235, 1350)]) & (~take_src) & (source[:, :, 3] > 128)
    fill_occluded_from_nearest(pants, take_src, pants_occluded)
    pants[2065:, :, 3] = 0

    neck_visible = [
        (344, 590), (380, 601), (418, 580), (429, 580), (418, 621),
        (420, 641), (431, 657), (313, 657), (307, 636), (334, 625), (342, 613),
    ]
    neck_visible_mask = polygon(neck_visible)
    neck = mapped["neck"].copy()
    neck[neck_visible_mask] = source[neck_visible_mask]

    inner = [
        (315, 620), (465, 620), (488, 685), (508, 730), (530, 768),
        (526, 815), (515, 875), (510, 940), (506, 1035), (282, 1035),
        (280, 940), (272, 875), (260, 815), (256, 768), (276, 730),
        (295, 685),
    ]
    inside = polygon(inner) & (~neck_visible_mask)

    hands_full_mask = hands_mask | forearms_mask
    card_upper_poly = (
        polygon([
            (215, 630), (578, 630), (582, 820), (570, 940), (562, 1040),
            (235, 1040), (225, 940), (210, 820),
        ])
        & (~inside)
        & (~neck_visible_mask)
    )
    skirt_poly = polygon([(215, 1035), (575, 1035), (625, 1365), (175, 1365)])
    sleeve_r_raw = polygon([(145, 630), (305, 630), (305, 1080), (145, 1080)]) & (~inside) & (~card_upper_poly)
    sleeve_l_raw = polygon([(475, 630), (650, 630), (650, 1080), (495, 1080)]) & (~inside) & (~card_upper_poly)
    sleeves_raw = sleeve_r_raw | sleeve_l_raw
    sleeves_mask = sleeves_raw & (~hands_full_mask)
    card_raw = (card_upper_poly | (skirt_poly & (~inside) & (~sleeves_raw))) & (~neck_visible_mask)

    # Exclude dark brown hair strands above y=665 on outer shoulders
    is_brown_hair = (np.arange(H)[:, None] < 665) & (source[:, :, 0].astype(int) < 185) & (source[:, :, 2].astype(int) < 110)

    arm_occ = binary_dilation(hands_full_mask, np.ones((7, 7), dtype=bool))
    camisole = np.zeros((H, W, 4), dtype=np.uint8)
    cam_vis = inside & (~arm_occ) & (~is_brown_hair) & (np.arange(H)[:, None] >= 620) & (source[:, :, 3] > 8)
    camisole[cam_vis] = source[cam_vis]

    # Vertically interpolate clean white/ivory frill swimsuit texture across occluded hands/forearms
    occ_cam = inside & (hands_full_mask | arm_occ) & (~cam_vis) & (source[:, :, 3] > 128)
    is_clean_ivory = (
        cam_vis
        & (camisole[:, :, 0].astype(int) > 175)
        & (camisole[:, :, 1].astype(int) > 150)
        & (camisole[:, :, 2].astype(int) > 140)
    )
    valid_cam = binary_erosion(is_clean_ivory, np.ones((5, 5), dtype=bool))
    if not valid_cam.any():
        valid_cam = binary_erosion(cam_vis, np.ones((5, 5), dtype=bool))
    for x in range(255, 535):
        occ_ys = np.nonzero(occ_cam[:, x])[0]
        if not len(occ_ys):
            continue
        y0, y1 = int(occ_ys.min()), int(occ_ys.max())
        above_ys = np.nonzero(valid_cam[:y0, x])[0]
        below_ys = np.nonzero(valid_cam[y1 + 1 :, x])[0] + (y1 + 1)
        if len(above_ys) and len(below_ys):
            ya = above_ys[-min(5, len(above_ys)) :]
            yb = below_ys[: min(5, len(below_ys))]
            top_rgb = camisole[ya, x, :3].astype(np.float32).mean(axis=0)
            bot_rgb = camisole[yb, x, :3].astype(np.float32).mean(axis=0)
            t = ((occ_ys - y0) / max(1.0, float(y1 - y0)))[:, None]
            camisole[occ_ys, x, :3] = np.clip((1.0 - t) * top_rgb + t * bot_rgb, 0, 255).astype(np.uint8)
            camisole[occ_ys, x, 3] = 255
    rem_occ = inside & (arm_occ | is_brown_hair) & (camisole[:, :, 3] <= 8) & (np.arange(H)[:, None] >= 630) & (source[:, :, 3] > 128)
    fill_occluded_from_nearest(camisole, valid_cam if valid_cam.any() else cam_vis, rem_occ)
    if occ_cam.any():
        for ch in range(3):
            sm = gaussian_filter(camisole[:, :, ch].astype(np.float32), sigma=2.5)
            camisole[occ_cam, ch] = np.clip(sm[occ_cam], 0, 255).astype(np.uint8)

    cardigan = np.zeros((H, W, 4), dtype=np.uint8)
    card_vis = card_raw & (~arm_occ) & (~is_brown_hair) & (np.arange(H)[:, None] >= 630) & (source[:, :, 3] > 8)
    cardigan[card_vis] = source[card_vis]
    card_occ = card_raw & (arm_occ | is_brown_hair) & (~card_vis) & (np.arange(H)[:, None] >= 635) & (source[:, :, 3] > 128)
    valid_card = binary_erosion(card_vis & (cardigan[:, :, 0] > 190) & (cardigan[:, :, 2] > 155), np.ones((5, 5), dtype=bool))
    if not valid_card.any():
        valid_card = card_vis
    for x in range(205, 590):
        occ_ys = np.nonzero(card_occ[:, x])[0]
        if not len(occ_ys):
            continue
        y0, y1 = int(occ_ys.min()), int(occ_ys.max())
        above_ys = np.nonzero(valid_card[:y0, x])[0]
        below_ys = np.nonzero(valid_card[y1 + 1 :, x])[0] + (y1 + 1)
        if len(above_ys) and len(below_ys):
            ya = above_ys[-min(5, len(above_ys)) :]
            yb = below_ys[: min(5, len(below_ys))]
            top_rgb = cardigan[ya, x, :3].astype(np.float32).mean(axis=0)
            bot_rgb = cardigan[yb, x, :3].astype(np.float32).mean(axis=0)
            t = ((occ_ys - y0) / max(1.0, float(y1 - y0)))[:, None]
            cardigan[occ_ys, x, :3] = np.clip((1.0 - t) * top_rgb + t * bot_rgb, 0, 255).astype(np.uint8)
            cardigan[occ_ys, x, 3] = 255
    rem_card = card_occ & (cardigan[:, :, 3] <= 8)
    fill_occluded_from_nearest(cardigan, valid_card, rem_card)
    if card_occ.any():
        for ch in range(3):
            sm = gaussian_filter(cardigan[:, :, ch].astype(np.float32), sigma=2.5)
            cardigan[card_occ, ch] = np.clip(sm[card_occ], 0, 255).astype(np.uint8)

    sleeves = np.zeros((H, W, 4), dtype=np.uint8)
    sl_vis = sleeves_mask & (~arm_occ) & (~is_brown_hair) & (np.arange(H)[:, None] >= 630) & (source[:, :, 3] > 8)
    sleeves[sl_vis] = source[sl_vis]
    sl_occ = sleeves_raw & (arm_occ | is_brown_hair) & (~sl_vis) & (np.arange(H)[:, None] >= 635) & (source[:, :, 3] > 128)
    sl_interior = binary_erosion(sl_vis, np.ones((5, 5), dtype=bool)) & (sleeves[:, :, 0] > 180)
    fill_occluded_from_nearest(sleeves, sl_interior if sl_interior.any() else sl_vis, sl_occ)

    hands = np.zeros((H, W, 4), dtype=np.uint8)
    hands_src = hands_full_mask & (source[:, :, 3] > 8)
    hands[hands_src] = source[hands_src]

    pieces = {
        "shoes": shoes,
        "bottomwear": pants,
        "neck": neck,
        "topwear": camisole,
        "cardigan": cardigan,
        "sleeves": sleeves,
        "hands": hands,
    }
    edge_treatment = apply_edge_treatment(pieces, source, upper_to_row=690, band_to_row=1370, topwear_underlap_px=52, cardigan_underlap_px=34)
    cuts = {
        "openPants": open_pants,
        "cardiganInnerBoundary": inner,
        "hands": hands_poly,
        "sourceShoesFromRow": 2030,
        "sourcePantsFullFromRow": 1350,
        "sourcePantsToRow": 2065,
        "sourceVisibleNeckPolygon": neck_visible,
    }
    return pieces, white, projection, edge_treatment, cuts


def build_nova(home):
    source, white, mapped, projection = load_character_layers(
        home,
        {"footwear", "legwear", "bottomwear", "topwear", "handwear-r", "handwear-l", "neck"},
        hair_max_y=640,
    )
    shoes = source.copy()
    shoes[:2000, :, 3] = 0

    hand_l_poly = [(205, 1180), (255, 1180), (255, 1345), (205, 1345)]
    hand_r_poly = [(350, 865), (465, 865), (520, 915), (520, 975), (350, 975)]
    hands_mask = polygon(hand_l_poly) | polygon(hand_r_poly)

    cardigan_r_poly = polygon([
        (450, 560), (575, 560), (575, 1140), (450, 1140),
    ])

    open_pants = [
        (288, 960), (460, 960), (588, 1135), (588, 2035), (190, 2035),
        (190, 1345), (250, 1345), (250, 1180), (273, 1160), (278, 1120), (280, 1080), (284, 1040), (288, 1000),
    ]
    pants_vis = polygon(open_pants) & (~hands_mask) & (~cardigan_r_poly)
    pants = np.zeros((H, W, 4), dtype=np.uint8)
    take_src = pants_vis & (source[:, :, 3] > 8)
    pants[take_src] = source[take_src]
    pants_occluded = polygon(open_pants) & (hands_mask | cardigan_r_poly) & (source[:, :, 3] > 128)
    fill_occluded_from_nearest(pants, take_src, pants_occluded)
    pants[2035:, :, 3] = 0

    neck_visible = [(415, 455), (510, 455), (510, 565), (415, 565)]
    neck = blend_visible_neck(mapped["neck"], source, neck_visible, min_r=150, min_diff=45)

    inner = [
        (260, 552), (515, 552), (535, 760), (452, 875),
        (452, 968), (294, 968), (298, 875), (282, 750),
    ]
    inside = polygon(inner)

    sleeve_l_poly = polygon([
        (200, 620), (305, 620), (305, 880), (294, 965), (288, 1000), (284, 1040),
        (280, 1080), (278, 1120), (273, 1160), (266, 1185), (200, 1185),
    ]) & (~inside) & (~pants_vis)
    sleeve_r_poly = polygon([(505, 560), (700, 560), (700, 965), (515, 965)]) & (~inside)
    sleeves_mask = (sleeve_l_poly | sleeve_r_poly) & (~hands_mask)

    camisole = np.zeros((H, W, 4), dtype=np.uint8)
    cam_vis = inside & (~hands_mask) & (np.arange(H)[:, None] >= 552) & (source[:, :, 3] > 8)
    camisole[cam_vis] = source[cam_vis]
    fill_occluded_from_nearest(camisole, cam_vis, inside & hands_mask & (source[:, :, 3] > 128))
    for y in range(552, 568):
        fade = (y - 552) / 16.0
        camisole[y, 355:515, 3] = (camisole[y, 355:515, 3].astype(np.float32) * fade).astype(np.uint8)

    card_mask = cardigan_r_poly & (~inside) & (~sleeves_mask) & (~hands_mask)
    cardigan = np.zeros((H, W, 4), dtype=np.uint8)
    card_vis = card_mask & (np.arange(H)[:, None] >= 565) & (source[:, :, 3] > 8)
    cardigan[card_vis] = source[card_vis]
    fill_occluded_from_nearest(cardigan, card_vis, card_mask & hands_mask & (source[:, :, 3] > 128))

    sleeves = np.zeros((H, W, 4), dtype=np.uint8)
    sl_vis = sleeves_mask & (np.arange(H)[:, None] >= 575) & (source[:, :, 3] > 8)
    sleeves[sl_vis] = source[sl_vis]

    hands = np.zeros((H, W, 4), dtype=np.uint8)
    hands_src = hands_mask & (source[:, :, 3] > 8)
    hands[hands_src] = source[hands_src]

    pieces = {
        "shoes": shoes,
        "bottomwear": pants,
        "neck": neck,
        "topwear": camisole,
        "cardigan": cardigan,
        "sleeves": sleeves,
        "hands": hands,
    }
    edge_treatment = apply_edge_treatment(pieces, source, upper_to_row=580, band_to_row=1350, topwear_underlap_px=45, cardigan_underlap_px=34)
    cuts = {
        "openPants": open_pants,
        "cardiganInnerBoundary": inner,
        "leftHand": hand_l_poly,
        "rightHand": hand_r_poly,
        "sourceShoesFromRow": 2000,
        "sourcePantsFullFromRow": 1150,
        "sourcePantsToRow": 2035,
        "sourceVisibleNeckPolygon": neck_visible,
    }
    return pieces, white, projection, edge_treatment, cuts


BUILDERS = {
    "roa": build_roa,
    "luna": build_luna,
    "jinni": build_jinni,
    "naru": build_naru,
    "nova": build_nova,
}


def run_character(family, char, candidate_name, force=False):
    home = family / "outfits/swimwear" / char
    out = home / candidate_name
    if out.exists():
        if force:
            shutil.rmtree(out)
        else:
            raise RuntimeError(f"SWIMWEAR_STATIC_FRESH_OUTPUT_REQUIRED: {out}")
    out.mkdir(parents=True)
    (out / "parts").mkdir()
    (home / "docs").mkdir(exist_ok=True)

    pieces, white, projection, edge_treatment, cuts = BUILDERS[char](home)
    part_records = []
    for name, array in pieces.items():
        ys, xs = np.nonzero(array[:, :, 3] > 0)
        if not len(xs):
            raise RuntimeError(f"SWIMWEAR_STATIC_NONEMPTY_PART_REQUIRED {char}:{name}")
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
            "source": (
                "painting:visible-neck+full:neck"
                if name == "neck"
                else "painting:source-sandals"
                if name == "shoes"
                else "full:" + ({"bottomwear": "legwear", "sleeves": "handwear", "hands": "handwear", "cardigan": "topwear"}.get(name, name))
            ),
        })

    baseline = json.loads((family / char / "out/parts.json").read_text())
    common = {r["name"]: r for r in baseline["parts"] if r["name"] not in OFFICE_CLOTHING}

    def accepted(name):
        record = common[name]
        return Image.open(family / char / "out/parts" / (name + ".png")).convert("RGBA"), (record["x"], record["y"])

    canvas = Image.new("RGBA", (W, H))
    im, at = accepted("hair_back")
    canvas.alpha_composite(im, at)
    for name in ["shoes", "bottomwear", "neck", "topwear", "cardigan", "sleeves", "hands"]:
        canvas.alpha_composite(Image.fromarray(pieces[name], "RGBA"))
    for name in common:
        if name == "hair_back":
            continue
        im, at = accepted(name)
        canvas.alpha_composite(im, at)
    canvas.save(out / "assembled.png")
    flat = Image.new("RGBA", (W, H), "white")
    flat.alpha_composite(canvas)
    flat.convert("RGB").save(out / "assembled-white.png")

    contact = Image.new("RGB", (840, 1220), "#dddddd")
    draw = ImageDraw.Draw(contact)
    for i, (im_panel, label_text) in enumerate([
        (Image.fromarray(white, "RGBA"), "Registered clothing source (new head)"),
        (flat, "Flat prototype (accepted face/hair)"),
    ]):
        contact.paste(im_panel.convert("RGB").resize((400, 1142), Image.Resampling.LANCZOS), (10 + i * 420, 35))
        draw.text((10 + i * 420, 12), label_text, fill="black")
    draw.text((10, 1190), "First flat composition only: no rig, build/check or motion acceptance. Visible source projected; hidden model art retained.", fill="black")
    contact_path = home / "docs" / (candidate_name + "-contact.png")
    contact.save(contact_path)

    metadata = {
        "spec": "family-swimwear-static-prototype/1",
        "character": char,
        "status": "STATIC_REVIEW_ONLY",
        "parts": part_records,
        "projection": projection,
        "projectionPolicy": {
            "source": "Existing family/parts projection constants",
            "coreAlpha": 250,
            "kernel": 5,
            "driftLimit": 90,
            "sigma": 1,
        },
        "geometry": {
            "inputSquare": [2284, 2284],
            "padLeft": 742,
            "runSquare": [1024, 1024],
            "output": [800, 2284],
            "resample": "Pillow BICUBIC; no claim of byte parity with public OpenCV-equivalent helper",
        },
        "edgeTreatment": edge_treatment,
        "cuts": cuts,
        "commonHead": "Existing accepted parts copied in the same canvas; generated head/hair are never adopted.",
        "limitations": [
            "This is an early flat source/occlusion review, not a mesh or runtime result.",
            "Cut boundary fit and source projection omissions still require visual review; no hidden pixel was painted by a heuristic.",
        ],
    }
    (out / "prototype.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return {"character": char, "status": "STATIC_REVIEW_READY", "contact": str(contact_path), "parts": len(part_records)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--characters", nargs="*", default=["roa", "luna", "jinni", "naru", "nova"])
    parser.add_argument("--candidate", default="prepared")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    family = pathlib.Path(__file__).resolve().parents[1]
    results = [run_character(family, c, args.candidate, force=args.force) for c in args.characters]
    print(json.dumps({"results": results}, indent=2))


if __name__ == "__main__":
    main()
