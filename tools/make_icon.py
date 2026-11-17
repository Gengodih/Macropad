"""Draws the app icon (a little purple macro pad) as icon.png and icon.ico.

    python tools/make_icon.py <out dir>
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


def draw(size=256):
    s = size / 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([14 * s, 22 * s, 242 * s, 246 * s], 46 * s, fill=(0, 0, 0, 120))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(8 * s)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([12 * s, 12 * s, 244 * s, 236 * s], 44 * s, fill=(124, 58, 237, 255))
    d.rounded_rectangle([12 * s, 12 * s, 244 * s, 120 * s], 44 * s, fill=(139, 92, 246, 255))
    d.rectangle([12 * s, 80 * s, 244 * s, 124 * s], fill=(132, 76, 241, 255))
    # 3 x 3 keys, the bottom right one glowing like the light key
    for r in range(3):
        for c in range(3):
            x, y = 40 * s + c * 62 * s, 40 * s + r * 60 * s
            glow = (r, c) == (2, 2)
            d.rounded_rectangle([x, y + 6 * s, x + 50 * s, y + 52 * s], 12 * s, fill=(46, 16, 101, 255))
            d.rounded_rectangle([x, y, x + 50 * s, y + 44 * s], 12 * s,
                                fill=(253, 224, 71, 255) if glow else (245, 243, 255, 255))
    return img


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    big = draw(256)
    big.save(out / "icon.png")
    big.save(out / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("icon written to", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "app/macropad_app/resources")
