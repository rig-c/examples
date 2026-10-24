#!/usr/bin/env python3
"""Author, merge, stitch, build, and check the 5 Family swimwear outfits.

Generalizes the Family outfit authoring pipeline (author-inputs -> rig-parts rig ->
merge -> neck-seam stitch -> rigc build -> rig-parts check -> protected-check)
for roa, luna, jinni, naru, and nova under family/outfits/swimwear/<char>.
"""
import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess

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
NEW_NAMES = ["shoes", "bottomwear", "neck", "topwear", "sleeves"]

CHAR_SPECS = {
    "roa": {
        "hem_r": {"at": [165, 1100], "tip": [155, 1480]},
        "hem_l": {"at": [575, 1100], "tip": [595, 1480]},
        "neck_segments": [["chest", [365, 430], [365, 657]], ["head", [365, 394], [365, 344]]],
        "topwear_segments": [["chest", [360, 448], [360, 843]], ["hip", [360, 843], [360, 1080]]],
        "cardigan_segments": [
            ["chest", [210, 480], [200, 840]],
            ["chest", [510, 480], [530, 840]],
            ["hip", [200, 840], [165, 1100]],
            ["hip", [530, 840], [575, 1100]],
            "cardigan_hem_r",
            "cardigan_hem_l",
        ],
        "sleeves_segments": [
            ["chest", [120, 520], [120, 940]],
            ["chest", [520, 520], [720, 580]],
        ],
        "stitch": [("neck", 440, True), ("topwear", 485, False)],
    },
    "luna": {
        "hem_r": {"at": [260, 940], "tip": [250, 1030]},
        "hem_l": {"at": [485, 940], "tip": [495, 1030]},
        "neck_segments": [["chest", [370, 565], [368, 790]], ["head", [370, 535], [370, 480]]],
        "topwear_segments": [["chest", [368, 575], [368, 940]], ["hip", [368, 940], [368, 1025]]],
        "cardigan_segments": [
            ["chest", [260, 600], [260, 940]],
            ["chest", [485, 600], [485, 940]],
            "cardigan_hem_r",
            "cardigan_hem_l",
        ],
        "sleeves_segments": [
            ["chest", [200, 650], [520, 1180]],
        ],
        "stitch": [("neck", 575, True), ("topwear", 645, False)],
    },
    "jinni": {
        "hem_r": {"at": [335, 860], "tip": [335, 940]},
        "hem_l": {"at": [535, 860], "tip": [540, 940]},
        "neck_segments": [["chest", [428, 545], [428, 734]], ["head", [428, 500], [428, 410]]],
        "topwear_segments": [["chest", [440, 552], [440, 866]], ["hip", [440, 866], [440, 935]]],
        "cardigan_segments": [
            ["chest", [335, 620], [335, 860]],
            ["chest", [535, 620], [535, 860]],
            "cardigan_hem_r",
            "cardigan_hem_l",
        ],
        "sleeves_segments": [
            ["chest", [230, 640], [520, 1080]],
        ],
        "stitch": [("neck", 555, True), ("topwear", 625, False)],
    },
    "naru": {
        "hem_r": {"at": [255, 1020], "tip": [210, 1200]},
        "hem_l": {"at": [525, 1020], "tip": [565, 1200]},
        "bust_regions": {
            "bust_r": {"cx": 325, "cy": 725, "r": 15, "band": 28},
            "bust_l": {"cx": 445, "cy": 725, "r": 15, "band": 28},
        },
        "neck_segments": [["chest", [380, 650], [380, 780]], ["head", [380, 575], [380, 510]]],
        "topwear_segments": [
            ["chest", [380, 630], [380, 855]],
            ["hip", [275, 925], [495, 925]],
            ["hip", [380, 925], [380, 1020]],
        ],
        "cardigan_segments": [
            ["chest", [265, 640], [255, 855]],
            ["chest", [515, 640], [525, 855]],
            ["hip", [255, 925], [255, 1020]],
            ["hip", [525, 925], [525, 1020]],
            "cardigan_hem_r",
            "cardigan_hem_l",
        ],
        "sleeves_segments": [
            ["chest", [180, 800], [615, 1060]],
        ],
        "stitch": [("neck", 625, True), ("topwear", 705, False)],
    },
    "nova": {
        "hem_r": {"at": [335, 880], "tip": [330, 965]},
        "hem_l": {"at": [495, 880], "tip": [505, 965]},
        "bust_regions": {
            "bust_r": {"cx": 268, "cy": 710, "r": 15, "band": 40},
            "bust_l": {"cx": 418, "cy": 715, "r": 18, "band": 40},
        },
        "neck_segments": [["chest", [435, 550], [410, 780]], ["head", [435, 500], [435, 450]]],
        "topwear_segments": [
            ["chest", [380, 555], [380, 760]],
            ["hip", [380, 885], [380, 965]],
            ["hip", [310, 885], [310, 965]],
            ["hip", [445, 885], [445, 965]],
        ],
        "cardigan_segments": [
            ["chest", [335, 580], [335, 760]],
            ["chest", [495, 580], [495, 760]],
            ["hip", [335, 885], [335, 965]],
            ["hip", [495, 885], [495, 965]],
        ],
        "sleeves_segments": [
            ["chest", [510, 580], [555, 650]],
            ["hip", [645, 900], [355, 965]],
            ["hip", [355, 920], [450, 1010]],
            ["hip", [280, 910], [230, 1300]],
        ],
        "stitch": [("neck", 560, True), ("topwear", 625, False)],
    },
}


