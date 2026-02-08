"""
Load transcript and scorecard content from Google Doc URLs, Drive folder, or local files.
"""
import logging
import os
import re
import requests
from pathlib import Path

log = logging.getLogger(__name__)

# Project root is parent of src/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
SCORECARDS_DIR = DATA_DIR / "scorecards"

# Google Docs export URL (may require doc to be "anyone with link can view")
EXPORT_FORMAT = "txt"
USER_AGENT = "CandidatesCalibrator/1.0"


def extract_google_doc_id(url: str) -> str | None:
    """Extract document ID from a Google Docs URL."""
    if not url:
        return None
    m = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    return m.group(1) if m else None


def fetch_google_doc_text(doc_id: str) -> tuple[str | None, str]:
    """
    Try to fetch document body as plain text via the export link.
    Returns (text, source_label) or (None, "") if the doc is private or the request fails.
    """
    url = f"https://docs.google.com/document/d/{doc_id}/export?format={EXPORT_FORMAT}"
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        text = r.text.strip()
        # If we got an HTML login page, treat as no access
        if text.lower().startswith("<!DOCTYPE") or "<html" in text.lower()[:200]:
            return None, ""
        return (text if text else None), f"Google Doc export (id={doc_id})"
    except Exception:
        return None, ""


def load_local_text(path: Path) -> str | None:
    """Load text from a local .txt file. Returns None if file missing or unreadable."""
    try:
        if path.exists():
            return path.read_text(encoding="utf-8").strip() or None
    except Exception:
        pass
    return None


def load_local_docx(path: Path) -> str | None:
    """Load text from a local .docx file. Uses docx2txt (better for some exports), then python-docx."""
    if not path.exists():
        return None
    try:
        import docx2txt
        text = docx2txt.process(str(path))
        if text and text.strip():
            return text.strip()
    except Exception:
        pass
    try:
        from docx import Document
        doc = Document(path)
        parts = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        parts.append(cell.text)
        return "\n".join(parts).strip() or None
    except Exception:
        return None


def _load_local_file(base_path: Path, base_name: str) -> str | None:
    """Try base_name.txt then base_name.docx; return first found content."""
    for ext in (".txt", ".docx"):
        p = base_path / f"{base_name}{ext}"
        text = load_local_text(p) if ext == ".txt" else load_local_docx(p)
        if text:
            return text
    return None


def get_transcript_content(transcript_url: str, candidate_email: str | None = None) -> str | None:
    """
    Get transcript text: try Google Doc export, Docs API, Drive folder (by email), then local files.
    Local: data/transcripts/{doc_id}.txt or .docx, or any file whose name contains candidate_email.
    """
    doc_id = extract_google_doc_id(transcript_url) if transcript_url else None
    if doc_id:
        text, source = fetch_google_doc_text(doc_id)
        if text:
            log.info("Transcript data source: %s", source)
            return text
        try:
            from docs_client import get_document_text
            text = get_document_text(doc_id)
            if text:
                log.info("Transcript data source: Google Docs API")
                return text
        except Exception:
            pass
    # Drive folder: subcarpeta "transcripts" (o raíz) y doc cuyo nombre contenga el email
    folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "").strip()
    if folder_id and candidate_email:
        try:
            from docs_client import get_doc_id_from_folder_by_name, get_document_text, get_subfolder_id
            search_folder_id = get_subfolder_id(folder_id, "transcripts") or folder_id
            drive_doc_id = get_doc_id_from_folder_by_name(search_folder_id, candidate_email)
            if drive_doc_id:
                text = get_document_text(drive_doc_id)
                if text:
                    log.info("Transcript data source: Google Drive folder (transcripts)")
                    return text
        except Exception:
            pass
    # Local: exact doc_id.txt / doc_id.docx (solo si tenemos doc_id)
    if doc_id:
        local_text = _load_local_file(TRANSCRIPTS_DIR, doc_id)
        if local_text:
            log.info("Transcript data source: local file %s (doc_id)", doc_id)
            return local_text
    # Fallback: any file whose name contains the candidate email (e.g. "transcript - email.docx")
    if candidate_email and TRANSCRIPTS_DIR.exists():
        needle = candidate_email.lower().replace(" ", "")
        for f in TRANSCRIPTS_DIR.iterdir():
            if f.suffix.lower() not in (".txt", ".docx") or not f.is_file():
                continue
            if needle in f.stem.lower().replace(" ", ""):
                text = load_local_text(f) if f.suffix.lower() == ".txt" else load_local_docx(f)
                if text:
                    log.info("Transcript data source: local file %s", f.name)
                    return text
    return None


