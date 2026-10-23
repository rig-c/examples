# Per-track extremes of a rigc-motion/1 animation: the angle table a trial publishes in place of the motion file.
import json, sys
doc = json.load(open(sys.argv[1])); name = sys.argv[2]
a = doc['animations'][name]
rows = []
for tr in a['tracks']:
    target = tr.get('bone') or tr.get('group')
    keys = tr['keys']; dims = len(keys[0]['v'])
    for d in range(dims):
        vs = [(k['v'][d], k['t']) for k in keys]
        lo = min(vs, key=lambda x: (x[0], x[1])); hi = max(vs, key=lambda x: (x[0], -x[1]))
        prop = tr['property'] + (['x', 'y'][d] if dims == 2 else '')
        rows.append({"target": target, "kind": "group" if 'group' in tr else "bone", "property": prop,
                     "start": keys[0]["v"][d] + 0.0, "end": keys[-1]["v"][d] + 0.0,
                     "min": lo[0] + 0.0, "min_at_s": round(lo[1], 4), "max": hi[0] + 0.0, "max_at_s": round(hi[1], 4),
                     "keys": len(keys)})
print(json.dumps({"animation": name, "duration_s": a['duration'], "loop": a.get('loop', False),
                  "sampled_fps": round((len(a['tracks'][0]['keys']) - 1) / a['duration']),
                  "units": "rotate in degrees, counter-clockwise positive; translate in rig px, y up; scale as a factor",
                  "tracks": rows}, indent=1))
