# rigboy v2

An articulated side-profile character rig built from 20 region pieces with circular joint caps (**0 meshes**), mapped onto the public-domain Spineboy skeleton (`spineboy-pro.json`), constraints and nine human animations (`idle`, `walk`, `run`, `jump`, `shoot`, `aim`, `idle-turn`, `run-to-idle`, `death`).

## Play (`@rig-c/play`)

Tested with `@rig-c/core@3.1.0` (`rigc`) and `@rig-c/play@1.22.1`. Serve this repository over HTTP and load `rigboy/v2/build/skeleton.model.json`:

```js
import { loadModel, RigPlayer } from '@rig-c/play';

const assets = await loadModel({
  modelUrl: new URL('./rigboy/v2/build/skeleton.model.json', document.baseURI).href,
  setsUrl: null,
  regions: 'data',
});
const root = document.getElementById('rigboy-v2'); // positioned world origin, Y-up
const player = new RigPlayer(root, assets, { mode: 'dom', meshBackend: 'canvas2d' });
player.play('walk'); // 'idle' | 'walk' | 'run' | 'jump' | 'shoot' | 'aim' | 'idle-turn' | 'run-to-idle' | 'death'
player.renderer.syncPixelRatio();

let last = performance.now();
let frameId = requestAnimationFrame(function tick(now) {
  player.frame((now - last) / 1000);
  last = now;
  frameId = requestAnimationFrame(tick);
});

function unload() {
  cancelAnimationFrame(frameId);
  player.dispose();
  assets.dispose();
}
```

## Files and rebuild

- [`rig/rig.json`](rig/rig.json) (`rigc-rig/1`) and [`rig/motion.json`](rig/motion.json) (`rigc-motion/1`): canonical final rig and motion specs.
- [`rig/disc-radii.json`](rig/disc-radii.json) and [`rig/downsampled.json`](rig/downsampled.json): the 12 limb joint-disc radii (`R` in world pixels) and the `gun/gun` downsample record (`730×400 -> 122×67`, scale `0.16743854`).
- [`images/`](images/): 20 RGBA part PNGs (`19` body pieces at `416×624` and `gun.png` at `122×67`).
- [`build/`](build/): compiled player and Spine 4.3.13 outputs (`skeleton.model.json`, `skeleton.json`, `skeleton.atlas`, `skeleton.png`, `skeleton2.png`).
- [`rounds/`](rounds/): intermediate rounds kept for provenance (`under-pieces`, `under-pieces-round2`, `cut-ends-round4`, `cut-ends-round6`).

Rebuild from the repository root:

```sh
# Packed @rig-c/play model + Spine 4.3.13 outputs (23/23 assertions pass):
rigc build \
  --rig rigboy/v2/rig/rig.json \
  --motion rigboy/v2/rig/motion.json \
  --out rigboy/v2/build \
  --profile rig-play \
  --pack --page-edges free --pack-shape polygon

# Unpacked Spine profile with copied part images (17/17 assertions pass):
rigc build \
  --rig rigboy/v2/rig/rig.json \
  --motion rigboy/v2/rig/motion.json \
  --out /tmp/rigboy-v2-spine \
  --profile spine --copy-images
```

## Why `v2/` sits beside [`rigboy` v1](../README.md)

