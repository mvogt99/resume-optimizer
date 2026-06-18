"""JWT authentication module for Resume Optimizer."""

import functools
import logging
import os
import secrets

import jwt
from flask import g, jsonify, request

logger = logging.getLogger(__name__)

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.environ.get("JWT_EXPIRY_HOURS", "24"))

_secret_file = os.path.join(os.path.dirname(__file__), ".jwt_secret")


def _load_or_generate_secret():
    """Load JWT secret from file, or generate and persist one."""
    if os.path.exists(_secret_file):
        with open(_secret_file, "r") as f:
            return f.read().strip()
    secret = secrets.token_hex(32)
    with open(_secret_file, "w") as f:
        f.write(secret)
    return secret


JWT_SECRET = os.environ.get("JWT_SECRET") or _load_or_generate_secret()


def create_token(user_id: int, email: str, role: str = "user") -> str:
    """Create a JWT token with user_id, email, role, iat, and exp claims."""
    import time

    now = int(time.time())
    payload = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + JWT_EXPIRY_HOURS * 3600,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token.

    Raises jwt.ExpiredSignatureError or jwt.InvalidTokenError.
    """
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


def require_auth(f):
    """Decorator: extract Bearer token or legacy user-id header -> g.user_id and g.user_role.

    Sets g.user_id as an int and g.user_role as a string. Returns 401 if neither auth method present.
    """

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                payload = decode_token(auth_header[7:])
                g.user_id = payload["user_id"]
                g.user_role = payload.get("role", "user")
            except jwt.ExpiredSignatureError:
                return jsonify({"error": "Token expired"}), 401
            except (jwt.InvalidTokenError, KeyError):
                return jsonify({"error": "Invalid token"}), 401
        else:
            # Legacy fallback: user-id header
            uid = request.headers.get("user-id")
            if uid:
                try:
                    g.user_id = int(uid)
                    g.user_role = "user"  # Default role for legacy auth
                except (ValueError, TypeError):
                    return jsonify({"error": "Invalid user-id"}), 401
            else:
                return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)

    return wrapper


def require_admin(f):
    """Decorator: require_auth + admin role check.

    Returns 403 if user is not an admin.
    """

    @require_auth
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if g.user_role != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)

    return wrapper
