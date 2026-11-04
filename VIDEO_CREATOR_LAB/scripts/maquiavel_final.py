"""Full test video from the user's script and images: talking scenes (SadTalker) + 2.5D scene + karaoke.

Scene modes: "fala" uses outputs/sadtalker/<id>.mp4 with a slow sub-pixel zoom on top;
"dolly" uses Depth Anything V2 Small parallax on the still image.
Run with the lab venv. Usage: maquiavel_final.py <scenes.json> <name> <talk_suffix>
"""
import json
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import measure
from montagem import VOICE_FX, write_ass
from run_test_b import SH, SW, estimate_depth, soften

LAB = Path(__file__).resolve().parent.parent
OUT = LAB / "outputs" / "maquiavel"
AUDIO = OUT / "audio"
FONTS = LAB / "inputs" / "fonts"
OW, OH, FPS = 1080, 1920, 30
LEAD, TAIL, XF = 0.3, 0.5, 0.5
X264 = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"]
SCENE_TALK = {"CENA_01": "cena1", "CENA_03": "cena3"}


def encoder(path):
    return subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
                             "-s", f"{OW}x{OH}", "-r", str(FPS), "-i", "-", *X264, str(path)], stdin=subprocess.PIPE)


def zoom_frame(frame, z):
    """Sub-pixel centred zoom with an affine warp (no integer rounding)."""
    m = np.float32([[z, 0, (1 - z) * OW / 2], [0, z, (1 - z) * OH / 2]])
    return cv2.warpAffine(frame, m, (OW, OH), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)


