# usage: stance.py rig.json base_motion.json out_motion.json [--target parallel|vertical] [--hipx N] [--lift N]
import json, math, sys
rig = json.load(open(sys.argv[1])); base = json.load(open(sys.argv[2])); out = sys.argv[3]
args = sys.argv[4:]
def opt(n, d):
    return type(d)(args[args.index(n)+1]) if n in args else d
target = opt('--target', 'parallel')
B = {b['name']: b for b in rig['bones']}
def world(name):
    # world origin and world angle (degrees), y up; assumes no scale
    b = B[name]
    if 'parent' not in b: return (b.get('x',0), b.get('y',0)), b.get('rotation',0)
    (px, py), pa = world(b['parent'])
    r = math.radians(pa); x, y = b.get('x',0), b.get('y',0)
    return (px + x*math.cos(r) - y*math.sin(r), py + x*math.sin(r) + y*math.cos(r)), pa + b.get('rotation',0)
def leg(s):
    H, a0 = world(f'leg_{s}0'); K, a1 = world(f'leg_{s}1')
    L0 = B[f'leg_{s}0']['length']; L1 = B[f'leg_{s}1']['length']
    A = (K[0] + L1*math.cos(math.radians(a1)), K[1] + L1*math.sin(math.radians(a1)))
    return dict(H=H, K=K, A=A, a0=a0, a1=a1, L0=L0, L1=L1, r0=B[f'leg_{s}0']['rotation'], r1=B[f'leg_{s}1']['rotation'])
def tilt(l):  # hip->ankle angle from vertical, deg, + = ankle to image-left
    return math.degrees(math.atan2(l['H'][0]-l['A'][0], l['H'][1]-l['A'][1]))
def ik(l, A2, H2=None):
    H = H2 or l['H']; dx, dy = A2[0]-H[0], A2[1]-H[1]; d = math.hypot(dx, dy)
    L0, L1 = l['L0'], l['L1']; d = min(d, L0+L1-1e-6)
    c = (L0*L0 + d*d - L1*L1)/(2*L0*d); al = math.acos(max(-1, min(1, c)))
    # rest knee side
    v1 = (l['K'][0]-l['H'][0], l['K'][1]-l['H'][1]); v2 = (l['A'][0]-l['H'][0], l['A'][1]-l['H'][1])
    side = 1 if (v2[0]*v1[1]-v2[1]*v1[0]) > 0 else -1
    if opt('--knee', 'in') == 'out': side = -side
    base_ang = math.degrees(math.atan2(dy, dx)); th = base_ang + side*math.degrees(al)
    K2 = (H[0]+L0*math.cos(math.radians(th)), H[1]+L0*math.sin(math.radians(th)))
    sh = math.degrees(math.atan2(A2[1]-K2[1], A2[0]-K2[0]))
    return th - l['a0'], (sh - th) - l['r1'], K2
R, Lf = leg('r'), leg('l')
info = dict(r=dict(H=R['H'], K=R['K'], A=R['A'], tilt=tilt(R)), l=dict(H=Lf['H'], K=Lf['K'], A=Lf['A'], tilt=tilt(Lf)))
if target == 'parallel': tgt = tilt(Lf)
else: tgt = 0.0
Hy = R['H'][1]-R['A'][1]
ax_target = R['H'][0] - Hy*math.tan(math.radians(tgt))
info['target_tilt'] = tgt; info['ankle_dx_full'] = ax_target - R['A'][0]
hipx = opt('--hipx', 0.0)
poses = {}
mode = opt('--mode', 'ik'); footdeg = opt('--foot', 0.0)
for f in (0, 0.25, 0.5, 0.75, 1.0):
    A2 = (R['A'][0] + f*(ax_target-R['A'][0]), R['A'][1])
    H2 = (R['H'][0]+f*hipx, R['H'][1])
    if mode == 'ik': d0, d1, K2 = ik(R, A2, H2)
    else: d0, d1, K2 = f*(tilt(R)-tgt), 0.0, None
    # left leg: ankle planted under a hip shift
    HL2 = (Lf['H'][0]+f*hipx, Lf['H'][1])
    e0, e1, _ = ik(Lf, Lf['A'], HL2) if hipx else (0.0, 0.0, None)
    poses[f] = dict(leg_r0=d0, leg_r1=d1, leg_l0=e0, leg_l1=e1, foot_r=f*footdeg, hipx=f*hipx, knee=K2 or (0,0), ankle=A2)
