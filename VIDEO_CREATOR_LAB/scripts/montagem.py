"""End-to-end assembly test: narration-driven scene timing, sub-pixel moves, xfade, captions, music.

Produces three versions for comparison:
  v1 no ducking + block captions, v2 ducking + block captions, v3 ducking + karaoke captions.
Music is a synthetic pad generated here (own rights), not a library track.
Run with the lab venv. Usage: montagem.py <scenes.json>
"""
import json
import subprocess
import sys
import time
import wave
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import measure

LAB = Path(__file__).resolve().parent.parent
OUT = LAB / "outputs" / "montagem"
AUDIO = OUT / "audio"
FONTS = LAB / "inputs" / "fonts"
OW, OH, FPS = 1080, 1920, 30
LEAD, TAIL, XF = 0.25, 0.45, 0.4   # silence before first line, after each line, crossfade length
X264 = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"]
# Voice chain reused from Video Cutter audio_tratamento.py ("locutor" preset).
VOICE_FX = ("highpass=f=90,equalizer=f=150:t=q:w=1:g=2,equalizer=f=350:t=q:w=1.2:g=-3,"
            "equalizer=f=4000:t=q:w=1:g=4,treble=g=4:f=11000:t=s,"
            "acompressor=threshold=-22dB:ratio=3.5:attack=8:release=120:makeup=2,deesser=i=0.5")
MOVES = {
    "zoom_in": (lambda e: 1 + 0.15 * e, lambda e: 0.5, lambda e: 0.5),
    "zoom_out": (lambda e: 1.15 - 0.15 * e, lambda e: 0.5, lambda e: 0.5),
    "pan_v": (lambda e: 1.15, lambda e: 0.5, lambda e: 1 - e),
    "combined": (lambda e: 1.05 + 0.15 * e, lambda e: 0.3 + 0.4 * e, lambda e: 0.4 + 0.2 * e),
}


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def load_9x16(path):
    im = Image.open(LAB / path if not Path(path).is_absolute() else path).convert("RGB")
    w, h = im.size
    if abs(w / h - 9 / 16) > 0.01:
        cw = round(h * 9 / 16)
        im = im.crop(((w - cw) // 2, 0, (w - cw) // 2 + cw, h))
    return im.resize((2160, 3840), Image.Resampling.LANCZOS)


def render_scene(scene, seconds, path):
    src = load_9x16(scene["image"])
    fz, fx, fy = MOVES[scene["move"]]
    n = round(seconds * FPS)
    enc = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
                            "-pix_fmt", "rgb24", "-s", f"{OW}x{OH}", "-r", str(FPS), "-i", "-", *X264, str(path)],
                           stdin=subprocess.PIPE)
    for i in range(n):
        t = i / max(n - 1, 1)
        e = t * t * (3 - 2 * t)
        z = fz(e)
        w, h = 2160 / z, 3840 / z
        x, y = max(0.0, (2160 - w) * fx(e)), max(0.0, (3840 - h) * fy(e))
        w, h = min(w, 2160 - x), min(h, 3840 - y)
        enc.stdin.write(src.resize((OW, OH), Image.Resampling.LANCZOS, box=(x, y, x + w, y + h)).tobytes())
    enc.stdin.close()
    enc.wait()


def read_wav(path):
    with wave.open(str(path)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), np.int16), w.getframerate()


