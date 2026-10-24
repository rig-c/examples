# Examples #29 — frozen handoff

State: implementation and evidence frozen. Parent owns review, PR, AI-review read, sign and merge. No running jobs.

## Source and scope

- Origin: `40db33d91e4aacbe4cd31ac9f3cc557973b4a1d4`.
- Canonical input: `family/roa/out/check/build/`, pinned by `family/accepted-inputs.json`.
- Model SHA256: `b9b61d55614805e468b27f9fb2dbaba65a50a0ce56b32ffef04f8cacd2570632`.
- Pins: rig-c 2.68.0, spine-core 4.3.13, Bun 1.4.2, FFmpeg 7.0.2-static.
- Changed paths: this checkpoint and five files in `trials/2026-10-25-character-1-idle-2x/`: `idle-2x.apng`, `sheet.png`, `encode.mjs`, `README.md`, `receipt.json`.
- All original repository files, including every `family/` file, remain unchanged. No rig/model/motion/art editing, generation, hand pass or retarget.

## Actual result

**PARTIAL**: 492×1290, all 41 renderer samples at 12 fps, lossless independent APNG decode, 41 exact 1/12-second delays and infinite-repeat metadata PASS. Encoded duration is 41/12 s, preserving the endpoint sample; authored duration is 40/12 s.

Smooth wrap PASS: RGB wrap MAE 0.44359887397323583 ≤ maximum adjacent step 0.7597497951723703. Exact endpoint closure FAIL: first/last max RGB difference 212, 1,917 pixels over 40. Repeat metadata is not closure proof. No exact-loop acceptance is claimed.

The initial max1280 render was 488×1280 and failed the width bar. Max1290 is the smallest integer renderer max-side value rounding the same world viewport to width 492. No framing or source changes.

## Staged verification

1. Actual renderer loader read accepted model, skeleton digest, atlas and PNG; help read.
2. Producer `20261024T163053Z-a93effd31f28457baddfd45a19251c95`: exit 0; width FAIL at 488.
3. Corrected producer `20261024T163209Z-c2f66be166854201a3aa38aa82035b50`: exit 0; 492×1290, 41 frames at 12 fps.
4. Downstream reader dry-run `20261024T163345Z-ec3a19af810f4d49a0b7749114700ef5`: exit 0; all PNG readers, FFmpeg decode and predeclared metric controls PASS.
5. Encode/measure `20261024T163538Z-ee335480381240dab28554ff2ee84045`: exit 0; every independently decoded APNG frame matches renderer RGBA pixels. See the trial README/receipt for exact commands, delays and actual loop line.
6. Both producer frame sets were concatenation-hash verified and deleted after the sheet verdict: 82 new frames deleted; original corpus untouched. Only the final compressed APNG, small sheet and reproducibility records are retained as trial outputs.

## Hashes and remaining bar

- APNG, 17,453,151 bytes: `462044902d2c1ac080d964238d3d05dab7eddafbe2c0940657cba8bf460c4ff7`.
- Final source PNG concatenation: `85e0d85756b3efc384a01a235e38a2e9dc3f178dae626937cd3f511c407ec8d9`.
- Exact endpoint equality remains unmet. No source repair or rerender was attempted to conceal it.
- No full suite or browser playback; no git commands or public writes by this worker.