def get_scorecard_content(scorecard_location_url: str, scorecard_name: str) -> str | None:
    """
    Get scorecard text: try Google Doc export, then local data/scorecards/{name}.txt.
    """
    doc_id = extract_google_doc_id(scorecard_location_url)
    if doc_id:
        text, source = fetch_google_doc_text(doc_id)
        if text:
            log.info("Scorecard data source: %s", source)
            return text
        try:
            from docs_client import get_document_text
            text = get_document_text(doc_id)
            if text:
                log.info("Scorecard data source: Google Docs API")
                return text
        except Exception:
            pass
    # Drive folder: subcarpeta "scorecards-templates" (o raíz) y doc por rol o "scorecard"
    folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "").strip()
    if folder_id:
        try:
            from docs_client import get_doc_id_from_folder_by_name, get_document_text, get_subfolder_id
            search_folder_id = get_subfolder_id(folder_id, "scorecards-templates") or folder_id
            role_word = scorecard_name.split("-")[0] if "-" in scorecard_name else scorecard_name
            drive_doc_id = get_doc_id_from_folder_by_name(search_folder_id, role_word)
            if not drive_doc_id:
                drive_doc_id = get_doc_id_from_folder_by_name(search_folder_id, "scorecard")
            if drive_doc_id:
                text = get_document_text(drive_doc_id)
                if text:
                    log.info("Scorecard data source: Google Drive folder (scorecards-templates)")
                    return text
        except Exception:
            pass
    # Fallback: local file by scorecard name (e.g. backend-engineer.txt or .docx)
    safe_name = re.sub(r"[^\w-]", "_", scorecard_name)
    local_text = _load_local_file(SCORECARDS_DIR, safe_name)
    if local_text:
        log.info("Scorecard data source: local file %s", safe_name)
        return local_text
    # Fallback: any file whose name contains the role (e.g. "Backend – Interview Scorecard.docx")
    if SCORECARDS_DIR.exists():
        role_word = scorecard_name.split("-")[0].lower() if "-" in scorecard_name else scorecard_name.lower()
        for f in SCORECARDS_DIR.iterdir():
            if f.suffix.lower() not in (".txt", ".docx") or not f.is_file():
                continue
            if role_word in f.stem.lower():
                text = load_local_text(f) if f.suffix.lower() == ".txt" else load_local_docx(f)
                if text:
                    log.info("Scorecard data source: local file %s", f.name)
                    return text
    return None


def get_transcript_offline(candidate_email: str) -> str | None:
    """
    Load transcript from local files only (data/transcripts/).
    Tries exact name {email}.txt/.docx first, then any file whose name contains the email.
    Returns None if not found. If file found but content empty, returns a short help message.
    """
    if not candidate_email or not TRANSCRIPTS_DIR.exists():
        return None
    email_clean = candidate_email.strip().lower().replace(" ", "")
    # 1) Exact filename: email.docx / email.txt (some filesystems are strict)
    for ext in (".docx", ".txt"):
        f = TRANSCRIPTS_DIR / f"{candidate_email.strip()}{ext}"
        if f.is_file():
            text = load_local_docx(f) if ext == ".docx" else load_local_text(f)
            if text:
                return text
            return "[File found but content is empty or could not be read. Save the transcript as plain .txt (e.g. brunomembrado10@gmail.com.txt) and try again.]"
    # 2) Any file whose name contains the email
    needle = email_clean
    for f in TRANSCRIPTS_DIR.iterdir():
        if f.suffix.lower() not in (".txt", ".docx") or not f.is_file():
            continue
        if needle in f.stem.lower().replace(" ", ""):
            text = load_local_text(f) if f.suffix.lower() == ".txt" else load_local_docx(f)
            if text:
                return text
            return "[File found but content is empty or could not be read. Save the transcript as plain .txt (name containing the email) and try again.]"
    return None


def get_scorecard_offline(scorecard_name: str) -> str | None:
    """
    Load scorecard from local files only (data/scorecards/).
    Tries exact name (e.g. backend-engineer.txt/.docx) then any file whose name contains the role.
    Returns None if not found or empty.
    """
    if not scorecard_name or not SCORECARDS_DIR.exists():
        return None
    safe_name = re.sub(r"[^\w-]", "_", scorecard_name)
    text = _load_local_file(SCORECARDS_DIR, safe_name)
    if text:
        return text
    role_word = scorecard_name.split("-")[0].lower() if "-" in scorecard_name else scorecard_name.lower()
    for f in SCORECARDS_DIR.iterdir():
        if f.suffix.lower() not in (".txt", ".docx") or not f.is_file():
            continue
        if role_word in f.stem.lower():
            text = load_local_text(f) if f.suffix.lower() == ".txt" else load_local_docx(f)
            if text:
                return text
    return None
