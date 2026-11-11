"""Video Creator: local web app. scripts in, videos out.

Run: iniciar.bat  (or .venvs/lab python app.py) and open http://127.0.0.1:5600
"""
import json
import subprocess
import sys
import tempfile
import threading
import webbrowser
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_file, send_from_directory
from werkzeug.utils import secure_filename

from core import biblioteca_animacoes, canais, capa, estilos, gdrive, jobs, library, metadados, recorte
from core.parser import SCRIPT_EXT

APP = Path(__file__).resolve().parent
PORT = 5600
app = Flask(__name__, static_folder=str(APP / "static"), static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024**3


def err(message, code=400):
    return jsonify({"erro": message}), code


@app.get("/")
def index():
    return send_from_directory(APP / "static", "index.html")


@app.get("/media")
def media():
    """Serve a file that lives under app/data (images, videos, music, results)."""
    path = Path(request.args.get("p", "")).resolve()
    if not path.is_file() or library.DATA.resolve() not in path.parents:
        abort(404)
    return send_file(path, conditional=True)


@app.get("/api/capa")
def capa_config():
    """Cover title colour(s) and font: one colour, or a sequence that changes on every new cover."""
    return jsonify({**capa.config(), "sugeridas": capa.CORES_SUGERIDAS})


@app.post("/api/capa")
def capa_salvar():
    try:
        return jsonify({**capa.save_config(request.get_json(force=True) or {}), "sugeridas": capa.CORES_SUGERIDAS})
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400


@app.get("/api/estilos")
def estilos_lista():
    """Fonts, video formats and the default caption look for the home page."""
    return jsonify(estilos.catalog())


@app.get("/fontes/<fid>")
def fonte(fid):
    """Font file for the caption preview on the home page."""
    path = estilos.font_file(fid)
    if not path:
        abort(404)
    return send_file(path, mimetype="font/ttf", max_age=86400)


@app.get("/api/biblioteca")
def biblioteca():
    return jsonify({"personagens": library.characters(), "fundos": library.backgrounds(),
                    "musicas": library.music(), "logos": library.logos(), "vozes": library.voices(),
                    "temas": library.themes()})


@app.post("/api/personagens")
def novo_personagem():
    f = request.form
    img = request.files.get("imagem")
    if not f.get("nome", "").strip() or not img:
        return err("Informe o nome e a imagem do personagem.")
    if library.find_character(f["nome"]):
        return err("Já existe um personagem com esse nome.")
    with tempfile.TemporaryDirectory() as tmp:
        img_path = Path(tmp) / secure_filename(img.filename or "imagem.png")
        img.save(img_path)
        voice_file = None
        clip = None
        if f.get("voz_tipo") == "clonar":
            ref = request.files.get("voz_arquivo")
            clip = recorte.path(f.get("voz_recorte"))
            if ref and ref.filename:
                voice_file = Path(tmp) / secure_filename(ref.filename or "voz.wav")
                ref.save(voice_file)
            elif clip:
                voice_file = clip
            else:
                return err("Envie a gravação de referência ou recorte um trecho de vídeo (10 a 30 s de fala limpa).")
            voz = {"motor": "chatterbox"}
        else:
            voz = library.voice_config(f.get("voz_kokoro", "pm_alex"))
        try:
            item = library.add_character(f["nome"], img_path, f.get("lado", "esquerda"), f.get("fundo", ""), voz,
                                         aliases=f.get("aliases", "").split(","),
                                         autorizacao_voz=f.get("autorizacao") == "sim", voice_file=voice_file)
        except ValueError as exc:
            return err(str(exc))
        if clip:  # the clip was copied into the character folder
            clip.unlink(missing_ok=True)
    extra_bgs = [b for b in f.getlist("fundos_extra") if library.get("fundos", b)]
    fundos = list(dict.fromkeys([f.get("fundo", ""), *extra_bgs]))
    item = library.update_character(item["id"], nicho=f.get("nicho", "").strip() or None,
                                    categoria=f.get("categoria", "").strip() or None,
                                    fundos=[b for b in fundos if b] if extra_bgs else None)
    falhas = []
    novos = [u for u in request.files.getlist("fundos_novos") if u and u.filename]
    if novos:  # background videos uploaded in the form: library + this character's rotation
        with tempfile.TemporaryDirectory() as tmp:
            files = []
            for k, up in enumerate(novos):
                path = Path(tmp) / f"{k}_{secure_filename(up.filename) or 'fundo.mp4'}"
                up.save(path)
                files.append((path, up.filename))
            item, _, fail = library.add_character_backgrounds(item["id"], files)
            falhas += fail
    with tempfile.TemporaryDirectory() as tmp:  # more poses for the image rotation (background removed too)
        for k, extra in enumerate(request.files.getlist("imagens_extra")):
            if not extra or not extra.filename:
                continue
            path = Path(tmp) / f"{k}_{secure_filename(extra.filename) or 'pose.png'}"
            extra.save(path)
            try:
                item = library.add_image(item["id"], path)
            except ValueError as exc:
                falhas.append(f"{extra.filename}: {exc}")
    return jsonify({**item, "falhas_imagens": falhas})


@app.post("/api/recortar-voz")
def recortar_voz():
    d = request.get_json(force=True)
    try:
        return jsonify(recorte.cut(d.get("url"), d.get("inicio"), d.get("fim")))
    except ValueError as exc:
        return err(str(exc))
    except subprocess.TimeoutExpired:
        return err("O vídeo demorou demais para responder. Tente de novo.")


@app.patch("/api/personagens/<cid>")
def editar_personagem(cid):
    data = request.get_json(force=True)
    voz = library.voice_config(data["voz"]) if data.get("voz") in library.voices() else None
    fundos = data.get("fundos")
    if fundos is not None:
        fundos = [f for f in fundos if library.get("fundos", f)]
    musicas = data.get("musicas")
    if musicas is not None:
        musicas = [m for m in musicas if library.get("musicas", m)]
    nome = (data.get("nome") or "").strip() or None
    aliases = data.get("aliases")
    if aliases is not None:
        aliases = [a.strip() for a in aliases if a.strip()]
    for n in [nome or "", *(aliases or [])]:
        other = library.find_character(n) if n else None
        if other and other["id"] != cid:
            return jsonify({"erro": f"\"{n}\" já é usado por {other['nome']}."}), 400
    old = library.get("personagens", cid)
    library.update_character(cid, nome=nome, aliases=aliases, especialidades=data.get("especialidades"))
    pack = Path(old["voz"]["voz"]).with_suffix(".json") if old["voz"].get("voz") else None  # cloned voices have none
    if nome and pack and old["voz"]["motor"] == "kokoro" and pack.parent == library.VOICES and pack.exists():
        meta = json.loads(pack.read_text(encoding="utf-8"))
        if meta.get("nome") == old["nome"]:  # the designed voice is labelled with the character's name
            pack.write_text(json.dumps({**meta, "nome": nome}, indent=2, ensure_ascii=False), encoding="utf-8")
    return jsonify(library.update_character(cid, lado=data.get("lado"), fundo=data.get("fundo"), voz=voz,
                                            autorizacao_voz=True if voz and voz["motor"] == "chatterbox" else None,
                                            fundos=fundos, fundos_manual=True if fundos else None,
                                            musicas=musicas, musicas_manual=True if musicas is not None else None,
                                            nicho=data.get("nicho"), categoria=data.get("categoria")))


@app.post("/api/personagens/<cid>/voz")
def trocar_voz(cid):
    cid = library.slug(cid)
    if not library.get("personagens", cid):
        abort(404)
    if request.form.get("autorizacao") != "sim":
        return err("Para clonar uma voz é preciso confirmar a autorização do dono da voz.")
    ref = request.files.get("voz_arquivo")
    clip = recorte.path(request.form.get("voz_recorte"))
    with tempfile.TemporaryDirectory() as tmp:
        if ref and ref.filename:
            voice_file = Path(tmp) / secure_filename(ref.filename or "voz.wav")
            ref.save(voice_file)
        elif clip:
            voice_file = clip
        else:
            return err("Envie a gravação ou recorte um trecho de vídeo.")
        item = library.set_voice_clone(cid, voice_file)
    if clip:
        clip.unlink(missing_ok=True)
    return jsonify(item)


@app.post("/api/personagens/<cid>/imagem")
def trocar_imagem(cid):
    img = request.files.get("imagem")
    if not img or not (library.CHARS / library.slug(cid) / "item.json").exists():
        return err("Escolha a imagem (PNG sem fundo).")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / secure_filename(img.filename or "imagem.png")
        img.save(path)
        return jsonify(library.set_image(library.slug(cid), path))


@app.post("/api/personagens/<cid>/imagens")
def adicionar_imagem(cid):
    img = request.files.get("imagem")
    cid = library.slug(cid)
    if not img or not library.get("personagens", cid):
        return err("Escolha a imagem.")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / secure_filename(img.filename or "imagem.png")
        img.save(path)
        try:
            return jsonify(library.add_image(cid, path))
        except ValueError as exc:
            return err(str(exc))


@app.post("/api/personagens/<cid>/fundos")
def adicionar_fundos(cid):
    """Several background videos at once: they go to the library and into this character's rotation."""
    cid = library.slug(cid)
    if not library.get("personagens", cid):
        abort(404)
    ups = [u for u in request.files.getlist("arquivos") if u and u.filename]
    if not ups:
        return err("Escolha um ou mais vídeos de fundo.")
    with tempfile.TemporaryDirectory() as tmp:
        files = []
        for k, up in enumerate(ups):
            path = Path(tmp) / f"{k}_{secure_filename(up.filename) or 'fundo.mp4'}"
            up.save(path)
            files.append((path, up.filename))
        ch, added, failures = library.add_character_backgrounds(
            cid, files, request.form.get("origem", "").strip() or "Enviado pelo usuário")
    return jsonify({**ch, "fundos_adicionados": [a["nome"] for a in added], "falhas_fundos": failures})


@app.post("/api/personagens/<cid>/musicas")
def adicionar_musicas(cid):
    """Several tracks at once: they go to the library and into this character's rotation."""
    cid = library.slug(cid)
    if not library.get("personagens", cid):
        abort(404)
    ups = [u for u in request.files.getlist("arquivos") if u and u.filename]
    if not ups:
        return err("Escolha uma ou mais músicas.")
    with tempfile.TemporaryDirectory() as tmp:
        files = []
        for k, up in enumerate(ups):
            path = Path(tmp) / f"{k}_{secure_filename(up.filename) or 'musica.mp3'}"
            up.save(path)
            files.append((path, up.filename))
        ch, failures = library.add_character_music(cid, files)
    return jsonify({**ch, "falhas_musicas": failures})


@app.delete("/api/personagens/<cid>/imagens")
def remover_imagem(cid):
    cid = library.slug(cid)
    if not library.get("personagens", cid):
        abort(404)
    try:
        return jsonify(library.remove_image(cid, request.get_json(force=True).get("caminho", "")))
    except ValueError as exc:
        return err(str(exc))


@app.post("/api/<kind>")
def nova_midia(kind):
    if kind not in ("fundos", "musicas", "logos"):
        abort(404)
    f, up = request.form, request.files.get("arquivo")
    if not up or not f.get("nome", "").strip():
        return err("Informe o nome e o arquivo.")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / secure_filename(up.filename or "arquivo")
        up.save(path)
        if kind == "logos":
            if path.suffix.lower() not in jobs.IMAGE_EXT:
                return err("O logo precisa ser uma imagem PNG, JPG ou WEBP.")
            return jsonify(library.add_logo(f["nome"], path, f.get("origem") or "Enviado pelo usuário"))
        if kind == "musicas" and not library.audio_ok(path):
            return err(f"{up.filename}: o arquivo de áudio não abriu.")
        try:
            return jsonify(library.add_media(kind, f["nome"], path, f.get("origem", ""), f.getlist("temas")))
        except ValueError as exc:
            return err(str(exc))


@app.delete("/api/<kind>/<iid>")
def apagar(kind, iid):
    if kind not in ("personagens", "fundos", "musicas", "logos"):
        abort(404)
    library.delete_item(kind, iid)
    return jsonify({"ok": True})


@app.post("/api/lotes")
def novo_lote():
    files = request.files.getlist("arquivos")
    if not any((f.filename or "").lower().endswith(SCRIPT_EXT) for f in files):
        return err("Nenhum roteiro encontrado. Envie roteiros .txt, .md ou .pdf (e as imagens das cenas, se houver).")
    batch_id = jobs.new_batch_id()
    folder = jobs.BATCHES / batch_id / "entrada"
    saved = []
    for f in files:  # keep the folder structure so images stay next to their PDF
        rel = Path(*[secure_filename(p) or "_" for p in Path(f.filename.replace("\\", "/")).parts])
        dst = folder / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        f.save(dst)
        saved.append(dst)
    return jsonify(jobs.analyse(batch_id, saved, request.form.get("canal")))


@app.get("/api/lotes")
def lotes():
    return jsonify(jobs.batches())


@app.get("/api/lotes/<bid>")
def lote(bid):
    return jsonify(jobs.load(bid))


@app.post("/api/lotes/<bid>/reanalisar")
def reanalisar(bid):
    return jsonify(jobs.recheck(bid))


@app.post("/api/lotes/<bid>/canal")
def mudar_canal(bid):
    try:
        return jsonify(jobs.move_channel(bid, request.get_json(force=True).get("canal")))
    except ValueError as exc:
        return err(str(exc))


@app.post("/api/lotes/<bid>/iniciar")
def iniciar(bid):
    data = request.get_json(force=True)
    return jsonify(jobs.start(bid, data.get("videos", []), data.get("opcoes", {})))


@app.post("/api/lotes/<bid>/videos/<vid>/metadados")
def gerar_metadados(bid, vid):
    """The card's "Novo" button: redo the description and hashtags even when they are filled.
    ?faltando=1 (the batch's "Gerar metadados", one video at a time): fill only the empty fields."""
    return jsonify(jobs.generate_meta(bid, vid, refazer=request.args.get("faltando") != "1"))


@app.put("/api/lotes/<bid>/videos/<vid>/metadados")
def salvar_metadados(bid, vid):
    d = request.get_json(force=True)
    if not d.get("titulo", "").strip():
        return err("O título não pode ficar vazio.")
    return jsonify(jobs.save_meta(bid, vid, d["titulo"], d.get("descricao", ""), d.get("hashtags", "")))


@app.post("/api/lotes/<bid>/metadados")
def gerar_metadados_lote(bid):
    """Fill the empty description/hashtags of every ready video of the batch ('todos' redoes them all)."""
    todos = request.get_json(force=True).get("todos")
    done = []
    for v in jobs.load(bid)["videos"]:
        if v["status"] == "pronto" and (todos or jobs.missing_meta(v)):
            jobs.generate_meta(bid, v["id"], refazer=bool(todos))
            done.append(v["id"])
    return jsonify({"gerados": done})


@app.delete("/api/lotes/<bid>/videos/<vid>/arquivo")
def apagar_video(bid, vid):
    try:
        jobs.delete_file(bid, vid)
    except PermissionError:
        return err("O vídeo está aberto em algum player. Feche e tente de novo.")
    return jsonify({"ok": True})


@app.post("/api/lotes/<bid>/videos/<vid>/refazer")
def refazer_video(bid, vid):
    try:
        return jsonify(jobs.retry(bid, vid))
    except ValueError as exc:
        return err(str(exc))


@app.post("/api/lotes/<bid>/videos/<vid>/parar")
def parar_video(bid, vid):
    try:
        jobs.stop(bid, vid)
    except ValueError as exc:
        return err(str(exc))
    return jsonify({"ok": True})


@app.get("/api/animacoes")
def animacoes():
    return jsonify(biblioteca_animacoes.estado())


@app.post("/api/animacoes")
def enviar_animacoes():
    """A file with new animations: the app tests each one, renders a sample video and adds it to its library."""
    textos = []
    for f in request.files.getlist("arquivos"):
        raw = f.read()
        try:
            textos.append(raw.decode("utf-8-sig"))
        except UnicodeDecodeError:
            textos.append(raw.decode("cp1252", errors="replace"))
    try:
        biblioteca_animacoes.aprender(textos)
    except ValueError as exc:
        return err(str(exc))
    return jsonify(biblioteca_animacoes.estado())


@app.post("/api/lotes/<bid>/videos/<vid>/velocidade")
def velocidade_video(bid, vid):
    try:
        jobs.set_speed(secure_filename(bid), vid, (request.get_json(force=True) or {}).get("fator", 1))
    except (ValueError, TypeError, StopIteration) as exc:
        return err(str(exc) or "Vídeo não encontrado.")
    return jsonify({"ok": True})


@app.post("/api/lotes/<bid>/cancelar")
def cancelar_lote(bid):
    if not (jobs.BATCHES / secure_filename(bid) / "lote.json").exists():
        abort(404)
    return jsonify({"cancelados": jobs.cancel_batch(secure_filename(bid))})


@app.post("/api/fila/pausar")
def pausar_fila():
    jobs.pause()
    return jsonify({"ok": True})


@app.post("/api/fila/continuar")
def continuar_fila():
    jobs.resume()
    return jsonify({"ok": True})


@app.delete("/api/lotes/<bid>")
def apagar_lote(bid):
    if not (jobs.BATCHES / secure_filename(bid) / "lote.json").exists():
        abort(404)
    try:
        jobs.delete_batch(secure_filename(bid))
    except ValueError as exc:
        return err(str(exc))
    except PermissionError:
        return err("Algum arquivo do lote está aberto (player ou pasta). Feche e tente de novo.")
    return jsonify({"ok": True})


@app.get("/api/ia")
def ia_config():
    return jsonify({**metadados.config(), "padrao": metadados.DEFAULT_PROMPT, "modelos": metadados.models()})


@app.post("/api/ia")
def salvar_ia_config():
    d = request.get_json(force=True)
    return jsonify(metadados.save_config(d.get("modelo"), d.get("prompt")))


@app.get("/api/google")
def google_status():
    return jsonify(gdrive.status())


@app.post("/api/google/credencial")
def google_credencial():
    up = request.files.get("arquivo")
    if not up:
        return err("Escolha o arquivo credentials.json.")
    try:
        return jsonify(gdrive.save_credentials(up.read().decode("utf-8", errors="replace")))
    except ValueError as exc:
        return err(str(exc))


@app.get("/api/canais")
def canais_lista():
    return jsonify(canais.listar())


@app.post("/api/canais")
def canal_novo():
    try:
        return jsonify(canais.create(request.get_json(force=True).get("nome")))
    except ValueError as exc:
        return err(str(exc))


@app.put("/api/canais/<cid>")
def canal_editar(cid):
    try:
        return jsonify(canais.update(cid, nome=request.get_json(force=True).get("nome")))
    except ValueError as exc:
        return err(str(exc))


@app.delete("/api/canais/<cid>")
def canal_apagar(cid):
    try:
        canais.delete(cid, jobs.batches())
        return jsonify({"ok": True})
    except ValueError as exc:
        return err(str(exc))


@app.post("/api/canais/<cid>/conectar")
def google_conectar(cid):
    """First time: opens the Google login in the browser and waits for it (up to 5 minutes)."""
    try:
        return jsonify(gdrive.connect(cid, request.get_json(force=True).get("pasta", "")))
    except (ValueError, RuntimeError) as exc:
        return err(str(exc))
    except Exception as exc:  # noqa: BLE001 - Google errors, login closed or timed out
        return err(f"Não consegui conectar ao Google: {exc}")


@app.post("/api/google/desconectar")
def google_desconectar():
    return jsonify(gdrive.disconnect())


@app.post("/api/lotes/<bid>/drive")
def enviar_drive(bid):
    try:
        again = bool((request.get_json(silent=True) or {}).get("de_novo"))
        return jsonify({"enviando": gdrive.send_batch(secure_filename(bid), again)})
    except (ValueError, RuntimeError) as exc:
        return err(str(exc))


@app.post("/api/lotes/<bid>/videos/<vid>/drive")
def enviar_drive_video(bid, vid):
    """Send again one video whose upload failed (only if it was not sent yet)."""
    try:
        return jsonify({"enviando": gdrive.send_batch(secure_filename(bid), only=vid)})
    except (ValueError, RuntimeError) as exc:
        return err(str(exc))


@app.post("/api/abrir")
def abrir():
    """Open a result folder in Windows Explorer (local app only)."""
    path = Path(request.get_json(force=True).get("caminho", "")).resolve()
    if library.DATA.resolve() not in path.parents or not path.exists():
        return err("Caminho inválido.")
    subprocess.Popen(["explorer", "/select,", str(path)] if path.is_file() else ["explorer", str(path)])
    return jsonify({"ok": True})


@app.get("/api/sistema")
def sistema():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=5).stdout.strip().split(",")
        used, total = int(out[0]), int(out[1])
    except Exception:
        used = total = None
    return jsonify({"gpu_usada_mb": used, "gpu_total_mb": total, "fila_pausada": jobs.paused()})


if __name__ == "__main__":
    import socket
    with socket.socket() as s:
        running = s.connect_ex(("127.0.0.1", PORT)) == 0
    if running:  # already open (another window or started in the background): just show it
        print(f"O Video Creator já está aberto em http://127.0.0.1:{PORT}")
        if "--sem-navegador" not in sys.argv:
            webbrowser.open(f"http://127.0.0.1:{PORT}")
        sys.exit()
    library.seed()
    jobs.resume_pending()
    gdrive.clear_stale()
    if "--sem-navegador" not in sys.argv:
        threading.Timer(1.2, lambda: webbrowser.open(f"http://127.0.0.1:{PORT}")).start()
    from waitress import serve
    print(f"Video Creator em http://127.0.0.1:{PORT}  (feche esta janela para encerrar)")
    serve(app, host="127.0.0.1", port=PORT, threads=8)
