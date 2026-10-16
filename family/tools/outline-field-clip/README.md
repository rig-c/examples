# Preserve the accepted deformation field while fitting a contour

Historical intermediate: the replay commands below require this stage's exact preimage images and metadata. Later Roa shoulder and Naru generated-hair/body-edge repairs changed some current `out/` files, so substituting those final images may correctly trigger a preimage refusal. Use a matching historical input revision for this stage, or the [final accepted-input build/check route](../../README.md#현재-승인된-입력과-재검증) for the current demo. Do not regenerate policies to accept a mismatch.

This consumer authoring transform clips weighted triangles in a reviewed public rig input. It does not patch emitted skeleton indices or bypass rigc. For each cut vertex, it interpolates each named bone's homogeneous contribution `(weight, weight*x, weight*y)` in its original triangle. It preserves the existing mapping through motion. Shared vertices are welded at 1e-9 image pixels. Interior stars merge only when every contribution is affine within absolute 1e-9; boundary and non-affine stars stay.

Dependencies are exact versions in package.json and bun.lock. From this directory, install with `bun install --frozen-lockfile`. `bun controls.ts` runs 16 self-contained positive and negative controls; use a fresh working directory or remove only your previous disposable control output first.

## Rebuild the reviewed inputs

Run from `family/tools/outline-field-clip`. Choose `CHAR=roa` or `CHAR=naru`, and a **new**, empty author output directory:

```sh
CHAR=roa
WORK=/tmp/roa-outline-rebuild
mkdir -p "$WORK/rig"
cp -R "../../$CHAR/out/rig/images" "$WORK/rig/images"
cp "../../$CHAR/out/rig/motion.json" "$WORK/rig/motion.json"
bun clip.ts --input "../../$CHAR/outline-field-clip.source.json" --images "../../$CHAR/out/rig/images" --motion "$WORK/rig/motion.json" --parts hair_front,bottomwear --policy "../../$CHAR/outline-field-clip.json" --output "$WORK/rig/rig.json"
bun --bun run rig-parts check --rig "$WORK/rig" --parts "../../$CHAR/out" --out "$WORK/check" --page-edges free --pack-shape polygon --seam-pairs
```

Path correction: `--parts` names the saved-parts home containing both `parts.json` and `parts/`. The earlier `out/parts` argument named only the PNG subdirectory and is replaced by `out` above.

The per-character `.source.json` is deliberately the accepted pre-clip public authored input, including prior accepted neck/earring work. It is **not** claimed to be a fresh output of the current config: source configs also contain unvalidated material/region experiments. Do not regenerate this snapshot from those configs. The policy freezes parsed-JSON, property-order-sensitive SHA256 for the source rig, motion and attachments, plus raw PNG SHA256. A changed input refuses; author-policy.ts is for establishing a separately reviewed new policy, not an automatic update step. Generated provenance records the baseline/policy/image hashes and barycentric origins. Source PNGs are read only.

The accepted silhouette uses every source alpha>=1 pixel, a derived four-pixel Chebyshev dilation and tolerance-three contour simplification. An exact pixel-centre union-of-triangles check refuses any lost alpha>=1 pixel. It supports one filled dilated island only, no target deform timelines, no linked target attachments or cross-slot/skin linked parent references, no sequences, and only explicit weighted source-sized images. Unsupported topology and self-intersections refuse. It never changes bones, constraints, physics parameters or motion.

## Scope of the measurement

Accepted Roa/Naru hair and lower garments total 372v/580t before and 783v/979t after (+411v/+399t). This is a contour fidelity cost, not a density optimization. Twelve strictly affine interior Roa trouser vertices were removed after clipping; no non-affine region was coarsened. All alpha>=1 pixel centres remain covered. Nine matched 60Hz motion profiles retain baseline boundary/uniform inversion fractions; source-UV positions differ by at most 0.000104 pixels and all non-target posed geometry/bone matrices agree exactly. Existing folds are preserved rather than repaired. New edge directions can have different edge-strain maxima despite the same deformation field. Both normal official spine-core 4.3.13 builds/checks pass, including loop seam measurements.

Disconnected islands, target linked/deform data and other characters require a separately reviewed extension; do not silently weaken these refusals. A regular family config rebuild does not invoke this transform automatically: run this explicit authoring stage and the normal gate.

## Final family attachment composition

The frozen inputs and counts above describe the accepted hair-clipping intermediate. The current Roa/Luna/Nova outputs additionally apply [the final mesh-repair stage](../../MESH_REGION_REPAIR.md). Replay this helper first, then apply the character's guarded `mesh-repair.json` into another fresh authoring directory, then run official build/check. That last stage changes only the approved topwear attachments and restores Nova's original364v576t trousers; it preserves the clipped hair payloads exactly. Do not stop at this historical intermediate or regenerate it from dirty material configs.
