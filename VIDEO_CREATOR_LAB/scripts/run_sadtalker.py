"""Test C: SadTalker talking head (photo + audio -> lip sync, blinks, head motion), measured.

Usage: run_sadtalker.py <scene_id> <image> <name> [--no-enhancer] [--size 256|512] [--move]
Writes outputs/sadtalker/<name>.mp4 and benchmarks/C_<name>.json.
"""
import json
import shutil
import sys
from pathlib import Path

import measure

LAB = Path(__file__).resolve().parent.parent
TOOL = LAB / "tools" / "SadTalker"
PY = LAB / ".venvs" / "sadtalker" / "Scripts" / "python.exe"
AUDIO = LAB / "outputs" / "maquiavel" / "audio"
OUT = LAB / "outputs" / "sadtalker"

if __name__ == "__main__":
    scene, image, name = sys.argv[1:4]
    enhancer = "--no-enhancer" not in sys.argv
    size = sys.argv[sys.argv.index("--size") + 1] if "--size" in sys.argv else "256"
    still = "--move" not in sys.argv
    work = OUT / "raw" / name
    shutil.rmtree(work, ignore_errors=True)
    cmd = [str(PY), "inference.py", "--driven_audio", str(AUDIO / f"{scene}.wav"),
           "--source_image", str(LAB / image), "--result_dir", str(work), "--preprocess", "full", "--size", size]
    if still:
        cmd.append("--still")
    if enhancer:
        cmd += ["--enhancer", "gfpgan"]
    import os
    os.chdir(TOOL)
    r = measure.run(cmd, log_path=OUT / f"{name}.log")
    produced = sorted(work.glob("*.mp4"))
    out = OUT / f"{name}.mp4"
    if produced:
        shutil.copy2(produced[-1], out)
    r.update({"test": "C", "name": name, "tool": "SadTalker (commit cd4c046, 2023-10-11)",
              "license": "Apache-2.0 (LICENSE do repo; componentes de terceiros com licenças próprias)",
              "settings": {"size": size, "still": still, "enhancer": "gfpgan" if enhancer else None,
                           "preprocess": "full"},
              "input": image, "audio": f"{scene}.wav", "output": str(out) if produced else None,
              "peak_ram_note": "python.exe do venv é um lançador; usar system_ram_delta_mb"})
    (LAB / "benchmarks" / f"C_{name}.json").write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{name}: rc={r['returncode']} {r['wall_s']}s  VRAM pico {r['gpu_mem_peak_mb']} MB "
          f"(+{r['gpu_mem_delta_mb']})  RAM sistema +{r['system_ram_delta_mb']} MB  saida={bool(produced)}")
