"""Create designed Kokoro voices from recipes: pack (.pt) + settings (.json) + a sample to listen (_amostra.wav).

Run with the Kokoro runtime python (torch):
  "C:/dev/Video Cutter/.runtime/voices/kokoro/Scripts/python.exe" criar_voz.py <receitas.json> [frase da amostra]

receitas.json: {"<id>": {"nome": "...", "descricao": "...", "mistura": {"pm_alex": 0.55, "am_onyx": 0.3, ...},
                         "velocidade": 0.86, "tom": 0.9, "efeito": "catedral|divino|eterno" (optional)}}
The voices are original mixes of Kokoro voices (pt-BR base for pronunciation + other timbres); no recording of
anyone is used. They show up in the app's voice list (app/data/vozes) right away.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parent
PT = Path(r"C:\Users\paulo\.cache\huggingface\hub\models--hexgrad--Kokoro-82M\snapshots"
          r"\f3ff3571791e39611d31c381e3a41a3af07b4987\voices")
EXTRA = HERE.parent / "models" / "kokoro_voices"
OUT = Path(r"D:\Video-Creator\app\data\vozes")
FRASE = ("Tudo o que você procura já existe dentro de você. Respire, silencie a mente, e escute: "
         "eu estou em cada pensamento que escolhe a coragem.")


def load(name):
    p = PT / f"{name}.pt"
    return torch.load(p if p.exists() else EXTRA / f"{name}.pt", weights_only=True)


def main():
    recipes = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    frase = sys.argv[2] if len(sys.argv) > 2 else FRASE
    OUT.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "HF_HUB_OFFLINE": "1"}
    for vid, r in recipes.items():
        if sum(w for v, w in r["mistura"].items() if v.startswith("p")) < 0.5:
            print(f"aviso {vid}: menos de 50% de voz pt-BR, a pronúncia pode piorar")
        pack = sum(load(v) * w for v, w in r["mistura"].items()) / sum(r["mistura"].values())
        torch.save(pack, OUT / f"{vid}.pt")
        meta = {k: r[k] for k in ("nome", "descricao", "mistura", "velocidade", "tom") if k in r}
        if r.get("efeito"):
            meta["efeito"] = r["efeito"]
        (OUT / f"{vid}.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            scenes = Path(tmp) / "cenas.json"
            scenes.write_text(json.dumps([{"id": "amostra", "text": frase}], ensure_ascii=False), encoding="utf-8")
            subprocess.run([sys.executable, str(HERE / "tts_kokoro.py"), str(scenes), tmp, str(OUT / f"{vid}.pt"), "pt"],
                           check=True, env=env, stdout=subprocess.DEVNULL)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(Path(tmp) / "amostra.wav"), "-af",
                            "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "24000", str(OUT / f"{vid}_amostra.wav")],
                           check=True)
        print(f"{vid}: {r['nome']} ({r['descricao']}) -> {OUT / (vid + '_amostra.wav')}")


if __name__ == "__main__":
    main()