info['poses'] = {str(k): v for k, v in poses.items()}
anims = {}
for f, p in poses.items():
    tr = [{"bone": b, "property": "rotate", "keys": [{"t": 0, "v": [round(p[b], 4)]}, {"t": 0.5, "v": [round(p[b], 4)]}]} for b in ('leg_r0','leg_r1','leg_l0','leg_l1','foot_r') if abs(p[b]) > 1e-6]
    sk = opt('--skirt', 0.0)
    if sk:
        for b, w in (('skirt_r0', 1.0), ('skirt_c0', opt('--cw', 0.5))):
            v = round(sk*w*p['leg_r0'], 4); tr.append({"bone": b, "property": "rotate", "keys": [{"t": 0, "v": [v]}, {"t": 0.5, "v": [v]}]})
    if p['hipx']:
        tr.append({"bone": "hip", "property": "translate", "keys": [{"t": 0, "v": [round(p['hipx'],3), 0]}, {"t": 0.5, "v": [round(p['hipx'],3), 0]}]})
    if not tr: tr = [{"bone": "leg_r0", "property": "rotate", "keys": [{"t": 0, "v": [0]}, {"t": 0.5, "v": [0]}]}]
    anims[opt('--prefix','s') + '%03d' % int(f*100)] = {"duration": 0.5, "loop": False, "note": f"right leg {int(f*100)}% to {target}", "tracks": tr}
# the beat: rest 0.3 s, out over 0.6 s (smoothstep), hold 0.4, back 0.6, rest 0.6 -> 2.5 s
def beat(F=1.0, dur_out=0.6, hold=0.4, lift=opt('--lift', 0.0)):
    T = [0, 0.3, 0.3+dur_out, 0.3+dur_out+hold, 0.3+2*dur_out+hold, 0.3+2*dur_out+hold+0.6]
    n = 24; tracks = {b: [] for b in ('leg_r0','leg_r1','leg_l0','leg_l1','hip')}
    total = T[-1]; steps = int(round(total*n))
    for i in range(steps+1):
        t = i/n
        if t <= T[1]: u = 0
        elif t <= T[2]: x = (t-T[1])/dur_out; u = x*x*(3-2*x)
        elif t <= T[3]: u = 1
        elif t <= T[4]: x = (t-T[3])/dur_out; u = 1 - x*x*(3-2*x)
        else: u = 0
        u *= F
        A2 = (R['A'][0] + u*(ax_target-R['A'][0]), R['A'][1] + (lift*math.sin(math.pi*min(1,max(0,(t-T[1])/dur_out))) if T[1]<t<T[2] else 0) + (lift*math.sin(math.pi*min(1,max(0,(t-T[3])/dur_out))) if T[3]<t<T[4] else 0))
        H2 = (R['H'][0]+u*hipx, R['H'][1]); d0, d1, _ = ik(R, A2, H2) if mode == 'ik' else (u*(tilt(R)-tgt), 0.0, None)
        HL2 = (Lf['H'][0]+u*hipx, Lf['H'][1]); e0, e1, _ = ik(Lf, Lf['A'], HL2) if hipx else (0.0, 0.0, None)
        tracks.setdefault('foot_r', [])
        for b, v in (('leg_r0', d0), ('leg_r1', d1), ('leg_l0', e0), ('leg_l1', e1), ('foot_r', u*footdeg)):
            tracks[b].append({"t": round(t, 5), "v": [round(v, 4)]})
        tracks['hip'].append({"t": round(t, 5), "v": [round(u*hipx, 3), 0]})
    sk = opt('--skirt', 0.0)
    if sk:
        for b, w in (('skirt_r0', 1.0), ('skirt_c0', opt('--cw', 0.5))):
            tracks[b] = [{"t": x['t'], "v": [round(sk*w*x['v'][0], 4)]} for x in tracks['leg_r0']]
    tr = [{"bone": b, "property": "rotate", "keys": k} for b, k in tracks.items() if b != 'hip' and any(abs(x['v'][0]) > 1e-6 for x in k)]
    if hipx: tr.append({"bone": "hip", "property": "translate", "keys": tracks['hip']})
    return {"duration": total, "loop": True, "note": f"stance beat to {target}", "tracks": tr}
anims[opt('--prefix','s') + 'beat'] = beat(F=opt('--amount', 1.0))
import os
if os.path.exists(out): base = json.load(open(out))
m = dict(base); m['animations'] = dict(base['animations']); m['animations'].update(anims)
json.dump(m, open(out, 'w'))
json.dump(info, open(out + '.info.json', 'w'), indent=1)
print(json.dumps({k: v for k, v in info.items() if k != 'poses'}, indent=1))
for k, v in poses.items(): print(k, {a: (round(b, 3) if isinstance(b, float) else [round(c, 1) for c in b]) for a, b in v.items()})
