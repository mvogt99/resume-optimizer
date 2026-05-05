"""Authentication routes — register, login, and approval workflow."""

import os
import re
import threading
import time

from auth import create_token, decode_token, require_auth
from email_service import send_approval_request
from flask import Blueprint, Response, g, jsonify, request
from models_classes import User

auth_bp = Blueprint("auth", __name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# In-memory rate limiting: {ip: [timestamp, ...]}
_LOGIN_ATTEMPTS: dict = {}
_LOGIN_LOCK = threading.Lock()
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_WINDOW_SECONDS = 60

APP_URL = os.environ.get("APP_URL", "http://localhost:5000")
# FRONTEND_URL = where the React app lives (may differ from APP_URL in local dev)
FRONTEND_URL = os.environ.get("FRONTEND_URL", APP_URL)
APP_ENV_NAME = os.environ.get("APP_ENV_NAME", "Development")


@auth_bp.route("/api/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    email = data.get("email", "").strip()
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    if not _EMAIL_RE.match(email):
        return jsonify({"error": "Invalid email format"}), 400

    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    existing_user = User.find_by_email(email)
    if existing_user:
        return jsonify({"error": "User already exists"}), 409

    # Auto-approve admin user
    admin_email = "mvogt99@gmail.com"
    if email == admin_email:
        user = User.create(email, password, role="admin", status="active")
        token = create_token(user.id, email, role="admin")
        return (
            jsonify(
                {
                    "message": "Admin user created successfully",
                    "user_id": str(user.id),
                    "token": token,
                    "role": "admin",
                }
            ),
            201,
        )

    # Create pending user
    user = User.create(email, password, role="user", status="pending")

    # Generate 7-day approval token
    import jwt
    from auth import JWT_SECRET, JWT_ALGORITHM
    now = int(time.time())
    approval_payload = {
        "user_id": user.id,
        "purpose": "approval",
        "exp": now + 7 * 86400,
    }
    approval_token = jwt.encode(approval_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    # Build approval URLs
    approve_url = f"{APP_URL}/api/auth/approve/{approval_token}"
    reject_url = f"{APP_URL}/api/auth/reject/{approval_token}"

    # Send approval email (best effort — never raise)
    send_approval_request(email, approve_url, reject_url, APP_ENV_NAME)

    return (
        jsonify(
            {
                "message": "Registration submitted. Awaiting admin approval.",
                "pending": True,
            }
        ),
        201,
    )


@auth_bp.route("/api/login", methods=["POST"])
def login():
    ip = request.remote_addr or "unknown"
    now = time.time()

    # Check rate limit (only counts failed attempts)
    with _LOGIN_LOCK:
        _LOGIN_ATTEMPTS[ip] = [
            t for t in _LOGIN_ATTEMPTS.get(ip, []) if now - t < _LOGIN_WINDOW_SECONDS
        ]
        if len(_LOGIN_ATTEMPTS[ip]) >= _LOGIN_MAX_ATTEMPTS:
            return jsonify({"error": "Too many login attempts. Try again later."}), 429

    data = request.get_json()
    email = data.get("email", "").strip()
    password = data.get("password")

    user = User.authenticate(email, password)
    if not user:
        # Record the failed attempt
        with _LOGIN_LOCK:
            _LOGIN_ATTEMPTS.setdefault(ip, []).append(now)
        return jsonify({"error": "Invalid credentials"}), 401

    # Check account status
    if user.status == "pending":
        return (
            jsonify({"error": "Your account is pending admin approval."}),
            403,
        )
    if user.status == "disabled":
        return (
            jsonify({"error": "Your account has been suspended."}),
            403,
        )

    # Successful login clears the rate limit window for this IP
    with _LOGIN_LOCK:
        _LOGIN_ATTEMPTS.pop(ip, None)

    token = create_token(user.id, user.email, role=user.role)
    return (
        jsonify(
            {
                "message": "Login successful",
                "user_id": str(user.id),
                "token": token,
                "role": user.role,
            }
        ),
        200,
    )


@auth_bp.route("/api/auth/approve/<token>", methods=["GET"])
def approve_request(token):
    """Approve a pending user registration."""
    try:
        import jwt
        from auth import JWT_SECRET, JWT_ALGORITHM
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

        if payload.get("purpose") != "approval":
            return Response(
                "<html><body style='font-family:sans-serif;text-align:center;padding:40px'>"
                "<h1 style='color:#ef4444'>Invalid Request</h1>"
                "<p>This approval link is invalid or has expired.</p>"
                "</body></html>",
                mimetype="text/html",
                status=400,
            )

        user_id = payload.get("user_id")
        user = User.find_by_id(user_id)
        if not user:
            return Response(
                "<html><body style='font-family:sans-serif;text-align:center;padding:40px'>"
                "<h1 style='color:#6b7280'>Already Processed</h1>"
                "<p>This request has already been handled.</p>"
                "</body></html>",
                mimetype="text/html",
                status=200,
            )

        # Single-use: only act if still pending
        if user.status != "pending":
            return Response(
                "<html><body style='font-family:sans-serif;text-align:center;padding:40px'>"
                "<h1 style='color:#6b7280'>Already Processed</h1>"
                "<p>This request has already been approved or rejected.</p>"
                "</body></html>",
                mimetype="text/html",
                status=200,
            )

        User.update(user_id, status="active")

        return Response(
            "<html><body style='font-family:sans-serif;text-align:center;padding:40px'>"
            "<h1 style='color:#22c55e'>✓ Access Approved</h1>"
            "<p>User account has been activated. They can now log in.</p>"
            "<p><a href='" + FRONTEND_URL + "/login' style='color:#0066cc;'>Return to login</a></p>"
            "</body></html>",
            mimetype="text/html",
            status=200,
        )

    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Approval link error: %s", e)
        return Response(
            "<html><body style='font-family:sans-serif;text-align:center;padding:40px'>"
            "<h1 style='color:#ef4444'>Invalid Link</h1>"
            "<p>This approval link is invalid or has expired.</p>"
            "</body></html>",
            mimetype="text/html",
            status=400,
        )


@auth_bp.route("/api/auth/reject/<token>", methods=["GET"])
def reject_request(token):
    """Reject a pending user registration."""
    try:
        import jwt
        from auth import JWT_SECRET, JWT_ALGORITHM
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

        if payload.get("purpose") != "approval":
            return Response(
                "<html><body style='font-family:sans-serif;text-align:center;padding:40px'>"
                "<h1 style='color:#ef4444'>Invalid Request</h1>"
                "<p>This rejection link is invalid or has expired.</p>"
                "</body></html>",
                mimetype="text/html",
                status=400,
            )

        user_id = payload.get("user_id")
        user = User.find_by_id(user_id)
        if not user:
            return Response(
                "<html><body style='font-family:sans-serif;text-align:center;padding:40px'>"
                "<h1 style='color:#6b7280'>Already Processed</h1>"
                "<p>This request has already been handled.</p>"
                "</body></html>",
                mimetype="text/html",
                status=200,
            )

        # Single-use: only reject if still pending — never delete an approved user
        if user.status != "pending":
            return Response(
                "<html><body style='font-family:sans-serif;text-align:center;padding:40px'>"
                "<h1 style='color:#6b7280'>Already Processed</h1>"
                "<p>This request has already been approved or rejected.</p>"
                "</body></html>",
                mimetype="text/html",
                status=200,
            )

        User.delete(user_id)

        return Response(
            "<html><body style='font-family:sans-serif;text-align:center;padding:40px'>"
            "<h1 style='color:#ef4444'>✗ Request Rejected</h1>"
            "<p>The registration request has been rejected.</p>"
            "</body></html>",
            mimetype="text/html",
            status=200,
        )

    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Rejection link error: %s", e)
        return Response(
            "<html><body style='font-family:sans-serif;text-align:center;padding:40px'>"
            "<h1 style='color:#ef4444'>Invalid Link</h1>"
            "<p>This rejection link is invalid or has expired.</p>"
            "</body></html>",
            mimetype="text/html",
            status=400,
        )


@auth_bp.route("/api/reset-password", methods=["POST"])
@require_auth
def reset_password():
    data = request.get_json() or {}
    old_password = data.get("old_password")
    new_password = data.get("new_password")

    if not old_password or not new_password:
        return (
            jsonify({"error": "Old password and new password are required"}),
            400,
        )

    if len(new_password) < 8:
        return jsonify({"error": "New password must be at least 8 characters"}), 400

    # Get user from token
    user = User.find_by_id(g.user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Verify old password
    from werkzeug.security import check_password_hash
    if not check_password_hash(user.password_hash, old_password):
        return jsonify({"error": "Invalid password"}), 401

    # Update password
    from werkzeug.security import generate_password_hash
    new_hash = generate_password_hash(new_password)
    User.update(g.user_id, password_hash=new_hash)

    return jsonify({"message": "Password reset successfully"}), 200
