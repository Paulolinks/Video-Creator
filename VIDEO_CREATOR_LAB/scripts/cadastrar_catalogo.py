"""Register the catalog characters in the app and assign matching backgrounds (rotation pool of up to 3).

  cadastrar_catalogo.py              register/update every catalog character (voice pack from data/vozes)
  cadastrar_catalogo.py fundos       only re-assign backgrounds (after new backgrounds were downloaded)
  cadastrar_catalogo.py musicas      only re-assign music

Characters whose backgrounds/music were changed by hand in the app (fundos_manual/musicas_manual) are left alone.
Run with the lab venv.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, r"D:\Video-Creator\app")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalogo_personagens import CATALOG, EXTRA, THEMES  # noqa: E402
from core import library  # noqa: E402

BUILTIN_BG_THEMES = {"particulas_douradas": ["particulas_douradas"], "nuvens": ["nuvens"]}


def _assign(kind, items, builtin=None):
    """Rotation pool of up to 3 items per character, matched by the character's themes (fundos/musicas)."""
    by_theme = {}
    for b in items:
        for t in b.get("temas") or (builtin or {}).get(b["id"], []):
            by_theme.setdefault(t, []).append(b["id"])
    themes_of = {c[0]: c[6] for c in CATALOG} | {n: e[3] for n, e in EXTRA.items()}
    changed = 0
    for ch in library.characters():
        temas = ch.get("temas_fundo") or themes_of.get(ch["nome"])  # stored themes survive renames in the app
        if not temas or ch.get(f"{kind}_manual"):
            continue
        pool = [ids[0] for t in temas if (ids := by_theme.get(t))]  # one per theme, in order of affinity
        for t in temas:  # fill up to 3 with second items of the same themes
            pool += [i for i in by_theme.get(t, [])[1:] if i not in pool]
        pool = list(dict.fromkeys(pool))[:3]
        if pool and pool != ch.get(kind):
            fields = {kind: pool, f"{kind[:-1]}_indice": 0}
            if kind == "fundos":
                fields["fundo"] = pool[0]
            library.update_character(ch["id"], **fields)
            changed += 1
    print(f"{kind} atribuídos: {changed} personagens")


def assign_backgrounds():
    _assign("fundos", library.backgrounds(), BUILTIN_BG_THEMES)


def assign_music():
    _assign("musicas", library.music())


def register():
    (library.DATA / "temas.json").write_text(json.dumps({k: v[0] for k, v in THEMES.items()}, indent=2,
                                                        ensure_ascii=False), encoding="utf-8")
    for bid, temas in BUILTIN_BG_THEMES.items():
        if library.get("fundos", bid) and not library.get("fundos", bid).get("temas"):
            item = library.get("fundos", bid)
            item["temas"] = temas
            (library.BGS / bid / "item.json").write_text(json.dumps(item, indent=2, ensure_ascii=False), encoding="utf-8")
    new = updated = 0
    for name, aliases, nicho, categoria, especialidades, profile, temas in CATALOG:
        meta = {"nicho": nicho, "categoria": categoria, "especialidades": especialidades, "temas_fundo": temas}
        ch = library.find_character(name)
        if ch:
            extra = [a for a in aliases if a not in ch.get("aliases", [])]
            library.update_character(ch["id"], aliases=ch.get("aliases", []) + extra, **meta)
            updated += 1
            continue
        pack = library.VOICES / f"{library.slug(name)}.pt"
        if not pack.exists():
            print("sem voz ainda:", name)
            continue
        with tempfile.TemporaryDirectory() as tmp:
            img = Path(tmp) / "provisoria.png"
            library.placeholder_image(img)
            item = library.add_character(name, img, "esquerda", "particulas_douradas",
                                         {"motor": "kokoro", "voz": str(pack)}, aliases=aliases)
        library.update_character(item["id"], imagem_provisoria=True, **meta)
        new += 1
    for name, (nicho, categoria, especialidades, temas) in EXTRA.items():
        ch = library.find_character(name)
        if ch:
            library.update_character(ch["id"], nicho=nicho, categoria=categoria, especialidades=especialidades,
                                     temas_fundo=temas)
    print(f"novos: {new}  atualizados: {updated}")
    assign_backgrounds()


if __name__ == "__main__":
    {"fundos": assign_backgrounds, "musicas": assign_music}.get((sys.argv[1:] or [""])[0], register)()
