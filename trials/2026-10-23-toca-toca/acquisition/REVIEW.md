# Reviewed external acquisition recipe

The supplied CPU recipe is used as external input acquisition. It is not a
shipped rig-pose command. The toolchain starts at rig-pose clean 1.0.1.

Preserved: RTMPose Wholebody balanced, YOLOX-M detector, rtmw-dw-x-l pose
model, CPU ONNX backend, largest eligible body-17 vertical extent for person
selection, body-18 joint names, shoulders' midpoint neck, score cut 0.3,
coordinate rounding to one decimal and score rounding to three decimals.

Reviewed changes, recorded before inference:

| Change | Reason |
| --- | --- |
| Explicit package versions and hashed requirements | Replace an unpinned package install with a reproducible environment |
| Exact local ONNX files and SHA-256 checks | Keep the existing balanced model choice and refuse changed weights |
| Headless OpenCV only; rtmlib installed without automatic dependencies | Avoid three overlapping OpenCV distributions; CPU inference APIs are unchanged |
| Four ONNX intra-op threads, one inter-op thread, sequential execution | Respect the shared job's four-worker budget without editing package files |
| Correct Toca Toca / YouTube Shorts HSug-0AAp3k source | Fresh output identifies its actual source; creator not identified |
| Parameterised video, model and output paths | No private path in the published recipe |
| Files instead of JSON console markers; progress every 30 frames | Preserve structured artifacts without flooding the raw log |
| Three-frame precheck and explicit input/count assertions | Refuse a wrong input or ineligible person before the full extraction |
| Raw pose and optional whole-body evidence kept separate from cleaned pose | Acquisition pose.json is not the trial root's cleanedpose.json |

Original recipe digest is recorded in pins.json. Exact review diffs remain in
private evidence. No existing pose frames are read or reused. No reference
image or video frame is written by these scripts.

Run from the trial directory, with the withheld original and hash-matching
public models supplied at the named relative paths:

```sh
sh acquisition/run.sh --video withheld/orig.webm --models withheld/models --out work/precheck --frames 0,246,491
sh acquisition/run.sh --video withheld/orig.webm --models withheld/models --out work/acquisition
```

The full run's body-18 work/acquisition/pose.json is copied to
acquisition/pose.json only after the recorded checks pass. Whole-body raw data
and detailed private logs remain outside the public trial deliverables.
