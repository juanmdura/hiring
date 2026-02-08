"""
Resolve the Google Drive folder ID for report uploads.
Uses GOOGLE_DRIVE_REPORTS_FOLDER_ID from env, then config/drive_reports.json.
"""
import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DRIVE_REPORTS_JSON = CONFIG_DIR / "drive_reports.json"


def get_reports_folder_id() -> str:
    """
    Return the Drive folder ID for report uploads.
    Priority: env GOOGLE_DRIVE_REPORTS_FOLDER_ID, then config/drive_reports.json.
    """
    env_id = (os.environ.get("GOOGLE_DRIVE_REPORTS_FOLDER_ID") or "").strip()
    if env_id:
        return env_id
    if DRIVE_REPORTS_JSON.exists():
        try:
            data = json.loads(DRIVE_REPORTS_JSON.read_text(encoding="utf-8"))
            fid = (data.get("reports_folder_id") or "").strip()
            if fid:
                return fid
        except Exception:
            pass
    return ""
