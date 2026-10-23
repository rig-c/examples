#!/usr/bin/env python3
"""make_sheet.py -> sheet.jpg. Two blocks (free, pose); each = a full row and a 2x face-crop row (crop = twice the full row's
scale, centred on the measured eye midpoint, 0.15 crop-height lower). Column 0: empty (free block, no control) and the OpenPose
control (pose block). Labels carry measure.json's numbers."""
import json
from PIL import Image, ImageDraw
M = json.load(open('measure.json'))['candidates']
TW = 240; LBL = 30
def thumb(im, w): return im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
def crop2x(im, cx, cy):
    s = TW / im.width * 2; c = TW / s
    box = (round(cx - c / 2), round(cy - c / 2 + 0.15 * c), round(cx + c / 2), round(cy + c / 2 + 0.15 * c))
    return im.crop(box).resize((TW, TW), Image.LANCZOS)
FH = round(2432 * TW / 1664)
sheet = Image.new('RGB', (9 * TW, 2 * (LBL + FH + TW)), 'white'); d = ImageDraw.Draw(sheet)
for b, mode in enumerate(('free', 'pose')):
    y0 = b * (LBL + FH + TW)
    if mode == 'free':
        d.text((4, y0 + 4), 'free: no control', fill='black')
    else:
        c = Image.open('control_pose.png').convert('RGB'); sheet.paste(thumb(c, TW), (0, y0 + LBL)); sheet.paste(crop2x(c, 416, 404), (0, y0 + LBL + FH))
        d.text((4, y0 + 4), 'OpenPose control', fill='black')
    for s in range(1, 9):
        im = Image.open(f'{mode}/{s}.png').convert('RGB'); r = M[f'{mode}/{s}']; k = json.load(open(f'kp/{mode}_{s}.json'))['joints']
        x = s * TW; sheet.paste(thumb(im, TW), (x, y0 + LBL))
        sheet.paste(crop2x(im, (k['l_eye'][0] + k['r_eye'][0]) / 2, (k['l_eye'][1] + k['r_eye'][1]) / 2), (x, y0 + LBL + FH))
        d.text((x + 4, y0 + 2), f"{mode} {s}  sh {r['shoulder_ratio']:.3f}  head {r['head_frac']}", fill='black')
        d.text((x + 4, y0 + 15), f"eye dy {r['eye_dy_px']} / face {r['eye_dy_face_px']}  {'FRONT' if r['front_pass'] else '-'}", fill='black')
sheet.save('sheet.jpg', quality=85); print(sheet.size)
