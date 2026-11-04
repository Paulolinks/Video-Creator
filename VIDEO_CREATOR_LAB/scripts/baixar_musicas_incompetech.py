"""Download background music from Incompetech (Kevin MacLeod, CC BY 4.0) for each catalog theme and add it to the
app's music library, then assign each character a rotation pool of up to 3 matching tracks.

Pixabay's API has no music endpoint and its music site blocks automated downloads, so the music comes from
Incompetech: instrumental, tagged by mood and instruments. CC BY needs the credit line in the video description
(saved in each track's "origem").

Usage: baixar_musicas_incompetech.py [tracks_per_theme=2] [--dry]
Run with the lab venv.
"""
import json
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, r"D:\Video-Creator\app")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cadastrar_catalogo import assign_music  # noqa: E402
from catalogo_personagens import THEMES  # noqa: E402
from core import library  # noqa: E402

CATALOG = "https://incompetech.com/music/royalty-free/pieces.json"
MP3 = "https://incompetech.com/music/royalty-free/mp3-royaltyfree/"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) VideoCreator/1.0"}
CREDIT = ('"{title}" Kevin MacLeod (incompetech.com), Licensed under Creative Commons: By Attribution 4.0 '
          'http://creativecommons.org/licenses/by/4.0/')

# theme: (wanted feels, words that should appear in instruments/description/title)
MOODS = {
    "particulas_douradas": ({"Uplifting", "Calming", "Bright"}, ["piano", "strings", "inspir", "hope"]),
    "nuvens": ({"Calming", "Relaxed"}, ["pad", "ambient", "piano", "float", "dream"]),
    "cosmos": ({"Mystical", "Mysterious", "Calming"}, ["synth", "space", "galaxy", "stars", "ambient"]),
    "luz_divina": ({"Calming", "Uplifting", "Mystical"}, ["choir", "harp", "organ", "strings", "heaven", "angel"]),
    "templo_grego": ({"Epic", "Somber", "Uplifting"}, ["strings", "brass", "harp", "french horn", "timpani", "ancient"]),
    "biblioteca_velas": ({"Somber", "Calming", "Mysterious"}, ["piano", "cello", "melanchol", "reflect"]),
    "egito": ({"Mysterious", "Mystical"}, ["middle east", "egypt", "desert", "oud", "duduk", "arabic", "sitar"]),
    "zen_natureza": ({"Calming", "Relaxed", "Mystical"}, ["zen", "koto", "shakuhachi", "bowl", "asian", "japan", "flute"]),
    "xadrez": ({"Suspenseful", "Mysterious", "Intense"}, ["strings", "piano", "pizzicato", "tension", "plan"]),
    "dinheiro_ouro": ({"Uplifting", "Driving", "Bright", "Epic"}, ["corporate", "success", "piano", "strings", "drums"]),
    "cidade_noite": ({"Grooving", "Relaxed"}, ["electric piano", "night", "city", "jazz", "chill", "bass"]),
    "tecnologia": ({"Driving", "Bright", "Grooving"}, ["synth", "electronic", "digital", "future", "tech"]),
    "cerebro_neuronios": ({"Mysterious", "Calming"}, ["synth", "piano", "mind", "thought", "pulse"]),
    "fisica_atomos": ({"Mysterious", "Bright", "Driving"}, ["synth", "science", "pulse", "particle", "arpegg"]),
    "matematica_geometria": ({"Calming", "Mystical"}, ["synth", "minimal", "pattern", "piano", "bell"]),
    "tinta_fumaca": ({"Mysterious", "Calming", "Somber"}, ["ambient", "drone", "pad", "slow", "dark"]),
    "oceano": ({"Calming", "Relaxed"}, ["ocean", "sea", "wave", "piano", "guitar", "ambient"]),
    "fogo": ({"Epic", "Intense", "Driving"}, ["drums", "taiko", "percussion", "brass", "battle", "strings"]),
    "energia_eletrica": ({"Intense", "Driving", "Action"}, ["synth", "electro", "energy", "drums", "power"]),
}
AVOID_FEELS = {"Humorous", "Bouncy", "Eerie", "Unnerving", "Aggressive"}
AVOID_WORDS = ["christmas", "holiday", "polka", "game show", "circus", "silly", "comedy", "cartoon", "kids",
               "waltz", "rag", "ska", "disco", "funk", "country", "cowboy", "sting", "voice", "vocal", "rap",
               "americana", "8bit", "8-bit", "chiptune", "horror", "scp-", "spooky", "zombie"]


def get(url, timeout=60, tries=4):
    for t in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout)
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            if t == tries - 1:
                raise
            time.sleep(3 * (t + 1))


def seconds(length):
    h, m, s = (int(x) for x in length.split(":"))
    return h * 3600 + m * 60 + s


def score(piece, theme):
    feels = {f.strip() for f in (piece.get("feel") or "").split(",") if f.strip()}
    text = " ".join(str(piece.get(k) or "") for k in ("title", "instruments", "description")).lower()
    if feels & AVOID_FEELS or any(w in text for w in AVOID_WORDS) or not feels:
        return None
    if not 90 <= seconds(piece["length"]) <= 420:
        return None
    if theme != "luz_divina" and "choir" in text:
        return None
    want, words = MOODS[theme]
    hit = len(feels & want)
    if not hit:
        return None
    return hit * 2 + sum(w in text for w in words) * 3 - len(feels - want) * 0.5


def plan(pieces, per_theme):
    """Best tracks per theme, never the same track for two themes."""
    taken = {b["origem"].split('"')[1] for b in library.music() if b.get("origem", "").startswith('"')}
    picks = {}
    for theme in MOODS:
        have = sum(theme in (m.get("temas") or []) for m in library.music())
        ranked = sorted((p for p in pieces if p["title"] not in taken and score(p, theme) is not None),
                        key=lambda p: -score(p, theme))
        picks[theme] = ranked[:max(0, per_theme - have)]
        taken |= {p["title"] for p in picks[theme]}
    return picks


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    per_theme = int(args[0]) if args else 2
    with get(CATALOG) as r:
        pieces = json.loads(r.read().decode("utf-8"))
    picks = plan(pieces, per_theme)
    if "--dry" in sys.argv:
        for theme, ps in picks.items():
            for p in ps:
                print(f"{theme}: {p['title']} | {p['feel']} | {p['instruments']} | {p['length']}")
        sys.exit()
    added = 0
    for theme, ps in picks.items():
        label = THEMES[theme][0]
        have = sum(theme in (m.get("temas") or []) for m in library.music())
        for i, p in enumerate(ps, have + 1):
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "faixa.mp3"
                with get(MP3 + urllib.parse.quote(p["filename"])) as r:
                    path.write_bytes(r.read())
                if subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-t", "1", "-f", "null", "-"],
                                  capture_output=True).returncode:
                    continue
                item = library.add_media("musicas", f"{label} {i} - {p['title']}", path,
                                         CREDIT.format(title=p["title"]), temas=[theme])
            added += 1
            print(f"{theme}: {item['nome']} ({p['length']})", flush=True)
            time.sleep(0.5)
    print(f"músicas baixadas: {added}")
    assign_music()
