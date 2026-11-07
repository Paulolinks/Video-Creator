"""Smart Motion Overlay Engine (Fase 1, laboratorio).

Adiciona motion graphics sincronizados com a fala sobre um MP4 ja pronto do Video Creator.
Nao altera o MP4 original; grava uma copia nova.

Uso:
  python smart_motion.py palavras  --ass legenda.ass [--de 40 --ate 60]
  python smart_motion.py numeros   --ass legenda.ass
  python smart_motion.py validar   --config overlays.json --ass legenda.ass --video in.mp4
  python smart_motion.py render    --config overlays.json --ass legenda.ass --video in.mp4 --out out.mp4
                                   [--encoder x264|nvenc] [--work pasta_temporaria]

Tempos: cada overlay usa start_ms/end_ms OU start_at/end_at ancorados numa palavra/frase da legenda:
  "start_at": {"word": "CEM MIL", "after_ms": 40000, "occurrence": 1, "offset_ms": -150, "edge": "start"}
"""
import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from marcacoes import norm, numeros_falados  # noqa: E402

HERE = Path(__file__).resolve().parent
FONTS = HERE.parent / "inputs" / "fonts"
FONT_XB = str(FONTS / "Poppins-ExtraBold.ttf")
FONT_B = str(FONTS / "Poppins-Bold.ttf")

GOLD = (255, 215, 69)
WHITE = (255, 255, 255)
PANEL = (12, 12, 16, 205)
DIM = (255, 255, 255, 70)
TYPES = {"counter", "bars", "flow", "cards", "keyword"}
PROFILES = {  # zonas seguras calibradas com frames reais (1080x1920)
    "F01": {"x": 80, "y": 1430, "width": 920, "height": 380},   # abaixo da legenda karaoke
    "T02": {"x": 80, "y": 280, "width": 920, "height": 400},    # entre o nome e a legenda
}


class ConfigError(Exception):
    pass


# ---------------------------------------------------------------- transcricao
def ts(s):
    h, m, sec = s.strip().split(":")
    return int(h) * 3600 + int(m) * 60 + float(sec)


def ler_ass(path):
    """Palavras com tempo global a partir das tags karaoke {\\K..} do legenda.ass do app."""
    words = []
    for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        if not line.startswith("Dialogue:"):
            continue
        parts = line.split(",", 9)
        text = parts[9]
        if not re.search(r"\\[kK][fo]?\d", text):
            continue
        t = ts(parts[1])
        for m in re.finditer(r"\{[^}]*?\\[kK][fo]?(\d+)[^}]*\}([^{]*)", text):
            dur = int(m.group(1)) / 100
            for w in m.group(2).split():
                if norm(w):
                    words.append({"w": w, "n": norm(w), "start": round(t, 3), "end": round(t + dur, 3)})
            t += dur
    words.sort(key=lambda x: x["start"])
    return words


def achar(words, spec, edge_default):
    """Resolve uma ancora {"word": "CEM MIL", ...} para segundos."""
    alvo = [norm(p) for p in str(spec["word"]).split() if norm(p)]
    if not alvo:
        raise ConfigError(f"ancora vazia: {spec}")
    after = spec.get("after_ms", 0) / 1000
    occ = spec.get("occurrence", 1)
    hits = []
    for i in range(len(words) - len(alvo) + 1):
        if words[i]["start"] + 1e-6 < after:
            continue
        if all(words[i + k]["n"] == alvo[k] for k in range(len(alvo))):
            hits.append((words[i], words[i + len(alvo) - 1]))
    if len(hits) < occ:
        raise ConfigError(f"palavra '{spec['word']}' (ocorrencia {occ}, apos {after:.1f}s) nao encontrada na fala")
    first, last = hits[occ - 1]
    edge = spec.get("edge", edge_default)
    t = first["start"] if edge == "start" else last["end"]
    return t + spec.get("offset_ms", 0) / 1000


def tempo(ov, chave, words, edge_default):
    if f"{chave}_ms" in ov:
        return ov[f"{chave}_ms"] / 1000
    if f"{chave}_at" in ov:
        return achar(words, ov[f"{chave}_at"], edge_default)
    raise ConfigError(f"{ov.get('id')}: falta {chave}_ms ou {chave}_at")


# ---------------------------------------------------------------- validacao
def valores_do_payload(ov):
    p = ov["payload"]
    if ov["type"] == "counter":
        return [p["to"]]
    if ov["type"] == "bars":
        return [b["value"] for b in p["bars"]]
    return []


