"""
Google Docs API client: fetch document text using service account or OAuth.
- Service account: set GOOGLE_APPLICATION_CREDENTIALS to the path of the JSON; share docs with the service account email.
- OAuth: set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN in .env (get refresh token with run/oauth_login.py).
"""
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

# Project root = parent of src/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DEFAULT_CREDENTIALS_PATH = CONFIG_DIR / "service_account.json"

SCOPES = [
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.file",  # create/upload files (e.g. reports)
]
GOOGLE_DOCS_MIME = "application/vnd.google-apps.document"
GOOGLE_FOLDER_MIME = "application/vnd.google-apps.folder"


def _read_structural_elements(elements: list) -> str:
    """Extract text from Docs API structural elements (paragraphs, tables, TOC)."""
    if not elements:
        return ""
    text_parts = []
    for value in elements:
        if "paragraph" in value:
            for elem in value.get("paragraph", {}).get("elements", []):
                tr = elem.get("textRun", {})
                if tr:
                    text_parts.append(tr.get("content", ""))
        elif "table" in value:
            for row in value.get("table", {}).get("tableRows", []):
                for cell in row.get("tableCells", []):
                    text_parts.append(
                        _read_structural_elements(cell.get("content", []))
                    )
        elif "tableOfContents" in value:
            toc = value.get("tableOfContents", {})
            text_parts.append(_read_structural_elements(toc.get("content", [])))
    return "".join(text_parts)


def _get_creds():
    """Return credentials (service account or OAuth). Used by get_document_text and list_drive_folder."""
    creds = None
    path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or DEFAULT_CREDENTIALS_PATH
    path = Path(path) if path else DEFAULT_CREDENTIALS_PATH
    if path.exists():
        try:
            from google.oauth2.service_account import Credentials
            creds = Credentials.from_service_account_file(str(path), scopes=SCOPES)
        except Exception as e:
            log.debug("Service account load failed: %s", e)
    if creds is None:
        creds = _get_creds_oauth()
    return creds


def _get_creds_oauth():
    """Build credentials from OAuth client_id, client_secret, refresh_token in env."""
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    refresh_token = (os.getenv("GOOGLE_REFRESH_TOKEN") or "").strip()
    if not client_id or not client_secret or not refresh_token:
        return None
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES,
        )
        creds.refresh(Request())
        return creds
    except Exception as e:
        log.debug("OAuth credentials failed: %s", e)
        return None


def list_drive_folder(folder_id: str) -> list[dict]:
    """
    List files in a Google Drive folder. Returns list of {"id", "name", "mimeType"}.
    Uses same credentials as get_document_text (service account or OAuth).
    """
    creds = _get_creds()
    if creds is None:
        return []
    try:
        from googleapiclient.discovery import build
        drive = build("drive", "v3", credentials=creds)
        result = drive.files().list(
            q=f"'{folder_id}' in parents",
            fields="files(id, name, mimeType)",
            pageSize=100,
        ).execute()
        return result.get("files", [])
    except Exception as e:
        log.debug("Drive list failed: %s", e)
        return []


def get_subfolder_id(parent_folder_id: str, subfolder_name: str) -> str | None:
    """
    Find a subfolder inside parent_folder_id whose name equals subfolder_name (case-insensitive).
    Returns the folder id or None.
    """
    name_lower = (subfolder_name or "").strip().lower()
    if not name_lower:
        return None
    for f in list_drive_folder(parent_folder_id):
        if f.get("mimeType") != GOOGLE_FOLDER_MIME:
            continue
        if (f.get("name") or "").strip().lower() == name_lower:
            return f.get("id")
    return None


def get_doc_id_from_folder_by_name(folder_id: str, name_contains: str) -> str | None:
    """
    Find a Google Doc in the folder whose name contains name_contains (case-insensitive).
    Returns the document id or None.
    """
    name_lower = (name_contains or "").strip().lower()
    if not name_lower:
        return None
    for f in list_drive_folder(folder_id):
        if f.get("mimeType") != GOOGLE_DOCS_MIME:
            continue
        if name_lower in (f.get("name") or "").lower():
            return f.get("id")
    return None


def upload_file_to_drive(folder_id: str, filename: str, content: str, mime_type: str = "text/plain") -> str | None:
    """
    Upload a text file to a Google Drive folder. Returns the new file id or None on failure.
    Requires drive.file scope (OAuth: re-run oauth_login.py if you added this scope later).
    """
    creds = _get_creds()
    if creds is None:
        return None
    try:
        import io
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseUpload
        drive = build("drive", "v3", credentials=creds)
        file_metadata = {"name": filename, "parents": [folder_id]}
        media = MediaIoBaseUpload(
            io.BytesIO(content.encode("utf-8")),
            mimetype=mime_type,
            resumable=False,
        )
        created = drive.files().create(
            body=file_metadata,
            media_body=media,
            fields="id,webViewLink",
        ).execute()
        return created.get("id")
    except Exception as e:
        log.debug("Drive upload failed: %s", e)
        return None


def get_document_text(doc_id: str, credentials_path: str | Path | None = None) -> str | None:
    """
    Fetch a Google Doc's body text using the Docs API.
    Tries: 1) Service account JSON  2) OAuth (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN).
    Returns None if credentials are missing or the doc is inaccessible.
    """
    if credentials_path is not None:
        path = Path(credentials_path)
        if path.exists():
            try:
                from google.oauth2.service_account import Credentials
                creds = Credentials.from_service_account_file(str(path), scopes=SCOPES)
            except Exception:
                creds = None
        else:
            creds = None
    else:
        creds = _get_creds()
    if creds is None:
        return None
    try:
        from googleapiclient.discovery import build
        service = build("docs", "v1", credentials=creds)
        doc = service.documents().get(documentId=doc_id).execute()
    except Exception as e:
        log.debug("Docs API get_document_text failed: %s", e)
        return None
    body = doc.get("body")
    if not body:
        return None
    content = body.get("content", [])
    text = _read_structural_elements(content).strip()
    return text if text else None


def is_configured() -> bool:
    """Return True if service account or OAuth credentials are available."""
    if Path(os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or DEFAULT_CREDENTIALS_PATH).exists():
        return True
    if os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET") and os.getenv("GOOGLE_REFRESH_TOKEN"):
        return True
    return False


def get_service_account_email() -> str | None:
    """Return the service account email from the JSON, or None if using OAuth."""
    path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or DEFAULT_CREDENTIALS_PATH
    path = Path(path) if path else DEFAULT_CREDENTIALS_PATH
    if not path.exists():
        return None
    try:
        import json
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("client_email")
    except Exception:
        return None
