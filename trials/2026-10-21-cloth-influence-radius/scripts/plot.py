# Contact sheets for this trial: one per covered part, folded frames per stimulus against the influence radius,
# drawn from results/<subject>-results.json. Written for this trial after the run, from the plot script of the
# first reading (2026-10-19), with the 60-degree stimulus added and the marks moved to the cells rule's values.
# It reads the run's output; it measures nothing.
# Usage, from this trial's directory: python3 -I scripts/plot.py   (needs rsvg-convert on PATH)
import json, subprocess
st = [('wind', 'wind +1, -1, calm', '#2a7fff'), ('sway8', 'hip sway 8 deg', '#20a060'),
      ('sway30', 'hip sway 30 deg', '#e0402a'), ('sway60', 'hip sway 60 deg', '#8a3ab9')]
for subj in ['fixture', 'wind']:
    d = json.load(open(f'results/{subj}-results.json'))
    lat = [r for r in d['results'] if r['id'] == 'lattice'][0]
    for p in d['covered']:
        far = d['farthest'][p]; cell = d['cells'][p]
        pts = sorted({(r['radii'][p],) + tuple(r['folds'][s][p]['frames'] for s, _, _ in st) for r in d['results'] if r['radii']})
        W, H, L, R, T, B = 760, 420, 70, 20, 50, 60
        xmax = max(x[0] for x in pts) * 1.03
        ytop = max(10, max(max(x[1:]) for x in pts), max(lat['folds'][s][p]['frames'] for s, _, _ in st))
        ymax = ytop * 1.1
        X = lambda v: L + (v / xmax) * (W - L - R)
        Y = lambda v: H - B - (v / ymax) * (H - T - B)
        g = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="Helvetica" font-size="12"><rect width="100%" height="100%" fill="white"/>',
             f'<text x="{L}" y="22" font-size="15" font-weight="bold">{subj} / {p}: folded frames vs influence radius (render --folds, 30 fps, physics on)</text>',
             f'<text x="{L}" y="40" fill="#555">farthest vertex {far} px, cell {cell} px, max 6, across, smooth; dashed = lattice</text>']
        for i in range(6):
            yv = ytop * i / 5
            g.append(f'<line x1="{L}" x2="{W-R}" y1="{Y(yv):.1f}" y2="{Y(yv):.1f}" stroke="#eee"/><text x="{L-6}" y="{Y(yv)+4:.1f}" text-anchor="end">{yv:.0f}</text>')
        step = max(10, round(xmax / 8 / 10) * 10)
        v = 0
        while v <= xmax:
            g.append(f'<text x="{X(v):.1f}" y="{H-B+16}" text-anchor="middle">{v}</text>'); v += step
        g.append(f'<text x="{(L+W-R)/2}" y="{H-14}" text-anchor="middle">radius (px)</text>')
        g.append(f'<line x1="{L}" x2="{L}" y1="{T}" y2="{H-B}" stroke="#333"/><line x1="{L}" x2="{W-R}" y1="{H-B}" y2="{H-B}" stroke="#333"/>')
        g.append(f'<line x1="{X(far):.1f}" x2="{X(far):.1f}" y1="{T}" y2="{H-B}" stroke="#000" stroke-width="1.5"/><text x="{X(far)+3:.1f}" y="{T+12}">farthest</text>')
        for k, n in enumerate([2, 3, 4]):
            rad = far + n * cell
            if rad <= xmax:
                g.append(f'<line x1="{X(rad):.1f}" x2="{X(rad):.1f}" y1="{T}" y2="{H-B}" stroke="#999" stroke-dasharray="2,3"/><text x="{X(rad)+3:.1f}" y="{T+26+k*13}" fill="#666">+{n} cells</text>')
        for i, (s, lab, c) in enumerate(st):
            lv = lat['folds'][s][p]['frames']
            g.append(f'<line x1="{L}" x2="{W-R}" y1="{Y(lv):.1f}" y2="{Y(lv):.1f}" stroke="{c}" stroke-dasharray="6,4" opacity="0.6"/>')
            g.append(f'<polyline points="{" ".join(f"{X(x[0]):.1f},{Y(x[1+i]):.1f}" for x in pts)}" fill="none" stroke="{c}" stroke-width="2"/>')
            g += [f'<circle cx="{X(x[0]):.1f}" cy="{Y(x[1+i]):.1f}" r="2.5" fill="{c}"/>' for x in pts]
            g.append(f'<rect x="{W-R-180}" y="{T+4+i*16}" width="12" height="3" fill="{c}"/><text x="{W-R-162}" y="{T+9+i*16}">{lab} (lattice {lv})</text>')
        g.append('</svg>')
        f = f'sheets/{subj}-{p}.svg'
        open(f, 'w').write('\n'.join(g))
        subprocess.run(['rsvg-convert', '-o', f[:-4] + '.png', f], check=True)
        print(f[:-4] + '.png')
