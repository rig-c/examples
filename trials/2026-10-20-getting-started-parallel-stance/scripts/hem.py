# usage: hem.py geometry_beat.json geometry_ref.json [slot]
# largest move of a slot's vertices between two renders of the same length, frame by frame,
# less the hip bone's own world translation in that frame
import json, sys, math
a = json.load(open(sys.argv[1]))['frames']; b = json.load(open(sys.argv[2]))['frames']
slot = sys.argv[3] if len(sys.argv) > 3 else 'bottomwear'
def verts(fr):
    x = [t for t in fr['attachments'] if t['slot'] == slot][0]['vertices']; return list(zip(x[0::2], x[1::2]))
def hip(fr):
    h = next(t for t in fr['bones'] if t['name'] == 'hip'); return h['worldX'], h['worldY']
best = (0, None, None); raw = 0
for i, (fa, fb) in enumerate(zip(a, b)):
    (hx, hy), (gx, gy) = hip(fa), hip(fb); dx, dy = hx - gx, hy - gy
    for j, ((x1, y1), (x2, y2)) in enumerate(zip(verts(fa), verts(fb))):
        raw = max(raw, math.hypot(x1 - x2, y1 - y2))
        m = math.hypot(x1 - x2 - dx, y1 - y2 - dy)
        if m > best[0]: best = (m, i, j)
print(json.dumps({'frames': min(len(a), len(b)), 'largest_less_hip_px': round(best[0], 2), 'frame': best[1], 't_s': round(best[1] / 24, 3) if best[1] is not None else None, 'vertex': best[2], 'largest_raw_px': round(raw, 2)}))
