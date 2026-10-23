#!/bin/sh
# From trial root, under Nova pooled 6GiB/four-worker guard; no inference.
set -eu
python3 fetch-inputs.py
mkdir -p work/runtime
cp package.json bun.lock work/runtime/
(cd work/runtime && bun install --frozen-lockfile)
pose=work/runtime/node_modules/.bin/rig-pose
core=work/runtime/node_modules/.bin/rigc
target() {
 bun --bun run "$pose" retarget --rig work/corpus/dancer/accepted --map hand/r3/inputs/map.json --sequence "$1" --out "$2/motion.json" --animation zero-two-r3 --profile spine --build "$2/build" --camera "$2/camera.json" --report "$2/report.json" --flip 90 --short 0.35 --bends clamp --leg-scale 0.8,1.05 --plant-feet --stance 0.04 --carry-idle --raised-by-head
}
target hand/r3/inputs/precheck.json hand/r3/work/precheck
target hand/r3/inputs/sequence.json hand/r3/work/retarget
bun --bun run "$core" render --candidate hand/r3/work/retarget/build --animation zero-two-r3 --fps 30 --geometry --folds --viewport-from hand/r3/viewport.json --out hand/r3/work/before-render
python3 hand/r3/apply_r3_hand.py
bun --bun run "$core" build --rig hand/r3/rig.json --motion hand/r3/motion.json --out hand/r3/work/build --profile spine
bun --bun run "$core" render --candidate hand/r3/work/build --animation zero-two-r3-hand --fps 30 --geometry --folds --pass-through bottomwear:thigh_r,bottomwear:thigh_l,bottomwear:shins --viewport-from hand/r3/viewport.json --out hand/r3/work/final-render
python3 hand/r3/bootstrap_analysis.py
hand/r3/work/analysis-env/bin/python hand/r3/media_r3.py
hand/r3/work/analysis-env/bin/python hand/r3/contact-sheet.py
