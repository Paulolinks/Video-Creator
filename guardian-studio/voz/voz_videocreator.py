"""Ponte entre o Guardian Studio e a voz clonada do Video Creator.

Usa os motores do Video Creator só para leitura: o motor de voz ativo (motor_clone.py) e o alinhamento por palavra
(align_whisper.py). Tudo que esta ponte grava fica dentro do guardian-studio.

Uso: voz_videocreator.py <entrada.json> <pasta_saida>
  entrada.json: {"voz": "<id do personagem>", "linhas": ["texto 1", ...]}
  saída: 01.wav, 02.wav... e resultado.json = [{"audio": "01.wav", "duration": 2.3, "words": [{"w": "Hello", "t": 0.05}]}]
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # importar motor_clone não pode criar __pycache__ no Video Creator

RAIZ = Path(__file__).resolve().parent.parent
TRABALHO = RAIZ / "voz" / "_trabalho"
VC = Path(r"D:\Video-Creator")
SCRIPTS = VC / "VIDEO_CREATOR_LAB" / "scripts"
PERSONAGENS = VC / "app" / "data" / "personagens"
CUTTER = Path(r"C:\dev\Video Cutter")
WHISPER_PY = CUTTER / ".venv" / "Scripts" / "python.exe"
TORCH_LIB = CUTTER / ".runtime" / "voices" / "chatterbox" / "Lib" / "site-packages" / "torch" / "lib"  # cuDNN do Whisper
IDIOMA = "en"
LOUDNORM = "loudnorm=I=-14:TP=-1.5:LRA=11"  # volume final dos vídeos do Video Creator (-14 LUFS)

sys.path.insert(0, str(SCRIPTS))
import motor_clone  # noqa: E402


def referencia(personagem):
    """Gravação da voz clonada do personagem cadastrado no Video Creator."""
    item = PERSONAGENS / personagem / "item.json"
    if not personagem or not item.exists():
        sys.exit(f"Personagem '{personagem}' não encontrado em {PERSONAGENS}. Confira VOZ_PERSONAGEM no config.txt.")
    ref = json.loads(item.read_text(encoding="utf-8")).get("voz", {}).get("referencia")
    if not ref or not Path(ref).exists():
        sys.exit(f"O personagem '{personagem}' não tem gravação de voz clonada.")
    return ref


def rodar(nome, comando, log, caminho_extra=None):
    print(f"  {nome}...", flush=True)
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "HF_HUB_OFFLINE": "1", "HF_HUB_DISABLE_SYMLINKS_WARNING": "1"}
    if caminho_extra:
        env["PATH"] = str(caminho_extra) + os.pathsep + env.get("PATH", "")
    with open(log, "w", encoding="utf-8") as out:
        r = subprocess.run(comando, stdout=out, stderr=subprocess.STDOUT, env=env, cwd=str(log.parent), check=False)
    if r.returncode != 0:
        fim = log.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-5:]
        sys.exit(f"{nome} falhou (código {r.returncode}):\n" + "\n".join(fim))


if __name__ == "__main__":
    pedido = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    saida = Path(sys.argv[2]).resolve()
    linhas = pedido["linhas"]
    IDIOMA = pedido.get("idioma") or IDIOMA  # o Video Creator envia o idioma do roteiro
    if not all(t.strip() for t in linhas):
        sys.exit("O roteiro tem uma linha FALA: vazia.")
    voz = referencia(pedido.get("voz", ""))

    work = TRABALHO / saida.name
    shutil.rmtree(work, ignore_errors=True)
    audio = work / "audio"
    audio.mkdir(parents=True)
    cenas = [{"id": f"{i:02}", "text": t} for i, t in enumerate(linhas, 1)]
    cenas_json, tts_json, alinhamento_json = work / "cenas.json", audio / "tts.json", audio / "alinhamento.json"
    cenas_json.write_text(json.dumps(cenas, indent=2, ensure_ascii=False), encoding="utf-8")

    rodar("gerando a voz clonada", [*motor_clone.comando(), str(cenas_json), str(audio), voz, IDIOMA], work / "voz.log")
    rodar("sincronizando as palavras", [str(WHISPER_PY), str(SCRIPTS / "align_whisper.py"), str(cenas_json), str(tts_json),
                                        str(alinhamento_json), IDIOMA], work / "alinhamento.log", TORCH_LIB)

    tts = {s["id"]: s for s in json.loads(tts_json.read_text(encoding="utf-8"))["scenes"]}
    alinhamento = {s["id"]: s for s in json.loads(alinhamento_json.read_text(encoding="utf-8"))["scenes"]}
    saida.mkdir(parents=True, exist_ok=True)
    resultado = []
    for c in cenas:
        nome = f"{c['id']}.wav"
        # o motor entrega a voz crua e muito baixa (cerca de -37 LUFS); o Remotion não ajusta o volume
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(audio / nome), "-af", LOUDNORM,
                        "-ar", "48000", "-ac", "1", str(saida / nome)], check=True)
        resultado.append({"audio": nome, "duration": tts[c["id"]]["duration_s"],
                          "words": [{"w": p["word"], "t": p["start"]} for p in alinhamento[c["id"]]["words"]]})
    (saida / "resultado.json").write_text(json.dumps(resultado, ensure_ascii=False), encoding="utf-8")
    shutil.rmtree(work, ignore_errors=True)
    print(f"  voz pronta: {len(resultado)} falas", flush=True)
