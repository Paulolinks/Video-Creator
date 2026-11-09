"""Narrate scenes with Qwen3-TTS 0.6B cloning a reference voice. Same arguments and tts.json as tts_chatterbox.py.
A scene is spoken in one go, which is what keeps the intonation natural; only a very long one is split, between sentences.

Run with: VIDEO_CREATOR_LAB/.venvs/qwen3tts/Scripts/python.exe (PYTHONDONTWRITEBYTECODE=1, HF_HUB_OFFLINE=1)
Usage: tts_qwen.py <scenes.json> <out_dir> <voice_ref> [pt|en]
       tts_qwen.py --lote <jobs.json>
       tts_qwen.py --refazer <redo.json> <out_dir> <voice_ref> [pt|en]
"""
import json
import os
import re
import subprocess
import sys
import time
import wave
from pathlib import Path

import numpy as np
import torch
from qwen_tts import Qwen3TTSModel

sys.path.insert(0, str(Path(__file__).resolve().parent))
import efeitos_voz
import preparar_ref_qwen

LAB = Path(__file__).resolve().parent.parent
MODEL = (LAB / ".cache" / "huggingface" / "hub" / "models--Qwen--Qwen3-TTS-12Hz-0.6B-Base" / "snapshots"
         / "5d83992436eae1d760afd27aff78a71d676296fc")
WHISPER_PY = Path(r"C:\dev\Video Cutter\.venv\Scripts\python.exe")
IDIOMAS = {"pt": "Portuguese", "en": "English"}
MAX_PALAVRAS = 55  # about 20 s: the longest stretch spoken in one go
PALAVRAS_POR_S = 3.0  # measured on this model in Portuguese: 3.2-3.6
TOKENS_POR_S = 12  # the model's rate: limits the length, so a take can't run on forever
PAUSA_S = 0.3  # between the stretches of a long scene
TENTATIVAS = 3


def blocos(text):
    """The text in stretches of up to MAX_PALAVRAS words, cut between sentences."""
    out = []
    for s in (p for p in re.split(r"(?<=[.!?])\s+", text.strip()) if p):
        if out and len(out[-1].split()) + len(s.split()) <= MAX_PALAVRAS:
            out[-1] += " " + s
        else:
            out.append(s)
    return out


def referencia(ref):
    """(clip, its text), cutting and transcribing the recording the first time it is used."""
    wav, info = preparar_ref_qwen.arquivos(ref)
    if not (wav.exists() and info.exists()):
        print("preparando a referência da voz...", flush=True)
        subprocess.run([str(WHISPER_PY), str(Path(__file__).with_name("preparar_ref_qwen.py")), str(ref)], check=True, timeout=300)
    return str(wav), json.loads(info.read_text(encoding="utf-8"))["texto"]


