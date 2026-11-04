"""Sub-pixel camera moves rendered frame by frame with Pillow, piped to FFmpeg.

Same moves and easing as run_test_a.py, but the crop box is fractional and resampled
with Lanczos, so there is no integer rounding. Measures itself plus the FFmpeg child.
Usage: pil_motion.py <move> <image> <name>
"""
import json
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

import measure
from run_test_a import BENCH, FPS, IMG, N, OH, OUT, OW, X264, border_check, probe

MOVES = {  # zoom(e), x_frac(e), y_frac(e): share of the free margin (iw - iw/zoom)
    "zoom_in": (lambda e: 1 + 0.25 * e, lambda e: 0.5, lambda e: 0.5),
    "zoom_out": (lambda e: 1.25 - 0.25 * e, lambda e: 0.5, lambda e: 0.5),
    "pan_h": (lambda e: 1.25, lambda e: e, lambda e: 0.5),
    "pan_v": (lambda e: 1.25, lambda e: 0.5, lambda e: 1 - e),
    "combined": (lambda e: 1.1 + 0.2 * e, lambda e: 0.15 + 0.35 * e, lambda e: 0.2 + 0.3 * e),
}


def render(move, image, name):
    src = Image.open(IMG[image]).convert("RGB")
    iw, ih = src.size
    fz, fx, fy = MOVES[move]
    out = OUT / f"{name}.mp4"
    log = open(OUT / f"{name}.log", "w", encoding="utf-8")
    start = time.perf_counter()
    enc = subprocess.Popen(["ffmpeg", "-hide_banner", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{OW}x{OH}", "-r", str(FPS), "-i", "-", *X264, str(out)],
                           stdin=subprocess.PIPE, stderr=log)
    enc_handle = measure.open_process(enc.pid)
    enc_peak = 0
    for i in range(N):
        t = i / (N - 1)
        e = t * t * (3 - 2 * t)
        z = fz(e)
        w, h = iw / z, ih / z
        x, y = (iw - w) * fx(e), (ih - h) * fy(e)
        frame = src.resize((OW, OH), Image.Resampling.LANCZOS, box=(x, y, x + w, y + h))
        enc.stdin.write(frame.tobytes())
        if i % 10 == 0:
            enc_peak = max(enc_peak, measure.peak_rss(enc_handle))
    enc.stdin.close()
    enc.wait()
    wall = time.perf_counter() - start
    enc_peak = max(enc_peak, measure.peak_rss(enc_handle))
    enc_cpu = measure.cpu_seconds(enc_handle)
    log.close()
    me = measure.kernel32.GetCurrentProcess()
    result = {"test": "A", "name": name, "method": "Pillow resize(box) Lanczos sub-pixel -> ffmpeg pipe",
              "move": move, "encoder": "x264", "input": IMG[image].name, "returncode": enc.returncode,
              "wall_s": round(wall, 2), "cpu_s": round(measure.cpu_seconds(me) + enc_cpu, 2),
              "peak_ram_mb": round((measure.peak_rss(me) + enc_peak) / 2**20, 1),
              "peak_ram_note": "python peak + ffmpeg peak (sum of peaks)", "output": str(out)}
    result["avg_cores_busy"] = round(result["cpu_s"] / wall, 2)
    result["probe"] = probe(out)
    result["border_min_luma"] = border_check(out, result["probe"]["duration_s"])
    result["border_ok"] = result["border_min_luma"] > 10
    result["render_s_per_video_s"] = round(wall / result["probe"]["duration_s"], 3)
    (BENCH / f"A_{name}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{name:28} ok {wall:7.2f}s  RAM {result['peak_ram_mb']:7.1f} MB  borda {result['border_min_luma']}")


if __name__ == "__main__":
    render(*sys.argv[1:4])
