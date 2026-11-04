"""Read a script (TXT/MD pasted from ChatGPT, or PDF) and detect its template, title and scenes.

Recommended input: a plain-text roteiro, exactly as in the framework PDFs:
  T02  FORMATO: ENTREVISTA_COM_MENTOR -> "CENA 01 | PERSONAGEM: NOME" + fala
  F01  FORMATO: PERSONAGEM_FALANDO    -> "CENA 01 | MODO: FALA|DOLLY|ZOOM" + "NARRAÇÃO: ..." + "IMAGEM: ..."
Everything after a line "FIM" is ignored. The parser also tolerates the usual slips (CENA_01, Markdown bold,
PDF page headers, extra sections such as sources after the last scene).
English scripts use the same layout with English keywords (SCENE 01 | CHARACTER: NAME, or SCENE 01 — NAME;
MODE / NARRATION / IMAGE; TITLE / SUBTITLE / FORMAT; END). The language ("pt" or "en") comes from a
LANGUAGE:/IDIOMA: line, or is detected from the words of the text, and decides how the voice reads it.
"""
import io
import re
from collections import Counter
from pathlib import Path

from pypdf import PdfReader

TEMPLATES = {"T02": "Entrevista com mentor", "F01": "Personagem falando"}
IDIOMAS = {"pt": "Português", "en": "Inglês"}
SCRIPT_EXT = (".txt", ".md", ".pdf")
_CENA = r"^(?:CENA|SCENE)[\s_\-]*(\d+)\s*[|:\-–—]\s*"
# "CENA 01 | PERSONAGEM: NOME", "SCENE 01 | CHARACTER: NAME" or just "SCENE 01 — NAME" (never "MODO: ...")
_SCENE_T02 = re.compile(_CENA + r"(?:(?:PERSONAGEM|CHARACTER|SPEAKER)\s*:\s*)?([^\n:|]+?)\s*$", re.M | re.I)
_SCENE_F01 = re.compile(_CENA + r"(?:MODO|MODE)\s*:\s*(\w+)\s*$", re.M | re.I)
_MODES = {"fala": "fala", "talk": "fala", "talking": "fala", "speak": "fala", "speaking": "fala",
          "dolly": "dolly", "zoom": "zoom"}
# end of the script: "FIM"/"END", the framework's technical section, the post description, or a numbered
# section heading such as "3. Descrição sugerida para publicação" that ChatGPT adds after the scenes
_STOP = re.compile(r"^(FIM\b.*|END\b.*|PADR[ÃA]O FIXO.*|POST DESCRIPTION.*|DESCRI[ÇC][ÃA]O DO POST.*|METADADOS\b.*|"
                   r"METADATA\b.*|\d{1,2}\.\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][^.!?]{0,70})$", re.M)
# Post metadata written by ChatGPT after FIM (block METADADOS / METADATA). A field runs until the next field;
# HASHTAGS is the last one and takes only its own line, so image prompts pasted after it are not swallowed.
_META_START = re.compile(r"^(?:METADADOS|METADATA|POST DESCRIPTION|DESCRI[ÇC][ÃA]O DO POST)\b", re.M)
_META_KEY = re.compile(r"^(T[ÍI]TULO DO POST|POST TITLE|DESCRI[ÇC][ÃA]O(?: DO POST)?|(?:POST )?DESCRIPTION"
                       r"(?: \(NOT SPOKEN\))?|NOTA EDITORIAL|EDITORIAL NOTE|HASHTAGS)\s*:?\s*(.*)$", re.M)
_PLACEHOLDER = re.compile(r"<[^<>\n]{2,40}>")
_LANG_LINE = re.compile(r"^(?:LANGUAGE|IDIOMA|L[ÍI]NGUA)\s*:\s*(\w+)", re.M | re.I)
_WORDS = {"pt": {"de", "que", "não", "nao", "você", "voce", "é", "para", "uma", "com", "os", "as", "do", "da",
                 "em", "um", "isso", "mais", "está", "como", "mas", "eu", "seu", "sua", "quando", "muito"},
          "en": {"the", "and", "you", "is", "to", "of", "that", "what", "your", "it", "in", "are", "this",
                 "with", "for", "do", "how", "we", "but", "not", "have", "can", "about", "when", "my"}}


def _clean(text):
    return re.sub(r"\s+", " ", text).strip()


