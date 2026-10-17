#!/usr/bin/env python3
"""Static 7-part clothing decomposition for the remaining 4 Family homewear characters.

Uses each character's full-pass See-through v3 masks, registered 4x upscaled
clothing source, explicit garment boundary polygons, and accepted office head
parts. Emits no rig/Spine data into prepared/.
"""
import argparse
import json
import os
import pathlib
os.environ.update(OMP_NUM_THREADS="4", OPENBLAS_NUM_THREADS="4", MKL_NUM_THREADS="4")
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import binary_closing, binary_dilation, binary_erosion, binary_fill_holes, gaussian_filter, label, distance_transform_edt

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


def load_character_layers(home, wanted, hair_max_y):
    raw = home / "inputs/layers/full_orig"
    source = np.array(Image.open(home / "inputs/upscale-run/registered-upscaled.png").convert("RGBA"))
    white = np.array(Image.open(home / "inputs/painting-clothing-source.png").convert("RGBA"))
    manifest = json.loads((raw / "layers.json").read_text())
    if [manifest["width"], manifest["height"]] != [1024, 1024]:
        raise RuntimeError("HOMEWEAR_STATIC_FULL_FRAME_REQUIRED")
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
        e = next(e for e in entries if e["name"] == hname)
        im = Image.open(raw / "parts" / (hname + ".png")).convert("RGBA")
        c1024 = Image.new("RGBA", (1024, 1024))
        c1024.alpha_composite(im, (e["left"], e["top"]))
        a800 = np.array(c1024.resize((2284, 2284), Image.Resampling.BICUBIC).crop((742, 0, 1542, 2284)))[:, :, 3]
        hair_st |= (a800 > 24)
    hair_st[hair_max_y:, :] = False

    projection = {}
    for name, array in mapped.items():
        i = next(i for i, e in enumerate(entries) if e["name"] == name)
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

    cloth_names = ["topwear", "cardigan", "sleeves", "hands"]
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
    from scipy.ndimage import binary_dilation
    four_conn = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=bool)

    def clean_mesh_islands():
        for name in order:
            arr = pieces[name]
            arr[arr[:, :, 3] <= 8, 3] = 0
            comp, n_comp = label(arr[:, :, 3] > 8, four_conn)
            if n_comp > 1:
                counts = np.bincount(comp.ravel())
                counts[0] = 0
                min_sz = 500 if name in ["neck", "topwear", "cardigan", "sleeves"] else 200
                small = (counts < min_sz) & (counts > 0)
                small_mask = small[comp]
                if small_mask.any():
                    arr[small_mask, 3] = 0

    # 1. Remove alpha <= 8 noise and stray islands from all parts before computing underlap
    clean_mesh_islands()

    # 2. Add underlap on lower layers strictly under fully-opaque (alpha == 255) pixels of higher layers,
    # extrapolating RGB from the nearest interior pixel of the lower layer so bilinear sampling and bust jiggle have zero gap.
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

    # 3. Clean any tiny 4-connected islands created by non-contiguous upper_opaque pockets
    clean_mesh_islands()

    return edge_treatment


