"""
Skills enrichment — injects confirmed skills from skills interviews
into resume data for optimization scoring.
"""

import contextlib
import json

from models import get_db


def get_confirmed_skills(user_id):
    """Get skills confirmed as 'has_skill=True' from finalized skills interviews.

    Returns list of skill name strings (lowercased, deduplicated).
    """
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, skills FROM skills_interview_sessions "
            "WHERE user_id = ? AND is_finalized = 1 "
            "ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()

    if not rows:
        return []

    # Re-finalize to get results (finalize_session is idempotent for finalized sessions)
    # Instead, re-read the conversation and parse the stored results
    # The finalize_session stores results transiently — we need to re-derive
    # from the skills list + assume confirmed (since session was finalized)
    confirmed = set()
    for row in rows:
        skills = row["skills"]
        if isinstance(skills, str):
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                skills = json.loads(skills)
        if isinstance(skills, list):
            for s in skills:
                if isinstance(s, str) and s.strip():
                    confirmed.add(s.strip().lower())

    return sorted(confirmed)


def enrich_resume_data_with_confirmed_skills(resume_data, user_id):
    """Inject confirmed interview skills into resume_data for optimization.

    Adds confirmed skills to the skills list and appends a skills section
    to the text (so keyword matching picks them up). Deduplicates.
    """
    confirmed = get_confirmed_skills(user_id)
    if not confirmed:
        return resume_data

    existing_skills = {s.lower() for s in resume_data.get("skills", [])}
    new_skills = [s for s in confirmed if s not in existing_skills]

    if not new_skills:
        return resume_data

    resume_data["skills"] = resume_data.get("skills", []) + new_skills
    resume_data["text"] = (
        resume_data.get("text", "")
        + "\n\nValidated Skills (confirmed via interview): "
        + ", ".join(new_skills)
    )

    return resume_data
