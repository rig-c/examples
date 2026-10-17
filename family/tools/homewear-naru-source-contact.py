#!/usr/bin/env python3
"""Compare source panels at the same canvas scale; no source pixel retouch."""
import pathlib
from PIL import Image, ImageDraw

family = pathlib.Path(__file__).resolve().parents[1]
home = family / "outfits/homewear/naru"
panels = [
    (family / "naru/inputs/painting.png", "Accepted office painting"),
    (home / "inputs/registration-draft.png", "Homewear crop - provisional registration"),
]
result = Image.new("RGB", (840, 1240), "#eeeeee")
draw = ImageDraw.Draw(result)
for i, (path, label) in enumerate(panels):
    image = Image.open(path).convert("RGB").resize((400, 1142), Image.Resampling.LANCZOS)
    left = 10 + i * 420
    result.paste(image, (left, 45))
    draw.text((left, 12), label, fill="black")
    for name, x, y in [("head",380,575),("neck",380,645),("chest",380,780),("hip",380,960)]:
        px, py = left + x / 2, 45 + y / 2
        draw.line((px - 8, py, px + 8, py), fill="#00ffff", width=1)
        draw.line((px, py - 8, px, py + 8), fill="#00ffff", width=1)
        draw.text((px + 10, py - 5), name, fill="#00aaaa")
draw.text((10,1202), "Cyan crosses: accepted authoring anchors, not measured source anatomical landmarks.", fill="black")
draw.text((10,1220), "No garment segmentation, face substitution, inpainting, or runtime acceptance claimed by this image.", fill="black")
(home / "docs").mkdir(exist_ok=True)
result.save(home / "docs/source-registration-draft.png")
print(home / "docs/source-registration-draft.png")
