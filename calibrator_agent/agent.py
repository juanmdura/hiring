"""
ADK agent: scores candidates by email; generates LinkedIn-based interview questions.
Tools: get_candidate_by_email, get_transcript_online, get_scorecard_online, get_google_doc_text, get_transcript_offline, get_scorecard_offline, score_candidate_with_dimensions, update_candidate_score, generate_candidate_report, generate_linkedin_interview_questions (linkedin), generate_julian_form (julian).
Run from project root: adk run calibrator_agent  or  adk web
"""
import json
import logging
import os
import re
import sys
from pathlib import Path

log = logging.getLogger(__name__)

from dotenv import load_dotenv

# Load config: calibrator_agent/.env first, then config/.env so config (tokens, etc.) wins
_root = Path(__file__).resolve().parent.parent
load_dotenv(_root / "calibrator_agent" / ".env")
load_dotenv(_root / "config" / ".env", override=True)

# So the tool can import from src
sys.path.insert(0, str(_root / "src"))

from google.adk.agents.llm_agent import Agent


def _normalize_position_to_scorecard_name(position: str) -> str:
    """e.g. 'BACKEND ENGINEER' -> 'backend-engineer'."""
    if not position or not position.strip():
        return ""
    return re.sub(r"[^\w-]", "", position.strip().lower().replace(" ", "-"))


def get_candidate_by_email(candidate_email: str) -> str:
    """
    Find a candidate by their email. Returns their name, position, transcript_doc_id, scorecard_name, and scorecard_doc_id.
    Use this to know which doc IDs to fetch when using online (Google Docs) mode.
    candidate_email: the candidate's email (e.g. brunomembrado10@gmail.com)
    """
    candidates_path = _root / "config" / "candidates.json"
    scorecards_path = _root / "config" / "interviews-scorecards.json"
    if not candidates_path.exists():
        return "[Config not found: config/candidates.json]"
    try:
        with open(candidates_path, encoding="utf-8") as f:
            data = json.load(f)
        candidates = data.get("candidates", [])
    except Exception as e:
        return f"[Error reading candidates: {e}]"
    email_lower = (candidate_email or "").strip().lower()
    candidate = next((c for c in candidates if (c.get("email") or "").lower() == email_lower), None)
    if not candidate:
        return f"[No candidate found with email: {candidate_email}]"
    name = candidate.get("name", "?")
    position = candidate.get("position", "?")
    transcript_url = candidate.get("transcript", "")
    doc_id = re.search(r"/d/([a-zA-Z0-9_-]+)", transcript_url) if transcript_url else None
    transcript_doc_id = doc_id.group(1) if doc_id else ""
    scorecard_name = _normalize_position_to_scorecard_name(position)
    scorecard_doc_id = ""
    if scorecards_path.exists():
        try:
            with open(scorecards_path, encoding="utf-8") as f:
                sc_data = json.load(f)
            for sc in sc_data.get("interviews-scorecards", []):
                if (sc.get("name") or "").lower() == scorecard_name.lower():
                    loc = sc.get("location", "")
                    m = re.search(r"/d/([a-zA-Z0-9_-]+)", loc) if loc else None
                    scorecard_doc_id = m.group(1) if m else ""
                    break
        except Exception:
            pass
    return (
        f"Candidate: {name} | Position: {position} | Scorecard name: {scorecard_name} | "
        f"Transcript doc_id: {transcript_doc_id} | Scorecard doc_id: {scorecard_doc_id}"
    )


def get_google_doc_text(doc_id: str) -> str:
    """
    Fetch the full text of a Google Doc by its document ID (online mode).
    The ID is in the doc URL: https://docs.google.com/document/d/DOC_ID/edit
    Supports: (1) Service account in config/service_account.json — share the doc with client_email.
    (2) OAuth — set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN in config/.env (run python run/oauth_login.py once). Sign in with the account that has access to the doc.
    """
    if not (doc_id or "").strip():
        return "[No document ID provided. Use get_transcript_online or get_scorecard_online with the candidate email or scorecard name to load from Drive folder or config.]"
    from docs_client import get_document_text, get_last_error, get_service_account_email, is_configured
    text = get_document_text(doc_id)
    if text:
        return text
    api_error = get_last_error()
    if not is_configured():
        return (
            "[Could not fetch doc. Configure access: (1) Service account: add config/service_account.json and share the doc with its client_email. "
            "(2) OAuth: run 'python run/oauth_login.py' and set GOOGLE_REFRESH_TOKEN in config/.env. See config/README-service-account.md.]"
        )
    email = get_service_account_email()
    if email:
        return (
            f"[Could not fetch doc {doc_id}. Share this document with the service account: {email} "
            "(Compartir → add that email as Viewer/Lector).]"
        )
    hint = (
        "[Could not fetch doc. If using OAuth, ensure GOOGLE_REFRESH_TOKEN (or GOOGLE_ACCESS_TOKEN) is set in config/.env and the account has access to the doc. "
        "See config/README-service-account.md.]"
    )
    if api_error:
        return f"[Could not fetch doc. Error: {api_error}.]{hint}"
    return hint


