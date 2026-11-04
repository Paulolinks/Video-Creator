"""Faster T02 composer: same look as compor_entrevista.py (it reuses its drawing and caption code), built for speed.

- scenes are drawn in parallel processes, and the per-scene clips are encoded on the GPU (NVENC) at high quality:
  they are temporary, only the final pass needs the template's quality;
- one final pass does transitions + captions + labels + audio (+ the cover over the first second), instead of two;
- final encoder from the template: video.codec_final = "h264_nvenc" (fast) or the template's codec (libx264);
- prepared backgrounds are cached in .cache/fundos and reused by later videos.
Usage: compor_entrevista_rapido.py <template.json> <roteiro.json> <workdir> <out.mp4>
"""
import hashlib
import json
import os
import subprocess
import sys
import time
import wave
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from compor_entrevista import FONTS, Waveform, prepare_background, read_wav, run, write_ass

NVENC_TEMP = ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", "14", "-b:v", "0", "-pix_fmt", "yuv420p"]
X264_TEMP = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "14", "-pix_fmt", "yuv420p"]
BG_CACHE = Path(__file__).resolve().parent.parent / ".cache" / "fundos"


def nvenc_ok():
    """True when this machine can encode with NVENC (NVIDIA GPU + driver)."""
    r = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=black:s=256x256:d=0.1", "-c:v", "h264_nvenc",
                        "-f", "null", "-"], capture_output=True)
    return r.returncode == 0


def final_encoder(v, nvenc):
    if v.get("codec_final") == "h264_nvenc" and nvenc:
        return ["-c:v", "h264_nvenc", "-preset", "p6", "-tune", "hq", "-rc", "vbr", "-cq", str(v.get("cq_final", 19)),
                "-b:v", "0", "-profile:v", "high", "-pix_fmt", "yuv420p"]
    return ["-c:v", v["codec"], "-preset", v["preset"], "-crf", str(v["crf"]), "-pix_fmt", "yuv420p"]


def render_scene(args):
    """Same drawing as compor_entrevista.render_scene; only the encoder differs. Runs in a worker process."""
    tpl, char, bg_loop, audio_path, lead, seconds, out, enc_args = args
    t0 = time.perf_counter()
    cv2.setNumThreads(2)  # several scenes run at once: keep each process light
    W, H, fps = tpl["video"]["largura"], tpl["video"]["altura"], tpl["video"]["fps"]
    rc = tpl["retrato"]
    png = Image.open(char["imagem"]).convert("RGBA")
    rgba = np.asarray(png)
    rgb = cv2.cvtColor(np.ascontiguousarray(rgba[..., :3]), cv2.COLOR_RGB2BGR)
    alpha = np.ascontiguousarray(rgba[..., 3].astype(np.float32) / 255.0)
    pw, ph = png.size
    base = rc["largura"] / pw
    left = char["lado"] == "esquerda"
    ax = (-rc["deslocamento_borda"] if left else W - rc["largura"] + rc["deslocamento_borda"]) + rc["largura"] / 2
    ay = H
    wave_x0 = (W - 40 - (tpl["onda"]["barras"] * (tpl["onda"]["largura_barra"] + tpl["onda"]["espaco"]))) if left else 40
    audio, rate = read_wav(audio_path)
    wf = Waveform(audio, rate, tpl["onda"], fps)
    n = round(seconds * fps)
    bg = subprocess.Popen(["ffmpeg", "-v", "error", "-stream_loop", "-1", "-i", str(bg_loop), "-t", f"{seconds:.3f}",
                           "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL)  # it is closed early on purpose: hide the broken-pipe noise
    enc = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
                            "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", *enc_args, str(out)], stdin=subprocess.PIPE)
    size = W * H * 3
    for i in range(n):
        buf = bg.stdout.read(size)
        if len(buf) < size:
            break
        frame = np.frombuffer(buf, np.uint8).reshape(H, W, 3).copy()
        t = i / fps
        p = i / max(n - 1, 1)
        s = base * (rc["respiracao"]["de"] + (rc["respiracao"]["pico"] - rc["respiracao"]["de"]) * np.sin(np.pi * p))
        m = np.float32([[s, 0, ax - s * pw / 2], [0, s, ay - s * ph]])
        y_top = max(0, int(ay - s * ph) - 2)
        roi = slice(y_top, H)
        m_roi = m.copy()
        m_roi[1, 2] -= y_top
        fg = cv2.warpAffine(rgb, m_roi, (W, H - y_top), flags=cv2.INTER_CUBIC, borderValue=0)
        al = cv2.warpAffine(alpha, m_roi, (W, H - y_top), flags=cv2.INTER_LINEAR, borderValue=0)
        # same alpha blend as the original, in OpenCV (~15x faster, and saturates instead of wrapping at the edges)
        frame[roi] = cv2.blendLinear(fg, frame[roi], al, 1 - al)
        audio_t = t - lead
        wf.draw(frame, audio_t if audio_t >= 0 else -1, wave_x0)
        enc.stdin.write(frame.tobytes())
    bg.stdout.close()
    bg.wait()
    enc.stdin.close()
    enc.wait()
    if enc.returncode:
        raise RuntimeError(f"falha ao codificar {Path(out).name}")
    return round(time.perf_counter() - t0, 2)


