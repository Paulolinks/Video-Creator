"""Read a script (TXT/MD pasted from ChatGPT, or PDF) and detect its template, title and scenes.

Recommended input: a plain-text roteiro, exactly as in the framework PDFs:
  T02  FORMATO: ENTREVISTA_COM_MENTOR -> "CENA 01 | PERSONAGEM: NOME" + fala
  F01  FORMATO: PERSONAGEM_FALANDO    -> "CENA 01 | MODO: FALA|DOLLY|ZOOM" + "NARRAÇÃO: ..." + "IMAGEM: ..."
Everything after a line "FIM" is ignored. The parser also tolerates the usual slips (CENA_01, Markdown bold,
PDF page headers, extra sections such as sources after the last scene).
English scripts use the same layout with English keywords (SCENE 01 | CHARACTER: NAME, or SCENE 01 — NAME;
MODE / NARRATION / IMAGE; TITLE / SUBTITLE / FORMAT; END). The language ("pt" or "en") comes from a
LANGUAGE:/IDIOMA: line, or is detected from the words of the text, and decides how the voice reads it.
Animation markers inside the spoken text ([CONTADOR: ...], [BARRAS: ...], [FLUXO: ...], [CARDS: ...],
[DESTAQUE: ...]) are removed from the text (never spoken) and kept per scene in "animacoes" (Smart Motion).
A scene of the character templates can also be a full-screen animation of the animation engine: an "ANIMACAO: nome"
block with its fields under it, or a [JORNADA: ...] marker. It is kept in scene["animacao"].
"""
import io
import re
import sys
from collections import Counter
from pathlib import Path

from pypdf import PdfReader

from .biblioteca_animacoes import custom_scenes

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "VIDEO_CREATOR_LAB" / "smart_motion"))
import marcacoes  # noqa: E402  (stdlib only: markers + spoken numbers)

TEMPLATES = {"T02": "Entrevista com mentor", "F01": "Personagem falando", "A01": "Só animação"}
# "Só animação" (A01): each block starts with "FALA: ..." and names its animation in "CENA: <tipo>"
CENAS_ANIMACAO = {"contador", "tabela", "console", "contato", "termostato", "busca", "barras", "produto", "comentario",
                  "mapa", "imagem", "frase", "celular", "mapapins", "painel", "linha", "linhadotempo", "comparar",
                  "medidor", "checklist", "relatorio", "formulario", "fluxo", "guardian3d", "jornada"}
# ("produto", "imagem"): the fields that name a picture sent with the script
_FALTA_ANIMACAO = "Se for nova, envie o arquivo dela em Animações e clique em Reanalisar."
_CAMPOS_IMAGEM = (("produto", "imagem"), ("imagem", "arquivo"), ("guardian3d", "imagem"))
_BLOCO_ANIMACAO = re.compile(r"^(?:ANIMA[ÇC][ÃA]O|ANIMATION)\s*:\s*([\w\- ]+?)\s*$", re.M | re.I)
_CAMPO_ANIMACAO = re.compile(r"^([\wÀ-ú]+)\s*:\s*(.*)$")
_FIM_BLOCO_ANIMACAO = {"IMAGEM", "IMAGE", "BUSCA", "SEARCH", "NARRAÇÃO", "NARRACAO", "NARRATION"}
_JORNADA_NA_FALA = re.compile(r"^(\s*FALA\s*:\s*)(.*?)\[\s*(?:JORNADA|JOURNEY|FUNIL|FUNNEL)\s*:\s*([^\[\]]*)\]\s*(.*)$", re.I)
_INICIO_CODIGO, _FIM_CODIGO = re.compile(r"^\s*CODIGO\s*:", re.I), re.compile(r"^\s*FIM_CODIGO\s*$", re.I)
_FALA = re.compile(r"^\s*FALA\s*:", re.M | re.I)
_FORMATO_ANIMACAO = re.compile(r"^\s*(?:FORMATO|FORMAT)\s*:\s*(?:A01\b|S[ÓO][\s_]*ANIMA|ANIMA)", re.M | re.I)
_BLOCO_NUMERADO = re.compile(r"^\s*(?:CENA|SCENE)[\s_\-]*\d+", re.M | re.I)
IDIOMAS = {"pt": "Português", "en": "Inglês"}
SCRIPT_EXT = (".txt", ".md", ".pdf")
_CENA = r"^(?:CENA|SCENE)[\s_\-]*(\d+)\s*[|:\-–—]\s*"
# "CENA 01 | PERSONAGEM: NOME", "SCENE 01 | CHARACTER: NAME" or just "SCENE 01 — NAME" (never "MODO: ...")
_SCENE_T02 = re.compile(_CENA + r"(?:(?:PERSONAGEM|CHARACTER|SPEAKER)\s*:\s*)?([^\n:|]+?)\s*$", re.M | re.I)
_SCENE_F01 = re.compile(_CENA + r"(?:MODO|MODE)\s*:\s*(\w+)\s*$", re.M | re.I)
_MODES = {"fala": "fala", "talk": "fala", "talking": "fala", "speak": "fala", "speaking": "fala",
          "dolly": "dolly", "zoom": "zoom", "animacao": "animacao", "animação": "animacao", "animation": "animacao"}
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