def preparar(cfg, words, duracao, estrito=True):
    """Valida o JSON, resolve tempos e checa que os numeros animados foram ditos. Retorna overlays prontos.
    estrito=False (geracao no app): overlay com problema vira aviso e e pulado, sem derrubar o video."""
    erros, avisos, prontos = [], [], []
    if cfg.get("version") != "1.0":
        erros.append("version deve ser '1.0'")
    canvas = cfg.get("canvas", {})
    CW, CH = canvas.get("width", 1080), canvas.get("height", 1920)
    if canvas.get("fps") not in (24, 25, 30, 60) or CW >= CH:
        erros.append("canvas deve ser vertical (ex.: 1080x1920) com fps 24/25/30/60")
    zona = cfg.get("safe_zone") or PROFILES.get(cfg.get("profile", ""))
    if not zona:
        erros.append("defina safe_zone ou profile (F01/T02)")
    else:
        if zona["x"] < 0 or zona["y"] < 0 or zona["x"] + zona["width"] > CW or zona["y"] + zona["height"] > CH:
            erros.append(f"safe_zone fora do quadro {CW}x{CH}")
    falados = numeros_falados(words)
    ids = set()
    for ov in cfg.get("overlays", []):
        oid = ov.get("id", "?")
        try:
            if oid in ids:
                raise ConfigError("id repetido")
            ids.add(oid)
            if ov.get("type") not in TYPES:
                raise ConfigError(f"type invalido '{ov.get('type')}' (use {sorted(TYPES)})")
            p = ov.get("payload")
            if not isinstance(p, dict):
                raise ConfigError("payload ausente")
            checar_payload(ov["type"], p)
            s = tempo(ov, "start", words, "start")
            e = tempo(ov, "end", words, "end")
            if not (0 <= s < e <= duracao + 0.01):
                raise ConfigError(f"tempo invalido {s:.2f}-{e:.2f}s (video tem {duracao:.2f}s)")
            if not 0.8 <= e - s <= 12:
                raise ConfigError(f"duracao {e - s:.2f}s fora de 0.8-12s")
            marcas = []
            for item in itens_com_tempo(ov):
                marcas.append(item["at_ms"] / 1000 if "at_ms" in item else
                              achar(words, item["at"], "start") if "at" in item else s)
            for v in valores_do_payload(ov):
                ok = [n for n in falados if abs(n["valor"] - float(v)) < 1e-6 and n["start"] <= e + 3 and n["end"] >= s - 3]
                if not ok:
                    perto = [f"{n['texto']}={n['valor']:g}@{n['start']:.1f}s" for n in falados if n["start"] <= e + 3 and n["end"] >= s - 3]
                    raise ConfigError(f"valor {v} nao foi dito na fala entre {s - 3:.1f}s e {e + 3:.1f}s "
                                      f"(numeros falados ali: {perto or 'nenhum'}) - dado nao sustentado, bloqueado")
            prontos.append({**ov, "_s": s, "_e": e, "_marcas": marcas, "_zona": ov.get("zone", zona)})
        except (ConfigError, KeyError, TypeError, ValueError) as ex:
            (erros if estrito else avisos).append(f"{ov.get('nome', oid)}: {ex}")
    prontos.sort(key=lambda o: (o["_s"], o.get("priority", 9)))
    finais = []
    for o in prontos:  # a zona comporta um overlay por vez; conflito -> mantem a maior prioridade
        conflito = next((f for f in finais if o["_s"] < f["_e"] and f["_s"] < o["_e"]), None)
        if conflito is None:
            finais.append(o)
        elif o.get("priority", 9) < conflito.get("priority", 9):
            finais.remove(conflito)
            finais.append(o)
            avisos.append(f"{conflito.get('nome', conflito['id'])} removido: sobrepoe {o.get('nome', o['id'])}")
        else:
            avisos.append(f"{o.get('nome', o['id'])} removido: sobrepoe {conflito.get('nome', conflito['id'])}")
    if erros and (estrito or not zona):
        raise ConfigError("overlays.json invalido:\n  - " + "\n  - ".join(erros))
    return finais, avisos


def itens_com_tempo(ov):
    p = ov["payload"]
    return {"bars": p.get("bars", []), "flow": p.get("steps", []), "cards": p.get("cards", [])}.get(ov["type"], [])


def checar_payload(tipo, p):
    def req(k, t):
        if not isinstance(p.get(k), t):
            raise ConfigError(f"payload.{k} obrigatorio ({t.__name__ if isinstance(t, type) else t})")
    if tipo == "counter":
        req("to", (int, float))
        if not isinstance(p.get("from", 0), (int, float)):
            raise ConfigError("payload.from deve ser numero")
    elif tipo == "keyword":
        req("text", str)
        if not 1 <= len(p["text"].split("\n")) <= 2:
            raise ConfigError("keyword aceita 1 ou 2 linhas")
    elif tipo == "bars":
        req("bars", list)
        if not 2 <= len(p["bars"]) <= 5:
            raise ConfigError("bars aceita 2 a 5 barras")
        for b in p["bars"]:
            if not isinstance(b.get("label"), str) or not isinstance(b.get("value"), (int, float)) or b["value"] < 0:
                raise ConfigError("cada barra precisa de label (texto) e value (numero >= 0)")
    elif tipo == "flow":
        req("steps", list)
        if not 2 <= len(p["steps"]) <= 5:
            raise ConfigError("flow aceita 2 a 5 etapas")
        if any(not isinstance(s.get("label"), str) for s in p["steps"]):
            raise ConfigError("cada etapa precisa de label")
    elif tipo == "cards":
        req("cards", list)
        if not 1 <= len(p["cards"]) <= 2:
            raise ConfigError("cards aceita ate dois cards simultaneos")
        if any(not isinstance(c.get("title"), str) for c in p["cards"]):
            raise ConfigError("cada card precisa de title")


