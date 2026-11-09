"""Google Drive + Sheets: each channel has its own Drive folder; the videos go there and one row per video goes to a
spreadsheet the app creates inside that same folder (same columns as the Video Cutter's sheet).

Lessons from the Video Cutter (docs/REFERENCIA_VIDEO_CREATOR_METADADOS_DRIVE.md):
- the credential must be a "Desktop app" one ({"installed": ...}); a "web" one makes the login fail;
- this app keeps its own token.json (data/google), and logs in on a free port (the Cutter uses 5501);
- drive.file only sees files the app created: the sheet is read and written through the Sheets API;
- rows are only appended, and the count is in result["updates"]["updatedRows"].
"""
import json
import re
import threading
import time
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from . import canais, jobs, library, metadados

DIR = library.DATA / "google"
CREDENTIALS, TOKEN = DIR / "credentials.json", DIR / "token.json"
SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/spreadsheets"]
SHEET_NAME = "Video Creator - Metadados"
HEADER = ["Arquivo", "Transcrição", "Título", "Hashtag", "Tipo", "Video_ID"]
SHEET_MIME = "application/vnd.google-apps.spreadsheet"
_sending = set()  # batches being uploaded right now
_send_lock = threading.Lock()


def status():
    """The Google account (shared by every channel)."""
    return {"credencial": CREDENTIALS.exists(), "conectado": TOKEN.exists()}


def extract_id(text):
    """Accept the whole link (folder or sheet) or the bare ID."""
    text = (text or "").strip()
    if "/my-drive" in text or text.lower() in ("root", "meu drive", "my drive"):
        return "root"  # the "Meu Drive" page itself (its link has no folder ID)
    m = re.search(r"/folders/([\w-]+)|/d/([\w-]+)|[?&]id=([\w-]+)", text)
    if m:
        return next(g for g in m.groups() if g)
    return text if re.fullmatch(r"[\w-]{20,}", text) else None


def save_credentials(raw):
    try:
        data = json.loads(raw)
    except ValueError:
        raise ValueError("Esse arquivo não é um JSON válido.")
    if "web" in data:
        raise ValueError('Essa credencial é do tipo "Aplicativo da Web" e o login falha com ela. No Google Cloud, crie '
                         'uma do tipo "App para computador" (Desktop app) e envie o JSON dela.')
    if "installed" not in data:
        raise ValueError('Esse JSON não é uma credencial OAuth do Google (falta o bloco "installed").')
    old = json.loads(CREDENTIALS.read_text(encoding="utf-8")) if CREDENTIALS.exists() else {}
    DIR.mkdir(parents=True, exist_ok=True)
    CREDENTIALS.write_text(json.dumps(data, indent=2), encoding="utf-8")
    if old.get("installed", {}).get("client_id") != data["installed"].get("client_id"):
        TOKEN.unlink(missing_ok=True)  # a token from another client would fail
    return status()


def _credentials(login=True):
    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES) if TOKEN.exists() else None
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            TOKEN.write_text(creds.to_json(), encoding="utf-8")
            return creds
        except Exception:  # noqa: BLE001 - revoked or expired refresh token: log in again
            creds = None
    if not login:
        raise RuntimeError("O Google não está conectado. Abra ⚙️ Canal e Google Drive e clique em Salvar e conectar.")
    if not CREDENTIALS.exists():
        raise RuntimeError("Envie primeiro o credentials.json em ⚙️ Canal e Google Drive.")
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS), SCOPES)
    creds = flow.run_local_server(port=0, open_browser=True, timeout_seconds=300,
                                  success_message="Pronto! O Video Creator foi conectado. Pode fechar esta aba.")
    TOKEN.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _services(login=False):
    creds = _credentials(login)
    return (build("drive", "v3", credentials=creds, cache_discovery=False),
            build("sheets", "v4", credentials=creds, cache_discovery=False))


def _sheet_ok(sheets, sheet_id):
    try:
        sheets.spreadsheets().get(spreadsheetId=sheet_id, fields="spreadsheetId").execute()
        return True
    except HttpError:
        return False


