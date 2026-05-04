"""DB helpers for ATS improvement sessions — extracted from ats_improvement_chat.py."""

import json

from models import get_db

_ALLOWED_COLUMNS = {"stage", "context_json", "is_finalized", "improvement_focus", "optimized_resume_text"}


def init_ats_tables() -> None:
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS ats_improvement_sessions (
                id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, resume_id TEXT,
                job_desc_text TEXT, original_resume_text TEXT, optimized_resume_text TEXT,
                score_json TEXT DEFAULT '{}', stage TEXT DEFAULT 'diagnose',
                improvement_focus TEXT DEFAULT '', pending_suggestions_json TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_finalized INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS ats_improvement_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
                role TEXT NOT NULL, content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );""")


def get_session(session_id: str, user_id=None) -> dict | None:
    with get_db() as conn:
        q = "SELECT * FROM ats_improvement_sessions WHERE id = ?"
        params = [session_id]
        if user_id is not None:
            q += " AND user_id = ?"
            params.append(user_id)
        row = conn.execute(q, params).fetchone()
    return dict(row) if row else None


def get_messages(session_id: str) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT role, content FROM ats_improvement_messages "
            "WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def save_message(session_id: str, role: str, content: str) -> None:
    with get_db() as conn:
        conn.execute(
            "INSERT INTO ats_improvement_messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )
        conn.commit()


def update_session(session_id: str, **fields) -> None:
    if not fields:
        return
    sets, vals = [], []
    for k, v in fields.items():
        if k in _ALLOWED_COLUMNS:
            sets.append(f"{k} = ?")
            vals.append(v)
    if not sets:
        return
    sets.append("updated_at = CURRENT_TIMESTAMP")
    vals.append(session_id)
    with get_db() as conn:
        conn.execute(
            f"UPDATE ats_improvement_sessions SET {', '.join(sets)} WHERE id = ?", vals
        )
        conn.commit()


def create_session(session_id: str, user_id: int, resume_id, score_data: dict) -> None:
    with get_db() as conn:
        conn.execute(
            "INSERT INTO ats_improvement_sessions "
            "(id, user_id, resume_id, job_desc_text, original_resume_text, "
            "optimized_resume_text, score_json, stage) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'diagnose')",
            (
                session_id, user_id, resume_id,
                score_data.get("job_desc_text", ""),
                score_data.get("original_text", ""),
                score_data.get("optimized_text", ""),
                json.dumps(score_data),
            ),
        )
        conn.commit()