# ---------------------------------------------------------------- desenho
_fcache = {}


def fonte(size, bold=False):
    k = (size, bold)
    if k not in _fcache:
        _fcache[k] = ImageFont.truetype(FONT_B if bold else FONT_XB, size)
    return _fcache[k]


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_back(x):
    x = clamp(x)
    c = 1.70158
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def fmt_num(v, decimals=0):
    s = f"{v:,.{decimals}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def wrap(text, font, width):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if font.getlength(t) <= width or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def texto_c(d, cx, y, txt, font, fill):
    w = font.getlength(txt)
    d.text((cx - w / 2, y), txt, font=font, fill=fill)


def painel(d, box, borda=GOLD, raio=34, fill=PANEL, largura=4):
    d.rounded_rectangle(box, radius=raio, fill=fill, outline=borda + (255,) if len(borda) == 3 else borda, width=largura)


def draw_counter(img, ov, t, D):
    d = ImageDraw.Draw(img)
    W, H = img.size
    p = ov["payload"]
    dur = p.get("count_ms", 1300) / 1000
    v = p.get("from", 0) + (p["to"] - p.get("from", 0)) * ease_out((t - 0.15) / dur)
    dec = p.get("decimals", 0)
    num = f"{p.get('prefix', '')}{fmt_num(v, dec)}{p.get('unit', '')}"
    big = fonte(128)
    while big.getlength(num) > W - 120 and big.size > 60:
        big = fonte(big.size - 8)
    lab = p.get("label", "")
    suf = p.get("suffix", "")
    h = 70 + (56 if lab else 0) + big.size + (64 if suf else 0)
    y0 = (H - h) / 2
    painel(d, (20, y0, W - 20, y0 + h))
    y = y0 + 34
    if lab:
        texto_c(d, W / 2, y, lab.upper(), fonte(40, True), WHITE)
        y += 56
    texto_c(d, W / 2, y - big.size * 0.12, num, big, GOLD)
    y += big.size
    if suf:
        texto_c(d, W / 2, y - 6, suf, fonte(48, True), WHITE)


def draw_keyword(img, ov, t, D):
    d = ImageDraw.Draw(img)
    W, H = img.size
    p = ov["payload"]
    linhas = p["text"].upper().split("\n")
    f = fonte(132 if len(linhas) == 1 else 104)
    for _ in range(12):
        if max(f.getlength(l) for l in linhas) <= W - 120:
            break
        f = fonte(f.size - 10)
    sub = p.get("subtitle", "")
    h = 60 + len(linhas) * f.size * 1.05 + 30 + (64 if sub else 0)
    y0 = (H - h) / 2
    painel(d, (20, y0, W - 20, y0 + h), borda=(255, 255, 255, 60), largura=2)
    y = y0 + 26
    for l in linhas:
        texto_c(d, W / 2, y - f.size * 0.1, l, f, WHITE)
        y += f.size * 1.05
    lw = (W - 260) * ease_out((t - 0.25) / 0.5)
    d.rounded_rectangle((W / 2 - lw / 2, y + 6, W / 2 + lw / 2, y + 20), radius=7, fill=GOLD)
    if sub:
        texto_c(d, W / 2, y + 30, sub, fonte(46, True), GOLD)


