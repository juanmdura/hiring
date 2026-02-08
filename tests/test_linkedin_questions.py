"""
Tests for the LinkedIn interview-questions flow.

- test_linkedin_generate_questions: uses Gemini to generate questions from sample profile text;
  requires GEMINI_API_KEY in config/.env.
- test_linkedin_tool_e2e: runs generate_linkedin_interview_questions (saves file, optionally uploads to Drive);
  requires GEMINI_API_KEY and optionally Google OAuth for Drive.

Run from project root:
  pytest tests/test_linkedin_questions.py -v
  pytest tests/test_linkedin_questions.py -v -s --log-cli-level=INFO
"""
import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
for _path in (ROOT / "config" / ".env", Path.cwd() / "config" / ".env"):
    if _path.exists():
        load_dotenv(_path, override=True)
        break

CANDIDATES_JSON = ROOT / "config" / "candidates.json"
DRIVE_REPORTS_JSON = ROOT / "config" / "drive_reports.json"

# Sample LinkedIn profile text (no real person)
SAMPLE_PROFILE_TEXT = """
About
Backend engineer with 5+ years building scalable APIs. Passionate about clean code and system design.
Previously at a fintech startup. Led migration to event-driven architecture.

Experience
Senior Backend Engineer | TechCorp | 2021 – Present
- Designed and implemented microservices handling 10M+ requests/day
- Introduced Kafka for async processing; reduced latency by 40%
- Mentored 3 junior developers

Software Engineer | StartupXYZ | 2019 – 2021
- Built REST and GraphQL APIs in Python and Node.js
- Improved test coverage from 60% to 90%

Education
BS Computer Science, University of Example (2019)

Skills
Python, Go, PostgreSQL, Redis, Kafka, AWS, Docker, Kubernetes
"""


@pytest.fixture(scope="module")
def candidate_email():
    """Use a candidate from config if present, else a placeholder."""
    if CANDIDATES_JSON.exists():
        try:
            data = json.loads(CANDIDATES_JSON.read_text(encoding="utf-8"))
            cand = next(iter(data.get("candidates", [])), None)
            if cand and (cand.get("email") or "").strip():
                return (cand.get("email") or "").strip()
        except Exception:
            pass
    return "test.linkedin@example.com"


def test_linkedin_generate_questions(candidate_email):
    """Generate questions from sample profile text using Gemini (requires GEMINI_API_KEY)."""
    assert os.environ.get("GEMINI_API_KEY"), "GEMINI_API_KEY must be set in config/.env"
    from linkedin_questions import generate_questions_from_profile

    result = generate_questions_from_profile(
        profile_text=SAMPLE_PROFILE_TEXT,
        candidate_name="Test Candidate",
        position="BACKEND ENGINEER",
    )
    assert result and len(result.strip()) > 50
    # Should contain numbered questions or list-like content
    assert any(c in result for c in ["1.", "2.", "?", "Question", "interview"])


def test_linkedin_tool_e2e(candidate_email):
    """
    Run the full generate_linkedin_interview_questions tool: local file + optional Drive upload.
    Requires GEMINI_API_KEY. Drive upload is attempted if OAuth/service account is configured.
    """
    assert os.environ.get("GEMINI_API_KEY"), "GEMINI_API_KEY must be set in config/.env"
    # Import agent tool (adds src and calibrator_agent context)
    sys.path.insert(0, str(ROOT / "calibrator_agent"))
    from agent import generate_linkedin_interview_questions

    out = generate_linkedin_interview_questions(
        candidate_email=candidate_email,
        profile_text=SAMPLE_PROFILE_TEXT,
        profile_url="https://www.linkedin.com/in/test/",
    )
    assert "[Error" not in out and "[No profile" not in out and "[Provide" not in out
    assert "saved to" in out or "Questions saved" in out

    # Check local file exists
    safe_email = re.sub(r"[^\w.-]", "_", candidate_email.strip().lower())
    expected_name = f"{safe_email}_linkedin_questions.md"
    for base in (ROOT, Path.cwd()):
        for _ in range(5):
            linkedin_dir = base / "data" / "linkedin_questions"
            if linkedin_dir.exists():
                path = linkedin_dir / expected_name
                if path.exists():
                    assert path.read_text(encoding="utf-8").strip()
                    return
            if (base / "config" / "candidates.json").exists():
                break
            base = base.parent
    pytest.fail(f"Expected local file data/linkedin_questions/{expected_name} not found")


def test_linkedin_tool_no_profile_returns_hint():
    """Calling the tool without profile_text returns an instruction to paste content."""
    sys.path.insert(0, str(ROOT / "calibrator_agent"))
    from agent import generate_linkedin_interview_questions

    out = generate_linkedin_interview_questions(
        candidate_email="brunomembrado10@gmail.com",
        profile_text="",
        profile_url="",
    )
    assert "[No profile" in out or "paste" in out.lower()
