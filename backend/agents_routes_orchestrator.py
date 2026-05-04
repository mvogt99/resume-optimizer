"""Application Orchestrator and Feedback routes."""

import logging

from application_orchestrator import (
    apply_to_job,
    get_bundle,
    get_feedback,
    get_insights,
    record_outcome,
)
from agents_routes_common import agents_bp
from auth import require_auth
from feedback_analyzer import analyze_outcomes
from flask import g, jsonify, request

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Application Orchestrator (Phase 13.3)
# ──────────────────────────────────────────────


@agents_bp.route("/api/agents/apply", methods=["POST"])
@require_auth
def orchestrate_apply():
    """One-click apply: tailor resume + generate cover letter + pipeline move."""
    data = request.get_json(silent=True) or {}
    posting_id = data.get("posting_id")
    template_id = data.get("template_id")
    if not posting_id:
        return jsonify({"error": "posting_id is required"}), 400

    try:
        bundle = apply_to_job(g.user_id, posting_id, template_id=template_id)
        return jsonify(bundle), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@agents_bp.route("/api/agents/apply/<posting_id>/bundle", methods=["GET"])
@require_auth
def get_application_bundle(posting_id):
    """Get previously generated application bundle."""
    bundle = get_bundle(g.user_id, posting_id)
    if not bundle:
        return jsonify({"error": "No bundle found for this posting"}), 404
    return jsonify(bundle), 200


@agents_bp.route("/api/agents/feedback", methods=["POST"])
@require_auth
def record_feedback():
    """Record application outcome."""
    data = request.get_json(silent=True) or {}
    posting_id = data.get("posting_id", "")
    outcome = data.get("outcome", "")
    notes = data.get("notes", "")

    if not outcome:
        return jsonify({"error": "outcome is required"}), 400

    valid_outcomes = (
        "interview",
        "rejected",
        "offer",
        "ghosted",
        "no_response",
        "withdrawn",
    )
    if outcome not in valid_outcomes:
        return jsonify({"error": f"outcome must be one of: {valid_outcomes}"}), 400

    fid = record_outcome(g.user_id, posting_id, outcome, notes)
    return jsonify({"id": fid, "message": "Feedback recorded"}), 201


@agents_bp.route("/api/agents/feedback", methods=["GET"])
@require_auth
def list_feedback():
    """List application outcomes."""
    items = get_feedback(g.user_id)
    return jsonify({"feedback": items, "count": len(items)}), 200


@agents_bp.route("/api/agents/feedback/insights", methods=["GET"])
@require_auth
def feedback_insights():
    """Analyze application outcomes for patterns."""
    insights = get_insights(g.user_id)

    # Enrich with detailed feedback analysis (Phase 17.05)
    try:
        analysis = analyze_outcomes(g.user_id)
        insights["skills_correlated_with_rejection"] = analysis.get(
            "skills_correlated_with_rejection", []
        )
        insights["skills_correlated_with_success"] = analysis.get(
            "skills_correlated_with_success", []
        )
        insights["score_vs_outcome"] = analysis.get("score_vs_outcome", {})
        insights["role_performance"] = analysis.get("role_performance", [])
        insights["detailed_insights"] = analysis.get("actionable_insights", [])
    except Exception:
        pass

    return jsonify(insights), 200


@agents_bp.route("/api/agents/feedback/analysis", methods=["GET"])
@require_auth
def feedback_analysis():
    """Detailed feedback analysis: skill correlations, score thresholds, role performance."""
    analysis = analyze_outcomes(g.user_id)
    return jsonify(analysis), 200
