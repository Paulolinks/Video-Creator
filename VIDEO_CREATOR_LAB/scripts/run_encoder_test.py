"""Encoder test: x264 vs NVENC quality (SSIM/PSNR vs lossless reference), size and speed."""
import json
import re
import subprocess
from pathlib import Path

import measure

LAB = Path(__file__).resolve().parent.parent
OUT = LAB / "outputs" / "encoder"
BENCH = LAB / "benchmarks"
SRC = LAB / "outputs" / "depth" / "lago_entrada_9x16.jpg"
REF = OUT / "_referencia_lossless.mkv"
N = 150
MOVE = ("zoompan=z='1.1+0.2*(on/149)*(on/149)*(3-2*(on/149))':x='(iw-iw/zoom)*0.4':y='(ih-ih/zoom)*0.45'"
        f":d={N}:s=1080x1920:fps=30,setsar=1")
VARIANTS = {
    "x264_crf18_medium": ["-c:v", "libx264", "-preset", "medium", "-crf", "18"],
    "x264_crf23_medium": ["-c:v", "libx264", "-preset", "medium", "-crf", "23"],
    "x264_crf18_veryfast": ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18"],
    "nvenc_cq19_p5": ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "19", "-b:v", "0"],
    "nvenc_cq23_p5": ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "23", "-b:v", "0"],
    "nvenc_cq19_p7": ["-c:v", "h264_nvenc", "-preset", "p7", "-tune", "hq", "-rc", "vbr", "-cq", "19", "-b:v", "0"],
}


def quality(path):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-i", str(REF), "-lavfi",
                          "[0:v][1:v]ssim;[0:v][1:v]psnr", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    return {"ssim": float(re.search(r"SSIM.*All:([\d.]+)", err).group(1)),
            "psnr_db": float(re.search(r"PSNR.*average:([\d.]+|inf)", err).group(1))}


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(SRC), "-vf", f"scale=2160:3840,{MOVE}",
                    "-frames:v", str(N), "-c:v", "ffv1", "-pix_fmt", "yuv420p", str(REF)], check=True)
    for name, args in VARIANTS.items():
        out = OUT / f"lago_{name}.mp4"
        r = measure.run(["ffmpeg", "-hide_banner", "-y", "-i", str(REF), *args, "-pix_fmt", "yuv420p",
                         "-movflags", "+faststart", str(out)], log_path=OUT / f"lago_{name}.log")
        q = quality(out)
        size = out.stat().st_size / 2**20
        res = {"test": "encoder", "name": f"lago_{name}", "encoder_args": args, "wall_s": r["wall_s"],
               "encode_fps": round(N / r["wall_s"], 1), "cpu_cores_avg": r["avg_cores_busy"],
               "nvenc_util_max_pct": r["nvenc_util_max_pct"], "size_mb": round(size, 2),
               "bitrate_mbps": round(size * 8 * 2**20 / 1e6 / 5, 2), **q,
               "reference": "ffv1 lossless, mesmo movimento", "output": str(out), "date": r["date"]}
        (BENCH / f"ENC_{name}.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
        print(f"{name:22} {r['wall_s']:5.2f}s {res['encode_fps']:6.1f} fps  {size:5.2f} MB  "
              f"SSIM {q['ssim']:.5f}  PSNR {q['psnr_db']:.2f} dB  CPU {r['avg_cores_busy']}")
