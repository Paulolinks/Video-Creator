"""T02 interview, one command: structured script -> voices per speaker -> level matching -> word timing -> video.

Usage: python gerar_entrevista.py <projeto_dir> [template.json] [pasta_saida]
  projeto_dir/roteiro.json: {personagens: {NOME: {imagem, lado, fundo, voz:{motor, voz|referencia}}}, cenas: [...]}
  Output: outputs/videos/<projeto>/<projeto>.mp4 + relatorio.json + logs/
"""
import json
import os
import shutil
import subprocess
import sys
import time
import wave
from pathlib import Path

import motor_clone

LAB = Path(__file__).resolve().parent.parent
SCRIPTS = LAB / "scripts"
CUTTER = Path(r"C:\dev\Video Cutter")
PY = {"kokoro": CUTTER / ".runtime" / "voices" / "kokoro" / "Scripts" / "python.exe",
      "whisper": CUTTER / ".venv" / "Scripts" / "python.exe", "lab": LAB / ".venvs" / "lab" / "Scripts" / "python.exe"}
DEFAULT_TEMPLATE = LAB / "templates" / "T02_entrevista.json"
TORCH_LIB = CUTTER / ".runtime" / "voices" / "chatterbox" / "Lib" / "site-packages" / "torch" / "lib"
# Same "locutor" chain as the Video Cutter, applied to every voice so both speakers sound consistent.
VOICE_FX = ("highpass=f=90,equalizer=f=150:t=q:w=1:g=2,equalizer=f=350:t=q:w=1.2:g=-3,"
            "equalizer=f=4000:t=q:w=1:g=4,acompressor=threshold=-22dB:ratio=3.5:attack=8:release=120:makeup=2,"
            "deesser=i=0.5")


# Conversation pace: a sales talk runs faster than a philosophy talk. Picked from the guests' niche/category
# (character records) unless the template sets voz.ritmo. Applied with atempo (same pitch) to every voice.
RITMOS = [
    ("rápido", 1.08, ("vend", "marketing", "negócio", "negocio", "empreend", "negocia", "lideran", "tráfego",
                      "trafego", "copywr", "persuas", "produtividade", "startup")),
    ("reflexivo", 1.0, ("filosof", "espiritual", "consciên", "conscien", "religi", "teolog", "estoic", "medita",
                        "sabedoria", "mística", "mistica", "poesia", "existencial")),
]
RITMO_PADRAO = ("natural", 1.04)


RITMOS_FILE = LAB.parent / "app" / "data" / "ritmos.json"  # the user's table (topic -> speed), edited by hand


def _guest_text(roteiro):
    """Niche/category/specialties of every speaker, from their records (item.json beside the image)."""
    text = ""
    for p in roteiro["personagens"].values():
        try:
            item = json.loads((Path(p["imagem"]).parent / "item.json").read_text(encoding="utf-8"))
        except (OSError, ValueError, KeyError):
            continue
        text += " " + " ".join(str(item.get(k, "")) for k in ("nicho", "categoria", "especialidades"))
    return text.lower()


def conversation_pace(roteiro, tpl):
    """(factor, name) for this interview: the template's voz.ritmo if set, else the first topic of ritmos.json
    whose words appear in the speakers' records, else its default."""
    fixed = tpl.get("voz", {}).get("ritmo")
    if fixed:
        return float(fixed), "definido no modelo"
    try:
        table = json.loads(RITMOS_FILE.read_text(encoding="utf-8"))
        text = _guest_text(roteiro)
        for r in table.get("ritmos", []):
            if any(w.lower() in text for w in r.get("palavras", [])):
                return round(float(r["velocidade"]), 3), r["nome"]
        d = table.get("padrao") or {}
        return round(float(d.get("velocidade", 1.0)), 3), d.get("nome", "padrão")
    except (OSError, ValueError, KeyError, TypeError):
        pass  # no table (or a typo in it): the built-in rules below
    text = ""
    for p in roteiro["personagens"].values():
        try:
            item = json.loads((Path(p["imagem"]).parent / "item.json").read_text(encoding="utf-8"))
        except (OSError, ValueError, KeyError):
            continue
        text += " " + " ".join(str(item.get(k, "")) for k in ("nicho", "categoria", "especialidades"))
    text = text.lower()
    for name, factor, words in RITMOS:  # sales first: a sales guest sets a fast talk even beside a thinker
        if any(w in text for w in words):
            return factor, name
    return RITMO_PADRAO[1], RITMO_PADRAO[0]


