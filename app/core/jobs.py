"""Batches: analyse uploaded PDFs, build one project per video, and render them one at a time in background."""
import json
import os
import queue
import random
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil

from . import biblioteca_animacoes, canais, capa, cenas_auto, estilos, library, metadados
from .parser import CENAS_ANIMACAO, IDIOMAS, SCRIPT_EXT, TEMPLATES, embedded_images, episode_label, parse_script
from .parser import animation_source as parser_animation_source

APP = Path(__file__).resolve().parent.parent
BATCHES = library.DATA / "lotes"
LAB = Path(r"D:\Video-Creator\VIDEO_CREATOR_LAB")
ENGINE = {"F01": (LAB / "scripts" / "gerar_video.py", LAB / "templates" / "formato_01_personagem_falando.json"),
          "T02": (LAB / "scripts" / "gerar_entrevista.py", LAB / "templates" / "T02_entrevista.json"),
          # T03 = the T02 interview with the speaker's mouth moving (SadTalker) and no sound bars; same scripts
          "T03": (LAB / "scripts" / "gerar_entrevista.py", LAB / "templates" / "T03_entrevista_falando.json"),
          # A01 = animations only (no character, no captions; the engine draws its own cover): it lives in its own folder
          "A01": (LAB / "scripts" / "gerar_animacao.py", LAB / "templates" / "A01_animacao.json")}
ANIMACAO = Path(r"D:\Video-Creator\guardian-studio")
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")
STEP_NAMES = [(r"^voz", "Gerando voz"), (r"^animacao", "Montando a animação"), (r"^alinhamento", "Sincronizando legenda"),
              (r"^fala_CENA_(\d+)", "Animando rosto (cena {0})"), (r"^fala$", "Animando os rostos"), (r"^composicao", "Montando o vídeo"),
              (r"^checagem", "Conferindo a voz"), (r"^correcao", "Corrigindo trechos da voz"),
              (r"^idioma", "Identificando o idioma das vozes")]

_lock = threading.RLock()
_queue = queue.Queue()
_current = {}  # the video in the worker now: batch, video, proc (its engine), parar (cancel requested)
_paused = threading.Event()


def _path(batch_id):
    return BATCHES / batch_id / "lote.json"


def load(batch_id):
    with _lock:
        return json.loads(_path(batch_id).read_text(encoding="utf-8"))


def save(batch):
    with _lock:
        _path(batch["id"]).write_text(json.dumps(batch, indent=2, ensure_ascii=False), encoding="utf-8")


def batches():
    BATCHES.mkdir(parents=True, exist_ok=True)
    with _lock:  # never read a lote.json while save() is rewriting it
        out = [json.loads(p.read_text(encoding="utf-8")) for p in BATCHES.glob("*/lote.json")]
    return sorted(out, key=lambda b: b["id"], reverse=True)


def _scene_images(pdf, uploads, n):
    """F01 images: files named cenaN / <pdf>_cenaN in the PDF's folder; otherwise images embedded in the PDF."""
    stem = library.slug(pdf.stem)
    found = {}
    for f in uploads:
        if f.suffix.lower() not in IMAGE_EXT or f.parent != pdf.parent:
            continue
        m = re.search(r"cena[_\s-]*0*(\d+)$", library.slug(f.stem))
        if m and (library.slug(f.stem).startswith(stem) or library.slug(f.stem).startswith("cena")):
            found[int(m.group(1))] = f
    if len(found) >= n:
        return [str(found[i]) for i in range(1, n + 1)], "enviadas"
    emb = embedded_images(pdf)
    if len(emb) >= n:
        paths = []
        for i, data in enumerate(emb[:n], 1):
            p = pdf.parent / f"{pdf.stem}__cena{i}.png"
            p.write_bytes(data)
            paths.append(str(p))
        return paths, "do PDF"
    # one slot per scene; an empty slot is filled when generating (registered character / Pixabay)
    return [str(found[i]) if i in found else "" for i in range(1, n + 1)], "faltando"


def _animation_voice():
    """The character whose cloned voice narrates when the script has no VOZ: line (VOZ_PERSONAGEM in the engine's config)."""
    try:
        m = re.search(r"^\s*VOZ_PERSONAGEM\s*=\s*(\S+)", (ANIMACAO / "config.txt").read_text(encoding="utf-8"), re.M)
    except OSError:
        return None
    return library.get("personagens", m[1]) if m else None


def _missing_animation_images(video):
    missing = sorted({f for c in video["cenas"] for f in c.get("imagens", [])
                      if not (ANIMACAO / "public" / "imagens" / Path(f).name).exists()})
    return [f"Imagem '{f}' não encontrada: envie o arquivo junto com o roteiro." for f in missing]


