"""Narrate each scene with Kokoro (pt-BR or English) using the Video Cutter's existing Kokoro runtime, read-only.

Run with: C:/dev/Video Cutter/.runtime/voices/kokoro/Scripts/python.exe (PYTHONDONTWRITEBYTECODE=1, HF_HUB_OFFLINE=1)
Usage: tts_kokoro.py <scenes.json> <out_dir> [voice] [pt|en]

voice: a built-in name (pm_alex) or the path of a character voice pack (.pt). A pack may have a
sidecar .json with "velocidade" (Kokoro speed), "tom" (pitch factor, applied with rubberband) and "efeito"
(optional voice character effect, see EFEITOS: catedral, divino, eterno).
"""
import json
import subprocess
import sys
import time
import wave
from pathlib import Path

import numpy as np
from kokoro import KModel, KPipeline

sys.path.insert(0, str(Path(__file__).resolve().parent))
import measure

WEIGHTS = Path(r"C:\Users\paulo\.cache\huggingface\hub\models--hexgrad--Kokoro-82M\snapshots"
               r"\f3ff3571791e39611d31c381e3a41a3af07b4987")
RATE = 24000
LANG_CODES = {"pt": "p", "en": "a"}  # Kokoro: p = Brazilian Portuguese, a = American English
# Optional "efeito" of a voice pack (ffmpeg filter graph, input [0:a], output [out]). apad leaves room for the tail.
# A short room ambience, not an echo: two quiet reflections under 50 ms blend with the voice instead of being
# heard as repeats (2026-11-07: the 60/130/250 ms taps sounded like delay). rubberband adds ~10 ms of latency, so
# the pitched layers are trimmed by 10 ms to stay glued to the main voice.
_SALA = "aecho=0.92:0.95:23|41:0.09|0.05"
EFEITOS = {
    # deep, a little more low end, short room
    "catedral": f"[0:a]apad=pad_dur=0.2,{_SALA},bass=g=2.5:f=110,alimiter=limit=0.95[out]",
    # calm and warm: a soft lower shadow under the voice (2026-11-07: lighter, it was too deep), short room,
    # gentle highs - a peaceful voice
    "divino": ("[0:a]apad=pad_dur=0.2,asplit=2[a][b];[b]rubberband=pitch=0.8:formant=preserved,atrim=start=0.010,"
               "asetpts=PTS-STARTPTS,lowpass=f=1400,volume=0.12[low];[a][low]amix=inputs=2:normalize=0:duration=first,"
               f"{_SALA},bass=g=1:f=120,treble=g=-1.5,alimiter=limit=0.95[out]"),
    # ethereal: a very slightly detuned double (soft chorus, no audible delay), short room, softened highs
    "eterno": ("[0:a]apad=pad_dur=0.2,asplit=2[a][b];[b]rubberband=pitch=1.008,atrim=start=0.007,asetpts=PTS-STARTPTS,"
               "volume=0.22[d];[a][d]amix=inputs=2:normalize=0:duration=first,"
               f"{_SALA},highpass=f=70,treble=g=-2,alimiter=limit=0.95[out]"),
}

if __name__ == "__main__":
    scenes = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = Path(sys.argv[2])
    voice = sys.argv[3] if len(sys.argv) > 3 else "pf_dora"
    lang = sys.argv[4] if len(sys.argv) > 4 else "pt"
    out.mkdir(parents=True, exist_ok=True)
    voice_pt = Path(voice) if voice.lower().endswith(".pt") else WEIGHTS / "voices" / f"{voice}.pt"
    side = voice_pt.with_suffix(".json")
    style = json.loads(side.read_text(encoding="utf-8")) if side.exists() else {}
    speed, pitch = float(style.get("velocidade", 1.0)), float(style.get("tom", 1.0))
    t0 = time.perf_counter()
    pipe = KPipeline(lang_code=LANG_CODES[lang], repo_id="hexgrad/Kokoro-82M", device="cpu",
                     model=KModel(config=str(WEIGHTS / "config.json"), model=str(WEIGHTS / "kokoro-v1_0.pth")))
    load_s = time.perf_counter() - t0
    result = {"engine": "kokoro 82M", "language": lang, "voice": voice, "speed": speed, "pitch": pitch, "device": "cpu", "load_s": round(load_s, 2), "scenes": []}
    for scene in scenes:
        t = time.perf_counter()
        audio = np.concatenate([a.detach().cpu().numpy() if hasattr(a, "detach") else np.asarray(a)
                                for _, _, a in pipe(scene["text"], voice=str(voice_pt), speed=speed)])
        path = out / f"{scene['id']}.wav"
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
        if abs(pitch - 1.0) > 0.005:
            tmp = path.with_suffix(".tom.wav")
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(path), "-af",
                            f"rubberband=pitch={pitch}:formant=preserved", str(tmp)], check=True)
            tmp.replace(path)
        if style.get("efeito") in EFEITOS:  # voice character effect (e.g. cathedral echo), kept inside the voice
            tmp = path.with_suffix(".efeito.wav")
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(path), "-filter_complex",
                            EFEITOS[style["efeito"]], "-map", "[out]", "-ar", str(RATE), "-ac", "1", str(tmp)],
                           check=True)
            tmp.replace(path)
        with wave.open(str(path)) as w:  # the real length: an echo tail makes the file longer than the speech
            dur = w.getnframes() / w.getframerate()
        result["scenes"].append({"id": scene["id"], "wav": str(path), "duration_s": round(dur, 3),
                                 "synth_s": round(time.perf_counter() - t, 2)})
    me = measure.kernel32.GetCurrentProcess()
    result["total_s"] = round(time.perf_counter() - t0, 2)
    result["peak_ram_mb"] = round(measure.peak_rss(me) / 2**20, 1)
    (out / "tts.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
