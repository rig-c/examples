#!/usr/bin/env python3
"""control.py -> control_pose.png + control_pose.json: a front half-body OpenPose control at the latent size (832x1216),
arms folded on a desk. Hips and legs are behind the desk, so they are left out (the standard OpenPose drawer skips missing
points; @rig-c/parts renderSkeleton needs all 18, so this re-draws its LIMB_SEQ / COLORS / stick width in PIL)."""
import json, math
from PIL import Image, ImageDraw
W, H = 832, 1216
P = {'nose': (416, 480), 'neck': (416, 680), 'r_eye': (356, 430), 'l_eye': (476, 430), 'r_ear': (266, 450), 'l_ear': (566, 450),
     'r_shoulder': (236, 730), 'l_shoulder': (596, 730), 'r_elbow': (212, 1010), 'l_elbow': (620, 1010),
     'r_wrist': (520, 985), 'l_wrist': (312, 1015)}
NAMES = ['nose','neck','r_shoulder','r_elbow','r_wrist','l_shoulder','l_elbow','l_wrist','r_hip','r_knee','r_ankle','l_hip','l_knee','l_ankle','r_eye','l_eye','r_ear','l_ear']
LIMB = [(2,3),(2,6),(3,4),(4,5),(6,7),(7,8),(2,9),(9,10),(10,11),(2,12),(12,13),(13,14),(2,1),(1,15),(15,17),(1,16),(16,18)]
COL = [(255,0,0),(255,85,0),(255,170,0),(255,255,0),(170,255,0),(85,255,0),(0,255,0),(0,255,85),(0,255,170),(0,255,255),(0,170,255),(0,85,255),(0,0,255),(85,0,255),(170,0,255),(255,0,255),(255,0,170),(255,0,85)]
sw = 4 * min(2 + max(W, H) // 1000, 7)   # @rig-c/parts stickScale: 3 at 1216 -> half width 12
im = Image.new('RGB', (W, H), (0, 0, 0)); d = ImageDraw.Draw(im)
for i, (a, b) in enumerate(LIMB):
    na, nb = NAMES[a - 1], NAMES[b - 1]
    if na not in P or nb not in P: continue
    (x1, y1), (x2, y2) = P[na], P[nb]; cx, cy = (x1 + x2) / 2, (y1 + y2) / 2; L = math.hypot(x1 - x2, y1 - y2) / 2; t = math.atan2(y1 - y2, x1 - x2)
    poly = [(cx + L * math.cos(u) * math.cos(t) - sw * math.sin(u) * math.sin(t), cy + L * math.cos(u) * math.sin(t) + sw * math.sin(u) * math.cos(t)) for u in [k * 2 * math.pi / 36 for k in range(36)]]
    d.polygon(poly, fill=tuple(int(c * 0.6) for c in COL[i]))
for i, n in enumerate(NAMES):
    if n in P: x, y = P[n]; d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=COL[i])
im.save('control_pose.png'); json.dump({'width': W, 'height': H, 'points': P}, open('control_pose.json', 'w'), indent=1)
