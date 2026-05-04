"""Draft personalized LinkedIn recommendation requests based on shared work history."""

import logging
import uuid

import linkedin_cache
from llm_helper import call_llm_quality
from models import get_db

logger = logging.getLogger(__name__)


def _init_recommendation_drafts_table():
    """Create recommendation_drafts table if not exists."""
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS recommendation_drafts (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                target_name TEXT NOT NULL,
                relationship TEXT NOT NULL DEFAULT '',
                subject TEXT NOT NULL DEFAULT '',
                draft_text TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        conn.commit()


_init_recommendation_drafts_table()


def draft_recommendation_request(
    user_id, target_name, relationship, shared_projects="", specific_skills=""
):
    """Generate a personalized LinkedIn recommendation request via LLM."""
    li_profile = linkedin_cache.get_raw(user_id) or {}
    user_name = li_profile.get("full_name", li_profile.get("name", ""))
    headline = li_profile.get("headline", "")

    prompt = (
        f"Write a short, professional LinkedIn recommendation request message.\n\n"
        f"From: {user_name} ({headline})\n"
        f"To: {target_name}\n"
        f"Relationship: {relationship}\n"
    )
    if shared_projects:
        prompt += f"Shared projects/work: {shared_projects}\n"
    if specific_skills:
        prompt += f"Skills to highlight: {specific_skills}\n"
    prompt += (
        "\nWrite a warm, concise message (150-300 words) asking for a LinkedIn recommendation. "
        "Be specific about the work done together. Include a suggested subject line.\n"
        "Format:\nSubject: <subject>\n\n<message body>"
    )

    raw = call_llm_quality(prompt, task_type="reasoning", max_tokens=1024)

    # Parse subject from response
    subject = f"Recommendation request from {user_name}"
    draft_text = raw or ""
    if raw and raw.startswith("Subject:"):
        lines = raw.split("\n", 2)
        subject = lines[0].replace("Subject:", "").strip()
        draft_text = (
            lines[2].strip() if len(lines) > 2 else lines[1].strip() if len(lines) > 1 else raw
        )

    if not draft_text:
        # Fallback template
        draft_text = (
            f"Hi {target_name},\n\n"
            f"I hope you're doing well! We worked together on "
            f"{shared_projects or 'several projects'} "
            "and I really valued our collaboration. "
            "Would you be willing to write a brief LinkedIn "
            "recommendation for me? I'd be happy to return the favor.\n\n"
            f"Best regards,\n{user_name or 'Me'}"
        )

    draft_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            "INSERT INTO recommendation_drafts "
            "(id, user_id, target_name, relationship, subject, draft_text) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (draft_id, user_id, target_name, relationship, subject, draft_text),
        )
        conn.commit()

    return {
        "id": draft_id,
        "draft": draft_text,
        "subject": subject,
        "target_name": target_name,
        "relationship": relationship,
        "char_count": len(draft_text),
    }


def list_drafts(user_id):
    """List all recommendation drafts for a user."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, target_name, relationship, subject, draft_text, created_at "
            "FROM recommendation_drafts WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def update_draft(draft_id, user_id, new_text):
    """Update a draft's text."""
    with get_db() as conn:
        result = conn.execute(
            "UPDATE recommendation_drafts SET draft_text = ? WHERE id = ? AND user_id = ?",
            (new_text, draft_id, user_id),
        )
        conn.commit()
    if result.rowcount == 0:
        return {"error": "Draft not found or not yours"}
    return {"id": draft_id, "draft_text": new_text, "char_count": len(new_text)}


def delete_draft(draft_id, user_id):
    """Delete a recommendation draft."""
    with get_db() as conn:
        result = conn.execute(
            "DELETE FROM recommendation_drafts WHERE id = ? AND user_id = ?",
            (draft_id, user_id),
        )
        conn.commit()
    if result.rowcount == 0:
        return {"error": "Draft not found or not yours"}
    return {"deleted": True, "id": draft_id}
