"""Which engine narrates cloned voices. Both stay installed: change ATIVO to switch ("qwen3" or "chatterbox").
The videos' next run uses it; a character's registered voice ("motor": "chatterbox") only means "cloned recording"."""
from pathlib import Path

ATIVO = "qwen3"

_LAB = Path(__file__).resolve().parent.parent
_SCRIPTS = _LAB / "scripts"
_MOTORES = {
    "qwen3": (_LAB / ".venvs" / "qwen3tts" / "Scripts" / "python.exe", _SCRIPTS / "tts_qwen.py"),
    "chatterbox": (Path(r"C:\dev\Video Cutter\.runtime\voices\chatterbox\Scripts\python.exe"),
                   _SCRIPTS / "tts_chatterbox.py"),
}


def comando():
    """Start of the command line of the active engine (both take the same arguments)."""
    return [str(p) for p in _MOTORES[ATIVO]]
