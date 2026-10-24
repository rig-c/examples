#!/bin/bash
# See-through on a hold painting, as keys2/run_seethrough.sh did (alts/seethrough_config.json for the input cut; resolution 1024,
# steps 30, seed 42, no --offload, no --lama). usage: keys3/run_seethrough.sh <K> <painting.png>   (run from the dancer directory,
# COMFY_HOST set; rig-parts from the scratch install). Writes keys3/set_<K>/ and appends to keys3/seethrough.log.
set -u
B=${RIG_PARTS_BIN:?set RIG_PARTS_BIN to the pinned runtime bin directory}
K=$1; IMG=$2
echo "=== $K $(date +%H:%M:%S) $IMG" >> keys3/seethrough.log
$B/rig-parts inputs --source "$IMG" --config alts/seethrough_config.json --out keys3/set_$K >> keys3/seethrough.log 2>&1 || { echo "inputs failed $K" >> keys3/seethrough.log; exit 1; }
$B/rig-parts comfy seethrough --image keys3/set_$K/st_input_full.png --out keys3/set_$K/layers_full --resolution 1024 --steps 30 --seed 42 --prefix rigc_keys3_$K --wait 900 --host "$COMFY_HOST" >> keys3/seethrough.log 2>&1 || { echo "seethrough failed $K rc=$?" >> keys3/seethrough.log; exit 2; }
echo "=== done $K $(date +%H:%M:%S)" >> keys3/seethrough.log
