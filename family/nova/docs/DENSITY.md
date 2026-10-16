# Nova density authoring recipe

This consumer recipe regenerates the accepted Nova density geometry through the public compiler gates. Hair outline work is separate.

- The config and upgrade generator use topwear background spacing60 (the accepted baseline used36). Bust region shape/spacing/band, all bones, constraints and motion remain unchanged.
- `reduce-nova-rigid-interior.ts` is a consumer authoring transform using public `rig-c/mesh.reduceMesh`. It reads a fresh public parts rig and writes another **rig spec**, before official build/check. It never edits Spine exports, writes into its input, or changes textures. It retriangulates only the protected-boundary rigid interior and retains every mixed/cuff triangle and surviving original binding.
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

The transform is deliberately frozen to the measured Nova trousers attachment SHA256 `25ce5798f3f1a66362176a5c4ff7d8d83e6a3910938d948892e8d28c999de9da`, and to214vertices/276triangles. A changed attachment, package, deform timeline, linked topology, insertion, UV, mixed triangle or newly uncovered source pixel refuses by name. All82vertices carrying any non-hip weight are active. The112vertices and259edges of every mixed/cuff triangle, plus the150-vertex outer hull, are protected. All150removed vertices are hip-only. The result's long rigid slivers are justified by that frozen field, not claimed safe for future authored deformation.

The helper retains each surviving original by-name bind-local position/weight through the API indexMap. It records the source rig/motion/PNG hashes, reduction report, removal map and exact alpha counters. Topwear and trousers must equal the independently measured attachments after composition; all other attachments/bones/constraints/stops/motion/images must match the chosen baseline. Combining disjoint hair clipping later requires that same guard and a final official build/check/browser review.

The helper imports `@rig-c/parts/src/raster/png.ts`, an implementation subpath of the explicitly pinned installed parts1.25.0 package. That reader is not claimed as a generic stable API; changing the pin requires revalidation. The mesh reduction API itself is the documented public `rig-c/mesh` entry.

Nine-profile result: native/core, bones and all non-target posed geometry delta0. Topwear352v/638t→255v/444t; all folds and sampled inversions0. Bust circle+weight-band sample max0.021376px, RMS≤0.000783px; whole-coat max3.802890px/RMS≤0.489040px. Trousers364v/576t→214v/276t; sourceUV max0.000895px/RMS0.000289px; every existing fold/inversion count remains equal and no new inversion sample-frame appears. These are measured sampled deformation fields, not a blanket material-feel claim.

Absolute alpha≥1 coverage defects already present in the baseline remain: topwear90/240045pixels, trousers200/277833pixels. Neither candidate newly omits any previously covered positive-alpha pixel. Every source PNG is unchanged. This does not claim full-alpha repair. The paired nine-profile evidence is identified by Nova runs `20261016T123149Z-90cc9bdaf15e49c7b66546a03144da4a`, `20261016T123425Z-6b4f1730615c4b69ad4e78fc25a96114` and `20261016T123946Z-5ced22752cfd4b74b6d370e87e159394`. This recipe does not certify the remaining hair grids or eliminate existing cuff folds.
