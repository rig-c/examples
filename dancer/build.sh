#!/bin/sh
# From dancer/. Inputs are unchanged; outputs stay in work/.
set -eu
python3 check-inputs.py
mkdir -p work/runtime
cp package.json work/runtime/package.json
(cd work/runtime && bun install)
exec bun --bun run work/runtime/node_modules/.bin/rig-parts build --config config.json --source painting.png --full layers/full --head layers/head --requirements requirements.json --out work/build
