#!/bin/sh
# From dancer/. Fresh output is optional; runtime and dependencies are frozen.
set -eu
python3 check-inputs.py
sh tools/ensure-runtime.sh
exec bun --bun run work/runtime/node_modules/.bin/rig-parts build --config config.json --source painting.png --full layers/full --head layers/head --requirements requirements.json --out "${1:-work/build}"