def episode(value):
    """'1 de 9', '1/9', 'Episódio 01 de 09', '1 of 9' -> {'numero': 1, 'total': 9}; '3' -> {'numero': 3, 'total': None};
    empty, the model's <...> or anything without a number -> None."""
    value = (value or "").strip()
    if not value or _PLACEHOLDER.search(value) or "<" in value:
        return None
    m = re.search(r"(\d+)\s*(?:/|de|of|-)\s*(\d+)", value, re.I) or re.search(r"(\d+)", value)
    if not m:
        return None
    total = int(m.group(2)) if m.lastindex and m.lastindex >= 2 else None
    return {"numero": int(m.group(1)), "total": total}


def episode_label(ep, idioma="pt"):
    """{'numero': 1, 'total': 9} -> 'EPISÓDIO 1 DE 9' (or 'EPISODE 1 OF 9')."""
    word, of = ("EPISODE", "OF") if idioma == "en" else ("EPISÓDIO", "DE")
    return f"{word} {ep['numero']}" + (f" {of} {ep['total']}" if ep.get("total") else "")


def _header(head):
    """Title/subtitle/format (and the optional series/episode) from the lines before the first scene."""
    info = {"titulo": "", "subtitulo": "", "formato": "", "personagem": "", "serie": "", "episodio": ""}
    loose = []
    for line in (x for x in head.splitlines() if x):
        m = re.match(r"^(T[ÍI]TULO(?: DA CAPA)?|SUBT[ÍI]TULO|FORMATO|PERSONAGEM|TEMA|(?:COVER )?TITLE|SUBTITLE|"
                     r"FORMAT|CHARACTER|TOPIC|THEME|LANGUAGE|IDIOMA|S[ÉE]RIES?|COLE[ÇC][ÃA]O|COLLECTION|"
                     r"EPIS[ÓO]DIO|EPISODE|EP)\s*:\s*(.*)$", line, re.I)
        if m:
            key, value = m.group(1).upper(), m.group(2).strip()
            if key.startswith(("SÉRIE", "SERIE", "COLE", "COLLECTION")):
                info["serie"] = "" if (_PLACEHOLDER.search(value) or "<" in value) else value
            elif key.startswith("EP"):
                info["episodio"] = value
            elif key.startswith("SUB"):
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


def _jornada_na_fala(line):
    """A01: "FALA: [JORNADA: ...] text" becomes the engine's own lines (FALA, CENA: jornada, titulo, etapa...)."""
    m = _JORNADA_NA_FALA.match(line)
    if not m:
        return line
    try:
        cena = marcacoes.jornada_para_cena(marcacoes.montar("journey", [c.strip() for c in m.group(3).split("|")]))
    except ValueError:
        return f"{m.group(1)}{m.group(2)}{m.group(4)}"  # no steps to draw: the parser reports the scene
    head = f"titulo: {cena['params']['titulo']}\n" if cena["params"]["titulo"] else ""
    return (f"{m.group(1)}{m.group(2)}{m.group(4)}\nCENA: jornada\n{head}"
            + "\n".join(f"etapa: {e}" for e in cena["params"]["etapa"]))


def animation_source(path):
    """An A01 script as the animation engine reads it. Not read_text(): that strips the '#' of comment lines."""
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        text = pdf_text(path)
    else:
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("cp1252")
    lines, in_code = [], False
    for x in text.splitlines():  # the code of a new animation goes to the engine exactly as it was written
        if _INICIO_CODIGO.match(x):
            in_code = True
        lines.append(x if in_code else _jornada_na_fala(x.replace("**", "").replace("`", "")))
        if _FIM_CODIGO.match(x):
            in_code = False
    text = "\n".join(lines)
    meta = _META_START.search(text)
    return text[:meta.start()] if meta else text


