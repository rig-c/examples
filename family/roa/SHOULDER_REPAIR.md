# Roa shoulder: source-backed restoration

The screen-left shoulder became flat and indented when hair moved aside. The assembled topwear PNG already contained the depression: the old upgrade script's guessed shoulder polyline deleted original cloth alpha. In crop x 160..235, y 445..500, 186 opaque original full-run pixels became transparent, all inside that exact trim condition. At x 170 the opaque shoulder edge moved down 17.844 crop pixels. The original head-run topwear retains smooth shirt cloth behind the hair.

The final stage restores only crop x 130..225, y 465..506 from that original head-run layer. It resizes the 1024 run to its measured 440 crop with Pillow LANCZOS, retains original alpha where it exceeds the existing cut edge, and blends source RGB over 4..18 pixels inside that edge. No collar, neck, waist or hair is replaced. The raster changes 2528 pixels, 971 of them gaining alpha. Five existing outer-hull vertices 98..102 expand to cover the restored shoulder. The 448 vertices, 790 triangles, 104 hull entries, scalar bone weights and every other UV/local coordinate remain unchanged. No remeshing or changed chest field is needed.

## Replay

Install Pillow for the guarded image check. Use the accepted pre-repair `roa/out` at commit `144f55676754543704911f651fda55f377e7c1fe` after the frozen hair/chest stages; retain its original `inputs` beside it. The policy refuses any changed authoring input, motion, image, source-art hash, unexpected input file or occupied output. It is deliberately not idempotent over its own result.

```sh
python3 family/tools/apply-roa-shoulder-repair.py \
  --source-out /absolute/path/to/accepted/roa/out \
  --out /absolute/path/to/fresh-roa-shoulder \
  --policy family/roa/shoulder-repair.json
```

The frozen PNGs and metadata are authoring payloads. The policy includes their hashes, original head-layer hash, exact crop/resampling/blend recipe and all five UV/local-coordinate changes. It checks the repair mask and matching parts/rig pixels independently. The original full-run visibility counts are preserved in provenance, but omitted as one optional group from the changed topwear row: a final PNG cannot reconstruct the old assembly pixel-ownership trace. Current opacity is recounted from alpha > 8, and recomposite figures are measured again with the public parts API.

Run the ordinary gated compiler and public check on the fresh output:

```sh
rigc build --rig FRESH/rig/rig.json --motion FRESH/rig/motion.json \
  --images FRESH/rig/images --out FRESH/build --profile rig-play \
  --pack --page-edges free --pack-shape polygon
rig-parts check --rig FRESH/rig --parts FRESH --source family/roa/inputs/painting.png \
  --out FRESH/check --page-edges free --pack-shape polygon --seam-pairs
```

## Measured acceptance

Pinned parts 1.25.0 / rig-c 2.57.0 / Spine 4.3.13 public build and check pass. Check measures 10 of 11 bars and explicitly skips BLINK_NO_HOLE. Pixel-centre coverage at alpha >= 1 loses 0 new pixels and covers every newly restored pixel. Existing full-texture uncovered faint pixels remain a separate baseline observation (289 before, 261 after); this restoration does not claim to repair all assembly defects.

Paired official-native and core poses at 60 Hz cover calm and the existing 48/96 gusts for 4 seconds each, including a full idle cycle. Native/core vertex delta is 0. Every bone matrix, every non-topwear attachment and all 443 protected topwear vertices have 0 difference. Both rigs have 0 topwear triangle inversions in these samples. No arbitrary wind or future animation claim is made.

The same gust96 frame 72 exposes the original notch and the repaired continuous shoulder:

| Before | After |
| --- | --- |
| ![Indented shoulder](docs/shoulder-before.png) | ![Restored original cloth](docs/shoulder-after.png) |

The first alpha-only candidate was rejected because the former cut edge retained a dotted white RGB seam; the final source-RGB blend removes it. Guard controls include a positive replay and refusal of changed motion, a changed bitmap, an interior-vertex patch and an occupied output. [Raw measurements](shoulder-repair.measurements.json) retain the sampled scope, execution receipt hash, old statistics and current recomposite report.