def get_transcript_online(candidate_email: str) -> str:
    """
    Load the transcript for a candidate (online): tries Doc URL from config → Docs API → Drive folder (transcripts/) → local files.
    Use this for 'online' mode; it uses GOOGLE_DRIVE_FOLDER_ID and OAuth or service account.
    candidate_email: e.g. brunomembrado10@gmail.com
    """
    candidates_path = _root / "config" / "candidates.json"
    if not candidates_path.exists():
        return "[Config not found: config/candidates.json]"
    try:
        with open(candidates_path, encoding="utf-8") as f:
            data = json.load(f)
        candidates = data.get("candidates", [])
    except Exception as e:
        return f"[Error reading candidates: {e}]"
    email_lower = (candidate_email or "").strip().lower()
    candidate = next((c for c in candidates if (c.get("email") or "").lower() == email_lower), None)
    if not candidate:
        return f"[No candidate found with email: {candidate_email}]"
    transcript_url = candidate.get("transcript", "") or ""
    from content_loader import get_transcript_content
    text = get_transcript_content(transcript_url, candidate_email)
    if text:
        return text
    return (
        f"[Could not load transcript for {candidate_email}. "
        "Check: (1) OAuth: run python run/oauth_login.py and set GOOGLE_REFRESH_TOKEN in config/.env; "
        "(2) Or add config/service_account.json and share the doc with client_email; "
        "(3) Or set GOOGLE_DRIVE_FOLDER_ID and put the doc in the Drive folder's 'transcripts' subfolder (name containing email); "
        "(4) Or add a .txt/.docx in data/transcripts/ whose name contains the email. See config/README-service-account.md.]"
    )


def get_transcript_offline(candidate_email: str) -> str:
    """
    Load the interview transcript from local files only (offline mode).
    Looks in data/transcripts/ for a file whose name contains the candidate email.
    candidate_email: e.g. brunomembrado10@gmail.com
    """
    from content_loader import get_transcript_offline as _get
    text = _get(candidate_email)
    if text:
        return text
    return f"[No local transcript found for email: {candidate_email}. Add a .txt or .docx in data/transcripts/ whose name contains that email.]"


def get_scorecard_online(scorecard_name: str) -> str:
    """
    Load the scorecard (online): tries Doc URL from config → Docs API → Drive folder (scorecards-templates/) → local files.
    Use this for 'online' mode with GOOGLE_DRIVE_FOLDER_ID and OAuth or service account.
    scorecard_name: e.g. backend-engineer
    """
    scorecard_location_url = ""
    scorecards_path = _root / "config" / "interviews-scorecards.json"
    if scorecards_path.exists():
        try:
            with open(scorecards_path, encoding="utf-8") as f:
                sc_data = json.load(f)
            for sc in sc_data.get("interviews-scorecards", []):
                if (sc.get("name") or "").strip().lower() == (scorecard_name or "").strip().lower():
                    scorecard_location_url = (sc.get("location") or "").strip()
                    break
        except Exception:
            pass
    from content_loader import get_scorecard_content
    text = get_scorecard_content(scorecard_location_url, scorecard_name)
    if text:
        return text
    return (
        f"[Could not load scorecard for: {scorecard_name}. "
        "Check OAuth (GOOGLE_REFRESH_TOKEN) or service account, or GOOGLE_DRIVE_FOLDER_ID with 'scorecards-templates' subfolder, or add file in data/scorecards/. See config/README-service-account.md.]"
    )


