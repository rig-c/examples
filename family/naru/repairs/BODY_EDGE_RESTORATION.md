# Naru body edge restoration

[Issue 16](https://github.com/rig-c/parts-examples/issues/16) restores the shoulder, sleeve and forearm contours lost by the earlier low-resolution masking process. This is a consumer asset correction. No public package, runtime sampling, physics setting, motion track or original painting changes.

## Evidence and cause

The accepted native painting retains fractional alpha. The previous upgrade thresholded its alpha at 220, eroded it by 2 native pixels, then sampled a binary mask into a 1024-square layer. That layer represents the 2284-pixel-tall figure, so each layer texel spans approximately 2.23 native pixels. Assembling restores sharp interior painting pixels but retains the stepped silhouette. Only 7 of 25,788 positive upper-shirt layer texels had fractional alpha.

The assembled part is pixel-identical to its padded rig image and atlas region. The atlas declares Linear filtering; the served player also sets both WebGL texture filters to LINEAR. Changing the renderer would leave the damaged matte in place.

A second defect was already in `painting_rgba.png`: removing the detached pale strand with the rectangle `x < 218, y = 575..690` also removed part of the real left shoulder. The unmodified group image preserves that shoulder. `body-edge-evidence/shoulder-source-compare.png` shows both stages.

## Narrow production repair

`family/tools/apply-naru-body-edge.py` consumes the accepted rig, parts and unchanged paintings under `body-edge-policy.json` preimage hashes. It writes fresh output directories and emits no Spine artifact. Python requires Pillow, NumPy and SciPy. The runtime directory must contain public `@rig-c/parts` 1.25.0; the measured gate also uses `rig-c` 2.57.0 and Spine 4.3.13.

The policy states three separate operations:

1. Restore the native painting's RGBA only in an 8-pixel strip along the exposed shoulder and sleeve silhouette. No texture is resized.
2. Recover the accidentally clipped shoulder from the unmodified group crop. For each selected row, choose the opaque interval containing shirt-interior column 300. Only its adjacent alpha fringe is copied; the detached pale strand stays excluded.
3. Restore the two forearm/cuff boundaries over the skirt within explicitly bounded source-coordinate trimap strips. The group image is already an opaque composite there, so it contains no independent foreground matte. This alpha is **inferred from source RGB**, using the policy's luminance interval 40..65. It is not claimed to be an original separate alpha channel. Source RGB supplies the pixels; no new artwork is painted or generated.

The resulting crop is `(154, 599, 493, 426)`, padded by 4 pixels for the rig image, `(501, 434)`. Its extra transparent domain covers the expanded mesh without out-of-range UVs. Source-coordinate texture registration is preserved.

Of 324 topwear vertices, only 61 exterior hull vertices move, by 6 native pixels along the source-derived outward normal. Their bone names and weight coefficients are unchanged. All 229 interior vertices and the other 34 hull vertices retain their exact bindings; all 551 triangle index triples are unchanged. The 90 adjacent triangles change shape, with zero orientation reversals. Their full change list is in `out/rig/body-edge-restoration.provenance.json`. Historical contour-generation figures are explicitly nested as `sourceContourReport` in `mesh_report.json`; they are not presented as fresh measurements of the repaired boundary.

The collar, shirt-core and clasped-hand protected pixel boxes each have 0 changed pixels. Motion bytes, all bone/constraint/stop data, other attachments, and every other rig image are unchanged. The accepted generated rear hair remains intact. The opaque count is remeasured at the public `alpha > 8` threshold. The mandatory projection/merge/seam counters retain the original assembly execution trace and explicitly exclude this later edge repair. The optional visibility set is omitted because this transform does not recreate the original run visibility masks; their old values remain historical in `sourcePartRecord`. The flat recomposite is remeasured with the public parts APIs.

## Validation

Final Nova run: `20261016T154001Z-c40393de403b45b4bf23b58082f6234e`. `body-edge-validation.json` includes the sealed result and receipt, including rejected earlier attempts.

- Ordinary `rigc build --profile rig-play --pack --page-edges free --pack-shape polygon`: 27 measured assertions passed, 23 skipped, official Spine round trip present.
- Ordinary `rig-parts check --seam-pairs`: 10 of 10 bars measured and passed. Idle strain severity is 1.112 against the unchanged ceiling 1.926544.
- Paired calm, gust 48 and gust 96: 361 samples per condition at 60 Hz over 6 seconds. Native/core posed-vertex difference, all bone differences, every other slot, and all 263 unchanged topwear vertices are exactly 0. No topwear folds occur. The modified adjacent triangles' maximum true-setup strain is 1.019302.
- Metadata-only follow-up: the public `readParts` reader accepts the omitted optional visibility set. An exact comparison proves that these three removed fields are the only `parts.json` change after the final full gate; geometry, pixels, mandatory assembly counters and recomposite are unchanged. See `body-edge-metadata-check.json`.
- Repaired opaque texels outside the mesh: 0 in the source-coordinate coverage control. Protected collar/core/hand changed pixels: 0. A mismatched preimage policy is refused before creating output directories.

The public check leaves physics out of its keyed loop and fold measurements and says so. The additional paired motion run includes the original physics. Gust 200 and physical-device rendering were not measured for this boundary-only change.

`body-edge-evidence/` contains matched native renders and the source comparison. Browser checks are recorded separately by the integrating task. Reproduction requires the preceding accepted inputs matching the policy, rather than rerunning the old all-character upgrade script over these repaired outputs.

```sh
python3 family/tools/apply-naru-body-edge.py \
  --source-rig-dir ACCEPTED/naru/out/rig \
  --source-parts-dir ACCEPTED/naru/out \
  --painting-rgba ACCEPTED/naru/inputs/painting_rgba.png \
  --painting ACCEPTED/naru/inputs/painting.png \
  --group-rgba ACCEPTED/group_4096x2284_animesharp_rgba.png \
  --policy family/naru/repairs/body-edge-policy.json \
  --runtime-dir PINNED_PUBLIC_PACKAGES \
  --out-rig-dir FRESH/rig --out-parts-dir FRESH/parts
```

Run the ordinary build and parts check on those fresh directories before using their outputs. The transform's `APPLIED_UNBUILT` message is not a gate verdict.
