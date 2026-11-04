"""Channels: each one has its own name and Drive folder (with its own metadata sheet); every batch belongs to one.
The Google account (credential + login) is shared by all channels."""
import json
import re
import threading
import time
import unicodedata

from . import library

FILE = library.DATA / "canais.json"
DEFAULT = "principal"  # batches made before channels existed belong to it
_lock = threading.Lock()


def _read():
    if not FILE.exists():  # first run: the folder configured before channels becomes the first channel
        old = library.DATA / "google" / "config.json"
        cfg = json.loads(old.read_text(encoding="utf-8")) if old.exists() else {}
        _write([{"id": DEFAULT, "nome": "Canal principal", **{k: cfg.get(k) for k in
                 ("pasta_id", "pasta_link", "planilha_id", "planilha_link")}}])
    return json.loads(FILE.read_text(encoding="utf-8"))


def _write(items):
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


def listar():
    with _lock:
        return _read()


def get(cid):
    found = next((c for c in listar() if c["id"] == cid), None)
    if not found:
        raise ValueError("Esse canal não existe mais. Escolha outro canal no topo da página.")
    return found


def of_batch(batch):
    return batch.get("canal") or DEFAULT


def create(nome):
    nome = (nome or "").strip()
    if not nome:
        raise ValueError("Dê um nome ao canal.")
    with _lock:
        items = _read()
        if any(c["nome"].lower() == nome.lower() for c in items):
            raise ValueError(f'Já existe um canal chamado "{nome}".')
        slug = re.sub(r"[^a-z0-9]+", "_", unicodedata.normalize("NFD", nome).encode("ascii", "ignore")
                      .decode().lower()).strip("_") or "canal"
        cid = slug if all(c["id"] != slug for c in items) else f"{slug}_{int(time.time())}"
        channel = {"id": cid, "nome": nome, "pasta_id": None, "pasta_link": None, "planilha_id": None,
                   "planilha_link": None}
        _write(items + [channel])
        return channel


def update(cid, **fields):
    with _lock:
        items = _read()
        channel = next((c for c in items if c["id"] == cid), None)
        if not channel:
            raise ValueError("Esse canal não existe mais.")
        if "nome" in fields:
            fields["nome"] = (fields["nome"] or "").strip()
            if not fields["nome"]:
                raise ValueError("Dê um nome ao canal.")
            if any(c["id"] != cid and c["nome"].lower() == fields["nome"].lower() for c in items):
                raise ValueError(f'Já existe um canal chamado "{fields["nome"]}".')
        channel.update(fields)
        _write(items)
        return channel


def delete(cid, batches):
    """Only a channel without batches can go (its videos would have nowhere to be shown)."""
    used = sum(1 for b in batches if of_batch(b) == cid)
    if used:
        raise ValueError(f"Esse canal tem {used} lote(s). Apague os lotes dele antes de excluir o canal.")
    with _lock:
        items = _read()
        if len(items) == 1:
            raise ValueError("Precisa existir pelo menos um canal.")
        _write([c for c in items if c["id"] != cid])
