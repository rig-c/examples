#!/bin/sh
# Run from the trial root after ./reproduce.sh has populated work/.
# Submit under the documented Nova 6 GiB / four-worker guard.
set -eu
cli=work/runtime/node_modules/.bin/rigc
bun --bun run "$cli" render --candidate work/build --animation zero-two --fps 24 --geometry --folds --viewport-from hand/viewport.json --out hand/work/before-render
python3 hand/apply_hand.py
bun --bun run "$cli" build --rig hand/rig.json --motion hand/motion.json --profile spine --out hand/work/build
bun --bun run "$cli" render --candidate hand/work/build --animation zero-two-hand --fps 24 --geometry --folds --viewport-from hand/viewport.json --out hand/work/final-render
python3 hand/bootstrap_analysis.py
py=hand/work/analysis-env/bin/python
"$py" hand/media.py
"$py" hand/measure_hand.py
# The historical seam reader uses build.parent/rig/images; copy only public inputs.
mkdir -p work/rig/images hand/work/rig/images
cp -R work/corpus/dancer/accepted/images/. work/rig/images/
cp -R work/corpus/dancer/accepted/images/. hand/work/rig/images/
"$py" hand/measure_mesh_seams.py hand/work/before-render/zero-two@24fps/geometry.json work/build hand/work/before-render/zero-two@24fps hand/work/seams-before
"$py" hand/measure_mesh_seams.py hand/work/final-render/zero-two-hand@24fps/geometry.json hand/work/build hand/work/final-render/zero-two-hand@24fps hand/work/seams-after
