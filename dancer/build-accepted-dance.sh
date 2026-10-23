#!/bin/sh
# Standalone dancer corpus replay; heavy execution belongs in the Nova pool.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$here"
exec python3 tools/reproduce-accepted-dance.py --out "${1:-work/accepted-dance}"
