#!/bin/sh
# Standalone dancer corpus replay; heavy execution belongs in the Nova pool.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$here"
if [ "${1:-}" = '--version' ]; then
  version=$2
  shift 2
  exec python3 tools/reproduce-accepted-dance.py --version "$version" --out "${1:-work/accepted-dance-$version}"
fi
exec python3 tools/reproduce-accepted-dance.py --out "${1:-work/accepted-dance}"
