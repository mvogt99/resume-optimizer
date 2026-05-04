"""Chat history export endpoint — generic across all AI interview session types."""

import logging
from datetime import datetime

from auth import require_auth
from flask import Blueprint, g, jsonify, request
from models import get_db

logger = logging.getLogger(__name__)

chat_history_bp = Blueprint("chat_history", __name__)

# Maps session_type → (session_table, messages_table, session_owner_col)
_SESSION_MAP = {
    "ats_improve": ("ats_improvement_sessions", "ats_improvement_messages", "user_id"),
    "experience": ("experience_sessions", "experience_messages", "user_id"),
    "campaign": ("campaign_sessions", "campaign_messages", "user_id"),
    "resume_interview": ("resume_interview_sessions", "resume_interview_messages", "user_id"),
    "builder_interview": ("builder_interview_sessions", "builder_interview_messages", "user_id"),
    "interview_coach": ("interview_coach_sessions", "interview_coach_messages", "user_id"),
}

# Human-readable labels for each session type
_SESSION_LABELS = {
    "ats_improve": "ATS Improvement",
    "experience": "Experience Extraction",
    "campaign": "Campaign Planning",
    "resume_interview": "Resume Interview",
    "builder_interview": "Builder Interview",
    "interview_coach": "Interview Coach",
}


@chat_history_bp.route("/api/chat-history/<session_type>/<session_id>", methods=["GET"])
@require_auth
def get_chat_history(session_type, session_id):
    """Return chat history for any AI interview session.

    Query params:
      format  'json' (default) | 'txt' — txt triggers a file download

    Returns JSON: {session_type, session_id, label, messages: [{role, content, created_at}]}
    Returns TXT: plain-text transcript as attachment
    """
    if session_type not in _SESSION_MAP:
        return jsonify({"error": f"Unknown session type '{session_type}'. "
                        f"Valid types: {', '.join(_SESSION_MAP)}"}), 400

    session_tbl, messages_tbl, owner_col = _SESSION_MAP[session_type]
    fmt = request.args.get("format", "json").lower()

    with get_db() as conn:
        # Verify session belongs to this user
        row = conn.execute(
            f"SELECT id FROM {session_tbl} WHERE id = ? AND {owner_col} = ?",
            (session_id, g.user_id),
        ).fetchone()
        if not row:
            return jsonify({"error": "Session not found or unauthorized"}), 404

        # Fetch messages ordered by creation time
        rows = conn.execute(
            f"SELECT role, content, created_at FROM {messages_tbl} "
            f"WHERE session_id = ? ORDER BY created_at ASC, id ASC",
            (session_id,),
        ).fetchall()

    messages = [
        {"role": r["role"], "content": r["content"], "created_at": r["created_at"]}
        for r in rows
    ]

    if fmt == "txt":
        return _render_txt(session_type, session_id, messages)

    return jsonify({
        "session_type": session_type,
        "session_id": session_id,
        "label": _SESSION_LABELS.get(session_type, session_type),
        "message_count": len(messages),
        "messages": messages,
    }), 200


def _render_txt(session_type, session_id, messages):
    """Return a plain-text transcript as a downloadable file."""
    from flask import Response

    label = _SESSION_LABELS.get(session_type, session_type)
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"Chat History — {label}",
        f"Session ID: {session_id}",
        f"Exported: {now}",
        "=" * 60,
        "",
    ]
    for msg in messages:
        role_label = "You" if msg["role"] == "user" else "AI"
        ts = (msg.get("created_at") or "")[:19]
        header = f"[{role_label}]" + (f"  {ts}" if ts else "")
        lines.append(header)
        lines.append(msg["content"])
        lines.append("")

    body = "\n".join(lines)
    filename = f"chat_history_{session_type}_{session_id}.txt"
    return Response(
        body,
        mimetype="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
