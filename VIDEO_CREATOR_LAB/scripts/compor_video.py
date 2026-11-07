"""Compose a finished video from a template, a scenes file and an already-prepared work folder.

The work folder must contain audio/<CENA>.wav, audio/tts.json, audio/alinhamento.json and, for "fala"
scenes, fala/<CENA>.mp4 (SadTalker). Run with the lab venv.
Usage: compor_video.py <template.json> <cenas.json> <workdir> <output.mp4>
"""
import json
import subprocess
import sys
import time
import wave
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from montagem import VOICE_FX, write_ass
from run_test_b import estimate_depth, soften
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "smart_motion"))
import smart_motion  # noqa: E402

LAB = Path(__file__).resolve().parent.parent
FONTS = LAB / "inputs" / "fonts"


def ease(t):
    return t * t * (3 - 2 * t)


class Composer:
    def __init__(self, tpl):
        v = tpl["video"]
        self.tpl, self.W, self.H, self.FPS = tpl, v["largura"], v["altura"], v["fps"]
        self.SW, self.SH = 2 * self.W, 2 * self.H  # working source size (2x output), any aspect
        self.enc_args = ["-c:v", v["codec"], "-preset", v["preset"], "-crf", str(v["crf"]), "-pix_fmt", "yuv420p"]

    def encoder(self, path):
        return subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
                                 "-pix_fmt", "bgr24", "-s", f"{self.W}x{self.H}", "-r", str(self.FPS), "-i", "-",
                                 *self.enc_args, str(path)], stdin=subprocess.PIPE)

    def zoom(self, frame, z):
        m = np.float32([[z, 0, (1 - z) * self.W / 2], [0, z, (1 - z) * self.H / 2]])
        return cv2.warpAffine(frame, m, (self.W, self.H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)

    def talk(self, src, seconds, lead, path):
        cfg = self.tpl["modos_de_cena"]["fala"]["zoom_lento"]
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(src), "-vf",
                              f"fps={self.FPS},scale={self.W}:{self.H}:force_original_aspect_ratio=increase:flags=lanczos,"
                              f"crop={self.W}:{self.H},tpad=start_mode=clone:"
                              f"start_duration={lead}:stop_mode=clone:stop_duration=5", "-t", f"{seconds:.3f}",
                              "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True, check=True).stdout
        frames = np.frombuffer(raw, np.uint8).reshape(-1, self.H, self.W, 3)
        enc = self.encoder(path)
        for i, f in enumerate(frames):
            e = ease(i / max(len(frames) - 1, 1))
            enc.stdin.write(self.zoom(f, cfg["de"] + (cfg["ate"] - cfg["de"]) * e).tobytes())
        enc.stdin.close()
        enc.wait()

    def still(self, image, seconds, path, depth_gain, z0, z1):
        img = Image.open(image).convert("RGB")
        w, h = img.size
        if abs(w / h - self.W / self.H) > 0.01:  # centre-crop to the output aspect
            cw = round(h * self.W / self.H)
            img = img.crop(((w - cw) // 2, 0, (w - cw) // 2 + cw, h))
        SW, SH = self.SW, self.SH
        img = img.resize((SW, SH), Image.Resampling.LANCZOS)
        depth = soften(estimate_depth(img, (SH, SW))[0]) if depth_gain else np.zeros((SH, SW), np.float32)
        src = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)
        pu, pv = np.meshgrid((np.arange(self.W, dtype=np.float32) + 0.5) / self.W - 0.5,
                             (np.arange(self.H, dtype=np.float32) + 0.5) / self.H - 0.5)
        n = round(seconds * self.FPS)
        enc = self.encoder(path)
        for i in range(n):
            e = ease(i / max(n - 1, 1))
            zoom = z0 + (z1 - z0) * e
            d = cv2.remap(depth, (pu / zoom + 0.5) * SW, (pv / zoom + 0.5) * SH, cv2.INTER_LINEAR)
            for _ in range(2):
                z = zoom * (1 + depth_gain * e * d)
                mx, my = (pu / z + 0.5) * SW, (pv / z + 0.5) * SH
                d = cv2.remap(depth, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            enc.stdin.write(cv2.remap(src, mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT).tobytes())
        enc.stdin.close()
        enc.wait()


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def compose(tpl, scenes, work, out):
    c = Composer(tpl)
    tm = tpl["tempo"]
    lead, tail, xf = tm["respiro_inicio_s"], tm["respiro_fim_cena_s"], tm["transicao_s"]
    audio = work / "audio"
    tts = {s["id"]: s for s in json.loads((audio / "tts.json").read_text(encoding="utf-8"))["scenes"]}
    align = {s["id"]: s for s in json.loads((audio / "alinhamento.json").read_text(encoding="utf-8"))["scenes"]}
    stages = {}

    starts, durations, cursor = [], [], 0.0
    for i, sc in enumerate(scenes):
        d = tts[sc["id"]]["duration_s"] + tail + (lead if i == 0 else 0)
        starts.append(cursor)
        durations.append(d)
        cursor += d
    total = cursor

    with wave.open(str(audio / f"{scenes[0]['id']}.wav")) as w:
        rate = w.getframerate()
    voice = np.zeros(round(total * rate), np.int16)
    timeline = []
    for i, sc in enumerate(scenes):
        with wave.open(str(audio / f"{sc['id']}.wav")) as w:
            samples = np.frombuffer(w.readframes(w.getnframes()), np.int16)
        offset = starts[i] + (lead if i == 0 else 0)
        voice[round(offset * rate):round(offset * rate) + len(samples)] = samples
        timeline.append([{**x, "start": x["start"] + offset, "end": x["end"] + offset}
                         for x in align[sc["id"]]["words"]])
    with wave.open(str(audio / "narracao.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(voice.tobytes())

    modes = tpl["modos_de_cena"]
    clips = []
    for i, sc in enumerate(scenes):
        t = time.perf_counter()
        seconds = durations[i] + (xf if i < len(scenes) - 1 else 0)
        clip = work / "cenas" / f"{sc['id']}.mp4"
        clip.parent.mkdir(exist_ok=True)
        image = Path(sc["image"]) if Path(sc["image"]).is_absolute() else LAB / sc["image"]
        if sc["mode"] == "fala":
            c.talk(work / "fala" / f"{sc['id']}.mp4", seconds, lead if i == 0 else 0, clip)
        elif sc["mode"] == "dolly":
            m = modes["dolly"]
            c.still(image, seconds, clip, m["ganho_profundidade"], m["zoom"]["de"], m["zoom"]["ate"])
        else:
            m = modes["zoom"]
            c.still(image, seconds, clip, 0.0, m["zoom"]["de"], m["zoom"]["ate"])
        clips.append(clip)
        stages[f"{sc['id']}_{sc['mode']}_s"] = round(time.perf_counter() - t, 2)

    t = time.perf_counter()
    graph, last, acc = [], "0:v", 0.0
    for i in range(1, len(clips)):
        acc += durations[i - 1]
        graph.append(f"[{last}][{i}:v]xfade=transition={tm['transicao']}:duration={xf}:offset={acc:.3f}[x{i}]")
        last = f"x{i}"
    base = work / "_base.mp4"
    run(["ffmpeg", "-hide_banner", "-y", *sum((["-i", str(p)] for p in clips), []),
         "-filter_complex", ";".join(graph) or "[0:v]null[x0]", "-map", f"[{last if graph else 'x0'}]",
         "-t", f"{total:.3f}", *c.enc_args, str(base)])

    ass_path = work / "legenda.ass"
    lg = tpl["legenda"]
    style = {**lg.get("ass", {}), "margem_inferior": lg.get("margem_inferior", 560)}
    write_ass(ass_path, timeline, lg["estilo"] == "karaoke", style, (c.W, c.H))
    ass = ass_path.as_posix().replace(":", "\\:")
    fonts = Path(lg.get("fontes_dir") or FONTS).as_posix().replace(":", "\\:")
    lufs = tpl["voz"]["loudness_lufs"]
    voice_chain = (f"[0:a]aresample=48000,aformat=channel_layouts=stereo,{VOICE_FX},"
                   f"loudnorm=I={lufs}:TP=-1.5:LRA=11,aresample=48000")  # loudnorm upsamples internally
    mus = tpl["musica"]
    inputs = ["-i", str(audio / "narracao.wav"), "-i", str(base)]
    if mus.get("arquivo"):
        dk = mus["ducking"]
        inputs += ["-stream_loop", "-1", "-i", mus["arquivo"]]
        mix = (f"{voice_chain},asplit[v][sc];[2:a]aresample=48000,aformat=channel_layouts=stereo,"
               f"volume={mus['volume']},afade=t=in:d=1,afade=t=out:st={total - 1.5:.2f}:d=1.5,atrim=0:{total:.3f}[m];"
               f"[m][sc]sidechaincompress=threshold={dk['limiar']}:ratio={dk['razao']}:attack={dk['ataque_ms']}:"
               f"release={dk['liberacao_ms']}:makeup=1[md];[v][md]amix=inputs=2:duration=first:normalize=0,"
               "alimiter=limit=0.9[a]")
    else:
        mix = f"{voice_chain},alimiter=limit=0.9[a]"
    # Smart Motion: animações marcadas no roteiro, na mesma passada (antes da legenda, que fica por cima)
    sm_inputs, sm_graph, vlast, sm_info = smart_motion.aplicar_no_filtro(
        tpl, "F01", scenes, timeline, total, work, inputs.count("-i"), "1:v")
    stages["smart_motion"] = sm_info
    inputs += sm_inputs
    sm_chain = (";".join(sm_graph) + ";") if sm_graph else ""
    run(["ffmpeg", "-hide_banner", "-y", *inputs, "-filter_complex",
         f"{mix};{sm_chain}[{vlast}]subtitles='{ass}':fontsdir='{fonts}'[vout]", "-map", "[vout]", "-map", "[a]",
         *c.enc_args, "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)])
    base.unlink()
    stages["transicoes_legenda_audio_s"] = round(time.perf_counter() - t, 2)
    return {"video_duration_s": round(total, 3), "stages": stages, "music": mus.get("arquivo"),
            "scenes": [{"id": s["id"], "mode": s["mode"], "start_s": round(a, 2), "duration_s": round(d, 2)}
                       for s, a, d in zip(scenes, starts, durations)]}


if __name__ == "__main__":
    tpl = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    scenes = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    print(json.dumps(compose(tpl, scenes, Path(sys.argv[3]), Path(sys.argv[4])), ensure_ascii=False))
