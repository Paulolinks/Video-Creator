"""Cut a voice reference out of an online video (YouTube etc.): only the chosen stretch of audio is fetched.

yt-dlp (from the Video Cutter venv, used read-only) resolves the audio stream URL; FFmpeg reads just the
selected section from it and saves a mono WAV. Nothing else of the video is downloaded.
"""
import os
import re
import subprocess
import time
import uuid
from pathlib import Path

from . import library

YTDLP_PY = Path(r"C:\dev\Video Cutter\.venv\Scripts\python.exe")
CLIPS = library.DATA / "recortes"
MIN_S, MAX_S = 5, 180


def seconds(text):
    """'3:05', '1:02:03', '185' or '185.5' -> seconds."""
    text = (text or "").strip().replace(",", ".")
    if not re.fullmatch(r"\d+(\.\d+)?(:\d{1,2}(\.\d+)?){0,2}", text):
        raise ValueError(f"Tempo inválido: '{text}'. Use minutos:segundos, ex.: 3:00")
    total = 0.0
    for part in text.split(":"):
        total = total * 60 + float(part)
    return total


def _clean_old(max_age_h=24):
    for f in CLIPS.glob("*.wav"):
        if time.time() - f.stat().st_mtime > max_age_h * 3600:
            f.unlink(missing_ok=True)


def cut(url, start, end):
    """Returns {id, arquivo, titulo, duracao}. The clip stays in data/recortes until used or 24 h old."""
    url = (url or "").strip()
    if not re.match(r"^https?://", url):
        raise ValueError("Cole o link completo do vídeo (começando com https://).")
    a, b = seconds(start), seconds(end)
    if b <= a:
        raise ValueError("O fim precisa ser depois do início.")
    if not MIN_S <= b - a <= MAX_S:
        raise ValueError(f"Escolha um trecho entre {MIN_S} segundos e {MAX_S // 60} minutos.")
    CLIPS.mkdir(parents=True, exist_ok=True)
    _clean_old()
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    info = subprocess.run([str(YTDLP_PY), "-B", "-m", "yt_dlp", "--no-playlist", "--js-runtimes", "node",
                           "-f", "bestaudio/best", "--print", "title", "--print", "duration", "--print", "urls", url],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=180)
    lines = [x for x in info.stdout.splitlines() if x.strip()]
    if info.returncode != 0 or len(lines) < 3:
        last = (info.stderr.strip().splitlines() or ["sem resposta"])[-1]
        raise ValueError(f"Não consegui abrir esse vídeo: {last}")
    title, duration, stream = lines[0], lines[1], lines[2]
    total = float(duration) if re.fullmatch(r"\d+(\.\d+)?", duration) else None  # "NA" for live streams
    if total and b > total + 1:
        raise ValueError(f"O vídeo tem só {int(total) // 60}:{int(total) % 60:02d}.")
    cid = uuid.uuid4().hex[:12]
    out = CLIPS / f"{cid}.wav"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{a:.2f}", "-i", stream,
           "-t", f"{b - a:.2f}", "-vn", "-ac", "1", "-ar", "44100",
           "-af", "loudnorm=I=-18:TP=-2:LRA=11,aresample=44100", "-c:a", "pcm_s16le", str(out)]
    run = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    if run.returncode != 0 or not out.exists() or out.stat().st_size < 10_000:
        out.unlink(missing_ok=True)
        raise ValueError("Falha ao recortar o áudio: " + (run.stderr.strip().splitlines() or ["?"])[-1])
    return {"id": cid, "arquivo": str(out), "titulo": title, "duracao": round(b - a, 1)}


def path(cid):
    p = CLIPS / f"{re.sub(r'[^0-9a-f]', '', cid or '')}.wav"
    return p if cid and p.exists() else None
