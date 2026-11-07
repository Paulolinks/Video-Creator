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
def norm(s):
    s = unicodedata.normalize("NFD", s.upper())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^A-Z0-9%]", "", s)


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


UNID = {"ZERO": 0, "UM": 1, "UMA": 1, "DOIS": 2, "DUAS": 2, "TRES": 3, "QUATRO": 4, "CINCO": 5, "SEIS": 6,
        "SETE": 7, "OITO": 8, "NOVE": 9, "DEZ": 10, "ONZE": 11, "DOZE": 12, "TREZE": 13, "CATORZE": 14,
        "QUATORZE": 14, "QUINZE": 15, "DEZESSEIS": 16, "DEZESSETE": 17, "DEZOITO": 18, "DEZENOVE": 19,
        "VINTE": 20, "TRINTA": 30, "QUARENTA": 40, "CINQUENTA": 50, "SESSENTA": 60, "SETENTA": 70,
        "OITENTA": 80, "NOVENTA": 90, "CEM": 100, "CENTO": 100, "DUZENTOS": 200, "DUZENTAS": 200,
        "TREZENTOS": 300, "QUATROCENTOS": 400, "QUINHENTOS": 500, "SEISCENTOS": 600, "SETECENTOS": 700,
        "OITOCENTOS": 800, "NOVECENTOS": 900}
MULT = {"MIL": 1000, "MILHAO": 10**6, "MILHOES": 10**6, "BILHAO": 10**9, "BILHOES": 10**9}


def numeros_falados(words):
    """Valores numericos ditos na fala (digitos ou por extenso em pt-BR) com seus tempos."""
    out, i = [], 0
    while i < len(words):
        n = words[i]["n"]
        if re.fullmatch(r"[\d.,]+%?", words[i]["w"].strip(".,;:!?")) and any(c.isdigit() for c in n):
            raw = words[i]["w"].strip(".,;:!?").replace("%", "")
            raw = raw.replace(".", "") if re.fullmatch(r"\d{1,3}(\.\d{3})+", raw) else raw.replace(",", ".")
            try:
                out.append({"valor": float(raw), "start": words[i]["start"], "end": words[i]["end"], "texto": words[i]["w"]})
            except ValueError:
                pass
            i += 1
            continue
        if n == "CENTO" and i > 0 and words[i - 1]["n"] == "POR":  # "dez por cento" -> 10, nao 100
            i += 1
            continue
        if n in UNID:
            total, cur, j, end = 0, 0, i, words[i]["end"]
            while j < len(words):
                nj = words[j]["n"]
                if nj in UNID:
                    cur += UNID[nj]
                elif nj in MULT:
                    total += max(cur, 1) * MULT[nj]
                    cur = 0
                elif nj == "E" and j + 1 < len(words) and (words[j + 1]["n"] in UNID or words[j + 1]["n"] in MULT):
                    pass
                else:
                    break
                end = words[j]["end"]
                j += 1
            val = total + cur
            out.append({"valor": float(val), "start": words[i]["start"], "end": end,
                        "texto": " ".join(w["w"] for w in words[i:j])})
            i = j
            continue
        i += 1
    return out


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


def preparar(cfg, words, duracao):
    """Valida o JSON, resolve tempos e checa que os numeros animados foram ditos. Retorna overlays prontos."""
    erros, avisos, prontos = [], [], []
    if cfg.get("version") != "1.0":
        erros.append("version deve ser '1.0'")
    canvas = cfg.get("canvas", {})
    if (canvas.get("width"), canvas.get("height"), canvas.get("fps")) != (1080, 1920, 30):
        erros.append("canvas deve ser 1080x1920 a 30fps")
    zona = cfg.get("safe_zone") or PROFILES.get(cfg.get("profile", ""))
    if not zona:
        erros.append("defina safe_zone ou profile (F01/T02)")
    else:
        if zona["x"] < 0 or zona["y"] < 0 or zona["x"] + zona["width"] > 1080 or zona["y"] + zona["height"] > 1920:
            erros.append("safe_zone fora do quadro 1080x1920")
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
                marcas.append(achar(words, item["at"], "start") if "at" in item else s)
            for v in valores_do_payload(ov):
                ok = [n for n in falados if abs(n["valor"] - float(v)) < 1e-6 and n["start"] <= e + 3 and n["end"] >= s - 3]
                if not ok:
                    perto = [f"{n['texto']}={n['valor']:g}@{n['start']:.1f}s" for n in falados if n["start"] <= e + 3 and n["end"] >= s - 3]
                    raise ConfigError(f"valor {v} nao foi dito na fala entre {s - 3:.1f}s e {e + 3:.1f}s "
                                      f"(numeros falados ali: {perto or 'nenhum'}) - dado nao sustentado, bloqueado")
            prontos.append({**ov, "_s": s, "_e": e, "_marcas": marcas, "_zona": ov.get("zone", zona)})
        except (ConfigError, KeyError, TypeError, ValueError) as ex:
            erros.append(f"{oid}: {ex}")
    prontos.sort(key=lambda o: (o["_s"], o.get("priority", 9)))
    finais = []
    for o in prontos:  # a zona comporta um overlay por vez; conflito -> mantem a maior prioridade
        conflito = next((f for f in finais if o["_s"] < f["_e"] and f["_s"] < o["_e"]), None)
        if conflito is None:
            finais.append(o)
        elif o.get("priority", 9) < conflito.get("priority", 9):
            finais.remove(conflito)
            finais.append(o)
            avisos.append(f"{conflito['id']} removido: sobrepoe {o['id']} (prioridade maior)")
        else:
            avisos.append(f"{o['id']} removido: sobrepoe {conflito['id']} (prioridade maior)")
    if erros:
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
    num = f"{p.get('prefix', '')}{fmt_num(v, dec)}"
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
