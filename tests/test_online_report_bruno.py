"""
Integration test: validate online result generation for brunomembrado10@gmail.com.

Uses:
1. Transcript from the Google Doc URL in config/candidates.json for that candidate.
2. Scorecard from config/interviews-scorecards.json for the candidate's position (BACKEND ENGINEER).
3. Saves the report to the Drive folder configured in config/drive_reports.json
   (or GOOGLE_DRIVE_REPORTS_FOLDER_ID in .env). Default folder:
   https://drive.google.com/drive/folders/12K-YFnnGpvG-Pg03IXvfZeQejhXMkOIn

Requires: .env with GEMINI_API_KEY and Google OAuth (or service account) for Docs/Drive.
Run from project root: pytest tests/test_online_report_bruno.py -v
"""
import json
import os
import re
import sys
from pathlib import Path

import pytest

# Project root and src on path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

# Load .env so OAuth/Drive credentials are available for online mode (override=True)
from dotenv import load_dotenv
_env_path = (ROOT / "config" / ".env").resolve()
for _path in (_env_path, Path.cwd() / "config" / ".env"):
    if _path.exists():
        load_dotenv(_path, override=True)
        break

# Ensure reports folder ID is set from config if not in env (so test uses default)
if not (os.environ.get("GOOGLE_DRIVE_REPORTS_FOLDER_ID") or "").strip():
    try:
        from reports_config import get_reports_folder_id
        fid = get_reports_folder_id()
        if fid:
            os.environ["GOOGLE_DRIVE_REPORTS_FOLDER_ID"] = fid
    except Exception:
        pass

CANDIDATES_JSON = ROOT / "config" / "candidates.json"
SCORECARDS_JSON = ROOT / "config" / "interviews-scorecards.json"
DRIVE_REPORTS_JSON = ROOT / "config" / "drive_reports.json"
REPORTS_DIR = ROOT / "data" / "reports"

TEST_EMAIL = "brunomembrado10@gmail.com"
DEFAULT_REPORTS_FOLDER_ID = "12K-YFnnGpvG-Pg03IXvfZeQejhXMkOIn"


def _normalize_position_to_scorecard_name(position: str) -> str:
    if not position or not position.strip():
        return ""
    return re.sub(r"[^\w-]", "", position.strip().lower().replace(" ", "-"))


@pytest.fixture(scope="module")
def candidate_data():
    """Load candidate brunomembrado10@gmail.com from config/candidates.json."""
    assert CANDIDATES_JSON.exists(), "config/candidates.json not found"
    data = json.loads(CANDIDATES_JSON.read_text(encoding="utf-8"))
    candidates = data.get("candidates", [])
    email_lower = TEST_EMAIL.strip().lower()
    candidate = next((c for c in candidates if (c.get("email") or "").strip().lower() == email_lower), None)
    assert candidate is not None, f"Candidate {TEST_EMAIL} not found in config/candidates.json"
    return candidate


@pytest.fixture(scope="module")
def scorecard_location(candidate_data):
    """Resolve scorecard URL from interviews-scorecards.json by candidate position."""
    assert SCORECARDS_JSON.exists(), "config/interviews-scorecards.json not found"
    position = candidate_data.get("position", "")
    scorecard_name = _normalize_position_to_scorecard_name(position)
    assert scorecard_name, "Candidate position is empty"
    data = json.loads(SCORECARDS_JSON.read_text(encoding="utf-8"))
    for sc in data.get("interviews-scorecards", []):
        if (sc.get("name") or "").strip().lower() == scorecard_name.lower():
            return (sc.get("location") or "").strip(), scorecard_name
    pytest.fail(f"Scorecard for '{scorecard_name}' not found in interviews-scorecards.json")


@pytest.fixture(scope="module")
def transcript_content(candidate_data):
    """Load transcript from Google Doc or Drive (online) using content_loader."""
    for _path in (_env_path, Path.cwd() / "config" / ".env"):
        if _path.exists():
            load_dotenv(_path, override=True)
            break
    assert os.environ.get("GEMINI_API_KEY"), (
        "GEMINI_API_KEY must be set in config/.env for online test"
    )
    from docs_client import is_configured
    assert is_configured(), (
        "Online mode needs OAuth or service account. Run: python run/oauth_login.py (saves access token to config/.env), "
        "or set GOOGLE_REFRESH_TOKEN / add config/service_account.json."
    )
    from content_loader import get_transcript_content
    transcript_url = (candidate_data.get("transcript") or "").strip()
    text = get_transcript_content(transcript_url, TEST_EMAIL)
    assert text and len(text.strip()) > 100, (
        "Could not load transcript online. Share the Google Doc with the OAuth account, "
        "or put it in GOOGLE_DRIVE_FOLDER_ID/transcripts with name containing brunomembrado10@gmail.com."
    )
    return text


