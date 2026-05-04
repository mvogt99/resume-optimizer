"""Phase 15: Routes for new features — version diff, portfolio, recommendations,
campaign analytics, suggestions, architecture analysis, orchestrator."""

import logging

from architecture_analyzer import analyze_architecture, get_architecture_summary
from auth import require_auth
from campaign_analytics import get_campaign_comparison, get_cross_campaign_analytics
from campaign_suggestor import get_uncovered_topics, suggest_campaigns
from flask import Blueprint, g, jsonify, request
from portfolio_generator import export_portfolio_text, generate_portfolio
from recommendation_drafter import (
    delete_draft,
    draft_recommendation_request,
    list_drafts,
    update_draft,
)
from version_diff import diff_versions, list_versions_for_diff

logger = logging.getLogger(__name__)

new_features_bp = Blueprint("new_features", __name__)


# --- Resume Version Diffing ---


@new_features_bp.route("/api/versions/for-diff", methods=["GET"])
@require_auth
def versions_for_diff():
    try:
        return jsonify(list_versions_for_diff(g.user_id)), 200
    except Exception as e:
        logger.exception("Unhandled error in route: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@new_features_bp.route("/api/versions/diff", methods=["POST"])
@require_auth
def diff_versions_route():
    try:
        data = request.get_json() or {}
        return jsonify(diff_versions(g.user_id, data.get("version_a"), data.get("version_b"))), 200
    except Exception as e:
        logger.exception("Unhandled error in route: %s", e)
        return jsonify({"error": "Internal server error"}), 500


# --- Portfolio ---


@new_features_bp.route("/api/portfolio/generate", methods=["POST"])
@require_auth
def generate_portfolio_route():
    try:
        return jsonify(generate_portfolio(g.user_id)), 200
    except Exception as e:
        logger.exception("Unhandled error in route: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@new_features_bp.route("/api/portfolio/export", methods=["GET"])
@require_auth
def export_portfolio_route():
    try:
        return jsonify(export_portfolio_text(g.user_id)), 200
    except Exception as e:
        logger.exception("Unhandled error in route: %s", e)
        return jsonify({"error": "Internal server error"}), 500


# --- Recommendation Drafts ---


@new_features_bp.route("/api/recommendations/draft", methods=["POST"])
@require_auth
def draft_recommendation():
    try:
        data = request.get_json() or {}
        result = draft_recommendation_request(
            g.user_id,
            data.get("target_name", ""),
            data.get("relationship", ""),
            data.get("shared_projects", ""),
            data.get("specific_skills", ""),
        )
        return jsonify(result), 200
    except Exception as e:
        logger.exception("Unhandled error in route: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@new_features_bp.route("/api/recommendations/drafts", methods=["GET"])
@require_auth
def list_recommendation_drafts():
    try:
        return jsonify(list_drafts(g.user_id)), 200
    except Exception as e:
        logger.exception("Unhandled error in route: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@new_features_bp.route("/api/recommendations/drafts/<draft_id>", methods=["PUT"])
@require_auth
def update_recommendation_draft(draft_id):
    try:
        data = request.get_json() or {}
        return jsonify(update_draft(draft_id, g.user_id, data.get("text", ""))), 200
    except Exception as e:
        logger.exception("Unhandled error in route: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@new_features_bp.route("/api/recommendations/drafts/<draft_id>", methods=["DELETE"])
@require_auth
def delete_recommendation_draft(draft_id):
    try:
        return jsonify(delete_draft(draft_id, g.user_id)), 200
    except Exception as e:
        logger.exception("Unhandled error in route: %s", e)
        return jsonify({"error": "Internal server error"}), 500


# --- Campaign Analytics ---


@new_features_bp.route("/api/campaigns/cross-analytics", methods=["GET"])
@require_auth
def cross_campaign_analytics():
    try:
        return jsonify(get_cross_campaign_analytics(g.user_id)), 200
    except Exception as e:
        logger.exception("Unhandled error in route: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@new_features_bp.route("/api/campaigns/comparison", methods=["GET"])
@require_auth
def campaign_comparison():
    try:
        return jsonify(get_campaign_comparison(g.user_id)), 200
    except Exception as e:
        logger.exception("Unhandled error in route: %s", e)
        return jsonify({"error": "Internal server error"}), 500


# --- Campaign Suggestions ---


@new_features_bp.route("/api/campaigns/suggestions", methods=["GET"])
@require_auth
def campaign_suggestions():
    try:
        max_s = int(request.args.get("max_suggestions", 5))
        return jsonify(suggest_campaigns(g.user_id, max_s)), 200
    except Exception as e:
        logger.exception("Unhandled error in route: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@new_features_bp.route("/api/campaigns/uncovered-topics", methods=["GET"])
@require_auth
def uncovered_topics():
    try:
        return jsonify(get_uncovered_topics(g.user_id)), 200
    except Exception as e:
        logger.exception("Unhandled error in route: %s", e)
        return jsonify({"error": "Internal server error"}), 500


# --- Architecture Analysis ---


@new_features_bp.route("/api/architecture/analyze", methods=["POST"])
@require_auth
def analyze_architecture_route():
    try:
        data = request.get_json() or {}
        return jsonify(analyze_architecture(g.user_id, data.get("project_id"))), 200
    except Exception as e:
        logger.exception("Unhandled error in route: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@new_features_bp.route("/api/architecture/summary", methods=["GET"])
@require_auth
def architecture_summary():
    try:
        return jsonify(get_architecture_summary(g.user_id)), 200
    except Exception as e:
        logger.exception("Unhandled error in route: %s", e)
        return jsonify({"error": "Internal server error"}), 500


# --- Orchestrator ---


@new_features_bp.route("/api/agents/orchestrate/apply", methods=["POST"])
@require_auth
def orchestrate_apply():
    try:
        from agents import get_orchestrator

        data = request.get_json() or {}
        result = get_orchestrator().full_application_pipeline(g.user_id, data.get("posting_id"))
        return jsonify(result), 200
    except Exception as e:
        logger.exception("Unhandled error in route: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@new_features_bp.route("/api/agents/orchestrate/career-dive", methods=["POST"])
@require_auth
def orchestrate_career_dive():
    try:
        from agents import get_orchestrator

        data = request.get_json() or {}
        result = get_orchestrator().career_deep_dive(g.user_id, data.get("posting_id"))
        return jsonify(result), 200
    except Exception as e:
        logger.exception("Unhandled error in route: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@new_features_bp.route("/api/agents/orchestrate/status", methods=["GET"])
@require_auth
def orchestrate_status():
    try:
        from agents import get_orchestrator

        return jsonify(get_orchestrator().get_workflow_status(g.user_id)), 200
    except Exception as e:
        logger.exception("Unhandled error in route: %s", e)
        return jsonify({"error": "Internal server error"}), 500
