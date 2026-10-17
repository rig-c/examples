#!/usr/bin/env python3
"""Prepare immutable source/protection records and source crops for remaining Family homewear characters.

Preserves accepted office artifacts and Naru's completed homewear prototype untouched.
"""
import argparse
import hashlib
import json
import pathlib
from PIL import Image

CROPS = {
    "roa": {
        "order": "First character, left to right, from the user-selected homewear sheet.",
        "groupCrop4096": [96, 0, 896, 2284],
        "sourceCrop": [64, 0, 602, 1536],
        "nonClothingExcludes": ["shoes", "legwear", "bottomwear", "neck", "topwear", "handwear_r"],
    },
    "luna": {
        "order": "Second character, left to right, from the user-selected homewear sheet.",
        "groupCrop4096": [896, 0, 1696, 2284],
        "sourceCrop": [602, 0, 1140, 1536],
        "nonClothingExcludes": ["shoes", "legwear", "bottomwear", "neck", "topwear", "handwear_r"],
    },
    "jinni": {
        "order": "Third character, left to right, from the user-selected homewear sheet.",
        "groupCrop4096": [1688, 0, 2488, 2284],
        "sourceCrop": [1134, 0, 1672, 1536],
        "nonClothingExcludes": ["shoes", "legwear", "bottomwear", "neck", "neckwear", "topwear", "handwear_r", "handwear_l"],
    },
    "nova": {
        "order": "Fifth character, left to right, from the user-selected homewear sheet.",
        "groupCrop4096": [3296, 0, 4096, 2284],
        "sourceCrop": [2214, 0, 2752, 1536],
        "nonClothingExcludes": ["shoes", "legwear", "bottomwear", "neck", "topwear"],
    },
}


def digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: pathlib.Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n")


def prepare_character(family: pathlib.Path, source_path: pathlib.Path, character: str) -> dict:
    spec = CROPS[character]
    target = family / "outfits/homewear" / character
    inputs = target / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)

    source = Image.open(source_path)
    if source.size != (2752, 1536) or source.mode != "RGB":
        raise RuntimeError("HOMEWEAR_SOURCE_EXPECTED_2752_1536_RGB")

    baseline = family / character
    paths = [
        baseline / "out/rig/rig.json",
        baseline / "out/rig/motion.json",
        baseline / "out/rig/mesh_report.json",
        baseline / "out/parts.json",
        baseline / "out/check/build/skeleton.model.json",
    ]
    paths += sorted((baseline / "out/rig/images").glob("*.png"))
    paths += sorted((baseline / "out/parts").glob("*.png"))
    record = {str(p.relative_to(family)): digest(p) for p in paths}

    protection = {
        "spec": "family-homewear-protected-baseline/1",
        "character": character,
        "files": record,
        "nonClothingExcludes": spec["nonClothingExcludes"],
        "rule": "Existing office artifacts are immutable. Copy accepted bones, constraints, stops, motion and non-clothing attachments; author only the new clothing variant.",
    }
    write_json(target / "protected-baseline.json", protection)

    source_box = tuple(spec["sourceCrop"])
    crop_im = source.crop(source_box)
    crop_file = inputs / f"{character}-source-crop.png"
    crop_im.save(crop_file)

    draft_im = crop_im.resize((800, 2284), Image.Resampling.LANCZOS)
    draft_im.save(inputs / "registration-draft.png")

    provenance = {
        "spec": "family-homewear-source/1",
        "source": "../naru/inputs/source-group.jpeg",
        "sourceSHA256": digest(source_path),
        "sourceSize": list(source.size),
        "sourceChannels": source.mode,
        "selectedCharacter": character,
        "selection": spec["order"],
        "sourceCrop": list(source_box),
        "sourceCropSHA256": digest(crop_file),
        "registrationCanvas": [800, 2284],
        "groupCrop4096": spec["groupCrop4096"],
        "sourcePixels": "Copied original JPEG crop. Cropping/resizing only; no retouching or invented hidden artwork.",
        "protectedBaseline": "protected-baseline.json",
    }
    write_json(target / "source-provenance.json", provenance)
    return {
        "character": character,
        "filesProtected": len(record),
        "sourceCrop": list(source_box),
        "sourceCropSHA256": provenance["sourceCropSHA256"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--characters", nargs="*", default=["roa", "luna", "jinni", "nova"])
    args = parser.parse_args()
    family = pathlib.Path(__file__).resolve().parents[1]
    source_path = family / "outfits/homewear/naru/inputs/source-group.jpeg"
    results = [prepare_character(family, source_path, ch) for ch in args.characters]
    print(json.dumps({"status": "WAVE_SOURCE_PREPARED", "characters": results}, indent=2))


if __name__ == "__main__":
    main()
