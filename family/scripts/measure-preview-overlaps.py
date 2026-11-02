#!/usr/bin/env python3
"""Measure the clip paths that let the README preview draw one character at two depths.

The lineup is not one depth order. Roa stands behind Luna with her hand on Luna's shoulder, so
Roa is drawn again above Luna inside the path around that hand. Jinni stands in front of Luna
with her arm and legs behind Luna's, so Luna is drawn again above Jinni inside the paths around
them. Naru stands in front of Jinni but Jinni's skirt is in front of Naru, so Jinni is drawn again
above Naru inside the path around the skirt. Each path is the part's overlap with the other
character, unioned over every captured frame of the loop and grown by GROW capture pixels, read
from renders of each character alone at its lineup place (render-readme-preview.mjs --isolate).
Where an outfit paints the part into its own slots, the part is those slots; where it does not, a
row window separates it.

Usage: measure-preview-overlaps.py --work <new-dir> [--out family/scripts/preview-overlaps.json]
PLAYWRIGHT_MODULE and PYTHON pass through to the renderer.
"""
import argparse, hashlib, json, subprocess, sys
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

FAMILY = Path(__file__).resolve().parent.parent
RENDER = FAMILY / 'scripts' / 'render-readme-preview.mjs'
OUTFITS = ['office', 'homewear', 'swimwear', 'uniform']
ALPHA = 8   # a pixel belongs to a character above this alpha (0..255)
GROW = 2    # capture pixels the union is grown by, so a path edge never lands on the overlap's own edge

# Each layer is one character's part drawn against another character. A part is a set of slots
# (None = every slot), optionally narrowed to capture rows [lo, hi); the other character is every
# slot, or every slot but a named set. Per outfit, since the outfits paint parts into different slots.
EVERY = {outfit: None for outfit in OUTFITS}
ARM = {
    # Office Roa paints the arm into `topwear`; there the overlap splits into a shoulder part and a
    # hip part with a measured gap between them (capture rows 346 and 456), and the rows keep the first.
    'roa': ({'office': None, 'homewear': ['sleeves'], 'swimwear': ['sleeves'], 'uniform': ['sleeves']},
            {'office': (0, 400)}),
    'jinni': ({'office': ['handwear_r'], 'homewear': ['sleeves'], 'swimwear': ['sleeves'], 'uniform': ['sleeves']}, {}),
}
# Luna's head and neck: Roa's forearm passes behind them and only her hand lies on Luna's shoulder.
# Luna's throat is painted into topwear as well, so the hand also stops at the column where Luna's
# face begins (STOP_AT).
HEAD = {'except': ['hair_back', 'hair_front', 'neck', 'face', 'eyewhite_r', 'eyewhite_l', 'iris_r', 'iris_l', 'nose',
                   'mouth', 'lash_r', 'lash_l', 'brow_r', 'brow_l', 'eyewear']}
# Jinni's legs: her overlap with Luna below these capture rows, read from frame 0. Office and
# uniform cut at the skirt's hem (bottomwear's last row 633, 617; office has no overlap between
# rows 621 and 679). Homewear and swimwear paint the legs into bottomwear: homewear cuts where the
# arm's path ends (row 516), so the two paths meet; swimwear cuts in the gap between the sarong's
# edge and the leg (one overlapping pixel per row over rows 660-680).
LEGS_FROM = {'office': (650, 2000), 'homewear': (500, 2000), 'swimwear': (670, 2000), 'uniform': (618, 2000)}
SKIRT = {outfit: ['bottomwear'] for outfit in OUTFITS}
PAIRS = [
    # name, (character, slots, rows) of the part, (character, slots) it is drawn against, which one is drawn again, its z
    ('roa-hand-over-luna', ('roa', *ARM['roa']), ('luna', HEAD), 'roa', 35),
    ('jinni-arm-behind-luna', ('jinni', *ARM['jinni']), ('luna', None), 'luna', 45),
    ('jinni-legs-behind-luna', ('jinni', EVERY, LEGS_FROM), ('luna', None), 'luna', 45),
    ('jinni-skirt-over-naru', ('jinni', SKIRT, {}), ('naru', None), 'jinni', 55),
]
STOP_AT = {'roa-hand-over-luna': ('luna', ['hair_front'])}


def model_slots(outfit, key):
    root = FAMILY / key if outfit == 'office' else FAMILY / 'outfits' / outfit / key
    return [slot['name'] for slot in json.loads((root / 'out/check/build/skeleton.model.json').read_text())['slots']]