def _tidy(line):
    """Drop Markdown decoration: headings, quotes, bold, code fences."""
    line = line.strip().replace("**", "").replace("`", "")
    return re.sub(r"^[#>\s]+", "", line).strip()


def pdf_text(path):
    """Text of all pages without the repeated page header/footer lines and bare page numbers."""
    pages = [[_tidy(x) for x in (p.extract_text() or "").splitlines()] for p in PdfReader(str(path)).pages]
    edges = Counter(x for lines in pages for x in set(lines[:3] + lines[-3:]) if x)
    repeated = {x for x, n in edges.items() if n >= 2 and len(pages) >= 2}
    return "\n".join(x for lines in pages for x in lines if x not in repeated and not x.isdigit())


def read_text(path):
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        return pdf_text(path)
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp1252"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    return "\n".join(_tidy(x) for x in text.splitlines())


def language(text):
    """'en' or 'pt': the script's LANGUAGE/IDIOMA line when there is one, otherwise the most common words."""
    m = _LANG_LINE.search(text)
    if m:
        value = m.group(1).upper()
        if value.startswith(("ENG", "ING", "EN")):
            return "en"
        if value.startswith(("PORT", "PT")):
            return "pt"
    words = re.findall(r"[a-záéíóúâêôãõç]+", text.lower())
    hits = {lang: sum(w in common for w in words) for lang, common in _WORDS.items()}
    return "en" if hits["en"] > hits["pt"] else "pt"


def metadata(text):
    """{'titulo', 'descricao', 'hashtags'} found in the script's METADADOS block (only the fields that are filled).
    The editorial note goes at the end of the description."""
    start = _META_START.search(text)
    if not start:
        return {}
    keys = list(_META_KEY.finditer(text, start.start()))
    fields = {}
    for i, m in enumerate(keys):
        key = m.group(1).upper()
        if key == "HASHTAGS":
            fields["hashtags"] = m.group(2).strip()
            break
        end = keys[i + 1].start() if i + 1 < len(keys) else len(text)
        value = "\n".join(x.strip() for x in (m.group(2) + text[m.end():end]).strip().splitlines()).strip()
        value = re.sub(r"\n{3,}", "\n\n", value)
        name = ("titulo" if "TULO" in key or "TITLE" in key else "nota" if "NOTA" in key or "NOTE" in key
                else "descricao")
        fields[name] = value
    if fields.get("nota"):
        fields["descricao"] = "\n\n".join(x for x in (fields.get("descricao"), fields["nota"]) if x)
    fields.pop("nota", None)
    # the model's <...> left unfilled: ignore that field (these placeholders are longer than _PLACEHOLDER allows)
    return {k: v for k, v in fields.items() if v and not re.search(r"<[^<>\n]{2,120}>", v)}


def _header(head):
    """Title/subtitle/format from the lines before the first scene."""
    info = {"titulo": "", "subtitulo": "", "formato": "", "personagem": ""}
    loose = []
    for line in (x for x in head.splitlines() if x):
        m = re.match(r"^(T[ÍI]TULO(?: DA CAPA)?|SUBT[ÍI]TULO|FORMATO|PERSONAGEM|TEMA|(?:COVER )?TITLE|SUBTITLE|"
                     r"FORMAT|CHARACTER|TOPIC|THEME|LANGUAGE|IDIOMA)\s*:\s*(.*)$", line, re.I)
        if m:
            key, value = m.group(1).upper(), m.group(2).strip()
            if key.startswith("SUB"):
                info["subtitulo"] = value
            elif "TULO" in key or "TITLE" in key:
                info["titulo"] = value
            elif key in ("FORMATO", "FORMAT"):
                info["formato"] = value.split("|")[0].strip().upper()
            elif key in ("PERSONAGEM", "CHARACTER"):
                info["personagem"] = value
            continue
        if not info["formato"]:
            loose.append(line)
    if not info["titulo"] and loose:  # cover layout: title lines, then one subtitle line
        info["titulo"] = _clean(" ".join(loose[:-1] if len(loose) > 1 else loose))
        if len(loose) > 1 and not info["subtitulo"]:
            info["subtitulo"] = loose[-1]
    return info


