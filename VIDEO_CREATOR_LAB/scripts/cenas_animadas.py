"""Animation scenes inside the character templates (F01, T02, T03): each one is drawn by the animation engine as a
full-screen clip, and the composer treats it like any other scene clip (the template keeps its own voice and captions).

A scene that cannot be drawn comes out as a plain background with a warning on the video's card: never a lost video.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

MOTOR = Path(r"D:\Video-Creator\guardian-studio")
TEMA = "ouro"  # same gold as the karaoke captions of these templates
FUNDO_LISO = "0x12121C"
ARQUIVO_AVISOS = "avisos_animacao.json"


def renderizar(tpl, cenas, pasta, texto, words_de):
    """cenas: [(scene, seconds, lead_s)]. texto: 'legenda-baixo' (F01, caption low) or 'centro' (interview, caption in the middle).
    Draws one clip per scene at pasta/<id>.mp4 and returns the warnings."""
    if not cenas:
        return []
    v = tpl["video"]
    W, H, fps = v["largura"], v["altura"], v["fps"]
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    avisos, feitas = [], {}
    if W >= H:
        avisos.append("As animações em tela cheia só funcionam no vertical 9:16: essas cenas saíram com fundo liso.")
    else:
        pedido = pasta / "_animacoes.json"
        itens = [{"id": sc["id"], "cena": sc["animacao"]["cena"], "params": sc["animacao"]["params"],
                  "words": [{"w": w["word"], "t": round(w["start"], 3)} for w in words_de(sc)],
                  "inicio": round(lead * fps), "total": round(seconds * fps), "saida": str(pasta / f"{sc['id']}.mp4")}
                 for sc, seconds, lead in cenas]
        pedido.write_text(json.dumps({"tema": TEMA, "texto": texto, "idioma": tpl.get("idioma", "pt"), "cenas": itens},
                                     ensure_ascii=False), encoding="utf-8")
        for it in itens:
            Path(it["saida"]).unlink(missing_ok=True)
        try:
            r = subprocess.run([shutil.which("node"), "scripts/cena_solta.mjs", str(pedido)], cwd=MOTOR, capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=3600, env={**os.environ})
            arq = pedido.with_suffix(".resultado.json")
            if arq.exists():
                feitas = json.loads(arq.read_text(encoding="utf-8"))
            elif r.returncode:
                avisos.append(f"O motor de animação falhou: {r.stdout[-200:]}{r.stderr[-200:]}")
        except (OSError, ValueError, subprocess.SubprocessError) as e:
            avisos.append(f"O motor de animação falhou: {e}")
    for sc, seconds, _ in cenas:
        clip = pasta / f"{sc['id']}.mp4"
        if feitas.get(sc["id"]) is True and clip.exists():
            # the composers join clips with xfade, which refuses a clip on another timebase: the same one ffmpeg gives theirs
            igual = clip.with_name(f"_{clip.name}")
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(clip), "-c", "copy",
                            "-video_track_timescale", str(fps * 512), str(igual)], check=True)
            igual.replace(clip)
            continue
        if W < H:
            avisos.append(f"{sc['id'].replace('_', ' ').title()}: a animação '{sc['animacao']['cena']}' falhou e a cena "
                          f"saiu com fundo liso ({feitas.get(sc['id']) or 'sem detalhe'}).")
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        f"color=c={FUNDO_LISO}:s={W}x{H}:r={fps}:d={seconds:.3f}", "-c:v", "libx264", "-preset", "veryfast",
                        "-crf", "16", "-pix_fmt", "yuv420p", str(clip)], check=True)
    return avisos


def guardar_avisos(work, avisos):
    """The app reads this file when the video finishes and shows the warnings on its card."""
    arq = Path(work) / ARQUIVO_AVISOS
    arq.unlink(missing_ok=True)
    if avisos:
        arq.write_text(json.dumps(avisos, ensure_ascii=False), encoding="utf-8")
