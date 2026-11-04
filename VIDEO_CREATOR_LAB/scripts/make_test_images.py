"""Generate synthetic 9:16 test images (2160x3840) for motion benchmarks.

Fine grid lines and small text make sub-pixel jitter and blur easy to see.
These are technical inputs only, not approved art.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 2160, 3840
FONT = "C:/Windows/Fonts/arial.ttf"


def make(path, top, bottom, accent, label):
    column = Image.new("RGB", (1, H))
    column.putdata([tuple(int(top[i] * (1 - y / (H - 1)) + bottom[i] * y / (H - 1)) for i in range(3))
                    for y in range(H)])
    img = column.resize((W, H))
    d = ImageDraw.Draw(img)
    for x in range(0, W, 60):
        d.line([(x, 0), (x, H)], fill=(90, 90, 110), width=1 if x % 300 else 3)
    for y in range(0, H, 60):
        d.line([(0, y), (W, y)], fill=(90, 90, 110), width=1 if y % 300 else 3)
    cx, cy = W // 2, H // 2
    for r in range(80, 1100, 80):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=accent, width=4)
    d.line([(0, 0), (W, H)], fill=accent, width=3)
    d.line([(W, 0), (0, H)], fill=accent, width=3)
    big = ImageFont.truetype(FONT, 150)
    small = ImageFont.truetype(FONT, 40)
    d.text((cx, 600), label, font=big, fill=(240, 240, 240), anchor="mm")
    d.text((cx, 780), "TESTE TECNICO - NAO E ARTE APROVADA", font=small, fill=(240, 240, 240), anchor="mm")
    for i, y in enumerate(range(300, H - 200, 300)):
        d.text((80, y), f"y={y}", font=small, fill=(220, 220, 220))
        d.text((W - 80, y), f"linha {i:02}", font=small, fill=(220, 220, 220), anchor="ra")
    img.save(path)


if __name__ == "__main__":
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    make(out / "teste_A_azul.png", (20, 28, 60), (40, 20, 70), (60, 220, 210), "IMAGEM A")
    make(out / "teste_B_ambar.png", (70, 40, 25), (30, 25, 40), (240, 190, 70), "IMAGEM B")
    make(out / "teste_C_verde.png", (20, 55, 40), (25, 25, 45), (200, 120, 240), "IMAGEM C")
    print("ok")