def _check_animation(video):
    if not (ANIMACAO / "node_modules").exists():
        return ["O motor de animação não está instalado (rode instalar.bat na pasta guardian-studio)."]
    name = video["personagens"][0] if video["personagens"] else None
    ch = library.find_character(name) if name else _animation_voice()
    if name and not ch:
        return [f"Voz '{name.title()}' não encontrada: confira a linha VOZ: do roteiro."]
    if not ch or not ch["voz"].get("referencia"):
        return ["Esse personagem não tem voz clonada para narrar a animação."]
    video["personagens"], video["personagens_status"] = [ch["nome"]], {ch["nome"]: ch["id"]}
    return _missing_animation_images(video)


def check(video):
    """Recompute problems against the current library (e.g. after registering a new character)."""
    known = CENAS_ANIMACAO | {s["nome"] for s in biblioteca_animacoes.custom_scenes()}
    # an animation that was missing when the script was read may have been learned since
    problems = [p for p in video["problemas_pdf"] if not ((m := re.search(r"animação '(.+?)' não existe", p)) and m[1] in known)]
    video["fotos_faltando"] = []  # registered characters still on the grey placeholder: the list shows a button
    if video["template"] == "A01":
        problems += _check_animation(video)
    elif any(c.get("animacao") for c in video["cenas"]):
        problems += _missing_animation_images(video)
    if video["template"] == "T02":
        video["personagens_status"] = {}
        for name in video["personagens"]:
            ch = library.find_character(name)
            video["personagens_status"][name] = ch["id"] if ch else None
            if not ch:
                problems.append(f"Personagem '{name.title()}' não cadastrado.")
            elif ch.get("imagem_provisoria"):
                problems.append(f"{ch['nome']} está cadastrado, mas sem foto (só a silhueta cinza): "
                                "clique no botão abaixo para enviar o PNG.")
                video["fotos_faltando"].append({"id": ch["id"], "nome": ch["nome"]})
        if len(video["personagens"]) < 2:
            problems.append("A entrevista precisa de pelo menos dois personagens.")
    if video["template"] == "F01":
        video["personagens_status"] = {}
        for name in video["personagens"]:  # the speaker: registered (green) or the "cadastrar" button
            ch = library.find_character(name)
            video["personagens_status"][name] = ch["id"] if ch else None
            if ch and ch.get("imagem_provisoria"):
                video["fotos_faltando"].append({"id": ch["id"], "nome": ch["nome"]})
        imgs = list(video["imagens"]) + [""] * (len(video["cenas"]) - len(video["imagens"]))
        missing = [(i + 1, c["mode"]) for i, (c, p) in enumerate(zip(video["cenas"], imgs)) if not p and c["mode"] != "animacao"]
        ch = cenas_auto.character_ready(video["personagens"][0] if video["personagens"] else None)
        key = cenas_auto.pixabay_key()
        fala = [n for n, m in missing if m == "fala"]
        outras = [n for n, m in missing if m != "fala"]
        if fala and not ch:
            problems.append(f"Faltam imagens das cenas de FALA ({', '.join(map(str, fala))}). Envie cena1.png, "
                            "cena2.png... ou cadastre o personagem com imagem recortada (sem fundo) e fundos: aí o "
                            "app monta essas cenas sozinho.")
        if outras and not (key or ch):
            problems.append(f"Faltam imagens das cenas sem fala ({', '.join(map(str, outras))}). Envie as imagens "
                            "ou configure a chave do Pixabay para o app buscar sozinho.")
        auto = len(missing)
        video["imagens_resumo"] = (f"{len(imgs) - auto} enviadas" + (f" · {len(fala)} do personagem" if fala else "")
                                   + (f" · {len(outras)} {'do Pixabay' if key else 'dos fundos'}" if outras else ""))
    video["problemas"] = problems
    video["pronto_para_gerar"] = not problems
    return video


def new_batch_id():
    base = time.strftime("%Y%m%d_%H%M%S")
    n = 1
    while (BATCHES / (base if n == 1 else f"{base}_{n}")).exists():
        n += 1
    return base if n == 1 else f"{base}_{n}"


