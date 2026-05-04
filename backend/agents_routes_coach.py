"""Interview Coach routes."""

import logging

from agents import get_interview_coach
from agents.acceptance import MAX_ATTEMPTS, build_failure_teaching, record_acceptance, should_retry, verify
from agents_routes_common import _LLM_LIMIT, _delete_coach_session, _persist_acceptance, agents_bp
from auth import require_auth
from flask import g, jsonify, request

from rate_limit import limiter

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Interview Coach routes
# ──────────────────────────────────────────────


@agents_bp.route("/api/agents/coach/start", methods=["POST"])
@require_auth
@limiter.limit(_LLM_LIMIT)
def coach_start():
    user_id = g.user_id

    data = request.get_json(silent=True) or {}
    posting_id = data.get("posting_id", "")
    persona = data.get("persona", "hiring_manager")
    question_count = int(data.get("question_count", 5))
    question_count = max(1, min(question_count, 15))

    coach = get_interview_coach()
    acceptance = None
    attempts = 0

    for attempt in range(MAX_ATTEMPTS):
        attempts = attempt + 1
        result = coach.start_session(user_id, posting_id, persona, question_count)
        acceptance = verify("interview_coach", result)
        teaching = build_failure_teaching(acceptance, {"posting_id": posting_id}, output=result)
        record_acceptance(result.get("session_id", ""), acceptance, attempt, teaching)
        if not should_retry(acceptance, attempt):
            break
        _delete_coach_session(result.get("session_id", ""))  # L1: clean up orphan
        coach._pending_retry_teaching = teaching  # W1
        logger.warning("[Route/coach] Attempt %d failed — retrying.\n%s", attempt + 1, teaching)

    _persist_acceptance(user_id, "interview_coach", acceptance, attempts)
    result["acceptance"] = acceptance.to_dict() if acceptance else {}  # W5
    result["acceptance_attempts"] = attempts  # W5
    return jsonify(result), 201


@agents_bp.route("/api/agents/coach/answer", methods=["POST"])
@require_auth
@limiter.limit(_LLM_LIMIT)
def coach_answer():
    user_id = g.user_id

    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    answer = data.get("answer", "")
    if not session_id or not answer:
        return jsonify({"error": "session_id and answer are required"}), 400

    coach = get_interview_coach()

    # coach_answer is non-idempotent: process_answer() persists the answer and
    # advances current_question on every call.  No retry — call once only.
    result = coach.process_answer(session_id, answer, user_id=user_id)
    if "error" in result:
        return jsonify(result), 400
    acceptance = verify("coach_answer", result)
    teaching = build_failure_teaching(acceptance, {"session_id": session_id}, output=result)
    record_acceptance(session_id, acceptance, 0, teaching)

    _persist_acceptance(user_id, "interview_coach", acceptance, 1)
    result["acceptance"] = acceptance.to_dict() if acceptance else {}
    result["acceptance_attempts"] = 1
    return jsonify(result), 200


@agents_bp.route("/api/agents/coach/<session_id>", methods=["GET"])
@require_auth
def coach_get_session(session_id):
    user_id = g.user_id

    coach = get_interview_coach()
    result = coach.get_session(session_id, user_id=user_id)
    if not result:
        return jsonify({"error": "Session not found"}), 404
    return jsonify(result), 200


@agents_bp.route("/api/agents/coach/sessions", methods=["GET"])
@require_auth
def coach_list_sessions():
    user_id = g.user_id

    coach = get_interview_coach()
    sessions = coach.list_sessions(user_id)
    return jsonify({"sessions": sessions, "count": len(sessions)}), 200


@agents_bp.route("/api/agents/coach/<session_id>/assessment", methods=["GET"])
@require_auth
def coach_get_assessment(session_id):
    user_id = g.user_id

    coach = get_interview_coach()
    result = coach.get_assessment(session_id, user_id=user_id)
    if not result:
        return jsonify({"error": "Session not found"}), 404
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result), 200


# ──────────────────────────────────────────────
# Agent Enhancements (Phase 13.5) — coach
# ──────────────────────────────────────────────


@agents_bp.route("/api/agents/coach/prep-sheet/<posting_id>", methods=["POST"])
@require_auth
def coach_prep_sheet(posting_id):
    """Generate comprehensive interview prep sheet."""
    coach = get_interview_coach()
    try:
        sheet = coach.generate_prep_sheet(g.user_id, posting_id)
        return jsonify(sheet), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