def compose(tpl, roteiro, work, out):
    W, H, fps = tpl["video"]["largura"], tpl["video"]["altura"], tpl["video"]["fps"]
    tm = tpl["tempo"]
    lead, tail, xf = tm["respiro_inicio_s"], tm["respiro_fim_cena_s"], tm["transicao_s"]
    audio = work / "audio"
    tts = {s["id"]: s for s in json.loads((audio / "tts.json").read_text(encoding="utf-8"))["scenes"]}
    align = {s["id"]: s for s in json.loads((audio / "alinhamento.json").read_text(encoding="utf-8"))["scenes"]}
    chars = roteiro["personagens"]
    scenes = roteiro["cenas"]
    stages, t0 = {}, time.perf_counter()
    nvenc = nvenc_ok()
    stages["nvenc"] = nvenc

    loops = {}
    for name, ch in chars.items():  # prepared backgrounds are shared by every video (same file + same look)
        src = Path(ch["fundo"]).resolve()
        st = src.stat()
        look = json.dumps([str(src), st.st_size, st.st_mtime, W, H, fps, tpl["fundo"]], sort_keys=True)
        key = f"{src.parent.name}_{src.stem}_{hashlib.sha1(look.encode()).hexdigest()[:10]}"
        dst = BG_CACHE / f"{key}_loop.mp4"
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            stages[f"fundo_{key}"] = prepare_background(ch["fundo"], dst, tpl)
        loops[name] = dst
    stages["fundos_s"] = round(time.perf_counter() - t0, 2)

    starts, durations, cursor = [], [], 0.0
    for i, sc in enumerate(scenes):
        d = tts[sc["id"]]["duration_s"] + tail + (lead if i == 0 else 0)
        starts.append(cursor)
        durations.append(d)
        cursor += d
    total = cursor

    rate = read_wav(tts[scenes[0]["id"]]["wav"])[1]
    voice = np.zeros(round(total * rate), np.float32)
    timeline, labels = [], []
    for i, sc in enumerate(scenes):
        samples, r = read_wav(tts[sc["id"]]["wav"])
        assert r == rate, "todas as falas devem ter a mesma taxa (normalizadas antes)"
        offset = starts[i] + (lead if i == 0 else 0)
        voice[round(offset * rate):round(offset * rate) + len(samples)] = samples
        timeline.append([{**w, "start": w["start"] + offset, "end": w["end"] + offset}
                         for w in align[sc["id"]]["words"]])
        simulated = chars[sc["personagem"]].get("simulado", sc["personagem"] != "PAULO")
        label = sc["personagem"] + (tpl["rotulos"]["sufixo_nome_simulado"] if simulated else "")
        labels.append((starts[i] + (0 if i == 0 else xf / 2), starts[i] + durations[i], label))
    with wave.open(str(audio / "narracao.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((np.clip(voice, -1, 1) * 32767).astype(np.int16).tobytes())

    t = time.perf_counter()
    (work / "cenas").mkdir(exist_ok=True)
    clips = [work / "cenas" / f"{sc['id']}.mp4" for sc in scenes]
    jobs = [(tpl, chars[sc["personagem"]], loops[sc["personagem"]], tts[sc["id"]]["wav"], lead if i == 0 else 0,
             durations[i] + (xf if i < len(scenes) - 1 else 0), clips[i], NVENC_TEMP if nvenc else X264_TEMP)
            for i, sc in enumerate(scenes)]
    workers = int(tpl["video"].get("cenas_em_paralelo") or min(4, max(1, (os.cpu_count() or 4) // 4)))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for sc, secs in zip(scenes, pool.map(render_scene, jobs)):
            stages[f"render_{sc['id']}_s"] = secs
    stages["cenas_paralelo"] = workers
    stages["cenas_total_s"] = round(time.perf_counter() - t, 2)

    # one final pass: transitions + captions/labels + logo + cover + audio
    t = time.perf_counter()
    ass_path = work / "legenda.ass"
    write_ass(ass_path, tpl, timeline, labels, total)
    ass = ass_path.as_posix().replace(":", "\\:")
    fonts = FONTS.as_posix().replace(":", "\\:")
    inputs = sum((["-i", str(c)] for c in clips), [])
    n_in = len(clips)  # input index of the next -i
    graph, last, acc = [], "0:v", 0.0
    for i in range(1, len(clips)):
        acc += durations[i - 1]
        graph.append(f"[{last}][{i}:v]xfade=transition=fade:duration={xf}:offset={acc:.3f}[x{i}]")
        last = f"x{i}"
    graph.append(f"[{last}]subtitles='{ass}':fontsdir='{fonts}'[s]")
    last = "s"
    rt = tpl["rotulos"]
    if rt.get("logo"):  # channel logo, centred at the top
        idx, n_in = n_in, n_in + 1
        inputs += ["-i", rt["logo"]]
        graph.append(f"[{idx}:v]scale={rt['logo_largura']}:-1[lg];[{last}][lg]overlay=(W-w)/2:{rt['logo_y']}[l]")
        last = "l"
    cover = tpl.get("capa") or {}
    if cover.get("arquivo") and Path(cover["arquivo"]).exists():  # thumbnail shown over the first second
        idx, n_in = n_in, n_in + 1
        sec = float(cover.get("segundos", 1.0))
        inputs += ["-loop", "1", "-t", str(sec), "-i", cover["arquivo"]]
        graph.append(f"[{idx}:v]scale={W}:{H}[cv];[{last}][cv]overlay=eof_action=pass:enable='lt(t,{sec})'[c]")
        last = "c"
        stages["capa_no_video"] = True
    lufs = tpl["voz"]["loudness_final_lufs"]
    vidx, n_in = n_in, n_in + 1
    inputs += ["-i", str(audio / "narracao.wav")]
    voice_f = f"[{vidx}:a]aresample=48000,aformat=channel_layouts=stereo,loudnorm=I={lufs}:TP=-1.5:LRA=11,aresample=48000"
    mus = tpl.get("musica") or {}
    if mus.get("arquivo"):  # background music, ducked under the voices
        dk = mus.get("ducking") or {"limiar": 0.02, "razao": 6, "ataque_ms": 20, "liberacao_ms": 500}
        midx, n_in = n_in, n_in + 1
        inputs += ["-stream_loop", "-1", "-i", mus["arquivo"]]
        graph.append(f"{voice_f},asplit[v][sc];[{midx}:a]aresample=48000,aformat=channel_layouts=stereo,"
                     f"volume={mus.get('volume', 0.25)},afade=t=in:d=1,afade=t=out:st={max(total - 2, 0):.2f}:d=2,"
                     f"atrim=0:{total:.3f}[m];[m][sc]sidechaincompress=threshold={dk['limiar']}:ratio={dk['razao']}:"
                     f"attack={dk['ataque_ms']}:release={dk['liberacao_ms']}:makeup=1[md];"
                     "[v][md]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.9[a]")
    else:
        graph.append(f"{voice_f},alimiter=limit=0.9[a]")
    run(["ffmpeg", "-hide_banner", "-y", *inputs, "-filter_complex", ";".join(graph), "-map", f"[{last}]",
         "-map", "[a]", "-t", f"{total:.3f}", *final_encoder(tpl["video"], nvenc), "-c:a", "aac", "-b:a", "192k",
         "-movflags", "+faststart", str(out)])
    stages["final_s"] = round(time.perf_counter() - t, 2)
    stages["composicao_total_s"] = round(time.perf_counter() - t0, 2)
    return {"video_duration_s": round(total, 3), "stages": stages,
            "scenes": [{"id": s["id"], "personagem": s["personagem"], "start_s": round(a, 2), "duration_s": round(d, 2)}
                       for s, a, d in zip(scenes, starts, durations)]}


if __name__ == "__main__":
    tpl = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    roteiro = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    print(json.dumps(compose(tpl, roteiro, Path(sys.argv[3]), Path(sys.argv[4])), ensure_ascii=False, indent=1))