def require_file(path: pathlib.Path) -> pathlib.Path:
    if not path.is_file():
        raise RuntimeError(f"FAMILY_INPUT_MISSING: {path}")
    return path


def tool_binary(env_name: str, command: str) -> str:
    requested = os.environ.get(env_name, command)
    resolved = shutil.which(requested) if requested else None
    if resolved is None:
        raise RuntimeError(f"FAMILY_TOOL_MISSING: {env_name}={requested!r}; install {command} on PATH or set {env_name} to an executable")
    return resolved


def prepare_author_inputs(family: pathlib.Path, char: str, force: bool):
    spec = CHAR_SPECS[char]
    home = family / "outfits/swimwear" / char
    candidate = home / "prepared"
    author = home / "authoring"
    prototype = json.loads(require_file(candidate / "prototype.json").read_text())
    require_file(family / char / "config.json")
    require_file(family / char / "out/rig/rig.json")
    for row in prototype["parts"]:
        require_file(candidate / "parts" / (row["name"] + ".png"))
    if author.exists():
        if force:
            shutil.rmtree(author)
        else:
            raise RuntimeError(f"SWIMWEAR_AUTHOR_FRESH_INPUT_REQUIRED: {author}")
    inputs = author / "inputs"
    (inputs / "parts").mkdir(parents=True)
    records = []
    for row in prototype["parts"]:
        name = row["name"]
        shutil.copy2(candidate / "parts" / (name + ".png"), inputs / "parts" / (name + ".png"))
        records.append({
            **{k: row[k] for k in ["name", "x", "y", "w", "h", "opaque_px"]},
            "from": "full:author:swimwear-" + name,
            "projected_core_px": 0,
            "source_px_taken": 0,
            "refused_drift_px": 0,
            "merged_px": 0,
            "seam_override_px": 0,
        })
    (inputs / "parts.json").write_text(
        json.dumps(
            {"rig_size": [800, 2284], "scale_rig_per_source": 1, "ghost_px": {}, "parts": records},
            indent=2,
        )
        + "\n"
    )
    cfg = json.loads((family / char / "config.json").read_text())
    cfg["key"] = f"{char}_swimwear"
    cfg.pop("seethrough", None)
    cfg["assemble"] = {
        "rig_scale": 1,
        "plan": [[r["name"], "full", "author:swimwear-" + r["name"]] for r in records],
    }
    cfg["motion"].pop("blink", None)
    baseline_rig = json.loads((family / char / "out/rig/rig.json").read_text())
    cfg["constraints"] = json.loads(json.dumps(baseline_rig["constraints"]))
    cfg["bones"] += [
        {"name": "cardigan_hem_r", "parent": "hip", **spec["hem_r"]},
        {"name": "cardigan_hem_l", "parent": "hip", **spec["hem_l"]},
    ]
    for side in ["r", "l"]:
        cfg["constraints"].append({
            "type": "physics",
            "name": f"cardigan_hem_{side}_phys",
            "bone": f"cardigan_hem_{side}",
            "rotate": 1,
            "inertia": 0.15,
            "strength": 360,
            "damping": 0.92,
            "mass": 1,
            "wind": 0.11,
            "gravity": 0.06,
            "mix": 1,
        })
    def resolve_generator_mesh(part_name: str) -> dict:
        m = cfg.get("meshes", {}).get(part_name, {})
        if isinstance(m.get("contour"), dict):
            return json.loads(json.dumps(m))
        rep_path = family / char / "declared-repairs.json"
        if rep_path.is_file():
            rep_doc = json.loads(rep_path.read_text())
            mc = rep_doc.get("parts", {}).get(part_name, {}).get("regenerated", {}).get("meshConfig", {})
            if isinstance(mc.get("contour"), dict):
                return json.loads(json.dumps(mc))
        raise RuntimeError(
            f"FAMILY_EXPLICIT_MESH_REFUSED: {char}/office/{part_name} declares meshes.{part_name}.explicit without "
            f"parts.{part_name}.regenerated.meshConfig.contour in {rep_path}; edit {author / 'config.json'} directly instead."
        )

    top = resolve_generator_mesh("topwear")
    top["segments"] = [*spec["topwear_segments"], *spec["cardigan_segments"]]
    top["contour"]["tolerance"] = 1
    top["contour"]["margin"] = 3
    bust_override = spec.get("bust_regions")
    bust_override_path = home / "bust-regions.json"
    if bust_override_path.is_file():
        bust_override = json.loads(bust_override_path.read_text())
    if bust_override:
        for reg in top["contour"].get("regions", []):
            if reg["name"] in bust_override:
                ov = bust_override[reg["name"]]
                reg["cx"] = round(float(ov["cx"]), 2)
                reg["cy"] = round(float(ov["cy"]), 2)
                reg["r"] = round(float(ov["r"]), 2)
                reg["band"] = round(float(ov["band"]), 2)
    neck = resolve_generator_mesh("neck")
    neck["segments"] = spec["neck_segments"]
    cfg["meshes"] = {
        "neck": neck,
        "topwear": top,
        "sleeves": {
            "contour": {
                "tolerance": 1,
                "margin": 3,
                "spacing": 32,
                "maxEdge": 54,
                "stray": 400,
                "bridges": True,
            },
            "r": 12,
            "segments": spec["sleeves_segments"],
        },
    }
    if any(r["name"] == "handwear_l" for r in records):
        cfg["meshes"]["handwear_l"] = json.loads(json.dumps(cfg["meshes"]["sleeves"]))
    cfg["regions"] = {"shoes": "root", "bottomwear": "hip"}
    cfg["note"] = (
        "Consumer authored swimwear: common bone/motion/physics definitions are preserved in final assembly; "
        "new cover-up/pareo hems have separate physics on unified topwear. Source lineage is in prepared/prototype.json."
    )
    (author / "config.json").write_text(json.dumps(cfg, indent=2) + "\n")