def connect(channel_id, folder_link):
    """Log in (first time), check the channel's folder by creating the metadata sheet inside it, and save it all."""
    folder_id = extract_id(folder_link)
    if not folder_id:
        raise ValueError("Não reconheci esse link de pasta: \"" + (folder_link or "").strip()[:120] + "\". "
                         "Abra a pasta no Drive e copie o endereço da barra do navegador "
                         "(https://drive.google.com/drive/folders/...).")
    cfg = canais.get(channel_id)
    drive, sheets = _services(login=True)
    if cfg.get("pasta_id") == folder_id and cfg.get("planilha_id") and _sheet_ok(sheets, cfg["planilha_id"]):
        return canais.update(channel_id, pasta_link=folder_link.strip())  # same folder, sheet still there
    try:
        sheet = drive.files().create(body={"name": SHEET_NAME, "mimeType": SHEET_MIME, "parents": [folder_id]},
                                     fields="id,webViewLink", supportsAllDrives=True).execute()
    except HttpError as e:
        if e.resp.status == 404:
            raise ValueError("Não encontrei essa pasta no Drive da conta conectada. Confira o link e se a conta "
                             "que fez o login tem acesso a ela.")
        raise
    sid = sheet["id"]
    sheets.spreadsheets().values().update(spreadsheetId=sid, range="A1:F1", valueInputOption="RAW",
                                          body={"values": [HEADER]}).execute()
    first = sheets.spreadsheets().get(spreadsheetId=sid, fields="sheets.properties.sheetId").execute()
    tab = first["sheets"][0]["properties"]["sheetId"]
    sheets.spreadsheets().batchUpdate(spreadsheetId=sid, body={"requests": [
        {"updateSheetProperties": {"properties": {"sheetId": tab, "gridProperties": {"frozenRowCount": 1}},
                                   "fields": "gridProperties.frozenRowCount"}},
        {"repeatCell": {"range": {"sheetId": tab, "startRowIndex": 0, "endRowIndex": 1},
                        "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                        "fields": "userEnteredFormat.textFormat.bold"}}]}).execute()
    return canais.update(channel_id, pasta_id=folder_id, pasta_link=folder_link.strip(), planilha_id=sid,
                         planilha_link=sheet.get("webViewLink") or f"https://docs.google.com/spreadsheets/d/{sid}")


def disconnect():
    TOKEN.unlink(missing_ok=True)
    return status()


TYPE = {"T02": "Entrevista", "F01": "Personagem falando", "A01": "Só animação"}


def _upload_one(drive, sheets, cfg, batch_id, v):
    meta = v.get("metadados") or {}
    title = meta.get("titulo") or v.get("titulo") or Path(v["saida"]).stem
    desc, tags = meta.get("descricao", ""), meta.get("hashtags", "")
    path = Path(v["saida"])
    tagged = metadados.tag_mp4(path, title, desc, tags)  # title/description/hashtags inside the file too
    req = drive.files().create(body={"name": path.name, "parents": [cfg["pasta_id"]]}, fields="id,webViewLink",
                               supportsAllDrives=True,
                               media_body=MediaFileUpload(str(tagged), mimetype="video/mp4", resumable=True,
                                                          chunksize=16 * 1024 * 1024))
    done = None
    while done is None:
        prog, done = req.next_chunk()
        if prog:
            jobs._update(batch_id, v["id"], drive_etapa=f"Enviando {int(prog.progress() * 100)}%")
    row = [path.name, desc, title, tags, TYPE.get(v["template"], v.get("template_nome", "")), done["id"]]
    res = sheets.spreadsheets().values().append(spreadsheetId=cfg["planilha_id"], range="A:F",
                                                valueInputOption="RAW", insertDataOption="INSERT_ROWS",
                                                body={"values": [row]}).execute()
    rows = res.get("updates", {}).get("updatedRows", 0)
    if tagged != path:  # the video was open in a player: try once more to keep the tagged copy, else drop it
        try:
            tagged.replace(path)
        except PermissionError:
            tagged.unlink(missing_ok=True)
    jobs._update(batch_id, v["id"], drive_etapa=None, drive_erro=None,
                 drive={"video_id": done["id"], "link": done.get("webViewLink"), "planilha": bool(rows),
                        "pasta_id": cfg["pasta_id"], "enviado_em": time.strftime("%d/%m/%Y %H:%M")})


def pending(batch_id, again=False, only=None):
    """Ready videos whose file still exists; unless again, only the ones never sent. only: just that video id."""
    return [v for v in jobs.load(batch_id)["videos"] if v["status"] == "pronto" and not v.get("apagado")
            and (only is None or v["id"] == only)
            and (again or not (v.get("drive") or {}).get("video_id")) and v.get("saida") and Path(v["saida"]).exists()]


def send_batch(batch_id, again=False, only=None):
    """Start uploading the batch's videos to its channel's folder (in the background; the cards show the progress).
    again: send also the ones already sent (e.g. they went to a wrong folder)."""
    channel = canais.get(canais.of_batch(jobs.load(batch_id)))
    if not channel.get("pasta_id") or not channel.get("planilha_id"):
        raise ValueError(f'Configure antes a pasta do Drive do canal "{channel["nome"]}" em ⚙️ Canal e Google Drive.')
    _services(login=False)  # fail now (not in the thread) when the login is missing
    todo = pending(batch_id, again, only)
    if not todo and only:
        raise ValueError("Esse vídeo já foi enviado para o Drive (ou o arquivo dele foi apagado).")
    if not todo:
        raise ValueError("Não há vídeos para enviar neste lote (todos já foram enviados ou apagados).")
    with _send_lock:
        if batch_id in _sending:
            raise ValueError("Esse lote já está sendo enviado.")
        _sending.add(batch_id)
    for v in todo:
        jobs._update(batch_id, v["id"], drive_etapa="Aguardando envio", drive_erro=None)
    threading.Thread(target=_send, args=(batch_id, [v["id"] for v in todo], channel, again), daemon=True).start()
    return len(todo)


def clear_stale():
    """At start-up: an upload cut by closing the app shows as not sent (it can be sent again)."""
    for b in jobs.batches():
        for v in b["videos"]:
            if v.get("drive_etapa"):
                jobs._update(b["id"], v["id"], drive_etapa=None)


def _send(batch_id, ids, cfg, again):
    try:
        try:
            drive, sheets = _services(login=False)
        except Exception as e:  # noqa: BLE001
            for vid in ids:
                jobs._update(batch_id, vid, drive_etapa=None, drive_erro=f"Falha no envio: {e}")
            return
        for vid in ids:
            v = jobs.get_video(batch_id, vid)
            if not again and (v.get("drive") or {}).get("video_id"):  # never twice by accident
                continue
            try:
                jobs._update(batch_id, vid, drive_etapa="Enviando 0%")
                _upload_one(drive, sheets, cfg, batch_id, v)
            except Exception as e:  # noqa: BLE001 - one failure does not stop the others
                jobs._update(batch_id, vid, drive_etapa=None, drive_erro=f"Falha no envio: {e}")
    finally:
        with _send_lock:
            _sending.discard(batch_id)