def _parse_animation(source, result):
    head, cenas, cur, in_code = {}, [], None, False
    for raw in source.splitlines():
        line = raw.strip()
        if _INICIO_CODIGO.match(line):
            in_code = True
        if in_code:
            in_code = not _FIM_CODIGO.match(line)
            continue
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = (x.strip() for x in line.split(":", 1))
        key = key.lower()
        if key == "fala":
            cur = {"id": f"CENA_{len(cenas) + 1:02}", "text": _clean(value), "cena": "frase", "imagens": []}
            cenas.append(cur)
        elif cur is None:
            head[key] = value
        elif key == "cena":
            cur["cena"] = value.lower()
        elif key == "etapa":
            cur.setdefault("etapas", []).append(value)
        elif (cur["cena"], key) in _CAMPOS_IMAGEM:
            cur["imagens"].append(value)
    result.update(template="A01", titulo=head.get("titulo") or head.get("título") or "", cenas=cenas,
                  personagens=[head["voz"].upper()] if head.get("voz") else [], avisos_animacao=[])
    if not cenas:
        result["problemas"].append("Nenhuma fala encontrada. Cada bloco começa numa linha FALA: ...")
    holes = sorted(set(_PLACEHOLDER.findall(" ".join(c["text"] for c in cenas))))
    if holes:
        result["problemas"].append(f"Campos do modelo não preenchidos: {', '.join(holes[:4])}. Troque pelo texto real.")
    known = CENAS_ANIMACAO | {s["nome"] for s in custom_scenes()}
    for c in cenas:
        if not c["text"]:
            result["problemas"].append(f"{c['id']} sem texto de fala.")
        if c["cena"] not in known:
            result["problemas"].append(f"{c['id']}: animação '{c['cena']}' não existe. {_FALTA_ANIMACAO} Disponíveis: "
                                       f"{', '.join(sorted(known))}.")
        if c["cena"] == "jornada":
            _check_journey(c, c.get("etapas", []), result)
    return result


def _check_journey(scene, etapas, result):
    problem, notes = marcacoes.checar_jornada(etapas, scene["text"])
    label = scene["id"].replace("_", " ").title()
    if problem:
        result["problemas"].append(f"{label}: {problem}")
    result["avisos_animacao"] += [f"{label}: {n}" for n in notes]


def _scene_animation(body):
    """A character-template scene's text -> (text without the "ANIMACAO: nome" block, {cena, params} or None).
    The block ends at the first blank line, or at a line that is not "field: value"."""
    m = _BLOCO_ANIMACAO.search(body)
    if not m:
        return body, None
    lines = body[m.end():].lstrip("\r\n").split("\n")
    params, used = {}, 0
    for line in lines:
        field = _CAMPO_ANIMACAO.match(line.strip())
        if not field or field.group(1).upper() in _FIM_BLOCO_ANIMACAO:
            break
        key, value = field.group(1).lower(), field.group(2).strip()
        params[key] = [*params[key], value] if isinstance(params.get(key), list) else [params[key], value] if key in params else value
        used += 1
    rest = "\n".join(lines[used:])
    return f"{body[:m.start()]}\n{rest}", {"cena": m.group(1).strip().lower(), "params": params}


def _check_scene_animations(result):
    """The animation scenes of a character template: known name, journey steps, pictures to send with the script."""
    known = CENAS_ANIMACAO | {s["nome"] for s in custom_scenes()}
    for c in result["cenas"]:
        anim = c.get("animacao")
        if c.get("mode") == "animacao" and not anim:
            n = c["id"].replace("_", " ").title()
            result["problemas"].append(f"{n} está no MODO ANIMACAO, mas não tem [JORNADA: ...] na narração nem a linha ANIMACAO: nome.")
        if not anim:
            continue
        if anim["cena"] not in known:
            result["problemas"].append(f"{c['id']}: animação '{anim['cena']}' não existe. {_FALTA_ANIMACAO} Disponíveis: "
                                       f"{', '.join(sorted(known))}.")
        c["imagens"] = [str(v) for (name, field) in _CAMPOS_IMAGEM if name == anim["cena"]
                        for v in ([anim["params"][field]] if field in anim["params"] else [])]
        if anim["cena"] == "jornada":
            e = anim["params"].get("etapa", [])
            _check_journey(c, [e] if isinstance(e, str) else e, result)




def _is_animation(source):
    return bool((_FALA.search(source) or _FORMATO_ANIMACAO.search(source)) and not _BLOCO_NUMERADO.search(source))


