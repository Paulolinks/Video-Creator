"""Which language was each voice reference recorded in? Detected once with Whisper and saved beside the recording
(<ref>.idioma.json, tied to its size/date), so later videos just read it.
Run with the Video Cutter .venv (faster-whisper). Usage: idioma_voz.py <ref.wav> [<ref2.wav> ...]"""
import json
import os
import sys
from pathlib import Path


def cache_file(ref):
    return Path(ref).with_suffix(".idioma.json")


def cached(ref):
    """The saved language of this recording, or None if it was never detected or the file changed."""
    st = Path(ref).stat()
    try:
        d = json.loads(cache_file(ref).read_text(encoding="utf-8"))
        if d.get("tamanho") == st.st_size and d.get("mtime") == st.st_mtime:
            return d["idioma"]
    except (OSError, ValueError, KeyError):
        pass
    return None


if __name__ == "__main__":
    from faster_whisper import WhisperModel
    refs = [r for r in sys.argv[1:] if cached(r) is None]
    if refs:
        try:
            model = WhisperModel("small", device="cuda", compute_type="float16")
        except Exception:  # noqa: BLE001
            model = WhisperModel("small", device="cpu", compute_type="int8")
        for r in refs:
            _, info = model.transcribe(r, beam_size=1, without_timestamps=True)
            st = Path(r).stat()
            cache_file(r).write_text(json.dumps({"idioma": info.language, "prob": round(info.language_probability, 3),
                                                 "tamanho": st.st_size, "mtime": st.st_mtime}), encoding="utf-8")
    print(json.dumps({r: cached(r) for r in sys.argv[1:]}), flush=True)
    sys.stdout.flush()
    os._exit(0)
