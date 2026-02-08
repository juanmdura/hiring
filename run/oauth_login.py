#!/usr/bin/env python3
"""
OAuth login for Google Docs/Drive (online mode).
Run from project root: python run/oauth_login.py
Saves GOOGLE_ACCESS_TOKEN, GOOGLE_TOKEN_EXPIRY and (when granted) GOOGLE_REFRESH_TOKEN to config/.env.
With a refresh token, the app can get new access tokens automatically; without it, re-run when the access token expires (~1 h).
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


def _update_env_file(access_token: str, expiry_iso: str, refresh_token: str | None = None) -> None:
    """Add or update GOOGLE_ACCESS_TOKEN, GOOGLE_TOKEN_EXPIRY and optionally GOOGLE_REFRESH_TOKEN in config/.env."""
    def set_or_add(text: str, key: str, value: str) -> str:
        if re.search(rf"^\s*{re.escape(key)}\s*=", text, re.M):
            return re.sub(rf"^(\s*{re.escape(key)}\s*=\s*).*$", lambda m: m.group(1) + value, text, count=1, flags=re.M)
        return text.rstrip() + f"\n{key}={value}\n"

    if not _env_path.exists():
        lines = [f"GOOGLE_ACCESS_TOKEN={access_token}", f"GOOGLE_TOKEN_EXPIRY={expiry_iso}"]
        if refresh_token:
            lines.append(f"GOOGLE_REFRESH_TOKEN={refresh_token}")
        _env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    text = _env_path.read_text(encoding="utf-8")
    text = set_or_add(text, "GOOGLE_ACCESS_TOKEN", access_token)
    text = set_or_add(text, "GOOGLE_TOKEN_EXPIRY", expiry_iso)
    if refresh_token:
        text = set_or_add(text, "GOOGLE_REFRESH_TOKEN", refresh_token)
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

    # Force consent screen so Google may return a refresh_token (then we don't need to re-run every hour)
    def _run_with_consent(flow, port: int):
        orig = flow.authorization_url
        def auth_url(*args, **kwargs):
            kwargs.setdefault("prompt", "consent")
            kwargs.setdefault("access_type", "offline")
            url, state = orig(*args, **kwargs)
            # Debug: verify URL contains params that trigger refresh_token
            if "prompt=consent" in url:
                print("[DEBUG] Auth URL contains prompt=consent (good for refresh_token)")
            else:
                print("[DEBUG] WARNING: Auth URL has no prompt=consent:", url.split("?")[0] + "?...")
            if "access_type=offline" in url:
                print("[DEBUG] Auth URL contains access_type=offline (required for refresh_token)")
            else:
                print("[DEBUG] WARNING: Auth URL has no access_type=offline")
            return url, state
        flow.authorization_url = auth_url
        return flow.run_local_server(port=port)

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
            creds = _run_with_consent(flow, port)
            break
        except OSError as e:
            if port == 80 and ("Permission denied" in str(e) or "Errno 13" in str(e)):
                print("Port 80 requires admin. Run: sudo python3 run/oauth_login.py\n")
                continue
            raise
    if not creds or not getattr(creds, "token", None):
        print("No access token in response. Complete sign-in in the browser.")
        return 1

    # Debug: verify what Google returned (to see if refresh_token is present)
    print("\n[DEBUG] Credentials after callback:")
    print("  type(creds):", type(creds).__name__)
    rt = getattr(creds, "refresh_token", None)
    print("  has refresh_token:", rt is not None)
    if rt:
        rt_str = (rt if isinstance(rt, str) else str(rt)).strip()
        print("  refresh_token length:", len(rt_str))
        print("  refresh_token starts with:", (rt_str[:30] + "..." if len(rt_str) > 30 else rt_str))
    else:
        # Some versions store it elsewhere
        for attr in ("_refresh_token", "refresh_token", "token_response"):
            if hasattr(creds, attr):
                val = getattr(creds, attr)
                if val and attr == "token_response" and isinstance(val, dict):
                    print("  token_response keys:", list(val.keys()))
                    if "refresh_token" in val:
                        print("  token_response['refresh_token'] present:", bool(val.get("refresh_token")))
                elif val and attr != "token_response":
                    print(f"  {attr}: present (len {len(str(val))})")

    expiry_iso = creds.expiry.isoformat() if getattr(creds, "expiry", None) else ""
    refresh_token = (getattr(creds, "refresh_token", None) or "").strip() or None
    _update_env_file(creds.token, expiry_iso, refresh_token=refresh_token if refresh_token else None)
    print("\nTokens saved to config/.env.")
    if refresh_token:
        print("GOOGLE_REFRESH_TOKEN was saved; the app will refresh the access token automatically.")
    else:
        print("No refresh token this time (valid ~1 h). To get one: revoke app access at https://myaccount.google.com/permissions and run this script again.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
