# Nova density authoring recipe

This consumer recipe regenerates the accepted Nova density geometry through the public compiler gates. Hair outline work is separate.

- The config and upgrade generator use topwear background spacing60 (the accepted baseline used36). Bust region shape/spacing/band, all bones, constraints and motion remain unchanged.
- `reduce-nova-rigid-interior.ts` retains its compatibility filename, but the trousers reduction is retired. The authoring step now retains the complete frozen source bottomwear attachment (364vertices/576triangles) before official build/check. It refuses a changed source attachment and requires its measured minimum angle, angle P10 and small-angle count. It never edits Spine exports, writes into its input, or changes textures.
- `geometry.postprocess.json` records pins, source-attachment identity, stage order and measured bounds. The helper lives in `family/tools/`; a consumer postprocess runner may call its exported function instead of its CLI.

## Reproducing the served baseline

The canonical source config also contains preserved, unvalidated material candidate overlays. Raw source config is not the served physics baseline. Start from a verified copy of the current live config/material recipe, change only topwear spacing to60, and run the complete authoring-transform/build/check sequence below. Keep the separate source candidate overlays intact; a blind rebuild from raw source config would apply those unvalidated settings. The recorded source-attachment hash and gates refuse a changed trousers field.

Use parts1.25.0/core2.57.0/officialSpine4.3.13. Heavy execution must use the normal nova-run guard, actual session metadata, four CPUs and4GiB. Public source generation is first, followed by this authoring transform and both standard gates:

```sh
bun --bun run rig-parts rig --config nova-config-with-topwear60.json --parts saved-parts --out fresh-rig-source
bun family/tools/reduce-nova-rigid-interior.ts --source-rig-dir fresh-rig-source --out-rig-dir fresh-out/rig
bun --bun run rigc build --rig fresh-out/rig/rig.json --motion fresh-out/rig/motion.json --out fresh-out/build --profile rig-play --pack --page-edges free --pack-shape polygon
bun --bun run rig-parts check --rig fresh-out/rig --parts saved-parts --out fresh-out/check --page-edges free --pack-shape polygon --seam-pairs
```

The source identity remains SHA256 `25ce5798f3f1a66362176a5c4ff7d8d83e6a3910938d948892e8d28c999de9da`. The prior 214vertex/276triangle result removed150hip-only interior vertices and retained the150-vertex hull plus148mixed/cuff triangles. That reduction is retired: its minimum angle fell from4.842579° to0.583181°, and triangles below5° rose from2to46. The checker measured those angles with undeclared bounds; current-motion agreement did not certify triangle quality. The repaired recipe retains all364source vertices/576triangles, every original binding and every cuff/mixed triangle. Its mandatory drawing-pixel bounds are minimum angle≥4.842578833857446°, nearest-rank angleP10≥24.776721222263504° and at most2triangles below5°. Counts identify the frozen source; they are not a replacement for those quality gates.

The helper retains the complete original attachment and every by-name bind-local position/weight. It records the source rig/motion/PNG hashes, source-fit measurement and mandatory triangle-quality report. Topwear and trousers must equal the independently measured attachments after composition; all other attachments/bones/constraints/stops/motion/images must match the chosen baseline. Combining disjoint hair clipping later requires that same guard and a final official build/check/browser review.

The helper imports `@rig-c/parts/src/raster/png.ts`, an implementation subpath of the explicitly pinned installed parts1.25.0 package. That reader is not claimed as a generic stable API; changing the pin requires revalidation. Art-fit measurement uses the documented public `rig-c/mesh` entry; the retired removal stage is not replayed.

Nine-profile result: native/core, bones and all non-target posed geometry delta0. Topwear352v/638t→255v/444t; all folds and sampled inversions0. Bust circle+weight-band sample max0.021376px, RMS≤0.000783px; whole-coat max3.802890px/RMS≤0.489040px. The earlier trousers364v/576t→214v/276t motion measurements remain historical evidence only: they did not protect topology quality. The accepted trousers topology is now the unchanged364v/576t source mesh, applied to the current rig independently of chest work. These are measured sampled deformation fields, not a blanket material-feel claim.

Absolute alpha≥1 coverage defects already present in the baseline remain: topwear90/240045pixels, trousers200/277833pixels. Neither candidate newly omits any previously covered positive-alpha pixel. Every source PNG is unchanged. This does not claim full-alpha repair. The paired nine-profile evidence is identified by Nova runs `20261016T123149Z-90cc9bdaf15e49c7b66546a03144da4a`, `20261016T123425Z-6b4f1730615c4b69ad4e78fc25a96114` and `20261016T123946Z-5ced22752cfd4b74b6d370e87e159394`. This recipe does not certify the remaining hair grids or eliminate existing cuff folds.

The current full composition also applies the [final chest/mesh attachment stage](../../MESH_REGION_REPAIR.md) after frozen hair clipping. Its guarded Nova payload restores the original trousers when the frozen intermediate still carries the retired214-vertex result. This retained-source compatibility helper alone does not restore that intermediate.
