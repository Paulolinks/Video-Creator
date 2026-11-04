"""T02 interview, one command: structured script -> voices per speaker -> level matching -> word timing -> video.

Usage: python gerar_entrevista.py <projeto_dir> [template.json] [pasta_saida]
  projeto_dir/roteiro.json: {personagens: {NOME: {imagem, lado, fundo, voz:{motor, voz|referencia}}}, cenas: [...]}
  Output: outputs/videos/<projeto>/<projeto>.mp4 + relatorio.json + logs/
"""
import json
import os
import subprocess
import sys
import time
import wave
from pathlib import Path

LAB = Path(__file__).resolve().parent.parent
SCRIPTS = LAB / "scripts"
CUTTER = Path(r"C:\dev\Video Cutter")
PY = {"kokoro": CUTTER / ".runtime" / "voices" / "kokoro" / "Scripts" / "python.exe",
      "chatterbox": CUTTER / ".runtime" / "voices" / "chatterbox" / "Scripts" / "python.exe",
      "whisper": CUTTER / ".venv" / "Scripts" / "python.exe", "lab": LAB / ".venvs" / "lab" / "Scripts" / "python.exe"}
DEFAULT_TEMPLATE = LAB / "templates" / "T02_entrevista.json"
TORCH_LIB = CUTTER / ".runtime" / "voices" / "chatterbox" / "Lib" / "site-packages" / "torch" / "lib"
# Same "locutor" chain as the Video Cutter, applied to every voice so both speakers sound consistent.
VOICE_FX = ("highpass=f=90,equalizer=f=150:t=q:w=1:g=2,equalizer=f=350:t=q:w=1.2:g=-3,"
            "equalizer=f=4000:t=q:w=1:g=4,acompressor=threshold=-22dB:ratio=3.5:attack=8:release=120:makeup=2,"
            "deesser=i=0.5")


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
    for (engine, voice), scenes in groups.items():
        tag = f"{engine}_{Path(voice).parent.name}_{Path(voice).stem}"  # clones all share the name voz_referencia
        sj, out = audio / f"_cenas_{tag}.json", audio / f"raw_{tag}"
        sj.write_text(json.dumps(scenes, ensure_ascii=False), encoding="utf-8")
        script = SCRIPTS / ("tts_kokoro.py" if engine == "kokoro" else "tts_chatterbox.py")
        step(f"voz_{tag}", [str(PY[engine]), str(script), str(sj), str(out), voice, lang], report,
             logs / f"voz_{tag}.log")
        for s in scenes:
            raw[s["id"]] = out / f"{s['id']}.wav"

    # 2. Treatment per engine (Kokoro voices get denoise + gate: their pauses carry hiss), same loudness, 48 kHz.
    t = time.perf_counter()
    lufs = tpl["voz"]["loudness_por_cena_lufs"]
    fx_by_engine = tpl["voz"].get("tratamento", {})
    merged = []
    for sc in roteiro["cenas"]:
        dst = audio / f"{sc['id']}.wav"
        engine = roteiro["personagens"][sc["personagem"]]["voz"]["motor"]
        fx = fx_by_engine.get(engine, VOICE_FX)
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw[sc["id"]]), "-af",
                        f"{fx},loudnorm=I={lufs}:TP=-2:LRA=11,aresample=48000", "-ac", "1",
                        "-c:a", "pcm_s16le", str(dst)], check=True)
        with wave.open(str(dst)) as w:
            merged.append({"id": sc["id"], "wav": str(dst), "duration_s": round(w.getnframes() / w.getframerate(), 3)})
    (audio / "tts.json").write_text(json.dumps({"scenes": merged}, indent=2), encoding="utf-8")
    report["etapas"]["nivelamento_vozes"] = round(time.perf_counter() - t, 2)

    # 3. Word timing (text always comes from the script).
    sj = audio / "_cenas_todas.json"
    sj.write_text(json.dumps([{"id": s["id"], "text": s["text"]} for s in roteiro["cenas"]], ensure_ascii=False),
                  encoding="utf-8")
    step("alinhamento", [str(PY["whisper"]), str(SCRIPTS / "align_whisper.py"), str(sj), str(audio / "tts.json"),
                         str(audio / "alinhamento.json"), lang], report, logs / "alinhamento.log", cudnn=True)

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
    report["total_s"] = round(time.perf_counter() - t0, 2)
    report["saida"] = str(out)
    al = json.loads((audio / "alinhamento.json").read_text(encoding="utf-8"))
    report["alinhamento"] = {s["id"]: f"{s['matched_words']}/{s['total_words']}" for s in al["scenes"]}
    report["reconhecido"] = {s["id"]: s["recognized"] for s in al["scenes"]}
    (work / "relatorio.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Pronto em {report['total_s']} s -> {out}")
    print(json.dumps(report["etapas"], ensure_ascii=False))
    print(json.dumps(report["alinhamento"], ensure_ascii=False))
