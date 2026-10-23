#!/bin/sh
set -eu
python3 check-inputs.py
mkdir -p work/runtime
cp package.json work/runtime/package.json
(cd work/runtime && bun install)
# Optional first argument: a trial motion file; default: the saved base motion.
# Optional second argument: the output directory.
exec bun --bun run work/runtime/node_modules/.bin/rigc build \
  --rig accepted/rig.json --motion "${1:-accepted/motion.json}" \
  --images accepted/images --profile spine --out "${2:-work/accepted}"
