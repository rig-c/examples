# Worst gap and ghost per pair, and pass-through frame counts, from a `rigc render --seam/--pass-through` output directory.
# Usage: python3 seam_summary.py <render dir> [<render dir> ...]  -> JSON on stdout, keyed by set directory name.
import glob, json, os, sys
out = {}
for d in sys.argv[1:]:
    for sd in sorted(glob.glob(os.path.join(d, '*', ''))):
        rec = {}
        f = os.path.join(sd, 'seam.json')
        if os.path.exists(f):
            for p in json.load(open(f))['pairs']:
                key = p['a'] + '|' + p['b']
                if p['status'] != 'read':
                    rec[key] = 'SKIP'; continue
                rec[key] = {"gap": max([x['px'] for x in p['gap']['frames']] or [0]),
                            "ghost": max([x['px'] for x in p['ghost']['frames']] or [0])}
        f = os.path.join(sd, 'pass-through.json')
        if os.path.exists(f):
            for p in json.load(open(f)).get('pairs', []):
                rec['pass-through ' + p['cloth'] + '>' + p['leg']] = len(p.get('frames', []))
        if rec: out[os.path.basename(os.path.normpath(sd))] = rec
print(json.dumps(out, indent=1))
