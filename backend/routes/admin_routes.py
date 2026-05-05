"""Admin routes for user management."""

from auth import require_admin
from flask import Blueprint, g, jsonify, request
from models_classes import User

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/api/admin/users", methods=["GET"])
@require_admin
def list_users():
    """List all users with pagination."""
    limit = request.args.get("limit", 200, type=int)
    offset = request.args.get("offset", 0, type=int)

    users = User.list_all(limit=limit, offset=offset)
    return jsonify([
        {
            "id": u.id,
            "email": u.email,
            "role": u.role,
            "status": u.status,
            "created_at": str(u.created_at) if u.created_at else None,
        }
        for u in users
    ]), 200


@admin_bp.route("/api/admin/users", methods=["POST"])
@require_admin
def create_user():
    """Create a new user as admin."""
    data = request.get_json() or {}
    email = data.get("email", "").strip()
    role = data.get("role", "user")

    if not email:
        return jsonify({"error": "Email is required"}), 400

    if role not in ("admin", "user"):
        return jsonify({"error": "Invalid role"}), 400

    existing = User.find_by_email(email)
    if existing:
        return jsonify({"error": "User already exists"}), 409

    # Create with auto-set password
    user = User.create(email, "password", role=role, status="active")
    return jsonify({
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "status": user.status,
    }), 201


@admin_bp.route("/api/admin/users/<int:user_id>", methods=["PATCH"])
@require_admin
def update_user(user_id):
    """Update a user's role or status."""
    # Prevent self-modification
    if user_id == g.user_id:
        return jsonify({"error": "Cannot modify your own account"}), 403

    user = User.find_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json() or {}
    updates = {}

    if "role" in data:
        role = data.get("role")
        if role not in ("admin", "user"):
            return jsonify({"error": "Invalid role"}), 400
        updates["role"] = role

    if "status" in data:
        status = data.get("status")
        if status not in ("active", "pending", "disabled"):
            return jsonify({"error": "Invalid status"}), 400
        updates["status"] = status

    if updates:
        User.update(user_id, **updates)

    # Refresh and return
    updated_user = User.find_by_id(user_id)
    return jsonify({
        "id": updated_user.id,
        "email": updated_user.email,
        "role": updated_user.role,
        "status": updated_user.status,
    }), 200


@admin_bp.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
@require_admin
def delete_user(user_id):
    """Delete a user."""
    # Prevent self-deletion
    if user_id == g.user_id:
        return jsonify({"error": "Cannot delete your own account"}), 403

    user = User.find_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    User.delete(user_id)
    return jsonify({"message": "User deleted"}), 200