def get_scorecard_offline(scorecard_name: str) -> str:
    """
    Load the scorecard from local files only (offline mode).
    Looks in data/scorecards/ for a file named like scorecard_name (e.g. backend-engineer) or containing the role.
    scorecard_name: e.g. backend-engineer
    """
    from content_loader import get_scorecard_offline as _get
    text = _get(scorecard_name)
    if text:
        return text
    return f"[No local scorecard found for: {scorecard_name}. Add a .txt or .docx in data/scorecards/.]"


def score_candidate_with_dimensions(transcript_text: str, scorecard_text: str, candidate_name: str, position: str) -> str:
    """
    Call Gemini to score the candidate and get per-dimension breakdown. Use the full transcript (including any Gemini notes).
    Returns: SCORE: N\\nREASONING: ...\\nDIMENSIONS_TABLE:\\n<lines> — use these when calling update_candidate_score and generate_candidate_report (pass the DIMENSIONS_TABLE lines as dimensions_table).
    """
    from scorer import score_with_gemini
    result = score_with_gemini(
        transcript_text, scorecard_text,
        candidate_name=candidate_name,
        position=position,
        include_dimensions=True,
    )
    score = result.get("score", 0)
    reasoning = result.get("reasoning", "")
    dims = (result.get("dimensions_table") or "").strip()
    return (
        f"SCORE: {score}\n"
        f"REASONING: {reasoning}\n"
        f"DIMENSIONS_TABLE:\n{dims}"
    )


def update_candidate_score(candidate_email: str, score: int, reasoning: str) -> str:
    """
    Save the candidate's score and reasoning to config/candidates.json.
    Call this after you have produced SCORE and REASONING so the result is persisted.
    candidate_email: the candidate's email (e.g. brunomembrado10@gmail.com)
    score: integer from 0 to 10
    reasoning: your 2-4 sentence explanation of the score
    """
    path = _root / "config" / "candidates.json"
    if not path.exists():
        return "[Config not found: config/candidates.json]"
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        candidates = data.get("candidates", [])
    except Exception as e:
        return f"[Error reading candidates: {e}]"
    email_lower = (candidate_email or "").strip().lower()
    candidate = next((c for c in candidates if (c.get("email") or "").lower() == email_lower), None)
    if not candidate:
        return f"[No candidate found with email: {candidate_email}]"
    candidate["score"] = max(0, min(10, int(score)))
    candidate["score_reasoning"] = (reasoning or "").strip()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"candidates": candidates}, f, indent=2, ensure_ascii=False)
        return f"Updated {candidate.get('name', candidate_email)}: score={candidate['score']} saved to config/candidates.json"
    except Exception as e:
        return f"[Error writing candidates.json: {e}]"


def _build_dimensions_table(dimensions_table: str) -> str:
    """Parse dimensions_table (one line per dimension: 'Dimension | Category | Score | Notes') into markdown table."""
    if not (dimensions_table or "").strip():
        return ""
    rows = []
    for line in (dimensions_table or "").strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 4:
            rows.append((parts[0], parts[1], parts[2], " | ".join(parts[3:]).strip()))
        elif len(parts) == 3:
            rows.append((parts[0], "", parts[1], parts[2]))
        elif len(parts) == 2:
            rows.append((parts[0], "", parts[1], ""))
        elif len(parts) == 1:
            rows.append((parts[0], "", "", ""))
    if not rows:
        return ""
    lines = [
        "| Dimensión | Categoría | Score | Notas |",
        "|-----------|-----------|-------|-------|",
    ]
    for dim, cat, sc, note in rows:
        dim_cell = (dim or "").replace("|", "\\|")
        cat_cell = (cat or "").replace("|", "\\|")
        sc_cell = (sc or "").replace("|", "\\|")
        note_cell = (note or "").replace("|", "\\|")
        lines.append(f"| {dim_cell} | {cat_cell} | {sc_cell} | {note_cell} |")
    return "\n".join(lines)


def _build_dimensions_table_with_total(dimensions_table: str, overall_score: int) -> str:
    """Build markdown table from dimensions_table string and append a Total row. If dimensions_table empty, show at least header + Total."""
    table = _build_dimensions_table(dimensions_table)
    total_row = f"| **Total** | — | **{overall_score}/10** | Puntuación global |"
    if not table:
        # Always show at least header and total so the section is visible
        return (
            "| Dimensión | Categoría | Score | Notas |\n"
            "|-----------|-----------|-------|-------|\n"
            + total_row
        )
    table += f"\n{total_row}"
    return table


