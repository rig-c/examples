"""Compose the six actual-browser public-rig screenshots; no reference pixels.

Capture play.html's six named controls using a 1128 x 831 browser viewport,
save each full-page JPEG as browser-frame<N>.jpg, then run this script.
Framing and crop are display choices, not measured acceptance thresholds.
"""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw

parser = argparse.ArgumentParser()
parser.add_argument('--captures', required=True)
parser.add_argument('--out', default='contact-sheet.jpg')
args = parser.parse_args()
frames = [0, 246, 491, 37, 278, 480]
labels = ['Start', 'Midpoint', 'End', 'Right support', 'Left support', 'Right support']
sheet = Image.new('RGB', (936, 862), '#eef0f4')
draw = ImageDraw.Draw(sheet)
draw.text((12, 8), 'Toca Toca / public wind rig / @rig-c/play 1.16.0', fill='#18202e')
draw.text((12, 25), 'Compiled SHA-256 0d4de3e2d76aef275091c75d5286acf34b8ce7c71ab3964d1b24ce8810a88ffb', fill='#18202e')
for index, (frame, label) in enumerate(zip(frames, labels)):
    image = Image.open(Path(args.captures) / f'browser-frame{frame}.jpg')
    if image.size != (1128, 831):
        raise SystemExit(f'Unexpected screenshot dimensions: {image.size}')
    # The complete fixed stage: both feet retained, same crop in every cell.
    image = image.crop((16, 170, 518, 792)).resize((300, 372), Image.Resampling.LANCZOS)
    x, y = 12 + (index % 3) * 312, 65 + (index // 3) * 400
    draw.text((x, y - 16), f'{label}: frame {frame}, t={frame / 30:.5f} s', fill='#18202e')
    sheet.paste(image, (x, y))
sheet.save(args.out, quality=88, optimize=True)
if Path(args.out).stat().st_size >= 1_000_000:
    raise SystemExit('Contact sheet exceeds 1 MB')
