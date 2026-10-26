# Current accepted dance: v3, 2026-10-24

The owner selected this existing hand result in [#56](https://github.com/rig-c/examples/issues/56).
The [trial source](https://github.com/rig-c/examples/tree/ee5ec1ad56b3d97e7af6fd85e1957cc0ff9ee7a4/trials/2026-10-24-zero-two-dancer/hand/v3)
is provenance; it is not a runtime dependency. This corpus keeps the original
`rig.json` and `motion.json` bytes once here, with the three original generated
PNGs beside the base art in `accepted/images/`. No source art, key or value is
changed, and no generation, retarget or hand-application script runs by default.

`declared-repairs-v3.json` at the corpus root pins the original producer config
(excluding only `x-repairs` metadata), v1 declarations, canonical v3 payload,
three PNGs, exact new slots/order/attachments and 14 changed or added motion
tracks. The current `config.json` binds that record by SHA-256 through the same
`x-repairs: {file, sha256}` shape as the historical v1/family convention.
Producer values are unchanged. `declared-repairs.json` and the old reproduction
evidence remain the v1 history; the keeper-config parts seam refusal is separate.

From `dancer/`, under Nova's pooled aggregate 6 GiB/four-CPU limit including
installation and children:

```sh
python3 tools/reproduce-accepted-dance.py --preflight
sh build-accepted-dance.sh
# A repeat must use a fresh output directory.
sh build-accepted-dance.sh work/accepted-v3-second
# Explicit historical v1 recipe, not the current default:
sh build-accepted-dance.sh --version v1 work/accepted-v1
```

The default installs the frozen `accepted-dance/package.json` / `bun.lock`:
core 2.67.2, spine-core 4.3.13, parts 1.60.0, pose 1.0.1 and play 1.16.0.
Bun is 1.4.2. Parts, pose and play are installed but not invoked for motion or
art authoring. The pure fixture check reads the exact rig/motion/sequence with
the real pinned readers and refuses a planted invalid rig. The script stages
the original source bytes as `hand/v3/rig.json` and `hand/v3/motion.json` while
preserving their original relative images field, then runs these commands in
its new output workspace:

```sh
bun "$RIGC_CLI" build --rig hand/v3/rig.json --motion hand/v3/motion.json --out build --profile spine
bun "$RIGC_CLI" render --candidate build --animation zero-two-r3-hand --fps 30 --viewport-from "$CORPUS/accepted-dance/viewport.json" --out render
```

`RIGC_CLI` is that workspace's installed `node_modules/rig-c/cli.ts`;
`CORPUS` is its staged `work/corpus/dancer`. Core posing uses the compiled
model. The original relative build layout preserves atlas references. The
three compiled hashes are checked before render; a mismatch stops without
path/value adjustments. Then 391 native RGBA PNGs (736×960, 30 fps, background
232/232/232/255) are streamed in `f0000.png` through `f0390.png` order into
SHA-256, without separators. It is a file-byte digest, not a hash-list text
digest, pixel-only comparison or promo video hash.

| Accepted target | SHA-256 |
| --- | --- |
| Original rig | `a1860937f20890818a206a2b15318eaf2bf9e253d58584976b8aa9697f73e135` |
| Original motion | `46189464040b3ef8b42357399e1c8b0c1c4cbf6feedeabb24927eb09242f5aa7` |
| Head-arm PNG, H1 seed 1 | `6954c20fbe1bf3d988b4d1e9c8baff38f91d2549bb2a3ac2ee06d1907737318b` |
| Front-arm PNG, H2z seed 53 | `18b392875be888e28bf116edceede5e4c14cafe31554e192348f7de54db00701` |
| Waist PNG, H1m seed 62 lineage | `1c733bdf717741d98162c96439995d3cb6a009ddf1900bad4c9271a55712d5cb` |
| skeleton.json | `4e6024989f06a15525bf5cb32a47bb7aa55a75d8adf58505ce6b1a12efb49f77` |
| skeleton.atlas | `bd9d9414f016e94407a61685455888a7aad6781acdd9d634a0a9f3c0c432cdf1` |
| skeleton.model.json | `a94c7cbee992acaf87c0e283efc1bbd44766441f791776064e929bd59a2f0e81` |
| 391 concatenated native PNGs | `b75fc5696ac468f3ea9f58cc892d79389d66bf6ce7aeb31428f95350b9121029` |
| Fixed viewport input | `8a0f07c4304419d64125314d773b3b0f62bacdd0229a40cc0cbdffa57545a13c` |

The accepted source uses head hold f124–218 and low hold f234–328 on `chest`,
with base articulated arms in front slots while lowering f219–233. A permanent
106×115 `waist` region rides `hip` behind jacket/skirt; the existing accepted
chest +17u and head −17u compensation ease f110→124 in and f219→233 out.
Other 41 bone tracks, other animations, existing attachments, bone and
constraint values remain as the v1 source. These facts are declarations of
existing authored data, not corrections inferred during replay. Shoulder/chest
lift intent is a pose-card candidate; newly generated art is not automatically
derivable from pose input. [Generation provenance](generation/README.md) carries
the full selected prompts, seeds, configs, historical recipe source and omitted
warp/control/layer hash references. Historical model binary digests and custom
node revisions were not recorded; generative byte identity is not claimed.

This is a non-looping 13-second take, including both sampled endpoints. Origin:
Zero Two challenge, a YouTube Shorts video (link withheld),
creator not identified. Source footage, audio and promo/PiP pixels are withheld.
The original retarget LAND20/20 and posthoc foot-goal residual belong to their
historical stages. Shins FOLD269/391 remains the historical known limit; a
new v3 fold/geometry diagnostic is not claimed. All-rig seams, detector-based
compare, loop seams and new browser/owner eye verification are not measured by
this transfer. Compiler gate skips/exclusions are not passes.

The completed corpus-only default replay exited 0 on Nova with these exact
three compiled digests and the complete native PNG digest. The actual gate
measured 23 PASS / 0 FAIL / 13 SKIP / 14 profile exclusions.
[Reproduction evidence](reproduction-evidence.json) records every frame hash,
real reader result scope, commands, budget and sealed raw-evidence hashes.
Only 101,067 changed artifact bytes were recovered; native frames, compiled
output and runtime remain retained remotely. Source input files stayed
unchanged during execution. The v1 explicit preflight also passed locally;
its historical full replay was not repeated.
