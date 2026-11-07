"""SadTalker for every talking scene of a video in one run: the models load once, and each source image's face
analysis (crop + 3DMM) is done once and reused by all scenes with that image.

Same steps and defaults as tools/SadTalker/inference.py (which stays untouched); one result mp4 per scene, written
like inference.py does (<result_dir>/<timestamp>.mp4).
Run with the sadtalker venv, cwd = tools/SadTalker.
Usage: sadtalker_lote.py <jobs.json>
  jobs.json: {"preprocess": "full", "size": 256, "still": true, "enhancer": null,
              "cenas": [{"id": "CENA_01", "audio": "...wav", "imagem": "...png", "saida": "<result_dir>"}]}
"""
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

SAD_DIR = Path(__file__).resolve().parent.parent / "tools" / "SadTalker"
sys.path.insert(0, str(SAD_DIR))

import torch  # noqa: E402
from src.facerender.animate import AnimateFromCoeff  # noqa: E402
from src.generate_batch import get_data  # noqa: E402
from src.generate_facerender_batch import get_facerender_data  # noqa: E402
from src.test_audio2coeff import Audio2Coeff  # noqa: E402
from src.utils.init_path import init_path  # noqa: E402
from src.utils.preprocess import CropAndExtract  # noqa: E402


FRAMES = [2]


def fast_paste(video_path, pic_path, crop_info, new_audio_path, full_video_path, extended_crop=False):
    """Same job as src/utils/paste_pic.paste_pic, ~10x faster: the animated face comes from this very photo, so a
    soft-edged blend matches as well as the Poisson seamlessClone (which costs ~0.1 s per frame on the CPU)."""
    import cv2
    import numpy as np
    import uuid
    from src.utils.videoio import save_video_with_watermark
    full_img = cv2.imread(pic_path)
    frame_h, frame_w = full_img.shape[:2]
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    r_w, r_h = crop_info[0]
    clx, cly, crx, cry = crop_info[1]
    lx, ly, rx, ry = (int(v) for v in crop_info[2])
    oy1, oy2, ox1, ox2 = (cly, cry, clx, crx) if extended_crop else (cly + ly, cly + ry, clx + lx, clx + rx)
    oy1, oy2, ox1, ox2 = max(0, oy1), min(frame_h, oy2), max(0, ox1), min(frame_w, ox2)
    h, w = oy2 - oy1, ox2 - ox1
    feather = max(3, int(0.06 * min(h, w)))
    mask = np.zeros((h, w), np.float32)
    mask[feather:-feather, feather:-feather] = 1.0
    mask = cv2.GaussianBlur(mask, (0, 0), feather / 2)[..., None]
    base = full_img[oy1:oy2, ox1:ox2].astype(np.float32)
    tmp_path = str(uuid.uuid4()) + ".mp4"
    out = cv2.VideoWriter(tmp_path, cv2.VideoWriter_fourcc(*"MP4V"), fps, (frame_w, frame_h))
    frame_out = full_img.copy()
    while True:
        ok, crop = cap.read()
        if not ok:
            break
        p = cv2.resize(crop, (w, h)).astype(np.float32)
        frame_out[oy1:oy2, ox1:ox2] = (p * mask + base * (1 - mask)).astype(np.uint8)
        out.write(frame_out)
    cap.release()
    out.release()
    save_video_with_watermark(tmp_path, new_audio_path, full_video_path, watermark=False)
    os.remove(tmp_path)


