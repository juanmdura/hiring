"""
Score a candidate using Gemini: transcript + scorecard criteria -> numeric score.
"""
import os
import re
from pathlib import Path

# Load .env from config/ when running as part of the app (run_calibrator loads it first)
_config_env = Path(__file__).resolve().parent.parent / "config" / ".env"
if _config_env.exists():
    from dotenv import load_dotenv
    load_dotenv(_config_env)


def normalize_position_to_scorecard_name(position: str) -> str:
    """Map position like 'BACKEND ENGINEER' to scorecard name 'backend-engineer'."""
    if not position or not position.strip():
        return ""
    slug = position.strip().lower().replace(" ", "-")
    return re.sub(r"[^\w-]", "", slug)


def score_with_gemini(
    transcript_text: str,
    scorecard_text: str,
    candidate_name: str,
    position: str,
    *,
    model: str | None = None,
    api_key: str | None = None,
) -> dict:
    """
    Use Gemini to score the candidate based on transcript and scorecard.
    Returns {"score": int, "reasoning": str}.
    Score should be 0-10 or 1-5 depending on scorecard; we ask for a single integer.
    """
    from google import genai

    model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    api_key = api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set")

    client = genai.Client(api_key=api_key)

    prompt = f"""You are an expert interviewer. Score this candidate based on the interview transcript and the scorecard criteria below.

Candidate: {candidate_name}
Position: {position}

## Scorecard (criteria and rubric)
{scorecard_text}

## Interview transcript
{transcript_text}

---
Provide your evaluation in this exact format (no other text before or after):
SCORE: <integer from 0 to 10>
REASONING: <2-4 sentences explaining the score>

Use only the line "SCORE: N" and "REASONING: ..." as shown."""

    response = client.models.generate_content(
        model=model,
        contents=prompt,
    )
    text = (response.text or "").strip()

    score = None
    reasoning = ""

    # Parse SCORE: N
    score_m = re.search(r"SCORE:\s*(\d+)", text, re.I)
    if score_m:
        score = int(score_m.group(1))

    # Parse REASONING: ... (rest of block or single line)
    reasoning_m = re.search(r"REASONING:\s*(.+)", text, re.I | re.DOTALL)
    if reasoning_m:
        reasoning = reasoning_m.group(1).strip()

    if score is None:
        numbers = re.findall(r"\b([0-9]|10)\b", text)
        if numbers:
            score = int(numbers[-1])
        else:
            score = -1
    score = max(0, min(10, score))

    return {"score": score, "reasoning": reasoning or text[:500]}
