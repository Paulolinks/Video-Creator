"""Video cover (thumbnail) at the video's size: background, the interviewee at the bottom, the title huge in yellow on
the top half."""
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT = r"D:\Video-Creator\VIDEO_CREATOR_LAB\inputs\fonts\Poppins-ExtraBold.ttf"
W, H = 1080, 1920
YELLOW, BLACK = (255, 212, 0), (0, 0, 0)
TITLE_TOP, TITLE_H, TITLE_W = 70, 760, 980
PORTRAIT_H = 1000


def _cover_crop(img):
    s = max(W / img.width, H / img.height)
    img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    x, y = (img.width - W) // 2, (img.height - H) // 2
    return img.crop((x, y, x + W, y + H))


def _background(path):
    """First seconds of a background video, or an image."""
    path = Path(path)
    if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
        return _cover_crop(Image.open(path).convert("RGB"))
    with tempfile.TemporaryDirectory() as tmp:
        frame = Path(tmp) / "f.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "2", "-i", str(path), "-frames:v", "1", str(frame)],
                       check=True)
        return _cover_crop(Image.open(frame).convert("RGB"))


def _wrap(words, font, draw):
    lines, cur = [], ""
    for w in words:
        t = f"{cur} {w}".strip()
        if draw.textlength(t, font=font) <= TITLE_W or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    return lines + [cur]


def _fit(title, draw):
    """Largest font size whose wrapped title fits the top half."""
    words = title.upper().split()
    for size in range(260, 60, -4):
        font = ImageFont.truetype(FONT, size)
        lines = _wrap(words, font, draw)
        lh = size * 1.1
        if all(draw.textlength(l, font=font) <= TITLE_W for l in lines) and lh * len(lines) <= TITLE_H:
            break
    return font, lines, lh


def make(title, out, background, portrait=None, name=None):
    img = _background(background)
    shade = Image.new("L", (W, H))  # darken the top so the title pops
    sd = ImageDraw.Draw(shade)
    for y in range(H):
        sd.line([(0, y), (W, y)], fill=int(170 * max(0.0, 1 - y / (H * 0.62))) + 40)
    img = Image.composite(Image.new("RGB", (W, H), BLACK), img, shade)

    if portrait:
        ch = Image.open(portrait).convert("RGBA")
        s = min(W / ch.width, PORTRAIT_H / ch.height)
        ch = ch.resize((round(ch.width * s), round(ch.height * s)), Image.LANCZOS)
        img.paste(ch, ((W - ch.width) // 2, H - ch.height), ch)

    draw = ImageDraw.Draw(img)
    font, lines, lh = _fit(title, draw)
    y0 = TITLE_TOP + (TITLE_H - lh * len(lines)) / 2
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    for i, line in enumerate(lines):
        sd.text((W / 2 + 8, y0 + i * lh + 10), line, font=font, fill=(0, 0, 0, 200), anchor="ma")
    shadow = shadow.filter(ImageFilter.GaussianBlur(6))
    img.paste(shadow, (0, 0), shadow)
    for i, line in enumerate(lines):
        draw.text((W / 2, y0 + i * lh), line, font=font, fill=YELLOW, anchor="ma",
                  stroke_width=max(6, font.size // 16), stroke_fill=BLACK)

    if name:
        tag = ImageFont.truetype(FONT, 46)
        tw = draw.textlength(name.upper(), font=tag)
        ty = TITLE_TOP + TITLE_H + 4
        draw.rounded_rectangle([(W - tw) / 2 - 30, ty, (W + tw) / 2 + 30, ty + 76], 38, fill=YELLOW)
        draw.text((W / 2, ty + 40), name.upper(), font=tag, fill=BLACK, anchor="mm")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return str(out)


def stamp(video, cover, encoder=("libx264", "medium", 18), seconds=1.0):
    """Show the cover over the video's first second (same length; the audio is copied untouched)."""
    video = Path(video)
    codec, preset, crf = encoder
    tmp = video.with_name(video.stem + "_capa.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-loop", "1", "-t", str(seconds), "-i", str(cover),
                    "-filter_complex", f"[1:v]scale={W}:{H}[c];[0:v][c]overlay=eof_action=pass:enable='lt(t,{seconds})'[out]",
                    "-map", "[out]", "-map", "0:a?", "-c:v", codec, "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p",
                    "-c:a", "copy", "-map_metadata", "0", "-movflags", "+faststart", str(tmp)], check=True)
    tmp.replace(video)
    return str(video)