1. **Preserving the v1 mesh-fold baseline ([issue #78](https://github.com/rig-c/examples/issues/78)):** `rigboy/` (v1, `seed 781301`, 3 weighted leg meshes, 2,297 triangles) demonstrates single-painting mesh behaviour over modest custom clips and why single-painting leg meshes fold at deep knee flexion.
2. **Consumer compatibility:** Existing pages pinned to `rigboy/build/skeleton.model.json` and `rigboy/controls.js` continue to work unchanged while `rigboy/v2/build/skeleton.model.json` serves the articulated v2 rig.
3. **Round provenance:** Canonical v2 specs live in `rigboy/v2/rig/`, while intermediate rounds (`under-pieces`, `under-pieces-round2`, `cut-ends-round4`, `cut-ends-round6`) remain under [`rounds/`](rounds/).

---

## Measured bars (`rig-c/examples#80`)

All bars are measured directly on the compiled rig (`rigboy/v2/build/`):

1. **Compile gate (`rigc build`):** **PASS (exit `0`)** — `23 / 23` measured assertions pass under `--profile rig-play --pack --page-edges free --pack-shape polygon` (`17 / 17` under `--profile spine --copy-images`).
2. **Mesh folds (`rigc render --folds`):** **PASS (`0 of 0` meshes fold)** across all 9 animations (`meshAttachments = 0`).
3. **Joint-disc gaps (`rig/disc-radii.json`, 12 limb joints at `1528×1864`):** **PASS (`12 / 12` joints at `0` background pixels across all 9 clips, `108 / 108` joint-clip pairs).**
4. **Ankle bend vs `spineboy-pro.json` (`|d| <= 15°`):** **PASS (`0` samples over `15°` on both front and rear ankles across all 9 clips; max `|d| = 12.98°`).**

### Per-clip summary (Round 6 baseline vs Final v2)

| Animation | Frames (`discgate`) | Joint discs at `0 px` (Round 6 -> Final) | Open disc pixels (Round 6 -> Final) | Front ankle max `|d|` / `>15°` (Round 6 -> Final) | Rear ankle max `|d|` / `>15°` (Round 6 -> Final) | Verdict |
| --- | ---: | --- | --- | --- | --- | --- |
| `walk` | `31f @ 30fps` | `12/12` -> **`12/12`** | `0px` -> **`0px`** | `13.82° (0/31)` -> **`12.98° (0/31)`** | `12.01° (0/31)` -> **`12.01° (0/31)`** | **PASS** |
| `run` | `21f @ 30fps` | `10/12` -> **`12/12`** | `5px` (`near wrist` `2f/3px`, `near ankle` `2f/2px`) -> **`0px`** | `23.98° (12/41)` -> **`10.81° (0/41)`** | `40.91° (17/41)` -> **`10.83° (0/41)`** | **PASS** |
| `jump` | `41f @ 30fps` | `9/12` -> **`12/12`** | `76px` (`near shoulder` `8f/68px`, `near wrist` `2f/2px`, `near ankle` `6f/6px`) -> **`0px`** | `7.28° (0/41)` -> **`6.97° (0/41)`** | `0.00° (0/41)` -> **`0.00° (0/41)`** | **PASS** |
| `death` | `60f @ 12fps` | `10/12` -> **`12/12`** | `44px` (`near shoulder` `4f/43px`, `far elbow` `1f/1px`) -> **`0px`** | `0.00° (0/41)` -> **`0.00° (0/41)`** | `0.03° (0/41)` -> **`0.12° (0/41)`** | **PASS** |
| `shoot` | `20f @ 30fps` | `12/12` -> **`12/12`** | `0px` -> **`0px`** | `7.22° (0/41)` -> **`6.93° (0/41)`** | `20.06° (41/41)` -> **`11.57° (0/41)`** | **PASS** |
| `idle` | `51f @ 30fps` | `12/12` -> **`12/12`** | `0px` -> **`0px`** | `3.18° (0/41)` -> **`2.20° (0/41)`** | `25.81° (41/41)` -> **`7.73° (0/41)`** | **PASS** |
| `aim` | `1f @ 30fps` | `12/12` -> **`12/12`** | `0px` -> **`0px`** | `7.22° (0/1)` -> **`6.93° (0/1)`** | `20.06° (1/1)` -> **`11.57° (0/1)`** | **PASS** |
| `idle-turn` | `9f @ 30fps` | `12/12` -> **`12/12`** | `0px` -> **`0px`** | `4.49° (0/41)` -> **`4.57° (0/41)`** | `25.42° (37/41)` -> **`12.86° (0/41)`** | **PASS** |
| `run-to-idle` | `9f @ 30fps` | `12/12` -> **`12/12`** | `0px` -> **`0px`** | `11.36° (0/41)` -> **`10.16° (0/41)`** | `27.34° (14/41)` -> **`7.21° (0/41)`** | **PASS** |

---

## Spineboy mapping (`rig-c/examples#80`)

Source reference: Esoteric Software LLC's `spineboy-pro.json` (`24ccffc13e334e721dfd427ee2b8aea05c25b59167b5fb0bb0f9685e11d2a7d3`, Spine `4.3.75-beta`, compiled here to Spine `4.3.13`).

| Category | `spineboy-pro.json` | Kept | Dropped | Added | Final `rigboy v2` |
| --- | ---: | ---: | ---: | ---: | ---: |
| **Bones** | 67 | 40 | 27 | 0 | **40** |
| **Slots** | 52 | 26 | 26 | 2 | **28** (`20` with region attachments, `8` unattached, `0` meshes) |
| **Constraints** | 14 | 10 (`6` IK, `4` transform) | 4 (`1` IK, `3` transform) | 0 | **10** |
| **Animations** | 11 | 9 | 2 (`hoverboard`, `portal`) | 0 | **9** |

- **27 dropped bones:** `hip-controller`, `board-ik`, `hoverboard-controller`, `hoverboard-thruster-front`, `hoverboard-thruster-rear`, `flare-front`, `jet-Exhaust1`, `jet-smoke4`, `jet-smoke3`, `flare-rear`, `jet-Exhaust2`, `jet-smoke1`, `jet-smoke2`, `muzzle`, `muzzle-ring`, `Front-Boot-Turn-Target`, `board-back`, `board-front`, `board-line`, `portal-root`, `portal`, `portal-shade`, `portal-streak1`, `portal-streak2`, `flare1`, `flare2`, `flare3`.
- **26 dropped slots:** `portal-bg`, `portal-shade`, `portal-ray1`..`portal-ray3`, `portal-flare1`..`portal-flare3`, `portal-streak1`, `portal-streak2`, `Rear-jet-smoke`, `Jet-exhaust-rear`, `Flame-rear-glow`, `Front-jet-smoke`, `Front-jet-smoke2`, `Jet-exhaust-front`, `Flame-front-glow`, `board-bottom`, `rear-foot-line`, `front-foot-line`, `board-body`, `rear-toes`, `front-toes`, `front-boot-turn`, `gun-back`, `eye-Rays`.
- **4 dropped constraints:** `board-ik` (IK), `front-foot-board-transform` (transform), `rear-foot-board-transform` (transform), `toes-board` (transform).
- **20 attached region slots** (`skins.default`, 0 meshes): `rear-upper-arm`, `rear-bracer`, `gun`, `rigboy-rear-gauntlet` *(added on `gun`)*, `rear-thigh`, `rear-shin`, `rear-foot`, `rigboy-rear-ankle-band` *(added on `rear-foot`)*, `neck`, `torso`, `front-thigh`, `front-shin`, `front-foot`, `head`, `eye` (`eye-indifferent`, `eye-surprised`), `mouth` (`mouth-smile`, `mouth-grind`, `mouth-oooo`), `goggles`, `front-upper-arm`, `front-bracer`, `front-fist` (`front-fist-closed`, `front-fist-open`). Slots `rear-foot`/`rigboy-rear-ankle-band` draw over `rear-shin`, and `front-foot` draws over `front-shin` so the painted gold boot cuff overlays the shin.
- **8 kept unattached slots** (so `shoot` colour timelines and bone references resolve cleanly): `muzzle`, `head-bb`, `crosshair`, `muzzle-glow`, `muzzle-ring`, `muzzle-ring2`, `muzzle-ring3`, `muzzle-ring4`.

### Base scale $S$ and bone exceptions

The uniform base scale factor from `spineboy-pro.json` to the `416×624` v2 canvas is $S = 0.621722553915$ ($1/S = 1.608434491725$).

- **16 kept bones follow pure uniform scale $S$** ($\Delta x = 0, \Delta y = 0, \Delta\text{length} = 0, \Delta\text{rotation} = 0^\circ$):
  `root`, `crosshair`, `aim-constraint-target`, `rear-leg-target`, `front-leg-target`, `gun-tip`, `hair1`, `hair2`, `hair3`, `hair4`, `muzzle`, `muzzle-ring`, `muzzle-ring2`, `muzzle-ring3`, `muzzle-ring4`, `head-control`.
- **24 kept bones depart from uniform scale $S$** (all 40 bones keep $\Delta\text{rotation} = 0.0^\circ$):
  1. **Axial proportion refit (`b10e-proportion-axis`):** 17 segment lengths and 14 child local `x` origins shifted along their parent bone axes to match `rigboy v2` proportions.
  2. **Joint-pivot and cap-centre alignment:** 5 proximal origins (`hip`, `front-thigh`, `rear-thigh`, `front-shoulder`, `back-shoulder`) placed on the painted joint centres in Round 2, plus sub-pixel cap-centre alignment (`0.60..0.80 px`, with inverse child-attachment offsets preserving rest world pose) on `front-fist`, `front-foot` (`front-foot-tip`), and `rear-bracer` (`gun`).
  3. **IK target & hip height tuning:** `hip.y + 7.0 px` (`149.0259`), `front-foot-target.x + 30.0 px` (`21.5883`), and `rear-foot-target.x - 18.0 px` (`20.4898`) to align the two-bone leg IK targets with the forward `front-thigh` (`+7.27`) and rear `rear-thigh` (`-9.28`) hip sockets.

| Bone | Parent | Source `(x, y, length)` | Uniform $S \times \text{src}$ `(x, y, length)` | Final `rigboy v2` `(x, y, length)` | $\Delta$ from $S$ `(\Delta x, \Delta y, \Delta\text{length})` |
| --- | --- | --- | --- | --- | --- |
| `hip` | `root` | `(0.00, 247.27, 0.00)` | `(0.0000, 153.7333, 0.0000)` | `(1.1265, 149.0259, 0.0000)` | `(+1.1265, -4.7074, +0.0000)` |
| `rear-foot-target` | `root` | `(61.91, 0.42, 0.00)` | `(38.4898, 0.2618, 0.0000)` | `(20.4898, 0.2618, 0.0000)` | `(-18.0000, +0.0000, +0.0000)` |
| `rear-thigh` | `hip` | `(8.91, -5.63, 85.72)` | `(5.5416, -3.4982, 53.2938)` | `(-9.2784, 1.3543, 70.6872)` | `(-14.8200, +4.8526, +17.3934)` |
| `rear-shin` | `rear-thigh` | `(86.10, -1.33, 121.88)` | `(53.5303, -0.8240, 75.7739)` | `(70.6824, -0.8240, 51.0748)` | `(+17.1521, -0.0000, -24.6991)` |
| `rear-foot` | `rear-shin` | `(121.46, -0.76, 51.58)` | `(75.5138, -0.4695, 32.0696)` | `(51.0726, -0.4695, 37.2202)` | `(-24.4412, -0.0000, +5.1506)` |
| `back-foot-tip` | `rear-foot` | `(51.17, 0.24, 50.30)` | `(31.8110, 0.1481, 31.2736)` | `(37.2199, 0.1481, 31.2736)` | `(+5.4089, +0.0000, +0.0000)` |
| `torso` | `hip` | `(-1.62, 4.90, 42.52)` | `(-1.0056, 3.0490, 26.4351)` | `(-1.0056, 3.0490, 32.5871)` | `(-0.0000, +0.0000, +6.1519)` |
| `torso2` | `torso` | `(42.52, 0.00, 42.52)` | `(26.4351, 0.0000, 26.4351)` | `(32.5871, 0.0000, 32.5871)` | `(+6.1519, +0.0000, +6.1519)` |
| `torso3` | `torso2` | `(42.52, 0.00, 42.52)` | `(26.4351, 0.0000, 26.4351)` | `(32.5871, 0.0000, 32.5417)` | `(+6.1519, +0.0000, +6.1066)` |
| `front-shoulder` | `torso3` | `(18.72, 19.33, 0.00)` | `(11.6395, 12.0174, 0.0000)` | `(33.5136, -14.5780, 0.0000)` | `(+21.8741, -26.5954, +0.0000)` |
| `front-upper-arm` | `front-shoulder` | `(0.00, 0.00, 69.45)` | `(0.0000, 0.0000, 43.1800)` | `(0.0000, 0.0000, 61.9276)` | `(+0.0000, +0.0000, +18.7476)` |
| `front-bracer` | `front-upper-arm` | `(68.80, -0.68, 40.57)` | `(42.7765, -0.4252, 25.2233)` | `(61.9262, -0.4252, 52.3174)` | `(+19.1497, -0.0000, +27.0941)` |
| `front-fist` | `front-bracer` | `(40.57, 0.20, 65.39)` | `(25.2230, 0.1237, 40.6515)` | `(52.1413, -0.4920, 63.0755)` | `(+26.9183, -0.6157, +22.4239)` |
| `front-foot-target` | `root` | `(-13.53, 0.04, 0.00)` | `(-8.4117, 0.0250, 0.0000)` | `(21.5883, 0.0250, 0.0000)` | `(+30.0000, +0.0000, +0.0000)` |
| `front-thigh` | `hip` | `(-17.46, -11.64, 74.81)` | `(-10.8546, -7.2395, 46.5089)` | `(7.2672, 4.7437, 72.2278)` | `(+18.1218, +11.9832, +25.7189)` |
| `front-shin` | `front-thigh` | `(78.69, 1.60, 128.77)` | `(48.9234, 0.9958, 80.0577)` | `(72.2209, 0.9958, 61.6445)` | `(+23.2975, +0.0000, -18.4132)` |
| `front-foot` | `front-shin` | `(128.76, -0.34, 41.01)` | `(80.0503, -0.2110, 25.4961)` | `(61.1656, -0.8540, 30.1865)` | `(-18.8848, -0.6430, +4.6903)` |
| `front-foot-tip` | `front-foot` | `(41.42, -0.09, 56.03)` | `(25.7546, -0.0552, 34.8347)` | `(30.9874, -0.0262, 34.8347)` | `(+5.2328, +0.0290, +0.0000)` |
| `back-shoulder` | `torso3` | `(7.32, -19.22, 0.00)` | `(4.5498, -11.9501, 0.0000)` | `(28.9969, -11.9837, 0.0000)` | `(+24.4471, -0.0337, +0.0000)` |
| `rear-upper-arm` | `back-shoulder` | `(0.00, 0.00, 51.94)` | `(0.0000, 0.0000, 32.2919)` | `(0.0000, 0.0000, 44.4770)` | `(+0.0000, +0.0000, +12.1851)` |
| `rear-bracer` | `rear-upper-arm` | `(51.36, 0.00, 34.56)` | `(31.9304, 0.0000, 21.4857)` | `(44.2649, -0.5657, 32.5362)` | `(+12.3345, -0.5657, +11.0505)` |
| `gun` | `rear-bracer` | `(34.42, -0.45, 43.11)` | `(21.4009, -0.2822, 26.7998)` | `(32.9525, 0.1545, 33.6600)` | `(+11.5516, +0.4367, +6.8601)` |
| `neck` | `torso3` | `(42.46, -0.31, 25.45)` | `(26.3976, -0.1918, 15.8253)` | `(32.5412, -0.1918, 46.0973)` | `(+6.1435, -0.0000, +30.2720)` |
| `head` | `neck` | `(27.66, -0.26, 131.79)` | `(17.1989, -0.1616, 81.9391)` | `(46.0971, -0.1616, 163.4929)` | `(+28.8982, -0.0000, +81.5538)` |

### Animation timelines

| Animation | Duration | Timeline adjustments beyond uniform translation scale $S$ |
| --- | ---: | --- |
| `idle` | `1.6667 s` | None (`1.0 × S`) |
| `walk` | `1.0000 s` | `front-foot-target.translate` & `rear-foot-target.translate` `x` scaled by `0.85 × S`; `rear-foot-target.translate` `x + 18 px` (preserving world trajectory under setup `rear-foot-target.x - 18`) |
| `run` | `0.6667 s` | `front-foot-target.translate` scaled by `(0.85, 0.75) × S`; `rear-foot-target.translate` scaled by `(0.85, 0.75) × S` with `x + 8 px` |
| `jump` | `1.3333 s` | `front-shoulder.translate` and `back-shoulder.translate` counter-translate `torso2`/`torso3` flexion so both shoulder discs stay inside the rigid `torso.png` silhouette |
| `shoot` | `0.6333 s` | None (`1.0 × S`) |
| `aim` | `0.0000 s` | None (`1.0 × S`) |
| `idle-turn` | `0.2667 s` | None (`1.0 × S`) |
| `run-to-idle` | `0.2667 s` | `rear-foot-target.translate` entry keys (`t = 0, 0.0667`) `x + 18 px` to transition from `run` into the `idle` stance |
| `death` | `4.9333 s` | `front-shoulder.translate` (`t = 0..1.0 s`) counter-translates `torso2`/`torso3` forward flexion so `near shoulder` stays inside `torso.png` |

---

## Terms and credits

`rigboy v2` derives its bone hierarchy, constraints and nine human animation timelines from Esoteric Software LLC's `spineboy-pro.json` (`24ccffc13e334e721dfd427ee2b8aea05c25b59167b5fb0bb0f9685e11d2a7d3`). Spineboy's `license.txt` states:

> Copyright (c) 2013, Esoteric Software LLC
>
> The images in this project may be redistributed as long as they are accompanied by this license file. The images may not be used for commercial use of any kind.
>
> The project file is released into the public domain. It may be used as the basis for derivative work.

- **Public-domain project file only; zero Spineboy images:** Only the public-domain project file (`spineboy-pro.json`) was used. None of Spineboy's images are used or redistributed here (0 SHA-256 matches across all 206 PNGs in `rigboy/` against all 42 Spineboy PNGs).
- **Artwork credit:** Painted with **Hassaku XL (Illustrious) v1.3 Style A by Ikena** (https://civitai.com/models/140272?modelVersionId=1240288), Fair AI Public License 1.0-SD (`seed 805082`), decomposed into limb pieces via two-stage turnaround inpainting, Flux Kontext and See-through, and finished with circular joint caps by `@rig-c/parts`. The repository's [MIT licence](../../LICENSE) and the checkpoint publisher's own terms concern their respective material.
