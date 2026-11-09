"""Characters, backgrounds and music stored under app/data (one JSON per item, files beside it)."""
import json
import os
import re
import shutil
import subprocess
import time
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw

APP = Path(__file__).resolve().parent.parent
DATA = APP / "data"
CHARS, BGS, MUSIC = DATA / "personagens", DATA / "fundos", DATA / "musicas"
VOICES = DATA / "vozes"  # character voice packs (<id>.pt + <id>.json + <id>_amostra.wav), see make_vozes.py
CLONES = VOICES / "clones"  # styled versions of the owner's voice (<id>.wav + <id>.json with tom/efeito, _amostra.wav)
KOKORO_VOICES = {"pm_alex": "Alex (masculina)", "pm_santa": "Santa (masculina, madura)", "pf_dora": "Dora (feminina)"}


def slug(text):
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_") or f"item_{int(time.time())}"


def norm_name(name):
    return slug(name).replace("_", " ")


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _items(folder):
    folder.mkdir(parents=True, exist_ok=True)
    return sorted((_read(p) for p in folder.glob("*/item.json")), key=lambda d: d["nome"].lower())


# ---------------------------------------------------------------- voices
def voices():
    """Voice id -> label. Built-in Kokoro voices by name; character packs by the path of their .pt."""
    out = dict(KOKORO_VOICES)
    own = own_voice()
    if own:  # after the built-in ones: the first entry is the new-character form's default
        out[str(own)] = "Paulo Links"
    for meta in sorted(CLONES.glob("*.json")):  # beside them: each recording's detected language, without a name
        info = _read(meta)
        if "nome" in info:
            out[str(meta.with_suffix(".wav"))] = f"{info['nome']} ({info['descricao']})"
    for meta in sorted(VOICES.glob("*.json")):
        info = _read(meta)
        out[str(meta.with_suffix(".pt"))] = f"{info['nome']} ({info['descricao']})"
    return out


def own_voice():
    """The channel owner's own recording (the only cloned voice offered in the lists), by its path."""
    return next((p for p in sorted((CHARS / "paulo").glob("voz_referencia.*"))
                 if p.suffix.lower() not in (".pt", ".json")), None)  # beside it: saved analysis and language


def voice_config(key):
    """What to save on a character for an entry of voices()."""
    if key == str(own_voice()) or Path(key).parent == CLONES:
        return {"motor": "chatterbox", "referencia": key}
    return {"motor": "kokoro", "voz": key}


def voice_sample(voz):
    if voz.get("motor") != "kokoro":  # cloned voice: play the saved reference recording
        ref = Path(voz.get("referencia") or "")
        sample = ref.with_name(ref.stem + "_amostra.wav")  # a styled version: hear the effect, not the recording
        ref = sample if sample.exists() else ref
        return str(ref) if ref.is_absolute() and ref.exists() else None
    sample = Path(voz.get("voz", "")).with_name(Path(voz.get("voz", "")).stem + "_amostra.wav")
    return str(sample) if sample.is_absolute() and sample.exists() else None


def themes():
    """Background theme key -> label (written by the catalog registration, see cadastrar_catalogo.py)."""
    path = DATA / "temas.json"
    return _read(path) if path.exists() else {}


# ---------------------------------------------------------------- characters
def characters():
    return [{**c, "amostra_voz": voice_sample(c["voz"])} for c in _items(CHARS)]


def find_character(name):
    key = norm_name(name)
    for c in characters():
        if key in [norm_name(n) for n in [c["nome"], *c.get("aliases", [])]]:
            return c
    return None


LAB = Path(r"D:\Video-Creator\VIDEO_CREATOR_LAB")
REMBG = (LAB / ".venvs" / "rembg" / "Scripts" / "python.exe", LAB / "scripts" / "remover_fundo.py")
CHATTERBOX_PY = Path(r"C:\dev\Video Cutter\.runtime\voices\chatterbox\Scripts\python.exe")


