"""Test A: simple image animation with FFmpeg (zoom, pan, combined, transitions).

Each run writes outputs/ffmpeg/<name>.mp4, a log and benchmarks/A_<name>.json.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageStat

import measure

LAB = Path(__file__).resolve().parent.parent
OUT = LAB / "outputs" / "ffmpeg"
BENCH = LAB / "benchmarks"
IMG = {k: LAB / "inputs" / f"teste_{k}.png" for k in ("A_azul", "B_ambar", "C_verde")}

FPS, SECONDS = 30, 5
N = FPS * SECONDS
OW, OH = 1080, 1920
X264 = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
NVENC = ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "19", "-b:v", "0",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart"]

# Smoothstep easing over the clip: e goes 0 -> 1 with soft start and end.
E = f"(on/{N - 1})*(on/{N - 1})*(3-2*(on/{N - 1}))"
CENTER_X, CENTER_Y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"

MOVES = {
    "zoom_in": (f"1+0.25*{E}", CENTER_X, CENTER_Y),
    "zoom_out": (f"1.25-0.25*{E}", CENTER_X, CENTER_Y),
    "pan_h": ("1.25", f"(iw-iw/zoom)*{E}", CENTER_Y),
    "pan_v": ("1.25", CENTER_X, f"(ih-ih/zoom)*(1-{E})"),
    "combined": (f"1.1+0.2*{E}", f"(iw-iw/zoom)*(0.15+0.35*{E})", f"(ih-ih/zoom)*(0.2+0.3*{E})"),
}


def zoompan_filter(move, supersample):
    z, x, y = MOVES[move]
    pre = f"scale={OW * supersample}:{OH * supersample}:flags=lanczos,"
    return f"{pre}zoompan=z='{z}':x='{x}':y='{y}':d={N}:s={OW}x{OH}:fps={FPS},setsar=1"


def probe(path):
    """Read stream info with ffmpeg itself (no ffprobe in this FFmpeg build)."""
    err = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-map", "0:v:0", "-c", "copy",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    stream = re.search(r"Video: (\w+).*?, (\d+)x(\d+).*?, ([\d.]+) fps", err)
    hh, mm, ss = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err).groups()
    frames = re.findall(r"frame=\s*(\d+)", err)
    return {"width": int(stream.group(2)), "height": int(stream.group(3)), "fps": float(stream.group(4)),
            "codec": stream.group(1), "frames": int(frames[-1]) if frames else 0,
            "duration_s": round(int(hh) * 3600 + int(mm) * 60 + float(ss), 3),
            "size_mb": round(path.stat().st_size / 2**20, 2)}


def border_check(path, duration):
    """Darkest border strip across first/middle/last frames. Test images never go below ~20."""
    worst = 255.0
    for t in (0, duration / 2, max(0, duration - 0.05)):
        frame = OUT / "_frame.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(path),
                        "-frames:v", "1", str(frame)], check=True)
        im = Image.open(frame).convert("L")
        w, h = im.size
        for box in ((0, 0, w, 4), (0, h - 4, w, h), (0, 0, 4, h), (w - 4, 0, w, h)):
            worst = min(worst, ImageStat.Stat(im.crop(box)).mean[0])
        frame.unlink()
    return round(worst, 1)


def record(name, cmd, meta):
    out = OUT / f"{name}.mp4"
    result = measure.run(cmd, log_path=OUT / f"{name}.log")
    result.update(meta)
    result["test"] = "A"
    result["name"] = name
    result["output"] = str(out)
    if result["returncode"] == 0 and out.exists():
        result["probe"] = probe(out)
        result["border_min_luma"] = border_check(out, result["probe"]["duration_s"])
        result["border_ok"] = result["border_min_luma"] > 10
        result["render_s_per_video_s"] = round(result["wall_s"] / result["probe"]["duration_s"], 3)
    (BENCH / f"A_{name}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    status = "ok" if result["returncode"] == 0 else f"ERRO {result['returncode']}"
    print(f"{name:28} {status:8} {result['wall_s']:7.2f}s  RAM {result['peak_ram_mb']:7.1f} MB  "
          f"borda {result.get('border_min_luma')}", flush=True)
    return out


def single(name, image, move, supersample, codec="x264"):
    cmd = ["ffmpeg", "-hide_banner", "-y", "-i", str(IMG[image]),
           "-vf", zoompan_filter(move, supersample), "-frames:v", str(N),
           *(X264 if codec == "x264" else NVENC), str(OUT / f"{name}.mp4")]
    return record(name, cmd, {"method": "ffmpeg zoompan", "move": move, "supersample": supersample,
                              "encoder": codec, "input": IMG[image].name})


def transitions(clips):
    """Chain clips with xfade: fade (dissolve) then smoothleft (slide)."""
    d, half = 0.5, SECONDS - 0.5
    graph = (f"[0:v][1:v]xfade=transition=fade:duration={d}:offset={half}[a];"
             f"[a][2:v]xfade=transition=smoothleft:duration={d}:offset={2 * half}[v]")
    cmd = ["ffmpeg", "-hide_banner", "-y", *sum((["-i", str(c)] for c in clips), []),
           "-filter_complex", graph, "-map", "[v]", *X264, str(OUT / "transicoes_fade_slide.mp4")]
    return record("transicoes_fade_slide", cmd, {"method": "ffmpeg xfade", "move": "fade + smoothleft",
                                                 "encoder": "x264", "input": [Path(c).name for c in clips]})


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    BENCH.mkdir(parents=True, exist_ok=True)
    only = set(sys.argv[1:])

    def wanted(tag):
        return not only or tag in only

    if wanted("jitter"):
        for ss in (1, 2, 4):
            single(f"zoom_in_ss{ss}", "A_azul", "zoom_in", ss)
    if wanted("moves"):
        single("zoom_out_ss4", "A_azul", "zoom_out", 4)
        single("pan_h_ss4", "B_ambar", "pan_h", 4)
        single("pan_v_ss4", "C_verde", "pan_v", 4)
        single("combined_ss4", "A_azul", "combined", 4)
    if wanted("nvenc"):
        single("combined_ss4_nvenc", "A_azul", "combined", 4, codec="nvenc")
    if wanted("transitions"):
        transitions([OUT / "zoom_in_ss4.mp4", OUT / "pan_h_ss4.mp4", OUT / "pan_v_ss4.mp4"])
