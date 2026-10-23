#!/usr/bin/env python3
"""ear_check.py -> ear_check.jpg + ear_check.json. Where do the keypoint script's ear points land on these paintings?
For each of the 16 candidates: the distance from each ear point to the eye point on the same side, divided by the
interocular distance, and a face crop with the eye points (green) and ear points (red) drawn on the 1664x2432 painting.
An ear point "on the eye" would read near 0."""
import json, math
from PIL import Image, ImageDraw
rows = {}; tiles = []
for mode in ('free', 'pose'):
    for seed in range(1, 9):
        k = json.load(open(f'kp/{mode}_{seed}.json'))['joints']
        io = math.dist(k['l_eye'][:2], k['r_eye'][:2])
        dl, dr = math.dist(k['l_ear'][:2], k['l_eye'][:2]), math.dist(k['r_ear'][:2], k['r_eye'][:2])
        rows[f'{mode}/{seed}'] = {'interocular_px': round(io, 1), 'l_ear_to_l_eye_px': round(dl, 1), 'r_ear_to_r_eye_px': round(dr, 1),
                                 'min_ear_eye_over_interocular': round(min(dl, dr) / io, 2)}
        im = Image.open(f'{mode}/{seed}.png').convert('RGB'); d = ImageDraw.Draw(im)
        for n, col in (('l_eye', 'lime'), ('r_eye', 'lime'), ('l_ear', 'red'), ('r_ear', 'red')):
            x, y, _ = k[n]; d.ellipse([x - 12, y - 12, x + 12, y + 12], outline=col, width=6)
        cx, cy = k['nose'][0], k['l_eye'][1]
        t = im.crop((int(cx - 450), int(cy - 300), int(cx + 450), int(cy + 300))).resize((300, 200), Image.LANCZOS)
        ImageDraw.Draw(t).text((4, 4), f'{mode} {seed}', fill='black'); tiles.append(t)
sheet = Image.new('RGB', (1200, 800))
for i, t in enumerate(tiles): sheet.paste(t, ((i % 4) * 300, (i // 4) * 200))
sheet.save('ear_check.jpg', quality=85); json.dump(rows, open('ear_check.json', 'w'), indent=1)
v = [r['min_ear_eye_over_interocular'] for r in rows.values()]; print('min ear-eye / interocular:', min(v), '-', max(v))
