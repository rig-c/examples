# The dancer

**Current producer:** the setup order puts both sleeves behind `topwear`; seven authored draw-order keys preserve arm crossings and lift the whole right sleeve at its first lost frame. Original projected art and the explicit smear50 skirt are unchanged. `build.sh` uses the staged order-only recipe below; [current source and sampled pose evidence](provenance/both-shoulder-order.json); [previous left-sleeve adoption](provenance/setup-order.json). The immutable accepted dance replay remains separate.

**Current accepted dance: owner v4, 2026-10-25.** Run `sh build-accepted-dance.sh` from this directory. The owner's eye verdict was "v4 looks good, merge it" ([#73](https://github.com/rig-c/examples/issues/73)). V4 replays the mesh-only smear50 rig with released core; motion and every other rig subtree are unchanged from v3. [V4 source, commands and measured evidence](accepted-dance/v4/README.md). The setup producer is separate provenance. V3 remains immutable and explicitly selectable with `sh build-accepted-dance.sh --version v3 work/accepted-v3`; its versioned records describe its earlier acceptance/default, not the current selection. [Historical v3 proof](accepted-dance/v3/reproduction-evidence.json).

| Dance version | Source date | Record / selection |
| --- | --- | --- |
| v1 | 2026-10-24 | Accepted R3/v5, [trial #52](https://github.com/rig-c/examples/pull/52) and [corpus #53](https://github.com/rig-c/examples/pull/53); original declarations/evidence retained; explicit `sh build-accepted-dance.sh --version v1 work/accepted-v1` |
| v2 | 2026-10-24 | Intermediate generated holds and lifted-jacket strip, [#38](https://github.com/rig-c/examples/issues/38); recorded, not promoted |
| v3 | 2026-10-24 | Owner-named final, [#56](https://github.com/rig-c/examples/issues/56), [trial #57](https://github.com/rig-c/examples/pull/57); permanent hip waist, generated chest holds, compensated +17u chest lift and front-slot lowering; historical accepted version, explicitly selectable |
| v4 | 2026-10-25 | Owner-accepted smear50 mesh-only replay, [#71](https://github.com/rig-c/examples/issues/71); original eval 20/4, bottomwear folds 0; [source, reproduction and evidence](accepted-dance/v4/README.md); current default; explicit `sh build-accepted-dance.sh --version v4 work/accepted-v4` also remains available |

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
- `config.json` states the explicit smear50 producer mesh with the original 11 physics declarations. `provenance/keeper-config-before-smear50.json` preserves the exact previous keeper for historical replay. `x-repairs` still pins the unchanged historical hand record.
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

No reference video, audio, picture-in-picture, installed dependency tree or private raw
log is included. The current accepted dance payload is stored under accepted-dance/v4/; immutable v3 remains beside it. Generation model names are source records; model binary hashes
are not available in those records.

## Reproduce the current producer build

From this directory, with Bun and Python 3:

```sh
sh build.sh
```

This command assembles art with the byte-preserved `config-before-setup-order.json`, then uses `@rig-c/parts` 1.64.0's `src/assemble.ts:drawOrder` to apply the active `config.json` setup order to the intermediate parts list. It remeasures that flat stack, generates rig/motion from the active config and `stress.json`, and runs the ordinary parts check. It never reassembles the active order into different projected art or patches emitted rig/motion. Output is ignored under `work/`. The saved accepted rig has the separate core build described below.

Both shoulders are compared to the same painting without changing PNG bytes. The right upper-arm part carries the extra contour and stays behind the torso at setup. Whole-right-arm keys start at crossed frame 0, elbow-positive frame 46 and shoulder-in frame 8 on the 12 fps grid, with the forearm directly under the upper arm. During those holds the contour returns in the accepted order; lifting the forearm alone was rejected for introducing a filled sleeve patch. The five earlier left-front key times remain; all offsets are recomputed for the frozen setup order. Both opposite-arm contributor loss and each same-arm contributor reassignment measure zero against the accepted build at matching frames over all 19 clips at 12 fps. The two earlier sleeve/chest key-boundary pops remain recorded nonblockers, and thigh-out viewport clipping remains out of scope. Setup-painting readings for each shoulder are informational, with per-slot values in the current provenance record.

The adopted canonical producer bytes are in `producer/rig/`. A fresh rebuild and byte/RGBA inventory comparison runs as:

```sh
bun tools/verify-producer.mjs --out work/fresh-producer
```

Choose a new output directory for each rebuild. The verifier refuses changed/missing files, changed decoded PNG pixels, a red check, or changed active config/package pins. It verifies all 31 producer files; it does not claim the original accepted dance can be played on this different producer rig.

The current frozen producer install pins `@rig-c/parts` 1.64.0, direct `rig-c` 2.67.2 and official `@esotericsoftware/spine-core` 4.3.13. Parts resolves its own compatible rig-c 2.70.0, recorded in `bun.lock`; that is the compiler its build/check invokes. The new Nova producer runs use Bun 1.4.4. Historical dance replay keeps its separate frozen package pins. `check-inputs.py` checks file
hashes and config/map closure; it does not render or establish rig correctness.

## Historical keeper-config build, 2026-10-23

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
of the saved accepted rig. This historical refusal is retained as provenance; the current explicit producer above resolves its setup seam.

## Input integrity

`source-manifest.json` lists repository-relative input paths, byte counts,
SHA-256 hashes, source hashes and origins. `path-normalization.json` records the
two See-through metadata image-path changes. Historical base config bytes and the archived pre-smear50 keeper are preserved exactly.
Removing only `x-repairs` from the archived keeper and writing two-space JSON with one trailing LF recovers its original recorded hash. The active config additionally declares the explicit skirt and approved setup order; the archived `config-before-setup-order.json` preserves the exact pre-order producer input for projected-art generation. Their separate hashes and the staged recipe are bound in the canonical producer inventory.
Accepted image bytes and map values are preserved.

## Build the accepted rig

The accepted v3 source is the hand-built transplant recorded by
`replace_shins.py`, using the weighted-shins output from the parts 1.57 source
build. `port_config.py` writes the keeper producer-input config and port ledger;
it does not write the accepted rig. Its external historical dependencies were
not followed or executed for this package. The archived keeper geometry and producer values remain unchanged. Historical replay readers explicitly use that archive for their original config preimage; they do not substitute the new active producer mesh.

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

## Historical v1 accepted dance record, 2026-10-24

The owner accepted the Zero Two result in [trial PR52](https://github.com/rig-c/examples/pull/52), merged at `25105715d1d9365a065bf55255bb13116e85f9f4`. The exact source is now part of this corpus: `accepted/sequence.json`, SHA256 `8713172431674a57caa8d7c3f452a05bf46ec8079ca368bb4cd9df7952c2edfd`. It preserves its `rig-pose-clean/1` record, measured waistband hip inference and camera normalisation from eight hand keys. There are 313 input samples at 24fps, 0–13s; 391@30fps describes rendering, not acquisition. The original videos and reference pixels are withheld. Origin: Zero Two challenge, [YouTube Shorts BGyjsZsWndA](https://www.youtube.com/shorts/BGyjsZsWndA); creator not identified.

The existing `map.json` is unchanged, SHA256 `9dca5394f6c0cf9cc72e2456b53b41adf898b963a6081d9f6f9b3c2ad6191096`. `config.json` now pins `declared-repairs-v3.json`; the preserved v1 record originally pinned `declared-repairs.json` through the same `x-repairs: {file, sha256}` metadata shape used by family configs. The record pins the original keeper producer bytes (excluding only `x-repairs` as explicitly specified by its `hashMode`), accepted rig, base motion, map and selected-art bytes. This avoids a circular hash without excluding any geometry or producer value from verification. It follows the family's explicit baseline/part-declaration/hash-pins pattern with a dancer-specific record format; it is not an input to the family repair scripts.

The record contains all seven attachment corrections (five additions and two K1 region-to-mesh replacements with full UV/weight/triangle/hull values), all 14 posthoc selection tracks and the K0–K4 set spans. The remaining rig bones, slots and 11 physics constraints are preserved. The distal 1.15 enlargement is in authored mesh coordinates, not a bone-scale change. The ending right foot is re-solved against newly rendered geometry using the declared 11.25s start, 0.35s smoothstep, 85-world-unit separation and late-left-foot floor rule. No historical whole-body motion is shipped or copied into the new result. Fresh acquisition remains a separate trial comparison; the selected final intentionally continues the owner-accepted camera/hip-adjusted pose sequence.

From `dancer/`, with Bun and Python 3, run under the Nova pooled 6 GiB/four-worker guard:

```sh
sh build-accepted-dance.sh --version v1 work/accepted-v1
# A second historical run must name a fresh output directory.
sh build-accepted-dance.sh --version v1 work/accepted-v1-second
```

Only this directory is needed. The recipe first checks the source manifest, then copies its own corpus into an ignored workspace and installs the frozen `accepted-dance/package.json` / `bun.lock` pins: pose 1.0.1, core 2.67.2, official spine-core 4.3.13, with play 1.16.0 and parts 1.60.0 installed but not invoked by this replay. It retargets with the recorded source options, renders the input geometry, applies the declared hand changes, builds the final and renders 391 frames at 30fps in the accepted viewport. It does not invoke the failing config-only parts build, access another checkout, download a source video, run a detector or import a package's private API.

`reproduction.json` in the chosen workspace records every command, gate logs and exact hashes. The reference compiled hash is `2a21d03affaadac4a314b7dd0345b0b2b842292a24ff3ce49b4de2b460fb12d1`; the recipe also compares the exact rig, motion and full geometry file digests before declaring byte reproduction. Reconstructing the measured relative layout keeps atlas page URLs stable. A mismatch is a named failure, not an inferred visual pass or a relaxed tolerance. The corpus-only Nova run exited 0. Its compiled model, final rig, motion and full geometry digests all exactly match the accepted result; `accepted-dance/reproduction-evidence.json` records the commands and raw gate lines. The final `spine` gate measured 23 PASS, 0 FAIL, 13 SKIP and 14 profile exclusions. Comparing all 391 geometry frames covered 37,536 bone samples and 592,651 attachment-vertex samples: maximum bone world-position, linear-matrix and vertex residuals were all 0. The full geometry SHA256 is `e701f3a709c83aadcde9db46c0ef3ad532ff38d77c3d8fbd45270e0149308c5c`.

After this successful replay, only the config/record metadata pin and its static input validation were added; producer values and rendering/apply commands were unchanged. Static checks verify that removing `x-repairs` recovers the exact config used in the replay. No second build or render was run. The pre-hand retarget passed LAND 20/20; this is not a post-hand original-pose fidelity claim. The final render retains 269 shins-fold frames; the three measured bottomwear pass-through pairs each reported 0/391. These do not replace seam or full-physics assessment.

The accepted source still includes shins folds. Standard retarget SEAM has no declared neighbour pairs; source-video fidelity, detector-based compare and full physics acceptance are not established by this replay. Source rig edits, declared attachment/motion hand corrections, owner eye acceptance and compiler assertions remain distinct records.