def ass_time(s):
    cs = max(0, round(s * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02}:{cs // 100 % 60:02}.{cs % 100:02}"


def caption_groups(words, max_words=3):
    groups, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= max_words or w["word"][-1] in ".,!?;:":
            groups.append(cur)
            cur = []
    return groups + ([cur] if cur else [])


def write_ass(path, timeline, karaoke):
    # Colours are &HAABBGGRR. Karaoke: Secondary (white) turns Primary (gold) as each word is spoken.
    primary = "&H0045D7FF" if karaoke else "&H00FFFFFF"
    lines = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {OW}", f"PlayResY: {OH}", "WrapStyle: 0", "",
             "[V4+ Styles]",
             "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
             "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
             "Alignment, MarginL, MarginR, MarginV, Encoding",
             f"Style: Main,Poppins,84,{primary},&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,2,"
             "2,90,90,560,1", "",
             "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    flat = [g for scene in timeline for g in caption_groups(scene)]
    for i, g in enumerate(flat):
        start = g[0]["start"]
        end = min(flat[i + 1][0]["start"], g[-1]["end"] + 0.6) if i + 1 < len(flat) else g[-1]["end"] + 0.6
        if karaoke:
            parts, t = [], start
            for w in g:
                parts.append(f"{{\\k{max(1, round((w['end'] - t) * 100))}}}{w['word']}")
                t = w["end"]
            text = " ".join(parts)
        else:
            text = " ".join(w["word"] for w in g)
        lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Main,,0,0,0,,{text.upper()}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    scenes = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    tts = {s["id"]: s for s in json.loads((AUDIO / "tts.json").read_text(encoding="utf-8"))["scenes"]}
    align = {s["id"]: s for s in json.loads((AUDIO / "alinhamento.json").read_text(encoding="utf-8"))["scenes"]}
    stages, t0 = {}, time.perf_counter()

    # 1. Scene timing comes from the narration.
    starts, durations, cursor = [], [], 0.0
    for i, sc in enumerate(scenes):
        d = tts[sc["id"]]["duration_s"] + TAIL + (LEAD if i == 0 else 0)
        starts.append(cursor)
        durations.append(d)
        cursor += d
    total = cursor

    # 2. Narration track + word timeline on the global clock.
    rate = read_wav(AUDIO / f"{scenes[0]['id']}.wav")[1]
    voice = np.zeros(round(total * rate), np.int16)
    timeline = []
    for i, sc in enumerate(scenes):
        samples, _ = read_wav(AUDIO / f"{sc['id']}.wav")
        offset = starts[i] + (LEAD if i == 0 else 0)
        voice[round(offset * rate):round(offset * rate) + len(samples)] = samples
        timeline.append([{**w, "start": w["start"] + offset, "end": w["end"] + offset}
                         for w in align[sc["id"]]["words"]])
    with wave.open(str(AUDIO / "narracao.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(voice.tobytes())
    stages["timing_e_narracao_s"] = round(time.perf_counter() - t0, 2)

    # 3. Scene clips (each extended by the crossfade so cuts land on scene boundaries).
    t = time.perf_counter()
    clips = []
    for i, sc in enumerate(scenes):
        clip = OUT / "_cenas" / f"{sc['id']}.mp4"
        clip.parent.mkdir(exist_ok=True)
        render_scene(sc, durations[i] + (XF if i < len(scenes) - 1 else 0), clip)
        clips.append(clip)
    stages["render_cenas_s"] = round(time.perf_counter() - t, 2)

    # 4. Crossfades.
    t = time.perf_counter()
    graph, last, acc = [], "0:v", 0.0
    for i in range(1, len(clips)):
        acc += durations[i - 1]
        graph.append(f"[{last}][{i}:v]xfade=transition=fade:duration={XF}:offset={acc:.3f}[x{i}]")
        last = f"x{i}"
    base = OUT / "_base_sem_legenda.mp4"
    run(["ffmpeg", "-hide_banner", "-y", *sum((["-i", str(c)] for c in clips), []),
         "-filter_complex", ";".join(graph), "-map", f"[{last}]", "-t", f"{total:.3f}", *X264, str(base)])
    stages["transicoes_s"] = round(time.perf_counter() - t, 2)

    # 5. Synthetic music pad (A minor, slow swell), own rights.
    t = time.perf_counter()
    music = AUDIO / "musica_sintetica.wav"
    pad = "+".join(f"0.18*sin(2*PI*{f}*t)" for f in (110, 130.81, 164.81, 220, 329.63))
    run(["ffmpeg", "-hide_banner", "-y", "-f", "lavfi", "-i",
         f"aevalsrc='({pad})*(0.75+0.25*sin(2*PI*0.25*t))':s=48000:d={total + 1:.2f}",
         "-af", "lowpass=f=1400,aecho=0.8:0.6:120|240:0.3|0.2,afade=t=in:d=1", "-ac", "2", str(music)])

    # 6. Captions + audio mixes.
    for tag, karaoke in (("simples", False), ("karaoke", True)):
        write_ass(OUT / f"legenda_{tag}.ass", timeline, karaoke)
    fade_out = total - 1.2
    voice_chain = (f"[0:a]aresample=48000,aformat=channel_layouts=stereo,{VOICE_FX},"
                   "loudnorm=I=-14:TP=-1.5:LRA=11")
    music_chain = f"[1:a]volume=0.35,afade=t=out:st={fade_out:.2f}:d=1.2,atrim=0:{total:.3f}"
    mixes = {
        "sem_ducking": f"{voice_chain}[v];{music_chain}[m];[v][m]amix=inputs=2:duration=first:normalize=0,"
                       "alimiter=limit=0.95[a]",
        "com_ducking": f"{voice_chain},asplit[v][sc];{music_chain}[m];"
                       "[m][sc]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=450:makeup=1[md];"
                       "[v][md]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]",
    }
    versions = {"v1_sem_ducking_legenda_simples": ("sem_ducking", "simples"),
                "v2_com_ducking_legenda_simples": ("com_ducking", "simples"),
                "v3_com_ducking_legenda_karaoke": ("com_ducking", "karaoke")}
    fonts = FONTS.as_posix().replace(":", "\\:")
    results = {}
    for name, (mix, caps) in versions.items():
        t = time.perf_counter()
        ass = (OUT / f"legenda_{caps}.ass").as_posix().replace(":", "\\:")
        out = OUT / f"montagem_{name}.mp4"
        r = measure.run(["ffmpeg", "-hide_banner", "-y", "-i", str(AUDIO / "narracao.wav"), "-i", str(music),
                         "-i", str(base), "-filter_complex",
                         f"{mixes[mix]};[2:v]subtitles='{ass}':fontsdir='{fonts}'[vout]",
                         "-map", "[vout]", "-map", "[a]", *X264, "-c:a", "aac", "-b:a", "192k",
                         "-movflags", "+faststart", str(out)], log_path=OUT / f"montagem_{name}.log")
        results[name] = {"wall_s": r["wall_s"], "peak_ram_mb": r["peak_ram_mb"], "returncode": r["returncode"],
                         "output": str(out)}
        print(f"{name:34} rc={r['returncode']} {r['wall_s']:6.2f}s RAM {r['peak_ram_mb']} MB", flush=True)

    me = measure.kernel32.GetCurrentProcess()
    summary = {"test": "montagem", "date": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "scenes": [{"id": s["id"], "start_s": round(st, 3), "duration_s": round(d, 3),
                           "narration_s": tts[s["id"]]["duration_s"], "move": s["move"]}
                          for s, st, d in zip(scenes, starts, durations)],
               "video_duration_s": round(total, 3), "stages": stages, "final_encodes": results,
               "python_peak_ram_mb": round(measure.peak_rss(me) / 2**20, 1),
               "wall_total_s": round(time.perf_counter() - t0, 2),
               "config": {"lead_s": LEAD, "tail_s": TAIL, "crossfade_s": XF, "voice_fx": "Cutter preset locutor",
                          "music": "pad sintetico (aevalsrc), volume 0.35", "ducking": "sidechaincompress thr 0.02 ratio 8"}}
    (LAB / "benchmarks" / "MONTAGEM_teste.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                                                            encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("video_duration_s", "stages", "wall_total_s", "python_peak_ram_mb")}))
