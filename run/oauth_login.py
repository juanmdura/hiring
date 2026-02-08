#!/usr/bin/env python3
"""
OAuth login for Google Docs/Drive (online mode). Uses access token only (no refresh token).
Run from project root: python run/oauth_login.py
Saves GOOGLE_ACCESS_TOKEN and GOOGLE_TOKEN_EXPIRY to config/.env. Token valid ~1 hour; run again when it expires.
"""
import os
import re
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root / "src"))

from dotenv import load_dotenv
_env_path = _root / "config" / ".env"
load_dotenv(_env_path)


def _update_env_file(access_token: str, expiry_iso: str) -> None:
    """Add or update GOOGLE_ACCESS_TOKEN and GOOGLE_TOKEN_EXPIRY in config/.env."""
    if not _env_path.exists():
        _env_path.write_text(
            f"GOOGLE_ACCESS_TOKEN={access_token}\n"
            f"GOOGLE_TOKEN_EXPIRY={expiry_iso}\n",
            encoding="utf-8",
        )
        return
    text = _env_path.read_text(encoding="utf-8")
    # Replace or add GOOGLE_ACCESS_TOKEN
    if re.search(r"^\s*GOOGLE_ACCESS_TOKEN\s*=", text, re.M):
        text = re.sub(r"^(\s*GOOGLE_ACCESS_TOKEN\s*=\s*).*$", lambda m: m.group(1) + access_token, text, count=1, flags=re.M)
    else:
        text = text.rstrip() + "\nGOOGLE_ACCESS_TOKEN=" + access_token + "\n"
    # Replace or add GOOGLE_TOKEN_EXPIRY
    if re.search(r"^\s*GOOGLE_TOKEN_EXPIRY\s*=", text, re.M):
        text = re.sub(r"^(\s*GOOGLE_TOKEN_EXPIRY\s*=\s*).*$", lambda m: m.group(1) + expiry_iso, text, count=1, flags=re.M)
    else:
        text = text.rstrip() + "\nGOOGLE_TOKEN_EXPIRY=" + expiry_iso + "\n"
    _env_path.write_text(text, encoding="utf-8")


# Puerto 80 → redirect http://localhost/ (suele venir ya en clientes tipo "Desktop").
# Si no tienes consola: probamos primero puerto 80; en Mac/Linux puede hacer falta: sudo python3 run/oauth_login.py
REDIRECT_URI_PORT80 = "http://localhost/"
REDIRECT_URI_PORT8080 = "http://localhost:8080/"


def main():
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        print("Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in config/.env")
        return 1

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("Install: pip install google-auth-oauthlib")
        return 1

    SCOPES = [
        "https://www.googleapis.com/auth/documents.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/drive.file",
    ]

    # Intentar primero puerto 80 (http://localhost/) — muchos clientes "Desktop" lo tienen ya autorizado
    creds = None
    for port, redirect_uri in [(80, REDIRECT_URI_PORT80), (8080, REDIRECT_URI_PORT8080)]:
        flow = InstalledAppFlow.from_client_config(
            {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri],
                }
            },
            scopes=SCOPES,
        )
        if port == 80:
            print("Trying port 80 (http://localhost/) — often allowed by default for Desktop OAuth clients...")
            print("If 'Permission denied', run: sudo python3 run/oauth_login.py\n")
        else:
            print("Trying port 8080. If you get redirect_uri_mismatch, add http://localhost:8080/ in Google Cloud Console when you have access.\n")
        print("Opening browser for Google sign-in (use the account that has access to your Docs)...")
        try:
            creds = flow.run_local_server(port=port)
            break
        except OSError as e:
            if port == 80 and ("Permission denied" in str(e) or "Errno 13" in str(e)):
                print("Port 80 requires admin. Run: sudo python3 run/oauth_login.py\n")
                continue
            raise
    if not creds or not getattr(creds, "token", None):
        print("No access token in response. Complete sign-in in the browser.")
        return 1
    expiry_iso = creds.expiry.isoformat() if getattr(creds, "expiry", None) else ""
    _update_env_file(creds.token, expiry_iso)
    print("\nAccess token saved to config/.env. Valid for ~1 hour.")
    print("When it expires, run this script again: python run/oauth_login.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
