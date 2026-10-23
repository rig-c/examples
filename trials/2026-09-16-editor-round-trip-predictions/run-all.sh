#!/usr/bin/env bash
#
# Round trip 6, one editor session over every probe rig.
#
#   ./run-all.sh                 # every rig
#   ./run-all.sh xform shear     # only these
#   RIGC_ROOT=/path/to/rigc ./run-all.sh
#
# It writes ONLY under this directory (round6/out/<rig>/), and it is idempotent:
# each rig's build and roundtrip directories are removed and remade. Nothing
# under the rigc checkout is touched, and no git command is run.
#
# ⚠️ The editor calls are NOT wrapped in an outer alarm, and that is deliberate.
# tools/editor_roundtrip.ts bounds every editor call itself -- spawnSync with a
# timeout, DEFAULT_TIMEOUT_S = 600, surfaced as --timeout -- and reports a bound
# that fired as a HANG rather than as a result ("the editor did not return within
# 600s on import -- that is a hang, not a result"). Wrapping it again would kill
# the harness mid-run and throw away the log that says what the editor printed,
# which is the whole of what issue #541 cost. The bound is passed explicitly
# below so the number is visible here rather than only in the tool's default.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RIGC_ROOT="${RIGC_ROOT:?set RIGC_ROOT to a rig-c/core checkout}"
export RIGC_ROOT
TIMEOUT_S="${TIMEOUT_S:-600}"
FPS="${FPS:-12}"

if [ ! -f "$RIGC_ROOT/cli.ts" ]; then
  echo "run-all.sh: no cli.ts under RIGC_ROOT=$RIGC_ROOT" >&2
  exit 2
fi

# rig name -> the one flag that differs. `packed` is built with --pack because
# the atlas IS its question; every other rig uses --copy-images, which the
# harness requires (an ordinary build names its pages by path and A17 would
# refuse the export for the harness's own reason).
ALL_RIGS="bbox_clip xform shear draworder pathmodes physlider packed fields"
RIGS="${*:-$ALL_RIGS}"

for rig in $RIGS; do
  src="$HERE/rigs/$rig"
  if [ ! -f "$src/rig.json" ]; then
    echo "run-all.sh: no rig at $src" >&2
    exit 2
  fi
done

for rig in $RIGS; do
  src="$HERE/rigs/$rig"
  out="$HERE/out/$rig"
  build="$out/build"

  echo ""
  echo "==================== $rig ===================="
  rm -rf "$build"
  mkdir -p "$build"

  # 1. the plates. Generated, never drawn and never copied from examples/.
  bun "$src/r6_make_plates.ts"

  # 2. the build. Green or nothing is written -- rigc emits only after green.
  if [ "$rig" = "packed" ]; then
    bun "$RIGC_ROOT/cli.ts" build --rig "$src/rig.json" --motion "$src/motion.json" --out "$build" --pack
  else
    bun "$RIGC_ROOT/cli.ts" build --rig "$src/rig.json" --motion "$src/motion.json" --out "$build" --copy-images
  fi

  # 3. the round trip. The tool refuses by name when there is no licensed editor,
  #    and it bounds every editor call itself (see the header).
  bun "$RIGC_ROOT/tools/editor_roundtrip.ts" \
    --build "$build" \
    --out "$out/roundtrip" \
    --name "$rig" \
    --fps "$FPS" \
    --timeout "$TIMEOUT_S" || echo "run-all.sh: $rig came back non-zero -- read $out/roundtrip/roundtrip.log before anything else"

  # 4. the verdict, from the prediction table alone.
  bun "$HERE/read.ts" --rig "$rig" --build "$build" --export "$out/roundtrip/export" \
    || echo "run-all.sh: $rig has rows that are not CONFIRMED -- that is a finding, not an error"
done

echo ""
echo "==================== every rig ===================="
bun "$HERE/read.ts" --all --out "$HERE/out" || true
echo ""
echo "logs:      $HERE/out/<rig>/roundtrip/roundtrip.log"
echo "exports:   $HERE/out/<rig>/roundtrip/export/"
echo "projects:  $HERE/out/<rig>/roundtrip/<rig>.spine   (inflateRawSync it to grep float32 patterns -- issue #540's recipe)"
