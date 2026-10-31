#!/bin/sh
# From dancer/. The normal producer preserves approved projected art before applying setup order.
set -eu
python3 check-inputs.py
out=${1:-work/build}
sh build-setup-order-candidate.sh "$out"
cp "$out/assemble/rig/parts.json" "$out/parts.json"
cp -R "$out/assemble/rig/parts" "$out/parts"
exec bun --bun run work/runtime/node_modules/.bin/rig-parts check --rig "$out/rig" --parts "$out" --requirements requirements.json --out "$out/check"
