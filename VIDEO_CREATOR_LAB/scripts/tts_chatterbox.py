"""Narrate scenes with Chatterbox Multilingual (pt) cloning a reference voice, using the Video Cutter's
existing Chatterbox runtime read-only. Long texts are synthesized sentence by sentence and joined.

Run with: C:/dev/Video Cutter/.runtime/voices/chatterbox/Scripts/python.exe (PYTHONDONTWRITEBYTECODE=1, HF_HUB_OFFLINE=1)
Usage: tts_chatterbox.py <scenes.json> <out_dir> <voice_ref.wav> [pt|en]
       tts_chatterbox.py --preparar <voice_ref.wav>   (analyse the reference once and save it, done at upload)
       tts_chatterbox.py --lote <jobs.json>           (several voices / fixes with a single model load)
       tts_chatterbox.py --refazer <redo.json> <out_dir> <voice_ref.wav> [pt|en]
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
CFG_MESMA_LINGUA = 0.5   # package default
CFG_OUTRA_LINGUA = 0.5   # 0.3 cut accent a little but made speech ~20% slower (user: "lento"): kept at the default


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
    # --refazer <redo.json> <out_dir> <voice_ref> [lang]: redo only some sentences of scenes already made
    # (redo.json: [{"id", "text", "frases": [sentence indexes]}]); the other sentences are kept as they were.
    # --lote <jobs.json>: several voices in one run, the model loads once
    # (jobs.json: [{"cenas": scenes.json, "saida": out_dir, "voz": voice_ref, "idioma": "en", "refazer": false}]).
    if sys.argv[1] == "--lote":
        jobs = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    else:
        redo = sys.argv[1] == "--refazer"
        args = sys.argv[2:] if redo else sys.argv[1:]
        jobs = [{"cenas": args[0], "saida": args[1], "voz": args[2], "idioma": args[3] if len(args) > 3 else "pt",
                 "refazer": redo}]
    t_load = time.perf_counter()
    model = ChatterboxMultilingualTTS.from_local(MODEL, device=device)
    load_s = round(time.perf_counter() - t_load, 2)
    print(f"modelo carregado em {load_s} s ({len(jobs)} voz(es))", flush=True)

    try:  # our fixes for the installed Chatterbox (cut-offs, babble, slowdown); see chatterbox_fix.py
        import chatterbox_fix as fx
    except Exception as e:  # noqa: BLE001 - never block narration: fall back to the package as it is
        fx = None
        print(f"(correções do Chatterbox indisponíveis: {e})", flush=True)
    stats = {"tentativas_extras": 0, "frases": 0}

    def take(s, lang, cfg):
        if fx is None:
            wav = model.generate(s, language_id=lang, exaggeration=EXAGGERATION, cfg_weight=cfg)
            return wav.detach().cpu().numpy().reshape(-1).astype(np.float32), {"fim": "natural"}
        wav, info = fx.gerar(model, s, lang, exaggeration=EXAGGERATION, cfg_weight=cfg)
        return wav.detach().cpu().numpy().reshape(-1).astype(np.float32), info

    def synth(scene_id, s, lang, cfg):
        """Up to TRIES takes; a take is good when it ended cleanly and its length fits the text.
        Bad: the guard caught a loop ("travou") or invented speech past the text ("longa_demais"), or the take is
        far too short (cut off) or far too long. If no take is good, keep the one closest to the expected length."""
        expected = len(s.split()) / WORDS_PER_S
        best, best_score = None, None
        stats["frases"] += 1
        for attempt in range(1, TRIES + 1):
            # a retry with the same setting tends to fail the same way: the 2nd take goes back to the package's
            # default guidance, the 3rd a little above it (lower values make speech slower)
            wav, info = take(s, lang, cfg if attempt == 1 else CFG_MESMA_LINGUA if attempt == 2 else 0.6)
            dur = len(wav) / model.sr
            bad = []
            if info.get("fim") in ("travou", "longa_demais"):
                bad.append(info["fim"])
            if dur < 0.6 * expected:
                bad.append("cortada")
            if dur > max(3.0, 2.2 * expected):
                bad.append("comprida")
            score = (len(bad), abs(dur - expected))
            if best is None or score < best_score:
                best, best_score = wav, score
            if not bad:
                break
            stats["tentativas_extras"] += 1
            print(f"  {scene_id}: tentativa {attempt} ruim ({', '.join(bad)}, {dur:.1f} s), refazendo: {s[:50]}",
                  flush=True)
        return best

    for job in jobs:
        scenes = json.loads(Path(job["cenas"]).read_text(encoding="utf-8"))
        out, ref, lang, redo = Path(job["saida"]), job["voz"], job.get("idioma", "pt"), bool(job.get("refazer"))
        # a reference recorded in another language pushes its accent (and drift) into the speech: a lower
        # guidance weight follows the target language more (measured: 8.7% -> 6.7% wrong words, same timbre)
        ref_lang = job.get("idioma_ref")
        cfg = CFG_OUTRA_LINGUA if ref_lang and ref_lang != lang else CFG_MESMA_LINGUA
        out.mkdir(parents=True, exist_ok=True)
        takes = out / "frases"  # every sentence's take, so a later fix can swap a single sentence
        takes.mkdir(exist_ok=True)
        t0 = time.perf_counter()
        if device == "cuda":
            torch.cuda.reset_peak_memory_stats()
        stats["tentativas_extras"] = 0
        cached = load_voice(model, ref)
        print(f"voz: {Path(ref).parent.name} ({len(scenes)} cena(s){', correção' if redo else ''})", flush=True)
        result = {"engine": "chatterbox multilingual", "language": lang, "voice_ref": ref, "device": device,
                  "voz_salva": cached, "load_s": load_s, "idioma_ref": ref_lang, "cfg_weight": cfg,
                  "corrigido": fx is not None, "scenes": []}
        for scene in scenes:
            t = time.perf_counter()
            parts = sentences(scene["text"])
            files = [takes / f"{scene['id']}_{i:02}.npy" for i in range(len(parts))]
            if redo and all(f.exists() for f in files):
                todo = set(scene.get("frases") or range(len(parts)))
            else:
                todo = set(range(len(parts)))
            for i, s in enumerate(parts):
                if i in todo:
                    if redo:
                        print(f"  {scene['id']} frase {i + 1}: refazendo: {s[:60]}", flush=True)
                    np.save(files[i], synth(scene["id"], s, lang, cfg))
            chunks, frases, pos = [], [], 0
            for i, s in enumerate(parts):
                wav = np.load(files[i])
                frases.append({"texto": s, "inicio": round(pos / model.sr, 3),
                               "fim": round((pos + len(wav)) / model.sr, 3)})
                chunks += [wav, np.zeros(int(GAP_S * model.sr), np.float32)]
                pos += len(wav) + int(GAP_S * model.sr)
            audio = np.concatenate(chunks[:-1])
            path = out / f"{scene['id']}.wav"
            with wave.open(str(path), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(model.sr)
                w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
            result["scenes"].append({"id": scene["id"], "wav": str(path), "duration_s": round(len(audio) / model.sr, 3),
                                     "synth_s": round(time.perf_counter() - t, 2), "sample_rate": model.sr,
                                     "frases": frases})
            print(scene["id"], result["scenes"][-1]["duration_s"], "s em", result["scenes"][-1]["synth_s"], "s",
                  flush=True)
        if redo:  # keep the full list: update only the redone scenes in the existing tts.json
            try:
                old = json.loads((out / "tts.json").read_text(encoding="utf-8"))
                new = {s["id"]: s for s in result["scenes"]}
                merged = [new.pop(s["id"], s) for s in old["scenes"]] + list(new.values())
                result = {**old, "scenes": merged, "correcao_s": round(time.perf_counter() - t0, 2)}
            except (OSError, ValueError):
                pass
        me = measure.kernel32.GetCurrentProcess()
        result["total_s"] = round(time.perf_counter() - t0, 2)
        result["tentativas_extras"] = stats["tentativas_extras"]
        result["peak_ram_mb"] = round(measure.peak_rss(me) / 2**20, 1)
        if device == "cuda":
            result["peak_vram_mb"] = round(torch.cuda.max_memory_allocated() / 2**20, 1)
        (out / "tts.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({k: result[k] for k in result if k != "scenes"}, ensure_ascii=False), flush=True)
