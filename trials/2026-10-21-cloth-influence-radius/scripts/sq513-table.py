# rig-c/parts#513 (parts#513 sweep): the sweep table and the per-rule decision from <workdir>/{fixture,wind}-results.json.
# Usage: python3 -I sq513-table.py <workdir> > sweep.md ; also writes <out>/sweep.csv when a second argument names <out>.
import json, sys, csv
W = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else None
STIM = ['wind', 'sway60', 'sway30', 'sway8']
subj = {s: json.load(open(f'{W}/{s}-results.json')) for s in ['fixture', 'wind']}
parts = [(s, p) for s in subj for p in subj[s]['covered']]
print('## Covered parts\n')
print('| part | farthest px | cell | drafted radius (+3 cells) | lattice folds wind / 60° / 30° / 8° |')
print('| --- | ---: | ---: | ---: | --- |')
lat = {}
for s, d in subj.items():
    L = next(r for r in d['results'] if r['id'] == 'lattice')
    for p in d['covered']:
        lat[(s, p)] = {k: L['folds'][k][p]['frames'] for k in STIM}
        print(f"| {s}/{p} | {d['farthest'][p]} | {d['cells'][p]} | {d['drafted_radii'][p]} | {' / '.join(str(lat[(s,p)][k]) for k in STIM)} |")
print('\n## Sweep: folded frames per stimulus (wind / sway 60° / 30° / 8°), physics on, render --folds at 30 fps; check = rig-parts check on the rig as written, under the wind schedule\n')
hdr = ['rule', 'value'] + [f'{s}/{p}' for s, p in parts] + ['check (fixture, wind)']
print('| ' + ' | '.join(hdr) + ' |')
print('| ' + ' | '.join(['---'] * len(hdr)) + ' |')
rows_csv = []
ids = [r['id'] for r in subj['fixture']['results']]
verdict = {}
for vid in ids:
    cells = []
    R = {s: next(r for r in subj[s]['results'] if r['id'] == vid) for s in subj}
    rule, value = R['fixture']['rule'], R['fixture']['value']
    chk = []
    for s, p in parts:
        r = R[s]
        if 'error' in r:
            cells.append('ERR'); continue
        f = {k: r['folds'][k][p]['frames'] for k in STIM}
        rad = '' if r['radii'] is None else f"r {r['radii'][p]}: "
        cells.append(rad + ' / '.join(str(f[k]) for k in STIM))
        rows_csv.append({'rule': rule, 'value': value, 'part': f'{s}/{p}', 'radius': None if r['radii'] is None else r['radii'][p], **{k: f[k] for k in STIM}, 'check_exit': r['check']['exit'], 'check_fails': ' '.join(r['check']['fails'])})
        verdict.setdefault(vid, []).append((s, p, f))
    for s in subj:
        r = R[s]
        chk.append('ERR' if 'error' in r else ('PASS' if r['check']['exit'] == 0 else 'FAIL ' + ','.join(r['check']['fails'])))
    print(f"| {rule} | {'' if value is None else value} | " + ' | '.join(cells) + f" | {', '.join(chk)} |")
print('\n## Per rule value: does it hold on every part?\n')
print('| rule | value | 0 folds, wind + 8° + 30° (the first reading\'s stimuli) | 0 folds, wind + 60° (#378 IF04\'s) | no more than the lattice, all four | checks green | parts breaking the 30° set |')
print('| --- | --- | --- | --- | --- | --- | --- |')
for vid in ids:
    if vid == 'lattice': continue
    v = verdict.get(vid, [])
    R = {s: next(r for r in subj[s]['results'] if r['id'] == vid) for s in subj}
    a = all(f['wind'] == 0 and f['sway8'] == 0 and f['sway30'] == 0 for _, _, f in v) and len(v) == len(parts)
    b = all(f['wind'] == 0 and f['sway60'] == 0 for _, _, f in v) and len(v) == len(parts)
    c = all(all(f[k] <= lat[(s, p)][k] for k in STIM) for s, p, f in v) and len(v) == len(parts)
    g = all('error' not in R[s] and R[s]['check']['exit'] == 0 for s in subj)
    br = [f"{s}/{p} {f['sway8']}/{f['sway30']}" for s, p, f in v if f['wind'] or f['sway8'] or f['sway30']]
    rule, value = R['fixture']['rule'], R['fixture']['value']
    print(f"| {rule} | {value} | {'yes' if a else 'no'} | {'yes' if b else 'no'} | {'yes' if c else 'no'} | {'yes' if g else 'no'} | {'; '.join(br) or '—'} |")
if OUT:
    with open(f'{OUT}/sweep.csv', 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows_csv[0].keys())); w.writeheader(); w.writerows(rows_csv)
