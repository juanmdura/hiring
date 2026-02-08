#!/usr/bin/env python3
"""
Candidates calibrator: score candidates with score=-1 using Gemini,
based on interview transcript and scorecard criteria.
"""
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

# Project root = parent of src/; load config first
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
load_dotenv(CONFIG_DIR / ".env")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

from content_loader import (
    TRANSCRIPTS_DIR,
    SCORECARDS_DIR,
    extract_google_doc_id,
    get_transcript_content,
    get_scorecard_content,
)
from scorer import normalize_position_to_scorecard_name, score_with_gemini

CANDIDATES_PATH = CONFIG_DIR / "candidates.json"
SCORECARDS_PATH = CONFIG_DIR / "interviews-scorecards.json"


def load_candidates() -> list[dict]:
    with open(CANDIDATES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("candidates", [])


def load_scorecards() -> list[dict]:
    with open(SCORECARDS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("interviews-scorecards", [])


def find_scorecard_by_position(scorecards: list[dict], position: str) -> dict | None:
    name = normalize_position_to_scorecard_name(position)
    for sc in scorecards:
        if (sc.get("name") or "").lower() == name.lower():
            return sc
    return None


def main() -> int:
    # Ensure local fallback dirs exist
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    SCORECARDS_DIR.mkdir(parents=True, exist_ok=True)

    candidates = load_candidates()
    scorecards_list = load_scorecards()

    to_score = [c for c in candidates if c.get("score") == -1]
    if not to_score:
        print("No candidates with score=-1 to calibrate.")
        return 0

    print(f"Calibrating {len(to_score)} candidate(s) with score=-1.\n")

    for c in to_score:
        name = c.get("name", "?")
        position = c.get("position", "")
        transcript_url = c.get("transcript", "")

        print(f"  {name} ({position})")

        scorecard = find_scorecard_by_position(scorecards_list, position)
        if not scorecard:
            print(f"    Skip: no scorecard for position '{position}'")
            continue

        transcript_text = get_transcript_content(
            transcript_url, candidate_email=c.get("email")
        )
        if not transcript_text:
            doc_id = extract_google_doc_id(transcript_url) or "doc_id"
            print(f"    Skip: could not load transcript. Add: data/transcripts/{doc_id}.txt")
            continue

        scorecard_text = get_scorecard_content(
            scorecard.get("location", ""), scorecard.get("name", "")
        )
        if not scorecard_text:
            print(f"    Skip: could not load scorecard '{scorecard.get('name')}' (add data/scorecards/<name>.txt if needed)")
            continue

        try:
            result = score_with_gemini(
                transcript_text,
                scorecard_text,
                candidate_name=name,
                position=position,
            )
            c["score"] = result["score"]
            if result.get("reasoning"):
                c["score_reasoning"] = result["reasoning"]
            print(f"    Score: {result['score']}")
            if result.get("reasoning"):
                print(f"    Reasoning: {result['reasoning'][:200]}...")
        except Exception as e:
            print(f"    Error: {e}")
            continue

    # Write back to config
    with open(CANDIDATES_PATH, "w", encoding="utf-8") as f:
        json.dump({"candidates": candidates}, f, indent=2, ensure_ascii=False)

    print("\nDone. Updated config/candidates.json with new scores.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
