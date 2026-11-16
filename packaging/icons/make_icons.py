"""Generate deterministic CREST icons for the Windows installer and app.

Run: python packaging/icons/make_icons.py
Requires Pillow (already present in the dev environment).
"""
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
OUT = HERE.parent.parent / "src-tauri" / "icons"
OUT.mkdir(parents=True, exist_ok=True)


def make(size: int) -> Image.Image:
    scale = 4
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = int(s * 0.06)
    d.rounded_rectangle(
        [pad, pad, s - pad, s - pad],
        radius=int(s * 0.22),
        fill=(15, 118, 110, 255),  # teal, matches web theme
    )
    # A crisp stylised "C" mark, drawn as an arc.
    bbox = [int(s * 0.27), int(s * 0.24), int(s * 0.73), int(s * 0.76)]
    d.arc(bbox, start=45, end=315, fill=(255, 255, 255, 255), width=max(2, int(s * 0.075)))
    # Two small "outcome" ticks inside the C.
    d.line(
        [(int(s * 0.50), int(s * 0.37)), (int(s * 0.60), int(s * 0.50)), (int(s * 0.50), int(s * 0.63))],
        fill=(255, 255, 255, 255),
        width=max(2, int(s * 0.045)),
        joint="curve",
    )
    return img.resize((size, size), Image.Resampling.LANCZOS)


sizes = [16, 32, 48, 64, 128, 256]
images = {n: make(n) for n in sizes}

# Multi-resolution ICO for the executable and NSIS installer.
images[256].save(OUT / "icon.ico", format="ICO", sizes=[(n, n) for n in sizes])
for n in (32, 128, 256):
    images[n].save(OUT / f"{n}x{n}.png")

print("Wrote icons to", OUT)
