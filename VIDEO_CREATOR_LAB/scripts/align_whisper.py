"""Align the known script text to the narration with faster-whisper word timestamps.

The text comes from the script (never from recognition): whisper only supplies timings.
Script words are matched to recognized words in order (difflib); unmatched words are interpolated.
Run with the Video Cutter's .venv python (faster-whisper 1.1.1), read-only.
Usage: align_whisper.py <scenes.json> <tts.json> <out.json> [pt|en]
"""
import difflib
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

from faster_whisper import WhisperModel

sys.path.insert(0, str(Path(__file__).resolve().parent))
import measure


def norm(word):
    word = unicodedata.normalize("NFD", word.lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in word if unicodedata.category(c) != "Mn"))


def align(script_words, rec, duration):
    a, b = [norm(w) for w in script_words], [norm(w["word"]) for w in rec]
    times = [None] * len(script_words)
    for block in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(block.size):
            r = rec[block.b + k]
            times[block.a + k] = (r["start"], r["end"])
    known = [i for i, t in enumerate(times) if t]
    matched = len(known)
    for i in range(len(times)):  # interpolate gaps between known neighbours
        if times[i]:
            continue
        prev = max((k for k in known if k < i), default=None)
        nxt = min((k for k in known if k > i), default=None)
        t0 = times[prev][1] if prev is not None else 0.0
        t1 = times[nxt][0] if nxt is not None else duration
        span = (nxt if nxt is not None else len(times)) - (prev if prev is not None else -1)
        pos = i - (prev if prev is not None else -1)
        start = t0 + (t1 - t0) * (pos - 1) / span
        times[i] = (start, t0 + (t1 - t0) * pos / span)
    return [{"word": w, "start": round(s, 3), "end": round(e, 3)} for w, (s, e) in zip(script_words, times)], matched


if __name__ == "__main__":
    scenes = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    tts = {s["id"]: s for s in json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))["scenes"]}
    lang = sys.argv[4] if len(sys.argv) > 4 else "pt"
    t0 = time.perf_counter()
    try:  # GPU (~10x faster); the cuDNN DLLs come from the Chatterbox torch install, put on PATH by the caller
        model, engine = WhisperModel("small", device="cuda", compute_type="float16"), "faster-whisper small fp16 cuda"
        list(model.transcribe(tts[scenes[0]["id"]]["wav"], language=lang, word_timestamps=True)[0])  # fails without cuDNN
    except Exception as e:  # noqa: BLE001
        print("GPU indisponível, usando CPU:", e, flush=True)
        model, engine = WhisperModel("small", device="cpu", compute_type="int8"), "faster-whisper small int8 cpu"
    load_s = time.perf_counter() - t0
    out = {"engine": engine, "language": lang, "load_s": round(load_s, 2), "scenes": []}
    for scene in scenes:
        t = time.perf_counter()
        segments, _ = model.transcribe(tts[scene["id"]]["wav"], language=lang, word_timestamps=True)
        rec = [{"word": w.word.strip(), "start": w.start, "end": w.end} for s in segments for w in s.words]
        words, matched = align(scene["text"].split(), rec, tts[scene["id"]]["duration_s"])
        out["scenes"].append({"id": scene["id"], "recognized": " ".join(r["word"] for r in rec),
                              "matched_words": matched, "total_words": len(words), "words": words,
                              "align_s": round(time.perf_counter() - t, 2)})
    me = measure.kernel32.GetCurrentProcess()
    out["total_s"] = round(time.perf_counter() - t0, 2)
    out["peak_ram_mb"] = round(measure.peak_rss(me) / 2**20, 1)
    Path(sys.argv[3]).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    for s in out["scenes"]:
        print(s["id"], f"{s['matched_words']}/{s['total_words']} palavras casadas |", s["recognized"])
    print("total", out["total_s"], "s  RAM", out["peak_ram_mb"], "MB", flush=True)
    # Leave without running the CUDA/CTranslate2 teardown: on Windows it sometimes crashes after all the work is saved
    # (seen on a 132-scene video), and the non-zero exit made the whole video fail.
    os._exit(0)
