"""One command: script + images -> finished video, using an approved template.

Steps: Kokoro narration -> Whisper word timing -> SadTalker for "fala" scenes -> composition.
Usage: python gerar_video.py <projeto_dir> [template.json] [pasta_saida]
  projeto_dir contains cenas.json ([{id, text, image, mode: fala|dolly|zoom}]) and the images.
  Output: outputs/videos/<projeto>/<projeto>.mp4 and a report JSON beside it.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

LAB = Path(__file__).resolve().parent.parent
SCRIPTS = LAB / "scripts"
CUTTER = Path(r"C:\dev\Video Cutter")
KOKORO_PY = CUTTER / ".runtime" / "voices" / "kokoro" / "Scripts" / "python.exe"
WHISPER_PY = CUTTER / ".venv" / "Scripts" / "python.exe"
LAB_PY = LAB / ".venvs" / "lab" / "Scripts" / "python.exe"
TORCH_LIB = CUTTER / ".runtime" / "voices" / "chatterbox" / "Lib" / "site-packages" / "torch" / "lib"
SAD_PY = LAB / ".venvs" / "sadtalker" / "Scripts" / "python.exe"
SAD_DIR = LAB / "tools" / "SadTalker"
DEFAULT_TEMPLATE = LAB / "templates" / "formato_01_personagem_falando.json"


def step(name, cmd, report, cwd=None, log=None, lab_cache=False, cudnn=False):
    print(f"-> {name}...", flush=True)
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "HF_HUB_OFFLINE": "1", "HF_HUB_DISABLE_SYMLINKS_WARNING": "1"}
    if lab_cache:  # Depth Anything lives in the lab cache; Whisper/Kokoro stay in the user's default cache
        env["HF_HOME"] = str(LAB / ".cache" / "hf")
    if cudnn:  # faster-whisper on the GPU needs cuDNN: reuse the DLLs shipped with Chatterbox's torch (read-only)
        env["PATH"] = str(TORCH_LIB) + os.pathsep + env.get("PATH", "")
    t = time.perf_counter()
    with open(log, "w", encoding="utf-8") if log else open(os.devnull, "w") as out:
        r = subprocess.run(cmd, cwd=cwd, env=env, stdout=out, stderr=subprocess.STDOUT)
    report["etapas"][name] = round(time.perf_counter() - t, 2)
    if r.returncode != 0:
        raise SystemExit(f"Falhou: {name} (veja {log})")


if __name__ == "__main__":
    proj = Path(sys.argv[1]).resolve()
    tpl_path = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else DEFAULT_TEMPLATE
    tpl = json.loads(tpl_path.read_text(encoding="utf-8"))
    scenes_file = proj / "cenas.json"
    scenes = json.loads(scenes_file.read_text(encoding="utf-8"))
    work = Path(sys.argv[3]).resolve() if len(sys.argv) > 3 else LAB / "outputs" / "videos" / proj.name
    (work / "audio").mkdir(parents=True, exist_ok=True)
    (work / "fala").mkdir(exist_ok=True)
    logs = work / "logs"
    logs.mkdir(exist_ok=True)
    report = {"projeto": proj.name, "template": tpl["id"], "inicio": time.strftime("%Y-%m-%dT%H:%M:%S"), "etapas": {}}
    t0 = time.perf_counter()

    lang = tpl.get("idioma", "pt")  # the script's language, detected by the app ("pt" or "en")
    report["idioma"] = lang
    step("voz", [str(KOKORO_PY), str(SCRIPTS / "tts_kokoro.py"), str(scenes_file), str(work / "audio"),
                 tpl["voz"]["voz"], lang], report, log=logs / "voz.log")
    step("alinhamento", [str(WHISPER_PY), str(SCRIPTS / "align_whisper.py"), str(scenes_file),
                         str(work / "audio" / "tts.json"), str(work / "audio" / "alinhamento.json"), lang],
         report, log=logs / "alinhamento.log", cudnn=True)

    fala = tpl["modos_de_cena"]["fala"]
    talking = [s for s in scenes if s["mode"] == "fala"]
    if talking:  # one SadTalker run for every talking scene: models load once, each image's face is analysed once
        jobs = {"preprocess": fala["preprocess"], "size": fala["tamanho"], "still": bool(fala["still"]),
                "enhancer": fala["realce"] or None, "cenas": []}
        for sc in talking:
            raw = work / "fala" / f"_raw_{sc['id']}"
            shutil.rmtree(raw, ignore_errors=True)
            image = Path(sc["image"]) if Path(sc["image"]).is_absolute() else LAB / sc["image"]
            jobs["cenas"].append({"id": sc["id"], "audio": str(work / "audio" / f"{sc['id']}.wav"),
                                  "imagem": str(image), "saida": str(raw)})
        jf = work / "fala" / "_sadtalker.json"
        jf.parent.mkdir(parents=True, exist_ok=True)
        jf.write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")
        step("fala", [str(SAD_PY), str(SCRIPTS / "sadtalker_lote.py"), str(jf)], report, cwd=SAD_DIR,
             log=logs / "fala.log")
        for sc in talking:
            raw = work / "fala" / f"_raw_{sc['id']}"
            shutil.move(str(sorted(raw.glob("*.mp4"))[-1]), work / "fala" / f"{sc['id']}.mp4")
            shutil.rmtree(raw, ignore_errors=True)

    out = work / f"{proj.name}.mp4"
    step("composicao", [str(LAB_PY), str(SCRIPTS / "compor_video.py"), str(tpl_path), str(scenes_file),
                        str(work), str(out)], report, log=logs / "composicao.log", lab_cache=True)
    report["total_s"] = round(time.perf_counter() - t0, 2)
    report["saida"] = str(out)
    (work / "relatorio.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Pronto em {report['total_s']} s -> {out}")
    print(json.dumps(report["etapas"], ensure_ascii=False))
