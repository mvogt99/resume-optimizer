"""Application Pipeline routes."""

import logging

import linkedin_cache
from agents import get_app_tracker
from agents_routes_common import _LLM_LIMIT, agents_bp
from auth import require_auth
from feedback_analyzer import (
    get_correlations,
    get_feedback_summary,
    record_stage_transition,
)
from flask import g, jsonify, request
from models import get_db

from rate_limit import limiter

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Application Pipeline routes
# ──────────────────────────────────────────────


@agents_bp.route("/api/agents/pipeline", methods=["GET"])
@require_auth
def pipeline_view():
    user_id = g.user_id

    tracker = get_app_tracker()
    pipeline = tracker.get_pipeline(user_id)
    return jsonify(pipeline), 200


@agents_bp.route("/api/agents/pipeline/<posting_id>", methods=["PUT"])
@require_auth
def pipeline_move(posting_id):
    user_id = g.user_id

    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    if not new_status:
        return jsonify({"error": "Status is required"}), 400

    # P2-C: Capture old stage before move for feedback tracking
    old_stage = ""
    ats_score = 0.0
    resume_version_id = ""
    cover_letter_id = ""
    try:
        with get_db() as _conn:
            _row = _conn.execute(
                "SELECT status, ats_score, tailored_version_id, cover_letter_id "
                "FROM job_postings WHERE id=? AND user_id=?",
                (posting_id, user_id),
            ).fetchone()
            if _row:
                old_stage = _row["status"] or ""
                ats_score = _row["ats_score"] or 0.0
                resume_version_id = _row["tailored_version_id"] or ""
                cover_letter_id = _row["cover_letter_id"] or ""
    except Exception:
        pass

    tracker = get_app_tracker()
    result = tracker.move_posting(
        posting_id, new_status, notes=data.get("notes", ""), user_id=user_id
    )
    if isinstance(result, dict) and "error" in result:
        return jsonify(result), 400

    # P2-C: Record stage transition feedback
    try:
        record_stage_transition(
            user_id=int(user_id),
            posting_id=str(posting_id),
            old_stage=old_stage,
            new_stage=new_status,
            ats_score=ats_score,
            resume_version_id=resume_version_id,
            cover_letter_id=cover_letter_id,
        )
    except Exception:
        pass

    return jsonify(result), 200


@agents_bp.route("/api/agents/pipeline/analytics", methods=["GET"])
@require_auth
def pipeline_analytics():
    user_id = g.user_id

    tracker = get_app_tracker()
    analytics = tracker.get_analytics(user_id)
    return jsonify(analytics), 200


@agents_bp.route("/api/agents/pipeline/correlations", methods=["GET"])
@require_auth
def pipeline_correlations():
    """P2-C: ATS score distribution and callback rate from stage-transition feedback."""
    result = get_correlations(user_id=int(g.user_id))
    return jsonify(result), 200


@agents_bp.route("/api/agents/pipeline/feedback-summary", methods=["GET"])
@require_auth
def pipeline_feedback_summary():
    """P2-C: High-level feedback counts for the dashboard."""
    result = get_feedback_summary(user_id=int(g.user_id))
    return jsonify(result), 200


@agents_bp.route("/api/agents/pipeline/reminders", methods=["GET"])
@require_auth
def pipeline_reminders():
    user_id = g.user_id

    tracker = get_app_tracker()
    reminders = tracker.get_reminders(user_id)
    return jsonify({"reminders": reminders, "count": len(reminders)}), 200


@agents_bp.route("/api/agents/pipeline/<posting_id>/checklist", methods=["GET"])
@require_auth
def pipeline_checklist(posting_id):
    """Ready-to-apply checklist for a posting (5090-generated, expert-validated)."""
    import json as _json

    with get_db() as conn:
        posting = conn.execute(
            "SELECT id, title, company FROM job_postings WHERE id = ? AND user_id = ?",
            (posting_id, g.user_id),
        ).fetchone()

        if not posting:
            return jsonify({"error": "Posting not found"}), 404

        # Check tailored resume
        tailor_row = conn.execute(
            "SELECT metadata_json FROM resume_versions "
            "WHERE source = 'agent_tailor' AND source_id = ? LIMIT 1",
            (posting_id,),
        ).fetchone()
        tailor_done = tailor_row is not None
        tailor_detail = "Not yet tailored"
        if tailor_row:
            try:
                meta = _json.loads(tailor_row["metadata_json"] or "{}")
                score = meta.get("ats_score", 0)
                tailor_detail = f"Tailored (ATS score: {score})" if score else "Tailored"
            except (_json.JSONDecodeError, TypeError):
                tailor_detail = "Tailored"

        # Check cover letter
        cl_done = (
            conn.execute(
                "SELECT 1 FROM cover_letters WHERE posting_id = ? AND user_id = ? LIMIT 1",
                (posting_id, g.user_id),
            ).fetchone()
            is not None
        )

        # Check interview prep
        prep_row = conn.execute(
            "SELECT is_complete FROM interview_coach_sessions "
            "WHERE posting_id = ? AND user_id = ? LIMIT 1",
            (posting_id, g.user_id),
        ).fetchone()
        prep_done = prep_row is not None
        prep_detail = "Not yet started"
        if prep_row:
            prep_detail = "Complete" if prep_row["is_complete"] else "In progress"

        # Check LinkedIn profile
        li_done = linkedin_cache.has_profile(g.user_id)

    checklist = [
        {"item": "Resume Tailored", "done": tailor_done, "detail": tailor_detail},
        {
            "item": "Cover Letter",
            "done": cl_done,
            "detail": "Generated" if cl_done else "Not yet written",
        },
        {"item": "Interview Prep", "done": prep_done, "detail": prep_detail},
        {
            "item": "LinkedIn Profile",
            "done": li_done,
            "detail": "Loaded" if li_done else "Not imported",
        },
    ]

    completed = sum(1 for c in checklist if c["done"])
    return (
        jsonify(
            {
                "posting_id": posting["id"],
                "title": posting["title"],
                "company": posting["company"],
                "checklist": checklist,
                "completion_pct": round(completed / len(checklist) * 100),
            }
        ),
        200,
    )


@agents_bp.route("/api/agents/pipeline/<posting_id>/followup", methods=["POST"])
@require_auth
@limiter.limit(_LLM_LIMIT)
def pipeline_followup(posting_id):
    user_id = g.user_id

    tracker = get_app_tracker()
    result = tracker.generate_followup(posting_id, user_id)
    if "error" in result:
        # 404 is reserved for genuine lookup failures. It tells the caller the
        # resource does not exist -- a different and more damaging claim than
        # "this attempt failed": the client may drop a record that is fine, or
        # retry against a different id, when the LLM was simply unavailable.
        message = result["error"]
        is_lookup_failure = isinstance(message, str) and any(
            phrase in message.lower() for phrase in ("not found", "no such", "does not exist")
        )
        return jsonify(result), (404 if is_lookup_failure else 400)
    return jsonify(result), 200


@agents_bp.route("/api/agents/pipeline/<posting_id>/analyze", methods=["POST"])
@require_auth
@limiter.limit(_LLM_LIMIT)
def pipeline_analyze(posting_id):
    """Analyze performance patterns. posting_id unused but kept for route consistency."""
    user_id = g.user_id

    tracker = get_app_tracker()
    result = tracker.analyze_performance(user_id)
    return jsonify(result), 200
