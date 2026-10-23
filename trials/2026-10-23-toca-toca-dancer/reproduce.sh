#!/bin/sh
# Run from this trial directory; acquisition is reused, never rerun implicitly.
set -eu
exec python3 reproduce.py
