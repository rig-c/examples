# Authored outline fields with disconnected art

This consumer authoring transform clips the accepted piecewise affine mesh field before rigc's normal build/check. It preserves each surviving source triangle cell's per-bone weighted bind-local coordinates. It does not edit Spine exports or source RGBA. The inherited authored triangle clipping implementation is the frozen tol3 helper SHA256704fa12bb0a6cf9dc57a3cbe59dbd3d9546856aeb0087ea9973b72cde39716c4; this extension adds deterministic derived-mask diagonal closure, separate contiguous island slots, fail-closed policies and exhaustive coverage/field checks.

From the repository root, install with `bun install --cwd family/tools/outline-field-islands --frozen-lockfile`. Dependencies are pinned by package.json and bun.lock: parts1.25.0, rig-c2.57.0, official Spine4.3.13 and polygon-clipping0.15.7. The PNG reader imports a **private implementation subpath** of the pinned parts package; that path is not a promised stable public API. Geometry uses the published rig-c/mesh API.

Run only through the standard nova-run four-CPU/4GiB guard. Author the accepted material baseline first. The canonical source config contains preserved unvalidated material candidate overlays and must not be blindly rebuilt as the served physics baseline. For Nova, generate topwear background spacing60 and apply the committed reduce-nova-rigid-interior authoring recipe first; its255v444t topwear and214v276t bottomwear are protected by the full semantic rig hash in this policy. Source PNGs remain untouched.

The committed `<character>/outline-field-islands.source.json` and `.source.mesh_report.json` are exact frozen preclip author inputs, not inferred replacements. They include the accepted Nova density payload. The current unchanged output motion/images remain their measured companions. Replaying does not require reconstructing overwritten inputs or using dirty source config.

For Jinni, run from the repository root into a fresh candidate directory (Luna uses `--parts hair_front`; Nova uses `--parts hair_back,hair_front` and the matching character paths):

```sh
mkdir -p candidate/jinni/source candidate/jinni/out/rig
cp family/jinni/outline-field-islands.source.json candidate/jinni/source/rig.json
cp family/jinni/outline-field-islands.source.mesh_report.json candidate/jinni/source/mesh_report.json
cp family/jinni/out/rig/motion.json candidate/jinni/out/rig/motion.json
cp -R family/jinni/out/rig/images candidate/jinni/out/rig/images
bun family/tools/outline-field-islands/clip-field-islands-guarded.ts \
  --input candidate/jinni/source/rig.json --motion family/jinni/out/rig/motion.json \
  --images family/jinni/out/rig/images --output candidate/jinni/out/rig/rig.json \
  --parts hair_front,earring --policy family/jinni/outline-field-islands.json
bun --bun run ./family/tools/outline-field-islands/node_modules/.bin/rigc build --rig candidate/jinni/out/rig/rig.json --motion candidate/jinni/out/rig/motion.json \
  --out candidate/jinni/out/build --profile rig-play --pack --page-edges free --pack-shape polygon
bun --bun run ./family/tools/outline-field-islands/node_modules/.bin/rig-parts check --rig candidate/jinni/out/rig --parts family/jinni/out \
  --out candidate/jinni/out/check --page-edges free --pack-shape polygon --seam-pairs
```

The output directory must differ from the source rig directory. Existing output rig, provenance or mesh_report.json is refused before writes. Pre-copying only unchanged motion/images into the fresh output is allowed. A source attachment must be a weighted mesh with exactly `<part>.png` as its image and no attachment sequence. The frozen snapshots and policies are the measured authoring input, while the public config's former grid remains only its upstream recipe; actual emitted topology is the authored contour recorded in the regenerated report.

The policy hashes a recursively key-sorted semantic rig/motion JSON using JavaScript JSON number serialization, and exact source PNG bytes. A changed rig, motion, image or dependency refuses by name. The tool refuses linked meshes, target setup entries, deform/sequence/slot timelines, and any draw-order timeline rather than silently discarding or incompletely remapping them. Policy changes are a new measured authoring decision, not a way to bypass a refusal.

