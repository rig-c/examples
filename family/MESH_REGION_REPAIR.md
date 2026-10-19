# Chest regions and Nova trousers: final authoring stage

> **Historical stage record:** This document records the initial office `chest-regions.json` and Nova trousers/cuff authoring stage. Subsequent 5×3 outfit calibration (`office`, `homewear`, `swimwear`), Luna upper/forearm split, Roa/Luna hand-weight decoupling, and the canonical `config.json` + `declared-repairs.json` (`x-repairs`) reproducibility gate are documented in [README.md](./README.md#현재-승인된-입력과-재검증).

The attachment stage changes Roa, Luna and Nova `topwear` geometry/weights and restores Nova's complete 364-vertex/576-triangle trousers. Within that attachment stage, bones, bone anchors, constraints, stops, idle motion and source PNGs remain identical to the previously accepted assets. The topwear deformation field intentionally changes; unchanged physics parameters do not imply unchanged texel motion.

Existing `config.json` and `scripts/upgrade_*_4x.py` contain unrelated material candidates. They are not the source for a wholesale current-output rebuild. Each `chest-regions.json` records only the approved public `rig-parts rig` topwear settings. Each `mesh-repair.attachments.json` freezes the corresponding publicly generated **authoring rig attachments**, before the ordinary compiler gate. The companion `mesh-repair.json` checks the original attachment, replacement attachment, complete bones/constraints/stops context, motion bytes and image bytes. It changes only named attachments, preserves other authoring state, and updates only their mesh report rows. An unexpected source/payload/image/bone/motion or occupied output directory is refused; the recipe is deliberately not an idempotent operation over its own result.

## Regions in crop pixels

Coordinates are the 800×2284 character crop, x toward screen-right and y down. `boob_r` is screen-left, `boob_l` screen-right. Centres describe the authored clothing deformation field, not measured anatomical ground truth. The official public generator supports circles and polygons; these ellipse-like contours are 32-sample polygons quantized to its 1/256-pixel grid.

| Character | Screen side | Core centre | Core semi-axes | Linear band | Deliberate change |
| --- | --- | --- | --- | --- | --- |
| Roa | left/r |296,640|38×49|28|Expand fully moving core and upper dense area; outer support semi-axes approximately66×77 |
| Roa | right/l |438,638|40×52|28|Expand core upward; outer support approximately68×80, bounded near raised hand |
| Luna | left/r |308,785|26.3984375×26.3984375|43.19921875|1.2× original22-pixel core and36-pixel band; clip medial core at x326.80078125 |
| Luna | right/l |436,785|26.3984375×26.3984375|43.19921875|Same 1.2× change; clip medial core at x417.19921875 |
| Nova | left/r |295,756|32×46|20|Move toward the forward white-shirt volume, upward/left and elongated vertically |
| Nova | right/l |394,776|24×42|20|Move toward the inner jacket volume; reduce influence over the flat outer jacket |

Luna's outward/vertical support radius is approximately69.6px, versus58px before. Medial support stops at x370 and x374, leaving a4px gap under the public generator's no-overlapping-region rule. The first candidate used band20 and a much larger full-weight core; it was rejected because that changed the core much more than1.2×. Both current Luna breast bones already had actual weighted vertices before this repair; the screen-right complaint was not evidence of a missing bone or centre occlusion. The repair expands the actual authored field on both sides.

| Target | Before v/t | Final v/t |
| --- | --- | --- |
| Roa topwear |376/646|448/790|
| Luna topwear |372/635|420/731|
| Nova topwear |255/444|265/459|
| Nova bottomwear |214/276|364/576|

Nova's retired interior reduction produced long sliver fans. The restored payload is the original public source topology, including all148mixed/cuff triangles and every source binding. The compatibility helper `reduce-nova-rigid-interior.ts` now retains and checks that original source; it cannot restore the reduced214-vertex input on its own. The guarded attachment recipe performs that restoration when replaying the frozen hair inputs.

## Reproduce the complete composition

The tracked `outline-field-clip.source.json` / `outline-field-islands.source.json` and their policies remain the frozen upstream hair authoring inputs. Their historical chest/pants values are intentional inputs, not the final output. First replay the existing hair clipping exactly as its README describes, using current unchanged `out/rig/images` and `out/rig/motion.json`. For Roa copy the current `out/rig/mesh_report.json` into that fresh intermediate directory too; its clip tool does not write a mesh report. Luna/Nova's island tool creates it from the tracked `.source.mesh_report.json`.

Then, from the repository root, apply the final attachment stage to each intermediate directory:

```sh
CHAR=roa # or luna or nova
INTERMEDIATE=/absolute/path/to/fresh-clipped-rig
FINAL=/absolute/path/to/new-final-rig
bun family/tools/apply-family-mesh-repair.ts \
  --source-rig-dir "$INTERMEDIATE" --out-rig-dir "$FINAL" \
  --policy "family/$CHAR/mesh-repair.json"
```

For Nova, apply the cuff stage below to `FINAL` and use its fresh output as the build input.

Install the exact dependencies in the existing outline helpers with their frozen locks. Run the normal official `rigc build --profile rig-play --pack --page-edges free --pack-shape polygon` and `rig-parts check --page-edges free --pack-shape polygon --seam-pairs` on `FINAL`, with that character's current assembled parts. No Spine export is patched, and the attachment authoring stage does not certify emitted artifacts or provide a validation bypass.

Replaying the tracked hair inputs followed by this guarded attachment step reproduces all three final authoring rigs exactly. Source/payload/bone/stop/image/motion and occupied-output negative controls are refused. The public generator baseline topwear and bone table independently reproduce the pre-change accepted input for all three characters.

## Measured acceptance

All three final compositions pass the official Spine4.3.13 build and public parts check with pinned parts1.25.0/rig-c2.57.0. Native and core poses agree at tolerance0 over nine12-second60Hz conditions: calm, constant±48/±96, normalized48/96gusts, constant200stress, and the existing18/-10 moved/release gesture at0.5/0.59s. All bone matrices and every non-target attachment are identical to baseline; Nova bottomwear is excluded only from this non-target comparison and has its own retained-source verification. Both baseline and final topwear have zero folding readings in this scope. These are sampled motion conditions, not a proof for arbitrary future animation.

Matched native chest images at the same animation/stimulus phase were directly inspected before application. Public check's loop measurement explicitly excludes physics constraints; it does not replace the separate live-physics comparison above. Source RGBA, hair clipping fields and accepted non-target clothing repairs remain unchanged.


## Nova narrow-cuff physics correction

The restored source trousers retained the original cuff dynamics. That retained a real motion defect: the narrow cuff mesh inverted under wind and exposed rectangular red texels beside the ankles. The source painting has narrow structured trouser openings. At matched 60Hz native poses, the existing 48/96 gusts produced up to5/9 inverted triangles, and constant+200/-200 stress produced23/30. Restoring source topology did not fix this motion defect.

The final Nova stage removes exactly `cuff_r0_phys`, `cuff_r1_phys`, `cuff_l0_phys` and `cuff_l1_phys`. It preserves all89bones, all attachments/UVs/weights/triangles, source images, stops and every motion byte. The small authored idle cuff rotations remain (root amplitude0.3°, tip0.9°); the cuffs no longer receive physics or wind. Chest, hair and all other constraints remain unchanged.

After the frozen hair stage and `apply-family-mesh-repair.ts`, run:

```sh
bun family/tools/apply-nova-cuff-physics.ts \
  --source-rig-dir "$FINAL" --out-rig-dir /absolute/path/to/fresh-nova-cuff-rig \
  --policy family/nova/cuff-physics.json
```

Then run the same normal official build and public parts check on that fresh output. The full source-rig hash enforces this order; it refuses a different rig or an already corrected result. Motion bytes, every source image and the expected output rig are separately guarded. An occupied output, changed bone, changed motion, changed image and non-cuff target are negative controls. Permanently setting the four mixes to0 was rejected by the existing `A23_PHYSICS_CONSTRAINT_EFFECTIVE` gate; removing those declarations expresses the intended absence of physics without weakening the gate.

Measured scope: nine12-second conditions at60Hz: calm, constant±48/±96, 48/96gusts and constant±200. Final bottomwear has0inverted triangles in every sampled frame. Native/core vertex delta is0; every non-cuff bone matrix and every non-bottomwear attachment is identical to the accepted input, including chest and hair. The official Spine4.3.13 build passes with21physics constraints; public parts check measures10/10bars and passes. Its existing `RECOMPOSITE_HOLES` report remains a report about source assembly, not a new seam certificate; its animation-fold bar excludes physics, so the separate live-physics comparison is required. These measurements cover the stated conditions, not arbitrary future animation or other stimuli.

The paired96gust renders below use the same camera and phase (frame50 at60Hz). The rectangular ankle protrusion is present before the change and absent after it. Mesh topology and source pixels are identical.

| Existing cuff physics | Cuff physics removed |
| --- | --- |
| ![Before: inverted narrow cuff](nova/docs/cuff-physics-before.png) | ![After: narrow cuff preserved](nova/docs/cuff-physics-after.png) |

Raw measurements and execution provenance: [`nova/cuff-physics.measurements.json`](nova/cuff-physics.measurements.json).
