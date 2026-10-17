# Luna homewear prototype

The local family viewer can replace Luna's office model with this homewear model while preserving the accepted 800x2284 stage, the exact idle `motion.json`, and `original common 77 bones + 14 head/hair attachments compared at every same-phase frame`.

## Validation Summary

- `rig-parts check --page-edges free --pack-shape polygon`: `PASS=True` (`gate_spine_html_green=True`, `seam_mean=0.154`, `seam_px_over_40=9`)
- `runtime/physics.json` (`official Spine4.3.13; exact all posed bone matrices and attachment vertices`, 6 scenarios x 721 frames @ 60 Hz): `PASS=True` (`commonBoneMaxDelta=0`, `commonAttachmentMaxDelta=0`, `bustBoneMaxDelta=0`, `foldingTriangleReadings=0`)