def build_roa(home):
    source, white, mapped, projection = load_character_layers(
        home,
        {"footwear", "legwear", "bottomwear", "topwear", "handwear-l", "handwear-r", "neck", "objects"},
        hair_max_y=515,
    )
    shoes = source.copy()
    shoes[:2080, :, 3] = 0

    legs = mapped["legwear"].copy()
    shorts = mapped["bottomwear"].copy()
    pants_canvas = Image.fromarray(legs, "RGBA")
    pants_canvas.alpha_composite(Image.fromarray(shorts, "RGBA"))
    pants = np.array(pants_canvas)
    open_pants = [
        (264, 922), (370, 936), (488, 916),
        (505, 1000), (522, 1080), (538, 1160), (548, 1235),
        (240, 1235), (244, 1160), (250, 1080), (256, 1000),
    ]
    pants_vis = polygon(open_pants)
    pants_vis[1215:2140, 140:560] = True
    pants_vis[2140:, :] = False
    take_src = pants_vis & (source[:, :, 3] > 128)
    pants[take_src] = source[take_src]
    pants[2140:, :, 3] = 0

    neck_visible = [(302, 370), (362, 405), (350, 444), (375, 476), (290, 476), (304, 438)]
    source_is_skin = (source[:, :, 0].astype(int) > 140) & ((source[:, :, 0].astype(int) - source[:, :, 2].astype(int)) > 45)
    neck_vis_mask = binary_erosion(polygon(neck_visible) & source_is_skin, np.ones((3, 3), bool))
    neck = mapped["neck"].copy()
    neck[:410, :285, 3] = 0
    w_neck = gaussian_filter(neck_vis_mask.astype(np.float32), sigma=2.0) * (neck[:, :, 3] > 0)
    neck[:, :, :3] = np.clip(
        w_neck[:, :, None] * source[:, :, :3] + (1.0 - w_neck[:, :, None]) * neck[:, :, :3],
        0,
        255,
    ).astype(np.uint8)

    top = mapped["topwear"].copy()
    top_cut_pants = polygon([
        (264, 934), (370, 946), (488, 924),
        (505, 1000), (522, 1080), (538, 1160), (550, 1245), (545, 1330),
        (240, 1330), (242, 1200), (250, 1080), (256, 1000),
    ])
    top[top_cut_pants, 3] = 0
    top[(neck[:, :, 3] > 200) & polygon([(285, 350), (395, 350), (395, 450), (285, 450)]), 3] = 0
    for y in range(450, 468):
        fade = (y - 450) / 18.0
        mask_row = neck[y, 285:395, 3] > 200
        top[y, 285:395, 3][mask_row] = (top[y, 285:395, 3][mask_row].astype(np.float32) * fade).astype(np.uint8)

    mug_top_poly = [
        (404, 668), (424, 650), (465, 642), (504, 644), (512, 660),
        (508, 688), (530, 686), (536, 706), (522, 730), (504, 744),
        (504, 758), (485, 764), (436, 764), (424, 748),
    ]
    is_purple_cam = (source[:, :, 2].astype(int) - source[:, :, 0].astype(int)) > 6
    is_handle_card_gap = (
        (np.arange(W)[None, :] >= 502)
        & ((source[:, :, 0].astype(int) - source[:, :, 2].astype(int)) < 16)
        & (source[:, :, 0].astype(int) < 185)
    )
    mug_top_mask = binary_closing(
        polygon(mug_top_poly) & (~is_purple_cam) & (~is_handle_card_gap) & (source[:, :, 3] > 128),
        np.ones((3, 3), dtype=bool),
    )
    mug_erase_mask = binary_dilation(polygon(mug_top_poly), np.ones((7, 7), dtype=bool))

    r_hand_poly = [(50, 955), (175, 955), (175, 1015), (156, 1080), (158, 1140), (180, 1180), (204, 1215), (204, 1365), (50, 1365)]
    r_hand_mask = polygon(r_hand_poly)
    l_hand_poly = [
        (488, 642), (496, 608), (512, 576), (534, 545), (562, 530),
        (610, 522), (652, 522), (682, 540), (688, 576), (680, 608),
        (650, 618), (605, 612), (580, 604), (576, 625), (568, 660),
        (556, 692), (530, 706), (490, 708),
    ]
    is_sleeve_cuff = (np.arange(W)[None, :] > 580) & (np.arange(H)[:, None] > 596) & ((source[:, :, 0].astype(int) - source[:, :, 2].astype(int)) < 22)
    l_hand_mask = binary_closing(polygon(l_hand_poly) & (~is_sleeve_cuff) & (~is_purple_cam), np.ones((3, 3), dtype=bool))

    inner = [
        (254, 448), (372, 448), (402, 488), (434, 540), (464, 592), (482, 635), (484, 656),
        (468, 760), (476, 850), (488, 932), (370, 948), (262, 938),
        (268, 840), (272, 700), (262, 575), (250, 500),
    ]
    inside = polygon(inner)
    camisole = top.copy()
    camisole[~inside, 3] = 0
    cardigan = top.copy()
    cardigan[inside, 3] = 0
    # Cut raised left sleeve out of cardigan body so sleeves owns x>=530, y=495..680 cleanly
    raised_sleeve_zone = polygon([(526, 490), (710, 490), (710, 680), (530, 680), (526, 555)])
    cardigan[raised_sleeve_zone, 3] = 0

    # Erase mug and left hand from camisole (topwear) and cardigan, inpainting with clean cloth pixels
    fg_occ = mug_erase_mask | binary_dilation(l_hand_mask, np.ones((5, 5), dtype=bool))
    cam_occ = inside & fg_occ & ((camisole[:, :, 3] > 8) | (source[:, :, 3] > 128))
    cam_valid = (
        inside
        & (~fg_occ)
        & (camisole[:, :, 3] > 220)
        & ((camisole[:, :, 2].astype(int) - camisole[:, :, 0].astype(int)) > 6)
        & (camisole[:, :, 2].astype(int) > 55)
    )
    cam_interior = binary_erosion(cam_valid, np.ones((9, 9), dtype=bool))
    if cam_occ.any() and cam_interior.any():
        _, near_cam = distance_transform_edt(~cam_interior, return_indices=True)
        full_cam = camisole[near_cam[0], near_cam[1], :3].astype(np.float32)
        for ch in range(3):
            full_cam[:, :, ch] = gaussian_filter(full_cam[:, :, ch], sigma=4.0)
        camisole[cam_occ, :3] = np.clip(full_cam[cam_occ], 0, 255).astype(np.uint8)
        camisole[cam_occ, 3] = 255

    card_body_zone = polygon([(465, 540), (528, 540), (532, 780), (465, 780)]) & (~inside) & (~raised_sleeve_zone)
    cardigan[(~inside) & fg_occ, 3] = 0
    card_occ = card_body_zone & fg_occ & (source[:, :, 3] > 128)
    card_valid = (
        (~inside)
        & (~raised_sleeve_zone)
        & (~fg_occ)
        & (cardigan[:, :, 3] > 220)
        & (cardigan[:, :, 0].astype(int) > 130)
        & ((cardigan[:, :, 0].astype(int) - cardigan[:, :, 2].astype(int)) < 25)
    )
    card_interior = binary_erosion(card_valid, np.ones((7, 7), dtype=bool))
    if card_occ.any() and card_interior.any():
        _, near_card = distance_transform_edt(~card_interior, return_indices=True)
        full_card = cardigan[near_card[0], near_card[1], :3].astype(np.float32)
        for ch in range(3):
            full_card[:, :, ch] = gaussian_filter(full_card[:, :, ch], sigma=4.5)
        cardigan[card_occ, :3] = np.clip(full_card[card_occ], 0, 255).astype(np.uint8)
        cardigan[card_occ, 3] = 255

    hw_r = mapped["handwear-r"].copy()
    obj = mapped["objects"].copy()
    hw_l = mapped["handwear-l"].copy()
    hw_l[inside, 3] = 0
    hw_l[(cardigan[:, :, 3] > 220) & polygon([(400, 440), (532, 440), (532, 660), (400, 660)]), 3] = 0
    hw_l[polygon([(400, 440), (650, 440), (650, 492), (400, 492)]), 3] = 0
    hw_l[535:, :580, 3] = 0

    sleeves_c = Image.new("RGBA", (W, H))
    sl_r = hw_r.copy()
    sl_r[r_hand_mask, 3] = 0
    sl_r[962:, :, 3] = 0
    sl_l = hw_l.copy()
    # Give raised sleeve zone from source/top to sl_l so the lower sleeve cuff is in sleeves, not cardigan
    take_sleeve_src = raised_sleeve_zone & (~l_hand_mask) & (~mug_erase_mask) & (source[:, :, 3] > 8) & (np.arange(H)[:, None] <= 635)
    sl_l[take_sleeve_src] = source[take_sleeve_src]
    sl_l[l_hand_mask | mug_erase_mask, 3] = 0
    sleeves_c.alpha_composite(Image.fromarray(sl_r, "RGBA"))
    sleeves_c.alpha_composite(Image.fromarray(sl_l, "RGBA"))
    sleeves = np.array(sleeves_c)

    hands_c = Image.new("RGBA", (W, H))
    hd_r = hw_r.copy()
    hd_r[~r_hand_mask, 3] = 0
    obj_clean = obj.copy()
    obj_clean[:740, :, 3] = 0
    hands_c.alpha_composite(Image.fromarray(obj_clean, "RGBA"))
    hands_c.alpha_composite(Image.fromarray(hd_r, "RGBA"))
    hands = np.array(hands_c)
    hands[mug_top_mask] = source[mug_top_mask]
    l_hand_src = l_hand_mask & (source[:, :, 3] > 128)
    hands[l_hand_src] = source[l_hand_src]
    r_hand_src = r_hand_mask & (source[:, :, 3] > 128)
    hands[r_hand_src] = source[r_hand_src]

    pieces = {
        "shoes": shoes,
        "bottomwear": pants,
        "neck": neck,
        "topwear": camisole,
        "cardigan": cardigan,
        "sleeves": sleeves,
        "hands": hands,
    }
    edge_treatment = apply_edge_treatment(pieces, source, upper_to_row=500, band_to_row=1370, topwear_underlap_px=52, cardigan_underlap_px=34)
    cuts = {
        "openPants": open_pants,
        "cardiganInnerBoundary": inner,
        "rightHand": r_hand_poly,
        "leftHand": l_hand_poly,
        "upperMug": mug_top_poly,
        "sourceShoesFromRow": 2080,
        "sourcePantsFullFromRow": 1215,
        "sourcePantsToRow": 2090,
        "sourceVisibleNeckPolygon": neck_visible,
    }
    return pieces, white, projection, edge_treatment, cuts


