"""Remove the background of a character image (rembg, runs locally on the CPU).

Usage: remover_fundo.py <input> <output.png> [model=birefnet-portrait]
Run with the rembg venv (.venvs/rembg). The output keeps only the person, cropped to it.
"""
import sys

from PIL import Image
from rembg import new_session, remove

if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    model = sys.argv[3] if len(sys.argv) > 3 else "birefnet-portrait"
    img = Image.open(src).convert("RGB")
    out = remove(img, session=new_session(model), post_process_mask=True)
    box = out.getchannel("A").point(lambda a: 255 if a > 16 else 0).getbbox()
    if box:  # crop to the person with a small margin, keeping the bottom edge (cut at the chest) where it was
        m = round(0.02 * max(out.size))
        out = out.crop((max(0, box[0] - m), max(0, box[1] - m), min(out.width, box[2] + m), out.height))
    out.save(dst)
    print(f"{out.width}x{out.height}")
