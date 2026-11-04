"""Narrate scenes with Chatterbox Multilingual (pt) cloning a reference voice, using the Video Cutter's
existing Chatterbox runtime read-only. Long texts are synthesized sentence by sentence and joined.

Run with: C:/dev/Video Cutter/.runtime/voices/chatterbox/Scripts/python.exe (PYTHONDONTWRITEBYTECODE=1, HF_HUB_OFFLINE=1)
Usage: tts_chatterbox.py <scenes.json> <out_dir> <voice_ref.wav> [pt|en]
       tts_chatterbox.py --preparar <voice_ref.wav>   (analyse the reference once and save it, done at upload)
"""
import hashlib
import json
import re
import sys
import time
import wave
from pathlib import Path

import numpy as np
import torch
from chatterbox.mtl_tts import ChatterboxMultilingualTTS, Conditionals

sys.path.insert(0, str(Path(__file__).resolve().parent))
import measure

MODEL = Path(r"C:\Users\paulo\.cache\huggingface\hub\models--ResembleAI--chatterbox\snapshots"
             r"\5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18")
GAP_S = 0.18
EXAGGERATION = 0.4
MIN_WORDS = 3  # shorter sentences are read together with the next one
WORDS_PER_S = 2.7  # normal speech; a take shorter than 60% of this was cut off by the model and is redone
TRIES = 3


def sentences(text):
    """Sentences to synthesize one at a time. A very short one ("No.", "Sim.") is joined to its neighbour:
    alone it crashes Chatterbox (IndexError in alignment_stream_analyzer) and sounds clipped anyway."""
    out = []
    for p in (p for p in re.split(r"(?<=[.!?])\s+", text.strip()) if p):
        if out and len(out[-1].split()) < MIN_WORDS:
            out[-1] += " " + p
        else:
            out.append(p)
    if len(out) > 1 and len(out[-1].split()) < MIN_WORDS:
        last = out.pop()
        out[-1] += " " + last
    return out


def conds_path(ref):
    """Saved voice analysis beside the reference; a new recording (size/date) gets a new file."""
    ref = Path(ref)
    st = ref.stat()
    key = hashlib.sha1(f"{ref.resolve()}|{st.st_size}|{st.st_mtime}|{EXAGGERATION}".encode()).hexdigest()[:10]
    return ref.with_name(f"{ref.stem}.{key}.conds.pt")


def load_voice(model, ref):
    """Reuse the saved analysis of the reference recording; analyse and save it the first time."""
    path = conds_path(ref)
    if path.exists():
        model.conds = Conditionals.load(path, map_location=model.device).to(model.device)
        return True
    model.prepare_conditionals(ref, exaggeration=EXAGGERATION)
    model.conds.save(path)
    return False


if __name__ == "__main__":
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if sys.argv[1] == "--preparar":
        model = ChatterboxMultilingualTTS.from_local(MODEL, device=device)
        print("já estava salva" if load_voice(model, sys.argv[2]) else "salva", conds_path(sys.argv[2]))
        sys.exit(0)
    scenes = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out, ref = Path(sys.argv[2]), sys.argv[3]
    lang = sys.argv[4] if len(sys.argv) > 4 else "pt"
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    model = ChatterboxMultilingualTTS.from_local(MODEL, device=device)
    cached = load_voice(model, ref)
    result = {"engine": "chatterbox multilingual", "language": lang, "voice_ref": ref, "device": device, "voz_salva": cached,
              "load_s": round(time.perf_counter() - t0, 2), "scenes": []}
    for scene in scenes:
        t = time.perf_counter()
        chunks = []
        for s in sentences(scene["text"]):
            best = None
            for attempt in range(1, TRIES + 1):  # the model sometimes stops mid-sentence: keep the longest take
                wav = model.generate(s, language_id=lang, exaggeration=EXAGGERATION, cfg_weight=0.5)
                wav = wav.detach().cpu().numpy().reshape(-1)
                if best is None or len(wav) > len(best):
                    best = wav
                if len(best) / model.sr >= 0.6 * len(s.split()) / WORDS_PER_S:
                    break
                print(f"  {scene['id']}: fala cortada ({len(wav) / model.sr:.1f} s), refazendo: {s[:50]}", flush=True)
            chunks += [best, np.zeros(int(GAP_S * model.sr), np.float32)]
        audio = np.concatenate(chunks[:-1])
        path = out / f"{scene['id']}.wav"
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(model.sr)
            w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
        result["scenes"].append({"id": scene["id"], "wav": str(path), "duration_s": round(len(audio) / model.sr, 3),
                                 "synth_s": round(time.perf_counter() - t, 2), "sample_rate": model.sr})
        print(scene["id"], result["scenes"][-1]["duration_s"], "s em", result["scenes"][-1]["synth_s"], "s", flush=True)
    me = measure.kernel32.GetCurrentProcess()
    result["total_s"] = round(time.perf_counter() - t0, 2)
    result["peak_ram_mb"] = round(measure.peak_rss(me) / 2**20, 1)
    if device == "cuda":
        result["peak_vram_mb"] = round(torch.cuda.max_memory_allocated() / 2**20, 1)
    (out / "tts.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: result[k] for k in result if k != "scenes"}, ensure_ascii=False))
