"""Rate limiter instance — shared across app and route modules.

Extracted to its own module to avoid circular imports between app.py
and agents_routes_*.py.
"""

from flask import g, request
from flask_limiter import Limiter


def _rate_limit_key():
    """Return user_id for authenticated requests, remote addr as fallback."""
    user_id = getattr(g, "user_id", None)
    if user_id is not None:
        return str(user_id)
    return request.remote_addr


limiter = Limiter(
    key_func=_rate_limit_key,
    storage_uri="memory://",
    default_limits=[],
)
