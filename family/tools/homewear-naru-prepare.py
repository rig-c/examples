#!/usr/bin/env python3
"""Prepare immutable source/protection records and a provisional registration crop.

This is the existing crop/upscale asset pipeline's deterministic input stage.
It performs no retouching, inpainting, alpha inference or clothing substitution.
"""
import argparse
import hashlib
import json
import pathlib
import shutil
from PIL import Image


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=pathlib.Path, required=True)
    args = parser.parse_args()
    family = pathlib.Path(__file__).resolve().parents[1]
    target = family / "outfits/homewear/naru"
    inputs = target / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    copied = inputs / "source-group.jpeg"
    if copied.exists() and digest(copied) != digest(args.source):
        raise RuntimeError("HOMEWEAR_SOURCE_COPY_ALREADY_DIFFERS")
    if not copied.exists():
        shutil.copyfile(args.source, copied)
    source = Image.open(copied)
    if source.size != (2752, 1536) or source.mode != "RGB":
        raise RuntimeError("HOMEWEAR_SOURCE_EXPECTED_2752_1536_RGB")
    baseline = family / "naru"
    paths = [baseline / "out/rig/rig.json", baseline / "out/rig/motion.json",
             baseline / "out/rig/mesh_report.json", baseline / "out/parts.json",
             baseline / "out/check/build/skeleton.model.json"]
    paths += sorted((baseline / "out/rig/images").glob("*.png"))
    paths += sorted((baseline / "out/parts").glob("*.png"))
    record = {str(p.relative_to(family)): digest(p) for p in paths}
    protection_path = target / "protected-baseline.json"
    protection = {"spec": "family-homewear-protected-baseline/1", "character": "naru",
                  "files": record,
                  "rule": "Existing office artifacts are immutable. Copy accepted bones, constraints, stops, motion and non-clothing attachments; author only the new clothing variant."}
    if protection_path.exists() and json.loads(protection_path.read_text()) != protection:
        raise RuntimeError("HOMEWEAR_ACCEPTED_BASELINE_CHANGED")
    write(protection_path, protection)
    # The new sheet shares the wide-group aspect and broad poses. This first
    # crop is explicitly provisional; no point here claims anatomical registration.
    scale = 2284 / source.height
    resized_width = round(source.width * scale)
    enlarged = source.resize((resized_width, 2284), Image.Resampling.LANCZOS)
    crop_box = (2496, 0, 3296, 2284)
    crop = enlarged.crop(crop_box)
    crop.save(inputs / "registration-draft.png")
    # A compact source crop for GPU model inference avoids running five people.
    source_box = (round(crop_box[0] / scale), 0, round(crop_box[2] / scale), 1536)
    source.crop(source_box).save(inputs / "naru-source-crop.png")
    provenance = {"spec": "family-homewear-source/1", "source": "inputs/source-group.jpeg",
                  "sourceSHA256": digest(copied), "sourceSize": list(source.size),
                  "sourceChannels": source.mode, "selectedCharacter": "naru",
                  "selection": "Fourth character, left to right, from the user-selected homewear sheet.",
                  "sourceCrop": list(source_box), "registrationCanvas": [800, 2284],
                  "draftOperation": {"resize": [resized_width, 2284], "method": "Pillow LANCZOS", "crop": list(crop_box)},
                  "registrationStatus": "DRAFT_NOT_MEASURED",
                  "sourcePixels": "Copied original JPEG. Cropping/resizing only; no retouching or invented hidden artwork.",
                  "protectedBaseline": "protected-baseline.json"}
    write(target / "source-provenance.json", provenance)
    rig = json.loads((baseline / "out/rig/rig.json").read_text())
    wanted = {"hip", "chest", "neck", "head", "boob_r", "boob_l"}
    write(target / "landmarks-draft.json", {
        "spec": "family-homewear-registration-landmarks/1", "status": "DRAFT_NOT_MEASURED",
        "coordinateSystem": "crop pixels, y down, origin top-left",
        "acceptedConfigAnchors": {b["name"]: b["at"] for b in json.loads((baseline / "config.json").read_text())["bones"] if b.get("name") in wanted},
        "protectedBoneNames": [b["name"] for b in rig["bones"]],
        "sourceLandmarks": None,
        "next": "Measure neck base, shoulder tips, clasped-hand centre, waist and feet against the accepted painting before garment attachment generation. The whole-sheet crop is a starting estimate only."})
    print(json.dumps({"status": "SOURCE_AND_BASELINE_PREPARED", "filesProtected": len(record),
                      "sourceSHA256": digest(copied), "registration": "DRAFT_NOT_MEASURED"}))


if __name__ == "__main__":
    main()
