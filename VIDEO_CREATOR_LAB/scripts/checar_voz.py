"""Find voice defects by comparing what Whisper heard with the script (the alignment already has both).

Chatterbox sometimes "hallucinates": babble in another language, repeated words, noise or a long hiss between
sentences, or it skips words. The script text is known, so:
  - words heard that are not in the script (2+ in a row)  -> "fala estranha" (babble, repetition, noise read as words)
  - script words not heard (3+ in a row)                   -> "palavras puladas"
  - a gap between two words with sound but no script word   -> "som estranho" (hiss, babble Whisper did not write)
  - a silent gap longer than SILENCIO_MAX                   -> "pausa longa"
Each problem gets its time in the scene and, when the voice engine recorded them, which sentence it is in, so only
that sentence is redone.

Usage (diagnosis of a finished video): checar_voz.py <saida_dir>
"""
import array
import difflib
import json
import math
import re
import sys
import unicodedata
import wave
from pathlib import Path

EXTRA_MIN = 2  # inserted words in a row
FALTA_MIN = 3  # skipped words in a row
GAP_MIN = 1.2  # seconds between two words worth looking at
SOM_DB = -35  # a gap whose median loudness is above this has sound in it (speech is around -16 dB)
SILENCIO_MAX = 2.5  # a really silent gap longer than this is dead air
FILLERS = {"mm", "hmm", "um", "uh", "ah", "eh", "e", "oh", "a", "the", "and", "so", "ok", "yeah"}


def norm(word):
    word = unicodedata.normalize("NFD", word.lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in word if unicodedata.category(c) != "Mn"))


def _words(text):
    return [w for w in text.split() if norm(w)]


def _loudness(samples, sr, t0, t1):
    """Median loudness (dB) of 100 ms windows between t0 and t1."""
    seg = samples[int(t0 * sr):int(t1 * sr)]
    step = max(1, sr // 10)
    vals = []
    for i in range(0, max(1, len(seg) - step + 1), step // 2 or 1):
        win = seg[i:i + step]
        if not len(win):
            break
        rms = math.sqrt(sum(v * v for v in win) / len(win)) / 32768
        vals.append(20 * math.log10(rms + 1e-9))
    vals.sort()
    return vals[len(vals) // 2] if vals else -120.0


def read_wav(path):
    with wave.open(str(path)) as w:
        sr, data = w.getframerate(), w.readframes(w.getnframes())
    return array.array("h", data), sr


def check_scene(text, recognized, words, duration, frases=None, wav=None):
    """words: the script words with their times (from the alignment). wav: (samples, sr) of the scene, to tell a
    silent gap from one with noise/babble in it. Returns a list of problems."""
    a = [norm(w) for w in _words(text)]
    raw_b = _words(recognized or "")
    b = [norm(w) for w in raw_b]
    n = len(words)

    def t_before(i):
        return words[i - 1]["end"] if 0 < i <= n else 0.0

    def t_after(i):
        return words[i]["start"] if i < n else duration

    problems = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        extra = [w for w in raw_b[j1:j2] if norm(w) not in FILLERS]
        if op == "insert" and len(extra) >= EXTRA_MIN:
            problems.append({"tipo": "fala estranha", "inicio": t_before(i1), "fim": t_after(i1),
                             "ouvido": " ".join(raw_b[j1:j2])})
        elif op == "replace" and (j2 - j1) - (i2 - i1) >= EXTRA_MIN and len(extra) >= EXTRA_MIN:
            problems.append({"tipo": "fala estranha", "inicio": t_after(i1), "fim": t_before(i2),
                             "ouvido": " ".join(raw_b[j1:j2]), "esperado": " ".join(_words(text)[i1:i2])})
        elif op == "delete" and i2 - i1 >= FALTA_MIN:
            problems.append({"tipo": "palavras puladas", "inicio": t_after(i1), "fim": t_before(i2),
                             "esperado": " ".join(_words(text)[i1:i2])})
    for k in range(n - 1):
        t0, t1 = words[k]["end"], words[k + 1]["start"]
        if t1 - t0 < GAP_MIN:
            continue
        if any(p["inicio"] <= (t0 + t1) / 2 <= p["fim"] for p in problems):
            continue  # already explained by the babble found there
        level = _loudness(*wav, t0, t1) if wav else -120.0
        if wav and level > SOM_DB:
            problems.append({"tipo": "som estranho", "inicio": t0, "fim": t1, "segundos": round(t1 - t0, 1),
                             "db": round(level)})
        elif t1 - t0 > SILENCIO_MAX:
            problems.append({"tipo": "pausa longa", "inicio": t0, "fim": t1, "segundos": round(t1 - t0, 1)})
    for p in problems:
        p["inicio"], p["fim"] = round(p["inicio"], 2), round(max(p["fim"], p["inicio"]), 2)
        if frases:  # which sentence (index) the problem falls in: the middle of the problem decides
            mid = (p["inicio"] + p["fim"]) / 2
            p["frase"] = min(range(len(frases)), key=lambda i: 0 if frases[i]["inicio"] <= mid <= frases[i]["fim"]
                             else min(abs(mid - frases[i]["inicio"]), abs(mid - frases[i]["fim"])))
    return sorted(problems, key=lambda p: p["inicio"])


def check_all(scenes, alignment, tts, frases_by_scene=None, only=None):
    """scenes: [{"id","text"}]; alignment: alinhamento.json; tts: tts.json (treated audio). {scene_id: [problems]}"""
    al = {s["id"]: s for s in alignment["scenes"]}
    info = {s["id"]: s for s in tts["scenes"]}
    out = {}
    for sc in scenes:
        a, t = al.get(sc["id"]), info.get(sc["id"])
        if not a or not t or (only and sc["id"] not in only):
            continue
        wav = read_wav(t["wav"]) if Path(t["wav"]).exists() else None
        probs = check_scene(sc["text"], a.get("recognized", ""), a["words"], t["duration_s"],
                            (frases_by_scene or {}).get(sc["id"]), wav)
        if probs:
            out[sc["id"]] = probs
    return out


def describe(p):
    if p.get("ouvido"):
        return f'ouviu "{p["ouvido"]}"'
    if p.get("esperado"):
        return f'faltou "{p["esperado"]}"'
    return f'{p.get("segundos")} s'


if __name__ == "__main__":
    saida = Path(sys.argv[1])
    audio = saida / "audio"
    scenes = json.loads((audio / "_cenas_todas.json").read_text(encoding="utf-8"))
    alignment = json.loads((audio / "alinhamento.json").read_text(encoding="utf-8"))
    tts = json.loads((audio / "tts.json").read_text(encoding="utf-8"))
    found = check_all(scenes, alignment, tts)
    total = sum(len(v) for v in found.values())
    print(f"{saida.parent.name}: {total} problema(s) em {len(found)} de {len(scenes)} cenas")
    for sid, probs in found.items():
        for p in probs:
            print(f"  {sid} {p['inicio']:7.1f}s  {p['tipo']:16} {describe(p)[:90]}")
