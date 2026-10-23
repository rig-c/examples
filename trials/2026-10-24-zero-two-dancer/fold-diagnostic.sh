#!/bin/sh
# Run after reproduction; no clean/retarget/build.
set -eu
exec bun --bun run work/runtime/node_modules/.bin/rigc render \
  --candidate work/build --animation zero-two --fps 24 --folds \
  --out work/fold-diagnostic
