"""
Generate interview questions from a LinkedIn profile using Gemini.
Used by the calibrator agent's linkedin flow.
"""
import os
from pathlib import Path

_config_env = Path(__file__).resolve().parent.parent / "config" / ".env"
if _config_env.exists():
    from dotenv import load_dotenv
    load_dotenv(_config_env)


def generate_questions_from_profile(
    profile_text: str,
    candidate_name: str = "",
    position: str = "",
    *,
    model: str | None = None,
    api_key: str | None = None,
) -> str:
    """
    Use Gemini to generate specific interview questions based on LinkedIn profile content.
    Returns markdown text with a short intro and a numbered list of questions.
    """
    from google import genai

    model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    api_key = api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set")

    client = genai.Client(api_key=api_key)

    context = ""
    if candidate_name or position:
        context = f"Candidate name: {candidate_name}\nTarget role/position: {position}\n\n"

    prompt = f"""You are an expert interviewer. Based on the following LinkedIn profile content, generate specific, personalized interview questions to ask this candidate. Questions should:
- Be tailored to their experience, skills, and background as shown in the profile
- Mix behavioral, situational, and role-relevant questions
- Help assess fit for the role and company
- Be concrete and answerable (not vague)

{context}## LinkedIn profile content
{profile_text}

---
Output a short markdown document with:
1. A one-line title: "Interview questions for [Name]"
2. A brief intro sentence (e.g. "Questions tailored to the candidate's profile for the [position] role.")
3. A numbered list of 8–12 specific questions. Each question should be one or two sentences, clear, and directly related to something in their profile.
Do not add explanations or categories; just the title, intro, and the numbered list."""

    response = client.models.generate_content(
        model=model,
        contents=prompt,
    )
    return (response.text or "").strip()
