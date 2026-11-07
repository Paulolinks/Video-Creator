"""Video cover (thumbnail) at the video's size.

Vertical (9:16): background, the interviewee at the bottom, the title huge on the top half
(yellow by default; the colour and font come from data/capa.json, one colour or a sequence).
Horizontal (16:9, YouTube): title on the left, the interviewee on the right (or the title centred when there is no
portrait, as in Personagem falando).
"""
import json
import re
import subprocess
import tempfile
import threading
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT = r"D:\Video-Creator\VIDEO_CREATOR_LAB\inputs\fonts\Poppins-ExtraBold.ttf"
VERTICAL = (1080, 1920)
YELLOW, BLACK = (255, 212, 0), (0, 0, 0)

# Title colour and font, set on the home page. modo "unica": always the first colour; "sequencia": each new cover
# takes the next colour of the list (yellow, green, white... and around again). "proxima" is where the turn is.
CONFIG = Path(__file__).resolve().parent.parent / "data" / "capa.json"
CORES_SUGERIDAS = [
    {"nome": "Amarelo", "cor": "#FFD400"}, {"nome": "Verde", "cor": "#39FF14"}, {"nome": "Branco", "cor": "#FFFFFF"},
    {"nome": "Vermelho", "cor": "#FF2A2A"}, {"nome": "Azul neon", "cor": "#00E5FF"}, {"nome": "Laranja", "cor": "#FF8A00"},
    {"nome": "Rosa", "cor": "#FF3FD2"}, {"nome": "Roxo", "cor": "#A64DFF"},
]
PADRAO = {"fonte": "poppins_extra", "modo": "sequencia", "cores": [c["cor"] for c in CORES_SUGERIDAS[:5]], "proxima": 0}
_lock = threading.Lock()


def _hex(value):
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", str(value or "").strip())
    return f"#{m.group(1).upper()}" if m else None


def _rgb(hex_colour):
    h = _hex(hex_colour) or "#FFD400"
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def config():
    try:
        saved = json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = {}
    c = {**PADRAO, **{k: v for k, v in saved.items() if k in PADRAO}}
    c["cores"] = [h for h in map(_hex, c["cores"] or []) if h] or list(PADRAO["cores"])
    c["modo"] = c["modo"] if c["modo"] in ("unica", "sequencia") else "sequencia"
    c["proxima"] = int(c.get("proxima") or 0) % len(c["cores"])
    return c


def save_config(new):
    """Keeps the turn unless the list changed size (then the turn restarts at the first colour)."""
    with _lock:
        old = config()
        c = {**old, **{k: v for k, v in (new or {}).items() if k in PADRAO}}
        cores = [h for h in map(_hex, c.get("cores") or []) if h][:12]
        if not cores:
            raise ValueError("Escolha pelo menos uma cor para o título da capa.")
        c["cores"] = cores
        if "proxima" not in (new or {}) and len(cores) != len(old["cores"]):
            c["proxima"] = 0
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CONFIG.write_text(json.dumps(c, indent=2, ensure_ascii=False), encoding="utf-8")
    return config()


