"""Crop the transparent border off a PNG (so it can sit flush in the layout).
Usage: python tools/trim_image.py assets/baking_potatoes.png static/img/baking_potatoes.png
"""
import sys
from PIL import Image

src, dst = sys.argv[1], sys.argv[2]
img = Image.open(src).convert('RGBA')
bbox = img.getchannel('A').point(lambda a: 255 if a > 8 else 0).getbbox()
img.crop(bbox).save(dst)
print(f'{src} {img.size} -> {dst} {img.crop(bbox).size}')