def run_rig_parts_rig(family: pathlib.Path, char: str):
    home = family / "outfits/swimwear" / char
    author = home / "authoring"
    cmd = [
        tool_binary("RIG_PARTS_BIN", "rig-parts"),
        "rig",
        "--config",
        str(author / "config.json"),
        "--parts",
        str(author / "inputs"),
        "--out",
        str(author / "rig"),
    ]
    subprocess.run(cmd, check=True)


def merge_with_baseline(family: pathlib.Path, char: str, force: bool):
    home = family / "outfits/swimwear" / char
    authored = home / "authoring/rig"
    baseline = family / char / "out"
    out = home / "out"
    if out.exists():
        if force:
            shutil.rmtree(out)
        else:
            raise RuntimeError(f"SWIMWEAR_MERGE_FRESH_OUTPUT_REQUIRED: {out}")

    rig = json.loads((baseline / "rig/rig.json").read_text())
    new = json.loads((authored / "rig.json").read_text())
    new_names = [p["name"] for p in json.loads((home / "authoring/inputs/parts.json").read_text())["parts"]]
    common_slots = [s["name"] for s in rig["slots"] if s["name"] not in OFFICE_CLOTHING]
    used = {"root", "hip", "chest", "chest_ctl", "neck", "head", "head_ctl", "boob_r", "boob_l"}
    old_bones = {b["name"]: b for b in rig["bones"]}
    new_bones = {b["name"]: b for b in new["bones"]}
    for name in used:
        if name in old_bones and old_bones[name] != new_bones.get(name):
            raise RuntimeError(f"SWIMWEAR_BIND_FRAME_CHANGED {char}:{name}")
    extra = [b for b in new["bones"] if b["name"] not in old_bones]
    if {b["name"] for b in extra} != {"cardigan_hem_r", "cardigan_hem_l"}:
        raise RuntimeError(f"SWIMWEAR_UNEXPECTED_NEW_BONE {char}: {[b['name'] for b in extra]}")
    rig["bones"] += extra

    old_constraints = {(c["type"], c["name"]) for c in rig["constraints"]}
    extra_constraints = [c for c in new.get("constraints", []) if (c["type"], c["name"]) not in old_constraints]
    if {c["name"] for c in extra_constraints} != {"cardigan_hem_r_phys", "cardigan_hem_l_phys"}:
        raise RuntimeError(f"SWIMWEAR_UNEXPECTED_NEW_CONSTRAINT {char}: {[c['name'] for c in extra_constraints]}")
    rig["constraints"] += extra_constraints

    old_slots = {s["name"]: s for s in rig["slots"]}
    new_slots = {s["name"]: s for s in new["slots"]}
    slot_order = ["hair_back", *new_names, *[n for n in common_slots if n != "hair_back"]]
    rig["slots"] = [new_slots[n] if n in new_names else old_slots[n] for n in slot_order]
    rig["skins"]["default"] = {
        n: new["skins"]["default"][n] if n in new_names else rig["skins"]["default"][n]
        for n in slot_order
    }

    (out / "rig/images").mkdir(parents=True)
    (out / "parts").mkdir()
    for n in slot_order:
        source_dir = authored if n in new_names else baseline / "rig"
        for attachment in rig["skins"]["default"][n].values():
            shutil.copy2(source_dir / "images" / attachment["image"], out / "rig/images" / attachment["image"])

    old_parts_list = json.loads((baseline / "parts.json").read_text())["parts"]
    common_part_names = [p["name"] for p in old_parts_list if p["name"] not in OFFICE_CLOTHING]
    part_order = ["hair_back", *new_names, *[n for n in common_part_names if n != "hair_back"]]
    for n in part_order:
        source_parts = home / "authoring/inputs" if n in new_names else baseline
        shutil.copy2(source_parts / "parts" / (n + ".png"), out / "parts" / (n + ".png"))

    old_parts = {p["name"]: p for p in old_parts_list}
    new_parts = {p["name"]: p for p in json.loads((home / "authoring/inputs/parts.json").read_text())["parts"]}
    parts = {
        "rig_size": [800, 2284],
        "scale_rig_per_source": 1,
        "ghost_px": {},
        "parts": [new_parts[n] if n in new_names else old_parts[n] for n in part_order],
    }
    old_reports = json.loads((baseline / "rig/mesh_report.json").read_text())
    new_reports = json.loads((authored / "mesh_report.json").read_text())
    (out / "rig/mesh_report.json").write_text(
        json.dumps([r for r in old_reports if r["part"] in common_part_names] + new_reports, indent=2) + "\n"
    )
    (out / "parts.json").write_text(json.dumps(parts, indent=2) + "\n")
    (out / "rig/rig.json").write_text(json.dumps(rig, indent=2) + "\n")
    shutil.copy2(baseline / "rig/motion.json", out / "rig/motion.json")
    shutil.copy2(home / "prepared/assembled-white.png", home / "inputs/painting.png")
    (out / "assembly.json").write_text(
        json.dumps(
            {
                "spec": "family-swimwear-assembly/1",
                "character": char,
                "commonBonePrefix": len(old_bones),
                "commonSlots": common_slots,
                "newClothingSlots": new_names,
                "appendedBones": [b["name"] for b in extra],
                "motion": "Exact accepted motion bytes",
                "commonPhysics": "Exact accepted constraint prefix",
                "sourceReference": (
                    "Registered full static composition with exact accepted head assets; this is the intended "
                    "composite reference, not untouched original artwork. Original crop remains painting-clothing-source.png."
                ),
                "status": "AWAITING_OFFICIAL_BUILD_CHECK",
            },
            indent=2,
        )
        + "\n"
    )


