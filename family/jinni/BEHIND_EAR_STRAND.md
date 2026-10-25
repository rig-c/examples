# Jinni's behind-ear side strand

> **Historical stage record (retired in `rig-c/parts-examples#69`):** `family/jinni/config.json` now declares `meshes.earring.explicit.islands` and `meshes.hair_front.explicit.islands` (`hair_front__island2` bound to `head` with `before: "ear_l"`) on `@rig-c/parts` `1.63.0`. `rig-parts rig` emits the island attachments and slot placement directly from `config.json`, retiring both `clip-field-islands-guarded.ts` and `apply-jinni-behind-ear-strand.ts` (no character uses either post-pass script anymore).

The historical Jinni authoring order was **frozen source → guarded outline-field-islands clip → guarded behind-ear strand binding/depth → normal official build/check**. The clipped intermediate alone is no longer the current Jinni output. This final stage changes only the disconnected side strand; the other four characters keep their existing final stages.

The source painting shows a side strand emerging **behind the ear**, following the left neck edge and curling onto the shoulder. The old separation upgrade explicitly reconstructed that curl in `head:front hair` (`scripts/upgrade_jinni_4x.py`, the block beginning `INCLUDE THE COMPLETE NECKLINE HAIR CURL`). Consequently the disconnected `hair_front__island2` inherited front-bang weights and was drawn last, above the ear and face. Gusts pulled its upper end into the cheek. Splitting its mesh islands had preserved this incorrect semantic ownership.

This correction keeps the original image, UVs and 26-vertex/25-triangle island. It binds that island rigidly to `head`, preserving every old weighted setup-world vertex through the inverse head transform (maximum measured residual 1.4210854715202004e-14). Its slot moves from index25 to11, after the body/shoulder and before both ears and the face. The existing front-bang island remains in its original front layer. The historical island identifier stays unchanged to preserve attachment/atlas identity; it no longer implies front-bang depth or binding.

Drawing this strand behind the entire body was rejected: it hid the source neck-edge/shoulder curl and failed the public parts seam check (1344.23 rig pixels over40 versus a50-pixel bar). Keeping it above the shoulder but behind the head surfaces reproduces the source occlusion. No source pixel is removed, repainted or added.

## Replay

First run the existing guarded outline-field-islands transform from the committed frozen Jinni source, as described in [its README](../tools/outline-field-islands/README.md), into a fresh intermediate directory. Then apply this measured stage into another fresh rig directory; pre-copy the unchanged motion and images into that final directory. Do not rebuild the dirty material configuration as a substitute for these frozen inputs.

```sh
bun family/tools/apply-jinni-behind-ear-strand.ts \
  --input candidate/jinni/intermediate/rig.json \
  --motion family/jinni/out/rig/motion.json \
  --images family/jinni/out/rig/images \
  --policy family/jinni/behind-ear-strand.json \
  --output candidate/jinni/final/rig.json
bun --bun run ./family/tools/outline-field-islands/node_modules/.bin/rigc build \
  --rig candidate/jinni/final/rig.json --motion candidate/jinni/final/motion.json \
  --out candidate/jinni/build --profile rig-play --pack --page-edges free --pack-shape polygon
bun --bun run ./family/tools/outline-field-islands/node_modules/.bin/rig-parts check \
  --rig candidate/jinni/final --parts family/jinni/out \
  --out candidate/jinni/check --page-edges free --pack-shape polygon --seam-pairs
```

Use the normal nova-run four-CPU/4GiB execution guard. The new stage has only Bun/Node built-in imports; the normal build/check uses the existing pinned tool package. Its policy pins the complete input rig, motion, source mesh report, every image and the exact measured output rig. The measured bind table is independently checked against the original weighted setup-world coordinates before any write. All other rig payloads must remain identical. Changed inputs, an incorrect bind table, unexpected output and an occupied/same-directory destination refuse without writing. The clipping proof retained in the mesh report describes the preceding clipping stage; `behindEarStrand` records this subsequent binding/depth correction explicitly.

## Measurements and limits

[behind-ear-strand.measurements.json](behind-ear-strand.measurements.json) records the raw run IDs and measurements. The selected candidate passed the natural Spine4.3.13 build (27 measured assertions,23 SKIP) and the public parts check (11 measured bars,0 SKIP). The initial candidate-comparison batch exited1 because the deliberately rejected behind-body comparator failed; that is kept distinct from the selected candidate's successful build/check.

Paired60Hz calm12s, gust48/96 at2.4s over12s, and positive/negative base100+peak200 at20s over24s give zero native/core pose difference, zero protected-attachment difference and zero bone difference. The corrected island has zero folded triangles in every sampled profile; the original reaches14 under positive stress. Other existing front-bang/rear-hair distortions under high stress are unchanged and are not claimed fixed. Original source alpha coverage and mesh counts stay unchanged.