def has_transparency(path):
    """A real cut-out: most of the top and side edges are see-through (a white or painted checkerboard is not)."""
    im = Image.open(path)
    if im.mode not in ("RGBA", "LA", "P"):
        return False
    a = im.convert("RGBA").getchannel("A")
    w, h = a.size
    edge = [a.getpixel((x, 0)) for x in range(0, w, 4)]
    edge += [a.getpixel((x, y)) for y in range(0, h * 2 // 3, 4) for x in (0, w - 1)]
    return sum(v < 20 for v in edge) / len(edge) >= 0.5


def save_cutout(src, dst):
    """Save the character image as a transparent PNG, removing its background first if it has one.
    Returns True when the background was removed (the upload is kept as original.<ext> beside it)."""
    if has_transparency(src):
        Image.open(src).convert("RGBA").save(dst)
        return False
    original = Path(dst).stem.replace("recorte", "original")  # recorte.png -> original.*, recorte_2.png -> original_2.*
    shutil.copy2(src, Path(dst).with_name(original + Path(src).suffix.lower()))
    r = subprocess.run([str(REMBG[0]), "-I", str(REMBG[1]), str(src), str(dst)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    if r.returncode or not Path(dst).exists():
        Image.open(src).convert("RGBA").save(dst)  # keep the image; the card warns it still has a background
        return False
    return True


def add_character(nome, image_path, lado, fundo, voz, aliases=(), autorizacao_voz=False, voice_file=None):
    sid = slug(nome)
    folder = CHARS / sid
    folder.mkdir(parents=True, exist_ok=True)
    img = folder / "recorte.png"
    removed = save_cutout(image_path, img)
    voz = dict(voz)
    if voz.get("referencia"):  # the owner's own voice, picked from the list: nothing to copy
        autorizacao_voz = True
    elif voz["motor"] == "chatterbox":
        if not autorizacao_voz:
            raise ValueError("Para clonar uma voz é preciso confirmar a autorização do dono da voz.")
        ref = folder / ("voz_referencia" + Path(voice_file).suffix.lower())
        shutil.copy2(voice_file, ref)
        voz["referencia"] = str(ref)
        prepare_voice(ref)
    item = {"id": sid, "nome": nome.strip(), "aliases": [a.strip() for a in aliases if a.strip()],
            "imagem": str(img), "lado": lado, "fundo": fundo, "voz": voz, "autorizacao_voz": bool(autorizacao_voz),
            "transparente": has_transparency(img), "fundo_removido": removed,
            "criado_em": time.strftime("%Y-%m-%d %H:%M")}
    _write(folder / "item.json", item)
    return item


def placeholder_image(path):
    """Grey bust silhouette on a transparent background, used until the real cut-out PNG is uploaded."""
    im = Image.new("RGBA", (800, 1000), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((260, 140, 540, 460), fill=(120, 124, 135, 255))
    d.ellipse((90, 500, 710, 1260), fill=(120, 124, 135, 255))
    im.save(path)


def set_image(cid, image_path):
    folder = CHARS / cid
    img = folder / "recorte.png"
    removed = save_cutout(image_path, img)
    ch = get("personagens", cid)
    extra = [p for p in images(ch) if p != str(img)] if ch.get("imagens") else None
    return update_character(cid, imagem=str(img), transparente=has_transparency(img), imagem_provisoria=False,
                            fundo_removido=removed, imagens=[str(img), *extra] if extra is not None else None)


def images(ch):
    """The character's image rotation: the main image plus the extra ones (only files that exist)."""
    paths = ch.get("imagens") or [ch["imagem"]]
    return [p for p in paths if Path(p).exists()] or [ch["imagem"]]


def add_image(cid, image_path):
    """Extra image for the rotation (background removed like the main one)."""
    ch = get("personagens", cid)
    folder = CHARS / cid
    n = 2
    while (folder / f"recorte_{n}.png").exists():
        n += 1
    img = folder / f"recorte_{n}.png"
    save_cutout(image_path, img)
    if not has_transparency(img):
        img.unlink()
        raise ValueError("Não consegui remover o fundo desta imagem. Envie um PNG sem fundo.")
    return update_character(cid, imagens=[*images(ch), str(img)])


def remove_image(cid, path):
    ch = get("personagens", cid)
    pool = images(ch)
    if path not in pool:
        raise ValueError("Imagem não encontrada.")
    if len(pool) == 1:
        raise ValueError("O personagem precisa de pelo menos uma imagem.")
    pool.remove(path)
    if Path(path).name != "recorte.png":  # the main file is kept: "Trocar imagem" writes to it
        Path(path).unlink(missing_ok=True)
    return update_character(cid, imagens=pool, imagem=pool[0] if ch["imagem"] == path else None)


def next_image(cid):
    """Image rotation: each new video uses the next of the character's images."""
    ch = get("personagens", cid)
    pool = images(ch)
    idx = int(ch.get("imagem_indice", 0))
    if len(pool) > 1:
        update_character(cid, imagem_indice=idx + 1)
    return pool[idx % len(pool)]


def set_voice_clone(cid, voice_file):
    """Replace a character's voice with a cloned one (recording uploaded or cut from a video)."""
    folder = CHARS / cid
    for old in folder.glob("voz_referencia.*"):  # also the old saved analysis (voz_referencia.<key>.conds.pt)
        old.unlink()
    ref = folder / ("voz_referencia" + Path(voice_file).suffix.lower())
    shutil.copy2(voice_file, ref)
    prepare_voice(ref)
    return update_character(cid, voz={"motor": "chatterbox", "referencia": str(ref)}, autorizacao_voz=True)


def prepare_voice(ref):
    """Analyse a cloned voice's recording once, in the background, so videos reuse it (see tts_chatterbox.py)."""
    subprocess.Popen([str(CHATTERBOX_PY), str(LAB / "scripts" / "tts_chatterbox.py"), "--preparar", str(ref)],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "HF_HUB_OFFLINE": "1"},
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def next_background(cid):
    """Background rotation: each new video uses the next of the character's matching backgrounds."""
    ch = get("personagens", cid)
    pool = [b for b in (get("fundos", f) for f in (ch.get("fundos") or [ch.get("fundo")])) if b]
    if not pool:
        return get("fundos", ch.get("fundo", "")) or (backgrounds() or [None])[0]
    idx = int(ch.get("fundo_indice", 0))
    update_character(cid, fundo_indice=idx + 1)
    return pool[idx % len(pool)]


def next_music(cid):
    """Music rotation: each new video uses the next of the character's matching tracks (None if it has none)."""
    ch = get("personagens", cid)
    pool = [m for m in (get("musicas", i) for i in ch.get("musicas") or []) if m]
    if not pool:
        return None
    idx = int(ch.get("musica_indice", 0))
    update_character(cid, musica_indice=idx + 1)
    return pool[idx % len(pool)]


def update_character(cid, **fields):
    path = CHARS / cid / "item.json"
    item = _read(path)
    item.update({k: v for k, v in fields.items() if v is not None})
    _write(path, item)
    return item


def delete_item(kind, iid):
    folder = {"personagens": CHARS, "fundos": BGS, "musicas": MUSIC}[kind] / slug(iid)
    if folder.exists():
        shutil.rmtree(folder)


# ---------------------------------------------------------------- backgrounds and music
def backgrounds():
    return _items(BGS)


def music():
    return _items(MUSIC)


def unique_name(kind, nome):
    """A media name whose id is free (the id comes from the name: equal names used to overwrite each other)."""
    base, n, cand = nome.strip(), 2, nome.strip()
    while get(kind, slug(cand)):
        cand, n = f"{base} {n}", n + 1
    return cand


def add_media(kind, nome, source_file, origem, temas=()):
    if not origem.strip():
        raise ValueError("Informe a origem ou a licença do arquivo.")
    base = {"fundos": BGS, "musicas": MUSIC}[kind]
    nome = unique_name(kind, nome)
    sid = slug(nome)
    folder = base / sid
    folder.mkdir(parents=True, exist_ok=True)
    dst = folder / ("arquivo" + Path(source_file).suffix.lower())
    shutil.copy2(source_file, dst)
    item = {"id": sid, "nome": nome.strip(), "arquivo": str(dst), "origem": origem.strip(),
            "temas": [t for t in temas if t], "criado_em": time.strftime("%Y-%m-%d %H:%M")}
    _write(folder / "item.json", item)
    return item


def add_character_music(cid, files, origem="Enviado pelo usuário"):
    """Tracks sent on the character's card, as (path, original filename): into the library and this character's
    rotation. A file that does not decode is refused here, it would stop the video at composition. Returns
    (character, failures)."""
    added, failures = [], []
    for path, filename in files:
        ok = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-t", "1", "-f", "null", "-"],
                            capture_output=True, timeout=120).returncode == 0
        if ok:
            added.append(add_media("musicas", Path(filename).stem, path, origem)["id"])
        else:
            failures.append(f"{filename}: o arquivo de áudio não abriu")
    ch = get("personagens", cid)
    if added:
        ch = update_character(cid, musicas=[*(ch.get("musicas") or []), *added], musicas_manual=True)
    return ch, failures


def get(kind, iid):
    path = {"personagens": CHARS, "fundos": BGS, "musicas": MUSIC}[kind] / iid / "item.json"
    return _read(path) if path.exists() else None


# ---------------------------------------------------------------- first run
def seed():
    """Start with the assets already approved in the lab (Paulo, Bob Proctor and the two backgrounds)."""
    src = Path(r"D:\Video-Creator\Video-Conversa-Mentor")
    if not backgrounds() and src.exists():
        add_media("fundos", "Partículas douradas", src / "27669-365224683_medium.mp4", "Enviado pelo usuário")
        add_media("fundos", "Nuvens", src / "35573-407595474_medium.mp4", "Enviado pelo usuário")
    if not characters() and src.exists():
        add_character("Paulo", src / "Paulo Goncalves - Right side.png", "direita", "nuvens",
                      {"motor": "chatterbox"}, aliases=["Paulo Gonçalves", "Eu"], autorizacao_voz=True,
                      voice_file=r"C:\dev\Video Cutter\voice_refs\paulo_links_fixed_optimized.wav")
        add_character("Bob Proctor", src / "Bob Proctor - Left side.png", "esquerda", "particulas_douradas",
                      {"motor": "kokoro", "voz": "pm_santa"})


VIDEO_EXT = (".mp4", ".mov", ".webm", ".mkv", ".m4v")


def add_character_backgrounds(cid, files, origem="Enviado pelo usuário"):
    """files: [(path, original filename)]. Each video goes into the background library (so other characters can
    pick it too) and into this character's rotation. Returns (character, added items, failures)."""
    ch = get("personagens", cid)
    pool = list(ch.get("fundos") or ([ch["fundo"]] if ch.get("fundo") else []))
    added, failures = [], []
    for path, filename in files:
        if Path(filename).suffix.lower() not in VIDEO_EXT:
            failures.append(f"{filename}: envie um vídeo (mp4, mov, webm)")
            continue
        ok = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-t", "1", "-f", "null", "-"],
                            capture_output=True, timeout=120).returncode == 0
        if not ok:
            failures.append(f"{filename}: o arquivo de vídeo não abriu")
            continue
        label = re.sub(r"[_\-]+", " ", Path(filename).stem).strip() or "Fundo"
        item = add_media("fundos", f"{ch['nome']} - {label}"[:60], path, origem)
        added.append(item)
        pool.append(item["id"])
    if added:
        ch = update_character(cid, fundos=list(dict.fromkeys(pool)), fundo=ch.get("fundo") or added[0]["id"],
                              fundos_manual=True)
    return ch, added, failures