def analyse(batch_id, files, channel=None):
    """files: saved Paths (scripts + images) under the batch's 'entrada' folder. Returns the batch."""
    pdfs = [f for f in files if f.suffix.lower() in SCRIPT_EXT]
    videos = []
    for i, pdf in enumerate(pdfs, 1):
        parsed = parse_script(pdf)
        video = {"id": f"v{i:02}", "pdf": str(pdf), "arquivo": parsed["arquivo"], "template": parsed["template"],
                 "template_nome": TEMPLATES.get(parsed["template"], "Desconhecido"), "titulo": parsed["titulo"],
                 "subtitulo": parsed["subtitulo"], "idioma": parsed["idioma"], "idioma_nome": IDIOMAS[parsed["idioma"]],
                 "cenas": parsed["cenas"], "personagens": parsed["personagens"],
                 "serie": parsed.get("serie"), "episodio": parsed.get("episodio"),
                 "episodio_txt": episode_label(parsed["episodio"], parsed["idioma"]) if parsed.get("episodio") else None,
                 "problemas_pdf": parsed["problemas"], "imagens": [], "origem_imagens": "",
                 "avisos_animacao": parsed.get("avisos_animacao", []),
                 "animacoes_total": sum(len(c.get("animacoes") or []) + bool(c.get("animacao")) for c in parsed["cenas"]),
                 "status": "analisado", "etapa": "", "passos_feitos": 0, "passos_total": 0}
        if parsed["metadados"]:  # title/description/hashtags written in the script itself: the AI won't redo them
            video["metadados"] = {**parsed["metadados"], "origem": "roteiro",
                                  "atualizado": time.strftime("%d/%m/%Y %H:%M")}
        if parsed["template"] == "F01":
            video["imagens"], video["origem_imagens"] = _scene_images(pdf, files, len(parsed["cenas"]))
        named = {Path(n).name for c in parsed["cenas"] for n in c.get("imagens", [])}
        for f in files:  # images sent with the script: the scenes read them by name from the engine's folder
            if f.suffix.lower() in IMAGE_EXT and f.parent == pdf.parent and (parsed["template"] == "A01" or f.name in named):
                shutil.copy2(f, ANIMACAO / "public" / "imagens" / f.name)
        videos.append(check(video))
    batch = {"id": batch_id, "criado_em": time.strftime("%d/%m/%Y %H:%M"), "canal": channel, "videos": videos,
             "opcoes": {},
             "ignorados": [f.name for f in files if f.suffix.lower() not in (*SCRIPT_EXT, *IMAGE_EXT)]}
    (BATCHES / batch_id).mkdir(parents=True, exist_ok=True)
    save(batch)
    return batch


def recheck(batch_id):
    batch = load(batch_id)
    for v in batch["videos"]:
        if v["status"] in ("analisado", "erro"):
            check(v)
    save(batch)
    return batch


