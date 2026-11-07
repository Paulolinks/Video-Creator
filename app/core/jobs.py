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

from . import canais, capa, cenas_auto, estilos, library, metadados
from .parser import IDIOMAS, SCRIPT_EXT, TEMPLATES, embedded_images, episode_label, parse_script

APP = Path(__file__).resolve().parent.parent
BATCHES = library.DATA / "lotes"
LAB = Path(r"D:\Video-Creator\VIDEO_CREATOR_LAB")
ENGINE = {"F01": (LAB / "scripts" / "gerar_video.py", LAB / "templates" / "formato_01_personagem_falando.json"),
          "T02": (LAB / "scripts" / "gerar_entrevista.py", LAB / "templates" / "T02_entrevista.json"),
          # T03 = the T02 interview with the speaker's mouth moving (SadTalker) and no sound bars; same scripts
          "T03": (LAB / "scripts" / "gerar_entrevista.py", LAB / "templates" / "T03_entrevista_falando.json")}
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")
STEP_NAMES = [(r"^voz", "Gerando voz"), (r"^alinhamento", "Sincronizando legenda"),
              (r"^fala_CENA_(\d+)", "Animando rosto (cena {0})"), (r"^fala$", "Animando os rostos"), (r"^composicao", "Montando o vídeo"),
              (r"^checagem", "Conferindo a voz"), (r"^correcao", "Corrigindo trechos da voz"),
              (r"^idioma", "Identificando o idioma das vozes")]

_lock = threading.RLock()
_queue = queue.Queue()


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


def check(video):
    """Recompute problems against the current library (e.g. after registering a new character)."""
    problems = list(video["problemas_pdf"])
    video["fotos_faltando"] = []  # registered characters still on the grey placeholder: the list shows a button
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
        missing = [(i + 1, c["mode"]) for i, (c, p) in enumerate(zip(video["cenas"], imgs)) if not p]
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
                 "animacoes_total": sum(len(c.get("animacoes") or []) for c in parsed["cenas"]),
                 "status": "analisado", "etapa": "", "passos_feitos": 0, "passos_total": 0}
        if parsed["metadados"]:  # title/description/hashtags written in the script itself: the AI won't redo them
            video["metadados"] = {**parsed["metadados"], "origem": "roteiro",
                                  "atualizado": time.strftime("%d/%m/%Y %H:%M")}
        if parsed["template"] == "F01":
            video["imagens"], video["origem_imagens"] = _scene_images(pdf, files, len(parsed["cenas"]))
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
    estilos.apply(tpl, template_id, (options or {}).get("estilo"))  # format + caption look chosen on the home page
    if voice:  # F01: narrate with the registered character's voice
        tpl["voz"]["voz"] = voice
    tpl["idioma"] = idioma  # the voices and the caption timing read the script in this language
    tpl.setdefault("musica", {})
    tpl["musica"].update({"arquivo": music_item["arquivo"] if music_item else None, "volume": volume})
    tpl["musica"].setdefault("ducking", {"limiar": 0.02, "razao": 6, "ataque_ms": 20, "liberacao_ms": 500})
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
    else:
        music_item = (random.choice(musics) if choice == "aleatoria" and musics
                      else library.get("musicas", choice) if choice not in ("nenhuma", "aleatoria") else None)
    video["musica"] = music_item["nome"] if music_item else None
    video["musica_credito"] = music_item.get("origem") if music_item else None
    voice = None
    if video["template"] == "F01" and video["personagens"]:
        ch = library.find_character(video["personagens"][0])
        voice = ch["voz"]["voz"] if ch and ch["voz"]["motor"] == "kokoro" else None
    video["voz"] = voice
    # an interview script (T02) can be made with either interview model: the batch option picks it
    video["modelo"] = "T03" if video["template"] == "T02" and options.get("modelo_entrevista") == "T03" else video["template"]
    tpl = _template_copy(ENGINE[video["modelo"]][1], folder, music_item, float(options.get("volume", 0.10)), voice,
                         video.get("idioma", "pt"), video["template"], options)
    video["formato"] = estilos.resolve(options.get("estilo"))["formato"]
    if video["template"] == "F01":
        imgs = list(video["imagens"]) + [""] * (len(video["cenas"]) - len(video["imagens"]))
        scenes = [{"id": c["id"], "text": c["text"], "mode": c["mode"], "image": img,
                   "animacoes": c.get("animacoes") or []}
                  for c, img in zip(video["cenas"], imgs)]
        (folder / "cenas.json").write_text(json.dumps(scenes, indent=2, ensure_ascii=False), encoding="utf-8")
        video["capa_fonte"] = {"fundo": imgs[0]} if imgs and imgs[0] else None  # auto images: set in _run
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


