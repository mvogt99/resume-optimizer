"""Application orchestrator — one-click apply pipeline."""

import json
import logging

from models import get_db

logger = logging.getLogger(__name__)


def apply_to_job(user_id, posting_id, template_id=None):
    """Full apply pipeline: tailor resume + cover letter + pipeline move.

    Returns bundle dict with all generated artifacts.
    """
    from agents import get_app_tracker, get_cover_letter, get_resume_tailor

    # 1. Load posting
    posting = _get_posting(user_id, posting_id)
    if not posting:
        raise ValueError(f"Posting {posting_id} not found")

    bundle = {
        "posting_id": posting_id,
        "posting_title": posting.get("title", ""),
        "posting_company": posting.get("company", ""),
    }

    # 2. Tailor resume
    tailor = get_resume_tailor()
    try:
        tailor_result = tailor.tailor_resume(user_id, posting_id, template_id=template_id)
        bundle["tailored_resume"] = tailor_result
    except Exception as exc:
        logger.warning("Resume tailor failed: %s", exc)
        bundle["tailored_resume"] = None
        bundle["tailor_error"] = str(exc)

    # 3. Generate cover letter
    cover = get_cover_letter()
    try:
        cover_result = cover.generate(user_id, posting_id)
        bundle["cover_letter"] = cover_result
    except Exception as exc:
        logger.warning("Cover letter failed: %s", exc)
        bundle["cover_letter"] = None
        bundle["cover_error"] = str(exc)

    # 4. Move to "applied" stage in pipeline
    tracker = get_app_tracker()
    try:
        tracker.move_stage(posting_id, "applied", user_id=user_id)
        bundle["pipeline_stage"] = "applied"
    except Exception as exc:
        logger.warning("Pipeline move failed: %s", exc)
        bundle["pipeline_stage"] = posting.get("status", "unknown")

    # Determine bundle completeness
    has_resume = bundle.get("tailored_resume") is not None
    has_cover = bundle.get("cover_letter") is not None
    if has_resume and has_cover:
        bundle["status"] = "complete"
    elif has_resume or has_cover:
        bundle["status"] = "partial"
    else:
        bundle["status"] = "failed"

    return bundle


def get_bundle(user_id, posting_id):
    """Get a previously generated application bundle (tailored resume + cover letter)."""
    posting = _get_posting(user_id, posting_id)
    if not posting:
        return None

    bundle = {
        "posting_id": posting_id,
        "posting_title": posting.get("title", ""),
        "posting_company": posting.get("company", ""),
        "pipeline_stage": posting.get("status", ""),
    }

    # Load tailored version if exists
    tv_id = posting.get("tailored_version_id", "")
    if tv_id:
        from models import ResumeVersion

        version = ResumeVersion.get_by_id(tv_id)
        if version:
            bundle["tailored_resume"] = {"text": version.parsed_text}

    # Load cover letter if exists
    cl_id = posting.get("cover_letter_id", "")
    if cl_id:
        with get_db() as conn:
            row = conn.execute("SELECT * FROM cover_letters WHERE id = ?", (cl_id,)).fetchone()
            if row:
                bundle["cover_letter"] = dict(row)

    return bundle


def record_outcome(user_id, posting_id, outcome, notes=""):
    """Record application feedback/outcome."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO application_feedback "
            "(user_id, posting_id, outcome, notes) VALUES (?, ?, ?, ?)",
            (user_id, posting_id, outcome, notes),
        )
        conn.commit()
        return cursor.lastrowid


def get_feedback(user_id):
    """Get all feedback for a user."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT af.*, jp.title as posting_title, jp.company as posting_company "
            "FROM application_feedback af "
            "LEFT JOIN job_postings jp ON af.posting_id = jp.id "
            "WHERE af.user_id = ? ORDER BY af.created_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_insights(user_id):
    """Analyze application outcomes for patterns."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT outcome, COUNT(*) as count FROM application_feedback "
            "WHERE user_id = ? GROUP BY outcome",
            (user_id,),
        ).fetchall()

    total = sum(r["count"] for r in rows)
    distribution = {r["outcome"]: r["count"] for r in rows}

    interviews = distribution.get("interview", 0) + distribution.get("offer", 0)
    response_rate = (interviews / max(total, 1)) * 100

    return {
        "total_applications": total,
        "outcome_distribution": distribution,
        "response_rate": round(response_rate, 1),
        "positive_outcomes": interviews,
        "recommendations": _generate_recommendations(distribution, total),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_posting(user_id, posting_id):
    """Load a job posting from DB."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM job_postings WHERE id = ? AND user_id = ?",
            (posting_id, user_id),
        ).fetchone()
        return dict(row) if row else None


def _generate_recommendations(distribution, total):
    """Simple rule-based recommendations from outcome data."""
    recs = []
    if total == 0:
        return ["Start applying to build data for insights."]

    ghosted = distribution.get("ghosted", 0) + distribution.get("no_response", 0)
    if ghosted > total * 0.5:
        recs.append("High ghost rate. Consider following up 5-7 days after applying.")
    rejected = distribution.get("rejected", 0)
    if rejected > total * 0.4:
        recs.append("High rejection rate. Review resume keywords and tailor more aggressively.")
    interviews = distribution.get("interview", 0)
    offers = distribution.get("offer", 0)
    if interviews > 0 and offers == 0:
        recs.append("Getting interviews but no offers. Focus on interview prep and STAR examples.")
    if offers > 0:
        recs.append(f"Great work! {offers} offer(s) received.")
    if not recs:
        recs.append("Keep applying and tracking outcomes to build actionable insights.")
    return recs
