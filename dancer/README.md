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
- `config.json` is the exact v3 keeper port with 11 physics constraints.
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
two See-through metadata image-path changes. Keeper and historical base config
bytes are preserved exactly. Accepted image bytes and map values are preserved.

## Build the accepted rig

The accepted v3 source is the hand-built transplant recorded by
`replace_shins.py`, using the weighted-shins output from the parts 1.57 source
build. `port_config.py` writes the keeper producer-input config and port ledger;
it does not write the accepted rig. Its external historical dependencies were
not followed or executed for this package. The keeper config remains unchanged.

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