def _template_copy(template_path, folder, music_item, volume, voice=None, idioma="pt", template_id="F01", options=None):
    tpl = json.loads(Path(template_path).read_text(encoding="utf-8"))
    if template_id != "A01":  # the animation has its own look: always vertical, the words are part of it
        estilos.apply(tpl, template_id, (options or {}).get("estilo"))  # format + caption look chosen on the home page
    if voice:  # F01: narrate with the registered character's voice (designed pack or cloned recording)
        tpl["voz"]["referencia" if voice["motor"] == "chatterbox" else "voz"] = voice.get("referencia") or voice["voz"]
    tpl["idioma"] = idioma  # the voices and the caption timing read the script in this language
    tpl["capa_segundos"] = capa.SEGUNDOS  # F01 stamps the cover afterwards: the animations must wait for it to leave
    tpl.setdefault("musica", {})
    tpl["musica"].update({"arquivo": music_item["arquivo"] if music_item else None, "volume": volume})
    path = folder / "template.json"
    path.write_text(json.dumps(tpl, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _character_music(video):
    """Next track of the video's main character: the speaker in F01, the mentor (not the host) in T02."""
    status = video.get("personagens_status") or {}
    chars = [library.get("personagens", status[n]) if n in status else library.find_character(n)
             for n in video["personagens"]]
    chars = [c for c in chars if c]
    main = next((c for c in chars if c.get("nicho") != "Apresentador"), chars[0] if chars else None)
    return library.next_music(main["id"]) if main else None


def _build_project(batch, video, options):
    folder = BATCHES / batch["id"] / "videos" / f"{video['id']}_{library.slug(video['titulo'] or video['arquivo'])[:40]}"
    folder.mkdir(parents=True, exist_ok=True)
    musics = library.music()
    choice = options.get("musica", "nenhuma")
    if choice == "personagem":
        music_item = _character_music(video)
    elif choice == "animacao":
        music_item = library.next_animation_music()
    else:
        music_item = (random.choice(musics) if choice == "aleatoria" and musics
                      else library.get("musicas", choice) if choice not in ("nenhuma", "aleatoria", "animacao") else None)
    video["musica"] = music_item["nome"] if music_item else None
    video["musica_credito"] = music_item.get("origem") if music_item else None
    voice = None
    if video["template"] == "F01" and video["personagens"]:
        ch = library.find_character(video["personagens"][0])
        voice = ch["voz"] if ch else None
    video["voz"] = (voice.get("voz") or voice.get("referencia")) if voice else None
    # an interview script (T02) can be made with either interview model: the batch option picks it
    video["modelo"] = "T03" if video["template"] == "T02" and options.get("modelo_entrevista") == "T03" else video["template"]
    tpl = _template_copy(ENGINE[video["modelo"]][1], folder, music_item, float(options.get("volume", 0.10)), voice,
                         video.get("idioma", "pt"), video["template"], options)
    video["formato"] = "vertical" if video["template"] == "A01" else estilos.resolve(options.get("estilo"))["formato"]
    if video["template"] == "A01":
        (folder / "roteiro.txt").write_text(parser_animation_source(video["pdf"]), encoding="utf-8")
        logo = library.get("logos", options["logo"]) if options.get("logo") else None
        data = json.loads(tpl.read_text(encoding="utf-8"))
        data.update(logo=logo["arquivo"] if logo else None, voz_personagem=video["personagens_status"][video["personagens"][0]])
        tpl.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        video["passos_total"] = 2
    elif video["template"] == "F01":
        imgs = list(video["imagens"]) + [""] * (len(video["cenas"]) - len(video["imagens"]))
        scenes = [{"id": c["id"], "text": c["text"], "mode": c["mode"], "image": img,
                   "animacoes": c.get("animacoes") or [], "animacao": c.get("animacao")}
                  for c, img in zip(video["cenas"], imgs)]
        (folder / "cenas.json").write_text(json.dumps(scenes, indent=2, ensure_ascii=False), encoding="utf-8")
        first = next((i for i, c in zip(imgs, video["cenas"]) if c["mode"] != "animacao"), None)
        video["capa_fonte"] = {"fundo": first} if first else None  # auto images: set in _run
        video["passos_total"] = 3 + (1 if any(c["mode"] == "fala" for c in scenes) else 0)  # SadTalker: one step for all
    else:
        chars = {}
        for name in video["personagens"]:
            ch = library.get("personagens", video["personagens_status"][name])
            choice = options.get("fundos", {}).get(name) or "auto"
            bg = (library.next_background(ch["id"]) if choice == "auto" else library.get("fundos", choice))                 or library.backgrounds()[0]
            image = library.next_image(ch["id"])  # rotation when the character has more than one image
            chars[name] = {"imagem": image, "lado": ch["lado"], "fundo": bg["arquivo"], "voz": ch["voz"]}
            if ch.get("nicho") != "Apresentador" or "capa_fonte" not in video:  # the cover shows the interviewee
                video["capa_fonte"] = {"fundo": bg["arquivo"], "retrato": image, "nome": ch["nome"]}
        roteiro = {"titulo": video["titulo"], "subtitulo": video["subtitulo"], "formato": "ENTREVISTA_COM_MENTOR",
                   "personagens": chars, "cenas": video["cenas"]}
        (folder / "roteiro.json").write_text(json.dumps(roteiro, indent=2, ensure_ascii=False), encoding="utf-8")
        voices = {json.dumps(c["voz"], sort_keys=True) for c in chars.values()}
        motors = [json.loads(x).get("motor") for x in voices]
        # Chatterbox voices run in one step; + alignment, voice check and composition (fix rounds may add more)
        video["passos_total"] = ((1 if "chatterbox" in motors else 0) + motors.count("kokoro") + 3
                                 + (1 if video["modelo"] == "T03" else 0))
    return folder, tpl


def start(batch_id, video_ids, options):
    with _lock:
        batch = load(batch_id)
        batch["opcoes"] = options
        batch["canal"] = options.get("canal") or batch.get("canal")  # the channel selected when starting
        queued = []
        for v in batch["videos"]:
            if v["id"] in video_ids and v["pronto_para_gerar"] and v["status"] in ("analisado", "erro"):
                folder, tpl = _build_project(batch, v, options)
                v.update(status="na_fila", etapa="Aguardando", passos_feitos=0, projeto=str(folder),
                         template_json=str(tpl), saida=None, erro=None)
                queued.append(v["id"])
        save(batch)  # persist BEFORE queueing: the worker reads the batch from disk
    for vid in queued:
        _queue.put((batch_id, vid))
    return batch


def move_channel(batch_id, channel):
    """Move a batch to another channel: from now on its videos go to that channel's Drive folder and sheet."""
    canais.get(channel)  # raises if the channel no longer exists
    with _lock:
        batch = load(batch_id)
        if any(v.get("drive_etapa") for v in batch["videos"]):
            raise ValueError("Espere terminar o envio para o Drive antes de mudar o lote de canal.")
        batch["canal"] = channel
        for v in batch["videos"]:  # sent to the old channel's folder: count as not sent to the new one
            v.update(drive=None, drive_erro=None)
        save(batch)
    return batch


def _update(batch_id, video_id, **fields):
    with _lock:
        batch = load(batch_id)
        for v in batch["videos"]:
            if v["id"] == video_id:
                v.update(fields)
        save(batch)


def _cover_look(v, batch_id=None):
    """The cover's colour and font, kept in the video once picked."""
    look = v.get("capa_estilo") or capa.next_style()
    if batch_id and not v.get("capa_estilo"):
        v["capa_estilo"] = look
        _update(batch_id, v["id"], capa_estilo=look)
    return look


def add_series_strip(v, batch_id=None):
    """A series episode keeps its name and number on screen the whole video; a failure here never fails the video."""
    if not (v.get("serie") and v.get("episodio_txt")):
        return
    try:
        tpl = json.loads(Path(v["template_json"]).read_text(encoding="utf-8"))
        enc = tpl["video"]
        tpl["faixa_serie"] = capa.series_strip(Path(v["projeto"]) / "faixa_serie.png", (enc["largura"], enc["altura"]),
                                               v["serie"], v["episodio_txt"], _cover_look(v, batch_id)["cor"])
        if "rotulos" in tpl:  # interview: the speaker's name goes right under the strip, not against the episode tag
            tpl["rotulos"]["nome_y"] = max(tpl["rotulos"].get("nome_y", 0), 275)
        Path(v["template_json"]).write_text(json.dumps(tpl, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        print("faixa da série:", e, file=sys.stderr)


def make_cover(v, out_dir, batch_id=None):
    """capa.png beside the video; a failed cover never fails the video.
    The title colour/font is picked once (the colour sequence moves on) and kept in the video, so a redo keeps it."""
    src = v.get("capa_fonte")
    if not src:
        return None
    try:
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        enc = json.loads(Path(v["template_json"]).read_text(encoding="utf-8"))["video"]
        look = _cover_look(v, batch_id)
        return capa.make(v["titulo"] or Path(v["arquivo"]).stem, Path(out_dir) / "capa.png", src["fundo"],
                         src.get("retrato"), src.get("nome"), size=(enc["largura"], enc["altura"]),
                         serie=v.get("serie"), episodio=v.get("episodio_txt"), cor=look["cor"], fonte=look["fonte"])
    except Exception as e:  # noqa: BLE001
        print("capa:", e, file=sys.stderr)
        return None


def stamp_cover(v, video_path, cover):
    """Cover over the first seconds, encoded like the template; a failure keeps the video as it was."""
    try:
        enc = json.loads(Path(v["template_json"]).read_text(encoding="utf-8"))["video"]
        capa.stamp(video_path, cover, (enc["codec"], enc["preset"], enc["crf"]), size=(enc["largura"], enc["altura"]))
        return True
    except Exception as e:  # noqa: BLE001
        print("capa no vídeo:", e, file=sys.stderr)
        return False


def _auto_images(batch_id, v):
    """F01: scenes without an uploaded image get one now (registered character + Pixabay), before the engine."""
    cenas_file = Path(v["projeto"]) / "cenas.json"
    scenes = json.loads(cenas_file.read_text(encoding="utf-8"))
    auto_dir = (Path(v["projeto"]) / "imagens_auto").resolve()
    for s in scenes:  # a retry rebuilds the automatic images too, so the pose + moving background come back
        if s.get("image") and Path(s["image"]).resolve().parent == auto_dir:
            s["image"] = ""
            for k in ("pose", "fundo_video"):
                s.pop(k, None)
    if all(s["mode"] == "animacao" or (s.get("image") and Path(s["image"]).exists()) for s in scenes):
        return
    _update(batch_id, v["id"], etapa="Montando as imagens das cenas")
    enc = json.loads(Path(v["template_json"]).read_text(encoding="utf-8"))["video"]
    v = {**v, "imagens": [s.get("image") or "" for s in scenes]}
    imgs, origens, extras = cenas_auto.complete(v, v["projeto"], enc["largura"], enc["altura"])
    for i, (s, img) in enumerate(zip(scenes, imgs)):
        s["image"] = img
        s.update(extras.get(i, {}))  # pose layer + moving background video for the composer
    cenas_file.write_text(json.dumps(scenes, indent=2, ensure_ascii=False), encoding="utf-8")
    fields = {"imagens": imgs, "imagens_origem": origens}
    first = next((i for i in imgs if i), None)  # the cover comes from a picture: an animation scene has none
    if not v.get("capa_fonte") and first:
        fields["capa_fonte"] = {"fundo": first}
    _update(batch_id, v["id"], **fields)


def _file_name(v):
    """A01 output: 'dia07 - Title', so a folder sorted by name is already in publishing order."""
    stem = Path(v["arquivo"]).stem
    m = re.match(r"dia[\s_-]*(\d+)", stem, re.I)
    tag = f"dia{int(m[1]):02}" if m else stem
    title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", v["titulo"] or "").strip().rstrip(".")[:90].strip()
    return f"{tag} - {title}" if title else tag


def _run(batch_id, video_id):
    v = next(x for x in load(batch_id)["videos"] if x["id"] == video_id)
    script, _ = ENGINE[v["template"]]
    out_dir = Path(v["projeto"]) / "saida"
    log = Path(v["projeto"]) / "execucao.log"
    _update(batch_id, video_id, status="gerando", etapa="Preparando", inicio=time.time())
    if v["template"] == "F01":
        _auto_images(batch_id, v)
        v = next(x for x in load(batch_id)["videos"] if x["id"] == video_id)  # images + cover source updated
    add_series_strip(v, batch_id)
    if v["template"] == "A01":  # here, not when the project is built: videos already in the queue get it too
        tpl = json.loads(Path(v["template_json"]).read_text(encoding="utf-8"))
        tpl["nome_arquivo"] = _file_name(v)
        Path(v["template_json"]).write_text(json.dumps(tpl, indent=2, ensure_ascii=False), encoding="utf-8")
    cover = make_cover(v, out_dir, batch_id) if v["template"] == "T02" else None
    if cover:  # T02: the composer puts the cover over the first seconds in its final pass (no extra encode)
        tpl = json.loads(Path(v["template_json"]).read_text(encoding="utf-8"))
        tpl["capa"] = {"arquivo": cover, "segundos": capa.SEGUNDOS}
        Path(v["template_json"]).write_text(json.dumps(tpl, indent=2, ensure_ascii=False), encoding="utf-8")
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    done = 0
    _wait_if_paused()
    if _current.get("parar"):
        return
    with open(log, "w", encoding="utf-8") as lf:
        proc = subprocess.Popen([sys.executable, str(script), v["projeto"], v["template_json"], str(out_dir)],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                errors="replace", env=env, cwd=str(LAB))
        _current["proc"] = proc
        if _paused.is_set():  # asked in the instant before the engine existed
            _on_tree("suspend")
        if _current.get("parar"):
            _on_tree("kill")
        for line in proc.stdout:
            lf.write(line)
            lf.flush()
            if line.startswith("-> "):
                step = line[3:].strip().rstrip(".")
                label = step
                for pattern, name in STEP_NAMES:
                    m = re.match(pattern, step)
                    if m:
                        label = name.format(*m.groups())
                        break
                _update(batch_id, video_id, etapa=label, passos_feitos=done)
                done += 1
        proc.wait()
    outputs = sorted(out_dir.glob("*.mp4"))
    if proc.returncode == 0 and outputs:
        report = out_dir / "relatorio.json"
        rep = json.loads(report.read_text(encoding="utf-8")) if report.exists() else {}
        stamped = rep.get("capa_no_video", False)
        # voice check (T02): defects found in the narration, and what is still left after the automatic fix
        extra = out_dir / "avisos_animacao.json"
        if extra.exists():  # an animation scene that could not be drawn: the video is fine, the card says what happened
            _update(batch_id, video_id, avisos_animacao=[*v.get("avisos_animacao", []), *json.loads(extra.read_text(encoding="utf-8"))])
        _update(batch_id, video_id, voz_alertas=rep.get("voz_alertas"), ritmo=rep.get("ritmo"),
                voz_corrigidos=max(0, (rep.get("voz_problemas_encontrados") or 0) - len(rep.get("voz_alertas") or [])))
        if v["template"] == "A01":  # drawn by the engine, which also shows it on the first frames
            biblioteca_animacoes.sync()
            cover, stamped = (str(out_dir / "capa.png"), True) if (out_dir / "capa.png").exists() else (None, False)
        cover = cover or make_cover(v, out_dir, batch_id)
        if cover and not stamped:  # F01, or the original composer was used: stamp it afterwards
            _update(batch_id, video_id, etapa="Colocando a capa no início do vídeo", passos_feitos=done)
            stamped = stamp_cover(v, outputs[-1], cover)
        _update(batch_id, video_id, status="pronto", etapa="Pronto", passos_feitos=done, saida=str(outputs[-1]),
                capa=cover, capa_no_video=stamped, fim=time.time())
        try:  # fill the description/hashtags the script didn't bring; the card can regenerate them later
            generate_meta(batch_id, video_id)
        except Exception as e:  # noqa: BLE001
            print("metadados:", e, file=sys.stderr)
    else:
        tail = log.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-3:]
        _update(batch_id, video_id, status="erro", etapa="Erro", erro=" | ".join(tail), fim=time.time())


def get_video(batch_id, video_id):
    return next(v for v in load(batch_id)["videos"] if v["id"] == video_id)


META_FIELDS = ("descricao", "hashtags")


def missing_meta(v):
    meta = v.get("metadados") or {}
    return [k for k in META_FIELDS if not (meta.get(k) or "").strip()]


def generate_meta(batch_id, video_id, refazer=False):
    """AI description + hashtags; the post title starts as the script's title (also on the cover).
    Only the empty fields are filled; refazer=True (the card's "Novo" button) redoes both. A field that already
    has text is never replaced by the no-AI fallback text."""
    v = get_video(batch_id, video_id)
    old = v.get("metadados") or {}
    meta = dict(old)
    todo = list(META_FIELDS) if refazer else missing_meta(v)
    if todo:
        ai = metadados.generate(v)
        changed = [k for k in todo if ai["origem"] == "ia" or not (old.get(k) or "").strip()]
        for k in changed:
            meta[k] = ai[k]
        meta.pop("aviso", None)
        if ai["origem"] == "local":
            meta["aviso"] = ai.get("aviso", "")
        if changed:
            meta.update(origem=ai["origem"], modelo=ai["modelo"])
    title = old.get("titulo") or v["titulo"] or Path(v["arquivo"]).stem
    meta.update(titulo=title, atualizado=time.strftime("%d/%m/%Y %H:%M"))
    _update(batch_id, video_id, metadados=meta)
    return meta


def save_meta(batch_id, video_id, titulo, descricao, hashtags):
    meta = {**(get_video(batch_id, video_id).get("metadados") or {}), "titulo": titulo.strip(),
            "descricao": descricao.strip(), "hashtags": metadados.clean_hashtags(hashtags),
            "atualizado": time.strftime("%d/%m/%Y %H:%M"), "editado": True}
    meta.pop("aviso", None)
    _update(batch_id, video_id, metadados=meta)
    return meta


def retry(batch_id, video_id):
    """Render one video again (after an error, or to redo it) with the batch's options; its metadata is kept."""
    with _lock:
        batch = load(batch_id)
        v = next(x for x in batch["videos"] if x["id"] == video_id)
        if v["status"] in ("na_fila", "gerando"):
            raise ValueError("Esse vídeo já está na fila.")
        check(v)
        if not v["pronto_para_gerar"]:
            raise ValueError("Resolva antes: " + " ".join(v["problemas"]))
        v["status"] = "analisado"
        save(batch)
    (Path(v.get("projeto") or ".") / ORIGINAL_VELOCIDADE).unlink(missing_ok=True)  # a new render starts at its own speed
    _update(batch_id, video_id, apagado=False, capa=None, capa_no_video=False, drive=None, velocidade=None)
    return start(batch_id, [video_id], load(batch_id).get("opcoes") or {})


VELOCIDADE_MIN, VELOCIDADE_MAX = 0.75, 1.5
ORIGINAL_VELOCIDADE = "velocidade_original.mp4"  # in the project folder, never in saida (the app takes the .mp4 it finds there)


def set_speed(batch_id, video_id, fator):
    """Re-encodes the finished video at this speed (voice keeps its pitch). The first change keeps the original render,
    and every later change starts from it: 1.0 brings the original back."""
    fator = round(float(fator), 2)
    if not VELOCIDADE_MIN <= fator <= VELOCIDADE_MAX:
        raise ValueError(f"Escolha uma velocidade entre {VELOCIDADE_MIN} e {VELOCIDADE_MAX}.")
    v = get_video(batch_id, video_id)
    if v["status"] != "pronto" or v.get("apagado") or not v.get("saida") or not Path(v["saida"]).exists():
        raise ValueError("Esse vídeo não está pronto (ou o arquivo foi apagado).")
    out, orig = Path(v["saida"]), Path(v["projeto"]) / ORIGINAL_VELOCIDADE
    if not orig.exists():
        if fator == 1:
            _update(batch_id, video_id, velocidade=1.0)
            return
        shutil.copy2(out, orig)
    tmp = out.with_name("_velocidade.mp4")
    if fator == 1:
        shutil.copy2(orig, tmp)
    else:
        base = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(orig), "-vf", f"setpts=PTS/{fator}",
                "-af", f"atempo={fator}", "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
        for enc in (["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "19", "-b:v", "0"],
                    ["-c:v", "libx264", "-preset", "fast", "-crf", "18"]):  # no NVIDIA encoder: the CPU one
            if subprocess.run([*base, *enc, str(tmp)], capture_output=True).returncode == 0:
                break
        else:
            tmp.unlink(missing_ok=True)
            raise ValueError("Não consegui mudar a velocidade deste vídeo.")
    for _ in range(20):  # the page may still be reading the old file for a moment
        try:
            tmp.replace(out)
            break
        except PermissionError:
            time.sleep(0.5)
    else:
        tmp.unlink(missing_ok=True)
        raise ValueError("O vídeo está aberto em outro programa. Feche e tente de novo.")
    _update(batch_id, video_id, velocidade=fator)


def delete_batch(batch_id):
    """Delete the whole batch folder (scripts, projects and videos)."""
    if any(v["status"] in ("na_fila", "gerando") for v in load(batch_id)["videos"]):
        raise ValueError("Esse lote ainda tem vídeos na fila. Espere terminar.")
    shutil.rmtree(BATCHES / batch_id)


def delete_file(batch_id, video_id):
    """Delete only the final .mp4 (the biggest file); the cover, metadata and project files stay."""
    v = get_video(batch_id, video_id)
    if v.get("saida"):
        Path(v["saida"]).unlink(missing_ok=True)
    _update(batch_id, video_id, apagado=True)


def _tree():
    """The running video's engine and everything it started, parents first."""
    try:
        root = psutil.Process(_current["proc"].pid)
        return [root, *root.children(recursive=True)]
    except (KeyError, AttributeError, psutil.Error):
        return []


def _on_tree(action):
    for p in _tree():
        try:
            getattr(p, action)()
        except psutil.Error:
            pass


def paused():
    return _paused.is_set()


def pause():
    """Freeze everything: the video being made stops where it is and the next one doesn't start."""
    _paused.set()
    _on_tree("suspend")


def resume():
    _paused.clear()
    _on_tree("resume")


def stop(batch_id, video_id):
    """Cancel the video being made (it goes back to 'not started'); the queue moves on to the next one."""
    if (_current.get("batch"), _current.get("video")) != (batch_id, video_id):
        raise ValueError("Esse vídeo não está sendo criado agora.")
    _current["parar"] = True
    _on_tree("kill")


def cancel_batch(batch_id):
    """Stop the batch's running video and take the rest out of the queue; finished videos stay."""
    with _lock:
        batch = load(batch_id)
        running = _current.get("video") if _current.get("batch") == batch_id else None
        waiting = [v for v in batch["videos"] if v["status"] in ("na_fila", "gerando") and v["id"] != running]
        for v in waiting:  # the worker skips their queue entries
            v.update(status="analisado", etapa="", erro=None, passos_feitos=0, fim=None)
        save(batch)
        if running:
            _current["parar"] = True
            _on_tree("kill")
    if _paused.is_set() and not any(v["status"] in ("na_fila", "gerando")
                                    for b in batches() if b["id"] != batch_id for v in b["videos"]):
        resume()  # a pause with nothing left to hold would freeze the next batch
    return len(waiting) + bool(running)


def _still_queued(batch_id, video_id):
    """False for an entry left by a cancelled or deleted batch."""
    try:
        return get_video(batch_id, video_id)["status"] == "na_fila"
    except (OSError, StopIteration):
        return False


def _wait_if_paused():
    while _paused.is_set():
        time.sleep(0.5)


def _worker():
    while True:
        batch_id, video_id = _queue.get()
        _wait_if_paused()
        with _lock:  # one check with the claim, so a cancel can't land between them
            if not _still_queued(batch_id, video_id):
                continue
            _current.update(batch=batch_id, video=video_id, proc=None, parar=False)
        try:
            _run(batch_id, video_id)
        except Exception as exc:  # keep the queue alive; the error shows on the video card
            _update(batch_id, video_id, status="erro", etapa="Erro", erro=str(exc), fim=time.time())
        if _current["parar"]:
            _update(batch_id, video_id, status="analisado", etapa="", erro=None, passos_feitos=0, fim=None)
        _current.clear()


def resume_pending():
    """Videos left 'na_fila' or 'gerando' by a previous session go back to the queue."""
    for b in batches():
        for v in b["videos"]:
            if v["status"] in ("na_fila", "gerando"):
                _update(b["id"], v["id"], status="na_fila", etapa="Aguardando (retomado)")
                _queue.put((b["id"], v["id"]))


biblioteca_animacoes.sync()
threading.Thread(target=_worker, daemon=True).start()
