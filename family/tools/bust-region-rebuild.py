#!/usr/bin/env python3
"""Read or update bust_r / bust_l contour regions and fast-rebuild the target rig."""
import argparse
import hashlib
import json
import math
import pathlib
import shutil
import subprocess

CHARACTERS = ["roa", "luna", "jinni", "naru", "nova"]
OUTFITS = ["office", "homewear", "swimwear"]

TOPWEAR_STITCH_THRESHOLD = {
    "homewear": {"roa": 520, "luna": 645, "jinni": 625, "naru": 705, "nova": 625},
    "swimwear": {"roa": 520, "luna": 645, "jinni": 625, "naru": 705, "nova": 625},
}


def config_path_for(family: pathlib.Path, char: str, outfit: str) -> pathlib.Path:
    if outfit == "office":
        return family / char / "config.json"
    return family / "outfits" / outfit / char / "authoring/config.json"


def read_all_regions(family: pathlib.Path) -> dict:
    result = {}
    for ch in CHARACTERS:
        base_cfg = json.loads((family / ch / "config.json").read_text())
        chest_bone = next((b for b in base_cfg["bones"] if b.get("name") == "chest"), {"at": [400, 750]})
        ch_entry = {"chest": chest_bone["at"], "outfits": {}}
        for outfit in OUTFITS:
            cpath = config_path_for(family, ch, outfit)
            if not cpath.is_file():
                cpath = family / ch / "config.json"
            cfg = json.loads(cpath.read_text())
            regs = cfg.get("meshes", {}).get("topwear", {}).get("contour", {}).get("regions", [])
            by_name = {}
            for r in regs:
                if r.get("name") in ("bust_r", "bust_l"):
                    by_name[r["name"]] = {
                        "cx": int(round(r["cx"])),
                        "cy": int(round(r["cy"])),
                        "r": int(round(r["r"])),
                        "band": int(round(r["band"])),
                    }
            ch_entry["outfits"][outfit] = by_name
        result[ch] = ch_entry
    return result


def clamp_non_overlapping(bust_r: dict, bust_l: dict, margin: float = 2.0) -> tuple[dict, dict, bool]:
    r_out = {k: int(round(float(bust_r[k]))) for k in ("cx", "cy", "r", "band")}
    l_out = {k: int(round(float(bust_l[k]))) for k in ("cx", "cy", "r", "band")}
    r_out["r"] = max(6, min(120, r_out["r"]))
    l_out["r"] = max(6, min(120, l_out["r"]))
    r_out["band"] = max(4, min(120, r_out["band"]))
    l_out["band"] = max(4, min(120, l_out["band"]))

    dist = math.hypot(l_out["cx"] - r_out["cx"], l_out["cy"] - r_out["cy"])
    avail = max(16.0, dist - margin)
    clamped = False
    if r_out["r"] + l_out["r"] + 8 > avail:
        scale = max(0.25, (avail - 8.0) / max(1.0, r_out["r"] + l_out["r"]))
        r_out["r"] = max(6, int(math.floor(r_out["r"] * scale)))
        l_out["r"] = max(6, int(math.floor(l_out["r"] * scale)))
        clamped = True
    max_band_sum = max(8, int(math.floor(avail - (r_out["r"] + l_out["r"]))))
    cur_band_sum = r_out["band"] + l_out["band"]
    if cur_band_sum > max_band_sum:
        ratio = max_band_sum / max(1, cur_band_sum)
        r_out["band"] = max(4, int(math.floor(r_out["band"] * ratio)))
        l_out["band"] = max(4, max_band_sum - r_out["band"])
        clamped = True
    return r_out, l_out, clamped


