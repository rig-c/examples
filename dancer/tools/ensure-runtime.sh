#!/bin/sh
# Frozen dancer runtime shared by producer adoption and accepted replay.
set -eu
cd "$(dirname "$0")/.."
mkdir -p work/runtime
cp package.json bun.lock work/runtime/
(cd work/runtime && bun install --frozen-lockfile)