def stitch_neck_seam(family: pathlib.Path, char: str):
    spec = CHAR_SPECS[char]
    home = family / "outfits/swimwear" / char
    target = home / "out/rig/rig.json"
    before = target.read_bytes()
    rig = json.loads(before)
    parts = {p["name"]: p for p in json.loads((home / "out/parts.json").read_text())["parts"]}
    rows = []
    for name, threshold, lower in spec["stitch"]:
        attachment = rig["skins"]["default"][name][name]
        record = parts[name]
        changed = []
        for i, weights in enumerate(attachment["weights"]):
            source_y = record["y"] - 4 + attachment["uvs"][2 * i + 1] * attachment["height"]
            if not (source_y >= threshold if lower else source_y <= threshold):
                continue
            chest = next((w for w in weights if w["bone"] == "chest"), None)
            if chest is None:
                continue
            bound = [{**chest, "weight": 1}]
            if bound != weights:
                changed.append({
                    "vertex": i,
                    "sourceY": source_y,
                    "before": [{"bone": w["bone"], "weight": w["weight"]} for w in weights],
                })
            attachment["weights"][i] = bound
        rows.append({
            "part": name,
            "sourceYThreshold": threshold,
            "side": "atOrBelow" if lower else "atOrAbove",
            "changed": changed,
        })
    text = json.dumps(rig, indent=2) + "\n"
    target.write_text(text)
    (home / "out/neck-seam-stitch.json").write_text(
        json.dumps(
            {
                "spec": "family-swimwear-neck-seam/1",
                "character": char,
                "beforeRigSHA256": hashlib.sha256(before).hexdigest(),
                "afterRigSHA256": hashlib.sha256(text.encode()).hexdigest(),
                "rows": rows,
                "scope": (
                    "Existing chest bind coordinates only. New neck lower edge and upper swimsuit/cover-up use "
                    "the same chest affine transform. Original common bones/constraints/motion/attachments and "
                    "every art pixel, UV and triangle remain unchanged."
                ),
                "reason": "Native dark motion closeup exposed independently weighted shared skin edge despite a green zero-fold check.",
            },
            indent=2,
        )
        + "\n"
    )
    return {r["part"]: len(r["changed"]) for r in rows}


