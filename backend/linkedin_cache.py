"""Thread-safe per-user LinkedIn profile cache with SQLite persistence."""

import contextlib
import json
import threading

from models import get_db

_lock = threading.Lock()
_profiles = {}  # {user_id: {"profile": {...}, "raw": {...}}}


def _persist(user_id, profile, raw):
    """Write-through to SQLite."""
    with contextlib.suppress(Exception), get_db() as conn:
        conn.execute(
            "INSERT INTO linkedin_profiles (user_id, profile_json, raw_json, updated_at) "
            "VALUES (?, ?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "profile_json=excluded.profile_json, raw_json=excluded.raw_json, "
            "updated_at=CURRENT_TIMESTAMP",
            (int(user_id), json.dumps(profile or {}), json.dumps(raw or {})),
        )
        conn.commit()


def _load_all():
    """Load all cached profiles from SQLite on startup."""
    with contextlib.suppress(Exception), get_db() as conn:
        rows = conn.execute(
            "SELECT user_id, profile_json, raw_json FROM linkedin_profiles"
        ).fetchall()
        for row in rows:
            uid = row["user_id"]
            _profiles[uid] = {
                "profile": json.loads(row["profile_json"] or "{}"),
                "raw": json.loads(row["raw_json"] or "{}"),
            }


def set_profile(user_id, profile, raw):
    """Store both processed and raw LinkedIn profile for a user."""
    uid = int(user_id)
    with _lock:
        _profiles[uid] = {"profile": profile, "raw": raw}
    _persist(uid, profile, raw)


def get_profile(user_id):
    """Get processed LinkedIn profile (skills as strings) for a user."""
    with _lock:
        entry = _profiles.get(int(user_id))
        return entry["profile"] if entry else None


def get_raw(user_id):
    """Get raw LinkedIn profile (skills as dicts with endorsement counts) for a user."""
    with _lock:
        entry = _profiles.get(int(user_id))
        return entry["raw"] if entry else None


def has_profile(user_id):
    """Check if a user has a cached LinkedIn profile."""
    with _lock:
        return int(user_id) in _profiles


# Load persisted profiles on import
_load_all()
