import sys
from PIL import Image, ImageDraw
C = sys.argv[1]; out = sys.argv[2]; rows = [r.split(',') for r in sys.argv[3].split(';')]; kind = sys.argv[4]
def load(n):
    im = Image.open(f'{C}/{kind}/{n}@2fps/f0000.png').convert('RGBA')
    bg = Image.new('RGBA', im.size, (255,255,255,255)); bg.alpha_composite(im); return bg.convert('RGB')
ims = [[load(n) for n in r] for r in rows]
w = max(sum(i.size[0] for i in r) for r in ims) + 6*max(len(r) for r in ims); h = sum(r[0].size[1]+22 for r in ims)
S = Image.new('RGB', (w, h), 'white'); d = ImageDraw.Draw(S); y = 0
for names, r in zip(rows, ims):
    x = 0
    for n, i in zip(names, r):
        d.text((x+4, y+4), n, fill='black'); S.paste(i, (x, y+20)); x += i.size[0]+6
    y += r[0].size[1]+22
S.save(out, quality=88); print(out, S.size)