def run_build_and_check(family: pathlib.Path, char: str):
    home = family / "outfits/swimwear" / char
    out = home / "out"
    subprocess.run(
        [
            tool_binary("RIG_PARTS_BIN", "rig-parts"),
            "check",
            "--rig",
            str(out / "rig"),
            "--parts",
            str(out),
            "--source",
            str(home / "inputs/painting.png"),
            "--out",
            str(out / "check"),
            "--page-edges",
            "free",
            "--pack-shape",
            "polygon",
        ],
        check=False,
    )
    check = json.loads((out / "check/check.json").read_text())
    return check


def verify_protected(family: pathlib.Path, char: str):
    home = family / "outfits/swimwear" / char
    record = json.loads((home / "protected-baseline.json").read_text())
    errors = []
    for rel, expected in record["files"].items():
        path = family / rel
        found = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "MISSING"
        if found != expected:
            errors.append({"file": rel, "found": found, "required": expected})
    source = json.loads((home / "source-provenance.json").read_text())
    if hashlib.sha256((home / source["source"]).read_bytes()).hexdigest() != source["sourceSHA256"]:
        errors.append({"file": source["source"], "reason": "original copy changed"})
    variant = home / "out/rig/rig.json"
    baseline = json.loads((family / char / "out/rig/rig.json").read_text())
    rig = json.loads(variant.read_text())
    for field in ["bones", "constraints", "stops"]:
        required = baseline.get(field, [])
        found = rig.get(field, [])
        if found[: len(required)] != required:
            errors.append({"field": field, "reason": "accepted common entries or their order changed"})
    if baseline.get("skeleton") != rig.get("skeleton"):
        errors.append({"field": "skeleton", "reason": "accepted stage changed"})
    old_motion = (family / char / "out/rig/motion.json").read_bytes()
    new_motion = (home / "out/rig/motion.json").read_bytes()
    if old_motion != new_motion:
        errors.append({"field": "motion", "reason": "accepted motion bytes changed"})
    common = [s["name"] for s in baseline["slots"] if s["name"] not in OFFICE_CLOTHING]
    for name in common:
        old = baseline["skins"]["default"].get(name)
        new = rig["skins"]["default"].get(name)
        if old != new:
            errors.append({"slot": name, "reason": "protected face/hair attachment changed"})
        for attachment in (old or {}).values():
            image = attachment.get("image")
            if image and (family / char / "out/rig/images" / image).read_bytes() != (home / "out/rig/images" / image).read_bytes():
                errors.append({"image": image, "reason": "protected face/hair PNG changed"})
    if errors:
        raise RuntimeError(f"SWIMWEAR_PROTECTED_CHECK_FAILED {char}: {errors}")
    return {"character": char, "status": "PRESERVATION_PASS", "commonSlotsChecked": len(common)}