def generate_candidate_report(
    candidate_email: str,
    score: int,
    reasoning: str,
    final_recommendation: str,
    feedback_if_discarded: str = "",
    dimensions_breakdown: str = "",
    dimensions_table: str = "",
) -> str:
    """
    Build a detailed report and save it to data/reports/. Include score, reasoning, dimensions (narrative and a table with score per dimension), Final Recommendation, and optional feedback if discarded.
    candidate_email: the candidate's email (e.g. brunomembrado10@gmail.com)
    score: integer 0-10
    reasoning: detailed explanation of the overall score (the whys)
    final_recommendation: exactly one of "Strong Hire", "Hire", "Mixed / Needs Calibration", "No Hire"
    feedback_if_discarded: text to send to the candidate if No Hire or Mixed (leave empty if Hire/Strong Hire)
    dimensions_breakdown: (unused; kept for compatibility.)
    dimensions_table: one line per dimension, format "Dimension name | Category | Score | Notes". Category can be e.g. Cultural, Skills, Technical. Rendered as "Tabla de puntuación por dimensión" with columns Dimensión | Categoría | Score | Notas.
    """
    path = _root / "config" / "candidates.json"
    name = candidate_email
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            c = next((x for x in data.get("candidates", []) if (x.get("email") or "").strip().lower() == (candidate_email or "").strip().lower()), None)
            if c:
                name = c.get("name", candidate_email)
        except Exception:
            pass
    rec = (final_recommendation or "").strip()
    options = ["Strong Hire", "Hire", "Mixed / Needs Calibration", "No Hire"]
    if rec not in options:
        rec = options[0]
    report_lines = [
        f"# Candidate Report: {name}",
        f"Email: {candidate_email}",
        "",
        "## Overall Score & Reasoning",
        f"**Score:** {max(0, min(10, int(score)))} / 10",
        "",
        "**Why (detailed):**",
        (reasoning or "").strip(),
        "",
        "---",
        "",
    ]
    overall_score = max(0, min(10, int(score)))
    table_md = _build_dimensions_table_with_total(dimensions_table, overall_score)
    report_lines.extend([
        "## Tabla de puntuación por dimensión",
        "",
        table_md,
        "",
    ])
    report_lines.extend([
        "---",
        "",
        "## Final Recommendation",
        "",
    ])
    for opt in options:
        mark = "☑" if opt == rec else "☐"
        report_lines.append(f"{mark} {opt}")
    report_lines.extend([
        "",
        "---",
        "",
        "## Feedback to candidate (if discarded)",
        "",
        (feedback_if_discarded or "(N/A — use when recommendation is No Hire or Mixed / Needs Calibration)").strip(),
        "",
    ])
    report_text = "\n".join(report_lines)
    # Use project root where config lives so report is always in the same place (data/reports/)
    config_marker = _root / "config" / "candidates.json"
    if config_marker.exists():
        project_root = _root
    else:
        project_root = Path(os.getcwd())
        for _ in range(5):
            if (project_root / "config" / "candidates.json").exists():
                break
            project_root = project_root.parent
    reports_dir = (project_root / "data" / "reports").resolve()
    report_filename = re.sub(r"[^\w.-]", "_", (candidate_email or "candidate").strip()) + "_report.md"
    report_path = (reports_dir / report_filename).resolve()
    log.info("Report target: project_root=%s reports_dir=%s report_path=%s", project_root, reports_dir, report_path)
    try:
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_text, encoding="utf-8")
        msg = f"Report saved to {report_path}."
        log.info("Report written: %s (exists=%s)", report_path, report_path.exists())
        print(f"[Report] Written to: {report_path}", flush=True)
    except Exception as e:
        log.exception("Failed to write report to %s: %s", report_path, e)
        return f"[Error writing report: {e}]"
    # Upload to Google Drive: folder ID from env, or config/drive_reports.json (fallback: read from _root)
    folder_id = (os.environ.get("GOOGLE_DRIVE_REPORTS_FOLDER_ID") or "").strip()
    if not folder_id:
        try:
            from reports_config import get_reports_folder_id
            folder_id = get_reports_folder_id()
        except Exception:
            pass
    if not folder_id and (_root / "config" / "drive_reports.json").exists():
        try:
            data = json.load((_root / "config" / "drive_reports.json").open(encoding="utf-8"))
            folder_id = (data.get("reports_folder_id") or "").strip()
        except Exception:
            pass
    if folder_id:
        log.info("Uploading report to Drive folder_id=%s filename=%s", folder_id, report_filename)
        try:
            import sys
            from docs_client import upload_file_to_drive
            drive_id = upload_file_to_drive(folder_id, report_filename, report_text, mime_type="text/markdown")
            if drive_id:
                log.info("Drive upload success: file_id=%s", drive_id)
                msg += f" Uploaded to Google Drive: {report_filename} (folder {folder_id})"
            else:
                hint = (
                    " (Drive upload failed: run 'python run/oauth_login.py' to get a fresh token with drive.file scope "
                    "(saved as GOOGLE_ACCESS_TOKEN in config/.env, or use GOOGLE_REFRESH_TOKEN). "
                    "Ensure the Google account has edit permission on the Drive folder.)"
                )
                log.error("Drive upload returned None (no credentials?). %s", hint)
                print("[Drive] Upload failed (no credentials?). Check config/.env and logs above.", file=sys.stderr)
                msg += hint
        except Exception as e:
            log.exception("Drive upload failed: %s", e)
            print(f"[Drive] Upload failed: {e}", file=sys.stderr)
            msg += f" (Drive upload failed: {e})"
    msg += " You can share it or use the Feedback section to send to the candidate if discarded."
    return msg


