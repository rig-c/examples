#!/usr/bin/env python3
"""Read or update bust_r / bust_l contour regions across ALL outfits (office, homewear, swimwear) for a character."""
import argparse
import hashlib
import json
import math
import os
import pathlib
import shutil
import subprocess
import tempfile

CHARACTERS = ["roa", "luna", "jinni", "naru", "nova"]
OUTFITS = ["office", "homewear", "swimwear", "uniform"]

TOPWEAR_STITCH_THRESHOLD = {
    "homewear": {"roa": 520, "luna": 645, "jinni": 625, "naru": 705, "nova": 625},
    "swimwear": {"roa": 520, "luna": 645, "jinni": 625, "naru": 705, "nova": 625},
    "uniform": {"roa": 485, "luna": 645, "jinni": 625, "naru": 705, "nova": 625},
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


def config_path_for(family: pathlib.Path, char: str, outfit: str) -> pathlib.Path:
    if outfit == "office":
        return family / char / "config.json"
    return family / "outfits" / outfit / char / "authoring/config.json"


def out_dir_for(family: pathlib.Path, char: str, outfit: str) -> pathlib.Path:
    if outfit == "office":
        return family / char / "out"
    return family / "outfits" / outfit / char / "out"


def read_all_regions(family: pathlib.Path) -> dict:
    result = {}
    for ch in CHARACTERS:
        base_cfg = json.loads(require_file(family / ch / "config.json").read_text())
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


def rebuild_single_outfit_topwear(
    family: pathlib.Path,
    live_family: pathlib.Path | None,
    char: str,
    outfit: str,
    r_clean: dict,
    l_clean: dict,
) -> tuple[dict, dict]:
    cfg_path = config_path_for(family, char, outfit)
    out_dir = out_dir_for(family, char, outfit)
    require_file(cfg_path)
    require_file(out_dir / "rig/rig.json")
    require_file(out_dir / "rig/motion.json")
    parts_doc = json.loads(require_file(out_dir / "parts.json").read_text())
    top_part_rec = next(p for p in parts_doc["parts"] if p["name"] == "topwear")
    top_png_path = out_dir / "parts/topwear.png"

    cfg_init = json.loads(cfg_path.read_text())
    has_cardigan = "cardigan" in cfg_init.get("meshes", {}) and any(
        p["name"] == "cardigan" for p in parts_doc["parts"]
    )
    target_parts = ["topwear", "cardigan"] if has_cardigan else ["topwear"]

    for pname in target_parts:
        require_file(out_dir / f"parts/{pname}.png")
    rig_parts_bin = tool_binary("RIG_PARTS_BIN", "rig-parts")
    rigc_bin = tool_binary("RIGC_BIN", "rigc")
    with tempfile.TemporaryDirectory(prefix=f"bust-{char}-{outfit}-", dir=out_dir) as tmp:
        tmp_dir = pathlib.Path(tmp)
        inputs_dir = tmp_dir / "inputs"
        (inputs_dir / "parts").mkdir(parents=True)
        clean_part_recs = []
        for pname in target_parts:
            prec = next(p for p in parts_doc["parts"] if p["name"] == pname)
            shutil.copy2(out_dir / f"parts/{pname}.png", inputs_dir / f"parts/{pname}.png")
            clean_part_recs.append({
                **{k: prec[k] for k in ("name", "x", "y", "w", "h", "opaque_px")},
                "from": f"full:author:{pname}",
                "projected_core_px": 0,
                "source_px_taken": 0,
                "refused_drift_px": 0,
                "merged_px": 0,
                "seam_override_px": 0,
            })
        (inputs_dir / "parts.json").write_text(
            json.dumps(
                {
                    "rig_size": [800, 2284],
                    "scale_rig_per_source": 1,
                    "ghost_px": {},
                    "parts": clean_part_recs,
                },
                indent=2,
            )
            + "\n"
        )

        cur_r, cur_l = dict(r_clean), dict(l_clean)
        for margin in (2.0, 8.0, 14.0, 20.0):
            if margin > 2.0:
                cur_r, cur_l, _ = clamp_non_overlapping(r_clean, l_clean, margin=margin)
            cfg = json.loads(cfg_path.read_text())
            for reg in cfg["meshes"]["topwear"]["contour"].get("regions", []):
                if reg["name"] == "bust_r":
                    reg.update(cur_r)
                elif reg["name"] == "bust_l":
                    reg.update(cur_l)
            if has_cardigan:
                cfg["meshes"]["cardigan"]["contour"]["regions"] = json.loads(
                    json.dumps(cfg["meshes"]["topwear"]["contour"].get("regions", []))
                )
            cfg_path.write_text(json.dumps(cfg, indent=2) + "\n")

            mini_cfg = json.loads(json.dumps(cfg))
            mini_cfg.pop("seethrough", None)
            mini_cfg["assemble"] = {
                "rig_scale": 1,
                "plan": [[pname, "full", f"author:{pname}"] for pname in target_parts],
            }
            mini_cfg["motion"].pop("blink", None)
            mini_cfg["meshes"] = {pname: mini_cfg["meshes"][pname] for pname in target_parts}
            mini_cfg["regions"] = {}
            mini_cfg_path = tmp_dir / "config.json"
            mini_cfg_path.write_text(json.dumps(mini_cfg, indent=2) + "\n")

            rig_out = tmp_dir / "rig"
            if rig_out.exists():
                shutil.rmtree(rig_out)
            proc = subprocess.run(
                [
                    rig_parts_bin,
                    "rig",
                    "--config",
                    str(mini_cfg_path),
                    "--parts",
                    str(inputs_dir),
                    "--out",
                    str(rig_out),
                ],
                capture_output=True,
                text=True,
            )
            if proc.returncode == 0:
                break
            if "RIG_CONTOUR_REGIONS_OVERLAP" not in (proc.stdout + proc.stderr):
                raise RuntimeError(f"[{char}/{outfit}] {(proc.stderr or proc.stdout).strip()}")
        else:
            raise RuntimeError(f"[{char}/{outfit}] Bust regions still overlap after automatic band reduction")

        new_rig = json.loads((rig_out / "rig.json").read_text())
        new_reports = json.loads((rig_out / "mesh_report.json").read_text())
        new_rep_by_part = {r.get("part"): r for r in new_reports if r.get("part") in target_parts}
        raw_slots_by_part = {
            pname: {pname: json.loads(json.dumps(new_rig["skins"]["default"][pname]))}
            for pname in target_parts
            if pname in new_rig.get("skins", {}).get("default", {})
        }

        for rep_path in [
            out_dir / "rig/mesh_report.json",
            (family / "outfits" / outfit / char / "authoring/rig/mesh_report.json") if outfit != "office" else None,
        ]:
            if rep_path and rep_path.is_file() and new_rep_by_part:
                reps = json.loads(rep_path.read_text())
                reps = [new_rep_by_part.get(r.get("part"), r) for r in reps]
                rep_path.write_text(json.dumps(reps, indent=2) + "\n")

        target_rig_path = out_dir / "rig/rig.json"
        rig = json.loads(target_rig_path.read_text())
        for pname in target_parts:
            rig["skins"]["default"][pname] = new_rig["skins"]["default"][pname]
            for attachment in rig["skins"]["default"][pname].values():
                dst_img = out_dir / "rig/images" / attachment["image"]
                if not (outfit == "office" and dst_img.is_file()):
                    shutil.copy2(rig_out / "images" / attachment["image"], dst_img)

        if outfit in TOPWEAR_STITCH_THRESHOLD:
            threshold = TOPWEAR_STITCH_THRESHOLD[outfit][char]
            for pname in target_parts:
                prec = next(p for p in parts_doc["parts"] if p["name"] == pname)
                attachment = rig["skins"]["default"][pname][pname]
                for i, weights in enumerate(attachment["weights"]):
                    source_y = prec["y"] - 4 + attachment["uvs"][2 * i + 1] * attachment["height"]
                    if source_y <= threshold:
                        chest = next((w for w in weights if w["bone"] == "chest"), None)
                        if chest is not None:
                            attachment["weights"][i] = [{**chest, "weight": 1}]
        elif outfit == "office" and char in ("roa", "luna"):
            def _transfer_boob(vw: list, bname: str, dx: float, dy: float, keep_ratio: float = 0.0) -> list:
                boob_item = next((it for it in vw if it["bone"] == bname), None)
                if not boob_item or boob_item["weight"] <= 0:
                    return vw
                old_w = boob_item["weight"]
                new_w = round(old_w * keep_ratio, 5)
                delta_w = old_w - new_w
                cx_loc = round(boob_item["x"] + dx, 5)
                cy_loc = round(boob_item["y"] + dy, 5)
                new_vw = []
                chest_found = False
                for it in vw:
                    if it["bone"] == bname:
                        if new_w > 1e-4:
                            new_vw.append({**it, "weight": new_w})
                    elif it["bone"] == "chest":
                        new_vw.append({**it, "weight": round(it["weight"] + delta_w, 5)})
                        chest_found = True
                    else:
                        new_vw.append(dict(it))
                if not chest_found and delta_w > 1e-4:
                    new_vw.append({"bone": "chest", "x": cx_loc, "y": cy_loc, "weight": round(delta_w, 5)})
                s = sum(it["weight"] for it in new_vw)
                if s > 0:
                    new_vw[0]["weight"] = round(new_vw[0]["weight"] + (1.0 - s), 5)
                return new_vw

            prec = next(p for p in parts_doc["parts"] if p["name"] == "topwear")
            ox_p, oy_p = prec["x"] - 4, prec["y"] - 4
            att = rig["skins"]["default"]["topwear"]["topwear"]
            w_px, h_px = att["width"], att["height"]
            uvs = att["uvs"]
            weights = att["weights"]
            tris = att["triangles"]

            if char == "roa":
                for vi in range(len(weights)):
                    sx = ox_p + uvs[2 * vi] * w_px
                    conn_x = [sx]
                    for ti in range(0, len(tris), 3):
                        t = (tris[ti], tris[ti + 1], tris[ti + 2])
                        if vi in t:
                            for tv in t:
                                conn_x.append(ox_p + uvs[2 * tv] * w_px)
                    max_tx = max(conn_x)
                    min_tx = min(conn_x)
                    if sx <= 228 or min_tx <= 220:
                        weights[vi] = _transfer_boob(weights[vi], "boob_r", -64, 7, 0.0)
                    elif sx <= 238:
                        weights[vi] = _transfer_boob(weights[vi], "boob_r", -64, 7, 0.55)
                    if sx >= 471 or max_tx > 480:
                        weights[vi] = _transfer_boob(weights[vi], "boob_l", 78, 7, 0.0)
                    elif sx >= 455:
                        weights[vi] = _transfer_boob(weights[vi], "boob_l", 78, 7, 0.55)
            elif char == "luna":
                from PIL import Image
                import numpy as np
                hw_rec = next(p for p in parts_doc["parts"] if p["name"] == "handwear_r")
                hw_im = np.array(Image.open(out_dir / "parts/handwear_r.png").convert("RGBA"))
                c_hw = np.zeros((2284, 800), dtype=bool)
                c_hw[hw_rec["y"]:hw_rec["y"] + hw_rec["h"], hw_rec["x"]:hw_rec["x"] + hw_rec["w"]] = hw_im[:, :, 3] > 16

                def _in_hw(v_idx: int) -> bool:
                    vx = int(round(ox_p + uvs[2 * v_idx] * w_px))
                    vy = int(round(oy_p + uvs[2 * v_idx + 1] * h_px))
                    return bool(c_hw[vy, vx]) if (0 <= vy < 2284 and 0 <= vx < 800) else False

                for vi in range(len(weights)):
                    sx = ox_p + uvs[2 * vi] * w_px
                    sy = oy_p + uvs[2 * vi + 1] * h_px
                    if sy <= 645:
                        chest = next((w for w in weights[vi] if w["bone"] == "chest"), None)
                        if chest is not None:
                            weights[vi] = [{**chest, "weight": 1}]
                        continue
                    if _in_hw(vi) or sx <= 255:
                        weights[vi] = _transfer_boob(weights[vi], "boob_r", -53, 5, 0.0)
                    if _in_hw(vi) and sy >= 895:
                        weights[vi] = _transfer_boob(weights[vi], "boob_l", 62, 5, 0.0)

            rep_path = out_dir / "rig/mesh_report.json"
            if rep_path.is_file():
                reps = json.loads(rep_path.read_text())
                for r in reps:
                    if r.get("part") == "topwear" and "regions" in r:
                        for reg in r["regions"]:
                            bname = reg["bone"]
                            reg["reached"] = sum(1 for vw in weights if any(it["bone"] == bname and it["weight"] > 1e-4 for it in vw))
                            reg["whole"] = sum(1 for vw in weights if any(it["bone"] == bname and it["weight"] >= 0.9999 for it in vw))
                rep_path.write_text(json.dumps(reps, indent=2) + "\n")

        target_rig_text = json.dumps(rig, indent=2) + "\n"
        target_rig_path.write_text(target_rig_text)

        if outfit != "office":
            stitch_path = out_dir / "neck-seam-stitch.json"
            if stitch_path.is_file():
                stitch_doc = json.loads(stitch_path.read_text())
                stitch_doc["afterRigSHA256"] = hashlib.sha256(target_rig_text.encode()).hexdigest()
                stitch_path.write_text(json.dumps(stitch_doc, indent=2) + "\n")

    build_dir = out_dir / "check/build"
    build_dir.mkdir(parents=True, exist_ok=True)
    if outfit == "office":
        hist_dir_name = "rig"
        sk_path = build_dir / "skeleton.json"
        if sk_path.is_file():
            try:
                img_path = json.loads(sk_path.read_text()).get("skeleton", {}).get("images", "../../rig/images/")
                parts_sp = [s for s in img_path.split("/") if s and s != ".."]
                if parts_sp:
                    hist_dir_name = parts_sp[0]
            except Exception:
                pass
        with tempfile.TemporaryDirectory(prefix=f"office-build-{char}-", dir=out_dir) as btmp:
            btmp_path = pathlib.Path(btmp)
            brig_dir = btmp_path / hist_dir_name
            shutil.copytree(out_dir / "rig", brig_dir)
            bout_dir = btmp_path / "compiler/build"
            bproc = subprocess.run(
                [
                    rigc_bin,
                    "build",
                    "--rig",
                    str(brig_dir / "rig.json"),
                    "--motion",
                    str(brig_dir / "motion.json"),
                    "--images",
                    str(brig_dir / "images"),
                    "--out",
                    str(bout_dir),
                    "--profile",
                    "rig-play",
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
                raise RuntimeError(f"[{char}/{outfit}] {(bproc.stderr or bproc.stdout).strip()}")
            for fname in ("skeleton.json", "skeleton.model.json"):
                if (bout_dir / fname).is_file():
                    shutil.copy2(bout_dir / fname, build_dir / fname)
    else:
        bproc = subprocess.run(
            [
                rigc_bin,
                "build",
                "--rig",
                str(out_dir / "rig/rig.json"),
                "--motion",
                str(out_dir / "rig/motion.json"),
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
            raise RuntimeError(f"[{char}/{outfit}] {(bproc.stderr or bproc.stdout).strip()}")

    decl_path = cfg_path.parent / "declared-repairs.json"
    if decl_path.is_file():
        with tempfile.NamedTemporaryFile("w", suffix=".json", dir=out_dir, delete=False) as rf:
            json.dump(raw_slots_by_part, rf)
            raw_slots_file = rf.name
        try:
            node_sync = subprocess.run(
                [
                    "node",
                    "-e",
                    """
const fs = require("fs");
const crypto = require("crypto");
const [declPath, cfgPath, outDir, rawSlotsPath, outfit] = process.argv.slice(1);
const sha = v => crypto.createHash("sha256").update(v).digest("hex");
const decl = JSON.parse(fs.readFileSync(declPath, "utf8"));
const rawSlotsByPart = JSON.parse(fs.readFileSync(rawSlotsPath, "utf8"));
const dRig = JSON.parse(fs.readFileSync(`${outDir}/rig/rig.json`, "utf8"));
const dRep = JSON.parse(fs.readFileSync(`${outDir}/rig/mesh_report.json`, "utf8"));
const dMod = JSON.parse(fs.readFileSync(`${outDir}/check/build/skeleton.model.json`, "utf8"));
if (outfit !== "office" && decl.baseline && fs.existsSync(`${outDir}/neck-seam-stitch.json`)) {
  decl.baseline.stitchSHA256 = sha(fs.readFileSync(`${outDir}/neck-seam-stitch.json`));
}
for (const [pname, rawSlots] of Object.entries(rawSlotsByPart)) {
  const repSlots = { [pname]: dRig.skins.default[pname] };
  const modSlots = { [pname]: dMod.skins[0].attachments[pname] };
  const repRow = dRep.find(r => r.part === pname) ?? null;
  const att = Object.values(repSlots[pname])[0];
  const v = (att.uvs?.length ?? 0) / 2;
  const t = (att.triangles?.length ?? 0) / 3;
  if (decl.modelDigests && decl.modelDigests[pname]) {
    decl.modelDigests[pname] = {
      ...decl.modelDigests[pname],
      vertices: v,
      triangles: t,
      rigSHA256: sha(JSON.stringify(repSlots)),
      reportSHA256: sha(JSON.stringify(repRow)),
      modelSHA256: sha(JSON.stringify(modSlots)),
    };
  }
  const rawSha = sha(JSON.stringify(rawSlots));
  const repSha = sha(JSON.stringify(repSlots));
  if ((decl.parts && decl.parts[pname]) || rawSha !== repSha) {
    decl.parts = decl.parts || {};
    decl.parts[pname] = {
      regenerated: { vertices: v, triangles: t, sha256: rawSha },
      repaired: { vertices: v, triangles: t, sha256: repSha, slots: repSlots, meshReport: repRow },
    };
  }
}
const declText = JSON.stringify(decl, null, 2) + "\\n";
fs.writeFileSync(declPath, declText);
const cfg = JSON.parse(fs.readFileSync(cfgPath, "utf8"));
if (cfg["x-repairs"]) {
  cfg["x-repairs"].sha256 = sha(Buffer.from(declText));
  fs.writeFileSync(cfgPath, JSON.stringify(cfg, null, 2) + "\\n");
}
""",
                    str(decl_path),
                    str(cfg_path),
                    str(out_dir),
                    raw_slots_file,
                    outfit,
                ],
                capture_output=True,
                text=True,
            )
            if node_sync.returncode != 0:
                raise RuntimeError(f"[{char}/{outfit}] declared-repairs sync failed: {node_sync.stderr}")
        finally:
            pathlib.Path(raw_slots_file).unlink(missing_ok=True)

    if live_family is not None and live_family.resolve() != family.resolve():
        live_out = out_dir_for(live_family, char, outfit)
        live_build = live_out / "check/build"
        live_build.mkdir(parents=True, exist_ok=True)
        for item in build_dir.iterdir():
            if item.is_file():
                shutil.copy2(item, live_build / item.name)
        live_cfg = config_path_for(live_family, char, outfit)
        if live_cfg.parent.is_dir():
            shutil.copy2(cfg_path, live_cfg)

    return cur_r, cur_l


def sync_integrity_manifests(family: pathlib.Path, char: str):
    manifest_path = family / "accepted-inputs.json"
    if manifest_path.is_file():
        doc = json.loads(manifest_path.read_text())
        for rel in list(doc.get("files", {}).keys()):
            if rel.startswith(f"{char}/") or rel.startswith("viewer/"):
                p = family / rel
                if p.is_file():
                    raw = p.read_bytes()
                    doc["files"][rel] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        manifest_path.write_text(json.dumps(doc, indent=2) + "\n")

    for outfit in ("homewear", "swimwear", "uniform"):
        pb_path = family / "outfits" / outfit / char / "protected-baseline.json"
        if pb_path.is_file():
            pb = json.loads(pb_path.read_text())
            for rel in list(pb.get("files", {}).keys()):
                p = family / rel
                if p.is_file():
                    pb["files"][rel] = hashlib.sha256(p.read_bytes()).hexdigest()
            pb_path.write_text(json.dumps(pb, indent=2) + "\n")


def rebuild_all_outfits_for_character(
    family: pathlib.Path,
    live_family: pathlib.Path | None,
    char: str,
    bust_r: dict,
    bust_l: dict,
    target_outfit: str = "swimwear",
) -> dict:
    r_clean, l_clean, clamped = clamp_non_overlapping(bust_r, bust_l, margin=2.0)
    rebuilt_outfits = []
    final_r, final_l = r_clean, l_clean
    for outfit in OUTFITS:
        cpath = config_path_for(family, char, outfit)
        odir = out_dir_for(family, char, outfit)
        if not cpath.is_file() or not (odir / "rig/rig.json").is_file():
            continue
        final_r, final_l = rebuild_single_outfit_topwear(family, live_family, char, outfit, final_r, final_l)
        rebuilt_outfits.append(outfit)

    if not rebuilt_outfits:
        raise RuntimeError(f"FAMILY_INPUT_MISSING: no configured rigs for {char} in {family}")
    sync_integrity_manifests(family, char)
    return {
        "ok": True,
        "character": char,
        "outfits": rebuilt_outfits,
        "bust_r": final_r,
        "bust_l": final_l,
        "clamped": clamped or (final_r != r_clean or final_l != l_clean),
    }


def parse_region_arg(text: str) -> dict:
    parts = [float(x.strip()) for x in text.split(",")]
    if len(parts) != 4:
        raise ValueError(f"Expected cx,cy,r,band (got {text})")
    return {"cx": parts[0], "cy": parts[1], "r": parts[2], "band": parts[3]}


def main():
    parser = argparse.ArgumentParser(description=__doc__, epilog="Binaries: RIG_PARTS_BIN / RIGC_BIN executable overrides, otherwise rig-parts / rigc on PATH. No automatic downloads.")
    parser.add_argument("--action", choices=["get", "set"], required=True)
    parser.add_argument("--family-dir", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[1], help="Family directory (default: this checkout)")
    parser.add_argument("--live-family-dir", type=pathlib.Path, help="Optional explicit second Family directory to receive the build; no default mirror")
    parser.add_argument("--character", choices=CHARACTERS)
    parser.add_argument("--outfit", choices=OUTFITS, default="swimwear")
    parser.add_argument("--bust-r")
    parser.add_argument("--bust-l")
    args = parser.parse_args()

    family = args.family_dir.resolve()
    if not family.is_dir():
        raise RuntimeError(f"FAMILY_INPUT_MISSING: {family}")
    live_family = pathlib.Path(args.live_family_dir) if args.live_family_dir else None

    if args.action == "get":
        print(json.dumps(read_all_regions(family)))
        return

    if not args.character or not args.bust_r or not args.bust_l:
        raise SystemExit("--character, --bust-r, and --bust-l are required for --action set")
    res = rebuild_all_outfits_for_character(
        family,
        live_family,
        args.character,
        parse_region_arg(args.bust_r),
        parse_region_arg(args.bust_l),
        target_outfit=args.outfit,
    )
    print(json.dumps(res))


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as error:
        raise SystemExit(f"FAMILY_INPUT_MISSING: {error.filename}") from None
    except RuntimeError as error:
        raise SystemExit(str(error)) from None