def parse_script(path):
    text = read_text(path)
    result = {"arquivo": Path(path).name, "template": None, "titulo": "", "subtitulo": "", "cenas": [],
              "personagens": [], "problemas": [], "idioma": language(text), "metadados": metadata(text)}
    if re.search(r"FRAMEWORK DE ROTEIRO|SCRIPT FRAMEWORK", text, re.I):
        result["problemas"].append("Este arquivo é o próprio framework (o modelo). Envie o roteiro que o ChatGPT "
                                   "criou a partir dele.")
        return result
    scenes = list(_SCENE_T02.finditer(text)) + list(_SCENE_F01.finditer(text))
    first = min([m.start() for m in scenes], default=len(text))
    stop = _STOP.search(text, first)
    if stop:
        text = text[:stop.start()]
    t02 = list(_SCENE_T02.finditer(text))
    f01 = list(_SCENE_F01.finditer(text))
    info = _header(text[:first])
    result.update(titulo=info["titulo"], subtitulo=info["subtitulo"])
    fmt = info["formato"]
    if "ENTREVISTA" in fmt or "INTERVIEW" in fmt or (t02 and not f01):
        result["template"] = "T02"
        for i, m in enumerate(t02):
            end = t02[i + 1].start() if i + 1 < len(t02) else len(text)
            name = _clean(m.group(2)).upper()
            body = text[m.end():end].strip()
            body = re.sub(rf"^{re.escape(name)}\s*:\s*", "", body, flags=re.I)  # "NOME: fala"
            result["cenas"].append({"id": f"CENA_{int(m.group(1)):02}", "personagem": name, "text": _clean(body)})
        result["personagens"] = list(dict.fromkeys(c["personagem"] for c in result["cenas"]))
    elif "PERSONAGEM_FALANDO" in fmt or "CHARACTER_TALKING" in fmt or f01:
        result["template"] = "F01"
        for i, m in enumerate(f01):
            end = f01[i + 1].start() if i + 1 < len(f01) else len(text)
            body = text[m.end():end]
            narr = re.search(r"(?:NARRA[ÇC][ÃA]O|NARRATION)\s*:\s*(.*?)(?=^IMAGE[M]?\s*:|\Z)", body,
                             re.S | re.M | re.I)
            img = re.search(r"^IMAGE[M]?\s*:\s*(.*)", body, re.S | re.M | re.I)
            mode = m.group(2).lower()
            result["cenas"].append({"id": f"CENA_{int(m.group(1)):02}", "mode": _MODES.get(mode, mode),
                                    "text": _clean(narr.group(1)) if narr else "",
                                    "descricao_imagem": _clean(img.group(1)) if img else ""})
        if info["personagem"]:
            result["personagens"] = [info["personagem"].upper()]
    if not result["template"]:
        result["problemas"].append("Não identifiquei o template: o roteiro precisa da linha FORMATO e dos blocos "
                                   "CENA 01 | PERSONAGEM: ... (Entrevista) ou CENA 01 | MODO: ... (Personagem falando).")
    elif not result["cenas"]:
        result["problemas"].append("Nenhuma cena encontrada. Cada cena começa numa linha própria, ex.: "
                                   "CENA 01 | PERSONAGEM: PAULO")
    filled = " ".join([result["titulo"], result["subtitulo"], *result["personagens"], *(c["text"] for c in result["cenas"])])
    holes = sorted(set(_PLACEHOLDER.findall(filled)))
    if holes:
        result["problemas"].append(f"Campos do modelo não preenchidos: {', '.join(holes[:4])}. Troque pelo texto real.")
    if not result["titulo"]:
        result["problemas"].append("Falta a linha TÍTULO: ...")
    for c in result["cenas"]:
        if not c["text"]:
            result["problemas"].append(f"{c['id']} sem texto de fala.")
        if c.get("mode") and c["mode"] not in ("fala", "dolly", "zoom"):
            result["problemas"].append(f"{c['id']}: modo '{c['mode']}' desconhecido (use FALA, DOLLY ou ZOOM).")
    return result


def embedded_images(path, min_side=300):
    """Images embedded in a PDF, in page order (used as F01 scene images when no files were uploaded)."""
    if Path(path).suffix.lower() != ".pdf":
        return []
    out = []
    for page in PdfReader(str(path)).pages:
        for img in page.images:
            try:
                im = img.image
            except Exception:
                continue
            if min(im.size) >= min_side:
                buf = io.BytesIO()
                im.convert("RGB").save(buf, "PNG")
                out.append(buf.getvalue())
    return out