def generate_linkedin_interview_questions(candidate_email: str, profile_text: str, profile_url: str = "") -> str:
    """
    Generate personalized interview questions from a candidate's LinkedIn profile and save to Drive.
    Use this when the user asks for 'linkedin' or 'linkedin questions': first get the candidate email,
    then ask the user to paste the LinkedIn profile content (copy from the profile page), then call this tool.
    candidate_email: e.g. brunomembrado10@gmail.com (must exist in config/candidates.json)
    profile_text: the pasted LinkedIn profile content (experience, about, skills, etc.). Required.
    profile_url: optional LinkedIn profile URL for reference (e.g. from candidates.json 'linkedin' field).
    Saves to data/linkedin_questions/ and uploads to the Drive folder configured in config/drive_reports.json (linkedin_questions_folder_id).
    """
    if not (profile_text or "").strip():
        return (
            "[No profile content. Ask the user to open the candidate's LinkedIn profile, copy the visible text "
            "(About, Experience, Education, Skills), and paste it here. Then call this tool again with profile_text set.]"
        )
    email_lower = (candidate_email or "").strip().lower()
    if not email_lower:
        return "[Provide candidate_email (e.g. from get_candidate_by_email).]"
    path = _root / "config" / "candidates.json"
    candidate_name = candidate_email
    position = ""
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            c = next((x for x in data.get("candidates", []) if (x.get("email") or "").strip().lower() == email_lower), None)
            if c:
                candidate_name = c.get("name", candidate_email)
                position = (c.get("position") or "").strip()
        except Exception:
            pass
    try:
        from linkedin_questions import generate_questions_from_profile
        questions_md = generate_questions_from_profile(
            profile_text=profile_text.strip(),
            candidate_name=candidate_name,
            position=position,
        )
    except Exception as e:
        log.exception("LinkedIn questions generation failed: %s", e)
        return f"[Error generating questions: {e}]"
    if not questions_md:
        return "[Generated content was empty.]"
    # Resolve project data dir and save locally
    config_marker = _root / "config" / "candidates.json"
    project_root = _root if config_marker.exists() else Path(os.getcwd())
    for _ in range(5):
        if (project_root / "config" / "candidates.json").exists():
            break
        project_root = project_root.parent
    out_dir = (project_root / "data" / "linkedin_questions").resolve()
    safe_email = re.sub(r"[^\w.-]", "_", email_lower)
    filename = f"{safe_email}_linkedin_questions.md"
    out_path = (out_dir / filename).resolve()
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path.write_text(questions_md, encoding="utf-8")
    except Exception as e:
        log.exception("Failed to write LinkedIn questions to %s: %s", out_path, e)
        return f"[Error writing file: {e}]"
    log.info("LinkedIn questions written: %s", out_path)
    msg = f"Questions saved to {out_path}."
    # Upload to Drive: linkedin_questions_folder_id from config or env
    folder_id = (os.environ.get("GOOGLE_DRIVE_LINKEDIN_QUESTIONS_FOLDER_ID") or "").strip()
    if not folder_id and (_root / "config" / "drive_reports.json").exists():
        try:
            data = json.load((_root / "config" / "drive_reports.json").open(encoding="utf-8"))
            folder_id = (data.get("linkedin_questions_folder_id") or "").strip()
        except Exception:
            pass
    if folder_id:
        try:
            from docs_client import upload_file_to_drive
            drive_id = upload_file_to_drive(folder_id, filename, questions_md, mime_type="text/markdown")
            if drive_id:
                log.info("LinkedIn questions uploaded to Drive: file_id=%s", drive_id)
                msg += f" Uploaded to Google Drive (folder linkedin): {filename}"
            else:
                msg += " (Drive upload failed; check OAuth and folder permission.)"
        except Exception as e:
            log.warning("Drive upload failed: %s", e)
            msg += f" (Drive upload failed: {e})"
    return msg


