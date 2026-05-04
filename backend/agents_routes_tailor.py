"""Resume Tailor and Cover Letter routes."""

import logging

from agents import get_cover_letter, get_resume_tailor
from agents.acceptance import MAX_ATTEMPTS, build_failure_teaching, record_acceptance, should_retry, verify
from agents_routes_common import _LLM_LIMIT, _persist_acceptance, agents_bp
from auth import require_auth
from flask import g, jsonify, request

from rate_limit import limiter

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Resume Tailor routes
# ──────────────────────────────────────────────


@agents_bp.route("/api/agents/tailor/<posting_id>", methods=["POST"])
@require_auth
@limiter.limit(_LLM_LIMIT)
def tailor_resume(posting_id):
    user_id = g.user_id

    tailor = get_resume_tailor()
    acceptance = None
    attempts = 0

    for attempt in range(MAX_ATTEMPTS):
        attempts = attempt + 1
        result = tailor.tailor_for_posting(user_id, posting_id)
        if "error" in result:
            return jsonify(result), 400
        acceptance = verify("resume_tailor", result)
        ctx = {"posting_id": posting_id, "user_id": user_id}
        teaching = build_failure_teaching(acceptance, ctx, output=result)
        record_acceptance(result.get("version_id", ""), acceptance, attempt, teaching)
        if not should_retry(acceptance, attempt):
            break
        tailor._pending_retry_teaching = teaching  # W1: feed teaching into next LLM call
        logger.warning("[Route/tailor] Attempt %d failed — retrying.\n%s", attempt + 1, teaching)

    _persist_acceptance(user_id, "resume_tailor", acceptance, attempts)
    result["acceptance"] = acceptance.to_dict() if acceptance else {}  # W5
    result["acceptance_attempts"] = attempts  # W5

    # CT-10: Run resume effectiveness audit asynchronously (non-blocking)
    try:
        from resume_effectiveness_audit import run_effectiveness_audit
        import asyncio

        asyncio.run(run_effectiveness_audit(user_id))
    except Exception as e:
        logger.debug("[CT-10] Resume effectiveness audit failed (non-blocking): %s", e)

    return jsonify(result), 200


@agents_bp.route("/api/agents/tailor/<posting_id>", methods=["GET"])
@require_auth
def get_tailored_resume(posting_id):
    user_id = g.user_id

    tailor = get_resume_tailor()
    result = tailor.get_tailored(posting_id, user_id=user_id)
    if not result:
        return jsonify({"error": "No tailored resume found for this posting"}), 404
    return jsonify(result), 200


# ──────────────────────────────────────────────
# Cover Letter routes
# ──────────────────────────────────────────────


@agents_bp.route("/api/agents/cover-letter/<posting_id>", methods=["POST"])
@require_auth
@limiter.limit(_LLM_LIMIT)
def generate_cover_letter(posting_id):
    user_id = g.user_id

    agent = get_cover_letter()
    acceptance = None
    attempts = 0

    for attempt in range(MAX_ATTEMPTS):
        attempts = attempt + 1
        result = agent.generate(user_id, posting_id)
        if "error" in result:
            return jsonify(result), 400
        acceptance = verify("cover_letter", result)
        teaching = build_failure_teaching(acceptance, {"posting_id": posting_id}, output=result)
        record_acceptance(result.get("id", ""), acceptance, attempt, teaching)
        if not should_retry(acceptance, attempt):
            break
        agent._pending_retry_teaching = teaching  # W1
        logger.warning("[Route/cover] Attempt %d failed — retrying.\n%s", attempt + 1, teaching)

    _persist_acceptance(user_id, "cover_letter", acceptance, attempts)
    result["acceptance"] = acceptance.to_dict() if acceptance else {}  # W5
    result["acceptance_attempts"] = attempts  # W5
    return jsonify(result), 201


@agents_bp.route("/api/agents/cover-letter/<posting_id>", methods=["GET"])
@require_auth
def get_cover_letter_for_posting(posting_id):
    user_id = g.user_id

    agent = get_cover_letter()
    result = agent.get_for_posting(user_id, posting_id)
    if not result:
        return jsonify({"error": "No cover letter found for this posting"}), 404
    return jsonify(result), 200


@agents_bp.route("/api/agents/cover-letters/<letter_id>", methods=["GET"])
@require_auth
def get_cover_letter_by_id(letter_id):
    user_id = g.user_id

    agent = get_cover_letter()
    result = agent.get_letter(letter_id, user_id=user_id)
    if not result:
        return jsonify({"error": "Cover letter not found"}), 404
    return jsonify(result), 200


@agents_bp.route("/api/agents/cover-letters/<letter_id>", methods=["PUT"])
@require_auth
def update_cover_letter(letter_id):
    user_id = g.user_id

    data = request.get_json(silent=True) or {}
    agent = get_cover_letter()
    result = agent.update(letter_id, data, user_id=user_id)
    if not result:
        return jsonify({"error": "No valid fields to update"}), 400
    return jsonify(result), 200


@agents_bp.route("/api/agents/cover-letters/<letter_id>", methods=["DELETE"])
@require_auth
def delete_cover_letter(letter_id):
    user_id = g.user_id

    agent = get_cover_letter()
    agent.delete(letter_id, user_id=user_id)
    return jsonify({"message": "Cover letter deleted"}), 200


@agents_bp.route("/api/agents/cover-letters/<letter_id>/regenerate", methods=["POST"])
@require_auth
@limiter.limit(_LLM_LIMIT)
def regenerate_cover_letter(letter_id):
    user_id = g.user_id

    data = request.get_json(silent=True) or {}
    feedback = data.get("feedback", "")
    agent = get_cover_letter()
    acceptance = None
    attempts = 0

    for attempt in range(MAX_ATTEMPTS):
        attempts = attempt + 1
        result = agent.regenerate(user_id, letter_id, feedback)
        if "error" in result:
            return jsonify(result), 400
        acceptance = verify("cover_letter_regen", result)
        teaching = build_failure_teaching(acceptance, {"letter_id": letter_id}, output=result)
        record_acceptance(result.get("id", letter_id), acceptance, attempt, teaching)
        if not should_retry(acceptance, attempt):
            break
        agent._pending_retry_teaching = teaching  # W1
        logger.warning(
            "[Route/regen] Attempt %d failed — retrying.\n%s", attempt + 1, teaching
        )

    _persist_acceptance(user_id, "cover_letter", acceptance, attempts)
    result["acceptance"] = acceptance.to_dict() if acceptance else {}
    result["acceptance_attempts"] = attempts
    return jsonify(result), 200
