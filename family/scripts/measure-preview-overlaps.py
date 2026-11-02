#!/usr/bin/env python3
"""Measure the clip paths that let the README preview draw one character at two depths.

Two places in the lineup are not one depth order. Roa stands behind Luna with her arm over
Luna's shoulder, so Roa is drawn again above Luna inside the path around that arm. Jinni stands
in front of Luna with her arm behind Luna's, so Luna is drawn again above Jinni inside the path
around that arm. Each path is the arm's overlap with the other character, unioned over every
captured frame of the loop and grown by GROW capture pixels, read from renders of each character
alone at its lineup place (render-readme-preview.mjs --isolate). Where an outfit paints the arm
into its own slot, the arm is that slot; where it does not, a row window separates it.

Usage: measure-preview-overlaps.py --work <new-dir> [--out family/scripts/preview-overlaps.json]
PLAYWRIGHT_MODULE and PYTHON pass through to the renderer.
"""
import argparse, json, subprocess, sys
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

FAMILY = Path(__file__).resolve().parent.parent
RENDER = FAMILY / 'scripts' / 'render-readme-preview.mjs'
OUTFITS = ['office', 'homewear', 'swimwear', 'uniform']
ALPHA = 8   # a pixel belongs to a character above this alpha (0..255)
GROW = 2    # capture pixels the union is grown by, so a path edge never lands on the overlap's own edge

# The arm's slots per outfit. Office Roa paints the arm into `topwear`; there the overlap splits
# into a shoulder part and a hip part with a measured gap between them (capture rows 346 and 456),
# and ROWS keeps the shoulder part.
ARM = {
    'roa': {'office': None, 'homewear': ['sleeves'], 'swimwear': ['sleeves'], 'uniform': ['sleeves']},
    'jinni': {'office': ['handwear_r'], 'homewear': ['sleeves'], 'swimwear': ['sleeves'], 'uniform': ['sleeves']},
}
ROWS = {('roa', 'office'): 400}
PAIRS = [
    # name, character whose arm it is, the other character, which one is drawn again, its z
    ('roa-arm-over-luna', 'roa', 'luna', 'roa', 35),
    ('jinni-arm-behind-luna', 'jinni', 'luna', 'luna', 45),
]


def isolate(work, outfit, key, slots):
    name = key + ('' if slots is None else '-' + '-'.join(slots))
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
        for name, armKey, otherKey, drawn, z in PAIRS:
            arm, meta = isolate(work, outfit, armKey, ARM[armKey][outfit])
            other, otherMeta = isolate(work, outfit, otherKey, None)
            whole, _ = isolate(work, outfit, armKey, None)
            # An isolated render's lineup holds its one character, at its place in the full lineup.
            scene, lineup = meta['scene'], {key: offset for m in (meta, otherMeta) for key, offset, *_ in m['lineup']}
            region = (arm & other).any(axis=0)
            if (armKey, outfit) in ROWS: region[ROWS[(armKey, outfit)]:] = False
            if not region.any(): sys.exit(f'OVERLAP_EMPTY {outfit} {name}')
            grown = cv2.dilate(region.astype(np.uint8), np.ones((2 * GROW + 1, 2 * GROW + 1), np.uint8)) > 0
            contours, _ = cv2.findContours(grown.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            offset = lineup[drawn]
            path = ''
            for contour in sorted(contours, key=lambda c: tuple(c[0][0])):
                points = cv2.approxPolyDP(contour, 0.75, True)[:, 0, :]
                path += 'M' + 'L'.join(f'{(x - scene["left"]) / scene["scale"] - offset:.1f} {(y - scene["top"]) / scene["scale"]:.1f}'
                                       for x, y in points) + 'Z'
            # What else the second drawing changes: the rest of the arm's character inside the path,
            # where it overlaps the other character, in the frame where that is largest.
            rest = (whole & ~arm & other & grown).reshape(len(whole), -1).sum(axis=1)
            ys, xs = np.nonzero(grown)
            layers.append({'name': name, 'key': drawn, 'z': z, 'clip': path, 'measured': {
                'frames': int(len(arm)), 'armSlots': ARM[armKey][outfit], 'rowsBelow': ROWS.get((armKey, outfit)),
                'overlapPixels': int(region.sum()), 'pathBox': [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1],
                'restPixelsMax': int(rest.max()), 'restPixelsMaxFrame': int(rest.argmax())}})
            print(outfit, name, layers[-1]['measured'])
        result['outfits'][outfit] = layers
    Path(args.out).write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
