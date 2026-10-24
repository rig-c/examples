# 2026-10-25 Character 1 idle at twice the recording scale

## Question

Does rendering the accepted Character 1 idle at a larger `rigc render --max`
produce a lossless recording at least 492 pixels wide, retaining all 41
12-fps samples and a measured loop?

[APNG recording](idle-2x.apng) · [41-frame sheet](sheet.png) ·
[Machine-readable receipt](receipt.json) · [Encoder and verification](encode.mjs)

## Inputs

The input is the current accepted office Character 1 build,
[`family/roa/out/check/build/`](https://github.com/rig-c/examples/tree/40db33d91e4aacbe4cd31ac9f3cc557973b4a1d4/family/roa/out/check/build),
at examples commit `40db33d91e4aacbe4cd31ac9f3cc557973b4a1d4`.
The [accepted manifest](https://github.com/rig-c/examples/blob/40db33d91e4aacbe4cd31ac9f3cc557973b4a1d4/family/accepted-inputs.json)
and the Family guide identify that serving build as canonical. The receipt
records the exact model, skeleton, atlas and PNG hashes. They were read,
not rebuilt or edited. The site's historical `c239b09` build is not silently
substituted for this current accepted input.

Withheld: nothing; the inputs already exist in the public corpus. New raw
frame sets are reproducible outputs, deleted after the sheet verdict and
concatenated-PNG hashes were recorded. Acquisition, pelvis, clean and retarget
are not applicable: this trial reads an existing idle and acquires no video
or new pose sequence.

## Commands and pins

| Tool | Pin |
| --- | --- |
| rig-c | 2.68.0 |
| official spine-core | 4.3.13 |
| Bun | 1.4.2 |
| FFmpeg, independent decoder | 7.0.2-static |

Run from a checkout that **contains this trial** (the PR or a later merged
commit), not from the older input commit alone: that older commit predates
`encode.mjs` and `receipt.json`. `TRIAL` is an absolute path to these new trial
files. `INPUT_ROOT` may be this current checkout or a separate input checkout;
the setup verifies all four accepted input hashes before any rendering. The
historical commit identifies input provenance, not where the new script lives.

Choose a new empty output path for `WORK`. Install only into that workspace.
The exact package manifest and frozen Bun lock are preserved in `receipt.json`.

```bash
TRIAL="$PWD/trials/2026-10-25-character-1-idle-2x"
INPUT_ROOT="$PWD"
WORK="$PWD/idle-2x-reproduction"
python3 - "$TRIAL" "$INPUT_ROOT" "$WORK" <<'PYSETUP'
import hashlib, json, sys
from pathlib import Path
trial, input_root, work = [Path(p).resolve() for p in sys.argv[1:]]
assert (trial / 'encode.mjs').is_file(), 'TRIAL must contain the new trial script'
receipt = json.loads((trial / 'receipt.json').read_text())
source = input_root / receipt['source']
for name, expected in receipt['sourceInputHashes'].items():
    actual = hashlib.sha256((source / name).read_bytes()).hexdigest()
    assert actual == expected['sha256'], 'accepted input hash mismatch: ' + name
work.mkdir(exist_ok=False)
(work / 'tools').mkdir()
(work / 'tools/package.json').write_text(json.dumps(receipt['toolchain']['packageJSON'], indent=2) + '\n')
(work / 'tools/bun.lock').write_text(receipt['toolchain']['bunLock'])
print('PASS: current trial files and all four pinned accepted input hashes')
PYSETUP
BUN_INSTALL_CACHE_DIR="$WORK/cache" bun install --cwd "$WORK/tools" --frozen-lockfile --ignore-scripts
export BUN_INSTALL_CACHE_DIR="$WORK/cache"
export BUN_RUNTIME_TRANSPILER_CACHE_PATH="$WORK/transpiler"
bun --no-install "$WORK/tools/node_modules/rig-c/bin/rigc.cjs" render --candidate "$INPUT_ROOT/family/roa/out/check/build" --animation idle --fps 12 --max 1290 --poser core --out "$WORK/frames"
bun "$TRIAL/encode.mjs" preflight "$WORK/frames" "$WORK/tools"
bun "$TRIAL/encode.mjs" encode "$WORK/frames" "$WORK/tools" "$WORK/reference.apng"
bun "$TRIAL/encode.mjs" compress "$WORK/reference.apng" "$WORK/tools" "$WORK/idle-2x.apng"
```

Heavy rendering and encoding were run on Nova. The staged order was render
checkpoint → actual PNG/FFmpeg reader dry-run and metric controls → encode
that same checkpoint → independently decode and compare all 41 frames.
`rigc render --help` was read before choosing the flags. Inspect the sheet
and retain the receipt before deleting the newly rendered frame directory.
The script prints the concatenated PNG hash and a separately labelled measured
seam. `compress` uses the exact FFmpeg predictor arguments measured for the
selected candidate, then checks timing/repeat metadata and independent decoded
RGBA equality. The original compressed reference was retained throughout
candidate measurement. No rerender was used for optimization.

The README setup was extracted and executed with absolute `TRIAL` and
`INPUT_ROOT`: all four pinned source hashes, a fresh frozen install and the
actual renderer model/skeleton/atlas/PNG loader passed. This setup dry-run did
not render. It fixes PR #64 review
[discussion_r4367769592](https://github.com/rig-c/examples/pull/64#discussion_r4367769592).

## Measurement

The bar was fixed before rendering: width at least 492, all 41 samples at
12 fps, exact delay fractions and repeat metadata, and an explicit endpoint
and wrap measurement. HQ adopted the measured-wrap acceptance criterion: wrap RGB mean absolute
difference no larger than the largest adjacent RGB step. RGB ignores alpha;
the renderer's background is opaque `(232,232,232,255)`. Equal frames are the
zero control; a black-to-white pixel gives max/mean difference 255 and one
pixel over 40. Zero motion is handled without dividing by a zero step.

| Measured | Result | Bar / interpretation |
| --- | --- | --- |
| First producer, max 1280 | 488×1280 | FAIL width ≥492 |
| Final producer, max 1290 | 492×1290 | PASS width ≥492 |
| Renderer samples | 41 at 12 fps, t=0…40/12 s | All retained |
| APNG decoded frames | 41, all RGBA pixels equal to source | PASS lossless |
| APNG delays | 41 × exactly 1/12 s | PASS; no centisecond rounding |
| Encoded duration | 41/12 s = 3.416666… s | Includes every sample, including endpoint |
| APNG `acTL.num_plays` | 0 | Infinite repeat metadata only |
| First vs last max RGB difference | 212; 1,917 pixels over 40 | Observation only; exact endpoint equality is **not a bar** |
| Wrap mean absolute RGB difference | 0.44359887397323583 | ≤0.7597497951723703 maximum adjacent step: PASS smooth wrap |
| Physics stepped during render | 23 constraints at 12 fps | Not a physics-disabled keyed-loop check |
| Selected APNG size | 11,351,964 bytes | Predictor-optimized; lossless RGBA, error 0 |

The issue's expected 492×1280 is contradicted by the actual renderer. Its
unchanged world viewport rounds to width 488 at max 1280. Applying the real
renderer's `round(worldWidth * maxSide / worldHeight)` formula gives 1290
as the smallest integer longest side reaching width 492; only scale changes.

Measured wrap, **not a native renderer verdict**:

```text
measured wrap: idle 41 frame(s) at 12 fps, f0000 vs f0040: max |d| 212; wrap MAE 0.44359887397323583 vs max adjacent 0.7597497951723703 — PASS smooth wrap; different endpoints
```

The authored animation lasts 40/12 s; displaying every one of its 41 sampled
frames gives a 41/12 s file. No last frame was dropped, replaced or blended.
Infinite repeat metadata is separate from seam quality and endpoint identity.

| Retained output / deleted frame series | SHA-256 |
| --- | --- |
| `idle-2x.apng` | `bd31ad5b7d952733417a8ac830c40e73719f95ef0cdb8569e092c2bde3161f0e` |
| Final 41 PNGs concatenated in filename order | `85e0d85756b3efc384a01a235e38a2e9dc3f178dae626937cd3f511c407ec8d9` |
| Rejected 488-wide 41 PNGs concatenated | `2fa8b2b905dd788a3653aec38edff10bda4bddc3740439da7803d5e849459dd3` |

The sheet shows all 41 labelled samples with the figure within the viewport;
that small-sheet verdict does not establish endpoint identity. Both producer
frame sets (82 PNGs total) were hash-verified and deleted after this verdict.

### Native renderer boundary

**rigc emits no closure verdict; this is the measured wrap**

The original max1290 producer log has no `loop:` line. The 2.68.0
`rigc render --help` has no loop/closure check flag. Its implementation,
`src/cli/core_commands.ts:1030–1092`, prints samples, physics and the sidecar
path; `physicsLine` at 1117–1130 counts stepped constraints, not closure.
The actual printed line is:

```text
  ..    physics: 23 constraint(s) stepped at 12 fps
```

Native closure is **UNAVAILABLE**, not a native PASS or FAIL. A separate
`rig-parts check` loop definition excludes physics; it is not this renderer's
output. The first/last max difference of 212 is retained as an observation,
not promoted into an exact-endpoint acceptance bar.

### Measured optimization comparison

All candidates were encoded on Nova from the original compressed APNG, after
actual APNG/filter/codec reader preflight and zero/255 error controls. No
rerender was performed. Independent FFmpeg decode compared every candidate's
41 RGBA frames with the original 41 decoded renderer frames. Maximum error
below is the largest absolute difference over all RGBA bytes, on 0–255.

| Encoding | Bytes | Decoded frames / max RGBA error | Actual delays | Decision |
| --- | --- | --- | --- | --- |
| Original full-frame APNG | 17,453,151 | 41 / 0 | 41 × 1/12 s | Reference retained remotely |
| Predictor lossless APNG | **11,351,964** | **41 / 0; every byte identical** | **41 × 1/12 s** | **Selected** |
| Palette APNG, no dithering | 2,638,904 | 41 / 66 | 41 × 1/12 s | Rejected: not lossless |
| Palette GIF, no dithering | 2,253,537 | 41 / 66 | 8/100 and 9/100 s | Rejected: error and exact-timing failure |

All three measured candidates are 492×1290 with infinite-repeat metadata.
Predictor APNG saves 6,101,187 bytes (about 35%) while preserving every RGBA
byte. The smaller palette candidates are not labelled lossless or silently
accepted as near-lossless; no nonzero error budget was assumed. GIF's
centisecond clock cannot express an exact 1/12-second frame delay. The
receipt retains each candidate's SHA-256, all actual delay fractions and the
measured FFmpeg commands.

## Verdict

**PASS under HQ's owner-adopted measured-wrap bar** — wrap MAE
0.44359887397323583 ≤ maximum adjacent step 0.7597497951723703, with width,
all 41 samples, exact 12-fps delays, infinite-repeat metadata and lossless
decoded pixels preserved in the selected predictor APNG. Exact endpoint
equality is not a bar. **rigc emits no closure verdict; this is the measured wrap**.

## Rejected alternatives

- Max 1280: actual width 488 misses the size bar.
- Upscaling the old recording: would not rerender the accepted build.
- Dropping frame 40: violates the requested 41-frame preservation.
- Replacing/blending endpoints, changing motion or suppressing physics:
  would alter what this accepted build actually renders.
- GIF: centisecond timing cannot express an exact 1/12-second delay.

## Limits

One accepted office idle only. This proves no new rig, artwork, hand motion,
retarget, physics settlement or arbitrary-force quality. The rendering includes
physics; the stored parts-check loop with physics excluded is not a substitute
for these measured pixels. The APNG keeps the renderer's opaque
background and every source frame's decoded RGBA values, using lossless predictor
compression. It remains larger than the rejected quantized recordings. No browser playback or new full toolchain suite was run.
