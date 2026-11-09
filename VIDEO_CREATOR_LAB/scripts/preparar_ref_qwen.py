"""Qwen3-TTS clones from a short clip plus its exact text: cut about 9 s of the recording at a clean point and write down
what is said there. Saved once per recording in .cache/qwen_refs, outside the app's voice folders.

Run with the Whisper python: preparar_ref_qwen.py <voice_ref>
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

PASTA = Path(__file__).resolve().parent.parent / ".cache" / "qwen_refs"
ALVO_S, MIN_S, MAX_S = 9.0, 6.0, 12.0  # length of the clip


def arquivos(ref):
    """(clip.wav, clip.json) of this recording; a new recording (size/date) gets new ones."""
    ref = Path(ref).resolve()
    st = ref.stat()
    key = hashlib.sha1(f"{ref}|{st.st_size}|{st.st_mtime}".encode()).hexdigest()[:12]
    return PASTA / f"{key}.wav", PASTA / f"{key}.json"


if __name__ == "__main__":
    from faster_whisper import WhisperModel

    ref = sys.argv[1]
    wav, info = arquivos(ref)
    model = WhisperModel("small", device="cpu", compute_type="int8")
    segs, _ = model.transcribe(ref, beam_size=5, word_timestamps=True, clip_timestamps=f"0,{MAX_S + 8}")
    words = [w for s in segs for w in s.words]
    if not words:
        sys.exit("Não encontrei fala na gravação da voz.")
    start = max(0.0, words[0].start - 0.2)

    def score(i):
        """Lower is better: a clean stop (sentence end, or a pause before the next word) close to the target length."""
        w = words[i]
        gap = (words[i + 1].start - w.end) if i + 1 < len(words) else 1.0
        clean = 0 if w.word.strip()[-1:] in ".!?" else 1 if gap >= 0.25 else 2
        return clean, abs(w.end - start - ALVO_S)

    fits = [i for i, w in enumerate(words) if MIN_S <= w.end - start <= MAX_S]
    last = min(fits, key=score) if fits else max(i for i, w in enumerate(words) if w.end - start <= MAX_S)
    end = words[last].end + 0.15
    PASTA.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{start:.2f}", "-t", f"{end - start:.2f}",
                    "-i", ref, "-ac", "1", "-ar", "24000", str(wav)], check=True)
    texto = " ".join(w.word.strip() for w in words[: last + 1])
    info.write_text(json.dumps({"texto": texto, "segundos": round(end - start, 2)}, ensure_ascii=False), encoding="utf-8")
    print("referência pronta:", round(end - start, 1), "s", flush=True)