def draw_bars(img, ov, t, D):
    d = ImageDraw.Draw(img)
    W, H = img.size
    p = ov["payload"]
    bars = p["bars"]
    titulo = p.get("title", "")
    n = len(bars)
    row = min(150, (H - 70 - (70 if titulo else 0)) / n)
    h = 50 + (70 if titulo else 0) + row * n
    y0 = (H - h) / 2
    painel(d, (20, y0, W - 20, y0 + h))
    y = y0 + 26
    if titulo:
        texto_c(d, W / 2, y, titulo.upper(), fonte(46), GOLD)
        y += 70
    vmax = max(b["value"] for b in bars) or 1
    fl, fv = fonte(int(row * 0.30), True), fonte(int(row * 0.32))
    x0, x1 = 60, W - 60
    for i, b in enumerate(bars):
        t0 = ov["_marcas"][i] - ov["_s"] if ov["_marcas"] else 0.2 + i * 0.25
        k = ease_out((t - t0) / 0.7)
        d.text((x0, y), b["label"].upper(), font=fl, fill=WHITE if k > 0 else (255, 255, 255, 110))
        by = y + row * 0.42
        bh = row * 0.38
        d.rounded_rectangle((x0, by, x1, by + bh), radius=bh / 2, fill=(255, 255, 255, 38))
        fw = (x1 - x0) * (b["value"] / vmax) * k
        if fw > bh:
            d.rounded_rectangle((x0, by, x0 + fw, by + bh), radius=bh / 2, fill=GOLD)
        if k > 0:
            txt = f"{p.get('prefix', '')}{fmt_num(b['value'] * k, p.get('decimals', 0))}{p.get('suffix', '')}"
            tw = fv.getlength(txt)
            d.text((x1 - tw, y - row * 0.06), txt, font=fv, fill=GOLD)
        y += row


def seta(d, x0, x1, y, cor, k):
    if k <= 0:
        return
    xe = x0 + (x1 - x0) * k
    d.line((x0, y, xe, y), fill=cor, width=6)
    if k > 0.6:
        d.polygon([(xe + 4, y), (xe - 14, y - 12), (xe - 14, y + 12)], fill=cor)


def draw_flow(img, ov, t, D):
    d = ImageDraw.Draw(img)
    W, H = img.size
    p = ov["payload"]
    steps = p["steps"]
    n = len(steps)
    titulo = p.get("title", "")
    h = H - 20
    y0 = 10
    painel(d, (16, y0, W - 16, y0 + h), borda=(255, 255, 255, 60), largura=2)
    top = y0 + 28
    if titulo:
        texto_c(d, W / 2, top, titulo.upper(), fonte(38, True), WHITE)
        top += 56
    gap = 36
    nw = (W - 72 - gap * (n - 1)) / n
    nh = y0 + h - 28 - top
    marcas = [m - ov["_s"] for m in ov["_marcas"]] or [0.2 + i * 0.6 for i in range(n)]
    ativo = max([i for i, m in enumerate(marcas) if t >= m], default=-1)
    fs = 44 if n <= 3 else 34 if n == 4 else 28
    palavras = [w for s in steps for w in s["label"].upper().split()]
    while fs > 18 and (max(fonte(fs, True).getlength(w) for w in palavras) > nw - 24
                       or max(len(wrap(s["label"].upper(), fonte(fs, True), nw - 24)) for s in steps) > 3):
        fs -= 2
    f = fonte(fs, True)
    for i, s in enumerate(steps):
        x = 36 + i * (nw + gap)
        on = i <= ativo
        atual = i == ativo
        k = ease_back((t - marcas[i]) / 0.35) if on else 0
        grow = 8 * k if atual else 0
        box = (x - grow, top - grow, x + nw + grow, top + nh + grow)
        d.rounded_rectangle(box, radius=26, fill=(GOLD + (255,)) if atual else (255, 255, 255, 30 if not on else 55),
                            outline=GOLD + (255,) if on else DIM, width=4)
        cor = (12, 12, 16) if atual else (WHITE if on else (255, 255, 255, 120))
        cx = x + nw / 2
        circ = 30
        d.ellipse((cx - circ, top + 22, cx + circ, top + 22 + 2 * circ),
                  fill=(12, 12, 16) if atual else (GOLD if on else (255, 255, 255, 60)))
        texto_c(d, cx, top + 22 + circ - 26, str(i + 1), fonte(36), GOLD if atual else (12, 12, 16))
        linhas = wrap(s["label"].upper(), f, nw - 24)[:3]
        ty = top + 22 + 2 * circ + (nh - 2 * circ - 22 - len(linhas) * fs * 1.15) / 2 - fs * 0.15
        for l in linhas:
            texto_c(d, cx, ty, l, f, cor)
            ty += fs * 1.15
        if i < n - 1:
            ka = ease_out((t - marcas[i + 1] + 0.25) / 0.25) if i + 1 <= ativo else 0
            seta(d, x + nw + 6, x + nw + gap - 6, top + nh / 2, GOLD + (255,) if ka > 0 else DIM, ka if ka > 0 else 1)


def icone(d, cx, cy, r, ok):
    if ok:
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=GOLD)
        d.line([(cx - r * 0.45, cy + r * 0.02), (cx - r * 0.1, cy + r * 0.38), (cx + r * 0.5, cy - r * 0.35)],
               fill=(12, 12, 16), width=max(4, int(r * 0.22)), joint="curve")
    else:
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 255, 255, 70))
        a = r * 0.38
        d.line((cx - a, cy - a, cx + a, cy + a), fill=WHITE, width=max(4, int(r * 0.2)))
        d.line((cx - a, cy + a, cx + a, cy - a), fill=WHITE, width=max(4, int(r * 0.2)))