SAD_PY = LAB / ".venvs" / "sadtalker" / "Scripts" / "python.exe"
SAD_DIR = LAB / "tools" / "SadTalker"


def talking_faces(tpl, roteiro, merged, work, report, logs):
    """T03: one SadTalker run for every scene (models load once, each portrait's face is analysed once).
    The portrait PNG is flattened on grey (SadTalker needs RGB) at the size it is drawn; the composer puts the
    animated frames back inside the PNG's own outline. Scenes whose audio and image did not change are reused.
    A scene SadTalker cannot animate (no face found) keeps the still portrait: the video is never lost for it."""
    import hashlib
    from PIL import Image
    fala = tpl["fala"]
    fdir = work / "fala"
    (fdir / "_imgs").mkdir(parents=True, exist_ok=True)
    width = int(tpl["retrato"]["largura"])
    flat = {}
    for name, ch in roteiro["personagens"].items():
        src = Path(ch["imagem"])
        st = src.stat()
        key = hashlib.sha1(f"{src.resolve()}|{st.st_size}|{st.st_mtime}|{width}".encode()).hexdigest()[:10]
        rgb_p, rgba_p = fdir / "_imgs" / f"{key}.png", fdir / "_imgs" / f"{key}_alpha.png"
        if not (rgb_p.exists() and rgba_p.exists()):
            im = Image.open(src).convert("RGBA")
            if im.width > width:
                im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
            im = im.crop((0, 0, im.width - im.width % 2, im.height - im.height % 2))  # even size for the encoder
            im.save(rgba_p)
            grey = Image.new("RGBA", im.size, (128, 128, 128, 255))
            Image.alpha_composite(grey, im).convert("RGB").save(rgb_p)
        flat[name] = (rgb_p, rgba_p)
    by_id = {m["id"]: m for m in merged}
    jobs = {"preprocess": fala.get("preprocess", "full"), "size": int(fala.get("tamanho", 256)),
            "still": bool(fala.get("still", True)), "enhancer": fala.get("realce") or None, "pular_sem_rosto": True, "colagem_rapida": True,
            "cenas": []}
    keys = {}
    for sc in roteiro["cenas"]:
        if sc.get("animacao"):  # that scene shows an animation, not the speaker
            continue
        rgb_p, _ = flat[sc["personagem"]]
        wav = Path(by_id[sc["id"]]["wav"])
        keys[sc["id"]] = hashlib.sha1(wav.read_bytes() + rgb_p.read_bytes()[:4096] + json.dumps(jobs["preprocess"]).encode()
                                      + str(rgb_p).encode()).hexdigest()
        dst = fdir / f"{sc['id']}.mp4"
        if dst.exists() and dst.with_suffix(".key").exists() and dst.with_suffix(".key").read_text() == keys[sc["id"]]:
            continue
        raw = fdir / f"_raw_{sc['id']}"
        shutil.rmtree(raw, ignore_errors=True)
        jobs["cenas"].append({"id": sc["id"], "audio": str(wav), "imagem": str(rgb_p), "saida": str(raw)})
    report["rostos_reaproveitados"] = len(roteiro["cenas"]) - len(jobs["cenas"])
    if jobs["cenas"]:
        jf = fdir / "_sadtalker.json"
        jf.write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")
        step("fala", [str(SAD_PY), str(SCRIPTS / "sadtalker_lote.py"), str(jf)], report, logs / "fala.log")
        for job in jobs["cenas"]:
            raw = Path(job["saida"])
            got = sorted(raw.glob("*.mp4"))
            dst = fdir / f"{job['id']}.mp4"
            if got:
                shutil.move(str(got[-1]), dst)
                dst.with_suffix(".key").write_text(keys[job["id"]])
            else:
                dst.unlink(missing_ok=True)
                print(f"   {job['id']}: sem rosto animado (imagem parada nesta cena)", flush=True)
            shutil.rmtree(raw, ignore_errors=True)
    # tell the composer which clip and outline go with each scene
    for sc in roteiro["cenas"]:
        clip = fdir / f"{sc['id']}.mp4"
        sc["fala_video"] = str(clip) if clip.exists() and not sc.get("animacao") else None
        sc["fala_alpha"] = str(flat[sc["personagem"]][1])
    report["rostos_animados"] = sum(1 for sc in roteiro["cenas"] if sc.get("fala_video"))


