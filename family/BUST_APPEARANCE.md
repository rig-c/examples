# Family bust appearance: measured cause separation

Historical diagnostic baseline: the measurements below belong to the named `e367287` snapshot, before the later [chest-field repair](MESH_REGION_REPAIR.md) and other final authoring stages. “Current” below means current at that investigation. The final demo has intentionally different topwear fields for Roa/Luna/Nova; these old texel displacements and influence areas were not remeasured on the final fields. Use the [final-input verification](README.md#현재-승인된-입력과-재검증) and per-stage evidence for the accepted output. This investigation separates causes on its frozen input; it does not establish the dominant cause of every later subjective impression.

Issue: https://github.com/rig-c/parts-examples/issues/10 . Local investigation record. The user-accepted jiggle, inertia1.35, constraints, anchors, weights and source artwork remain frozen. This document records diagnostic observations; it does not authorize a physics, weight or artwork repair. No browser execution or publication is claimed.

## Finding

**Observed:** All five paintings already contain unequal visible left/right clothing shapes, folds, pose or perspective. Those features remain in native unanimated setup and in the matched current animation with only the two bust constraints disabled. Current bust physics therefore does not create all of the unequal appearance. This is especially evident in Jinni/Nova's oblique view, Roa's raised arm and diagonal placket, and Naru's clasped hands and shirt folds. Source perspective is not classified as a defect.

**Measured:** The same jolt produces small left/right differences, rather than a large opposite-phase response: first free-rebound peak magnitudes differ by1.77–3.08%; first-peak timing is identical except Naru, whose peaks differ by one60Hz sample. The native and own-core normal poses agree exactly in the measured protocol. That demonstrates the actual current motion and excludes a native-versus-own runtime discrepancy here; it does not certify anatomical placement or subjective appearance.

**Confirmed separate contribution:** Roa's raised hand and Naru's clasped hand have visible skin texels inside the moving topwear mesh. The same texel follows the bust influence by up to3.369/2.303 source pixels respectively under the tested jolt. This is visible feature coupling, not evidence of a hidden duplicate hand becoming exposed. No double contour was observed in the inspected paired frames. A shirt badge following the shirt surface is legitimate and is not classified as a defect.

**Remaining conclusion boundary:** The exact dominant cause of the user's subjective “uneven breasts” impression is not established by this experiment. The matched images separate source-authored appearance, actual small side-response differences and hand coupling, but no anatomical center/volume ground truth or user-selected offending time/side exists in these inputs. It would be false to label a particular anchor wrong, make the art symmetric, or blame the accepted jiggle solely on this evidence. No repair is proposed for the accepted physics.

## Inputs and provenance

- Reported local baseline commit: `e36728718a9f31b515a9f8b367e603a8bfe8c030`. Git history was not independently queried as part of this diagnostic.
- Immutable baseline: `/tmp/naru-family-bust-appearance-baseline` —492 paths assembled exclusively from previously released immutable outputs, matching the current apply manifest. Manifest: `AUDIT-BASELINE-MANIFEST.json`, SHA256 `3c2c6778944d007b7d5193a5932320bcabd6a992d93343157ca8f77e715253b0`.
- Paintings: `/tmp/naru-family-bust-appearance-baseline/{roa,luna,jinni,naru,nova}/inputs/painting.png`. Current gated outputs are under each character's `out/check/build/`; authored rig inputs under `out/rig/`.
- The apply manifest does not list `out/parts.json`. Its unchanged crop metadata was copied from the older immutable `/tmp/naru-family-cloth-hair-baseline/{name}/out/parts.json`, with actual PNG dimensions/padding checked. This auxiliary metadata is not claimed to have been independently read from the current commit.
- Frozen viewer player SHA256: `7be0dface8eb043aca97e88c51741f82090c80def401e62c9b598b2c928097aa`. No read of the concurrently repaired serving tree.
- Fresh public runtime dependencies measured by both runs: `rig-c@2.59.0`, official `@esotericsoftware/spine-core@4.3.13`; each evidence directory contains `versions.json`. Native Node22.16.0 was bootstrapped from the official release with checksum verification; Bun1.4.2 executed the probes.

## Controlled experiment

Consume already gated assets without rebuilding or changing them. Each native diagnostic parses the original Spine JSON into memory and changes only named `boob_r_phys` / `boob_l_phys` constraint `mix` to0. No diagnostic rig is emitted. Other animation, body pose, environmental inputs, renderer and viewport remain the same. Every source skeleton file is hashed before/after and unchanged.

Roa/Naru: normal, both-bust-off, right-off and left-off; idle3s, jolt3s and phase-zero autoGust12s. Luna/Jinni/Nova: normal and both-off only, idle3s and jolt3s. The latter intentionally does not repeat the first pair's full ablations/autoGust run. The generic wind descriptor in run2 report protocol is not evidence of an autoGust execution: its actual `conditions` contain only idle/moved, and its one-side additivity is `null`, not0.

Animation `idle`, looptrue, phase0. Gravity `[0,0]`; wind0 except `2*sin(2.2*t)+.8*sin(5.1*t)` in the first pair's autoGust. Jolt packet `physicsTranslate(18,-10)` at.5s, inverse at.59s. Physics elapsed time is `dt+dt*2^-30`, matching the frozen player's `physicsClockStep`. Measurements60Hz, with exact.59s sample; renders exact12Hz. Jolt is applied at the start of the following integration interval. This is a controlled consumer reproduction of the public APIs, not a browser event/phase-offset test.

Source/crop coordinates are pixels, y-down. World conversion: sourcex=worldx+400; sourcey=2284-worldy. Chest viewport is source `[150,450,650,1050]`,500×600 at1:1. The source and unanimated setup use the same source coordinate window; the painting has no animation time. Every normal/off pair uses exactly the same posed animation time and viewport. Source/setup need not be pixel-identical because the already existing parts extraction/compositing and sampling are different.

Free rebound is calculated after release.59s as `(moved normal − moved off) − (idle normal − idle off)`, at matched time. This removes the animated idle's forcing. Total forced excursion is not reported as free rebound.

## Actual results: all five

| Character | r first peak Y(px) / time(s) | l first peak Y(px) / time(s) | Magnitude difference | First-peak time difference | Unaffected topwear vertices |
| --- | --- | --- | --- | --- | --- |
| Roa | -5.177125 / .650000 | -5.273119 / .650000 |1.854% |0 |209 |
| Luna | -5.334646 / .616667 | -5.429127 / .616667 |1.771% |0 |262 |
| Jinni | -5.247731 / .633333 | -5.357619 / .633333 |2.094% |0 |103 |
| Naru | -5.307969 / .616667 | -5.471680 / .633333 |3.084% |.016667s |198 |
| Nova | -5.338174 / .616667 | -5.475183 / .616667 |2.567% |0 |225 |

Magnitude difference is `abs(l)/abs(r)-1`, not a breast-size measure. These are bone motion responses, not reconstructed3D volume. Peaks/next extrema are preserved in raw `isolated-moved-minus-idle.json` and `report.json`.

All measured normal-versus-own-core bone matrices and all drawn vertices: maxdifference0. All normal/off unaffected topwear vertices: maxdifference0. Topwear inverted/zero-area triangle readings:0 over the measured samples. All skeleton hashes unchanged. Roa/Naru one-side contribution additivity residual0; remaining three not measured. Idle/moved182 samples per mode; first pair autoGust721 per mode. None of these controls establishes a correct anatomical center.

## Source shape and weight-field distinctions

Directly viewed all five paintings and all five source/setup/current-moved/off panels. Roa/Naru idle/autoGust paired panels at2.5s were also viewed. At the inspected times, removing bust physics retains the unequal drawn folds/visible contours already present in the painting:

| Character | Direct visual observation | Inference deliberately not made |
| --- | --- | --- |
| Roa | Raised arm, sloping shoulder/diagonal placket, distinct left/right shirt shadows already in original | That the larger-looking painted side has an incorrect breast size |
| Luna | Unequal lapel opening, oblique fold bands and head/shoulder pose already in original | That front-facing presentation requires symmetric anatomy |
| Jinni | Oblique torso/silhouette and off-shoulder fold pattern already in original | That near/far visible width should be equal |
| Naru | Tilted pose, clasped hands, badge and unequal cloth-fold patterns already in original | That badge motion is faulty or that both breasts must share an image-space centerline |
| Nova | Strongly oblique torso, blazer covering a different fraction on each side already in original | That image-space asymmetry demonstrates physical volume inequality |

Static weighted2D cloth area was independently calculated from current authored mesh UV triangle pixel area multiplied by mean per-vertex side weight. It is a texture-plane influence measure, **not anatomy, visible body area or volume**. l/r ratios: Roa1.13091234; Luna1.00092625; Jinni1.06090784; Naru1.00031778; Nova1.00050086. Thus Roa has a materially unequal authored influence footprint, but nearly equal Naru/Luna/Nova footprints do not remove the source's unequal drawn appearance. This is not a common all-five unequal-weight-area defect.

No authored vertex has positive weights from both `boob_r` and `boob_l` in all five. Image-left authored field is r, image-right l. Anchors and circular influence centers are data, not measured anatomical ground truth: Roa r(296,650),l(438,650); Luna anchors(315,785)/(430,785), circlecenters(308,785)/(436,785); Jinni(384,724)/(514,720); Naru(312,785)/(448,785); Nova(312,775)/(435,785). The source pose/perspective prevents declaring these correct or incorrect from a circle overlay alone. No semantic left/right swap is demonstrated by the measured coordinates.

Current bust channels are translation x/y, with no active bust ScaleX/rotation/Volume mode. Those2D weighted translations move painted folds and deform their influence boundary; they do not independently infer3D breast volume. Native parity for this case does not resolve the separate corePR1454 editor gate, which remains outside this investigation.

## Visible hand coupling: stronger evidence than the old static suspicion

Selected source texels are manually observed features, located in the authored UV triangle using the immutable parts crop plus mesh padding, then tracked barycentrically in posed native vertices. Exact source points and triangle IDs/coefficients are in raw `report.json`. For every rendered sample in the first pair's tested conditions, tracked hand points have3×3 topwear alpha255 and foreground alpha0. Source painting and topwear PNG RGBA are identical at the selected skin texels.

| Character/source point | Actual texel RGBA | Largest normal/off displacement in moved3s | Time | Interpretation |
| --- | --- | --- | --- | --- |
| Roa(490,657), raised-hand-A |238,131,109,255 |3.369470px |.516667s |Visible hand surface follows bust influence during forcing |
| Roa(504,657), raised-hand-B |191,90,85,255 |.971223px |.516667s |Same hand, lower influence |
| Roa(504,643), raised-hand-C |246,139,109,255 |.971223px |.516667s |Same hand, lower influence |
| Naru(436,833), clasped-hand-A |254,164,138,255 |2.066455px |.633333s |Visible hand surface follows bust influence |
| Naru(450,833), clasped-hand-B |254,169,140,255 |2.303353px |.633333s |Visible hand surface follows bust influence |
| Naru(464,735), shirt badge |235,143,64,255 |1.567986px |.633333s |Clothing feature; not a defect |

These maxima compare normal/off under the same animated pose, not moved-minus-idle free rebound. Roa's maximum occurs during the forward forcing interval. Units are full source/rig pixels:3.369px is about1.18 pixels at an800px-high full-character display,2.303px about.81 pixels. Severity must not be exaggerated from enlarged diagnostic crops.

Roa's raised hand is visibly part of topwear; the separate `handwear_r` is the other/down arm and precedes topwear in draw order. Naru has no separate handwear slot. **Correction to the earlier suspicion:** the present evidence does not show concealed duplicated skin revealed by moving cloth. It establishes a visible hand-texture segment sharing the cloth deformation. No two-hand/double-outline artifact was observed in inspected keyframes. An isolated hand-weight cleanup, if later wanted, needs a separate explicit boundary and preservation proof; it must not silently retune the accepted bust.

## Pixel evidence and navigation

Evidence directory: `/tmp/naru-family-bust-appearance-evidence/`.

- `{roa,luna,jinni,naru,nova}-source-setup-normal-off.png`: source crop / native true setup / normal moved / bust-off moved, t=.666667s for both lower panels. These are the first review targets.
- `{roa,naru}-idle-autoGust-normal-off.png`: actual idle normal/off and autoGust normal/off at2.5s.
- `{roa,naru}-hand-normal-off-nearest.png`: nearest-neighbor diagnostic hand enlargement; original source PNGs remain untouched.
- `measurement-summary.json`: derived raw landmark maxima and per-frame difference counts; `sha256.json`: evidence file hashes.

Normal/off at.666667s has24,330 changed pixels for Roa,12,624 Luna,20,332 Jinni,19,201 Naru,16,363 Nova out of300,000. This confirms the pair is not a duplicate/no-effect comparison; antialiasing also contributes to counts. It is **not** a breast-size or quality score. The material visual conclusion is in actual paired PNGs and selected texel displacement, not these aggregate counts.

Actual encoded videos, normal LEFT / bust-off RIGHT: each character's evidence folder contains `moved-normal-left-bust-off-right.mp4` and `idle-normal-left-bust-off-right.mp4`; Roa/Naru also `autoGust-normal-left-bust-off-right.mp4`. All12 encoding commands completed0. Selected PNG frames were directly viewed; MP4 generation is not claimed as browser/UI playback or complete human review of every frame.

## Probe and local execution evidence

The executed probes are standalone `probe.ts` files in the frozen run inputs identified below. They are offline diagnostic consumers of gated model/Spine assets, not product build bypasses or browser tests. The executed probes are local evidence inputs, not a tracked tool in this checkout. Preserve the accepted input assets and use the repository's Nova-run admission/resource rules for any new execution. The measurements below belong to the exact submitted standalone inputs; this document does not claim a run of a later repository copy.

These are **local evidence locations**, not distributable repository fixtures or a requirement that another checkout have the same `/tmp` paths. The original run inputs are `/tmp/naru-family-bust-cause-run1/probe.ts` and `/tmp/naru-family-bust-cause-run2/probe.ts`, with immutable input copies, guard and package manifests beside them. The run receipts retain the exact submitted command and input manifests. A new run needs its own actual session identity and preserved gated input assets; copying a receipt ID is not a reproduction.

| Receipt | Result | Held seconds | Probe peak RSS | Input SHA256 |
| --- | --- | --- | --- | --- |
| `20261015T200250Z-efcadbd7cddb4a9381a6801c29ac8aa2` | passed / exit0 |92.066352 |342,618,112bytes | `1c56f1562e3ec7d7b945667f3af1911337b701187af5902b9ef3f96ffcb1dc3d` |
| `20261015T200946Z-5deabe861c644a529d4c5bb0f715e228` | passed / exit0 |51.008429 |266,715,136bytes | `af0629742f19bc54b76ee56b23a982ec8eefa7eefe6bf72675f24ef96e9591a3` |

Both used the standard Nova pool,4CPU affinity,4GiB aggregate process-tree RSS cap and3600s timeout, without local fallback. Recovered evidence is under the local Nova state directory:

- `~/.local/state/nova-run/20261015T200250Z-efcadbd7cddb4a9381a6801c29ac8aa2/bust-cause/` — Roa/Naru; `report.json` SHA256 `95139087da6735fe65e57ba868262f497bf66f57d77e376959a6d01d9f6f7c69`.
- `~/.local/state/nova-run/20261015T200946Z-5deabe861c644a529d4c5bb0f715e228/bust-cause/` — Luna/Jinni/Nova; `report.json` SHA256 `0af128b050469c476a8668a568b7f8b6cdbdab6e2324e155418e5ae8a9f0d58f`.

Their parent directories retain `request.json`, `result.json`, `input-manifest.json` and `command.log`; the evidence folders retain raw traces, versions, budget readings, PNGs, MP4s and encoding exits. Standalone probe SHA256 values are `02e7b30b801862465ec560606a63a5cd8082708b123880220e5fcbe55a46fb5e` (run1) and `3918e9a40eb727ab1dd0b7f4859e1b5fe3e5a6a1ad197a8f71e2e719a15b0234` (run2). These exact inputs, rather than current mutable demo files, identify the experiment.

## Disposition

Keep accepted physics/anchors/weights and the original perspective intact. This investigation supplies all-five source/current/off visual comparisons and an actual visible hand-coupling finding; it does not establish a general “unequal anatomy” product defect, an anchor correction, a new physics solver requirement or permission to edit art. Luna hidden-surface repair is a separate texture-only scope; it does not change this investigation's frozen jiggle or establish a bust cause. Public familyPR5 remains held. If a further causal claim is wanted, target the exact visible side/time/feature in these paired artifacts rather than broadly changing every character.
