#!/bin/sh
# External input acquisition, not a rig-pose command.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
python3 "$here/bootstrap.py" "$@"
exec "$here/.runtime/bin/python" "$here/extract.py" "$@"
