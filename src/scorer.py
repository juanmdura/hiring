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
    include_dimensions: bool = True,
) -> dict:
    """
    Use Gemini to score the candidate based on transcript and scorecard.
    The transcript may include interview content and Gemini notes; all of it is used for evaluation.
    Returns {"score": int, "reasoning": str, "dimensions_table": str}.
    dimensions_table: one line per dimension, "Dimension | Category | Score | Notes" (Category = Cultural, Skills, Technical).
    """
    from google import genai

    model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    api_key = api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set")

    client = genai.Client(api_key=api_key)

    prompt = f"""You are an expert interviewer. Score this candidate based on the **full** interview transcript and the scorecard criteria below.
The transcript may include the interview dialogue and any "notas de Gemini" or evaluator notes — use **all** of this content for your evaluation.

Candidate: {candidate_name}
Position: {position}

## Scorecard (criteria and rubric)
{scorecard_text}

## Interview transcript (use everything below, including any Gemini notes)
{transcript_text}

---
Provide your evaluation in this exact format (no other text before or after):

SCORE: <integer from 0 to 10>
REASONING: <2-4 sentences explaining the overall score>

DIMENSIONS:
<one line per dimension from the scorecard, each line: Dimension name | Category | Score | Brief notes>
Use Category = Cultural, Skills, or Technical. Score can be e.g. 4/5 or 8/10. Example lines:
Execution under Austerity | Cultural | 4/5 | Described constraints well
Adaptabilidad y Cambio | Cultural | 4/5 | Good examples
JavaScript | Technical | 3/5 | Basic level
"""
    if not include_dimensions:
        prompt = f"""You are an expert interviewer. Score this candidate based on the **full** interview transcript and the scorecard below.
The transcript may include interview dialogue and "notas de Gemini" — use **all** of it.

Candidate: {candidate_name}
Position: {position}

## Scorecard
{scorecard_text}

## Interview transcript
{transcript_text}

---
Reply with only:
SCORE: <integer 0 to 10>
REASONING: <2-4 sentences>
"""


    response = client.models.generate_content(
        model=model,
        contents=prompt,
    )
    text = (response.text or "").strip()

    score = None
    reasoning = ""
    dimensions_table = ""

    # Parse SCORE: N
    score_m = re.search(r"SCORE:\s*(\d+)", text, re.I)
    if score_m:
        score = int(score_m.group(1))

    # Parse REASONING: ... (rest of block or until DIMENSIONS:)
    reasoning_m = re.search(r"REASONING:\s*(.+)", text, re.I | re.DOTALL)
    if reasoning_m:
        reasoning = reasoning_m.group(1).strip()
        if include_dimensions and "DIMENSIONS:" in reasoning:
            reasoning = reasoning.split("DIMENSIONS:")[0].strip()

    if score is None:
        numbers = re.findall(r"\b([0-9]|10)\b", text)
        if numbers:
            score = int(numbers[-1])
        else:
            score = -1
    score = max(0, min(10, score))

    # Parse DIMENSIONS: block (lines after "DIMENSIONS:" that look like "X | Y | Z | W")
    if include_dimensions:
        dim_block = re.search(r"DIMENSIONS:\s*\n(.+?)(?=\n\s*\n|\Z)", text, re.I | re.DOTALL)
        if dim_block:
            lines = []
            for line in dim_block.group(1).strip().split("\n"):
                line = line.strip()
                if line and "|" in line:
                    lines.append(line)
            dimensions_table = "\n".join(lines)

    return {
        "score": score,
        "reasoning": reasoning or text[:500],
        "dimensions_table": dimensions_table,
    }