def main(cfg):
    if cfg.get("colagem_rapida"):  # T03 only; the approved F01 look keeps SadTalker's own paste
        import src.facerender.animate as anim
        anim.paste_pic = fast_paste
    FRAMES[0] = int(cfg.get("lote_quadros", 2))  # frames rendered together on the GPU (SadTalker default 2)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    preprocess, size, still, enhancer = cfg.get("preprocess", "crop"), int(cfg.get("size", 256)), bool(cfg.get("still")), cfg.get("enhancer")
    t0 = time.perf_counter()
    paths = init_path(str(SAD_DIR / "checkpoints"), str(SAD_DIR / "src" / "config"), size, False, preprocess)
    preprocess_model = CropAndExtract(paths, device)
    audio_to_coeff = Audio2Coeff(paths, device)
    animate = AnimateFromCoeff(paths, device)
    print(f"modelos carregados em {time.perf_counter() - t0:.1f} s ({len(cfg['cenas'])} cena(s))", flush=True)

    faces = {}  # image -> (first_coeff_path, crop_pic_path, crop_info), analysed once
    report = {}
    skip = bool(cfg.get("pular_sem_rosto"))  # T03: a scene that fails keeps the still portrait instead
    for sc in cfg["cenas"]:
        if not skip:
            run_scene(sc, faces, report, preprocess_model, audio_to_coeff, animate, device, preprocess, size, still,
                      enhancer)
            continue
        try:
            run_scene(sc, faces, report, preprocess_model, audio_to_coeff, animate, device, preprocess, size, still,
                      enhancer)
        except (Exception, SystemExit) as e:  # noqa: BLE001
            report[sc["id"]] = f"falhou: {e}"
            print(f"{sc['id']}: não deu para animar ({e}); fica a imagem parada", flush=True)
    for d in {Path(sc["saida"]).parent / "_rostos" for sc in cfg["cenas"]}:
        shutil.rmtree(d, ignore_errors=True)
    print(json.dumps({"cenas_s": report, "total_s": round(time.perf_counter() - t0, 2)}), flush=True)


def run_scene(sc, faces, report, preprocess_model, audio_to_coeff, animate, device, preprocess, size, still, enhancer):
    if True:
        t = time.perf_counter()
        pic = str(Path(sc["imagem"]).resolve())
        result_dir = Path(sc["saida"])
        result_dir.mkdir(parents=True, exist_ok=True)
        if pic not in faces:
            st = Path(pic).stat()
            key = hashlib.sha1(f"{pic}|{st.st_size}|{st.st_mtime}|{preprocess}|{size}".encode()).hexdigest()[:12]
            face_dir = result_dir.parent / "_rostos" / key  # kept for the whole video (not inside a scene folder)
            face_dir.mkdir(parents=True, exist_ok=True)
            print(f"3DMM Extraction for source image ({Path(pic).name})", flush=True)
            faces[pic] = preprocess_model.generate(pic, str(face_dir), preprocess, source_image_flag=True, pic_size=size)
        else:
            print(f"{sc['id']}: rosto já analisado, reaproveitando ({Path(pic).name})", flush=True)
        first_coeff_path, crop_pic_path, crop_info = faces[pic]
        if first_coeff_path is None:
            raise SystemExit(f"Não achei o rosto na imagem: {pic}")
        save_dir = result_dir / time.strftime("%Y_%m_%d_%H.%M.%S")
        save_dir.mkdir(parents=True, exist_ok=True)
        batch = get_data(first_coeff_path, sc["audio"], device, None, still=still)
        coeff_path = audio_to_coeff.generate(batch, str(save_dir), 0, None)
        data = get_facerender_data(coeff_path, crop_pic_path, first_coeff_path, sc["audio"], FRAMES[0], None, None, None,
                                   expression_scale=1.0, still_mode=still, preprocess=preprocess, size=size)
        result = animate.generate(data, str(save_dir), pic, crop_info, enhancer=enhancer, background_enhancer=None,
                                  preprocess=preprocess, img_size=size)
        shutil.move(result, str(save_dir) + ".mp4")
        shutil.rmtree(save_dir, ignore_errors=True)
        report[sc["id"]] = round(time.perf_counter() - t, 2)
        print(f"{sc['id']} pronto em {report[sc['id']]} s -> {save_dir}.mp4", flush=True)


if __name__ == "__main__":
    os.chdir(SAD_DIR)  # SadTalker loads some files relative to its folder
    main(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")))
    sys.stdout.flush()
    os._exit(0)  # skip the CUDA teardown (it can crash on Windows after the work is saved)