if __name__ == "__main__":
    if sys.argv[1] == "--lote":
        jobs = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    else:
        redo = sys.argv[1] == "--refazer"
        args = sys.argv[2:] if redo else sys.argv[1:]
        jobs = [{"cenas": args[0], "saida": args[1], "voz": args[2], "idioma": args[3] if len(args) > 3 else "pt",
                 "refazer": redo}]
    t_load = time.perf_counter()
    model = Qwen3TTSModel.from_pretrained(str(MODEL), device_map="cuda:0", dtype=torch.bfloat16)
    load_s = round(time.perf_counter() - t_load, 2)
    print(f"modelo carregado em {load_s} s ({len(jobs)} voz(es))", flush=True)
    extras = 0

    def falar(cena, s, idioma, prompt):
        """Up to TENTATIVAS takes; a take is bad if it is far too short (cut off) or far too long (ran on)."""
        global extras
        esperado = len(s.split()) / PALAVRAS_POR_S
        melhor, nota_melhor, sr = None, None, 24000
        for tentativa in range(TENTATIVAS):
            torch.manual_seed(42 + tentativa)
            wavs, sr = model.generate_voice_clone(text=s, language=idioma, voice_clone_prompt=prompt,
                                                  max_new_tokens=int(max(8.0, 2.6 * esperado) * TOKENS_POR_S))
            wav = np.asarray(wavs[0], dtype=np.float32).reshape(-1)
            dur = len(wav) / sr
            ruim = ["cortada"] * (dur < 0.5 * esperado) + ["comprida"] * (dur > max(3.0, 2.2 * esperado))
            nota = (len(ruim), abs(dur - esperado))
            if melhor is None or nota < nota_melhor:
                melhor, nota_melhor = wav, nota
            if not ruim:
                break
            extras += 1
            print(f"  {cena}: tentativa {tentativa + 1} ruim ({', '.join(ruim)}, {dur:.1f} s): {s[:50]}", flush=True)
        return melhor, sr

    for job in jobs:
        scenes = json.loads(Path(job["cenas"]).read_text(encoding="utf-8"))
        out, ref, lang, redo = Path(job["saida"]), job["voz"], job.get("idioma", "pt"), bool(job.get("refazer"))
        side = Path(ref).with_suffix(".json")  # a styled version of a cloned voice: pitch and effect (efeitos_voz.py)
        style = json.loads(side.read_text(encoding="utf-8")) if side.exists() else {}
        out.mkdir(parents=True, exist_ok=True)
        takes = out / "frases"  # every stretch's take, so a later fix can swap a single one
        takes.mkdir(exist_ok=True)
        t0 = time.perf_counter()
        extras = 0
        clip, texto = referencia(ref)
        prompt = model.create_voice_clone_prompt(ref_audio=clip, ref_text=texto, x_vector_only_mode=False)
        idioma = IDIOMAS.get(lang, "Auto")
        print(f"voz: {Path(ref).parent.name} ({len(scenes)} cena(s){', correção' if redo else ''})", flush=True)
        result = {"engine": "qwen3-tts 0.6B", "language": lang, "voice_ref": ref, "device": "cuda", "load_s": load_s,
                  "scenes": []}
        for scene in scenes:
            t = time.perf_counter()
            parts = blocos(scene["text"])
            files = [takes / f"{scene['id']}_{i:02}.npy" for i in range(len(parts))]
            todo = (set(scene.get("frases") or range(len(parts))) if redo and all(f.exists() for f in files)
                    else set(range(len(parts))))
            sr = 24000
            for i, s in enumerate(parts):
                if i in todo:
                    wav, sr = falar(scene["id"], s, idioma, prompt)
                    np.save(files[i], wav)
            chunks, frases, pos = [], [], 0
            gap = int(PAUSA_S * sr)
            for f, s in zip(files, parts):
                wav = np.load(f)
                frases.append({"texto": s, "inicio": round(pos / sr, 3), "fim": round((pos + len(wav)) / sr, 3)})
                chunks += [wav, np.zeros(gap, np.float32)]
                pos += len(wav) + gap
            audio = np.concatenate(chunks[:-1])
            path = out / f"{scene['id']}.wav"
            with wave.open(str(path), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sr)
                w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
            efeitos_voz.aplicar(path, style, sr)  # applied on the raw takes, so a redo never stacks it
            with wave.open(str(path)) as w:  # the real length: an effect's tail makes the file longer than the speech
                dur = w.getnframes() / w.getframerate()
            result["scenes"].append({"id": scene["id"], "wav": str(path), "duration_s": round(dur, 3),
                                     "synth_s": round(time.perf_counter() - t, 2), "sample_rate": sr, "frases": frases})
            print(scene["id"], result["scenes"][-1]["duration_s"], "s em", result["scenes"][-1]["synth_s"], "s", flush=True)
        if redo:  # keep the full list: update only the redone scenes in the existing tts.json
            try:
                old = json.loads((out / "tts.json").read_text(encoding="utf-8"))
                new = {s["id"]: s for s in result["scenes"]}
                merged = [new.pop(s["id"], s) for s in old["scenes"]] + list(new.values())
                result = {**old, "scenes": merged, "correcao_s": round(time.perf_counter() - t0, 2)}
            except (OSError, ValueError):
                pass
        result["total_s"] = round(time.perf_counter() - t0, 2)
        result["tentativas_extras"] = extras
        result["peak_vram_mb"] = round(torch.cuda.max_memory_allocated() / 2**20, 1)
        (out / "tts.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({k: result[k] for k in result if k != "scenes"}, ensure_ascii=False), flush=True)
    sys.stdout.flush()
    os._exit(0)  # the work is saved: leave without the GPU teardown, which can hang or crash on Windows
