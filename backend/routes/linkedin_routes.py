"""LinkedIn profile update generator routes (Phase 13.3)."""

from auth import require_auth
from flask import Blueprint, g, jsonify, request
from linkedin_generator import (
    compare_current_vs_suggested,
    generate_profile_update,
    get_updates,
    update_suggestion,
)

linkedin_bp = Blueprint("linkedin_gen", __name__)


@linkedin_bp.route("/api/linkedin/generate-update", methods=["POST"])
@require_auth
def generate_update():
    result = generate_profile_update(g.user_id)
    return jsonify(result), 200


@linkedin_bp.route("/api/linkedin/updates", methods=["GET"])
@require_auth
def list_updates():
    updates = get_updates(g.user_id)
    return jsonify({"updates": updates, "count": len(updates)}), 200


@linkedin_bp.route("/api/linkedin/updates/<int:update_id>", methods=["PUT"])
@require_auth
def update_section(update_id):
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    content = data.get("suggested_content")
    if not status and content is None:
        return jsonify({"error": "status or suggested_content required"}), 400
    if status and status not in ("pending", "applied", "rejected"):
        return jsonify({"error": "status must be pending, applied, or rejected"}), 400
    updated = update_suggestion(update_id, g.user_id, status=status, suggested_content=content)
    if not updated:
        return jsonify({"error": "Update not found"}), 404
    return jsonify({"message": "Updated"}), 200


@linkedin_bp.route("/api/linkedin/compare", methods=["GET"])
@require_auth
def compare():
    result = compare_current_vs_suggested(g.user_id)
    return jsonify(result), 200
