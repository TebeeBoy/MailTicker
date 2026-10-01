"""A program ikonjának (assets/mailticker.ico) előállítása: boríték kék lekerekített négyzeten.

Futtatás: python3 assets/make_icon.py   (Pillow kell hozzá; az .ico a gitben van, csak módosításkor kell)
"""
import os

from PIL import Image, ImageDraw

SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]
BG = (43, 108, 176, 255)  # badge_bg
ENVELOPE = (255, 255, 255, 255)
FLAP = (255, 211, 107, 255)  # sender_fg
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mailticker.ico")


def draw(size: int) -> Image.Image:
    scale = 4  # túlmintavételezés a sima élekért
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=s * 0.2, fill=BG)
    left, right = s * 0.17, s * 0.83
    top, bottom = s * 0.28, s * 0.72
    d.rectangle([left, top, right, bottom], fill=ENVELOPE)
    line = max(scale, int(s * 0.045))
    mid = ((left + right) / 2, top + (bottom - top) * 0.58)
    d.polygon([(left, top), (right, top), mid], fill=FLAP)
    d.line([(left, top), mid, (right, top)], fill=BG, width=line)
    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    images = [draw(size) for size in SIZES]
    images[-1].save(OUT, format="ICO", sizes=[(s, s) for s in SIZES], append_images=images[:-1])
    print("Kész:", OUT)