def voice_tag(engine, voice):
    """Folder name of a voice's takes. Clones all share the name voz_referencia, so the character's folder goes in; and
    the active clone engine too, so redoing a video after switching engines doesn't reuse the other engine's takes."""
    return f"{motor_clone.ATIVO if engine == 'chatterbox' else engine}_{Path(voice).parent.name}_{Path(voice).stem}"


def step(name, cmd, report, log, lab_cache=False, cudnn=False):
    print(f"-> {name}...", flush=True)
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "HF_HUB_OFFLINE": "1", "HF_HUB_DISABLE_SYMLINKS_WARNING": "1"}
    if lab_cache:
        env["HF_HOME"] = str(LAB / ".cache" / "hf")
    if cudnn:  # faster-whisper on the GPU needs cuDNN/cuBLAS: reuse the ones shipped with Chatterbox's torch (read-only)
        env["PATH"] = str(TORCH_LIB) + os.pathsep + env.get("PATH", "")
    t = time.perf_counter()
    with open(log, "w", encoding="utf-8") as out:
        r = subprocess.run(cmd, env=env, stdout=out, stderr=subprocess.STDOUT)
    report["etapas"][name] = round(time.perf_counter() - t, 2)
    if r.returncode != 0:
        raise SystemExit(f"Falhou: {name} (veja {log})")


