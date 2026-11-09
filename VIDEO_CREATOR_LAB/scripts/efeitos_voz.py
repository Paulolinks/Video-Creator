"""Voice character applied to a finished narration file, shared by the TTS engines.
A voice's settings .json may set "tom" (pitch factor, rubberband, same formants) and "efeito" (a key of EFEITOS)."""
import subprocess
from pathlib import Path

# Optional "efeito" of a voice (ffmpeg filter graph, input [0:a], output [out]). apad leaves room for the tail.
# A short room ambience, not an echo: two quiet reflections under 50 ms blend with the voice instead of being
# heard as repeats (2026-11-07: the 60/130/250 ms taps sounded like delay). rubberband adds ~10 ms of latency, so
# the pitched layers are trimmed by 10 ms to stay glued to the main voice.
_SALA = "aecho=0.92:0.95:23|41:0.09|0.05"
EFEITOS = {
    # deep, a little more low end, short room
    "catedral": f"[0:a]apad=pad_dur=0.2,{_SALA},bass=g=2.5:f=110,alimiter=limit=0.95[out]",
    # calm and warm: a soft lower shadow under the voice (2026-11-07: lighter, it was too deep), short room,
    # gentle highs - a peaceful voice
    "divino": ("[0:a]apad=pad_dur=0.2,asplit=2[a][b];[b]rubberband=pitch=0.8:formant=preserved,atrim=start=0.010,"
               "asetpts=PTS-STARTPTS,lowpass=f=1400,volume=0.12[low];[a][low]amix=inputs=2:normalize=0:duration=first,"
               f"{_SALA},bass=g=1:f=120,treble=g=-1.5,alimiter=limit=0.95[out]"),
    # ethereal: a very slightly detuned double (soft chorus, no audible delay), short room, softened highs
    "eterno": ("[0:a]apad=pad_dur=0.2,asplit=2[a][b];[b]rubberband=pitch=1.008,atrim=start=0.007,asetpts=PTS-STARTPTS,"
               "volume=0.22[d];[a][d]amix=inputs=2:normalize=0:duration=first,"
               f"{_SALA},highpass=f=70,treble=g=-2,alimiter=limit=0.95[out]"),
    # a counsellor speaking close in a small study: fuller lows, clear consonants, tight and controlled
    "conselheiro": ("[0:a]apad=pad_dur=0.2,bass=g=3:f=130,equalizer=f=2600:t=q:w=1.2:g=2,aecho=0.95:0.95:11|19:0.06|0.03,"
                    "acompressor=threshold=-24dB:ratio=3:attack=10:release=160:makeup=1.5,alimiter=limit=0.95[out]"),
    # a stone palace room: a dark lower shadow under the voice, more room, muted highs
    "palacio": ("[0:a]apad=pad_dur=0.3,asplit=2[a][b];[b]rubberband=pitch=0.84:formant=preserved,atrim=start=0.010,"
                "asetpts=PTS-STARTPTS,lowpass=f=1200,volume=0.14[low];[a][low]amix=inputs=2:normalize=0:duration=first,"
                "aecho=0.9:0.92:27|43:0.12|0.07,bass=g=2.5:f=110,treble=g=-2,alimiter=limit=0.95[out]"),
}


def _ffmpeg(args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def aplicar(path, style, rate):
    """Apply the voice's pitch and effect to a mono wav, in place."""
    path = Path(path)
    pitch = float(style.get("tom", 1.0))
    if abs(pitch - 1.0) > 0.005:
        tmp = path.with_suffix(".tom.wav")
        _ffmpeg(["-i", str(path), "-af", f"rubberband=pitch={pitch}:formant=preserved", str(tmp)])
        tmp.replace(path)
    if style.get("efeito") in EFEITOS:  # kept inside the voice: every later step sees the final sound
        tmp = path.with_suffix(".efeito.wav")
        _ffmpeg(["-i", str(path), "-filter_complex", EFEITOS[style["efeito"]], "-map", "[out]", "-ar", str(rate),
                 "-ac", "1", str(tmp)])
        tmp.replace(path)
