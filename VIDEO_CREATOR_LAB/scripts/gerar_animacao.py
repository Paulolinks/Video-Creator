"""Só animação (A01): script -> finished video through the animation engine (Remotion, in the guardian-studio folder).
The voice comes from the app's active clone engine (motor_clone.py), through the engine's own bridge.

Usage: gerar_animacao.py <projeto_dir> <template.json> <pasta_saida>
  projeto_dir contains roteiro.txt, written by the app.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

MOTOR = Path(r"D:\Video-Creator\guardian-studio")

if __name__ == "__main__":
    proj, out = Path(sys.argv[1]).resolve(), Path(sys.argv[3]).resolve()
    tpl = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    out.mkdir(parents=True, exist_ok=True)
    gen = MOTOR / "public" / "gen"
    for old in gen.glob("vc_*"):  # left by a video that was cancelled: the render would carry these files along
        shutil.rmtree(old, ignore_errors=True)
    job = "vc_" + hashlib.sha1(str(proj).encode()).hexdigest()[:10]
    mus = tpl.get("musica") or {}
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "GUARDIAN_ROTEIRO": str(proj / "roteiro.txt"),
           "GUARDIAN_SAIDA": str(out / f"{proj.name}.mp4"), "GUARDIAN_VOZ": tpl["voz_personagem"],
           "GUARDIAN_IDIOMA": tpl.get("idioma", "pt")}
    if mus.get("arquivo"):
        env.update(GUARDIAN_MUSICA=mus["arquivo"], GUARDIAN_VOLUME=str(mus.get("volume", 0.1)))
    if tpl.get("logo"):
        env["GUARDIAN_LOGO"] = tpl["logo"]
    print("-> voz...", flush=True)
    proc = subprocess.Popen([shutil.which("node"), "scripts/gerar.mjs", job], cwd=MOTOR, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    for line in proc.stdout:
        if "Preparando o projeto" in line:
            print("-> animacao...", flush=True)
        print(line, end="", flush=True)
    code = proc.wait()
    shutil.rmtree(gen / job, ignore_errors=True)
    sys.exit(code)