def next_style():
    """Colour and font for the next cover; in sequence mode the turn moves on."""
    with _lock:
        c = config()
        if c["modo"] == "unica":
            cor = c["cores"][0]
        else:
            cor = c["cores"][c["proxima"]]
            c["proxima"] = (c["proxima"] + 1) % len(c["cores"])
            CONFIG.parent.mkdir(parents=True, exist_ok=True)
            CONFIG.write_text(json.dumps(c, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"cor": cor, "fonte": c["fonte"]}


def _title_font(fid):
    from . import estilos  # the same font list as the captions
    path = estilos.font_file(fid) if fid else None
    return str(path or FONT)


def _layout(W, H, portrait, serie=False):
    """Title box (left, top, width, height), portrait max height and where it sits, and how the shade runs.
    serie=True (cover model 2): the title box starts lower and the title is a bit smaller, to make room for the
    series name and the episode tag above it."""
    if H >= W:  # the approved vertical cover (numbers for 1080x1920, scaled)
        k = W / 1080
        if serie:
            return {"box": (50 * k, 250 * k, 980 * k, 580 * k), "portrait_h": 1000 * k, "portrait_x": "centro",
                    "shade": "topo", "max_font": 210, "serie_y": 62 * k}
        return {"box": (50 * k, 70 * k, 980 * k, 760 * k), "portrait_h": 1000 * k, "portrait_x": "centro",
                "shade": "topo", "max_font": 260}
    if portrait:
        if serie:
            return {"box": (70, 215, W * 0.55, H - 385), "portrait_h": H * 0.95, "portrait_x": "direita",
                    "shade": "esquerda", "max_font": 170, "serie_y": 50}
        return {"box": (70, 90, W * 0.55, H - 260), "portrait_h": H * 0.95, "portrait_x": "direita",
                "shade": "esquerda", "max_font": 200}
    if serie:
        return {"box": (W * 0.08, 225, W * 0.84, H * 0.55), "portrait_h": 0, "portrait_x": None,
                "shade": "topo", "max_font": 170, "serie_y": 55}
    return {"box": (W * 0.08, H * 0.12, W * 0.84, H * 0.62), "portrait_h": 0, "portrait_x": None,
            "shade": "topo", "max_font": 200}


def _serie_band(img, draw, cx, top, width, serie, episodio, accent=YELLOW):
    """Series name in white capitals, and under it the episode tag (black pill, border and text in the title colour)."""
    name = serie.upper()
    for size in range(56, 22, -2):  # largest size that fits the column
        font = ImageFont.truetype(FONT, size)
        if draw.textlength(name, font=font) <= width:
            break
    draw.text((cx, top), name, font=font, fill=(255, 255, 255), anchor="ma",
              stroke_width=max(3, size // 12), stroke_fill=BLACK)
    if not episodio:
        return
    tag = ImageFont.truetype(FONT, 40)
    tw = draw.textlength(episodio, font=tag)
    ty = top + size * 1.25 + 14
    draw.rounded_rectangle([cx - tw / 2 - 28, ty, cx + tw / 2 + 28, ty + 66], 33, fill=BLACK, outline=accent, width=4)
    draw.text((cx, ty + 34), episodio, font=tag, fill=accent, anchor="mm")


def _cover_crop(img, W, H):
    s = max(W / img.width, H / img.height)
    img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    x, y = (img.width - W) // 2, (img.height - H) // 2
    return img.crop((x, y, x + W, y + H))


def _background(path, W, H):
    """First seconds of a background video, or an image."""
    path = Path(path)
    if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
        return _cover_crop(Image.open(path).convert("RGB"), W, H)
    with tempfile.TemporaryDirectory() as tmp:
        frame = Path(tmp) / "f.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "2", "-i", str(path), "-frames:v", "1", str(frame)],
                       check=True)
        return _cover_crop(Image.open(frame).convert("RGB"), W, H)


def _wrap(words, font, draw, max_w):
    lines, cur = [], ""
    for w in words:
        t = f"{cur} {w}".strip()
        if draw.textlength(t, font=font) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    return lines + [cur]


def _fit(title, draw, box_w, box_h, max_font, font_path=FONT):
    """Largest font size whose wrapped title fits the box."""
    words = title.upper().split()
    for size in range(max_font, 40, -4):
        font = ImageFont.truetype(font_path, size)
        lines = _wrap(words, font, draw, box_w)
        lh = size * 1.1
        if all(draw.textlength(l, font=font) <= box_w for l in lines) and lh * len(lines) <= box_h:
            break
    return font, lines, lh


def _shade(W, H, direction):
    """Darken the side where the title goes so it pops."""
    shade = Image.new("L", (W, H))
    sd = ImageDraw.Draw(shade)
    if direction == "esquerda":
        for x in range(W):
            sd.line([(x, 0), (x, H)], fill=int(190 * max(0.0, 1 - x / (W * 0.75))) + 40)
    else:
        for y in range(H):
            sd.line([(0, y), (W, y)], fill=int(170 * max(0.0, 1 - y / (H * 0.62))) + 40)
    return shade


def make(title, out, background, portrait=None, name=None, size=VERTICAL, serie=None, episodio=None,
         cor=None, fonte=None):
    """serie + episodio (e.g. 'EPISÓDIO 1 DE 9') filled = cover model 2 (series); otherwise model 1.
    cor (#RRGGBB) and fonte (font id) style the title; the name tag and the episode tag follow the same colour."""
    W, H = size
    accent = _rgb(cor) if cor else YELLOW
    em_serie = bool(serie and episodio)
    lay = _layout(W, H, portrait, em_serie)
    img = _background(background, W, H)
    img = Image.composite(Image.new("RGB", (W, H), BLACK), img, _shade(W, H, lay["shade"]))

    if portrait and lay["portrait_x"]:
        ch = Image.open(portrait).convert("RGBA")
        max_w = W if lay["portrait_x"] == "centro" else W * 0.48
        s = min(max_w / ch.width, lay["portrait_h"] / ch.height)
        ch = ch.resize((round(ch.width * s), round(ch.height * s)), Image.LANCZOS)
        x = (W - ch.width) // 2 if lay["portrait_x"] == "centro" else W - ch.width - round(W * 0.03)
        img.paste(ch, (x, H - ch.height), ch)

    bx, by, bw, bh = lay["box"]
    cx = bx + bw / 2
    draw = ImageDraw.Draw(img)
    font, lines, lh = _fit(title, draw, bw, bh, lay["max_font"], _title_font(fonte))
    y0 = by + (bh - lh * len(lines)) / 2
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    for i, line in enumerate(lines):
        sd.text((cx + 8, y0 + i * lh + 10), line, font=font, fill=(0, 0, 0, 200), anchor="ma")
    shadow = shadow.filter(ImageFilter.GaussianBlur(6))
    img.paste(shadow, (0, 0), shadow)
    for i, line in enumerate(lines):
        draw.text((cx, y0 + i * lh), line, font=font, fill=accent, anchor="ma",
                  stroke_width=max(6, font.size // 16), stroke_fill=BLACK)

    if em_serie:
        _serie_band(img, draw, cx, lay["serie_y"], bw, serie, episodio, accent)

    if name:
        tag = ImageFont.truetype(FONT, 46)
        tw = draw.textlength(name.upper(), font=tag)
        ty = by + bh + 4
        draw.rounded_rectangle([cx - tw / 2 - 30, ty, cx + tw / 2 + 30, ty + 76], 38, fill=accent)
        draw.text((cx, ty + 40), name.upper(), font=tag, fill=BLACK, anchor="mm")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return str(out)


def stamp(video, cover, encoder=("libx264", "medium", 18), seconds=1.0, size=VERTICAL):
    """Show the cover over the video's first second (same length; the audio is copied untouched)."""
    video = Path(video)
    codec, preset, crf = encoder
    W, H = size
    tmp = video.with_name(video.stem + "_capa.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-loop", "1", "-t", str(seconds), "-i", str(cover),
                    "-filter_complex", f"[1:v]scale={W}:{H}[c];[0:v][c]overlay=eof_action=pass:enable='lt(t,{seconds})'[out]",
                    "-map", "[out]", "-map", "0:a?", "-c:v", codec, "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p",
                    "-c:a", "copy", "-map_metadata", "0", "-movflags", "+faststart", str(tmp)], check=True)
    tmp.replace(video)
    return str(video)