def make_cover(v, out_dir, batch_id=None):
    """capa.png beside the video; a failed cover never fails the video.
    The title colour/font is picked once (the colour sequence moves on) and kept in the video, so a redo keeps it."""
    src = v.get("capa_fonte")
    if not src:
        return None
    try:
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        enc = json.loads(Path(v["template_json"]).read_text(encoding="utf-8"))["video"]
        look = v.get("capa_estilo") or capa.next_style()
        if batch_id and not v.get("capa_estilo"):
            v["capa_estilo"] = look
            _update(batch_id, v["id"], capa_estilo=look)
        return capa.make(v["titulo"] or Path(v["arquivo"]).stem, Path(out_dir) / "capa.png", src["fundo"],
                         src.get("retrato"), src.get("nome"), size=(enc["largura"], enc["altura"]),
                         serie=v.get("serie"), episodio=v.get("episodio_txt"), cor=look["cor"], fonte=look["fonte"])
    except Exception as e:  # noqa: BLE001
        print("capa:", e, file=sys.stderr)
        return None


def stamp_cover(v, video_path, cover):
    """Cover over the first second, encoded like the template; a failure keeps the video as it was."""
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
    if all(s.get("image") and Path(s["image"]).exists() for s in scenes):
        return
    _update(batch_id, v["id"], etapa="Montando as imagens das cenas")
    enc = json.loads(Path(v["template_json"]).read_text(encoding="utf-8"))["video"]
    v = {**v, "imagens": [s.get("image") or "" for s in scenes]}
    imgs, origens = cenas_auto.complete(v, v["projeto"], enc["largura"], enc["altura"])
    for s, img in zip(scenes, imgs):
        s["image"] = img
    cenas_file.write_text(json.dumps(scenes, indent=2, ensure_ascii=False), encoding="utf-8")
    fields = {"imagens": imgs, "imagens_origem": origens}
    if not v.get("capa_fonte"):
        fields["capa_fonte"] = {"fundo": imgs[0]}
    _update(batch_id, v["id"], **fields)


def _run(batch_id, video_id):
    v = next(x for x in load(batch_id)["videos"] if x["id"] == video_id)
    script, _ = ENGINE[v["template"]]
    out_dir = Path(v["projeto"]) / "saida"
    log = Path(v["projeto"]) / "execucao.log"
    _update(batch_id, video_id, status="gerando", etapa="Preparando", inicio=time.time())
    if v["template"] == "F01":
        _auto_images(batch_id, v)
        v = next(x for x in load(batch_id)["videos"] if x["id"] == video_id)  # images + cover source updated
    cover = make_cover(v, out_dir, batch_id) if v["template"] == "T02" else None
    if cover:  # T02: the composer puts the cover over the first second in its final pass (no extra encode)
        tpl = json.loads(Path(v["template_json"]).read_text(encoding="utf-8"))
        tpl["capa"] = {"arquivo": cover, "segundos": 1.0}
        Path(v["template_json"]).write_text(json.dumps(tpl, indent=2, ensure_ascii=False), encoding="utf-8")
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    done = 0
    with open(log, "w", encoding="utf-8") as lf:
        proc = subprocess.Popen([sys.executable, str(script), v["projeto"], v["template_json"], str(out_dir)],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                errors="replace", env=env, cwd=str(LAB))
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
        _update(batch_id, video_id, voz_alertas=rep.get("voz_alertas"), ritmo=rep.get("ritmo"),
                voz_corrigidos=max(0, (rep.get("voz_problemas_encontrados") or 0) - len(rep.get("voz_alertas") or [])))
        cover = cover or make_cover(v, out_dir, batch_id)
        if cover and not stamped:  # F01, or the original composer was used: stamp it afterwards
            _update(batch_id, video_id, etapa="Colocando a capa no 1º segundo", passos_feitos=done)
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
    _update(batch_id, video_id, apagado=False, capa=None, capa_no_video=False, drive=None)
    return start(batch_id, [video_id], load(batch_id).get("opcoes") or {})


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


def _worker():
    while True:
        batch_id, video_id = _queue.get()
        try:
            _run(batch_id, video_id)
        except Exception as exc:  # keep the queue alive; the error shows on the video card
            _update(batch_id, video_id, status="erro", etapa="Erro", erro=str(exc), fim=time.time())


def resume_pending():
    """Videos left 'na_fila' or 'gerando' by a previous session go back to the queue."""
    for b in batches():
        for v in b["videos"]:
            if v["status"] in ("na_fila", "gerando"):
                _update(b["id"], v["id"], status="na_fila", etapa="Aguardando (retomado)")
                _queue.put((b["id"], v["id"]))


threading.Thread(target=_worker, daemon=True).start()
