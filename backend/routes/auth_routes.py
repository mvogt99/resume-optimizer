"""Authentication routes — register and login."""

import re
import threading
import time

from auth import create_token
from flask import Blueprint, jsonify, request
from models import User

auth_bp = Blueprint("auth", __name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# In-memory rate limiting: {ip: [timestamp, ...]}
_LOGIN_ATTEMPTS: dict = {}
_LOGIN_LOCK = threading.Lock()
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_WINDOW_SECONDS = 60


@auth_bp.route("/api/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    email = data.get("email")
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

    user = User.create(email, password)
    token = create_token(user.id, email)
    return (
        jsonify(
            {
                "message": "User created successfully",
                "user_id": str(user.id),
                "token": token,
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
    email = data.get("email")
    password = data.get("password")

    user = User.authenticate(email, password)
    if user:
        # Successful login clears the rate limit window for this IP
        with _LOGIN_LOCK:
            _LOGIN_ATTEMPTS.pop(ip, None)
        token = create_token(user.id, user.email)
        return (
            jsonify(
                {
                    "message": "Login successful",
                    "user_id": str(user.id),
                    "token": token,
                }
            ),
            200,
        )
    else:
        # Record the failed attempt
        with _LOGIN_LOCK:
            _LOGIN_ATTEMPTS.setdefault(ip, []).append(now)
        return jsonify({"error": "Invalid credentials"}), 401


@auth_bp.route("/api/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json() or {}
    email = data.get("email")
    old_password = data.get("old_password")
    new_password = data.get("new_password")

    if not email or not old_password or not new_password:
        return jsonify({"error": "Email, old password, and new password are required"}), 400

    if len(new_password) < 8:
        return jsonify({"error": "New password must be at least 8 characters"}), 400

    # Authenticate with old password
    user = User.authenticate(email, old_password)
    if not user:
        return jsonify({"error": "Invalid email or password"}), 401

    # Update password
    from werkzeug.security import generate_password_hash
    import sqlite3

    db_path = "database.db"
    password_hash = generate_password_hash(new_password)

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user.id))
        conn.commit()
        conn.close()

        return jsonify({"message": "Password reset successfully"}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to reset password: {str(e)}"}), 500
