"""Personagem falando (F01) sem enviar imagens: o app monta as cenas sozinho.

- Cena de FALA sem imagem: uma pose recortada do personagem cadastrado sobre um dos fundos dele (pose e fundo
  mudam a cada cena). O SadTalker anima o rosto depois, como numa imagem enviada.
- Cena sem fala (DOLLY/ZOOM) sem imagem: uma foto do Pixabay buscada pela linha BUSCA: da cena (palavras-chave)
  ou, sem ela, pela descrição IMAGEM:. Sem chave do Pixabay ou sem resultado: um quadro de um fundo do personagem.
- Imagem enviada (cenaN.png) sempre tem prioridade.
A chave do Pixabay fica em app/data/pixabay.json ({"key": "..."}) ou na variável PIXABAY_API_KEY.
"""
import json
import os
import random
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

from . import library

KEY_FILE = library.DATA / "pixabay.json"
USED_FILE = library.DATA / "pixabay_usadas.json"
API = "https://pixabay.com/api/"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) VideoCreator/1.0"}  # urllib's default UA gets 403
_STOP = {"a", "o", "as", "os", "um", "uma", "de", "da", "do", "das", "dos", "e", "em", "no", "na", "nos", "nas",
         "com", "para", "por", "que", "se", "sem", "ao", "à", "sua", "seu", "suas", "seus", "the", "of", "and",
         "in", "on", "with", "to", "for", "an", "is", "sobre", "entre", "como", "mais", "muito", "onde", "quando"}


def pixabay_key():
    key = os.environ.get("PIXABAY_API_KEY", "").strip()
    if not key and KEY_FILE.exists():
        key = json.loads(KEY_FILE.read_text(encoding="utf-8")).get("key", "").strip()
    return key or None


def save_key(key):
    KEY_FILE.write_text(json.dumps({"key": key.strip()}), encoding="utf-8")


def character_ready(name):
    """O personagem do F01 está cadastrado com recorte de verdade (sem fundo) e ao menos um fundo?"""
    ch = library.find_character(name) if name else None
    if not ch or ch.get("imagem_provisoria") or not ch.get("transparente"):
        return None
    return ch if _bg_pool(ch) else None


def _bg_pool(ch):
    ids = ch.get("fundos") or [ch.get("fundo")]
    return [b for b in (library.get("fundos", i) for i in ids if i) if b and Path(b["arquivo"]).exists()]


# ------------------------------------------------------------------ imagens
def _cover(img, W, H):
    s = max(W / img.width, H / img.height)
    img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    x, y = (img.width - W) // 2, (img.height - H) // 2
    return img.crop((x, y, x + W, y + H))


def _frame(path, at=None):
    """Imagem do fundo: o arquivo, ou um quadro do vídeo (variando o instante para não repetir)."""
    path = Path(path)
    if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
        return Image.open(path).convert("RGB")
    out = path.parent / f"_quadro_{int((at or 0) * 10)}.jpg"
    if not out.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{at or 2:.1f}", "-i", str(path), "-frames:v", "1",
                        "-q:v", "2", str(out)], check=True, timeout=60)
    return Image.open(out).convert("RGB")


def talking_image(pose, background, out, W, H, at=2.0):
    """Pose recortada sobre o fundo (escurecido e levemente desfocado, como na entrevista), embaixo, no centro."""
    bg = _cover(_frame(background, at), W, H).filter(ImageFilter.GaussianBlur(3))
    bg = ImageEnhance.Brightness(bg).enhance(0.72).convert("RGBA")
    p = Image.open(pose).convert("RGBA")
    p = p.crop(p.split()[-1].getbbox() or (0, 0, p.width, p.height))
    vertical = H > W
    # vertical: sized by height so the face sits above the F01 caption (y ~ 64-71% of the frame); the sides of a
    # wide pose may be cropped a little. Horizontal: the person on half of the frame.
    s = min(W * 1.45 / p.width, H * 0.76 / p.height) if vertical else min(W * 0.5 / p.width, H * 0.92 / p.height)
    p = p.resize((round(p.width * s), round(p.height * s)), Image.LANCZOS)
    top = np.asarray(p.split()[-1])[: max(1, int(p.height * 0.22))] > 160  # top of the pose = head (solid pixels)
    cols = np.nonzero(top)[1]
    cx = float(np.median(cols)) if cols.size else p.width / 2
    x = round(W / 2 - cx) if vertical else (W - p.width) // 2
    a = np.asarray(p.split()[-1]) > 160
    cut_l, cut_r = a[:, 0].mean() > 0.15, a[:, -1].mean() > 0.15  # body cut by the original photo's border
    if cut_r and not cut_l:
        x = max(x, W - p.width)  # hide the straight cut behind the frame's right edge
    elif cut_l and not cut_r:
        x = min(x, 0)
    x = min(max(x, round(W * 0.25 - cx)), round(W * 0.75 - cx))  # the head stays in the middle half
    bg.alpha_composite(p, (x, H - p.height))
    bg.convert("RGB").save(out, quality=95)
    return out


def _get(url, timeout=30):
    for t in range(3):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout)
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            if t == 2:
                raise
            time.sleep(2 * (t + 1))