def run_fast_build(family: pathlib.Path, char: str):
    home = family / "outfits/swimwear" / char
    out = home / "out"
    build_dir = out / "check/build"
    build_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            tool_binary("RIGC_BIN", "rigc"),
            "build",
            "--rig",
            str(out / "rig/rig.json"),
            "--motion",
            str(out / "rig/motion.json"),
            "--out",
            str(build_dir),
            "--profile",
            "spine-html",
            "--pack",
            "--page-edges",
            "free",
            "--pack-shape",
            "polygon",
        ],
        check=True,
    )
    for rel in ["authoring/rig/images", "authoring/rig/rig.json", "authoring/rig/motion.json"]:
        p = home / rel
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()
    return {"PASS": True, "gate_spine_html_green": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__, epilog="Binaries: RIG_PARTS_BIN / RIGC_BIN executable overrides, otherwise rig-parts / rigc on PATH. No automatic downloads.")
    parser.add_argument("--family-dir", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[1], help="Family directory (default: this checkout)")
    parser.add_argument("--characters", nargs="*", choices=CHAR_SPECS, default=["roa", "luna", "jinni", "naru", "nova"])
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--fast-build", action="store_true")
    args = parser.parse_args()
    family = args.family_dir.resolve()
    if not family.is_dir():
        raise RuntimeError(f"FAMILY_INPUT_MISSING: {family}")
    if args.characters:
        tool_binary("RIG_PARTS_BIN", "rig-parts")
        if args.fast_build:
            tool_binary("RIGC_BIN", "rigc")
    summary = []
    for char in args.characters:
        prev_check = None
        prev_gate = None
        out_check = family / "outfits/swimwear" / char / "out/check"
        if args.fast_build and (out_check / "check.json").is_file():
            prev_check = (out_check / "check.json").read_bytes()
        if args.fast_build and (out_check / "gate_spine-html.txt").is_file():
            prev_gate = (out_check / "gate_spine-html.txt").read_bytes()
        prepare_author_inputs(family, char, force=args.force)
        run_rig_parts_rig(family, char)
        merge_with_baseline(family, char, force=args.force)
        stitched = stitch_neck_seam(family, char)
        if args.fast_build:
            check = run_fast_build(family, char)
            if prev_check is not None:
                (out_check / "check.json").write_bytes(prev_check)
            if prev_gate is not None:
                (out_check / "gate_spine-html.txt").write_bytes(prev_gate)
        else:
            check = run_build_and_check(family, char)
        protected = verify_protected(family, char)
        row = {
            "character": char,
            "stitched": stitched,
            "PASS": check["PASS"],
            "gate_spine_html_green": check["gate_spine_html_green"],
            "seam_mean": check.get("seam_mean"),
            "seam_rig_px_over_40": check.get("seam_rig_px_over_40"),
            "fold_status": check.get("ANIMATIONS_DO_NOT_FOLD", {}).get("status"),
            "stretch_severity": check.get("TEXTURE_STRETCH", {}).get("severity"),
            "protected": protected["status"],
        }
        print(json.dumps(row), flush=True)
        summary.append(row)
    print(json.dumps({"results": summary}, indent=2), flush=True)
    if not all(r["PASS"] and r["gate_spine_html_green"] for r in summary):
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as error:
        raise SystemExit(f"FAMILY_INPUT_MISSING: {error.filename}") from None
    except RuntimeError as error:
        raise SystemExit(str(error)) from None
