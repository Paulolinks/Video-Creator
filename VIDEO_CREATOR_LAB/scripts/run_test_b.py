"""Test B: 2.5D parallax from a single image with Depth Anything V2 Small (CPU).

Pipeline: crop 9:16 -> depth map -> per-frame backward warp with cv2.remap (sub-pixel),
near pixels move/magnify more than far ones -> FFmpeg x264.
Usage: run_test_b.py <image> <tag> [crop_center_x]
Run with the lab venv; set HF_HOME to the lab cache first.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForDepthEstimation

sys.path.insert(0, str(Path(__file__).resolve().parent))
import measure
from jitter_metric import jitter

LAB = Path(__file__).resolve().parent.parent
OUT = LAB / "outputs" / "depth"
BENCH = LAB / "benchmarks"
MODEL = "depth-anything/Depth-Anything-V2-Small-hf"
SW, SH = 2160, 3840          # working source size (2x output)
OW, OH, FPS, SECONDS = 1080, 1920, 30, 5
N = FPS * SECONDS
X264 = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]


def crop_9x16(path, center_x):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    cw = round(h * 9 / 16)
    x0 = int(min(max(center_x * w - cw / 2, 0), w - cw))
    return im.crop((x0, 0, x0 + cw, h)).resize((SW, SH), Image.Resampling.LANCZOS)


def estimate_depth(img):
    processor = AutoImageProcessor.from_pretrained(MODEL)
    model = AutoModelForDepthEstimation.from_pretrained(MODEL).eval()
    t = time.perf_counter()
    with torch.no_grad():
        pred = model(**processor(images=img, return_tensors="pt")).predicted_depth
    depth = torch.nn.functional.interpolate(pred[None], size=(SH, SW), mode="bicubic")[0, 0].numpy()
    seconds = time.perf_counter() - t
    lo, hi = np.percentile(depth, [2, 98])
    depth = np.clip((depth - lo) / (hi - lo), 0, 1).astype(np.float32)  # 1 = near
    return depth, seconds


def soften(depth):
    """Grow near regions slightly and blur, so edges stretch background instead of tearing objects."""
    grown = cv2.dilate(depth, np.ones((15, 15), np.uint8))
    return cv2.GaussianBlur(grown, (0, 0), 6)


MOVES = {
    # (global zoom start, global zoom end, depth zoom gain, lateral shift gain)
    "dolly": (1.12, 1.22, 0.10, 0.0),
    "orbit": (1.15, 1.15, 0.0, 0.035),
    "flat_zoom": (1.12, 1.32, 0.0, 0.0),  # 2D reference with similar on-screen magnification
}


def render(img, depth, move, name):
    z0, z1, dz, sh = MOVES[move]
    src = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)
    u = (np.arange(OW, dtype=np.float32) + 0.5) / OW - 0.5
    v = (np.arange(OH, dtype=np.float32) + 0.5) / OH - 0.5
    pu, pv = np.meshgrid(u, v)
    out = OUT / f"{name}.mp4"
    log = open(OUT / f"{name}.log", "w", encoding="utf-8")
    enc = subprocess.Popen(["ffmpeg", "-hide_banner", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
                            "-s", f"{OW}x{OH}", "-r", str(FPS), "-i", "-", *X264, str(out)],
                           stdin=subprocess.PIPE, stderr=log)
    handle = measure.open_process(enc.pid)
    enc_peak, start = 0, time.perf_counter()
    for i in range(N):
        t = i / (N - 1)
        e = t * t * (3 - 2 * t)
        zoom = z0 + (z1 - z0) * e
        d = cv2.remap(depth, ((pu / zoom + 0.5) * SW), ((pv / zoom + 0.5) * SH), cv2.INTER_LINEAR)
        for _ in range(2):  # fixed point: sample depth where the pixel actually comes from
            z = zoom * (1 + dz * e * d)
            qx = pu / z - sh * (2 * e - 1) * (d - 0.5)
            qy = pv / z
            mx, my = (qx + 0.5) * SW, (qy + 0.5) * SH
            d = cv2.remap(depth, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        frame = cv2.remap(src, mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
        enc.stdin.write(frame.tobytes())
        if i % 10 == 0:
            enc_peak = max(enc_peak, measure.peak_rss(handle))
    enc.stdin.close()
    enc.wait()
    log.close()
    wall = time.perf_counter() - start
    enc_peak = max(enc_peak, measure.peak_rss(handle))
    return out, wall, enc_peak, measure.cpu_seconds(handle)


if __name__ == "__main__":
    image, tag = Path(sys.argv[1]), sys.argv[2]
    center = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
    OUT.mkdir(parents=True, exist_ok=True)
    img = crop_9x16(image, center)
    img.save(OUT / f"{tag}_entrada_9x16.jpg", quality=92)
    t0 = time.perf_counter()
    raw_depth, infer_s = estimate_depth(img)
    load_and_infer_s = time.perf_counter() - t0
    Image.fromarray((raw_depth * 255).astype(np.uint8)).save(OUT / f"{tag}_profundidade.png")
    depth = soften(raw_depth)
    me = measure.kernel32.GetCurrentProcess()
    for move in MOVES:
        name = f"{tag}_{move}"
        out, wall, enc_peak, enc_cpu = render(img, depth, move, name)
        res = {"test": "B", "name": name, "move": move, "input": image.name, "crop_center_x": center,
               "method": "Depth Anything V2 Small (CPU) + cv2.remap parallax" if move != "flat_zoom"
               else "cv2.remap zoom 2D (referencia sem profundidade)",
               "model": MODEL, "model_license": "apache-2.0 (model card)", "device": "cpu",
               "torch": torch.__version__, "depth_infer_s": round(infer_s, 2),
               "depth_load_and_infer_s": round(load_and_infer_s, 2), "render_wall_s": round(wall, 2),
               "render_s_per_video_s": round(wall / SECONDS, 3),
               "peak_ram_mb": round((measure.peak_rss(me) + enc_peak) / 2**20, 1),
               "peak_ram_note": "python (modelo + render) + ffmpeg, soma dos picos",
               "smoothness": jitter(out), "output": str(out),
               "date": time.strftime("%Y-%m-%dT%H:%M:%S")}
        (BENCH / f"B_{name}.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"{name:24} render {wall:6.2f}s  depth {infer_s:5.2f}s  RAM {res['peak_ram_mb']:7.1f} MB  "
              f"tremor {res['smoothness']['jitter']}", flush=True)
