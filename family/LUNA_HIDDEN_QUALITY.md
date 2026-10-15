# Luna hidden skirt surface

[Issue #9](https://github.com/rig-c/parts-examples/issues/9) separates saved-layer contamination from source pose/asymmetry. This repair changes only the lower-garment texture and its normal build descendants. The original painting remains unchanged. **The user-accepted bust jiggle is final: physics, anchors, weights and motion are frozen.** Completed clothing/hair authoring is also unchanged.

## Source and authored repair

The inspected original See-through layer (`inputs/layers/full_orig/parts/bottomwear.png`) and processed layer both retain object-shaped remnants; neither supplied a verified clean hidden surface. The existing upgrade script's nearest-source-color/blur operation is not a recovery of hidden cloth and was not rerun.

`luna/repairs/bottomwear-hidden.png` is an explicitly authored repair made with the built-in imagegen editor. Its raw output changed protected framing/waist details and was rejected as a whole-image replacement. Only generated RGB inside `bottomwear-hidden-mask.png` was technically composited into the original436×681 saved part. The original alpha is identical everywhere; every RGBA channel outside the mask is identical. Source/target/raw-output/final/mask hashes and the editing prompt are recorded in `bottomwear-hidden.json`. No original image was publicly attached.

The mask follows verified foreground handwear ownership and a bounded neighborhood containing old notebook/paper cast shadows and remnants. Removing an old object-dependent shadow from this part is an authored correction even where that shadow was visible in the original painting. The painting itself is preserved. The final mask additionally protects8125 originally exposed clean-cloth pixels at exact RGBA; candidate3 was rejected before application because two such samples changed by6–10 RGB. The source-backed exposed vertical cloth expression near source x390/y1030–1150 remains: sampled painting and bottomwear RGB agree, with both foreground alpha values zero. Existing topwear overlap near source (390,1180),(378,1180),(370,1200) remains separate and unchanged; this repair does not certify every other part's hidden surface.

## Reproducible saved-parts boundary

Use public `@rig-c/parts@1.25.0`, `rig-c@2.59.0`, native Spine4.3.13 for the oracle and Bun for the helper. All builds/verification use standard `nova-run` admission and4CPU/4GiB process-tree guards.

Retain the unrepaired saved part before application. The helper requires its exact recorded SHA; it refuses an unrelated or changed assembly rather than forcing a patch onto different art. An already repaired target is idempotent, but the baseline is still required to verify protected pixels.

```sh
cp "$lunaParts/parts/bottomwear.png" "$lunaBeforePng"
bun family/tools/apply-luna-hidden-repair.ts --parts "$lunaParts" --baseline "$lunaBeforePng"
rig-parts rig --config family/luna/config.json --parts "$lunaParts" --out "$lunaRig"
rig-parts check --rig "$lunaRig" --parts "$lunaParts" --source family/luna/inputs/painting.png --out "$lunaCheck"
```

Here `lunaParts` is the directory holding `parts.json` and `parts/`, and the remaining variables are explicit baseline/output paths. If reassembling from the unchanged source layers, apply this repair **after** assembly and **before** `rig`/`check`. The official assemble command writes its saved parts under `<out>/rig`; retain the original assembly's project/seam settings. A new assembly that does not reproduce the recorded baseline requires review. Do not run the broad `upgrade_luna_4x.py` as a repair command: it processes the painting and unrelated layers. The original `parts.json` projection counts describe the preceding assembly; the repair sidecar explicitly records the later authored RGB changes. Existing `out/recomposite*_rig.png` files likewise remain historical pre-repair assembly receipts; use the new gated render/reveal evidence to judge the repaired surface.

## Evidence and limits

Final candidate run `20261015T201825Z-9f7bf1096f704770b923449f603fc812` passed the ordinary gated build/full parts check and five matched12-second,60-Hz calm/steady/UI-autoGust conditions. Every native/core bone/vertex difference and bust/topwear difference is0. Rig, motion, emitted model/Spine and atlas bytes are identical to the accepted baseline; only texture/derived raster bytes differ. Alpha and outside-mask differences are0. The actual helper passed application/idempotence and refused a wrong baseline and a planted outside-mask RGB edit; that private fixture was restored.

An unchanged contaminated negative control and the repaired texture were rendered through the official native poser in the same crop. Diagnostic offsets of the existing `arms_hold0_ctl` expose the former patch region; they exist only in the offline consumer probe, never in product motion. Rest composites, cloth-only views and source/rest/moving comparisons are separate evidence. The original known cloth expression and existing topwear state are preserved rather than silently painted away. Numerical gates alone do not certify a convincing cloth surface; frozen paired images require independent visual review.

No browser inspection or public publication is implied. Perceived bust asymmetry has a separate investigation and is not attributed to this skirt repair.
