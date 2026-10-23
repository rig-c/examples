# usage: measure.py render_dir rig.json set[,set...]
import json, sys, os
d, rigp, sets = sys.argv[1], sys.argv[2], sys.argv[3].split(',')
rig = json.load(open(rigp)); L = {b['name']: b.get('length', 0) for b in rig['bones']}
def load(s, n):
    for c in (f'{s}@4fps', f'{s}@24fps', s):
        p = os.path.join(d, c, n)
        if os.path.exists(p): return json.load(open(p))
def tip(fr, bone):
    b = next(x for x in fr['bones'] if x['name'] == bone)
    return b['worldX'] + b['a']*L[bone], b['worldY'] + b['c']*L[bone]
def lowest(fr, slot):
    a = [x for x in fr['attachments'] if x['slot'] == slot]
    if not a: return None
    v = a[0]['vertices']; return min(v[1::2])
rows = []
ref = None
for s in sets:
    seam = load(s, 'seam.json'); pt = load(s, 'pass-through.json'); fo = load(s, 'folds.json'); g = load(s, 'geometry.json')
    r = {'set': s}
    for p in seam['pairs']:
        k = f"{p['a']}|{p['b']}"
        gap = max([f['px'] for f in (p.get('gap') or {}).get('frames', [])] or [0])
        gh = max([f['px'] for f in (p.get('ghost') or {}).get('frames', [])] or [0])
        r[k] = (gap, gh) if p['status'] == 'read' or p.get('opens') is not None else p['status']
    r['pass'] = sum(len(p.get('frames', []) or []) for p in pt['pairs'])
    r['folds'] = [m['slot'] for m in fo['meshes'] if m['frames']]
    fr_all = g['frames']
    feet = {}
    for side in ('r', 'l'):
        ys = [tip(fr, f'leg_{side}1')[1] for fr in fr_all]
        xs = [tip(fr, f'leg_{side}1')[0] for fr in fr_all]
        lo = [lowest(fr, f'foot_{side}') for fr in fr_all]
        if lo[0] is None: lo = [lowest(fr, 'shoes') for fr in fr_all]
        feet[side] = (min(ys), max(ys), min(xs), max(xs), min(lo), max(lo))
    r['feet'] = feet
    rows.append(r)
json.dump(rows, open(os.path.join(d, 'measure-' + sets[0] + '.json'), 'w'), indent=1)
for r in rows:
    print(json.dumps(r))
