#!/bin/sh
# Candidate only: preserve accepted projected art, then generate authored order/motion.
# This does not adopt outputs as the accepted producer or establish visual acceptance.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$here"
out=${1:-work/setup-order-candidate}
if [ -e "$out" ]; then
  echo 'SETUP_ORDER_OUTPUT_EXISTS: choose a fresh output directory' >&2
  exit 2
fi
sh tools/ensure-runtime.sh
parts=work/runtime/node_modules/@rig-c/parts/cli.ts
# The archived config is the exact published producer input, before setup-order edits.
bun "$parts" assemble --config config-before-setup-order.json --source painting.png --full layers/full --head layers/head --out "$out/assemble"
# @rig-c/parts 1.64.0 exports drawOrder from src/assemble.ts. No PNG is rewritten.
bun tools/reorder-setup.ts work/runtime "$out/assemble/rig" painting.png config.json
bun "$parts" rig --config config.json --parts "$out/assemble/rig" --out "$out/rig"