def parse_script(path):
    text = read_text(path)
    result = {"arquivo": Path(path).name, "template": None, "titulo": "", "subtitulo": "", "cenas": [],
              "personagens": [], "problemas": [], "idioma": language(text), "metadados": metadata(text),
              "serie": None, "episodio": None}
    if re.search(r"FRAMEWORK DE ROTEIRO|SCRIPT FRAMEWORK", text, re.I):
        result["problemas"].append("Este arquivo é o próprio framework (o modelo). Envie o roteiro que o ChatGPT "
                                   "criou a partir dele.")
        return result
    source = animation_source(path)
    if _is_animation(source):
        return _parse_animation(source, result)
    scenes = list(_SCENE_T02.finditer(text)) + list(_SCENE_F01.finditer(text))
    first = min([m.start() for m in scenes], default=len(text))
    stop = _STOP.search(text, first)
    if stop:
        text = text[:stop.start()]
    t02 = list(_SCENE_T02.finditer(text))
    f01 = list(_SCENE_F01.finditer(text))
    info = _header(text[:first])
    result.update(titulo=info["titulo"], subtitulo=info["subtitulo"])
    # series cover only when BOTH are filled; empty/missing lines = a single video with the usual cover
    ep = episode(info["episodio"])
    result["serie"] = info["serie"] if info["serie"] and ep else None
    result["episodio"] = ep if info["serie"] and ep else None
    fmt = info["formato"]
    if "ENTREVISTA" in fmt or "INTERVIEW" in fmt or (t02 and not f01):
        result["template"] = "T02"
        for i, m in enumerate(t02):
            end = t02[i + 1].start() if i + 1 < len(t02) else len(text)
            name = _clean(m.group(2)).upper()
            body, anim = _scene_animation(text[m.end():end].strip())
            body = re.sub(rf"^{re.escape(name)}\s*:\s*", "", body.strip(), flags=re.I)  # "NOME: fala"
            result["cenas"].append({"id": f"CENA_{int(m.group(1)):02}", "personagem": name, "text": _clean(body),
                                    "animacao": anim})
        result["personagens"] = list(dict.fromkeys(c["personagem"] for c in result["cenas"]))
    elif "PERSONAGEM_FALANDO" in fmt or "CHARACTER_TALKING" in fmt or f01:
        result["template"] = "F01"
        for i, m in enumerate(f01):
            end = f01[i + 1].start() if i + 1 < len(f01) else len(text)
            body, anim = _scene_animation(text[m.end():end])
            narr = re.search(r"(?:NARRA[ÇC][ÃA]O|NARRATION)\s*:\s*(.*?)(?=^IMAGE[M]?\s*:|^(?:BUSCA|SEARCH)\s*:|\Z)",
                             body, re.S | re.M | re.I)
            img = re.search(r"^IMAGE[M]?\s*:\s*(.*?)(?=^(?:BUSCA|SEARCH)\s*:|\Z)", body, re.S | re.M | re.I)
            busca = re.search(r"^(?:BUSCA|SEARCH)\s*:\s*(.*)$", body, re.M | re.I)  # image-bank keywords
            mode = m.group(2).lower()
            result["cenas"].append({"id": f"CENA_{int(m.group(1)):02}", "mode": _MODES.get(mode, mode),
                                    "text": _clean(narr.group(1)) if narr else "",
                                    "descricao_imagem": _clean(img.group(1)) if img else "",
                                    "busca": _clean(busca.group(1)) if busca else "", "animacao": anim})
        if info["personagem"]:
            result["personagens"] = [info["personagem"].upper()]
    result["avisos_animacao"] = _animations(result["cenas"])
    _check_scene_animations(result)
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
        if c.get("mode") and c["mode"] not in ("fala", "dolly", "zoom", "animacao"):
            result["problemas"].append(f"{c['id']}: modo '{c['mode']}' desconhecido (use FALA, DOLLY, ZOOM ou ANIMACAO).")
    return result


def _animations(scenes):
    """Strip the Smart Motion markers from each scene's text (they are not spoken) and keep them in
    scene["animacoes"]. Returns warnings; an animation whose numbers are not spoken in the scene is dropped."""
    warnings = []
    for c in scenes:
        c["text"], anims, notes = marcacoes.extrair(c["text"])
        label = c["id"].replace("_", " ").title()
        warnings += [f"{label}: {n}" for n in notes]
        kept = []
        for a in anims:
            if a["tipo"] == "journey":
                c["animacao"] = c.get("animacao") or marcacoes.jornada_para_cena(a["payload"])
                continue
            missing = marcacoes.checar_no_texto(a, c["text"])
            if missing:
                vals = ", ".join(f"{v:,.0f}".replace(",", ".") if v == int(v) else str(v) for v in missing)
                warnings.append(f"{label}: {marcacoes.NOMES[a['tipo']]} ignorado, o valor {vals} não é dito na fala "
                                "desta cena (escreva o número por extenso na fala).")
            else:
                kept.append(a)
        if c.get("animacao"):
            if kept:
                warnings.append(f"{label}: a animação ocupa a tela toda, então as outras marcações desta cena foram removidas.")
                kept = []
            if c.get("mode") not in (None, "animacao"):
                warnings.append(f"{label} virou MODO ANIMACAO por causa da animação marcada nela.")
                c["mode"] = "animacao"
        c["animacoes"] = kept
    return warnings


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
