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


def apply_edge_treatment(pieces, source, upper_to_row, band_to_row):
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

    struct = np.ones((9, 9), dtype=bool)
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
        _, nearest_idx = distance_transform_edt(~uncovered, return_indices=True)
        underlap = binary_dilation(uncovered, struct) & upper_opaque & (pieces[name][:, :, 3] <= 8)
        pieces[name][underlap, :3] = pieces[name][nearest_idx[0][underlap], nearest_idx[1][underlap], :3]
        pieces[name][underlap, 3] = 255

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
    l_hand_poly = [(470, 540), (730, 540), (730, 610), (560, 620), (548, 725), (470, 725)]
    hands_mask = polygon(r_hand_poly) | polygon(l_hand_poly)

    inner = [
        (215, 430), (405, 430), (455, 515), (490, 650),
        (485, 760), (505, 860), (528, 955), (382, 1105), (200, 955),
        (230, 840), (236, 720), (225, 570),
    ]
    inside = polygon(inner)

    outer_robe_l = polygon([(15, 950), (202, 950), (265, 1450), (265, 1615), (15, 1615)])
    outer_robe_r = polygon([(532, 950), (710, 950), (710, 1615), (545, 1615)])
    robe_left_tail = polygon([(15, 435), (235, 435), (205, 955), (275, 1480), (275, 1615), (15, 1615)]) & (~inside)
    robe_right_tail = polygon([(415, 435), (710, 435), (710, 1615), (545, 1615), (500, 955)]) & (~inside)
    r_forearm_poly = polygon([(90, 910), (190, 910), (190, 1085), (90, 1085)])

    open_pants = [
        (195, 950), (382, 1095), (535, 950), (555, 1460), (495, 2035), (235, 2035), (195, 1300),
    ]
    pants_vis = polygon(open_pants) & (~hands_mask) & (~outer_robe_l) & (~outer_robe_r)
    pants = np.zeros((H, W, 4), dtype=np.uint8)
    take_src = pants_vis & (source[:, :, 3] > 8)
    pants[take_src] = source[take_src]
    # Fill occluded leg area under robe/hands from nearest visible leg skin
    pants_occluded = polygon(open_pants) & (~take_src) & (source[:, :, 3] > 128)
    fill_occluded_from_nearest(pants, take_src, pants_occluded)
    pants[2035:, :, 3] = 0

    neck_visible = [(302, 370), (362, 405), (350, 444), (375, 476), (290, 476), (304, 438)]
    neck = blend_visible_neck(mapped["neck"], source, neck_visible, min_r=140, min_diff=45)
    neck[:410, :285, 3] = 0

    camisole = np.zeros((H, W, 4), dtype=np.uint8)
    cam_vis = inside & (~hands_mask) & (np.arange(H)[:, None] >= 440) & (source[:, :, 3] > 8)
    camisole[cam_vis] = source[cam_vis]
    for y in range(440, 458):
        fade = (y - 440) / 18.0
        mask_row = neck[y, 285:395, 3] > 200
        camisole[y, 285:395, 3][mask_row] = (camisole[y, 285:395, 3][mask_row].astype(np.float32) * fade).astype(np.uint8)
    fill_occluded_from_nearest(camisole, cam_vis, inside & hands_mask & (source[:, :, 3] > 128))

    sleeve_upper_l = polygon([(15, 450), (150, 450), (150, 915), (15, 915)])
    sleeve_upper_r = polygon([(555, 500), (730, 500), (730, 790), (555, 790)])
    sleeves_mask = (r_forearm_poly | sleeve_upper_l | sleeve_upper_r) & (~hands_mask) & (~inside)

    card_mask = (robe_left_tail | robe_right_tail | outer_robe_l | outer_robe_r) & (~sleeves_mask) & (~hands_mask) & (~pants_vis)
    cardigan = np.zeros((H, W, 4), dtype=np.uint8)
    card_vis = card_mask & (np.arange(H)[:, None] >= 445) & (source[:, :, 3] > 8)
    cardigan[card_vis] = source[card_vis]
    fill_occluded_from_nearest(cardigan, card_vis, card_mask & hands_mask & (source[:, :, 3] > 128))

    sleeves = np.zeros((H, W, 4), dtype=np.uint8)
    sl_vis = sleeves_mask & (np.arange(H)[:, None] >= 450) & (source[:, :, 3] > 8)
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
    edge_treatment = apply_edge_treatment(pieces, source, upper_to_row=485, band_to_row=1615)
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
        (165, 1020), (585, 1020), (585, 2050), (165, 2050),
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

    top = mapped["topwear"].copy()
    top[:568, :, 3] = 0

    inner = [
        (305, 568), (435, 568), (475, 680), (480, 780),
        (455, 900), (455, 1030), (315, 1030), (315, 900), (285, 760), (295, 650),
    ]
    inside = polygon(inner)
    sleeve_l_poly = polygon([(170, 580), (285, 580), (335, 1135), (210, 1135)]) & (~inside)
    sleeve_r_poly = polygon([(455, 580), (565, 580), (545, 1135), (445, 1135)]) & (~inside)
    sleeves_mask = (sleeve_l_poly | sleeve_r_poly) & (~hands_mask)

    camisole = np.zeros((H, W, 4), dtype=np.uint8)
    cam_vis = inside & (~hands_mask) & (np.arange(H)[:, None] >= 568) & (source[:, :, 3] > 8)
    camisole[cam_vis] = source[cam_vis]
    for y in range(568, 584):
        fade = (y - 568) / 16.0
        camisole[y, 310:405, 3] = (camisole[y, 310:405, 3].astype(np.float32) * fade).astype(np.uint8)

    card_poly = polygon([(230, 568), (515, 568), (525, 1035), (220, 1035)]) & (~inside) & (~sleeves_mask) & (~hands_mask)
    cardigan = np.zeros((H, W, 4), dtype=np.uint8)
    card_vis = card_poly & (np.arange(H)[:, None] >= 568) & (source[:, :, 3] > 8)
    cardigan[card_vis] = source[card_vis]

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
    edge_treatment = apply_edge_treatment(pieces, source, upper_to_row=600, band_to_row=1480)
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
        (535, 880), (545, 935), (335, 935), (335, 860), (315, 720),
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
    edge_treatment = apply_edge_treatment(pieces, source, upper_to_row=585, band_to_row=1460)
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
        (332, 810), (446, 800), (508, 860), (508, 945), (332, 945),
    ]
    hands_mask = polygon(hands_poly)

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
        (295, 620), (505, 620), (512, 760), (505, 1035), (290, 1035), (282, 760),
    ]
    inside = polygon(inner) & (~neck_visible_mask)

    sleeve_r_poly = polygon([(155, 650), (292, 650), (340, 835), (340, 1075), (245, 1075), (155, 1000)]) & (~inside)
    sleeve_l_poly = polygon([(498, 650), (645, 650), (645, 1000), (555, 1075), (465, 1075), (465, 835)]) & (~inside)
    skirt_poly = polygon([(185, 1035), (615, 1035), (625, 1365), (175, 1365)])
    sleeves_mask = (sleeve_r_poly | sleeve_l_poly) & (~skirt_poly) & (~hands_mask)

    # Exclude dark brown hair strands above y=665 on outer shoulders
    is_brown_hair = (np.arange(H)[:, None] < 665) & (source[:, :, 0].astype(int) < 185) & (source[:, :, 2].astype(int) < 110)

    camisole = np.zeros((H, W, 4), dtype=np.uint8)
    cam_vis = inside & (~hands_mask) & (~is_brown_hair) & (np.arange(H)[:, None] >= 620) & (source[:, :, 3] > 8)
    camisole[cam_vis] = source[cam_vis]
    fill_occluded_from_nearest(camisole, cam_vis, inside & (hands_mask | is_brown_hair) & (np.arange(H)[:, None] >= 630) & (source[:, :, 3] > 128))

    card_mask = (skirt_poly | (polygon([(220, 625), (580, 625), (580, 1045), (220, 1045)]) & (~inside))) & (~sleeves_mask) & (~hands_mask) & (~neck_visible_mask)
    cardigan = np.zeros((H, W, 4), dtype=np.uint8)
    card_vis = card_mask & (~is_brown_hair) & (np.arange(H)[:, None] >= 625) & (source[:, :, 3] > 8)
    cardigan[card_vis] = source[card_vis]
    fill_occluded_from_nearest(cardigan, card_vis, card_mask & is_brown_hair & (np.arange(H)[:, None] >= 635) & (source[:, :, 3] > 128))

    sleeves = np.zeros((H, W, 4), dtype=np.uint8)
    sl_vis = sleeves_mask & (~is_brown_hair) & (np.arange(H)[:, None] >= 650) & (source[:, :, 3] > 8)
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
    edge_treatment = apply_edge_treatment(pieces, source, upper_to_row=690, band_to_row=1370)
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
        (294, 965), (455, 965), (565, 1135), (565, 2035), (195, 2035),
        (252, 1345), (266, 1185), (273, 1160), (278, 1120), (280, 1080), (284, 1040), (288, 1000),
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
        (452, 968), (294, 968), (298, 875), (245, 750),
    ]
    inside = polygon(inner)

    sleeve_l_poly = polygon([
        (200, 620), (298, 780), (294, 965), (288, 1000), (284, 1040),
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
    edge_treatment = apply_edge_treatment(pieces, source, upper_to_row=580, band_to_row=1350)
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
