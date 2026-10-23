#!/bin/sh
# Run after reproduction, from this trial directory; no clean/retarget/build.
set -eu
exec bun --bun run work/runtime/node_modules/.bin/rigc render \
  --candidate work/build --animation toca-toca --fps 30 --folds \
  --out work/fold-diagnostic
