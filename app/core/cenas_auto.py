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


def _duration(path):
    """Seconds of a video, read from ffmpeg's banner (None if it can't be read)."""
    err = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path)], capture_output=True, text=True, encoding="utf-8",
                         errors="replace", timeout=60).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else None


def _frame(path, at=None):
    """Imagem do fundo: o arquivo, ou um quadro do vídeo (variando o instante para não repetir)."""
    path = Path(path)
    if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
        return Image.open(path).convert("RGB")
    at = at or 2
    seconds = _duration(path)
    if seconds:  # a short video wraps around: asking for a moment past its end makes ffmpeg fail and stops the whole video
        at = round(at % max(seconds - 0.5, 0.5), 1)
    out = path.parent / f"_quadro_{int(at * 10)}.jpg"
    if not out.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{at:.1f}", "-i", str(path), "-frames:v", "1",
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
    # the pose alone on a transparent frame: the composer puts it over the MOVING background video (the still
    # composite below is only what SadTalker needs to find and animate the face)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    layer.alpha_composite(p, (x, H - p.height))
    out = Path(out)
    layer.save(out.with_name(out.stem + "_pose.png"))
    bg.alpha_composite(layer)
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
        words = busca.replace(",", " ").split()[:4]
        out += [(" ".join(words), "en"), (" ".join(words[:3]), "en"), (" ".join(words[1:]), "en")]
        out += [(f"{a} {b}", "en") for a, b in zip(words, words[1:])]  # neighbour pairs: "customers waiting"...
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
    queries = _queries(busca, descricao, idioma)
    # every result is scored against ALL the words of the scene's search (not only the shortened query): a photo
    # must show at least half of them in its tags/title, otherwise a shorter query is tried (2026-11-07: a phone
    # alone came for "worried employee smartphone office", cupcakes for "bakery customers waiting line")
    first = queries[0][0] if queries else ""
    words = {w.lower()[:5] for w in re.findall(r"[\wÀ-ú]+", first) if len(w) > 2}
    need = max(1, -(-len(words) // 2))

    def score(h):
        tokens = re.split(r"[,\s\-/]+", (h.get("tags", "") + " " + h.get("pageURL", "")).lower())
        return sum(any(t.startswith(w) for t in tokens if t) for w in words)

    fallback = None
    for q, lang in queries:
        for orient in ("vertical", "all"):
            params = {"key": key, "q": q[:100], "lang": lang, "image_type": "photo", "orientation": orient,
                      "safesearch": "true", "per_page": 50, "order": "popular"}
            with _get(f"{API}?{urllib.parse.urlencode(params)}") as r:
                hits = json.loads(r.read().decode("utf-8")).get("hits", [])
            hits = [h for h in hits if h.get("largeImageURL") and max(h["imageWidth"], h["imageHeight"]) >= 1200]
            fresh = [h for h in hits if h["id"] not in used] or hits
            if not fresh:
                continue
            best = max(score(h) for h in fresh)
            pick = random.choice([x for x in fresh if score(x) == best][:3])
            if best >= need:
                return _baixar(pick, q, out, used)
            if fallback is None or best > fallback[0]:
                fallback = (best, pick, q)
    return _baixar(fallback[1], fallback[2], out, used) if fallback else None


def _baixar(h, q, out, used):
    with _get(h["largeImageURL"], 60) as r:
        Path(out).write_bytes(r.read())
    used.add(h["id"])
    USED_FILE.write_text(json.dumps(sorted(used)[-3000:]), encoding="utf-8")
    return out, f"Pixabay #{h['id']} ({h['pageURL']}), busca \"{q}\""


class Fila:
    """A character's rotation queue (poses or backgrounds), saved in the character so every scene takes the NEXT
    item and the next video continues where this one stopped. All items are used before any repeats; each new
    round is shuffled and never starts with the item that ended the previous round. Items added in the middle
    of a round join the end of the current queue; removed ones leave it."""

    def __init__(self, ch, field, items, key=lambda x: x):
        self.ch, self.field, self.key = ch, field, key
        self.by_id = {key(x): x for x in items}
        state = (ch or {}).get(field) or {}
        self.queue = [i for i in state.get("fila", []) if i in self.by_id]
        self.round = [i for i in state.get("usados", []) if i in self.by_id]  # used in the current round
        self.last = state.get("ultimo")
        self.queue += [i for i in self.by_id if i not in self.queue and i not in self.round]  # new items
        self.taken = 0

    def next(self):
        if not self.queue:
            self.queue = list(self.by_id)
            random.shuffle(self.queue)
            if len(self.queue) > 1 and self.queue[0] == self.last:
                self.queue.append(self.queue.pop(0))
            self.round = []
        item = self.queue.pop(0)
        self.round.append(item)
        self.last = item
        self.taken += 1
        return self.by_id[item]

    def state(self):
        return {"fila": self.queue, "usados": self.round, "ultimo": self.last}


def complete(video, folder, W, H):
    """Preenche as imagens que faltam (lista com uma posição por cena). Retorna (imagens, origens, extras):
    extras[i] = {"pose": camada da pose sem fundo, "fundo_video": vídeo do fundo} nas cenas de FALA montadas."""
    folder = Path(folder) / "imagens_auto"
    folder.mkdir(parents=True, exist_ok=True)
    imgs = list(video.get("imagens") or [])
    imgs += [""] * (len(video["cenas"]) - len(imgs))
    ch = character_ready(video["personagens"][0] if video.get("personagens") else None)
    key = pixabay_key()
    origens, extras = [], {}
    # rotation queues saved in the character: each scene takes the next pose/background, the next video goes on
    poses = Fila(ch, "fila_poses", library.images(ch)) if ch else None
    bgs = Fila(ch, "fila_fundos", _bg_pool(ch), key=lambda b: b["id"]) if ch else None
    for i, c in enumerate(video["cenas"]):
        if (imgs[i] and Path(imgs[i]).exists()) or c["mode"] == "animacao":  # the animation engine draws that scene
            continue
        out = folder / f"cena{i + 1}.jpg"
        if c["mode"] == "fala":
            if not ch:
                raise RuntimeError(f"Cena {i + 1} (FALA) sem imagem e o personagem não está cadastrado com recorte "
                                   "e fundo. Envie cena%d.png ou cadastre o personagem." % (i + 1))
            pose, bg = poses.next(), bgs.next()
            talking_image(pose, bg["arquivo"], out, W, H, at=2.0 + 1.5 * bgs.taken)
            extras[i] = {"pose": str(out.with_name(out.stem + "_pose.png"))}
            if Path(bg["arquivo"]).suffix.lower() in library.VIDEO_EXT:  # the scene's background keeps moving
                extras[i]["fundo_video"] = bg["arquivo"]
            origens.append(f"Cena {i + 1}: {Path(pose).name} sobre o fundo {bg['nome']}")
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
        elif bgs and bgs.by_id:  # sem Pixabay: um quadro do próximo fundo do personagem, sem pessoa
            bg = bgs.next()
            _cover(_frame(bg["arquivo"], 4.0 + 1.5 * bgs.taken), W, H).save(out, quality=95)
            imgs[i] = str(out)
            origens.append(f"Cena {i + 1}: quadro do fundo {bg['nome']}")
        else:
            raise RuntimeError(f"Cena {i + 1} sem imagem: envie cena{i + 1}.png, configure a chave do Pixabay ou "
                               "cadastre fundos para o personagem.")
    if ch and (poses.taken or bgs.taken):  # the next video continues these queues
        library.update_character(ch["id"], fila_poses=poses.state(), fila_fundos=bgs.state())
    return imgs, origens, extras
