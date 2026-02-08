#!/usr/bin/env python3
"""
One-time OAuth login to get a refresh token for Google Docs API (online mode).
Run from project root: python run/oauth_login.py
Then add the printed GOOGLE_REFRESH_TOKEN to config/.env
"""
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root / "src"))

from dotenv import load_dotenv
load_dotenv(_root / "config" / ".env")

import os

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
    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost:8080/"],
            }
        },
        scopes=SCOPES,
    )
    print("Opening browser for Google sign-in (use the account that has access to your Docs)...")
    creds = flow.run_local_server(port=8080)
    if not creds or not getattr(creds, "refresh_token", None):
        print("No refresh_token in response. Ensure you completed sign-in and that the OAuth consent screen allows offline access.")
        return 1
    print("\nAdd this line to config/.env:\n")
    print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}\n")
    return 0

if __name__ == "__main__":
    sys.exit(main())
