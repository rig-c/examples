# The dancer

Generated painting and saved rig inputs accepted on 2026-10-22. Origin:
accepted dance-skirt v3/v5; original painting and See-through runs, 2026-10-13.
Each input's origin is recorded in `source-manifest.json`.

- Painting: `painting.png`; seed 74101, checkpoint
  `novaAnimeXL_ilV80.safetensors`, LoRAs `[]`, prompt ID
  `a8cbc2ef-0302-4529-91ba-cc4b2b808ec0`. Full prompts and the original
  generation graph are recorded in `painting_meta.json` and the PNG metadata.
- See-through: `inputs/st_input_full.png` and `inputs/st_input_head.png`;
  `layers/full/` and `layers/head/` each contain 29 tagged parts and saved
  metadata. Each `layers.json` retains original server filename/depth
  provenance; exported parts are addressed by `parts/<tag>.png`.
- `config.json` preserves the v3 keeper producer values with 11 physics constraints; its added `x-repairs` metadata pins the declared hand record.
  `config-base.json` is the historical 9-constraint input, not the active
  keeper. `under/`, `stress.json` and `requirements.json` close the declared
  build dependencies.
- `accepted/rig.json`, `accepted/motion.json` and `accepted/images/` preserve
  the exact v3 hand-built rig, base motion and source images / atlas inputs.
  The base motion contains 31 idle, pose, sweep, set, range and turn animations;
  it contains no dance animation. `map.json` is the accepted dance’s map, 2026-10-22.
  `selected-art.json` records the K0–K4 slot/attachment/image closure.
- `provenance/` records the source skirt hand-port and weighted-shins
  replacement. These source rig edits are distinct from a trial's motion hand
  phase. The saved accepted hand-built rig and a config-only generation are
  separate artifacts; config-only output is not claimed to recreate that rig.

No reference video, old dance motion, installed dependency tree or private raw
log is included. Generation model names are source records; model binary hashes
are not available in those records.

## Reproduce the keeper-config build

From this directory, with Bun and Python 3:

```sh
sh build.sh
```

This command builds `config.json`; it does not build `accepted/rig.json`.
**It may exit 1: the recorded current run below did so at the seam check.**
Output is ignored under `work/`. The accepted rig has the separate core build described below.

Direct package pins are `@rig-c/parts` 1.60.0, `rig-c` 2.67.2 and the official
round-trip runtime `@esotericsoftware/spine-core` 4.3.13. The recorded Nova run
used Bun 1.4.2, Node v24.21.0 and Python 3.12.3. `check-inputs.py` checks file
hashes and config/map closure; it does not render or establish rig correctness.

## Recorded current build, 2026-10-23

One targeted closure and keeper-config build ran on Nova. Inputs were unchanged
through the run. No fallback build or rig modification was performed.

| Check | Actual result |
| --- | --- |
| Input closure | PASS; full/head 29 + 29 tagged layers, declared dependencies, 11-constraint config and accepted map references |
| Generated rig | 137 bones, 7 meshes, 19 animations, 11 physics constraints |
| rigc loose gate, rig-play profile | 27 measured PASS, 0 FAIL, 23 SKIP |
| rigc packed gate, rig-play profile | 28 measured PASS, 0 FAIL, 22 SKIP |
| parts check | 11 of 12 bars measured: 10 PASS, 1 FAIL; 1 SKIP (`STRESS_OFF_CHAIN`) |
| Setup seam mean absolute difference | 1.544/255; required ≤ 1.0 |
| Setup seam pixels over 40 | 5262 frame px; scale 1.029183; 4967.82 rig px, required ≤ 50 rig px |
| Setup seam pixels over 80 | 4235 frame px, reported |
| Warning | 1 `CLOTH_SETTLES` warning; not a bar |
| Build exit | 1, `CHECK_SEAM_WITHIN_BAR`; stopped before loop encoding; no completed build artifact reported |

