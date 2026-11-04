"""Post metadata (description + hashtags) from the script itself, with Ollama; a local fallback never leaves it empty.

The title is the script's own (it is also on the cover), so the AI only writes the description, ending with a
provocative question that invites comments, and the hashtags.
"""
import json
import os
import re
import subprocess
import time
import unicodedata
from pathlib import Path

import requests

from . import library

CONFIG = library.DATA / "metadados_ia.json"
HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
if not HOST.startswith("http"):
    HOST = "http://" + HOST
MIN_TEXT = 50  # shorter scripts make the AI invent generic text
PLACEHOLDERS = ("titulo", "subtitulo", "formato", "mentor", "nicho", "temas", "roteiro")

DEFAULT_PROMPT = """Você escreve a descrição e as hashtags de um vídeo curto (Reels, Shorts, TikTok) em PORTUGUÊS DO BRASIL.
Responda somente com JSON válido, sem comentários.

TÍTULO (já aparece na capa; não repita): {titulo}
SUBTÍTULO: {subtitulo}
FORMATO: {formato}
MENTOR: {mentor} | nicho: {nicho} | temas: {temas}

ROTEIRO:
{roteiro}

DESCRIÇÃO (máximo 300 caracteres):
- Uma frase curta que dá o contexto da conversa, sem repetir o título.
- Termine com UMA pergunta provocativa, pessoal e direta, que faça a pessoa comentar se já viveu aquilo
  (ex.: "Você já...?", "Qual foi a última vez que...?", "O que te impede de...?").
- Tom humano, de rede social. Nada de "veja até o fim", "neste vídeo" ou clichês.

HASHTAGS: 5 a 8, EM PORTUGUÊS (nada de inglês), minúsculas, sem acento, sem repetir, ligadas ao tema do
roteiro e ao nicho do mentor (ex.: #psicologia #autoconhecimento #habitos #mudanca #mentalidade).

{"descricao": "contexto curto + pergunta provocativa?", "hashtags": "#tema #nicho #emocao #intencao #outra"}"""

# English scripts get an English description and English hashtags (same JSON keys).
DEFAULT_PROMPT_EN = """You write the description and hashtags of a short video (Reels, Shorts, TikTok) in ENGLISH.
Answer only with valid JSON, no comments.

TITLE (already on the cover; do not repeat it): {titulo}
SUBTITLE: {subtitulo}
FORMAT: {formato}
GUEST: {mentor} | niche: {nicho} | topics: {temas}

SCRIPT:
{roteiro}

DESCRIPTION (300 characters max):
- One short sentence giving the context of the conversation, without repeating the title.
- End with ONE provocative, personal and direct question that makes people comment on their own experience
  (e.g. "Have you ever...?", "When was the last time...?", "What stops you from...?").
- Human, social-media tone. No "watch until the end", "in this video" or clichés.

HASHTAGS: 5 to 8, IN ENGLISH, lowercase, no repeats, tied to the script's topic and the guest's niche.

{"descricao": "short context + provocative question?", "hashtags": "#topic #niche #emotion #intent #other"}"""


def config():
    cfg = {"modelo": "llama3:latest", "prompt": DEFAULT_PROMPT, "prompt_en": DEFAULT_PROMPT_EN}
    if CONFIG.exists():
        cfg.update(json.loads(CONFIG.read_text(encoding="utf-8")))
    return cfg


def save_config(modelo=None, prompt=None):
    cfg = config()
    if modelo:
        cfg["modelo"] = modelo
    if prompt is not None:
        cfg["prompt"] = prompt.strip() or DEFAULT_PROMPT
    CONFIG.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    return cfg


def models():
    """Installed Ollama models, or [] when Ollama is not running."""
    try:
        return [m["name"] for m in requests.get(f"{HOST}/api/tags", timeout=5).json().get("models", [])]
    except requests.RequestException:
        return []


def context(video):
    """Prompt fields from a batch video: the mentor is the main non-host character."""
    status = video.get("personagens_status") or {}
    chars = [library.get("personagens", status[n]) if status.get(n) else library.find_character(n)
             for n in video["personagens"]]
    chars = [c for c in chars if c]
    main = next((c for c in chars if c.get("nicho") != "Apresentador"), chars[0] if chars else {})
    roteiro = "\n".join(f"{c.get('personagem') or 'NARRADOR'}: {c['text']}" for c in video["cenas"] if c.get("text"))
    return {"titulo": video.get("titulo") or "", "subtitulo": video.get("subtitulo") or "",
            "formato": video.get("template_nome") or "", "mentor": main.get("nome", ""),
            "nicho": main.get("nicho") or "", "temas": main.get("especialidades") or main.get("categoria") or "",
            "roteiro": roteiro, "idioma": video.get("idioma", "pt")}


def render(prompt, ctx):
    for key in PLACEHOLDERS:  # replace() instead of format(): the prompt's JSON example has braces
        prompt = prompt.replace("{" + key + "}", ctx.get(key, ""))
    return prompt


