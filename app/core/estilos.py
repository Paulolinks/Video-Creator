"""Caption look (font, size, colours) and video format (vertical 9:16 or YouTube 16:9) chosen on the home page.

apply() writes them into the per-video copy of the engine template; nothing here changes the approved templates.
"""
import re
import shutil
from pathlib import Path

LAB = Path(r"D:\Video-Creator\VIDEO_CREATOR_LAB")
LAB_FONTS = LAB / "inputs" / "fonts"
WIN_FONTS = Path(r"C:\Windows\Fonts")
FONT_CACHE = LAB / ".cache" / "fontes_legenda"  # one folder per font: libass reads a single fonts dir

# id: (name on screen, ASS family, file, bold flag)
FONTES = {
    "poppins": ("Poppins (padrão)", "Poppins", LAB_FONTS / "Poppins-Bold.ttf", True),
    "poppins_extra": ("Poppins ExtraBold", "Poppins ExtraBold", LAB_FONTS / "Poppins-ExtraBold.ttf", False),
    "impact": ("Impact", "Impact", WIN_FONTS / "impact.ttf", False),
    "arial_black": ("Arial Black", "Arial Black", WIN_FONTS / "ariblk.ttf", False),
    "segoe_black": ("Segoe UI Black", "Segoe UI Black", WIN_FONTS / "seguibl.ttf", False),
    "verdana": ("Verdana", "Verdana", WIN_FONTS / "verdanab.ttf", True),
    "trebuchet": ("Trebuchet", "Trebuchet MS", WIN_FONTS / "trebucbd.ttf", True),
    "georgia": ("Georgia (serifa)", "Georgia", WIN_FONTS / "georgiab.ttf", True),
    "comic": ("Comic Sans", "Comic Sans MS", WIN_FONTS / "comicbd.ttf", True),
}

FORMATOS = {
    "vertical": {"nome": "Vertical 9:16", "uso": "Shorts · Reels · TikTok", "largura": 1080, "altura": 1920},
    "horizontal": {"nome": "Horizontal 16:9", "uso": "YouTube", "largura": 1920, "altura": 1080},
}

PADRAO = {"formato": "vertical", "fonte": "poppins", "tamanho": 84, "cor": "#FFD745", "cor_texto": "#FFFFFF"}
TAMANHO_MIN, TAMANHO_MAX = 40, 140


def catalog():
    fontes = [{"id": k, "nome": n, "familia": fam, "url": f"/fontes/{k}"}
              for k, (n, fam, path, _) in FONTES.items() if path.exists()]
    return {"fontes": fontes, "formatos": FORMATOS, "padrao": PADRAO,
            "tamanho_min": TAMANHO_MIN, "tamanho_max": TAMANHO_MAX}


def font_file(fid):
    item = FONTES.get(fid)
    return item[2] if item and item[2].exists() else None


def _ass_colour(hex_colour, fallback):
    """#RRGGBB -> &H00BBGGRR (ASS is blue-green-red)."""
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", str(hex_colour or ""))
    if not m:
        return _ass_colour(fallback, "#FFFFFF")
    rr, gg, bb = m.group(1)[0:2], m.group(1)[2:4], m.group(1)[4:6]
    return f"&H00{bb}{gg}{rr}".upper()


def _fonts_dir(fid):
    """Poppins is always there (T02 name labels use Poppins ExtraBold) plus the chosen font."""
    folder = FONT_CACHE / fid
    folder.mkdir(parents=True, exist_ok=True)
    for src in {LAB_FONTS / "Poppins-Bold.ttf", LAB_FONTS / "Poppins-ExtraBold.ttf", FONTES[fid][2]}:
        dst = folder / src.name
        if src.exists() and (not dst.exists() or dst.stat().st_size != src.stat().st_size):
            shutil.copy2(src, dst)
    return str(folder)


def resolve(opcoes):
    """The options as sent by the page, validated, with defaults."""
    o = {**PADRAO, **{k: v for k, v in (opcoes or {}).items() if k in PADRAO and v not in (None, "")}}
    if o["formato"] not in FORMATOS:
        o["formato"] = PADRAO["formato"]
    if not font_file(o["fonte"]):
        o["fonte"] = PADRAO["fonte"]
    try:
        o["tamanho"] = max(TAMANHO_MIN, min(TAMANHO_MAX, int(o["tamanho"])))
    except (TypeError, ValueError):
        o["tamanho"] = PADRAO["tamanho"]
    return o


def apply(tpl, template_id, opcoes):
    o = resolve(opcoes)
    fmt = FORMATOS[o["formato"]]
    tpl["video"].update(largura=fmt["largura"], altura=fmt["altura"])
    lg = tpl.setdefault("legenda", {})
    _, family, _, bold = FONTES[o["fonte"]]
    look = {"fonte": family, "negrito": bold, "tamanho": o["tamanho"], "contorno": max(3, round(7 * o["tamanho"] / 84)),
            "cor_falada": _ass_colour(o["cor"], PADRAO["cor"]),
            "cor_aguardando": _ass_colour(o["cor_texto"], PADRAO["cor_texto"])}
    lg["fontes_dir"] = _fonts_dir(o["fonte"])
    if template_id == "F01":
        lg["ass"] = look  # the F01 template keeps descriptive values ("dourado"); the composer reads these
        if o["formato"] == "horizontal":
            lg["margem_inferior"] = 110
            lg["ass"]["max_palavras"] = 4
    else:
        lg.update(look)
        if o["formato"] == "horizontal":  # portrait at the side, wave on the other side, captions low
            tpl["retrato"].update(largura=900, altura_max=1000, deslocamento_borda=40)
            tpl["onda"]["centro_y"] = 470
            lg.update(centro_y=900, max_caracteres=30, max_palavras=4)
            tpl.setdefault("rotulos", {}).update(nome_y=70, aviso_y=30, logo_y=20)
    return o
