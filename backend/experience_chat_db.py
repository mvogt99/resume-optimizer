"""
Database helper functions for ExperienceExtractor sessions and messages.
"""

import json

from models import get_db


def get_session(session_id, user_id=None):
    """Fetch session from DB, optionally filtering by user_id."""
    with get_db() as conn:
        if user_id is not None:
            row = conn.execute(
                "SELECT * FROM experience_sessions WHERE id = ? AND user_id = ?",
                (session_id, user_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM experience_sessions WHERE id = ?", (session_id,)
            ).fetchone()

    if not row:
        return None

    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "employer": row["employer"],
        "client": row["client"],
        "stage": row["stage"],
        "context_json": row["context_json"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "is_finalized": row["is_finalized"],
    }


def get_messages(session_id):
    """Fetch all messages for a session."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, content, created_at FROM experience_messages "
            "WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        )
        rows = cursor.fetchall()
    return [{"role": r[0], "content": r[1], "created_at": r[2]} for r in rows]


def save_message(session_id, role, content):
    """Save a message to the session history."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO experience_messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )
        conn.commit()


_ALLOWED_COLUMNS = {"stage", "context_json", "employer", "client", "is_finalized"}


def update_session(session_id, **kwargs):
    """Update session fields (column allowlist prevents SQL injection)."""
    if not kwargs:
        return

    sets, values = [], []
    for key, val in kwargs.items():
        if key not in _ALLOWED_COLUMNS:
            continue
        sets.append(f"{key} = ?")
        values.append(val)
    if not sets:
        return
    sets.append("updated_at = CURRENT_TIMESTAMP")
    values.append(session_id)
    with get_db() as conn:
        conn.execute(
            f"UPDATE experience_sessions SET {', '.join(sets)} WHERE id = ?",
            values,
        )
        conn.commit()


def get_extracted_experiences(user_id):
    """Get all finalized experiences for a user."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM extracted_experiences WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        )
        rows = cursor.fetchall()

    columns = [
        "id",
        "session_id",
        "user_id",
        "employer",
        "client",
        "title",
        "duration",
        "responsibilities",
        "technologies",
        "accomplishments",
        "challenges",
        "bullet_points",
        "created_at",
    ]
    json_cols = {
        "responsibilities",
        "technologies",
        "accomplishments",
        "challenges",
        "bullet_points",
    }
    return [
        {
            col: (
                json.loads(row[col])
                if col in json_cols and isinstance(row[col], str) and row[col]
                else row[col]
            )
            for col in columns
        }
        for row in rows
    ]
