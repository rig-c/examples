#!/usr/bin/env python3
"""Read back office protection records and, when present, the variant's common rig.

This verifies preservation, not garment appearance or compiler acceptance.
"""
import hashlib
import argparse
import json
import pathlib

parser=argparse.ArgumentParser();parser.add_argument("--require-variant",action="store_true");args=parser.parse_args()

family = pathlib.Path(__file__).resolve().parents[1]
home = family / "outfits/homewear/naru"
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
result = {"spec": "family-homewear-protected-check/1", "officeFilesChecked": len(record["files"]),
          "variantPresent": variant.is_file(), "errors": errors}
if variant.is_file():
    baseline = json.loads((family / "naru/out/rig/rig.json").read_text())
    rig = json.loads(variant.read_text())
    for field in ["bones", "constraints", "stops"]:
        required=baseline.get(field,[])
        found=rig.get(field,[])
        if found[:len(required)] != required:
            errors.append({"field": field, "reason": "accepted common entries or their order changed"})
    if baseline.get("skeleton") != rig.get("skeleton"):
        errors.append({"field":"skeleton","reason":"accepted stage changed"})
    old_motion = (family / "naru/out/rig/motion.json").read_bytes()
    new_motion = (home / "out/rig/motion.json").read_bytes()
    if old_motion != new_motion:
        errors.append({"field": "motion", "reason": "accepted motion bytes changed"})
    common = [s["name"] for s in baseline["slots"] if s["name"] not in ["shoes", "legwear", "bottomwear", "neck", "topwear"]]
    for name in common:
        old = baseline["skins"]["default"].get(name)
        new = rig["skins"]["default"].get(name)
        if old != new:
            errors.append({"slot": name, "reason": "protected face/hair attachment changed"})
        for attachment in (old or {}).values():
            image = attachment.get("image")
            if image and (family / "naru/out/rig/images" / image).read_bytes() != (home / "out/rig/images" / image).read_bytes():
                errors.append({"image": image, "reason": "protected face/hair PNG changed"})
    result["commonSlotsChecked"] = common
if args.require_variant and not variant.is_file():
    errors.append({"field":"variant", "reason":"completion mode requires the authored variant"})
result["completionMode"] = args.require_variant
result["status"] = "FAIL" if errors else ("PRESERVATION_PASS" if variant.is_file() else "SOURCE_PREPARATION_PASS_VARIANT_PENDING")
print(json.dumps(result, indent=2))
raise SystemExit(1 if errors else 0)
