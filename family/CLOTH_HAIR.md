# Clothing and hair profiles

Historical stage record: the profiles and commands below describe the original clothing/hair change, before the later mesh, cuff, strand, texture and silhouette repairs. Current configs also contain unadopted material experiments. Do not execute this config regeneration over the final accepted assets. Use the [final-input build/check route](README.md#현재-승인된-입력과-재검증) for the current demo; reproducing this earlier experiment requires its exact historical baseline. In particular, Nova's four cuff physics declarations below were later removed by the [final cuff stage](MESH_REGION_REPAIR.md#nova-narrow-cuff-physics-correction).

This local family-demo experiment is tracked in [issue #8](https://github.com/rig-c/parts-examples/issues/8). It changes authoring inputs, not the physics solver. Names such as `skirt_r` are historical identifiers: Roa wears wide trousers, Nova wears slim trousers, Luna and Naru wear fitted skirts, and Jinni wears a loose pleated skirt.

## Authoring boundary

The accepted bust profile is unchanged: both `boob_*` constraints, their bones, all topwear mesh coordinates/UVs/weights, hem chains, and existing motion tracks retain their baseline values. Global wind is not multiplied. Hair and lower clothing have separate per-constraint wind coefficients. Constant wind changes a spring's equilibrium; the accepted bust inertia gain changes its response to movement, not equilibrium wind gain.

No source painting or extracted part is regenerated. The upgrade scripts carry matching future-authoring values, but were not executed: they also perform image processing, which is outside this change.

| Character | Hair/back wind by link | Bang wind by link | Lower clothing |
| --- | --- | --- | --- |
| Roa | 0.96, 2.4, 4.32 | 2.925, 6.825 | Existing trouser chains: wind 0.32, 0.6, 1; existing idle retained |
| Luna | 0.88, 1.65, 2.53 | 0.625, 1.375 | New two-link lower-edge chains: wind 3, 6; idle amplitudes 0.875, 2.75 degrees |
| Nova | 0.5, 0.95, 1.45 | 0.42, 0.91 | New two-link cuffs: wind 0.8, 1.4; idle amplitudes 0.3, 0.9 degrees |
| Jinni | 0.4, 0.8, 1.2 | 1.125, 2.475 | Existing skirt chains: wind 0.35, 0.65, 1; existing idle retained |
| Naru | 0.875, 1.625, 2.5 | 0.75, 1.5 | Existing fitted-skirt chains: wind 0.25, 0.4, 0.6; existing idle retained |

Only wind changes on existing hair/clothing constraints; their stiffness, damping, mass and inertia are retained. New Luna/Nova chains have explicit parameters in their configs. Luna's upper skirt and hands/documents overlap area is hip-bound; Nova's upper trousers, knees and central support remain hip-bound. The former whole-part `not_swinging` requirement is replaced by a narrower measured fixed-region contract, since the user now requests moving lower edges. That is an intentional authoring change, not permission to bypass the parts check.

## Reproduce

Use public `@rig-c/parts@1.25.0`, `rig-c@2.59.0`, and `@esotericsoftware/spine-core@4.3.13`. Use native Node for the official CLI launcher and Bun for the TypeScript probe. Run builds and verification through the repository's required `nova-run` admission and aggregate process-tree 4-CPU/4-GiB guard. Preserve a complete pre-change family snapshot before regenerating anything.

For each character, using its saved parts rather than invoking image extraction:

```sh
rig-parts rig --config family/NAME/config.json --parts BASELINE/NAME/out --out OUTPUT/NAME/rig
rig-parts check --rig OUTPUT/NAME/rig --parts BASELINE/NAME/out --source BASELINE/NAME/inputs/painting.png --out OUTPUT/NAME/check
bun family/tools/check-cloth-hair.ts --baseline BASELINE/NAME/out/check/build --candidate OUTPUT/NAME/check/build --rig-baseline BASELINE/NAME/out/rig/rig.json --rig-candidate OUTPUT/NAME/rig/rig.json --out OUTPUT/NAME/runtime --render
```

Add `--fixed-source-y 1450` for Luna and `--fixed-source-y 1750` for Nova. Those source-pixel boundaries are authored protection contracts, not measurements inferred from generated art. Execute all characters and retain each failure before reporting the aggregate result.

The probe runs 721 samples at 60 Hz over 12 seconds, with gravity zero, idle looping and winds 0, 1, 3, 4 plus the viewer's existing phase-zero `sin(t*2.2)*2 + sin(t*5.1)*0.8`. Twelve seconds covers several component cycles, not the full joint waveform period. Animation advances by dt; physics uses the player's `dt + dt*2^-30` callback. This is a controlled offline comparison, not a browser interaction claim or the viewer's `moved` jolt input.

Every posed bone matrix and drawn vertex is compared to official Spine 4.3.13 at tolerance zero. The report separately measures the unchanged bust/topwear, wind-zero common geometry, exact fixed vertices, protected clothing regions, weighted root response, winding reversals, edge-length ratios and wind response. A part with no exactly fixed vertices is reported as unmeasured for that metric; its most-anchor-weighted vertices are measured separately against head (hair) or hip (clothing). Missing required mesh data is a named refusal. Edge ratios and response magnitudes are observations, not declarations that a material looks natural.

Matched renders use the official native poser: full body at 800 px high, and a head crop at source scale. Wind 0/3 renders cover the first four seconds at 12 fps; autoGust renders cover twelve seconds at 12 fps. Numerical geometry continues at 60 Hz. Raw setup PNGs are taken before any animation is applied. Optional side-by-side video packaging must not prevent later characters' measurements.

## Measurement corrections and limits

An earlier probe called the idle first frame “setup”; Luna's newly authored nonzero first rotation keys produced about 0.1888 px of intended idle deformation there. That number is not a serialization error. The current probe obtains true setup before applying animation and retains its raw UV-to-world mismatch and unrelaxed `exactPASS` separately from motion checks. Rounded emitted UVs and weighted bindings can prevent exact coordinate identity; a green motion report does not silently turn a nonzero raw setup result into an exact pass. Compare the actual setup raster and silhouette as well.

An earlier weighted-root fallback searched for head weights on clothing. Jinni's clothing has no such weights; its failed report was a probe role error. The corrected probe uses the clothing's hip anchor and still requires actual weighted vertices and a smaller root response than the moving part. Earlier reports remain historical evidence under their original definitions.

[Luna source-quality issue #9](https://github.com/rig-c/parts-examples/issues/9) remains separate: hidden patch-shaped pixels occur in bottomwear beneath the hands/documents layer. This experiment does not repaint them or certify their safety under arbitrary future hand poses. Source asymmetry is preserved; no bust symmetry or artwork correction is performed. Numerical safety and offline images do not replace the user's final material-motion judgment. Public demo publication/PR merge remains a separate decision.