def parse_json(text):
    """JSON object from a model answer: strips ``` fences, takes the balanced {...} and closes a missing '}'."""
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    start = text.find("{")
    if start == -1:
        raise ValueError("a resposta não tem JSON")
    depth, end = 0, None
    for i, ch in enumerate(text[start:], start):
        depth += (ch == "{") - (ch == "}")
        if depth == 0:
            end = i + 1
            break
    candidate = text[start:end] if end else text[start:] + "}" * depth
    for attempt in (candidate, re.sub(r",(\s*[}\]])", r"\1", candidate), candidate.replace("\n", " ")):
        try:
            return json.loads(attempt)
        except json.JSONDecodeError:
            continue
    raise ValueError(f"JSON inválido: {candidate[:120]}")


def clean_hashtags(tags):
    """'#Motivação, mindset' or ['a','b'] -> '#motivacao #mindset' (lowercase, no accents, unique, max 8)."""
    if isinstance(tags, list):
        tags = " ".join(str(t) for t in tags)
    out = []
    for word in re.split(r"[\s,;]+", tags or ""):
        word = unicodedata.normalize("NFD", word.lower())
        word = re.sub(r"[^a-z0-9_]", "", "".join(c for c in word if unicodedata.category(c) != "Mn"))
        if word and f"#{word}" not in out:
            out.append(f"#{word}")
    return " ".join(out[:8])


def valid(meta):
    desc, tags = meta.get("descricao", ""), meta.get("hashtags", "")
    return 0 < len(desc) <= 500 and len(tags.split()) >= 2


def local(ctx):
    """No-AI fallback: first sentence of the mentor's speech + a generic question; tags from the niche."""
    lines = [l.split(": ", 1)[-1] for l in ctx["roteiro"].splitlines()]
    speech = next((l for l in lines[1:] if l), lines[0] if lines else ctx["titulo"])
    first = re.split(r"(?<=[.!?])\s", speech.strip())[0][:200]
    words = " ".join([ctx["nicho"], ctx["temas"], ctx["mentor"].replace(" ", ""), "reflexao desenvolvimentopessoal"])
    tags = clean_hashtags([w for w in re.split(r"[\s,;]+", words) if len(w) > 3])  # skips "e", "de", "para"
    if ctx.get("idioma") == "en":
        return {"descricao": f"{first} Have you ever been through this? Tell us in the comments.",
                "hashtags": clean_hashtags([w for w in re.split(r"[\s,;]+", ctx["nicho"] + " " + ctx["temas"])
                                            if len(w) > 3] + ["mindset", "personalgrowth"])}
    return {"descricao": f"{first} Você já passou por isso? Conta aqui nos comentários.", "hashtags": tags}


def generate(video):
    """{'descricao', 'hashtags', 'origem': 'ia'|'local', 'modelo', 'aviso'?} for one batch video."""
    ctx = context(video)
    cfg = config()
    if len(ctx["roteiro"].strip()) < MIN_TEXT:
        return {**local(ctx), "origem": "local", "modelo": None, "aviso": "Roteiro curto demais para a IA."}
    prompt = render(cfg["prompt_en"] if ctx["idioma"] == "en" else cfg["prompt"], ctx)
    error = None
    for _ in range(3):  # llama3 sometimes answers empty or with broken JSON
        try:
            r = requests.post(f"{HOST}/api/generate", timeout=300, json={
                "model": cfg["modelo"], "prompt": prompt, "stream": False, "format": "json",
                "keep_alive": 0,  # free the GPU for the next video of the batch
                "options": {"temperature": 0.7, "top_p": 0.9}})
            r.raise_for_status()
            data = parse_json(r.json().get("response", ""))
            meta = {"descricao": str(data.get("descricao") or data.get("caption") or "").strip(),
                    "hashtags": clean_hashtags(data.get("hashtags", ""))}
            if valid(meta):
                return {**meta, "origem": "ia", "modelo": cfg["modelo"]}
            error = "resposta da IA incompleta"
        except requests.ConnectionError:
            error = "o Ollama não está aberto"
            break
        except (requests.RequestException, ValueError) as exc:
            error = str(exc)
    return {**local(ctx), "origem": "local", "modelo": None, "aviso": f"Usei o texto automático: {error}."}


def tag_mp4(path, titulo, descricao, hashtags):
    """Write the metadata inside the MP4 without re-encoding (ffmpeg -c copy). Returns the file to use: the video
    itself; the tagged copy when the video is open in a player and cannot be replaced; the untagged video on failure."""
    path = Path(path)
    tmp = path.with_name(path.stem + "_meta.mp4")
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-map", "0", "-c", "copy",
                        "-metadata", f"title={titulo}", "-metadata", f"comment={descricao}",
                        "-metadata", f"description={descricao}", "-metadata", f"keywords={hashtags}",
                        "-metadata", "album=Video Creator", "-movflags", "+faststart", str(tmp)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        tmp.unlink(missing_ok=True)
        return path
    for _ in range(5):
        try:
            tmp.replace(path)
            return path
        except PermissionError:  # Windows: the app's player (or another program) has the video open
            time.sleep(1)
    return tmp
