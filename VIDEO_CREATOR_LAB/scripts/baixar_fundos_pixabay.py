"""Download background videos from Pixabay (Pixabay Content License) for each catalog theme and add them to
the app's background library, then re-assign the characters' rotation pools.

Usage: baixar_fundos_pixabay.py <PIXABAY_API_KEY> [videos_per_theme=2]
Get a free key at https://pixabay.com/api/docs/ (logged in, the key is shown on that page).
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
from cadastrar_catalogo import assign_backgrounds  # noqa: E402
from catalogo_personagens import THEMES  # noqa: E402
from core import library  # noqa: E402

API = "https://pixabay.com/api/videos/"
SKIP = {"particulas_douradas", "nuvens"}  # the user's own backgrounds already cover these
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) VideoCreator/1.0"}  # urllib's default UA gets 403


def get(url, timeout=60, tries=4):
    for t in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout)
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            if t == tries - 1:
                raise
            time.sleep(3 * (t + 1))


def search(key, terms):
    q = urllib.parse.urlencode({"key": key, "q": terms, "per_page": 30, "safesearch": "true", "order": "popular"})
    with get(f"{API}?{q}", 30) as r:
        return json.loads(r.read().decode("utf-8"))["hits"]


def pick(hits, n):
    """Calm loops: 10-60 s, landscape, at least 1280 px wide in the 'medium' rendition, no duplicates."""
    good = [h for h in hits if 10 <= h["duration"] <= 60 and (m := h["videos"]["medium"])["url"]
            and m["width"] >= 1280 and m["width"] > m["height"]]
    return good[:n]


if __name__ == "__main__":
    key = sys.argv[1]
    per_theme = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    known = {b.get("origem", "") for b in library.backgrounds()}
    added = 0
    for theme, (label, terms) in THEMES.items():
        if theme in SKIP:
            continue
        have = [b for b in library.backgrounds() if theme in (b.get("temas") or [])]
        for i, hit in enumerate(pick(search(key, terms), per_theme), len(have) + 1):
            if len(have) >= per_theme:
                break
            origem = f"Pixabay #{hit['id']} ({hit['pageURL']}), Pixabay Content License"
            if origem in known:
                continue
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / f"{hit['id']}.mp4"
                with get(hit["videos"]["medium"]["url"]) as r:
                    path.write_bytes(r.read())
                ok = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-t", "1", "-f", "null", "-"],
                                    capture_output=True).returncode == 0
                if not ok:
                    continue
                item = library.add_media("fundos", f"{label} {i}", path, origem, temas=[theme])
            have.append(item)
            added += 1
            print(f"{theme}: {item['nome']} ({hit['duration']} s, {hit['videos']['medium']['width']}x"
                  f"{hit['videos']['medium']['height']})", flush=True)
            time.sleep(0.5)
    print(f"fundos baixados: {added}")
    assign_backgrounds()
