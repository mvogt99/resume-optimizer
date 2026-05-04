"""Deep profile staleness detection — Phase P2-A.

Tracks whether the deep profile is stale relative to underlying data sources.
Source hash encodes: approved project count, finalized experience count,
journey event count, narrative count, LinkedIn import timestamp.
"""

import hashlib
import json
import logging

from models import get_db

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Source count helpers
# ---------------------------------------------------------------------------


def _get_source_counts(user_id: int) -> dict:
    """Return current source data counts for user."""
    with get_db() as conn:
        counts = {}
        try:
            counts["projects"] = conn.execute(
                "SELECT COUNT(*) FROM client_projects WHERE user_id=? AND approved=1",
                (user_id,),
            ).fetchone()[0]
        except Exception:
            counts["projects"] = 0

        try:
            counts["experiences"] = conn.execute(
                "SELECT COUNT(*) FROM experience_sessions "
                "WHERE user_id=? AND status='finalized'",
                (user_id,),
            ).fetchone()[0]
        except Exception:
            counts["experiences"] = 0

        try:
            counts["events"] = conn.execute(
                "SELECT COUNT(*) FROM journey_events WHERE user_id=?",
                (user_id,),
            ).fetchone()[0]
        except Exception:
            counts["events"] = 0

        try:
            counts["narratives"] = conn.execute(
                "SELECT COUNT(*) FROM journey_narratives "
                "WHERE user_id=? AND superseded_at IS NULL",
                (user_id,),
            ).fetchone()[0]
        except Exception:
            counts["narratives"] = 0

        try:
            row = conn.execute(
                "SELECT MAX(updated_at) FROM users WHERE id=?",
                (user_id,),
            ).fetchone()
            counts["linkedin_ts"] = row[0] or ""
        except Exception:
            counts["linkedin_ts"] = ""

    return counts


def _hash_counts(counts: dict) -> str:
    """SHA256 of deterministic JSON-serialised source counts."""
    payload = json.dumps(counts, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def compute_source_hash(user_id: int) -> str:
    """Compute current source hash for user."""
    counts = _get_source_counts(user_id)
    return _hash_counts(counts)


# ---------------------------------------------------------------------------
# Staleness API
# ---------------------------------------------------------------------------


def check_staleness(user_id: int) -> dict:
    """Compare current source hash to stored hash. Return staleness info dict.

    Keys: is_stale (bool), current_hash (str), stored_hash (str),
          stale_reason (str), source_counts (dict).
    """
    counts = _get_source_counts(user_id)
    current_hash = _hash_counts(counts)

    with get_db() as conn:
        row = conn.execute(
            "SELECT source_hash, is_stale, stale_reason, last_checked_at "
            "FROM deep_profiles WHERE user_id=? ORDER BY updated_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()

    if not row:
        return {
            "is_stale": False,
            "current_hash": current_hash,
            "stored_hash": None,
            "stale_reason": "",
            "source_counts": counts,
        }

    stored_hash = row["source_hash"] or ""
    is_stale = stored_hash != "" and current_hash != stored_hash

    # Persist check result
    _update_staleness_flags(user_id, current_hash, is_stale, row)

    return {
        "is_stale": is_stale,
        "current_hash": current_hash,
        "stored_hash": stored_hash,
        "stale_reason": row["stale_reason"] or "",
        "source_counts": counts,
    }


def _update_staleness_flags(user_id: int, current_hash: str, is_stale: bool, row) -> None:
    """Update last_checked_at and is_stale on the profile row."""
    with get_db() as conn:
        try:
            conn.execute(
                "UPDATE deep_profiles SET last_checked_at=CURRENT_TIMESTAMP, "
                "is_stale=? WHERE user_id=? AND source_hash=?",
                (1 if is_stale else 0, user_id, row["source_hash"] or ""),
            )
            conn.commit()
        except Exception:
            pass


def mark_profile_stale(user_id: int, reason: str) -> None:
    """Mark a user's deep profile as stale (called after data changes)."""
    with get_db() as conn:
        try:
            conn.execute(
                "UPDATE deep_profiles SET is_stale=1, stale_reason=?, "
                "last_checked_at=CURRENT_TIMESTAMP "
                "WHERE user_id=?",
                (reason, user_id),
            )
            conn.commit()
        except Exception as e:
            logger.warning("mark_profile_stale failed for user %s: %s", user_id, e)


def clear_staleness(user_id: int, new_hash: str) -> None:
    """Clear stale flag and update source hash after successful rebuild."""
    with get_db() as conn:
        try:
            conn.execute(
                "UPDATE deep_profiles SET source_hash=?, is_stale=0, stale_reason='', "
                "last_checked_at=CURRENT_TIMESTAMP "
                "WHERE user_id=? ORDER BY updated_at DESC LIMIT 1",
                (new_hash, user_id),
            )
            conn.commit()
        except Exception as e:
            logger.warning("clear_staleness failed for user %s: %s", user_id, e)


def get_profile_status(user_id: int) -> dict | None:
    """Full status dict for /api/deep-profile/status.

    Returns None if no profile exists.
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, source_hash, is_stale, stale_reason, last_checked_at, "
            "updated_at, created_at FROM deep_profiles "
            "WHERE user_id=? ORDER BY updated_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()

    if not row:
        return None

    counts = _get_source_counts(user_id)
    current_hash = _hash_counts(counts)
    stored_hash = row["source_hash"] or ""
    is_stale = stored_hash != "" and current_hash != stored_hash

    return {
        "is_stale": is_stale,
        "stale_reason": row["stale_reason"] or "",
        "last_built_at": row["updated_at"],
        "last_checked_at": row["last_checked_at"],
        "source_counts": counts,
        "current_hash": current_hash,
        "stored_hash": stored_hash,
    }
