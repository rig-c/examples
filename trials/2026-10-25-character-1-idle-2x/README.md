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

Run from a checkout of the input commit. Choose a new empty output path for
`WORK`; install only into that workspace. The exact package manifest and
frozen Bun lock are preserved in `receipt.json`.

```bash
TRIAL=trials/2026-10-25-character-1-idle-2x
WORK="$PWD/idle-2x-reproduction"
python3 - "$TRIAL" "$WORK" <<'PY'
import json, sys
from pathlib import Path
trial, work = map(Path, sys.argv[1:])
receipt = json.loads((trial / 'receipt.json').read_text())
work.mkdir(exist_ok=False)
(work / 'tools').mkdir()
(work / 'tools/package.json').write_text(json.dumps(receipt['toolchain']['packageJSON'], indent=2) + '\n')
(work / 'tools/bun.lock').write_text(receipt['toolchain']['bunLock'])
PY
BUN_INSTALL_CACHE_DIR="$WORK/cache" bun install --cwd "$WORK/tools" --frozen-lockfile --ignore-scripts
export BUN_INSTALL_CACHE_DIR="$WORK/cache"
export BUN_RUNTIME_TRANSPILER_CACHE_PATH="$WORK/transpiler"
bun --no-install "$WORK/tools/node_modules/rig-c/bin/rigc.cjs" render --candidate family/roa/out/check/build --animation idle --fps 12 --max 1290 --poser core --out "$WORK/frames"
bun "$TRIAL/encode.mjs" preflight "$WORK/frames" "$WORK/tools"
bun "$TRIAL/encode.mjs" encode "$WORK/frames" "$WORK/tools" "$WORK/idle-2x.apng"
```

Heavy rendering and encoding were run on Nova. The staged order was render
checkpoint → actual PNG/FFmpeg reader dry-run and metric controls → encode
that same checkpoint → independently decode and compare all 41 frames.
`rigc render --help` was read before choosing the flags. Inspect the sheet
and retain the receipt before deleting the newly rendered frame directory.
The script prints the concatenated PNG hash and the actual `loop:` line.

## Measurement

The bar was fixed before rendering: width at least 492, all 41 samples at
12 fps, exact delay fractions and repeat metadata, and an explicit endpoint
and wrap measurement. The smooth-wrap criterion is wrap RGB mean absolute
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
| First vs last max RGB difference | 212; 1,917 pixels over 40 | Endpoints are **not identical** |
| Wrap mean absolute RGB difference | 0.44359887397323583 | ≤0.7597497951723703 maximum adjacent step: PASS smooth wrap |
| Physics stepped during render | 23 constraints at 12 fps | Not a physics-disabled keyed-loop check |
| APNG size | 17,453,151 bytes | Full-frame, lossless, unquantized |

The issue's expected 492×1280 is contradicted by the actual renderer. Its
unchanged world viewport rounds to width 488 at max 1280. Applying the real
renderer's `round(worldWidth * maxSide / worldHeight)` formula gives 1290
as the smallest integer longest side reaching width 492; only scale changes.

Actual measurement line:

```text
loop: idle 41 frame(s) at 12 fps, f0000 vs f0040: max |d| 212; wrap MAE 0.44359887397323583 vs max adjacent 0.7597497951723703 — PASS smooth wrap; different endpoints
```

The authored animation lasts 40/12 s; displaying every one of its 41 sampled
frames gives a 41/12 s file. No last frame was dropped, replaced or blended.
Infinite repeat metadata is separate from seam quality and endpoint identity.

| Retained output / deleted frame series | SHA-256 |
| --- | --- |
| `idle-2x.apng` | `462044902d2c1ac080d964238d3d05dab7eddafbe2c0940657cba8bf460c4ff7` |
| Final 41 PNGs concatenated in filename order | `85e0d85756b3efc384a01a235e38a2e9dc3f178dae626937cd3f511c407ec8d9` |
| Rejected 488-wide 41 PNGs concatenated | `2fa8b2b905dd788a3653aec38edff10bda4bddc3740439da7803d5e849459dd3` |

The sheet shows all 41 labelled samples with the figure within the viewport;
that small-sheet verdict does not establish endpoint identity. Both producer
frame sets (82 PNGs total) were hash-verified and deleted after this verdict.

## Verdict

**PARTIAL** — resolution, all 41 samples, exact 12-fps delays, infinite-repeat
metadata, lossless decoded pixels and the predeclared smooth-wrap criterion
pass. Exact endpoint closure does **not** pass: max RGB difference is 212.
The original issue's “loop closes” must not be reported as exact closure.

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
for these measured pixels. The APNG deliberately keeps the renderer's opaque
background and every compressed source frame, so it is larger than an indexed
or lossy recording. No browser playback or new full toolchain suite was run.