if __name__ == "__main__":
    proj = Path(sys.argv[1]).resolve()
    tpl_path = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else DEFAULT_TEMPLATE
    tpl = json.loads(tpl_path.read_text(encoding="utf-8"))
    roteiro_path = proj / "roteiro.json"
    roteiro = json.loads(roteiro_path.read_text(encoding="utf-8"))
    work = Path(sys.argv[3]).resolve() if len(sys.argv) > 3 else LAB / "outputs" / "videos" / proj.name
    audio, logs = work / "audio", work / "logs"
    for d in (audio, logs):
        d.mkdir(parents=True, exist_ok=True)
    lang = tpl.get("idioma", "pt")  # the script's language, detected by the app ("pt" or "en")
    report = {"projeto": proj.name, "template": tpl["id"], "idioma": lang, "inicio": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "etapas": {}}
    t0 = time.perf_counter()

    # 1. Voices, grouped by engine/voice so each model loads once.
    groups = {}
    for sc in roteiro["cenas"]:
        voz = roteiro["personagens"][sc["personagem"]]["voz"]
        key = (voz["motor"], voz.get("voz") or voz.get("referencia"))
        groups.setdefault(key, []).append({"id": sc["id"], "text": sc["text"]})
    raw = {}
    chatterbox_jobs = []  # every Chatterbox voice goes in one run: the model loads once for all speakers
    for (engine, voice), scenes in groups.items():
        tag = voice_tag(engine, voice)
        sj, out = audio / f"_cenas_{tag}.json", audio / f"raw_{tag}"
        try:
            same_text = json.loads(sj.read_text(encoding="utf-8")) == scenes
        except (OSError, ValueError):
            same_text = False
        if same_text and all((out / f"{s['id']}.wav").exists() for s in scenes):
            # retry after a later step failed: same texts and every voice file is there, so reuse them
            print(f"-> voz_{tag}: reaproveitando as vozes já geradas", flush=True)
            report["etapas"][f"voz_{tag}"] = "reaproveitada"
        elif engine == "chatterbox":
            sj.write_text(json.dumps(scenes, ensure_ascii=False), encoding="utf-8")
            chatterbox_jobs.append({"cenas": str(sj), "saida": str(out), "voz": voice, "idioma": lang})
        else:
            sj.write_text(json.dumps(scenes, ensure_ascii=False), encoding="utf-8")
            step(f"voz_{tag}", [str(PY[engine]), str(SCRIPTS / "tts_kokoro.py"), str(sj), str(out), voice, lang],
                 report, logs / f"voz_{tag}.log")
        for s in scenes:
            raw[s["id"]] = out / f"{s['id']}.wav"
    sys.path.insert(0, str(SCRIPTS))
    import idioma_voz  # each cloned voice's recording language (detected once, then read from beside the file)
    ref_langs = {}
    clone_refs = sorted({v for (e, v) in groups if e == "chatterbox"})
    if clone_refs:
        if any(idioma_voz.cached(r) is None for r in clone_refs):
            step("idioma_vozes", [str(PY["whisper"]), str(SCRIPTS / "idioma_voz.py"), *clone_refs], report,
                 logs / "idioma_vozes.log", cudnn=True)
        ref_langs = {r: idioma_voz.cached(r) for r in clone_refs}
        report["idioma_referencias"] = {Path(r).parent.name: l for r, l in ref_langs.items()}
    for j in chatterbox_jobs:
        j["idioma_ref"] = ref_langs.get(j["voz"])
    if chatterbox_jobs:
        jj = audio / "_vozes_chatterbox.json"
        jj.write_text(json.dumps(chatterbox_jobs, ensure_ascii=False), encoding="utf-8")
        step("voz_clones", [*motor_clone.comando(), "--lote", str(jj)], report, logs / "voz_clones.log")

    # 2. Treatment per engine (Kokoro voices get denoise + gate: their pauses carry hiss), same loudness, 48 kHz.
    t = time.perf_counter()
    lufs = tpl["voz"]["loudness_por_cena_lufs"]
    fx_by_engine = tpl["voz"].get("tratamento", {})
    pace, pace_name = conversation_pace(roteiro, tpl)
    report["ritmo"] = {"nome": pace_name, "fator": pace}
    print(f"   ritmo da conversa: {pace_name} ({pace}x)", flush=True)
    tempo_fx = f"atempo={pace}," if pace != 1.0 else ""  # same pitch, only faster/slower

    def treat(sc):
        dst = audio / f"{sc['id']}.wav"
        engine = roteiro["personagens"][sc["personagem"]]["voz"]["motor"]
        fx = fx_by_engine.get(engine, VOICE_FX)
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw[sc["id"]]), "-af",
                        f"{tempo_fx}{fx},loudnorm=I={lufs}:TP=-2:LRA=11,aresample=48000", "-ac", "1",
                        "-c:a", "pcm_s16le", str(dst)], check=True)
        with wave.open(str(dst)) as w:
            return {"id": sc["id"], "wav": str(dst), "duration_s": round(w.getnframes() / w.getframerate(), 3)}

    merged = [treat(sc) for sc in roteiro["cenas"]]
    (audio / "tts.json").write_text(json.dumps({"scenes": merged}, indent=2), encoding="utf-8")
    report["etapas"]["nivelamento_vozes"] = round(time.perf_counter() - t, 2)

    # 3. Word timing (text always comes from the script).
    sj = audio / "_cenas_todas.json"
    sj.write_text(json.dumps([{"id": s["id"], "text": s["text"]} for s in roteiro["cenas"]], ensure_ascii=False),
                  encoding="utf-8")
    step("alinhamento", [str(PY["whisper"]), str(SCRIPTS / "align_whisper.py"), str(sj), str(audio / "tts.json"),
                         str(audio / "alinhamento.json"), lang], report, logs / "alinhamento.log", cudnn=True)

    # 3b. Voice check: Whisper heard the narration, the script says what it should be. Babble in another language,
    # repeated words, noise/hiss between words or skipped words are found per sentence, and (Chatterbox) only those
    # sentences are synthesized again, treated, re-aligned and checked again. What is left goes to the report.
    sys.path.insert(0, str(SCRIPTS))
    import checar_voz  # noqa: E402

    by_id = {sc["id"]: sc for sc in roteiro["cenas"]}
    all_scenes = json.loads(sj.read_text(encoding="utf-8"))

    def sentence_map():
        frases = {}
        for key, scenes in groups.items():
            tag = voice_tag(*key)
            try:
                info = json.loads((audio / f"raw_{tag}" / "tts.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            for s in info["scenes"]:
                if s.get("frases"):  # sentence times of the raw take; the treated voice is `pace` times faster
                    frases[s["id"]] = [{**f, "inicio": round(f["inicio"] / pace, 3), "fim": round(f["fim"] / pace, 3)}
                                       for f in s["frases"]]
        return frases

    t = time.perf_counter()
    al_path = audio / "alinhamento.json"
    found = checar_voz.check_all(all_scenes, json.loads(al_path.read_text(encoding="utf-8")),
                                 {"scenes": merged}, sentence_map())
    report["voz_problemas_encontrados"] = sum(len(v) for v in found.values())
    print(f"-> checagem da voz: {report['voz_problemas_encontrados']} problema(s) em {len(found)} cena(s)", flush=True)
    for rodada in (1, 2):
        fixable = {}
        for (engine, voice), scenes in groups.items():
            if engine != "chatterbox":
                continue
            items = [{"id": s["id"], "text": s["text"],
                      "frases": sorted({p["frase"] for p in found[s["id"]] if "frase" in p}) or None}
                     for s in scenes if s["id"] in found]
            if items:
                fixable[(engine, voice)] = items
        if not fixable:
            break
        fix_jobs = []  # all speakers' fixes in one Chatterbox run (one model load)
        for (engine, voice), items in fixable.items():
            tag = voice_tag(engine, voice)
            rj = audio / f"_refazer_{tag}.json"
            rj.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
            for it in items:
                print(f"   {it['id']}: refazendo frase(s) {[i + 1 for i in it['frases'] or []] or 'todas'}", flush=True)
            fix_jobs.append({"cenas": str(rj), "saida": str(audio / f"raw_{tag}"), "voz": voice, "idioma": lang,
                             "refazer": True, "idioma_ref": ref_langs.get(voice)})
        jj = audio / f"_correcao_{rodada}.json"
        jj.write_text(json.dumps(fix_jobs, ensure_ascii=False), encoding="utf-8")
        step(f"correcao_{rodada}", [*motor_clone.comando(), "--lote", str(jj)], report, logs / f"correcao_{rodada}.log")
        redone = [it["id"] for items in fixable.values() for it in items]
        fresh = {sid: treat(by_id[sid]) for sid in redone}
        merged = [fresh.get(m["id"], m) for m in merged]
        (audio / "tts.json").write_text(json.dumps({"scenes": merged}, indent=2), encoding="utf-8")
        part_sj, part_out = audio / "_cenas_refeitas.json", audio / "_alinhamento_refeitas.json"
        part_sj.write_text(json.dumps([s for s in all_scenes if s["id"] in fresh], ensure_ascii=False), encoding="utf-8")
        step(f"alinhamento_correcao_{rodada}", [str(PY["whisper"]), str(SCRIPTS / "align_whisper.py"), str(part_sj),
                                                str(audio / "tts.json"), str(part_out), lang], report,
             logs / f"alinhamento_correcao_{rodada}.log", cudnn=True)
        al = json.loads(al_path.read_text(encoding="utf-8"))
        new = {s["id"]: s for s in json.loads(part_out.read_text(encoding="utf-8"))["scenes"]}
        al["scenes"] = [new.get(s["id"], s) for s in al["scenes"]]
        al_path.write_text(json.dumps(al, indent=2, ensure_ascii=False), encoding="utf-8")
        again = checar_voz.check_all(all_scenes, al, {"scenes": merged}, sentence_map(), only=set(fresh))
        found = {**{k: v for k, v in found.items() if k not in fresh}, **again}
        print(f"-> checagem da voz (rodada {rodada}): {sum(len(v) for v in found.values())} problema(s) restante(s)",
              flush=True)
    report["etapas"]["checagem_voz"] = round(time.perf_counter() - t, 2)
    report["voz_problemas"] = found  # left after the fixes; times are inside each scene

    # 3c. Talking faces (T03): SadTalker moves the speaker's mouth with the final (treated) voice of each scene.
    if tpl.get("fala"):
        talking_faces(tpl, roteiro, merged, work, report, logs)
        roteiro_path = work / "roteiro_composicao.json"  # the script plus each scene's animated face clip
        roteiro_path.write_text(json.dumps(roteiro, indent=2, ensure_ascii=False), encoding="utf-8")

    # 4. Composition.
    out = work / f"{proj.name}.mp4"
    try:  # fast composer (parallel scenes, NVENC, one final pass); the original one is the fallback
        step("composicao", [str(PY["lab"]), str(SCRIPTS / "compor_entrevista_rapido.py"), str(tpl_path),
                            str(roteiro_path), str(work), str(out)], report, logs / "composicao.log", lab_cache=True)
        cover = (tpl.get("capa") or {}).get("arquivo")
        report["capa_no_video"] = bool(cover and Path(cover).exists())  # the app skips its own cover pass
    except SystemExit:
        print("Compositor rápido falhou; usando o original.", flush=True)
        step("composicao_original", [str(PY["lab"]), str(SCRIPTS / "compor_entrevista.py"), str(tpl_path),
                                     str(roteiro_path), str(work), str(out)], report, logs / "composicao_original.log",
             lab_cache=True)
    starts = {}
    try:  # where each scene begins in the final video (the fast composer prints it)
        text = (logs / "composicao.log").read_text(encoding="utf-8", errors="replace")
        comp = json.loads(text[text.index("{"):])["scenes"]
        lead0 = tpl.get("tempo", {}).get("respiro_inicio_s", 0)  # only the first scene waits before speaking
        starts = {s["id"]: s["start_s"] + (lead0 if i == 0 else 0) for i, s in enumerate(comp)}
    except (OSError, ValueError, KeyError):
        pass
    report["voz_alertas"] = [
        {"cena": sid, "tipo": p["tipo"], "detalhe": checar_voz.describe(p), "no_video_s":
         round(starts[sid] + p["inicio"], 1) if sid in starts else None, "na_cena_s": p["inicio"]}
        for sid, probs in report["voz_problemas"].items() for p in probs]
    report["total_s"] = round(time.perf_counter() - t0, 2)
    report["saida"] = str(out)
    al = json.loads((audio / "alinhamento.json").read_text(encoding="utf-8"))
    report["alinhamento"] = {s["id"]: f"{s['matched_words']}/{s['total_words']}" for s in al["scenes"]}
    report["reconhecido"] = {s["id"]: s["recognized"] for s in al["scenes"]}
    (work / "relatorio.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Pronto em {report['total_s']} s -> {out}")
    print(json.dumps(report["etapas"], ensure_ascii=False))
    print(json.dumps(report["alinhamento"], ensure_ascii=False))
