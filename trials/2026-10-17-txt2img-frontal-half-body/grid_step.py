#!/usr/bin/env python3
"""grid_step.py -> grid_step.json. How finely does the keypoint script place a point on these paintings?
For each candidate: the smallest non-zero difference between distinct y values, over the 17 body joints and over all 133
whole-body points of kp/<mode>_<seed>.json, in painting px (1664x2432). Reads only the committed keypoint files."""
import json
rows = {}
def step(vals):
    v = sorted(set(vals)); g = [b - a for a, b in zip(v, v[1:]) if b - a > 0.05]
    return round(min(g), 1)
for mode in ('free', 'pose'):
    for seed in range(1, 9):
        k = json.load(open(f'kp/{mode}_{seed}.json'))
        rows[f'{mode}/{seed}'] = {'body17_min_y_step_px': step(v[1] for n, v in k['joints'].items() if n != 'neck'),
                                 'wholebody133_min_y_step_px': step(p[1] for p in k['wholebody'])}
json.dump(rows, open('grid_step.json', 'w'), indent=1)
for key in ('body17_min_y_step_px', 'wholebody133_min_y_step_px'):
    v = [r[key] for r in rows.values()]; print(key, min(v), '-', max(v))
