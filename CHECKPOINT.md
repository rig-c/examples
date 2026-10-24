# Examples #29 / PR #64 — final frozen revision

State: PASS under HQ's owner-adopted measured-wrap bar; frozen for parent commit, P2 response, CI/review/sign. No active jobs; no further render or encoding after candidate measurement.

## Canonical input

Origin `40db33d91e4aacbe4cd31ac9f3cc557973b4a1d4`; accepted Character 1 `family/roa/out/check/build/`, hash-bound by `family/accepted-inputs.json`. Model SHA256 `b9b61d55614805e468b27f9fb2dbaba65a50a0ce56b32ffef04f8cacd2570632`. All original corpus files remain unchanged.

Pins: rig-c 2.68.0, spine-core 4.3.13, Bun 1.4.2, FFmpeg 7.0.2-static. Source rig/model/motion/art untouched; no generation, hand pass or retarget.

## Adopted result and native boundary

**rigc emits no closure verdict; this is the measured wrap**

Original max1290 producer logs have zero `loop:` lines. Renderer help supplies no closure flag; `core_commands.ts:1030–1092` prints sample count, physics and sidecar, and `physicsLine` at 1117–1130 counts constraints. Actual native output: `  ..    physics: 23 constraint(s) stepped at 12 fps`. Native closure is UNAVAILABLE, not PASS or FAIL.

HQ adopted measured wrap MAE 0.44359887397323583 ≤ max adjacent 0.7597497951723703 as this card's bar: PASS. First/last max RGB difference 212 and 1,917 pixels over 40 are observations only; exact endpoint equality is NOT a bar. Repeat metadata is recorded separately.

## Selected artifact

- Predictor lossless APNG: 492×1290, 41 independently decoded frames, all RGBA bytes identical (max error 0), each delay exactly 1/12 s, infinite plays metadata 0.
- 11,351,964 bytes, SHA256 `bd31ad5b7d952733417a8ac830c40e73719f95ef0cdb8569e092c2bde3161f0e`.
- Original compressed reference: 17,453,151 bytes, SHA256 `462044902d2c1ac080d964238d3d05dab7eddafbe2c0940657cba8bf460c4ff7`, retained remotely throughout and after measurement. Reduction: 6,101,187 bytes, about 35%.
- Palette APNG: 2,638,904 bytes, max RGBA error 66, timing exact; rejected.
- GIF: 2,253,537 bytes, max RGBA error 66, 8/100 and 9/100-second delays; rejected for error and exact-timing failure. All candidates preserve 41 decoded frames and infinite metadata.
- Full candidate hashes/delays/commands are in the trial receipt. No rerender for optimization.

## Verification and P2

- Optimization preflight `20261024T164354Z-ca8fa850a810460797563a2952311be5`: exit 0; actual source APNG decoder, palette readers, codec control and error controls 0/255.
- Candidate measurement `20261024T164502Z-48352c7770aa49189a0445bc3f2d7819`: exit 0; selected measured artifact copied unchanged.
- P2 discussion_r4367769592 at reviewed head b8422d447d7ae91586a61e849fc9b76d9dd1ee4f READ and fixed: absolute TRIAL from a trial-containing checkout, separate INPUT_ROOT with four pinned source hashes. Extracted README setup, fresh frozen install and actual renderer loader dry-run passed without rendering.
- `encode.mjs compress` uses the exact measured predictor arguments. Final revision validation is limited to lightweight hashes, syntax, path/setup consistency and command-argument comparison; no new full encode run is claimed for this final wiring.
- Prior 82 producer PNGs were hash-verified and deleted. Optimization used in-memory decoded RGBA; its temporary workspace was removed. Small logs and compressed candidates remain remotely. No original source deletion.

## File ownership

PR revision changes: CHECKPOINT.md plus trial README.md, encode.mjs, receipt.json and idle-2x.apng. The trial sheet.png remains unchanged. No family edits, git/public writes, new review requests, subagents or full suite. Parent owns commit, P2 response, CI, review and sign.