def render_talk(src, seconds, lead, path):
    """Talking-head clip, padded with held frames before (lead) and after (to fill the scene)."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(src), "-vf",
                          f"fps={FPS},scale={OW}:{OH}:flags=lanczos,tpad=start_mode=clone:start_duration={lead}"
                          f":stop_mode=clone:stop_duration=5", "-t", f"{seconds:.3f}",
                          "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True, check=True).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, OH, OW, 3)
    enc = encoder(path)
    n = len(frames)
    for i, f in enumerate(frames):
        t = i / max(n - 1, 1)
        enc.stdin.write(zoom_frame(f, 1.0 + 0.07 * t * t * (3 - 2 * t)).tobytes())
    enc.stdin.close()
    enc.wait()


def render_dolly(image, seconds, path):
    img = Image.open(LAB / image).convert("RGB").resize((SW, SH), Image.Resampling.LANCZOS)
    depth = soften(estimate_depth(img)[0])
    src = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)
    pu, pv = np.meshgrid((np.arange(OW, dtype=np.float32) + 0.5) / OW - 0.5,
                         (np.arange(OH, dtype=np.float32) + 0.5) / OH - 0.5)
    n = round(seconds * FPS)
    enc = encoder(path)
    for i in range(n):
        t = i / max(n - 1, 1)
        e = t * t * (3 - 2 * t)
        zoom = 1.06 + 0.08 * e
        d = cv2.remap(depth, (pu / zoom + 0.5) * SW, (pv / zoom + 0.5) * SH, cv2.INTER_LINEAR)
        for _ in range(2):
            z = zoom * (1 + 0.10 * e * d)
            mx, my = (pu / z + 0.5) * SW, (pv / z + 0.5) * SH
            d = cv2.remap(depth, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        enc.stdin.write(cv2.remap(src, mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT).tobytes())
    enc.stdin.close()
    enc.wait()


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


if __name__ == "__main__":
    scenes = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    name, talk_suffix = sys.argv[2], sys.argv[3]
    tts = {s["id"]: s for s in json.loads((AUDIO / "tts.json").read_text(encoding="utf-8"))["scenes"]}
    align = {s["id"]: s for s in json.loads((AUDIO / "alinhamento.json").read_text(encoding="utf-8"))["scenes"]}
    t0, stages = time.perf_counter(), {}

    starts, durations, cursor = [], [], 0.0
    for i, sc in enumerate(scenes):
        d = tts[sc["id"]]["duration_s"] + TAIL + (LEAD if i == 0 else 0)
        starts.append(cursor)
        durations.append(d)
        cursor += d
    total = cursor

    import wave
    with wave.open(str(AUDIO / f"{scenes[0]['id']}.wav")) as w:
        rate = w.getframerate()
    voice = np.zeros(round(total * rate), np.int16)
    timeline = []
    for i, sc in enumerate(scenes):
        with wave.open(str(AUDIO / f"{sc['id']}.wav")) as w:
            samples = np.frombuffer(w.readframes(w.getnframes()), np.int16)
        offset = starts[i] + (LEAD if i == 0 else 0)
        voice[round(offset * rate):round(offset * rate) + len(samples)] = samples
        timeline.append([{**w_, "start": w_["start"] + offset, "end": w_["end"] + offset}
                         for w_ in align[sc["id"]]["words"]])
    with wave.open(str(AUDIO / "narracao.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(voice.tobytes())

    clips = []
    for i, sc in enumerate(scenes):
        t = time.perf_counter()
        seconds = durations[i] + (XF if i < len(scenes) - 1 else 0)
        clip = OUT / "_cenas" / f"{name}_{sc['id']}.mp4"
        clip.parent.mkdir(parents=True, exist_ok=True)
        if sc["mode"] == "fala":
            render_talk(LAB / "outputs" / "sadtalker" / f"{SCENE_TALK[sc['id']]}_sadtalker_{talk_suffix}.mp4",
                        seconds, LEAD if i == 0 else 0, clip)
        else:
            render_dolly(sc["image"], seconds, clip)
        clips.append(clip)
        stages[f"render_{sc['id']}_{sc['mode']}_s"] = round(time.perf_counter() - t, 2)

    t = time.perf_counter()
    graph, last, acc = [], "0:v", 0.0
    for i in range(1, len(clips)):
        acc += durations[i - 1]
        graph.append(f"[{last}][{i}:v]xfade=transition=fade:duration={XF}:offset={acc:.3f}[x{i}]")
        last = f"x{i}"
    base = OUT / f"_{name}_base.mp4"
    run(["ffmpeg", "-hide_banner", "-y", *sum((["-i", str(c)] for c in clips), []),
         "-filter_complex", ";".join(graph), "-map", f"[{last}]", "-t", f"{total:.3f}", *X264, str(base)])

    music = AUDIO / "musica_sintetica.wav"
    pad = "+".join(f"0.18*sin(2*PI*{f}*t)" for f in (98, 116.54, 146.83, 196, 293.66))  # G minor pad
    run(["ffmpeg", "-hide_banner", "-y", "-f", "lavfi", "-i",
         f"aevalsrc='({pad})*(0.75+0.25*sin(2*PI*0.2*t))':s=48000:d={total + 1:.2f}",
         "-af", "lowpass=f=1200,aecho=0.8:0.6:140|280:0.3|0.2,afade=t=in:d=1.5", "-ac", "2", str(music)])
    write_ass(OUT / f"{name}_karaoke.ass", timeline, True)
    ass = (OUT / f"{name}_karaoke.ass").as_posix().replace(":", "\\:")
    fonts = FONTS.as_posix().replace(":", "\\:")
    mix = (f"[0:a]aresample=48000,aformat=channel_layouts=stereo,{VOICE_FX},loudnorm=I=-14:TP=-1.5:LRA=11,"
           f"asplit[v][sc];[1:a]volume=0.30,afade=t=out:st={total - 1.5:.2f}:d=1.5,atrim=0:{total:.3f}[m];"
           "[m][sc]sidechaincompress=threshold=0.02:ratio=6:attack=20:release=500:makeup=1[md];"
           "[v][md]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.9[a]")
    out = OUT / f"{name}.mp4"
    r = measure.run(["ffmpeg", "-hide_banner", "-y", "-i", str(AUDIO / "narracao.wav"), "-i", str(music),
                     "-i", str(base), "-filter_complex", f"{mix};[2:v]subtitles='{ass}':fontsdir='{fonts}'[vout]",
                     "-map", "[vout]", "-map", "[a]", *X264, "-c:a", "aac", "-b:a", "192k",
                     "-movflags", "+faststart", str(out)], log_path=OUT / f"{name}.log")
    stages["transicoes_legenda_audio_s"] = round(time.perf_counter() - t, 2)
    summary = {"test": "C+montagem", "name": name, "date": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "video_duration_s": round(total, 3), "stages": stages, "final_rc": r["returncode"],
               "scenes": [{"id": s["id"], "mode": s["mode"], "start_s": round(a, 2), "duration_s": round(d, 2)}
                          for s, a, d in zip(scenes, starts, durations)],
               "talk_clips": f"SadTalker {talk_suffix}", "voice": "Kokoro pm_alex",
               "wall_total_s_sem_sadtalker": round(time.perf_counter() - t0, 2), "output": str(out)}
    (LAB / "benchmarks" / f"MAQ_{name}.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                                                         encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