def build_luna(home):
    source, white, mapped, projection = load_character_layers(
        home,
        {"footwear", "legwear", "topwear", "handwear-l", "handwear-r", "neck"},
        hair_max_y=640,
    )
    shoes = source.copy()
    shoes[:2090, :, 3] = 0

    hands_poly = [
        (242, 1230), (296, 1212), (300, 1192), (366, 1182), (380, 1222),
        (406, 1222), (425, 1176), (488, 1190), (488, 1230), (535, 1255),
        (540, 1298), (508, 1334), (465, 1326), (392, 1300), (388, 1344),
        (332, 1344), (305, 1322), (255, 1330), (238, 1288),
    ]
    hands_mask = polygon(hands_poly)

    pants = mapped["legwear"].copy()
    open_pants = [(336, 1018), (458, 1018), (454, 1220), (340, 1220)]
    pants_vis = polygon(open_pants)
    pants_vis[1235:2130, 160:620] = True
    pants_vis[hands_mask] = False
    take_src = pants_vis & (source[:, :, 3] > 128)
    pants[take_src] = source[take_src]
    mask_remnant = hands_mask & (pants[:, :, 3] > 128) & (pants[:, :, 0] > 95)
    pants[mask_remnant, :3] = [48, 47, 58]
    pants[2130:, :, 3] = 0

    neck_visible = [(315, 505), (398, 505), (398, 595), (315, 595)]
    source_is_skin = (source[:, :, 0].astype(int) > 150) & ((source[:, :, 0].astype(int) - source[:, :, 2].astype(int)) > 40)
    neck_vis_mask = binary_erosion(polygon(neck_visible) & source_is_skin, np.ones((3, 3), bool))
    neck = mapped["neck"].copy()
    w_neck = gaussian_filter(neck_vis_mask.astype(np.float32), sigma=2.0) * (neck[:, :, 3] > 0)
    neck[:, :, :3] = np.clip(
        w_neck[:, :, None] * source[:, :, :3] + (1.0 - w_neck[:, :, None]) * neck[:, :, :3],
        0,
        255,
    ).astype(np.uint8)

    top = mapped["topwear"].copy()
    top[polygon([(346, 1026), (448, 1026), (442, 1270), (350, 1270)]), 3] = 0
    top[:568, 310:405, 3] = 0
    for y in range(568, 586):
        fade = (y - 568) / 18.0
        top[y, 310:405, 3] = (top[y, 310:405, 3].astype(np.float32) * fade).astype(np.uint8)

    inner = [
        (310, 568), (398, 568), (414, 620), (434, 700), (444, 760),
        (448, 880), (446, 1030), (358, 1030), (368, 880), (366, 755),
        (348, 700), (320, 635),
    ]
    inside = polygon(inner)
    camisole = top.copy()
    camisole[~inside, 3] = 0
    cardigan = top.copy()
    cardigan[inside, 3] = 0

    hw_r = mapped["handwear-r"].copy()
    hw_l = mapped["handwear-l"].copy()
    sleeves_c = Image.new("RGBA", (W, H))
    sl_r = hw_r.copy()
    sl_r[hands_mask, 3] = 0
    sl_r[1225:, :, 3] = 0
    sl_l = hw_l.copy()
    sl_l[hands_mask, 3] = 0
    sl_l[1220:, :, 3] = 0
    sleeves_c.alpha_composite(Image.fromarray(sl_r, "RGBA"))
    sleeves_c.alpha_composite(Image.fromarray(sl_l, "RGBA"))
    sleeves = np.array(sleeves_c)

    hands = np.zeros((H, W, 4), dtype=np.uint8)
    hands_src = hands_mask & (source[:, :, 3] > 128)
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
    edge_treatment = apply_edge_treatment(pieces, source, upper_to_row=610, band_to_row=1245, topwear_underlap_px=58, cardigan_underlap_px=34)
    cuts = {
        "openPants": open_pants,
        "cardiganInnerBoundary": inner,
        "hands": hands_poly,
        "sourceShoesFromRow": 2090,
        "sourcePantsFullFromRow": 1235,
        "sourcePantsToRow": 2105,
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
    shoes[:2105, :, 3] = 0

    hand_r_poly = [(290, 1098), (350, 1090), (405, 1230), (405, 1340), (315, 1340), (290, 1200)]
    hand_l_poly = [(555, 875), (610, 875), (675, 950), (675, 1060), (570, 1060), (565, 945)]
    hands_mask = polygon(hand_r_poly) | polygon(hand_l_poly)

    legs = mapped["legwear"].copy()
    shorts = mapped["bottomwear"].copy()
    shorts_keep = polygon([
        (335, 1015), (595, 1015), (618, 1258), (455, 1300), (288, 1265), (305, 1120),
    ])
    shorts[~shorts_keep, 3] = 0
    pants_c = Image.fromarray(legs, "RGBA")
    pants_c.alpha_composite(Image.fromarray(shorts, "RGBA"))
    pants = np.array(pants_c)

    robe_center_tail = polygon([(395, 1285), (460, 1285), (465, 1505), (382, 1510)])
    robe_left_tail = polygon([(140, 1100), (332, 1100), (328, 1605), (140, 1605)])
    robe_right_tail = polygon([(575, 1015), (665, 1015), (665, 1605), (518, 1605), (542, 1275), (602, 1255)])

    open_pants = [
        (348, 1020), (595, 1010), (615, 1255), (555, 1285), (560, 1600), (560, 2140),
        (170, 2140), (170, 1600), (305, 1550), (330, 1275),
    ]
    pants_vis = polygon(open_pants)
    pants_vis[hands_mask | robe_center_tail | robe_left_tail | robe_right_tail] = False
    take_src = pants_vis & (source[:, :, 3] > 128)
    pants[take_src] = source[take_src]
    pants[2140:, :, 3] = 0

    neck_visible = [(322, 470), (410, 470), (410, 565), (322, 565)]
    source_is_skin = (source[:, :, 0].astype(int) > 135) & ((source[:, :, 0].astype(int) - source[:, :, 2].astype(int)) > 35)
    neck_vis_mask = binary_erosion(polygon(neck_visible) & source_is_skin, np.ones((3, 3), bool))
    neck = mapped["neck"].copy()
    w_neck = gaussian_filter(neck_vis_mask.astype(np.float32), sigma=2.0) * (neck[:, :, 3] > 0)
    neck[:, :, :3] = np.clip(
        w_neck[:, :, None] * source[:, :, :3] + (1.0 - w_neck[:, :, None]) * neck[:, :, :3],
        0,
        255,
    ).astype(np.uint8)

    top = mapped["topwear"].copy()
    camisole_vis_poly = polygon([
        (235, 558), (410, 558), (508, 635), (588, 680), (598, 760),
        (560, 860), (585, 1035), (465, 1055), (355, 1055),
        (345, 860), (318, 720), (255, 650),
    ])
    camisole_src_mask = camisole_vis_poly & (source[:, :, 3] > 128) & (~polygon([(265, 535), (350, 535), (350, 582), (265, 582)]))
    top[camisole_src_mask] = source[camisole_src_mask]

    top_cut_shorts = polygon([
        (352, 1045), (582, 1020), (602, 1255), (542, 1278),
        (518, 1620), (462, 1620), (458, 1290), (398, 1290),
        (380, 1620), (328, 1620), (332, 1275),
    ])
    top[top_cut_shorts, 3] = 0
    top[:548, 315:420, 3] = 0
    for y in range(548, 566):
        fade = (y - 548) / 18.0
        top[y, 315:420, 3] = (top[y, 315:420, 3].astype(np.float32) * fade).astype(np.uint8)

    inner = [
        (230, 548), (445, 548), (510, 635), (592, 680), (602, 760),
        (568, 860), (585, 1042), (352, 1055), (345, 860), (318, 720), (255, 645),
    ]
    inside = polygon(inner)
    camisole = top.copy()
    camisole[~inside, 3] = 0
    cardigan = top.copy()
    cardigan[inside, 3] = 0
    robe_vis = (robe_left_tail | robe_right_tail | robe_center_tail) & (~hands_mask) & (source[:, :, 3] > 128)
    cardigan[robe_vis] = source[robe_vis]

    hw_r = mapped["handwear-r"].copy()
    hw_l = mapped["handwear-l"].copy()
    sleeves_c = Image.new("RGBA", (W, H))
    sl_r = hw_r.copy()
    sl_r[hands_mask, 3] = 0
    sl_r[1125:, :, 3] = 0
    sl_r[inside, 3] = 0
    sl_l = hw_l.copy()
    sl_l[hands_mask, 3] = 0
    sl_l[:, 568:, 3] = 0
    sl_l[inside, 3] = 0
    sleeves_c.alpha_composite(Image.fromarray(sl_r, "RGBA"))
    sleeves_c.alpha_composite(Image.fromarray(sl_l, "RGBA"))
    sleeves = np.array(sleeves_c)

    hands = np.zeros((H, W, 4), dtype=np.uint8)
    hands_src = hands_mask & (source[:, :, 3] > 128)
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
    edge_treatment = apply_edge_treatment(pieces, source, upper_to_row=590, band_to_row=1590, topwear_underlap_px=45, cardigan_underlap_px=34)
    cuts = {
        "openPants": open_pants,
        "cardiganInnerBoundary": inner,
        "rightHand": hand_r_poly,
        "leftHand": hand_l_poly,
        "sourceShoesFromRow": 2105,
        "sourcePantsFullFromRow": 1255,
        "sourcePantsToRow": 2110,
        "sourceVisibleNeckPolygon": neck_visible,
    }
    return pieces, white, projection, edge_treatment, cuts


def build_nova(home):
    source, white, mapped, projection = load_character_layers(
        home,
        {"footwear", "legwear", "bottomwear", "topwear", "handwear-r", "neck", "neckwear"},
        hair_max_y=640,
    )
    shoes = source.copy()
    shoes[:2085, :, 3] = 0

    hand_l_poly = [(185, 1210), (235, 1225), (235, 1360), (185, 1360)]
    hand_r_poly = [(332, 902), (410, 902), (504, 946), (508, 995), (435, 1005), (370, 1022), (332, 995)]
    hands_mask = polygon(hand_l_poly) | polygon(hand_r_poly)

    legs = mapped["legwear"].copy()
    shorts = mapped["bottomwear"].copy()
    pants_c = Image.fromarray(legs, "RGBA")
    pants_c.alpha_composite(Image.fromarray(shorts, "RGBA"))
    pants = np.array(pants_c)

    cardigan_r_poly = polygon([
        (485, 538), (650, 538), (650, 1442), (470, 1442),
        (462, 1260), (446, 1050), (432, 950), (432, 850), (440, 740), (468, 620),
    ])
    cardigan_l_lapel_poly = polygon([
        (255, 538), (425, 538), (320, 680), (255, 695),
    ])

    open_pants = [
        (265, 960), (438, 975), (470, 1285), (234, 1265), (255, 1140),
    ]
    pants_vis = polygon(open_pants)
    pants_vis[1255:2130, 170:540] = True
    pants_vis[hands_mask | cardigan_r_poly] = False
    take_src = pants_vis & (source[:, :, 3] > 128)
    pants[take_src] = source[take_src]
    pants[2130:, :, 3] = 0

    neck_c = Image.fromarray(mapped["neck"], "RGBA")
    if "neckwear" in mapped:
        neck_c.alpha_composite(Image.fromarray(mapped["neckwear"], "RGBA"))
    neck = np.array(neck_c)
    neck_visible = [(415, 455), (510, 455), (510, 565), (415, 565)]
    source_is_skin = (source[:, :, 0].astype(int) > 150) & ((source[:, :, 0].astype(int) - source[:, :, 2].astype(int)) > 45)
    neck_vis_mask = binary_erosion(polygon(neck_visible) & source_is_skin, np.ones((3, 3), bool))
    w_neck = gaussian_filter(neck_vis_mask.astype(np.float32), sigma=2.0) * (neck[:, :, 3] > 0)
    neck[:, :, :3] = np.clip(
        w_neck[:, :, None] * source[:, :, :3] + (1.0 - w_neck[:, :, None]) * neck[:, :, :3],
        0,
        255,
    ).astype(np.uint8)

    top = mapped["topwear"].copy()
    top[:538, 395:505, 3] = 0
    for y in range(538, 556):
        fade = (y - 538) / 18.0
        top[y, 395:505, 3] = (top[y, 395:505, 3].astype(np.float32) * fade).astype(np.uint8)

    inner = [
        (320, 538), (488, 538), (470, 620), (442, 740),
        (434, 860), (434, 976), (288, 972), (288, 860), (240, 790), (240, 710), (295, 645),
    ]
    inside = polygon(inner)
    camisole = top.copy()
    camisole[~inside, 3] = 0
    bra_vis = inside & (~hands_mask) & (np.arange(H)[:, None] >= 625) & (source[:, :, 3] > 128)
    camisole[bra_vis] = source[bra_vis]
    midriff_hand = inside & hands_mask & (camisole[:, :, 3] > 128) & (np.arange(H)[:, None] < 968)
    camisole[midriff_hand, :3] = [235, 138, 118]

    sleeve_l_poly = polygon([
        (160, 620), (282, 780), (300, 962), (240, 1250), (160, 1230),
    ])
    sleeve_r_poly = polygon([
        (500, 580), (720, 580), (720, 1130), (560, 1130), (465, 960), (505, 920),
    ])

    cardigan = top.copy()
    cardigan_keep = (cardigan_r_poly | cardigan_l_lapel_poly) & (~inside)
    cardigan[~cardigan_keep, 3] = 0
    card_r_vis = cardigan_r_poly & (~sleeve_r_poly) & (~hands_mask) & (np.arange(H)[:, None] >= 640) & (source[:, :, 3] > 128)
    cardigan[card_r_vis] = source[card_r_vis]

    hw = mapped["handwear-r"].copy()
    sleeves = hw.copy()
    sleeves[~(sleeve_l_poly | sleeve_r_poly), 3] = 0
    sleeves[hands_mask | inside, 3] = 0
    sleeve_l_vis = sleeve_l_poly & (~hands_mask) & (~inside) & (source[:, :, 3] > 128)
    sleeve_r_vis = sleeve_r_poly & (~hands_mask) & (np.arange(H)[:, None] >= 660) & (source[:, :, 3] > 128)
    sleeves[sleeve_l_vis] = source[sleeve_l_vis]
    sleeves[sleeve_r_vis] = source[sleeve_r_vis]

    hands = np.zeros((H, W, 4), dtype=np.uint8)
    hands_src = hands_mask & (source[:, :, 3] > 128)
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
    edge_treatment = apply_edge_treatment(pieces, source, upper_to_row=580, band_to_row=1435, topwear_underlap_px=45, cardigan_underlap_px=34)
    cuts = {
        "openPants": open_pants,
        "cardiganInnerBoundary": inner,
        "leftHand": hand_l_poly,
        "rightHand": hand_r_poly,
        "sourceShoesFromRow": 2085,
        "sourcePantsFullFromRow": 1255,
        "sourcePantsToRow": 2090,
        "sourceVisibleNeckPolygon": neck_visible,
    }
    return pieces, white, projection, edge_treatment, cuts


BUILDERS = {
    "roa": build_roa,
    "luna": build_luna,
    "jinni": build_jinni,
    "nova": build_nova,
}


def run_character(family, char, candidate_name, force=False):
    home = family / "outfits/homewear" / char
    out = home / candidate_name
    if out.exists():
        if force:
            import shutil
            shutil.rmtree(out)
        else:
            raise RuntimeError(f"HOMEWEAR_STATIC_FRESH_OUTPUT_REQUIRED: {out}")
    out.mkdir(parents=True)
    (out / "parts").mkdir()
    (home / "docs").mkdir(exist_ok=True)

    pieces, white, projection, edge_treatment, cuts = BUILDERS[char](home)
    part_records = []
    for name, array in pieces.items():
        ys, xs = np.nonzero(array[:, :, 3] > 0)
        if not len(xs):
            raise RuntimeError("HOMEWEAR_STATIC_NONEMPTY_PART_REQUIRED " + name)
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
                else "painting:source-slippers"
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
        "spec": "family-homewear-static-prototype/1",
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
    parser.add_argument("--characters", nargs="*", default=["roa", "luna", "jinni", "nova"])
    parser.add_argument("--candidate", default="prepared")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    family = pathlib.Path(__file__).resolve().parents[1]
    results = [run_character(family, c, args.candidate, force=args.force) for c in args.characters]
    print(json.dumps({"results": results}, indent=2))


if __name__ == "__main__":
    main()