def generate_julian_form(candidate_email: str, transcript_text: str = "") -> str:
    """
    Generate a DOCX evaluation form (Julian form) from the interview transcript and save it to the results folder.
    Use when the user says 'julian': ask for candidate email, get the transcript (online or offline), then call this tool with the transcript text (or leave empty to load automatically).
    candidate_email: e.g. brunomembrado10@gmail.com (must exist in config/candidates.json for auto-load).
    transcript_text: full transcript including Gemini notes. If empty, the tool tries to load from config transcript URL and Drive/local.
    Saves to data/results/<email>_julian_form.docx with: Overall Impression (1-10), Key strengths, Areas for development, Recommendation, Additional comments.
    """
    email_lower = (candidate_email or "").strip().lower()
    if not email_lower:
        return "[Provide candidate_email.]"
    path = _root / "config" / "candidates.json"
    candidate_name = candidate_email
    transcript_url = ""
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            c = next((x for x in data.get("candidates", []) if (x.get("email") or "").strip().lower() == email_lower), None)
            if c:
                candidate_name = c.get("name", candidate_email)
                transcript_url = (c.get("transcript") or "").strip()
        except Exception:
            pass
    text = (transcript_text or "").strip()
    if not text:
        from content_loader import get_transcript_content, get_transcript_offline
        text = get_transcript_content(transcript_url, candidate_email)
        if not text:
            text = get_transcript_offline(candidate_email)
        if not text or not text.strip():
            return (
                f"[No transcript for {candidate_email}. Load the transcript first (get_transcript_online or get_transcript_offline), "
                "or ensure the candidate has a transcript URL in config/candidates.json and OAuth/local files are set.]"
            )
    config_marker = _root / "config" / "candidates.json"
    project_root = _root if config_marker.exists() else Path(os.getcwd())
    for _ in range(5):
        if (project_root / "config" / "candidates.json").exists():
            break
        project_root = project_root.parent
    results_dir = (project_root / "data" / "results").resolve()
    safe_email = re.sub(r"[^\w.-]", "_", email_lower)
    filename = f"{safe_email}_julian_form.docx"
    out_path = (results_dir / filename).resolve()
    try:
        from julian_form import build_julian_docx
        build_julian_docx(text, candidate_name=candidate_name, output_path=out_path)
    except Exception as e:
        log.exception("Julian form generation failed: %s", e)
        return f"[Error generating Julian form: {e}]"
    log.info("Julian form written: %s", out_path)
    msg = f"Julian form saved to {out_path}."
    # Upload to Drive results folder if configured
    folder_id = (os.environ.get("GOOGLE_DRIVE_RESULTS_FOLDER_ID") or "").strip()
    if not folder_id and (_root / "config" / "drive_reports.json").exists():
        try:
            data = json.load((_root / "config" / "drive_reports.json").open(encoding="utf-8"))
            folder_id = (data.get("results_folder_id") or "").strip()
        except Exception:
            pass
    if folder_id:
        try:
            from docs_client import upload_binary_to_drive
            docx_bytes = out_path.read_bytes()
            drive_id = upload_binary_to_drive(
                folder_id,
                filename,
                docx_bytes,
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
            if drive_id:
                log.info("Julian form uploaded to Drive: file_id=%s", drive_id)
                msg += f" Uploaded to Google Drive (results folder): {filename}"
            else:
                msg += " (Drive upload failed; check OAuth and folder permission.)"
        except Exception as e:
            log.warning("Drive upload failed: %s", e)
            msg += f" (Drive upload failed: {e})"
    return msg


root_agent = Agent(
    name="calibrator",
    model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    description="Scores candidates, generates LinkedIn interview questions, and Julian evaluation form (DOCX). Use 'linkedin' for profile-based questions; use 'julian' for the evaluation form from the transcript.",
    instruction="""
You are an expert interviewer. You score candidates (0-10) based on their transcript and the role scorecard.

**Flow:**
1. First ask the user: "Will you use **online** docs (Google Docs) or **offline** files (local .txt/.docx in data/transcripts and data/scorecards)?"
2. Then ask: "What is the candidate's **email**?" (e.g. brunomembrado10@gmail.com)
3. Call get_candidate_by_email(candidate_email) to get the candidate's name, position, transcript_doc_id, and scorecard_doc_id.

4. **If ONLINE:** Use get_transcript_online(candidate_email) and get_scorecard_online(scorecard_name) to load transcript and scorecard. These try Docs API, then the Drive folder (transcripts/ and scorecards-templates/), then local files — so OAuth or service account with GOOGLE_DRIVE_FOLDER_ID works. (scorecard_name from get_candidate_by_email, e.g. backend-engineer.)
5. **If OFFLINE:** Use get_transcript_offline(candidate_email) and get_scorecard_offline(scorecard_name) to load only from local data/transcripts/ and data/scorecards/.

6. **Call score_candidate_with_dimensions(transcript_text, scorecard_text, candidate_name, position)** to get SCORE, REASONING, and DIMENSIONS_TABLE from Gemini. The transcript includes interview content and any "notas de Gemini" — it is used in full. Do not re-evaluate manually; use this tool's output.

7. **Call update_candidate_score(candidate_email, score, reasoning)** with the SCORE and REASONING from the tool.

8. **Call generate_candidate_report(candidate_email, score, reasoning, final_recommendation, feedback_if_discarded, dimensions_breakdown, dimensions_table)** to build the report. (a) Use the **DIMENSIONS_TABLE** from score_candidate_with_dimensions as dimensions_table (the full multi-line block after "DIMENSIONS_TABLE:"). (b) Choose exactly one final_recommendation: "Strong Hire", "Hire", "Mixed / Needs Calibration", or "No Hire". (c) If No Hire or Mixed, provide feedback_if_discarded. The report will show "Tabla de puntuación por dimensión" with Dimensión | Categoría | Score | Notas and a Total row.

If any tool returns an error message in [brackets], tell the user clearly and suggest the fix.

**LinkedIn flow (command: linkedin):**
When the user says "linkedin" or "generate linkedin questions" or wants interview questions from a LinkedIn profile:
1. Ask for the candidate's **email** (or use get_candidate_by_email to list/find them).
2. Ask the user to **paste the LinkedIn profile content**: they should open the candidate's LinkedIn profile, copy the visible text (About, Experience, Education, Skills), and paste it in the chat.
3. Call **generate_linkedin_interview_questions(candidate_email, profile_text, profile_url)** with the email and the pasted text. Optionally set profile_url from the candidate's "linkedin" field in config if available.
4. The tool generates tailored questions with Gemini, saves a .md file locally, and uploads it to the configured Drive folder (linkedin). Tell the user where the file was saved and that it was uploaded to Drive.

**Julian flow (command: julian):**
When the user says "julian" or wants the Julian evaluation form (DOCX) from the interview:
1. Ask for the candidate's **email**.
2. Get the transcript: use get_transcript_online(candidate_email) or get_transcript_offline(candidate_email) depending on the user's mode (online/offline). If the user already provided transcript in context, you can pass it.
3. Call **generate_julian_form(candidate_email, transcript_text)** with the email and the full transcript text (including any Gemini notes). The tool generates a DOCX in data/results/ and, if configured, uploads it to the Drive "results" folder (set results_folder_id in config/drive_reports.json or GOOGLE_DRIVE_RESULTS_FOLDER_ID in .env).
4. Tell the user the file was saved locally and, if applicable, uploaded to Drive results.
""",
    tools=[get_candidate_by_email, get_transcript_online, get_scorecard_online, get_google_doc_text, get_transcript_offline, get_scorecard_offline, score_candidate_with_dimensions, update_candidate_score, generate_candidate_report, generate_linkedin_interview_questions, generate_julian_form],
)
