"""Side-by-side comparison videos with a label on each panel (outputs/comparacoes)."""
import subprocess
from pathlib import Path

LAB = Path(__file__).resolve().parent.parent
OUT = LAB / "outputs" / "comparacoes"
FONT = "C\\:/Windows/Fonts/arialbd.ttf"

SETS = {
    "01_tremor_zoom_in": [("ffmpeg/zoom_in_ss1", "FFmpeg zoompan 1x"), ("ffmpeg/zoom_in_ss4", "FFmpeg zoompan 4x"),
                          ("ffmpeg/zoom_in_pil", "Python subpixel")],
    "02_tremor_combinado": [("ffmpeg/combined_ss4", "FFmpeg zoompan 4x"), ("ffmpeg/combined_pil", "Python subpixel"),
                            ("moviepy/combined_moviepy", "MoviePy 2.1")],
    "03_profundidade_lago": [("depth/lago_flat_zoom", "Zoom 2D (sem profundidade)"), ("depth/lago_dolly", "2.5D dolly"),
                             ("depth/lago_orbit", "2.5D orbita")],
    "04_profundidade_fitas": [("depth/fitas_flat_zoom", "Zoom 2D (sem profundidade)"),
                              ("depth/fitas_dolly", "2.5D dolly"), ("depth/fitas_orbit", "2.5D orbita")],
    "05_legenda_simples_x_karaoke": [("montagem/montagem_v2_com_ducking_legenda_simples", "Legenda simples"),
                                     ("montagem/montagem_v3_com_ducking_legenda_karaoke", "Legenda karaoke")],
}

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, panels in SETS.items():
        inputs, chains = [], []
        for i, (path, label) in enumerate(panels):
            inputs += ["-i", str(LAB / "outputs" / f"{path}.mp4")]
            chains.append(f"[{i}:v]scale=540:960,drawtext=fontfile='{FONT}':text='{label}':x=(w-tw)/2:y=24:"
                          f"fontsize=30:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=10[p{i}]")
        stack = "".join(f"[p{i}]" for i in range(len(panels))) + f"hstack={len(panels)}[v]"
        audio = ["-map", "1:a?", "-c:a", "aac"] if "legenda" in name else ["-an"]
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs, "-filter_complex",
                        ";".join(chains) + ";" + stack, "-map", "[v]", *audio, "-c:v", "libx264", "-crf", "20",
                        "-pix_fmt", "yuv420p", "-shortest", "-movflags", "+faststart", str(OUT / f"{name}.mp4")],
                       check=True)
        print("ok", name)