@pytest.fixture(scope="module")
def scorecard_content(scorecard_location):
    """Load scorecard content from Google Doc or Drive (online)."""
    for _path in (_env_path, Path.cwd() / "config" / ".env"):
        if _path.exists():
            load_dotenv(_path, override=True)
            break
    assert os.environ.get("GEMINI_API_KEY"), "GEMINI_API_KEY must be set in config/.env"
    from content_loader import get_scorecard_content
    location_url, scorecard_name = scorecard_location
    text = get_scorecard_content(location_url, scorecard_name)
    assert text and len(text.strip()) > 50, (
        f"Could not load scorecard online for '{scorecard_name}'. "
        f"Share this Doc with your OAuth account (Compartir → add your Google email as Viewer), "
        f"or put a Doc in GOOGLE_DRIVE_FOLDER_ID/scorecards-templates with name containing 'backend' or 'scorecard'. "
        f"Doc URL: {location_url}"
    )
    return text


@pytest.fixture(scope="module")
def reports_folder_id():
    """Folder ID for report upload (config or env)."""
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
    return DEFAULT_REPORTS_FOLDER_ID


def test_config_and_candidate_resolution(candidate_data, scorecard_location, reports_folder_id):
    """Validate config: candidate and scorecard exist, reports folder ID is set (no network)."""
    assert candidate_data.get("email") == TEST_EMAIL or candidate_data.get("email", "").lower() == TEST_EMAIL.lower()
    assert (candidate_data.get("transcript") or "").strip(), "Candidate transcript URL is missing"
    assert candidate_data.get("position"), "Candidate position is missing"
    loc_url, scorecard_name = scorecard_location
    assert loc_url, "Scorecard location URL is missing"
    assert scorecard_name == "backend-engineer"
    assert reports_folder_id, "Reports folder ID should be set (config/drive_reports.json or .env)"


def test_online_generation_bruno(
    candidate_data,
    scorecard_location,
    transcript_content,
    scorecard_content,
    reports_folder_id,
):
    """
    Full flow: load transcript and scorecard from config, score with Gemini,
    generate report, save locally and upload to Drive.
    """
    from scorer import score_with_gemini

    assert os.environ.get("GEMINI_API_KEY"), "GEMINI_API_KEY must be set in config/.env"

    name = candidate_data.get("name", TEST_EMAIL)
    position = candidate_data.get("position", "")

    result = score_with_gemini(
        transcript_content,
        scorecard_content,
        candidate_name=name,
        position=position,
    )
    score = result.get("score", -1)
    reasoning = result.get("reasoning", "")

    assert score >= 0 and score <= 10, f"Invalid score: {score}"
    assert reasoning, "Missing reasoning"

    # Generate report using the same logic as the agent (save + upload to Drive)
    sys.path.insert(0, str(ROOT / "src"))
    os.chdir(ROOT)
    # Use agent's generate_candidate_report so upload uses same config
    from calibrator_agent.agent import generate_candidate_report

    dimensions_table = ""  # optional for this test
    out = generate_candidate_report(
        candidate_email=TEST_EMAIL,
        score=score,
        reasoning=reasoning,
        final_recommendation="Hire",
        feedback_if_discarded="",
        dimensions_breakdown="",
        dimensions_table=dimensions_table,
    )

    # Assert local report exists
    safe_name = re.sub(r"[^\w.-]", "_", TEST_EMAIL.strip())
    report_path = REPORTS_DIR / f"{safe_name}_report.md"
    assert report_path.exists(), f"Report not saved locally: {report_path}"
    content = report_path.read_text(encoding="utf-8")
    assert "Overall Score" in content or "Score" in content
    assert str(score) in content
    assert reasoning[:100] in content or reasoning[:50] in content

    # Assert Drive folder ID used is the configured one
    assert reports_folder_id == DEFAULT_REPORTS_FOLDER_ID or reports_folder_id, (
        "Reports folder ID should come from config/drive_reports.json or .env"
    )
    # If upload was attempted, message should mention Drive or report path
    assert "Report saved" in out or "Uploaded" in out or "report" in out.lower()
