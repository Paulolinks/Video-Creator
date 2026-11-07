"""T02 interview composer: alternating speakers, each with own background loop, side and portrait.

Per scene (Python + OpenCV, frame by frame): looping background + breathing cut-out portrait + waveform
driven by the scene audio. Then xfade between scenes, and captions/labels via ASS/libass in FFmpeg.
Run with the lab venv. Usage: compor_entrevista.py <template.json> <roteiro.json> <workdir> <out.mp4>
"""
import hashlib
import json
import subprocess
import sys
import time
import wave
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

LAB = Path(__file__).resolve().parent.parent
FONTS = LAB / "inputs" / "fonts"


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def mean_luma(video):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", "1", "-i", str(video), "-vf", "scale=160:90,format=gray",
                          "-frames:v", "5", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    return float(np.frombuffer(raw, np.uint8).mean())


def prepare_background(src, dst, tpl):
    """Cover-crop to 9:16, darken toward a target luma, light blur, and make a seamless crossfade loop."""
    W, H, fps = tpl["video"]["largura"], tpl["video"]["altura"], tpl["video"]["fps"]
    bg = tpl["fundo"]
    hh, mm, ss = (subprocess.run(["ffmpeg", "-hide_banner", "-i", str(src)], capture_output=True, text=True)
                  .stderr.split("Duration: ")[1].split(",")[0].split(":"))
    dur = int(hh) * 3600 + int(mm) * 60 + float(ss)
    gain = min(1.0, bg["escurecer_ate_luma"] / max(mean_luma(src), 1))
    xf = bg["loop_crossfade_s"]
    look = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps},"
            f"eq=brightness=0:contrast=1:saturation=0.9,colorchannelmixer=rr={gain:.3f}:gg={gain:.3f}:bb={gain:.3f},"
            f"gblur=sigma={bg['desfoque_sigma']},format=yuv420p")
    graph = (f"[0:v]{look},split[a][b];[a]trim=start={xf},setpts=PTS-STARTPTS,fps={fps}[body];"
             f"[b]trim=0:{xf},setpts=PTS-STARTPTS,fps={fps}[head];"
             f"[body][head]xfade=transition=fade:duration={xf}:offset={dur - 2 * xf:.3f}[v]")
    tmp = dst.with_suffix(".tmp.mp4")  # never leave a broken cache file behind
    run(["ffmpeg", "-hide_banner", "-y", "-i", str(src), "-filter_complex", graph, "-map", "[v]", "-an",
         "-c:v", "libx264", "-crf", "16", "-preset", "fast", str(tmp)])
    tmp.replace(dst)
    return {"gain": round(gain, 3), "loop_s": round(dur - xf, 2)}


