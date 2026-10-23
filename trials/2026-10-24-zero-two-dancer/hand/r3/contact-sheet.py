"""Caption-only public sheet layout from existing rig frames; no poser/render."""
import argparse
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
p=argparse.ArgumentParser();p.add_argument('--frames',default='hand/r3/work/final-render/zero-two-r3-hand@30fps');p.add_argument('--out',default='hand/r3/contact-sheet.jpg');a=p.parse_args();source=Path(a.frames);sheet=Image.new('RGB',(1020,1320),'#e8e8e8');d=ImageDraw.Draw(sheet);font=ImageFont.load_default(size=13)
for i,f in enumerate([0,15,30,120,170,220,338,374,390]):
 im=Image.open(source/f'f{f:04d}.png').convert('RGB');im.thumbnail((308,394),Image.Resampling.NEAREST);x=(i%3)*340+16+(308-im.width)//2;y=(i//3)*440+8;sheet.paste(im,(x,y));label=f'Frame {f} | {f/30:.4f} s';assert d.textbbox((0,0),label,font=font)[2]<=308;d.text(((i%3)*340+16,(i//3)*440+410),label,fill='#18202e',font=font)
sheet.save(a.out,quality=86)