def draw_cards(img, ov, t, D):
    W, H = img.size
    p = ov["payload"]
    cards = p["cards"]
    n = len(cards)
    gap = 30
    cw = (W - 40 - gap * (n - 1)) / n
    marcas = [m - ov["_s"] for m in ov["_marcas"]] or [0.0, 0.5][:n]
    for i, c in enumerate(cards):
        k = ease_out((t - marcas[i]) / 0.4)
        if k <= 0:
            continue
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        x = 20 + i * (cw + gap)
        ok = c.get("tone", "positive" if i == n - 1 else "negative") == "positive"
        y0, y1 = 10, H - 10
        painel(d, (x, y0, x + cw, y1), borda=GOLD if ok else (255, 255, 255, 80), largura=4 if ok else 2)
        icone(d, x + cw / 2, y0 + 70, 42, ok)
        sz = 58 if n == 2 else 72
        while sz > 30 and (len(wrap(c["title"].upper(), fonte(sz), cw - 40)) > 2
                           or max(fonte(sz).getlength(w) for w in c["title"].upper().split()) > cw - 40):
            sz -= 4
        ft = fonte(sz)
        tl = wrap(c["title"].upper(), ft, cw - 40)
        fb = fonte(38, True)
        bl = wrap(c.get("text", ""), fb, cw - 50)[:3]
        bloco = len(tl) * sz * 1.08 + (14 + len(bl) * 48 if bl else 0)
        ty = y0 + 124 + (y1 - y0 - 124 - bloco) / 2 - 14
        for l in tl:
            texto_c(d, x + cw / 2, ty, l, ft, GOLD if ok else WHITE)
            ty += sz * 1.08
        ty += 14
        for l in bl:
            texto_c(d, x + cw / 2, ty, l, fb, (255, 255, 255, 225))
            ty += 48
        dy = int((1 - k) * 60)
        a = np.asarray(lay).copy()
        a[..., 3] = (a[..., 3] * k).astype(np.uint8)
        img.alpha_composite(Image.fromarray(a), (0, dy))


DRAW = {"counter": draw_counter, "keyword": draw_keyword, "bars": draw_bars, "flow": draw_flow, "cards": draw_cards}
INTENSIDADE = {"minimal": (0.35, 0.3, 0.0), "balanced": (0.30, 0.25, 0.06), "dynamic": (0.24, 0.2, 0.12)}


