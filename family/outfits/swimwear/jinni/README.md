# Jinni swimwear prototype

The local family viewer can replace Jinni's office model with this swimwear model while preserving the accepted 800x2284 stage, the exact idle `motion.json`, and `original common bones and head/hair attachments compared at every same-phase frame`.

## Validation Summary

- `rig-parts check --page-edges free --pack-shape polygon`: `PASS=True` (`gate_spine_html_green=True`, `seam_mean=0.14`, `seam_px_over_40=22`)
- `runtime/physics.json` (`official Spine4.3.13`, 6 scenarios x 721 frames @ 60 Hz): `PASS=True` (`commonBoneMaxDelta=0`, `commonAttachmentMaxDelta=0`, `bustBoneMaxDelta=0`, `foldingTriangleReadings=0`)