The refusal compares the setup-pose render with the flat composite of parts.
The documented diagnostic is to inspect the `seam pair` lines and
`check/seam/` images against `recomposite_rig.png`; see the
[pinned official guide](https://github.com/rig-c/parts/blob/6f4e8040d5a4861462b6be20933a4d7c85dac01f/docs/AUTHORING.md#CHECK_SEAM_WITHIN_BAR).
No corrective config, art, geometry, limit or gate changes were made. This
config-build refusal does not establish a regression or a failure of the
separate accepted hand-built rig. The config gap is recorded for a separate parts issue and does not block use
of the saved accepted rig. No producer fix is included.

## Input integrity

`source-manifest.json` lists repository-relative input paths, byte counts,
SHA-256 hashes, source hashes and origins. `path-normalization.json` records the
two See-through metadata image-path changes. Keeper producer values and historical base config bytes are preserved exactly.
The keeper adds only `x-repairs` metadata; removing that field and writing
two-space JSON with one trailing LF recovers its original recorded hash.
Accepted image bytes and map values are preserved.

## Build the accepted rig

The accepted v3 source is the hand-built transplant recorded by
`replace_shins.py`, using the weighted-shins output from the parts 1.57 source
build. `port_config.py` writes the keeper producer-input config and port ledger;
it does not write the accepted rig. Its external historical dependencies were
not followed or executed for this package. Keeper geometry and producer values remain unchanged; only the declared-record metadata pin is added.

From this directory:

```sh
sh build-accepted.sh
# For a trial, supply that trial's motion and output directory:
sh build-accepted.sh path/to/trial-motion.json work/trial
```

This runs core `rigc build --rig accepted/rig.json --motion <motion>` with
`--images accepted/images --profile spine`. Dance trials use this accepted rig
plus their own motion, rather than rebuilding the parts config.

The current canonical base-motion build exited 0 through the official
spine-core 4.3.13 round trip: 50 assertions, 23 measured PASS, 0 FAIL, 13 SKIP
and 14 outside the `spine` profile. It produced 54 pages, 54 regions, 96 bones,
38 slots, 31 animations and 11 physics constraints. Exact assertion lines, input
and output hashes, versions and relative output layout are in
`build-evidence.json`. The atlas refers to the included source PNGs; generated
outputs remain under ignored `work/`. This gate establishes validity, not visual
fidelity or the quality of a new dance.

## Accepted dance record, 2026-10-24

The owner accepted the Zero Two result in [trial PR52](https://github.com/rig-c/examples/pull/52), merged at `25105715d1d9365a065bf55255bb13116e85f9f4`. The exact source is now part of this corpus: `accepted/sequence.json`, SHA256 `8713172431674a57caa8d7c3f452a05bf46ec8079ca368bb4cd9df7952c2edfd`. It preserves its `rig-pose-clean/1` record, measured waistband hip inference and camera normalisation from eight hand keys. There are 313 input samples at 24fps, 0–13s; 391@30fps describes rendering, not acquisition. The original videos and reference pixels are withheld. Origin: Zero Two challenge, [YouTube Shorts BGyjsZsWndA](https://www.youtube.com/shorts/BGyjsZsWndA); creator not identified.

The existing `map.json` is unchanged, SHA256 `9dca5394f6c0cf9cc72e2456b53b41adf898b963a6081d9f6f9b3c2ad6191096`. `config.json` pins `declared-repairs.json` through the same `x-repairs: {file, sha256}` metadata shape used by family configs. The record pins the original keeper producer bytes (excluding only `x-repairs` as explicitly specified by its `hashMode`), accepted rig, base motion, map and selected-art bytes. This avoids a circular hash without excluding any geometry or producer value from verification. It follows the family's explicit baseline/part-declaration/hash-pins pattern with a dancer-specific record format; it is not an input to the family repair scripts.

The record contains all seven attachment corrections (five additions and two K1 region-to-mesh replacements with full UV/weight/triangle/hull values), all 14 posthoc selection tracks and the K0–K4 set spans. The remaining rig bones, slots and 11 physics constraints are preserved. The distal 1.15 enlargement is in authored mesh coordinates, not a bone-scale change. The ending right foot is re-solved against newly rendered geometry using the declared 11.25s start, 0.35s smoothstep, 85-world-unit separation and late-left-foot floor rule. No historical whole-body motion is shipped or copied into the new result. Fresh acquisition remains a separate trial comparison; the selected final intentionally continues the owner-accepted camera/hip-adjusted pose sequence.

From `dancer/`, with Bun and Python 3, run under the Nova pooled 6 GiB/four-worker guard:

```sh
sh build-accepted-dance.sh
# A second run must name a fresh output directory; existing evidence is preserved.
sh build-accepted-dance.sh work/accepted-dance-second
```

Only this directory is needed. The recipe first checks the source manifest, then copies its own corpus into an ignored workspace and installs the frozen `accepted-dance/package.json` / `bun.lock` pins: pose 1.0.1, core 2.67.2, official spine-core 4.3.13, with play 1.16.0 and parts 1.60.0 installed but not invoked by this replay. It retargets with the recorded source options, renders the input geometry, applies the declared hand changes, builds the final and renders 391 frames at 30fps in the accepted viewport. It does not invoke the failing config-only parts build, access another checkout, download a source video, run a detector or import a package's private API.

`reproduction.json` in the chosen workspace records every command, gate logs and exact hashes. The reference compiled hash is `2a21d03affaadac4a314b7dd0345b0b2b842292a24ff3ce49b4de2b460fb12d1`; the recipe also compares the exact rig, motion and full geometry file digests before declaring byte reproduction. Reconstructing the measured relative layout keeps atlas page URLs stable. A mismatch is a named failure, not an inferred visual pass or a relaxed tolerance. The corpus-only Nova run exited 0. Its compiled model, final rig, motion and full geometry digests all exactly match the accepted result; `accepted-dance/reproduction-evidence.json` records the commands and raw gate lines. The final `spine` gate measured 23 PASS, 0 FAIL, 13 SKIP and 14 profile exclusions. Comparing all 391 geometry frames covered 37,536 bone samples and 592,651 attachment-vertex samples: maximum bone world-position, linear-matrix and vertex residuals were all 0. The full geometry SHA256 is `e701f3a709c83aadcde9db46c0ef3ad532ff38d77c3d8fbd45270e0149308c5c`.

After this successful replay, only the config/record metadata pin and its static input validation were added; producer values and rendering/apply commands were unchanged. Static checks verify that removing `x-repairs` recovers the exact config used in the replay. No second build or render was run. The pre-hand retarget passed LAND 20/20; this is not a post-hand original-pose fidelity claim. The final render retains 269 shins-fold frames; the three measured bottomwear pass-through pairs each reported 0/391. These do not replace seam or full-physics assessment.

The accepted source still includes shins folds. Standard retarget SEAM has no declared neighbour pairs; source-video fidelity, detector-based compare and full physics acceptance are not established by this replay. Source rig edits, declared attachment/motion hand corrections, owner eye acceptance and compiler assertions remain distinct records.
