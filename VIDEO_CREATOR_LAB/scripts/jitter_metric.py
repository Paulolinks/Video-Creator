"""Objective motion-smoothness metric for camera-move clips.

d[i] = mean |frame[i+1] - frame[i]| (grayscale). Smooth motion makes d vary smoothly;
integer-pixel stepping makes it spike. jitter = mean |d[i+1] - d[i]| / mean(d), lower is better.
frozen = share of frames that barely moved (d < 25% of the median), i.e. visible stutter.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np


def frames(path, w=1080, h=1920):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.int16)


def jitter(path, skip=10):
    f = frames(path)
    d = np.array([np.abs(f[i + 1] - f[i]).mean() for i in range(len(f) - 1)])[skip:-skip]
    return {"jitter": round(float(np.abs(np.diff(d)).mean() / d.mean()), 4),
            "frozen_pct": round(float((d < 0.25 * np.median(d)).mean() * 100), 1),
            "mean_frame_diff": round(float(d.mean()), 3)}


if __name__ == "__main__":
    bench = Path(sys.argv[1])
    for p in sys.argv[2:]:
        p = Path(p)
        r = jitter(p)
        j = bench / f"A_{p.stem}.json"
        if j.exists():
            data = json.loads(j.read_text(encoding="utf-8"))
            data["smoothness"] = r
            j.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"{p.stem:24} jitter {r['jitter']:.4f}  frozen {r['frozen_pct']:5.1f}%  diff {r['mean_frame_diff']}")