def read_wav(path):
    with wave.open(str(path)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768, w.getframerate()


class Waveform:
    """Bars from log-spaced FFT bands of the scene audio, smoothed with attack/decay."""

    def __init__(self, audio, rate, cfg, fps):
        self.audio, self.rate, self.cfg, self.fps = audio, rate, cfg, fps
        n = cfg["barras"] // 2
        self.edges = np.geomspace(90, 5000, n + 1)
        self.level = np.zeros(n)

    def heights(self, t):
        win = 2048
        c = int(t * self.rate)
        seg = self.audio[max(0, c - win // 2):c + win // 2]
        mags = np.zeros(len(self.level))
        if len(seg) == win:
            spec = np.abs(np.fft.rfft(seg * np.hanning(win)))
            freqs = np.fft.rfftfreq(win, 1 / self.rate)
            for i in range(len(mags)):
                band = spec[(freqs >= self.edges[i]) & (freqs < self.edges[i + 1])]
                mags[i] = band.mean() if band.size else 0
        db = np.clip((20 * np.log10(mags + 1e-6) + 10) / 40, 0, 1)
        self.level = np.where(db > self.level, 0.6 * db + 0.4 * self.level, 0.82 * self.level)
        half = self.level
        return np.concatenate([half[::-1], half])  # mirrored: low frequencies in the centre

    def draw(self, frame, t, x0):
        cfg = self.cfg
        h = self.heights(t)
        overlay = frame.copy()
        step = cfg["largura_barra"] + cfg["espaco"]
        cy = cfg["centro_y"]
        for i, v in enumerate(h):
            x = x0 + i * step + cfg["largura_barra"] // 2
            half = max(3, int(v * cfg["altura_max"] / 2))
            cv2.line(overlay, (x, cy - half), (x, cy + half), tuple(cfg["cor"][::-1]), cfg["largura_barra"], cv2.LINE_AA)
        a = cfg["opacidade"]
        y0, y1 = cy - cfg["altura_max"] // 2 - 10, cy + cfg["altura_max"] // 2 + 10
        frame[y0:y1] = cv2.addWeighted(overlay[y0:y1], a, frame[y0:y1], 1 - a, 0)


def render_scene(tpl, char, bg_loop, audio_path, lead, seconds, out):
    W, H, fps = tpl["video"]["largura"], tpl["video"]["altura"], tpl["video"]["fps"]
    rc = tpl["retrato"]
    png = Image.open(char["imagem"]).convert("RGBA")
    rgba = np.asarray(png).astype(np.float32)
    rgb = cv2.cvtColor(np.ascontiguousarray(rgba[..., :3]), cv2.COLOR_RGB2BGR)
    alpha = rgba[..., 3:] / 255.0
    pw, ph = png.size
    base = min(rc["largura"] / pw, rc.get("altura_max", 10**9) / ph)  # altura_max: 16:9 keeps the head in frame
    left = char["lado"] == "esquerda"
    # anchor = bottom-centre of the portrait on screen
    ax = (-rc["deslocamento_borda"] if left else W - rc["largura"] + rc["deslocamento_borda"]) + rc["largura"] / 2
    ay = H
    wave_x0 = (W - 40 - (tpl["onda"]["barras"] * (tpl["onda"]["largura_barra"] + tpl["onda"]["espaco"]))) if left else 40
    audio, rate = read_wav(audio_path)
    wf = Waveform(audio, rate, tpl["onda"], fps)
    n = round(seconds * fps)
    bg = subprocess.Popen(["ffmpeg", "-v", "error", "-stream_loop", "-1", "-i", str(bg_loop), "-t", f"{seconds:.3f}",
                           "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
                            "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-c:v", tpl["video"]["codec"], "-preset",
                            tpl["video"]["preset"], "-crf", str(tpl["video"]["crf"]), "-pix_fmt", "yuv420p", str(out)],
                           stdin=subprocess.PIPE)
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
        al = cv2.warpAffine(alpha, m_roi, (W, H - y_top), flags=cv2.INTER_LINEAR, borderValue=0)[..., None]
        frame[roi] = (fg * al + frame[roi].astype(np.float32) * (1 - al)).astype(np.uint8)
        audio_t = t - lead
        if 0 <= audio_t:
            wf.draw(frame, audio_t, wave_x0)
        else:
            wf.draw(frame, -1, wave_x0)
        enc.stdin.write(frame.tobytes())
    bg.stdout.close()
    bg.wait()
    enc.stdin.close()
    enc.wait()


def ass_time(s):
    cs = max(0, round(s * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02}:{cs // 100 % 60:02}.{cs % 100:02}"


def groups(words, max_words, max_chars):
    out, cur = [], []
    for w in words:
        if cur and (len(cur) >= max_words or len(" ".join(x["word"] for x in cur + [w])) > max_chars):
            out.append(cur)
            cur = []
        cur.append(w)
        if w["word"][-1] in ".!?;:":
            out.append(cur)
            cur = []
    return out + ([cur] if cur else [])


def write_ass(path, tpl, timeline, labels, total):
    """Captions + optional labels. 'karaoke_cor' = v3 style: each word turns from white to gold as it is spoken
    (ASS \\k). 'caixa' = white text with a yellow box on the active word."""
    W, H = tpl["video"]["largura"], tpl["video"]["altura"]
    lg, rt = tpl["legenda"], tpl["rotulos"]
    y = lg["centro_y"]
    bold = -1 if lg.get("negrito", True) else 0
    head = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0",
            "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
            "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
            "MarginR, MarginV, Encoding",
            f"Style: Kara,{lg['fonte']},{lg['tamanho']},{lg.get('cor_falada', '&H0045D7FF')},"
            f"{lg.get('cor_aguardando', '&H00FFFFFF')},&H00000000,&H64000000,{bold},0,0,0,100,100,0,0,"
            f"1,{lg['contorno']},{lg.get('sombra', 2)},5,60,60,0,1",
            f"Style: Txt,{lg['fonte']},{lg['tamanho']},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,{bold},0,0,0,100,100,"
            f"0,0,1,{lg['contorno']},3,5,60,60,0,1",
            f"Style: Box,{lg['fonte']},{lg['tamanho']},&H00FFFFFF,&H00FFFFFF,&H0000C8FF,&H00000000,{bold},0,0,0,100,100,"
            "0,0,3,10,0,5,60,60,0,1",
            "Style: Aviso,Poppins ExtraBold,30,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,1,0,"
            "1,2,0,5,40,40,0,1",
            "Style: Nome,Poppins ExtraBold,46,&H0000D7FF,&H0000D7FF,&H00000000,&H64000000,0,0,0,0,100,100,1,0,"
            "1,4,0,5,40,40,0,1", "", "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    ev = []
    if rt.get("aviso"):
        ev.append(f"Dialogue: 3,{ass_time(0)},{ass_time(total)},Aviso,,0,0,0,,{{\\pos({W // 2},{rt['aviso_y']})}}"
                  f"{rt['aviso']}")
    if rt.get("mostrar_nomes", True):
        for start, end, name in labels:
            ev.append(f"Dialogue: 3,{ass_time(start)},{ass_time(end)},Nome,,0,0,0,,"
                      f"{{\\pos({W // 2},{rt['nome_y']})\\fad(250,250)}}{name}")
    pos = f"{{\\pos({W // 2},{y})}}"
    for scene_words in timeline:
        gs = groups(scene_words, lg["max_palavras"], lg["max_caracteres"])
        for gi, g in enumerate(gs):
            g_end = gs[gi + 1][0]["start"] if gi + 1 < len(gs) else g[-1]["end"] + 0.35
            words = [w["word"].upper() if lg["maiusculas"] else w["word"] for w in g]
            if lg.get("estilo", "karaoke_cor") == "karaoke_cor":
                parts, t = [], g[0]["start"]
                for w, text in zip(g, words):
                    parts.append(f"{{\\k{max(1, round((w['end'] - t) * 100))}}}{text}")
                    t = w["end"]
                ev.append(f"Dialogue: 0,{ass_time(g[0]['start'])},{ass_time(g_end)},Kara,,0,0,0,,{pos}{' '.join(parts)}")
                continue
            ev.append(f"Dialogue: 0,{ass_time(g[0]['start'])},{ass_time(g_end)},Txt,,0,0,0,,{pos}{' '.join(words)}")
            for wi, w in enumerate(g):
                w_end = g[wi + 1]["start"] if wi + 1 < len(g) else g_end
                parts = [(f"{{\\alpha&H00&}}{x}{{\\alpha&HFF&}}" if k == wi else x) for k, x in enumerate(words)]
                ev.append(f"Dialogue: 1,{ass_time(w['start'])},{ass_time(w_end)},Box,,0,0,0,,{pos}{{\\alpha&HFF&}}"
                          + " ".join(parts))
    path.write_text("\n".join(head + ev) + "\n", encoding="utf-8")


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

    loops = {}
    for name, ch in chars.items():
        # key by the full path: library backgrounds are all called "arquivo.mp4" in different folders
        src = Path(ch["fundo"]).resolve()
        key = f"{src.parent.name}_{src.stem}_{hashlib.sha1(str(src).encode()).hexdigest()[:8]}"
        dst = work / "fundos" / f"{key}_loop.mp4"
        dst.parent.mkdir(exist_ok=True)
        if not dst.exists():
            stages[f"fundo_{key}"] = prepare_background(ch["fundo"], dst, tpl)
        loops[name] = dst

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

    clips = []
    for i, sc in enumerate(scenes):
        t = time.perf_counter()
        seconds = durations[i] + (xf if i < len(scenes) - 1 else 0)
        clip = work / "cenas" / f"{sc['id']}.mp4"
        clip.parent.mkdir(exist_ok=True)
        render_scene(tpl, chars[sc["personagem"]], loops[sc["personagem"]], tts[sc["id"]]["wav"],
                     lead if i == 0 else 0, seconds, clip)
        clips.append(clip)
        stages[f"render_{sc['id']}_s"] = round(time.perf_counter() - t, 2)

    t = time.perf_counter()
    graph, last, acc = [], "0:v", 0.0
    for i in range(1, len(clips)):
        acc += durations[i - 1]
        graph.append(f"[{last}][{i}:v]xfade=transition=fade:duration={xf}:offset={acc:.3f}[x{i}]")
        last = f"x{i}"
    base = work / "_base.mp4"
    v = tpl["video"]
    enc = ["-c:v", v["codec"], "-preset", v["preset"], "-crf", str(v["crf"]), "-pix_fmt", "yuv420p"]
    run(["ffmpeg", "-hide_banner", "-y", *sum((["-i", str(c)] for c in clips), []), "-filter_complex",
         ";".join(graph), "-map", f"[{last}]", "-t", f"{total:.3f}", *enc, str(base)])
    ass_path = work / "legenda.ass"
    write_ass(ass_path, tpl, timeline, labels, total)
    ass = ass_path.as_posix().replace(":", "\\:")
    fonts = Path(tpl["legenda"].get("fontes_dir") or FONTS).as_posix().replace(":", "\\:")
    lufs = tpl["voz"]["loudness_final_lufs"]
    rt = tpl["rotulos"]
    inputs = ["-i", str(audio / "narracao.wav"), "-i", str(base)]
    video = f"[1:v]subtitles='{ass}':fontsdir='{fonts}'[vout]"
    if rt.get("logo"):  # channel logo, centred at the top
        inputs += ["-i", rt["logo"]]
        video = (f"[1:v]subtitles='{ass}':fontsdir='{fonts}'[s];[2:v]scale={rt['logo_largura']}:-1[lg];"
                 f"[s][lg]overlay=(W-w)/2:{rt['logo_y']}[vout]")
    voice = f"[0:a]aresample=48000,aformat=channel_layouts=stereo,loudnorm=I={lufs}:TP=-1.5:LRA=11,aresample=48000"
    mus = tpl.get("musica") or {}
    if mus.get("arquivo"):  # background music, ducked under the voices
        dk = mus.get("ducking") or {"limiar": 0.02, "razao": 6, "ataque_ms": 20, "liberacao_ms": 500}
        idx = len(inputs) // 2
        inputs += ["-stream_loop", "-1", "-i", mus["arquivo"]]
        audio_graph = (f"{voice},asplit[v][sc];[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,"
                       f"volume={mus.get('volume', 0.25)},afade=t=in:d=1,afade=t=out:st={max(total - 2, 0):.2f}:d=2,"
                       f"atrim=0:{total:.3f}[m];[m][sc]sidechaincompress=threshold={dk['limiar']}:ratio={dk['razao']}:"
                       f"attack={dk['ataque_ms']}:release={dk['liberacao_ms']}:makeup=1[md];"
                       "[v][md]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.9[a]")
    else:
        audio_graph = f"{voice},alimiter=limit=0.9[a]"
    run(["ffmpeg", "-hide_banner", "-y", *inputs, "-filter_complex", f"{audio_graph};{video}",
         "-map", "[vout]", "-map", "[a]", *enc, "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)])
    base.unlink()
    stages["transicoes_legenda_audio_s"] = round(time.perf_counter() - t, 2)
    stages["composicao_total_s"] = round(time.perf_counter() - t0, 2)
    return {"video_duration_s": round(total, 3), "stages": stages,
            "scenes": [{"id": s["id"], "personagem": s["personagem"], "start_s": round(a, 2), "duration_s": round(d, 2)}
                       for s, a, d in zip(scenes, starts, durations)]}


if __name__ == "__main__":
    tpl = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    roteiro = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    print(json.dumps(compose(tpl, roteiro, Path(sys.argv[3]), Path(sys.argv[4])), ensure_ascii=False, indent=1))
