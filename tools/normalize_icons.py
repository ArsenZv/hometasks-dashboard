"""Normalise raw icons from assets/icons into static/icons.

Each icon is trimmed of transparent padding, scaled to fit (aspect kept) into
a SIZE x SIZE transparent canvas with a small margin, and centred. Re-run it
whenever you add or change icons in assets/icons.
Usage: python tools/normalize_icons.py   (needs Pillow)
"""
from pathlib import Path
from PIL import Image

SIZE = 128
MARGIN = 8
RENAME = {'water_flowerspng': 'water_flowers', 'windom_cleaning': 'window_cleaning'}
ROOT = Path(__file__).resolve().parent.parent
SRC, DST = ROOT / 'assets' / 'icons', ROOT / 'static' / 'icons'

DST.mkdir(parents=True, exist_ok=True)
for path in sorted(SRC.glob('*.png')):
    img = Image.open(path).convert('RGBA')
    bbox = img.getchannel('A').point(lambda a: 255 if a > 8 else 0).getbbox()
    if bbox:
        img = img.crop(bbox)
    box = SIZE - 2 * MARGIN
    scale = box / max(img.size)
    new = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
    img = img.resize(new, Image.LANCZOS)
    canvas = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    canvas.paste(img, ((SIZE - new[0]) // 2, (SIZE - new[1]) // 2), img)
    name = RENAME.get(path.stem, path.stem)
    canvas.save(DST / f'{name}.png')
    print(f'{path.name} {Image.open(path).size} -> {name}.png')