def isolate(work, outfit, key, slots):
    name = key + ('' if slots is None else '-' + '-'.join(slots) if len(slots) < 4 else '-' + hashlib.sha256(','.join(slots).encode()).hexdigest()[:12])
    evidence = work / outfit / name
    if not evidence.exists():
        spec = key if slots is None else key + ':' + ','.join(slots)
        subprocess.run(['node', str(RENDER), '--outfit', outfit, '--isolate', spec, '--evidence', str(evidence)],
                       check=True, stdout=subprocess.DEVNULL)
    metadata = json.loads((evidence / 'isolate.json').read_text())
    frames = sorted(evidence.glob('frame-*.png'))
    if len(frames) != metadata['frames'] + 1 or [f.name for f in frames] != sorted(metadata['frameSHA256']):
        sys.exit(f'OVERLAP_FRAMES_INCOMPLETE {evidence}: {len(frames)} frames')
    masks = np.stack([np.array(Image.open(f))[..., 3] > ALPHA for f in frames])
    return masks, metadata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', required=True)
    parser.add_argument('--out', default=str(FAMILY / 'scripts' / 'preview-overlaps.json'))
    args = parser.parse_args()
    work = Path(args.work).resolve()
    result = {'schema': 'family-preview-overlaps/1', 'generatedBy': 'family/scripts/measure-preview-overlaps.py',
              'alpha': ALPHA, 'grow': GROW, 'outfits': {}}
    for outfit in OUTFITS:
        layers = []
        for name, (partKey, partSlots, partRows), (otherKey, otherSpec), drawn, z in PAIRS:
            slots = partSlots[outfit]
            if not slots and not partRows.get(outfit): sys.exit(f'OVERLAP_PART_UNBOUNDED {outfit} {name}')
            otherSlots = None if otherSpec is None else [n for n in model_slots(outfit, otherKey) if n not in otherSpec['except']]
            part, meta = isolate(work, outfit, partKey, slots)
            other, otherMeta = isolate(work, outfit, otherKey, otherSlots)
            whole, _ = isolate(work, outfit, partKey, None)
            # An isolated render's lineup holds its one character, at its place in the full lineup.
            scene, lineup = meta['scene'], {key: offset for m in (meta, otherMeta) for key, offset, *_ in m['lineup']}
            region = (part & other).any(axis=0)
            rows = partRows.get(outfit)
            if rows: region[:rows[0]] = False; region[rows[1]:] = False
            stop = None
            if name in STOP_AT:
                stopMask, _ = isolate(work, outfit, *STOP_AT[name])
                stop = int(np.nonzero(stopMask.any(axis=(0, 1)))[0].min())
                region[:, stop:] = False
            if not region.any(): sys.exit(f'OVERLAP_EMPTY {outfit} {name}')
            grown = cv2.dilate(region.astype(np.uint8), np.ones((2 * GROW + 1, 2 * GROW + 1), np.uint8)) > 0
            contours, _ = cv2.findContours(grown.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            offset = lineup[drawn]
            path = ''
            for contour in sorted(contours, key=lambda c: tuple(c[0][0])):
                points = cv2.approxPolyDP(contour, 0.75, True)[:, 0, :]
                path += 'M' + 'L'.join(f'{(x - scene["left"]) / scene["scale"] - offset:.1f} {(y - scene["top"]) / scene["scale"]:.1f}'
                                       for x, y in points) + 'Z'
            # What else the second drawing changes: the rest of the part's character inside the path,
            # where it overlaps the other character, in the frame where that is largest.
            rest = (whole & ~part & other & grown).reshape(len(whole), -1).sum(axis=1)
            ys, xs = np.nonzero(grown)
            layers.append({'name': name, 'key': drawn, 'z': z, 'clip': path, 'measured': {
                'frames': int(len(part)), 'partSlots': slots, 'rows': list(rows) if rows else None, 'columnsBefore': stop,
                'against': otherKey + ('' if otherSpec is None else ' without ' + ', '.join(otherSpec['except'])),
                'overlapPixels': int(region.sum()), 'pathBox': [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1],
                'restPixelsMax': int(rest.max()), 'restPixelsMaxFrame': int(rest.argmax())}})
            print(outfit, name, layers[-1]['measured'])
        result['outfits'][outfit] = layers
    Path(args.out).write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
