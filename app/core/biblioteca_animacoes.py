"""Scenes the animation engine has learned (guardian-studio/src/custom), and the frameworks that list them.

A new scene comes in its own file, uploaded on the home page before the scripts that use it. The engine tests it in a
private copy of the project and renders a sample video; only a scene that renders whole is kept. The frameworks are
then rewritten, so the next scripts already know every animation available.
"""
import json
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path

MOTOR = Path(r"D:\Video-Creator\guardian-studio")
CUSTOM = MOTOR / "src" / "custom"
EXEMPLOS = Path(__file__).resolve().parent.parent / "data" / "animacoes"
MODELOS = Path(__file__).resolve().parent.parent / "static" / "modelos"
FRAMEWORK = MODELOS / "Framework_A01_So_Animacao.md"
PDF_SCRIPT = Path(r"D:\Video-Creator\VIDEO_CREATOR_LAB\scripts\framework_a01_pdf.py")
_INICIO, _FIM = "<!-- BIBLIOTECA -->", "<!-- FIM_BIBLIOTECA -->"
_CODIGO = re.compile(r"^\s*CODIGO\s*:", re.M | re.I)
_trava = threading.Lock()
_estado = {"rodando": False, "resultado": [], "erro": None}


def custom_scenes():
    """[{nome, campos, entrou}] of the scenes that passed their test."""
    out = []
    for f in sorted(CUSTOM.glob("*.tsx")):
        text = f.read_text(encoding="utf-8", errors="replace")
        field = lambda k: (re.search(rf"^// {k}: (.*)$", text, re.M) or [None, ""])[1].strip()  # noqa: E731
        out.append({"nome": f.stem, "campos": field("campos"), "entrou": field("entrou")})
    return out


def estado():
    """The upload in progress or just finished, and every learned animation with its sample video."""
    lista = []
    for s in custom_scenes():
        v = EXEMPLOS / s["nome"] / "exemplo.mp4"
        lista.append({**s, "exemplo": str(v) if v.exists() else None, "versao": int(v.stat().st_mtime) if v.exists() else 0})
    lista.sort(key=lambda s: s["entrou"], reverse=True)
    return {**_estado, "animacoes": lista}


def aprender(textos):
    """Starts learning the animations in the uploaded files (their text). Raises ValueError for a wrong file."""
    texto = "\n".join(textos)
    if not _CODIGO.search(texto):
        raise ValueError("Esse arquivo não tem nenhuma animação (nenhuma linha CODIGO: nome).")
    with _trava:
        if _estado["rodando"]:
            raise ValueError("Já tem uma animação sendo testada. Espere terminar.")
        _estado.update(rodando=True, resultado=[], erro=None)
    threading.Thread(target=_aprender, args=(texto,), daemon=True).start()


def _aprender(texto):
    saida = EXEMPLOS / "_envio"
    try:
        shutil.rmtree(saida, ignore_errors=True)
        saida.mkdir(parents=True)
        arquivo = saida / "animacoes.txt"
        arquivo.write_text(texto, encoding="utf-8")
        r = subprocess.run([shutil.which("node"), "scripts/aprender.mjs", str(arquivo), str(saida)], cwd=MOTOR, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=3600)
        res = saida / "resultado.json"
        if not res.exists():
            raise RuntimeError((r.stdout + r.stderr)[-300:])
        resultado = json.loads(res.read_text(encoding="utf-8"))
        for item in resultado:
            if item["ok"]:
                (EXEMPLOS / item["nome"]).mkdir(parents=True, exist_ok=True)
                shutil.move(str(saida / f"{item['nome']}.mp4"), EXEMPLOS / item["nome"] / "exemplo.mp4")
        _estado["resultado"] = resultado
        sync()
    except Exception as e:  # noqa: BLE001 - shown on the page
        _estado["erro"] = str(e)
    finally:
        shutil.rmtree(saida, ignore_errors=True)
        _estado["rodando"] = False


def _section():
    scenes = custom_scenes()
    if not scenes:
        return "Nenhuma ainda. Quando um arquivo de animação nova for enviado ao app, ela aparece aqui e pode ser usada em qualquer roteiro."
    rows = "\n".join(f"| {s['nome']} | {s['campos'] or 'sem campos'} | {s['entrou']} |" for s in scenes)
    return f"| CENA | Campos | Entrou em |\n|---|---|---|\n{rows}"


def sync():
    """Rewrites the framework's list of learned scenes (and its PDF) when it changed. Never raises."""
    try:
        text = FRAMEWORK.read_text(encoding="utf-8")
        new = re.sub(re.escape(_INICIO) + r".*?" + re.escape(_FIM), lambda _: f"{_INICIO}\n{_section()}\n{_FIM}", text, flags=re.S)
        if new != text:
            FRAMEWORK.write_text(new, encoding="utf-8")
            for script in (PDF_SCRIPT, PDF_SCRIPT.with_name("make_framework_pdfs.py")):  # F01 and T02 list the same animations
                subprocess.run([sys.executable, str(script)], check=True, timeout=120, capture_output=True)
    except Exception as e:  # noqa: BLE001 - a stale manual must never fail a video
        print("framework A01:", e, file=sys.stderr)
