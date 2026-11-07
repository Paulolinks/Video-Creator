"""Benchmark A/B/C do Smart Motion Overlay Engine sobre videos reais do Video Creator.

python smart_motion/bench.py      (roda tudo e grava smart_motion/reports/BENCHMARK_SMART_MOTION.md)
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB / "scripts"))
sys.path.insert(0, str(HERE))
import measure  # noqa: E402
import smart_motion as sm  # noqa: E402

OUT = LAB / "outputs" / "smart_motion" / "bench"
REP = HERE / "reports"
VIDS = LAB / "outputs" / "videos"
CASOS = [
    # (id, video, ass, config, encoder)
    ("T02_A0_remux", "entrevista_bob_proctor", None, "remux"),
    ("T02_A_x264", "entrevista_bob_proctor", None, "x264"),
    ("T02_B_x264", "entrevista_bob_proctor", "bob_B.json", "x264"),
    ("T02_C_x264", "entrevista_bob_proctor", "bob_C.json", "x264"),
    ("T02_A_nvenc", "entrevista_bob_proctor", None, "nvenc"),
    ("T02_B_nvenc", "entrevista_bob_proctor", "bob_B.json", "nvenc"),
    ("T02_C_nvenc", "entrevista_bob_proctor", "bob_C.json", "nvenc"),
    ("F01_A_x264", "teste_maquiavel", None, "x264"),
    ("F01_2ov_x264", "teste_maquiavel", "maquiavel_F01.json", "x264"),
]
VAZIO = {"version": "1.0", "canvas": {"width": 1080, "height": 1920, "fps": 30}, "profile": "T02", "overlays": []}


def info(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path)], capture_output=True, text=True, errors="replace").stderr
    v = re.search(r"Video: (\w+).*?, (\d+)x(\d+).*?, ([\d.]+) fps", r)
    a = re.search(r"Audio: (\w+)", r)
    d = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r)
    return {"vcodec": v.group(1), "res": f"{v.group(2)}x{v.group(3)}", "fps": float(v.group(4)),
            "acodec": a.group(1) if a else None,
            "dur_s": int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3)),
            "mb": round(Path(path).stat().st_size / 2**20, 1)}


def audio_md5(path):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a", "-c", "copy", "-f", "md5", "-"],
                       capture_output=True, text=True)
    return r.stdout.strip()


def frames(video, ov_list, nome):
    """Folha com inicio/meio/fim de cada overlay (recorte da zona + legenda)."""
    pasta = REP / "frames"
    pasta.mkdir(parents=True, exist_ok=True)
    tmp = OUT / "_frames"
    tmp.mkdir(exist_ok=True)
    linhas = []
    for o in ov_list:
        cel = []
        for k, t in enumerate([o["start_s"] + 0.25, (o["start_s"] + o["end_s"]) / 2, o["end_s"] - 0.35]):
            f = tmp / f"{nome}_{o['id']}_{k}.png"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
                            "-vf", "scale=360:-1", str(f)], check=True)
            cel.append(f)
        linhas.append(cel)
    for i, cel in enumerate(linhas):
        dst = pasta / f"{nome}_{ov_list[i]['id']}_{ov_list[i]['type']}.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", *sum((["-i", str(c)] for c in cel), []),
                        "-filter_complex", "hstack=3", str(dst)], check=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    REP.mkdir(exist_ok=True)
    res = {}
    md5_orig = {}
    for cid, vid, cfg, enc in CASOS:
        video = VIDS / vid / f"{vid}.mp4"
        ass = VIDS / vid / "legenda.ass"
        out = OUT / f"{cid}.mp4"
        md5_orig.setdefault(vid, audio_md5(video))
        print(f"== {cid}", flush=True)
        if enc == "remux":
            m = measure.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-c", "copy", str(out)])
            etapas = {}
        else:
            if cfg is None:
                cp = OUT / "_vazio.json"
                cp.write_text(json.dumps({**VAZIO, "profile": vid.startswith("teste") and "F01" or "T02"}))
            else:
                cp = HERE / "configs" / cfg
            log = OUT / f"{cid}.log"
            m = measure.run([sys.executable, str(HERE / "smart_motion.py"), "render", "--config", str(cp),
                             "--ass", str(ass), "--video", str(video), "--out", str(out), "--encoder", enc,
                             "--work", str(OUT / f"_camadas_{cid}")], log_path=log)
            txt = log.read_text(encoding="utf-8", errors="replace")
            etapas = json.loads(txt[txt.index("{"):])
        if m["returncode"] != 0:
            raise SystemExit(f"{cid} falhou: veja {OUT / (cid + '.log')}")
        m.pop("cmd")
        res[cid] = {"video": vid, "config": cfg, "encoder": enc, "medida": m, "etapas": etapas,
                    "saida": info(out), "original": info(video),
                    "audio_identico": audio_md5(out) == md5_orig[vid]}
        print(json.dumps({k: res[cid][k] for k in ("etapas", "saida", "audio_identico")}, ensure_ascii=False)[:400])
        if cid in ("T02_C_nvenc", "F01_2ov_x264"):
            frames(out, etapas["overlays"], cid)
    (REP / "bench_resultados.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print("ok")


if __name__ == "__main__":
    main()