Every alpha≥1 source pixel center must be covered exactly once across the target pieces. Every new triangle must lie within one original triangle cell and reproduce its per-bone weighted field at all three vertices. These conditions are checked before writes. The tool updates mesh_report.json with actual union counts, source-generator provenance and per-piece identities. No region fallback, pixel deletion or new painted connector is used.

Jinni hair_front and earring each become two meshes. The original slot/attachment stays first; a sibling named `<part>__island2` immediately follows, with the same bone/color/blend and the original full image/path/UV domain. Original slots keep their order and settings. Both pieces reference one shared atlas region. Positive-alpha union and no-double-paint measurements are mandatory; a partial original slot's coverage is not full-image coverage by itself.

The derived mask uses alpha≥1, Chebyshev dilation4 and closed-polygon simplification3. Nova rear contains two ambiguous diagonal corners after dilation; filling two *derived mask* pixels closes those pinches. This changes no source pixel. Its authored fit improves74.793048→11.401754px excess with full alpha coverage. **It does not satisfy the rejected parts contour generator's4px guarantee** (the earlier T1/M2 candidate measured11.7047px). This authoring route has its own measured fit debt; it does not claim that generator promise. The accepted original public-parts output was already authored topology, so A21/A28 generator-topology checks were already SKIP and remain SKIP; no newly applicable assertion or user invariant was disabled.

Accepted final mesh counts:

| Character/part | Before v/t | After v/t |
| --- | --- | --- |
| Luna front |52/74|156/174|
| Jinni front, sum of two slots |41/50|105/112|
| Jinni earring, sum of two slots |13/12|29/26|
| Nova rear |78/120|193/234|
| Nova front |56/80|202/221|

Final per-character totals: Luna1173v1669t, Jinni685v971t, Nova904v1217t. Hair clipping increases these counts; the previous outfit-only Nova reduction remains intact. Luna/Jinni rear meshes are unchanged.

Paired9wind profiles at60Hz, including48/96gust and stronger±100/200stress, measure native/core, bones and protected geometry delta0. Uniform and boundary inversion fractions equal baseline in every profile; source-UV maximum is Luna0.00006669px, Jinni0.00006070px and combined Nova0.00008980px. Existing Jinni lower-strand folds and other pre-existing hair folds remain; this does not claim fold repair. Source alpha≥1 coverage is complete: Luna57495, Jinni front31707/earring2219, Nova rear134620/front62829 pixels. All source PNGs remain byte-identical.

Natural official parser/build and public parts check passed for each composed character. Frozen guarded replay reproduces the measured authored payloads exactly; negative controls cover changed source, target deform/slot attachment, draw-order, linked mesh and setup attachment. These checks establish the current frozen fields, not arbitrary future deformation robustness.

`measurements.json` keeps the per-part absolute coverage and authored fit, all9 paired motion profiles (including original/candidate fold counts and inversion fractions), exact final counts, and reviewed helper/control hashes. Full-alpha coverage and sampled motion are different instruments; the measured boundaries remain explicit.

## Final family attachment composition

Current Jinni outputs additionally apply [the guarded behind-ear strand stage](../../jinni/BEHIND_EAR_STRAND.md): replay this clipping helper from the frozen source, then apply `tools/apply-jinni-behind-ear-strand.ts` with `jinni/behind-ear-strand.json` into a fresh rig directory, then run normal official build/check. The side strand is bound to `head` and drawn behind the ears/face but above the shoulder, preserving the source curl. The earlier Jinni lower-strand fold measurements above describe the clipping intermediate; the linked final-stage measurements cover its correction. Original bang/rear-hair stress distortions remain outside that correction.

The frozen inputs and counts above describe the accepted hair-clipping intermediate. The current Roa/Luna/Nova outputs additionally apply [the final mesh-repair stage](../../MESH_REGION_REPAIR.md). Replay this helper first, then apply the character's guarded `mesh-repair.json` into another fresh authoring directory, then run official build/check. That last stage changes only the approved topwear attachments and restores Nova's original364v576t trousers; it preserves the clipped hair payloads exactly. Do not stop at this historical intermediate or regenerate it from dirty material configs.
