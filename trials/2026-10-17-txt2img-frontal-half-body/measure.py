#!/usr/bin/env python3
"""measure.py -> measure.json. Reads kp/<mode>_<seed>.json (keypoints.py output on the 1664x2432 painting) and the painting.
Units: painting px. Definitions (the brief names the bars, not the formulas, so these are this squad's):
  shoulder_ratio = min(dL, dR) / max(dL, dR), dX = |X_shoulder.x - nose.x|  (left-right symmetry about the face's midline; bar >= 0.95)
  eye_dy         = |l_eye.y - r_eye.y|                                          (bar <= 3 px)
  eye_dy_face    = |mean y of face landmarks 42-47 - mean y of 36-41| (wholebody 65-70 vs 59-64): the same instrument's six-point eye
                   outlines, averaged, as a finer second reading of the same bar (body-eye y comes in ~5 px steps here, see REPORT)
  ear_ratio      = the same symmetry for the ears (a head-yaw proxy; no bar, reported only)
  head_frac      = (chin.y - hair_top.y) / H; chin = wholebody face landmark 8 (index 31); hair_top = first row, over the columns
                   between the ears, whose pixel differs from the background (median of the top-left 32x32 patch) by > 40 summed RGB
                   (brief: head >= 1/3 of the frame)
  ctrl_err       = pose set only: distance from each control point x2 to the measured joint (control is at the 832x1216 latent)."""
import json
import numpy as np
from PIL import Image
ctrl = json.load(open('control_pose.json'))['points']
out = {'definitions': __doc__, 'bars': {'shoulder_ratio_min': 0.95, 'eye_dy_max_px': 3, 'head_frac_min': 1 / 3}, 'candidates': {}}
for mode in ('free', 'pose'):
    for seed in range(1, 9):
        k = json.load(open(f'kp/{mode}_{seed}.json')); J = k['joints']; wb = k['wholebody']
        im = np.asarray(Image.open(f'{mode}/{seed}.png').convert('RGB')).astype(int); H, W = im.shape[:2]
        nx = J['nose'][0]
        dl, dr = abs(J['l_shoulder'][0] - nx), abs(J['r_shoulder'][0] - nx)
        el, er = abs(J['l_ear'][0] - nx), abs(J['r_ear'][0] - nx)
        bg = np.median(im[:32, :32].reshape(-1, 3), axis=0)
        x0, x1 = sorted([int(J['r_ear'][0]), int(J['l_ear'][0])])
        diff = np.abs(im[:, x0:x1 + 1] - bg).sum(axis=2) > 40
        rows = np.where(diff.any(axis=1))[0]; top = int(rows[0]) if len(rows) else None
        chin = wb[31]
        r = {'people_detected': k['people_detected'],
             'shoulder_ratio': round(min(dl, dr) / max(dl, dr), 3), 'eye_dy_px': round(abs(J['l_eye'][1] - J['r_eye'][1]), 1),
             'eye_dy_face_px': round(abs(np.mean([wb[i][1] for i in range(65, 71)]) - np.mean([wb[i][1] for i in range(59, 65)])), 1),
             'ear_ratio': round(min(el, er) / max(el, er), 3),
             'head_frac': (round((chin[1] - top) / H, 3) if top is not None else None), 'hair_top_y': top, 'chin': chin,
             'scores': {n: J[n][2] for n in ('nose', 'l_eye', 'r_eye', 'l_ear', 'r_ear', 'l_shoulder', 'r_shoulder')},
             'bg_rgb': [int(v) for v in bg]}
        r['front_pass'] = bool(r['shoulder_ratio'] >= 0.95 and r['eye_dy_px'] <= 3)
        r['front_pass_face_eyes'] = bool(r['shoulder_ratio'] >= 0.95 and r['eye_dy_face_px'] <= 3)
        r['head_pass'] = bool(r['head_frac'] is not None and r['head_frac'] >= 1 / 3)
        if mode == 'pose':
            r['ctrl_err_px'] = {n: round(float(np.hypot(J[n][0] - 2 * p[0], J[n][1] - 2 * p[1])), 1) for n, p in ctrl.items()}
        out['candidates'][f'{mode}/{seed}'] = r
json.dump(out, open('measure.json', 'w'), indent=1)
print('cand   people sh_ratio eye_dy eye_dy_face ear_ratio head_frac front front_face head')
for c, r in out['candidates'].items():
    print(f"{c:7s} {r['people_detected']} {r['shoulder_ratio']:.3f} {r['eye_dy_px']:5.1f} {r['eye_dy_face_px']:5.1f} {r['ear_ratio']:.3f} {r['head_frac']} {r['front_pass']} {r['front_pass_face_eyes']} {r['head_pass']}"
          + (f"  ctrl max {max(r['ctrl_err_px'].values())} ({max(r['ctrl_err_px'], key=r['ctrl_err_px'].get)})" if 'ctrl_err_px' in r else ''))