def _queries(busca, descricao, idioma):
    """Tentativas da mais específica para a mais ampla (a API do Pixabay exige todas as palavras)."""
    out = []
    if busca:
        words = busca.replace(",", " ").split()
        out += [(" ".join(words[:4]), "en"), (" ".join(words[:2]), "en")]
    words = [w for w in re.findall(r"[\wÀ-ú]+", descricao or "") if w.lower() not in _STOP and len(w) > 2]
    lang = "pt" if idioma == "pt" else "en"
    out += [(" ".join(words[:3]), lang), (" ".join(words[:2]), lang), (" ".join(words[:1]), lang)]
    seen, res = set(), []
    for q, l in out:
        if q and (q, l) not in seen:
            seen.add((q, l))
            res.append((q, l))
    return res


def pixabay_image(busca, descricao, idioma, out, key):
    """Baixa uma foto (vertical de preferência) que ainda não foi usada. Retorna (arquivo, crédito) ou None."""
    used = set(json.loads(USED_FILE.read_text(encoding="utf-8"))) if USED_FILE.exists() else set()
    for q, lang in _queries(busca, descricao, idioma):
        for orient in ("vertical", "all"):
            params = {"key": key, "q": q[:100], "lang": lang, "image_type": "photo", "orientation": orient,
                      "safesearch": "true", "per_page": 30, "order": "popular"}
            with _get(f"{API}?{urllib.parse.urlencode(params)}") as r:
                hits = json.loads(r.read().decode("utf-8")).get("hits", [])
            hits = [h for h in hits if h.get("largeImageURL") and max(h["imageWidth"], h["imageHeight"]) >= 1200]
            fresh = [h for h in hits if h["id"] not in used] or hits
            if fresh:
                h = random.choice(fresh[:6])
                with _get(h["largeImageURL"], 60) as r:
                    Path(out).write_bytes(r.read())
                used.add(h["id"])
                USED_FILE.write_text(json.dumps(sorted(used)[-3000:]), encoding="utf-8")
                return out, f"Pixabay #{h['id']} ({h['pageURL']}), busca \"{q}\""
    return None


def complete(video, folder, W, H):
    """Preenche as imagens que faltam (lista com uma posição por cena). Retorna (imagens, origens)."""
    folder = Path(folder) / "imagens_auto"
    folder.mkdir(parents=True, exist_ok=True)
    imgs = list(video.get("imagens") or [])
    imgs += [""] * (len(video["cenas"]) - len(imgs))
    ch = character_ready(video["personagens"][0] if video.get("personagens") else None)
    key = pixabay_key()
    origens = []
    poses = library.images(ch) if ch else []
    bgs = _bg_pool(ch) if ch else []
    pi = int(ch.get("imagem_indice", 0)) if ch else 0  # continue the rotation from the last video
    bi = int(ch.get("fundo_indice", 0)) if ch else 0
    used_pose = used_bg = 0
    for i, c in enumerate(video["cenas"]):
        if imgs[i] and Path(imgs[i]).exists():
            continue
        out = folder / f"cena{i + 1}.jpg"
        if c["mode"] == "fala":
            if not ch:
                raise RuntimeError(f"Cena {i + 1} (FALA) sem imagem e o personagem não está cadastrado com recorte "
                                   "e fundo. Envie cena%d.png ou cadastre o personagem." % (i + 1))
            pose, bg = poses[(pi + used_pose) % len(poses)], bgs[(bi + used_bg) % len(bgs)]
            talking_image(pose, bg["arquivo"], out, W, H, at=2.0 + 1.5 * used_bg)
            origens.append(f"Cena {i + 1}: {Path(pose).name} sobre o fundo {bg['nome']}")
            used_pose += 1
            used_bg += 1
            imgs[i] = str(out)
            continue
        got = None
        if key:
            try:
                got = pixabay_image(c.get("busca"), c.get("descricao_imagem") or c["text"], video.get("idioma", "pt"),
                                    out, key)
            except (urllib.error.URLError, OSError, ValueError) as e:
                origens.append(f"Cena {i + 1}: Pixabay falhou ({e}); usando um fundo do personagem")
        if got:
            imgs[i] = str(got[0])
            origens.append(f"Cena {i + 1}: {got[1]}")
        elif bgs:  # sem Pixabay: um quadro de outro fundo do personagem, sem pessoa
            bg = bgs[(bi + used_bg) % len(bgs)]
            _cover(_frame(bg["arquivo"], 4.0 + 1.5 * used_bg), W, H).save(out, quality=95)
            used_bg += 1
            imgs[i] = str(out)
            origens.append(f"Cena {i + 1}: quadro do fundo {bg['nome']}")
        else:
            raise RuntimeError(f"Cena {i + 1} sem imagem: envie cena{i + 1}.png, configure a chave do Pixabay ou "
                               "cadastre fundos para o personagem.")
    if ch and (used_pose or used_bg):  # next video starts on the next pose/background
        library.update_character(ch["id"], imagem_indice=pi + max(used_pose, 1), fundo_indice=bi + max(used_bg, 1))
    return imgs, origens
