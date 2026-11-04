"""MoviePy 2.x baseline: classic Ken Burns recipe (resized(lambda t) + animated position).

Same 'combined' move and easing as Test A, same synthetic image. Run with the lab venv.
Usage: run_moviepy.py <image> <name>
"""
import sys
from pathlib import Path

from moviepy import CompositeVideoClip, ImageClip

LAB = Path(__file__).resolve().parent.parent
OW, OH, SECONDS = 1080, 1920, 5


def ease(t):
    p = min(max(t / SECONDS, 0), 1)
    return p * p * (3 - 2 * p)


def zoom(t):
    return 1.1 + 0.2 * ease(t)


def position(t):
    z, e = zoom(t), ease(t)
    return (-(OW * z - OW) * (0.15 + 0.35 * e), -(OH * z - OH) * (0.2 + 0.3 * e))


if __name__ == "__main__":
    image, name = Path(sys.argv[1]), sys.argv[2]
    out = LAB / "outputs" / "moviepy" / f"{name}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    base = ImageClip(str(image)).with_duration(SECONDS)
    scale = OW / base.w
    moving = base.resized(lambda t: scale * zoom(t)).with_position(position)
    CompositeVideoClip([moving], size=(OW, OH)).with_duration(SECONDS).write_videofile(
        str(out), fps=30, codec="libx264", audio=False, preset="medium", logger=None,
        ffmpeg_params=["-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart"])
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import measure
    me = measure.kernel32.GetCurrentProcess()
    print(f"SELF_PEAK_MB={measure.peak_rss(me) / 2**20:.1f} SELF_CPU_S={measure.cpu_seconds(me):.2f}")