def rebuild_variant(
    family: pathlib.Path,
    live_family: pathlib.Path | None,
    char: str,
    outfit: str,
    bust_r: dict,
    bust_l: dict,
) -> dict:
    if outfit not in ("swimwear", "homewear"):
        raise RuntimeError(f"Only swimwear and homewear variants support live bust rebuild (got {outfit})")

    home = family / "outfits" / outfit / char
    author = home / "authoring"
    out = home / "out"
    cfg_path = author / "config.json"
    rig_tmp = author / "rig_tmp"

    r_clean, l_clean, clamped = clamp_non_overlapping(bust_r, bust_l, margin=2.0)
    for margin in (2.0, 8.0, 14.0, 20.0):
        r_clean, l_clean, c_step = clamp_non_overlapping(bust_r, bust_l, margin=margin)
        clamped = clamped or c_step
        cfg = json.loads(cfg_path.read_text())
        for reg in cfg["meshes"]["topwear"]["contour"].get("regions", []):
            if reg["name"] == "bust_r":
                reg.update(r_clean)
            elif reg["name"] == "bust_l":
                reg.update(l_clean)
        cfg_path.write_text(json.dumps(cfg, indent=2) + "\n")
        if rig_tmp.exists():
            shutil.rmtree(rig_tmp)
        proc = subprocess.run(
            [
                "node",
                "/Users/firejune/Workspace/Firejune/rig-parts/bin/rig-parts.cjs",
                "rig",
                "--config",
                str(cfg_path),
                "--parts",
                str(author / "inputs"),
                "--out",
                str(rig_tmp),
            ],
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            break
        if "RIG_CONTOUR_REGIONS_OVERLAP" not in (proc.stdout + proc.stderr):
            raise RuntimeError((proc.stderr or proc.stdout).strip())
    else:
        raise RuntimeError("Bust regions still overlap after automatic band reduction")

    (home / "bust-regions.json").write_text(
        json.dumps({"bust_r": r_clean, "bust_l": l_clean}, indent=2) + "\n"
    )

    try:
        new_rig = json.loads((rig_tmp / "rig.json").read_text())
        new_reports = json.loads((rig_tmp / "mesh_report.json").read_text())

        # Update topwear mesh report in authoring/rig/mesh_report.json and out/rig/mesh_report.json
        auth_report_path = author / "rig/mesh_report.json"
        if auth_report_path.is_file():
            auth_reports = json.loads(auth_report_path.read_text())
            new_top_rep = next((r for r in new_reports if r.get("part") == "topwear"), None)
            if new_top_rep:
                auth_reports = [new_top_rep if r.get("part") == "topwear" else r for r in auth_reports]
                auth_report_path.write_text(json.dumps(auth_reports, indent=2) + "\n")

        out_report_path = out / "rig/mesh_report.json"
        if out_report_path.is_file():
            out_reports = json.loads(out_report_path.read_text())
            new_top_rep = next((r for r in new_reports if r.get("part") == "topwear"), None)
            if new_top_rep:
                out_reports = [new_top_rep if r.get("part") == "topwear" else r for r in out_reports]
                out_report_path.write_text(json.dumps(out_reports, indent=2) + "\n")

        # Update topwear skin attachment in out/rig/rig.json and re-apply neck-seam stitch on topwear
        target_rig_path = out / "rig/rig.json"
        rig = json.loads(target_rig_path.read_text())
        rig["skins"]["default"]["topwear"] = new_rig["skins"]["default"]["topwear"]
        for attachment in rig["skins"]["default"]["topwear"].values():
            shutil.copy2(rig_tmp / "images" / attachment["image"], out / "rig/images" / attachment["image"])

        parts = {p["name"]: p for p in json.loads((out / "parts.json").read_text())["parts"]}
        threshold = TOPWEAR_STITCH_THRESHOLD[outfit][char]
        attachment = rig["skins"]["default"]["topwear"]["topwear"]
        record = parts["topwear"]
        for i, weights in enumerate(attachment["weights"]):
            source_y = record["y"] - 4 + attachment["uvs"][2 * i + 1] * attachment["height"]
            if source_y <= threshold:
                chest = next((w for w in weights if w["bone"] == "chest"), None)
                if chest is not None:
                    attachment["weights"][i] = [{**chest, "weight": 1}]

        target_rig_text = json.dumps(rig, indent=2) + "\n"
        target_rig_path.write_text(target_rig_text)

        stitch_path = out / "neck-seam-stitch.json"
        if stitch_path.is_file():
            stitch_doc = json.loads(stitch_path.read_text())
            stitch_doc["afterRigSHA256"] = hashlib.sha256(target_rig_text.encode()).hexdigest()
            stitch_path.write_text(json.dumps(stitch_doc, indent=2) + "\n")
    finally:
        if rig_tmp.exists():
            shutil.rmtree(rig_tmp)

    # Fast packed build into out/check/build
    build_dir = out / "check/build"
    build_dir.mkdir(parents=True, exist_ok=True)
    bproc = subprocess.run(
        [
            "node",
            "/Users/firejune/Workspace/Firejune/rigc/bin/rigc.cjs",
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
        capture_output=True,
        text=True,
    )
    if bproc.returncode != 0:
        raise RuntimeError((bproc.stderr or bproc.stdout).strip())

    # Sync to live server directory if distinct from worktree
    if live_family is not None and live_family.resolve() != family.resolve():
        live_home = live_family / "outfits" / outfit / char
        live_build = live_home / "out/check/build"
        live_build.mkdir(parents=True, exist_ok=True)
        for item in build_dir.iterdir():
            if item.is_file():
                shutil.copy2(item, live_build / item.name)
        live_cfg = live_home / "authoring/config.json"
        if live_cfg.parent.is_dir():
            shutil.copy2(cfg_path, live_cfg)

    return {
        "ok": True,
        "character": char,
        "outfit": outfit,
        "bust_r": r_clean,
        "bust_l": l_clean,
        "clamped": clamped,
    }


def parse_region_arg(text: str) -> dict:
    parts = [float(x.strip()) for x in text.split(",")]
    if len(parts) != 4:
        raise ValueError(f"Expected cx,cy,r,band (got {text})")
    return {"cx": parts[0], "cy": parts[1], "r": parts[2], "band": parts[3]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", choices=["get", "set"], required=True)
    parser.add_argument("--family-dir", default="/Users/firejune/Workspace/Firejune/parts-examples-naru-homewear/family")
    parser.add_argument("--live-family-dir", default="/Users/firejune/Workspace/Firejune/spine-parts-examples/family")
    parser.add_argument("--character", choices=CHARACTERS)
    parser.add_argument("--outfit", choices=OUTFITS, default="swimwear")
    parser.add_argument("--bust-r")
    parser.add_argument("--bust-l")
    args = parser.parse_args()

    family = pathlib.Path(args.family_dir)
    live_family = pathlib.Path(args.live_family_dir) if args.live_family_dir else None

    if args.action == "get":
        print(json.dumps(read_all_regions(family)))
        return

    if not args.character or not args.bust_r or not args.bust_l:
        raise SystemExit("--character, --bust-r, and --bust-l are required for --action set")
    res = rebuild_variant(
        family,
        live_family,
        args.character,
        args.outfit,
        parse_region_arg(args.bust_r),
        parse_region_arg(args.bust_l),
    )
    print(json.dumps(res))


if __name__ == "__main__":
    main()