def frame_overlay(ov, t, D, intensidade):
    z = ov["_zona"]
    img = Image.new("RGBA", (z["width"], z["height"]), (0, 0, 0, 0))
    DRAW[ov["type"]](img, ov, t, D)
    t_in, t_out, pop = INTENSIDADE[intensidade]
    a_in = ease_out(t / t_in)
    a_out = clamp((D - t) / t_out)
    alpha = min(a_in, a_out)
    escala = 1 - pop + pop * ease_back(t / (t_in * 1.4)) if t < D - t_out else 1 - 0.03 * (1 - a_out)
    if abs(escala - 1) > 1e-3:
        w, h = img.size
        sw, sh = max(1, int(w * escala)), max(1, int(h * escala))
        small = img.resize((sw, sh), Image.BILINEAR)
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        img.alpha_composite(small, ((w - sw) // 2, (h - sh) // 2)) if sw <= w and sh <= h else \
            img.alpha_composite(small.crop(((sw - w) // 2, (sh - h) // 2, (sw - w) // 2 + w, (sh - h) // 2 + h)))
    a = np.asarray(img).copy()
    if alpha < 1:
        a[..., 3] = (a[..., 3].astype(np.float32) * alpha).astype(np.uint8)
    return a


# ---------------------------------------------------------------- video
def ffmpeg():
    return shutil.which("ffmpeg") or "ffmpeg"


def duracao_video(video):
    r = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(video)], capture_output=True, text=True, errors="replace")
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    if not m:
        raise ConfigError(f"nao consegui ler a duracao de {video}")
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def render_camadas(overlays, work, fps, intensidade):
    """Uma camada .mov com alpha (qtrle) por overlay, so do tamanho da zona e so durante o overlay."""
    work.mkdir(parents=True, exist_ok=True)
    out = []
    for ov in overlays:
        z = ov["_zona"]
        f0, f1 = round(ov["_s"] * fps), round(ov["_e"] * fps)
        D = (f1 - f0) / fps
        path = work / f"{ov['id']}.mov"
        enc = subprocess.Popen([ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
                                "-pix_fmt", "rgba", "-s", f"{z['width']}x{z['height']}", "-r", str(fps), "-i", "-",
                                "-c:v", "qtrle", "-pix_fmt", "argb", str(path)], stdin=subprocess.PIPE)
        for k in range(f1 - f0):
            enc.stdin.write(frame_overlay(ov, k / fps, D, intensidade).tobytes())
        enc.stdin.close()
        if enc.wait() != 0:
            raise RuntimeError(f"falha ao gravar camada {ov['id']}")
        out.append({"path": path, "x": z["x"], "y": z["y"], "s": f0 / fps, "e": f1 / fps, "id": ov["id"]})
    return out


def enc_args(encoder):
    if encoder == "nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p6", "-tune", "hq", "-rc", "vbr", "-cq", "19", "-b:v", "0",
                "-pix_fmt", "yuv420p"]
    return ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"]


def compor(video, camadas, out, encoder):
    cmd = [ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(video)]
    for c in camadas:
        cmd += ["-i", str(c["path"])]
    if not camadas:
        cmd += ["-map", "0:v", "-map", "0:a?", *enc_args(encoder), "-c:a", "copy", "-movflags", "+faststart", str(out)]
    else:
        g, last = [], "0:v"
        for i, c in enumerate(camadas, 1):
            g.append(f"[{i}:v]setpts=PTS-STARTPTS+{c['s']:.3f}/TB[o{i}]")
            g.append(f"[{last}][o{i}]overlay=x={c['x']}:y={c['y']}:eof_action=pass:"
                     f"enable='between(t,{c['s']:.3f},{c['e']:.3f})'[v{i}]")
            last = f"v{i}"
        cmd += ["-filter_complex", ";".join(g), "-map", f"[{last}]", "-map", "0:a?", *enc_args(encoder),
                "-c:a", "copy", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)


def aplicar(video, ass, config, out, encoder="x264", work=None, log=print):
    """Pipeline completo. Retorna dict com tempos por etapa."""
    video, out = Path(video), Path(out)
    if video.resolve() == out.resolve():
        raise ConfigError("a saida nao pode sobrescrever o MP4 original")
    t = {}
    t0 = time.perf_counter()
    cfg = json.loads(Path(config).read_text(encoding="utf-8")) if not isinstance(config, dict) else config
    words = ler_ass(ass)
    dur = duracao_video(video)
    overlays, avisos = preparar(cfg, words, dur)
    for a in avisos:
        log("AVISO:", a)
    t["planejar_validar_s"] = round(time.perf_counter() - t0, 3)
    work = Path(work) if work else out.parent / f"_camadas_{out.stem}"
    t1 = time.perf_counter()
    camadas = render_camadas(overlays, work, cfg["canvas"]["fps"], cfg.get("intensity", "balanced"))
    t["render_camadas_s"] = round(time.perf_counter() - t1, 3)
    t2 = time.perf_counter()
    out.parent.mkdir(parents=True, exist_ok=True)
    compor(video, camadas, out, encoder)
    t["compor_encode_s"] = round(time.perf_counter() - t2, 3)
    t["total_s"] = round(time.perf_counter() - t0, 3)
    t["overlays"] = [{"id": o["id"], "type": o["type"], "start_s": round(o["_s"], 3), "end_s": round(o["_e"], 3),
                      "marcas_s": [round(m, 3) for m in o["_marcas"]]} for o in overlays]
    t["avisos"] = avisos
    return t


def aplicar_com_fallback(video, ass, config, out, **kw):
    """Para a Fase 2: se algo falhar, devolve o video normal e registra o erro, sem interromper a geracao."""
    try:
        return Path(out), aplicar(video, ass, config, out, **kw)
    except Exception as ex:  # noqa: BLE001
        return Path(video), {"erro": f"{type(ex).__name__}: {ex}"}


# ---------------------------------------------------------------- integracao com o app (marcacoes no roteiro)
from marcacoes import NOMES  # noqa: E402

_FIM_FRASE = re.compile(r"[.!?…]['\")\]]*$")
_STOP = {"PARA", "COMO", "MAIS", "QUE", "COM", "UMA", "ESSE", "ESSA", "ISSO", "ESTE", "ESTA", "SEUS", "SUAS",
         "SOBRE", "THE", "AND", "WITH", "THAT", "THIS", "YOUR", "FROM", "INTO", "MUITO", "PELO", "PELA", "NAO"}
DURACAO = {"counter": (2.5, 6), "keyword": (2.0, 5), "bars": (3.0, 10), "flow": (3.0, 12), "cards": (3.0, 10)}


def zona(tpl, modelo):
    """Zona segura calculada do template já com o estilo escolhido (fonte/tamanho da legenda).
    None = formato sem zona validada (horizontal 16:9): o vídeo sai sem animações."""
    W, H = tpl["video"]["largura"], tpl["video"]["altura"]
    if W >= H:
        return None
    lg = tpl.get("legenda") or {}
    if modelo == "F01":  # legenda presa embaixo (MarginV): a animação fica abaixo dela
        y0, y1 = H - int(lg.get("margem_inferior", 560)) + 70, H - 100
    else:  # entrevista: entre o nome de quem fala e a legenda
        y0 = int((tpl.get("rotulos") or {}).get("nome_y", 225)) + 55
        y1 = int(lg.get("centro_y", 760)) - int(int(lg.get("tamanho", 84)) * 0.75) - 20
    if y1 - y0 < 300:
        return None
    h = min(y1 - y0, 420)
    return {"x": 80, "y": y0 + (y1 - y0 - h) // 2, "width": W - 160, "height": h}


def _chaves(texto):
    return {norm(w) for w in texto.split() if len(norm(w)) >= 4 and norm(w) not in _STOP}


def _bate(n, chave):
    return n == chave or (len(chave) >= 5 and len(n) >= 5 and n[:5] == chave[:5])


def _achar_item(ws, ini, chaves):
    """Primeira posição >= ini com o maior número de palavras-chave do item logo em seguida."""
    if not chaves:
        return None
    melhor, pos = 0, None
    for j in range(ini, min(len(ws), ini + 80)):
        if not any(_bate(ws[j]["n"], c) for c in chaves):
            continue
        janela = ws[j:j + len(chaves) + 2]
        score = sum(1 for c in chaves if any(_bate(w["n"], c) for w in janela))
        if score > melhor:
            melhor, pos = score, j
    return pos


def _fim_frase(ws, i):
    for j in range(i, len(ws)):
        if _FIM_FRASE.search(ws[j]["word"]):
            return j
    return len(ws) - 1


def _indice_em(ws, t):
    return next((j for j, w in enumerate(ws) if w["start"] >= t - 1e-3), len(ws) - 1)


def planejar(anim, ws):
    """Uma marcação + palavras da cena (tempo global) -> overlay com start_ms/end_ms e itens com at_ms."""
    tipo, p = anim["tipo"], json.loads(json.dumps(anim["payload"]))
    i0 = min(anim["palavra"], len(ws) - 1)
    s = max(0.0, ws[i0]["start"] - 0.12)
    ultimo = i0
    itens = {"flow": p.get("steps"), "cards": p.get("cards"), "bars": p.get("bars")}.get(tipo) or []
    marcas = []
    if tipo in ("flow", "cards"):
        cur = i0
        for k, it in enumerate(itens):
            if k == 0:
                j = i0
            else:
                rot = it["label"] if tipo == "flow" else it["title"]
                j = _achar_item(ws, cur, _chaves(rot))
                if j is None and tipo == "cards":
                    j = _achar_item(ws, cur, _chaves(it.get("text", "")))
            if j is None:
                marcas = []
                break
            marcas.append(ws[j]["start"])
            cur, ultimo = j + 1, j
    elif tipo == "bars":
        falados = numeros_falados(ws[i0:])
        t = s
        for b in itens:
            hit = next((n for n in falados if abs(n["valor"] - b["value"]) < 1e-6 and n["start"] >= t - 0.01), None)
            if hit is None:
                marcas = []
                break
            marcas.append(hit["start"])
            t = hit["start"]
        if marcas:
            ultimo = _indice_em(ws, marcas[-1])
    if itens and not marcas:  # palavras das etapas não encontradas na fala: acende uma por vez
        marcas = [s + 0.15 + k * 1.4 for k in range(len(itens))]
        ultimo = _indice_em(ws, marcas[-1])
    for it, m in zip(itens, marcas):
        it["at_ms"] = round(m * 1000)
    e = ws[_fim_frase(ws, ultimo)]["end"] + 0.6
    lo, hi = DURACAO[tipo]
    e = min(max(e, s + lo, (marcas[-1] + 1.8) if marcas else 0), s + hi)
    return {"type": tipo, "start_ms": round(s * 1000), "end_ms": round(e * 1000), "payload": p, "priority": 1}


def overlays_do_roteiro(scenes, timeline, total, inicio_min=0.0):
    ovs, avisos = [], []
    for sc, words in zip(scenes, timeline):
        ws = [{**w, "n": norm(w["word"])} for w in words]
        for k, a in enumerate(sc.get("animacoes") or []):
            nome = f"{NOMES.get(a['tipo'], a['tipo'])} da {sc['id'].replace('_', ' ').lower()}"
            if not ws:
                continue
            try:
                ov = planejar(a, ws)
            except (KeyError, ValueError, TypeError, IndexError) as ex:
                avisos.append(f"{nome}: {ex}")
                continue
            ov.update(id=f"{sc['id']}_{k + 1}", nome=nome)
            ovs.append(ov)
    ovs.sort(key=lambda o: o["start_ms"])
    finais = []
    for o in ovs:
        o["start_ms"] = max(o["start_ms"], round(inicio_min * 1000))
        o["end_ms"] = min(o["end_ms"], round((total - 0.1) * 1000))
        if finais and finais[-1]["end_ms"] > o["start_ms"] - 150:  # uma por vez: a anterior encurta
            finais[-1]["end_ms"] = o["start_ms"] - 150
            if finais[-1]["end_ms"] - finais[-1]["start_ms"] < 1500:
                avisos.append(f"{finais[-1]['nome']} removido: ficou curto demais antes de {o['nome']}")
                finais.pop()
        if o["end_ms"] - o["start_ms"] >= 1500:
            finais.append(o)
        else:
            avisos.append(f"{o['nome']} removido: tempo de tela curto demais")
    return finais, avisos


def aplicar_no_filtro(tpl, modelo, scenes, timeline, total, work, primeiro_indice, ultimo_rotulo, inicio_min=0.0):
    """Para os compositores: devolve (inputs, filtros, novo_rotulo, info). Os overlays entram na mesma passada
    final da legenda (antes de subtitles=), sem encode extra. Qualquer falha -> vídeo normal + erro em info."""
    info = {"animacoes": 0, "avisos": []}
    sm = tpl.get("smart_motion") or {}
    if sm.get("ativo") is False or not any(sc.get("animacoes") for sc in scenes):
        return [], [], ultimo_rotulo, info
    t0 = time.perf_counter()
    try:
        z = zona(tpl, modelo)
        if not z:
            info["avisos"].append("Animações ainda não disponíveis neste formato (só vertical 9:16): vídeo sem elas.")
            return [], [], ultimo_rotulo, info
        ovs, avisos = overlays_do_roteiro(scenes, timeline, total, inicio_min)
        flat = [{"w": w["word"], "n": norm(w["word"]), "start": w["start"], "end": w["end"]} for ws in timeline for w in ws]
        v = tpl["video"]
        cfg = {"version": "1.0", "canvas": {"width": v["largura"], "height": v["altura"], "fps": v["fps"]},
               "intensity": sm.get("intensidade", "balanced"), "safe_zone": z, "overlays": ovs}
        finais, av2 = preparar(cfg, flat, total, estrito=False)
        camadas = render_camadas(finais, Path(work) / "motion", v["fps"], cfg["intensity"])
        inputs, graph, last = [], [], ultimo_rotulo
        for k, c in enumerate(camadas):
            inputs += ["-i", str(c["path"])]
            graph.append(f"[{primeiro_indice + k}:v]setpts=PTS-STARTPTS+{c['s']:.3f}/TB[sm{k}]")
            graph.append(f"[{last}][sm{k}]overlay=x={c['x']}:y={c['y']}:eof_action=pass:"
                         f"enable='between(t,{c['s']:.3f},{c['e']:.3f})'[smv{k}]")
            last = f"smv{k}"
        info.update(animacoes=len(camadas), avisos=avisos + av2, render_s=round(time.perf_counter() - t0, 2),
                    lista=[{"nome": o.get("nome"), "tipo": o["type"], "inicio_s": round(o["_s"], 2),
                            "fim_s": round(o["_e"], 2)} for o in finais])
        return inputs, graph, last, info
    except Exception as ex:  # noqa: BLE001  fallback: nunca derruba a geração
        info["erro"] = f"{type(ex).__name__}: {ex}"
        return [], [], ultimo_rotulo, info


# ---------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["palavras", "numeros", "validar", "render"])
    ap.add_argument("--ass", required=True)
    ap.add_argument("--config")
    ap.add_argument("--video")
    ap.add_argument("--out")
    ap.add_argument("--encoder", choices=["x264", "nvenc"], default="x264")
    ap.add_argument("--work")
    ap.add_argument("--de", type=float, default=0)
    ap.add_argument("--ate", type=float, default=1e9)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    words = ler_ass(a.ass)
    if a.cmd == "palavras":
        for w in words:
            if a.de <= w["start"] <= a.ate:
                print(f"{w['start']:8.2f} {w['end']:8.2f}  {w['w']}")
    elif a.cmd == "numeros":
        for n in numeros_falados(words):
            print(f"{n['start']:8.2f}  {n['valor']:>14,.0f}  {n['texto']}")
    elif a.cmd == "validar":
        cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
        try:
            ovs, avisos = preparar(cfg, words, duracao_video(a.video))
        except ConfigError as ex:
            print(ex)
            sys.exit(2)
        for a_ in avisos:
            print("AVISO:", a_)
        for o in ovs:
            print(f"OK {o['id']:6} {o['type']:8} {o['_s']:7.2f}-{o['_e']:7.2f}s marcas={[round(m, 2) for m in o['_marcas']]}")
    else:
        try:
            r = aplicar(a.video, a.ass, a.config, a.out, a.encoder, a.work)
        except ConfigError as ex:
            print(ex)
            sys.exit(2)
        print(json.dumps(r, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
