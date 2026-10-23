"""Compose actual-browser public-rig screenshots: standard six plus count-ranked three.
Capture the controls in play.html. Save browser-frame<N>.png for the six
standard controls and browser-fold-frame<N>.png for the three fold controls.
Crop/framing are display choices, not acceptance metrics. Requires Pillow.
"""
import argparse,json
from pathlib import Path
from PIL import Image, ImageDraw
parser=argparse.ArgumentParser()
parser.add_argument('--captures',required=True)
parser.add_argument('--out',default='contact-sheet.jpg')
args=parser.parse_args()
selection=json.loads(Path('fold-selection.json').read_text())
folds=json.loads(Path('fold-diagnostic/folds.json').read_text())
mesh=next(m for m in folds['meshes'] if m['slot']=='shins' and m['attachment']=='shins')
ranked=sorted(mesh['frames'],key=lambda f:(-len(f['triangles']),f['index']))[:3]
assert [(f['index'],len(f['triangles'])) for f in ranked]==[(f['frame'],f['foldedTriangles']) for f in selection['selected']]
frames=[0,156,312,30,227,299]
labels=['Start','Midpoint','End','Left support','Right support','Left support']
items=[(f'browser-frame{f}.png',f'{label}: frame {f}, t={f/24:.5f} s') for f,label in zip(frames,labels)]
items += [(f"browser-fold-frame{f['frame']}.png",f['label']+f" / t={f['timeSeconds']:.5f}s") for f in selection['selected']]
sheet=Image.new('RGB',(936,1262),'#eef0f4');draw=ImageDraw.Draw(sheet)
draw.text((12,8),'Zero Two / accepted dancer rig / @rig-c/play 1.16.0',fill='#18202e')
draw.text((12,25),'Compiled SHA-256 21999456afd779a7c67e2c12a6de95ff4234f037981db8a0a0c2ee5a4d1f24cd',fill='#18202e')
for i,(name,label) in enumerate(items):
 image=Image.open(Path(args.captures)/name)
 if image.width<468 or image.height<672:raise SystemExit(f'Unexpected screenshot dimensions: {image.size}')
 image=image.crop((16,170,468,672)).resize((300,372),Image.Resampling.LANCZOS)
 x,y=12+(i%3)*312,65+(i//3)*400
 draw.text((x,y-16),label,fill='#18202e');sheet.paste(image,(x,y))
sheet.save(args.out,quality=88,optimize=True)
if Path(args.out).stat().st_size>=1_000_000:raise SystemExit('Contact sheet exceeds 1 MB')
