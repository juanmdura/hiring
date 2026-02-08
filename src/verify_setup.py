#!/usr/bin/env python3
"""
Verify access to Gemini API and all data from the JSON config files.
Run from project root: python -m src.verify_setup  or  python run/verify_setup.py
"""
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv

# Project root = parent of src/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
load_dotenv(CONFIG_DIR / ".env")

CANDIDATES_PATH = CONFIG_DIR / "candidates.json"
SCORECARDS_PATH = CONFIG_DIR / "interviews-scorecards.json"


def extract_google_doc_id(url: str) -> str | None:
    """Extract document ID from a Google Docs URL."""
    if not url:
        return None
    m = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    return m.group(1) if m else None


def load_json(path: Path) -> dict:
    """Load and parse a JSON file."""
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    if not raw.strip():
        raise ValueError(f"File is empty: {path}")
    return json.loads(raw)


def verify_candidates() -> dict:
    """Load candidates.json and return parsed data."""
    data = load_json(CANDIDATES_PATH)
    candidates = data.get("candidates", [])
    print(f"  Loaded {len(candidates)} candidate(s) from config/candidates.json")
    for c in candidates:
        name = c.get("name", "?")
        score = c.get("score", "?")
        transcript = c.get("transcript", "")
        doc_id = extract_google_doc_id(transcript) if transcript else None
        print(f"    - {name} (score={score}, transcript_doc_id={doc_id or 'N/A'})")
    return data


def verify_scorecards() -> dict:
    """Load interviews-scorecards.json and return parsed data."""
    data = load_json(SCORECARDS_PATH)
    scorecards = data.get("interviews-scorecards", [])
    print(f"  Loaded {len(scorecards)} scorecard(s) from config/interviews-scorecards.json")
    for s in scorecards:
        name = s.get("name", "?")
        location = s.get("location", "")
        doc_id = extract_google_doc_id(location) if location else None
        print(f"    - {name}: doc_id={doc_id or 'N/A'}")
    return data


def verify_gemini() -> bool:
    """Test Gemini API with a minimal request."""
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    if not api_key:
        print("  ERROR: GEMINI_API_KEY not set in config/.env")
        return False

    print(f"  Using model: {model}")

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents="Reply with exactly: OK",
        )
        text = response.text.strip() if response.text else ""
        if "OK" in text or response.text:
            print("  Gemini API: OK (connection successful)")
            return True
        print("  Gemini API: Unexpected response:", repr(response.text))
        return False
    except Exception as e:
        print(f"  Gemini API: ERROR - {e}")
        return False


def main() -> None:
    print("Verifying setup for candidates calibrator\n")

    # 1. Config JSON files exist and are readable
    print("1. Config (config/)")
    if not CANDIDATES_PATH.exists():
        print(f"  ERROR: Missing {CANDIDATES_PATH}")
        return
    if not SCORECARDS_PATH.exists():
        print(f"  ERROR: Missing {SCORECARDS_PATH}")
        return
    verify_candidates()
    verify_scorecards()

    # 2. Gemini API
    print("\n2. Gemini API")
    gemini_ok = verify_gemini()

    # 3. Document URLs (informational)
    print("\n3. Document URLs (from config)")
    print("  Transcripts and scorecards point to Google Docs.")
    print("  To use their content you can: export docs as text and put in data/transcripts or data/scorecards,")
    print("  or use Google Drive API with OAuth for direct access.")

    print("\n" + ("All checks passed." if gemini_ok else "Fix errors above and re-run."))


if __name__ == "__main__":
    main()
