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
frames=[0,246,491,37,278,480]
labels=['Start','Midpoint','End','Right support','Left support','Right support']
items=[(f'browser-frame{f}.png',f'{label}: frame {f}, t={f/30:.5f} s') for f,label in zip(frames,labels)]
items += [(f"browser-fold-frame{f['frame']}.png",f['label']+f" / t={f['timeSeconds']:.5f}s") for f in selection['selected']]
sheet=Image.new('RGB',(936,1262),'#eef0f4');draw=ImageDraw.Draw(sheet)
draw.text((12,8),'Toca Toca / accepted dancer rig / @rig-c/play 1.16.0',fill='#18202e')
draw.text((12,25),'Compiled SHA-256 cc8205444b76ae2c312d4a15f41bd44b56b1c3f7d0f56dd4e3fa28268e921577',fill='#18202e')
for i,(name,label) in enumerate(items):
 image=Image.open(Path(args.captures)/name)
 if image.width<468 or image.height<672:raise SystemExit(f'Unexpected screenshot dimensions: {image.size}')
 image=image.crop((16,170,468,672)).resize((300,372),Image.Resampling.LANCZOS)
 x,y=12+(i%3)*312,65+(i//3)*400
 draw.text((x,y-16),label,fill='#18202e');sheet.paste(image,(x,y))
sheet.save(args.out,quality=88,optimize=True)
if Path(args.out).stat().st_size>=1_000_000:raise SystemExit('Contact sheet exceeds 1 MB')
