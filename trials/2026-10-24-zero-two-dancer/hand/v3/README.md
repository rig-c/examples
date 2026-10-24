# Accepted v3 transfer, 2026-10-24

## Question

Can the owner's accepted v3 rig, motion and generated parts reproduce the
accepted dance frames with released tools, without another hand pass? **Yes:**
the compiled files and all 391 native frames reproduce byte for byte.

## Inputs

The owner selected v3 on 2026-10-24 in [#56](https://github.com/rig-c/examples/issues/56).
This directory transfers that existing result. It does not generate, re-rig,
retarget, repair or tune it. [inputs.json](inputs.json) binds each transferred
file to its original SHA-256, including the exact rig/motion bytes and three
PNG files. Their original relative `images` field is retained. Base images
are fetched from the trial's existing [corpus-inputs.json](../../corpus-inputs.json),
pinned to `06f994995a2adcae915c75edd8038586e0e3e781`, with each blob checked.

The underlying pose remains [the accepted source](../r3/inputs/sequence.json),
SHA-256 `8713172431674a57caa8d7c3f452a05bf46ec8079ca368bb4cd9df7952c2edfd`,
313 samples at 24 fps. Its declared camera normalization and inferred hips are
already in those values. Neither is reapplied. The animation is `zero-two-r3-hand`,
13 seconds, rendered non-looping at 30 fps including both endpoints (391 frames).

Origin: Zero Two challenge, [YouTube Shorts BGyjsZsWndA](https://www.youtube.com/shorts/BGyjsZsWndA),
creator not identified. Reference footage, audio, picture-in-picture and promo
cards are absent. The accepted digest is of native dance PNG bytes, not a promo
container, encoded video, pixel-only digest or text list of hashes.

| Version | Source date | Selection / retained record |
| --- | --- | --- |
| v1 | 2026-10-24 | Accepted R3/v5 transfer, [#52](https://github.com/rig-c/examples/pull/52), [#53](https://github.com/rig-c/examples/pull/53); [immutable R3 history](../r3/README.md) |
| v2 | 2026-10-24 | Owner's intermediate held-parts/jacket-strip pass, [#38 version record](https://github.com/rig-c/examples/issues/38); not promoted |
| v3 | 2026-10-24 | Owner-named final: generated chest-bound holds, permanent hip waist and compensated chest lift; this trial transfer, [#56](https://github.com/rig-c/examples/issues/56) |

## Commands and pins

Replay from the trial root, under a pooled aggregate 6 GiB/four-CPU limit that
also contains dependency installation and children. The measured execution used
Bun 1.4.2, Python 3.12.3, rig-c 2.67.2, spine-core 4.3.13, parts 1.60.0,
pose 1.0.1 and play 1.16.0 from the existing frozen `bun.lock`. Pose, parts and
play are installed dependencies; this replay invokes no retarget or inference.

```sh
mkdir -p work/v3-runtime
cp package.json bun.lock work/v3-runtime/
(cd work/v3-runtime && bun install --frozen-lockfile)
python3 hand/v3/reproduce.py --preflight
python3 hand/v3/reproduce.py --runtime work/v3-runtime --out work/v3-replay
```

The output directory must be new. The script verifies payload hashes, PNG chunk
hygiene, pose timestamps, and inputs through the actual rig/motion/pose readers.
It stages the original rig/motion bytes, fetches pinned public images and copies
the accepted three parts beside them. Within the staged trial it executes:

```sh
bun "$RIGC_CLI" build --rig hand/v3/rig.json --motion hand/v3/motion.json --out build --profile spine
bun "$RIGC_CLI" render --candidate build --animation zero-two-r3-hand --fps 30 --viewport-from "$TRIAL/hand/r3/viewport.json" --out render
```

`RIGC_CLI` is the installed `node_modules/rig-c/cli.ts`, and `TRIAL` is the input
trial directory. The core poser reads the compiled model. No path normalization
of the rig, motion or images is necessary. Build hashes are checked before
rendering; any mismatch stops without adapting values. [Generation provenance](generation/README.md)
records the historical inpaint, See-through and cutting steps; replay consumes
their accepted PNG outputs and never repeats those operations.

## Measurement

The acceptance bars were fixed before replay: original source bytes, all three
compiled hashes and the complete accepted native-frame digest must match exactly.
No tolerance, image similarity or fitted threshold substitutes for those bars.
[replay-result.json](replay-result.json) contains all 391 individual frame hashes;
[verification.json](verification.json) and [gate-lines.txt](gate-lines.txt) record
the completed run. Only 82,316 bytes of changed evidence were recovered; native
frames, runtime and generated build stay remotely retained.

| Artifact | Exact SHA-256 |
| --- | --- |
| `rig.json` | `a1860937f20890818a206a2b15318eaf2bf9e253d58584976b8aa9697f73e135` |
| `motion.json` | `46189464040b3ef8b42357399e1c8b0c1c4cbf6feedeabb24927eb09242f5aa7` |
| `images/arms_hold_head.png` | `6954c20fbe1bf3d988b4d1e9c8baff38f91d2549bb2a3ac2ee06d1907737318b` |
| `images/arms_hold_front.png` | `18b392875be888e28bf116edceede5e4c14cafe31554e192348f7de54db00701` |
| `images/waist.png` | `1c733bdf717741d98162c96439995d3cb6a009ddf1900bad4c9271a55712d5cb` |
| `skeleton.json` | `4e6024989f06a15525bf5cb32a47bb7aa55a75d8adf58505ce6b1a12efb49f77` |
| `skeleton.atlas` | `bd9d9414f016e94407a61685455888a7aad6781acdd9d634a0a9f3c0c432cdf1` |
| `skeleton.model.json` | `a94c7cbee992acaf87c0e283efc1bbd44766441f791776064e929bd59a2f0e81` |
| Concatenated `f0000.png` through `f0390.png` | `b75fc5696ac468f3ea9f58cc892d79389d66bf6ce7aeb31428f95350b9121029` |
| Existing viewport input | `8a0f07c4304419d64125314d773b3b0f62bacdd0229a40cc0cbdffa57545a13c` |

Native frames are RGBA 736×960, background `[232,232,232,255]`, 30 fps. The
fixed viewport is recorded in [accepted-render.json](accepted-render.json).
The SHA computation streams each complete PNG file in index order with no
separator. First frame `af7b4d3c2242b7146fc2f1580f9b3310a584c6c0f471badaf2bf18759c4f07e5`;
last frame `375a1429a70258d893d75f60b66440114d0eb19533cf5caf19ddca9d5ec6c53b`.
The new gate measured 23 PASS / 0 FAIL, skipped 13 and excluded 14 for `spine`.
All 11 skirt physics constraints remain present and step at 30 fps.

| Change | Before (v1) | Accepted v3 after / source | Could pose/parts derive it? |
| --- | --- | --- | --- |
| Head hold | Articulated K1 arms during a held pose | Generated H1 seed 1, 318×222 region on `chest`, selected f124–218; exact source PNG and placement transferred | Parts can represent it. Generated art and owner seed selection are not automatic pose derivation |
| Low hold | Articulated K2 arms | Generated H2z seed 53, 201×334 region on `chest`, selected f234–328; straight arms with crossed wrists | Parts can represent it; new painting and owner anatomy selection remain authored inputs |
| Lowering z-order | Back/under articulated slots | Base `forearm_r/upperarm_r/forearm_l/upperarm_l` in front slots f219–233; exact accepted attachment keys | A declared layer intent can be represented; this artistic choice was not inferred here |
| Waist | No permanent `waist` slot | H1m seed 62 painting historically cut and extended into the accepted 106×115 part, permanently on `hip` behind jacket/skirt | New generated skin is not derivable from missing base pixels. No new cut or extension was made here |
| Chest exposure / head compensation | `chest_ctl.translatey` 33 keys; no `head_ctl.translatey` track | Accepted +17u chest lift, −17u head compensation; eased f110→124 and f219→233; 62 chest keys / 31 head keys | A pose-card candidate for shoulder/chest lift intent; the scalar and compensation are accepted hand values, not newly inferred |
| Other motion / rig | v1 accepted keeper | 41 other bone tracks, all other animations, existing attachments, bone and constraint values unchanged; [delta record](transfer-delta.json) | Preservation, not a new hand pass or new LAND proof |

## Verdict

**PASS for this trial transfer:** the original source payload and accepted native
render reproduce exactly with released pins. Corpus promotion is a separate
second PR; `dancer/` is unchanged here. Existing v1/v2 records remain history.

## Rejected alternatives

No new alternatives were tried. The source record rejected hip-bound low holds,
baking flawed articulated holds, rotating/cropping hands inside an existing part,
and the intermediate v2 lifted-jacket swap. This transfer preserves the selected
v3 permanent waist instead. H1m seed 62 supplies the waist lineage, **not** the
final H1 seed 1 head-arm PNG; the shorter H2z front-arm cut is also not substituted.
The promo MP4, audio, PiP and source footage are not reproduction targets.

## Limits

This is a non-looping 13-second take; no loop-seam claim is made. The original
retarget's LAND 20/20 belongs before the historical hand foot-goal change. Its
v1 posthoc foot-goal residual and four-pair seam readings remain historical;
neither is newly measured by this transfer. Historical shins FOLD 269/391 is
preserved as a known limit, not hidden or counted green; v3 was rendered without
an additional fold/geometry diagnostic. All-rig seams and same-detector compare
remain NOT MEASURED. Profile skips and exclusions are not passes. There is no
new Play/browser verification and no new owner eye review beyond the source's
recorded acceptance. The public site consumer and post-transfer corpus are
separate work.
