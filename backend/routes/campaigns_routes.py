"""Campaign routes — interview, CRUD, posts, export.

Analytics, graph traversal, and engagement routes are in campaigns_routes_analytics.py
(side-effect import — loads automatically when app.py imports this blueprint).
"""

import json

from auth import require_auth
from flask import Blueprint, g, jsonify, request
from models import get_db

campaigns_bp = Blueprint("campaigns", __name__)

# --- Allowed column names for SQL updates (prevent injection) ---
CAMPAIGN_UPDATE_FIELDS = {"theme", "audience", "tone", "cadence", "status", "storyline"}
POST_UPDATE_FIELDS = {"title", "content", "hashtags", "status", "scheduled_date"}


def _verify_campaign_ownership(conn, campaign_id, user_id):
    """Return campaign row if owned by user, else None."""
    row = conn.execute(
        "SELECT * FROM campaigns WHERE id = ? AND user_id = ?",
        (campaign_id, user_id),
    ).fetchone()
    return row


# --- Campaign interview ---


@campaigns_bp.route("/api/campaigns/interview/start", methods=["POST"])
@require_auth
def start_campaign_interview():
    from campaign_interview import get_campaign_interviewer

    data = request.get_json() or {}
    theme = data.get("theme", "")

    interviewer = get_campaign_interviewer()
    result = interviewer.start_session(g.user_id, initial_theme=theme)
    return jsonify(result), 201


@campaigns_bp.route("/api/campaigns/interview/message", methods=["POST"])
@require_auth
def send_campaign_message():
    from campaign_interview import get_campaign_interviewer

    data = request.get_json()
    session_id = data.get("session_id")
    message = data.get("message")

    if not session_id or not message:
        return jsonify({"error": "session_id and message are required"}), 400

    interviewer = get_campaign_interviewer()
    result = interviewer.process_message(session_id, message, user_id=g.user_id)

    if "error" in result:
        return jsonify(result), 404
    return jsonify(result), 200


@campaigns_bp.route("/api/campaigns/interview/<session_id>/state", methods=["GET"])
@require_auth
def get_campaign_session_state(session_id):
    from campaign_interview import get_campaign_interviewer

    interviewer = get_campaign_interviewer()
    result = interviewer.get_session_state(session_id, user_id=g.user_id)

    if "error" in result:
        return jsonify(result), 404
    return jsonify(result), 200


@campaigns_bp.route("/api/campaigns/create", methods=["POST"])
@require_auth
def create_campaign_from_interview():
    from campaign_interview import get_campaign_interviewer

    data = request.get_json()
    session_id = data.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400

    interviewer = get_campaign_interviewer()
    result = interviewer.finalize_to_campaign(session_id, g.user_id)

    if "error" in result:
        return jsonify(result), 400
    return jsonify(result), 201


# --- Campaign CRUD ---


@campaigns_bp.route("/api/campaigns", methods=["GET"])
@require_auth
def list_campaigns():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM campaigns WHERE user_id = ? ORDER BY created_at DESC",
            (g.user_id,),
        ).fetchall()

    campaigns = []
    for r in rows:
        d = dict(r)
        d["metadata"] = json.loads(d.pop("metadata_json", "{}"))
        campaigns.append(d)
    return jsonify({"campaigns": campaigns}), 200


@campaigns_bp.route("/api/campaigns/<int:campaign_id>", methods=["GET"])
@require_auth
def get_campaign(campaign_id):
    with get_db() as conn:
        row = _verify_campaign_ownership(conn, campaign_id, g.user_id)
    if not row:
        return jsonify({"error": "Campaign not found"}), 404

    d = dict(row)
    d["metadata"] = json.loads(d.pop("metadata_json", "{}"))
    return jsonify(d), 200


@campaigns_bp.route("/api/campaigns/<int:campaign_id>", methods=["PUT"])
@require_auth
def update_campaign(campaign_id):
    with get_db() as conn:
        row = _verify_campaign_ownership(conn, campaign_id, g.user_id)
        if not row:
            return jsonify({"error": "Campaign not found"}), 404

        data = request.get_json()
        updates = []
        values = []
        for field in CAMPAIGN_UPDATE_FIELDS:
            if field in data:
                updates.append(f"{field} = ?")
                values.append(data[field])

        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            values.append(campaign_id)
            conn.execute(
                f"UPDATE campaigns SET {', '.join(updates)} WHERE id = ?",
                values,
            )
            conn.commit()

    return jsonify({"message": "Campaign updated"}), 200


@campaigns_bp.route("/api/campaigns/<int:campaign_id>", methods=["DELETE"])
@require_auth
def delete_campaign(campaign_id):
    with get_db() as conn:
        row = _verify_campaign_ownership(conn, campaign_id, g.user_id)
        if not row:
            return jsonify({"error": "Campaign not found"}), 404

        conn.execute("DELETE FROM campaign_posts WHERE campaign_id = ?", (campaign_id,))
        conn.execute("DELETE FROM campaigns WHERE id = ?", (campaign_id,))
        conn.commit()

    return jsonify({"message": "Campaign deleted"}), 200


# --- Post management ---


@campaigns_bp.route("/api/campaigns/<int:campaign_id>/generate", methods=["POST"])
@require_auth
def generate_campaign_posts(campaign_id):
    from batch_jobs import get_batch_manager
    from post_generator import PostGenerator

    manager = get_batch_manager()
    job_id = manager.create_job("campaign_posts", g.user_id, {"campaign_id": campaign_id})

    def worker(jid):
        gen = PostGenerator()
        posts = gen.generate_campaign_posts(campaign_id, g.user_id, job_id=jid)
        return {"posts_generated": len(posts)}

    manager.start_job(job_id, worker)
    return jsonify({"message": "Post generation started", "job_id": job_id}), 202


@campaigns_bp.route("/api/campaigns/<int:campaign_id>/posts", methods=["GET"])
@require_auth
def list_campaign_posts(campaign_id):
    with get_db() as conn:
        # Verify campaign ownership
        campaign = _verify_campaign_ownership(conn, campaign_id, g.user_id)
        if not campaign:
            return jsonify({"error": "Campaign not found"}), 404

        rows = conn.execute(
            "SELECT * FROM campaign_posts WHERE campaign_id = ? ORDER BY position",
            (campaign_id,),
        ).fetchall()

    posts = []
    for r in rows:
        d = dict(r)
        d["source_refs"] = json.loads(d.get("source_refs", "[]") or "[]")
        d["draft_history"] = json.loads(d.get("draft_history", "[]") or "[]")
        posts.append(d)
    return jsonify({"posts": posts}), 200


@campaigns_bp.route("/api/campaigns/<int:campaign_id>/posts", methods=["POST"])
@require_auth
def add_campaign_post(campaign_id):
    with get_db() as conn:
        campaign = _verify_campaign_ownership(conn, campaign_id, g.user_id)
        if not campaign:
            return jsonify({"error": "Campaign not found"}), 404

        data = request.get_json()
        title = data.get("title", "")
        content = data.get("content", "")

        row = conn.execute(
            "SELECT MAX(position) FROM campaign_posts WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()
        next_pos = (row[0] or 0) + 1 if row and row[0] is not None else 0

        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO campaign_posts "
            "(campaign_id, position, title, content, char_count, status) "
            "VALUES (?, ?, ?, ?, ?, 'draft')",
            (campaign_id, next_pos, title, content, len(content)),
        )
        conn.commit()
        post_id = cursor.lastrowid

    return jsonify({"message": "Post added", "post_id": post_id}), 201


@campaigns_bp.route("/api/campaigns/<int:campaign_id>/posts/<int:post_id>", methods=["PUT"])
@require_auth
def update_campaign_post(campaign_id, post_id):
    with get_db() as conn:
        campaign = _verify_campaign_ownership(conn, campaign_id, g.user_id)
        if not campaign:
            return jsonify({"error": "Campaign not found"}), 404

        data = request.get_json()
        updates = []
        values = []
        for field in POST_UPDATE_FIELDS:
            if field in data:
                updates.append(f"{field} = ?")
                values.append(data[field])
                if field == "content":
                    updates.append("char_count = ?")
                    values.append(len(data[field]))

        if not updates:
            return jsonify({"error": "No fields to update"}), 400

        updates.append("updated_at = CURRENT_TIMESTAMP")
        values.append(post_id)

        conn.execute(
            f"UPDATE campaign_posts SET {', '.join(updates)} WHERE id = ?",
            values,
        )
        conn.commit()

    return jsonify({"message": "Post updated"}), 200


@campaigns_bp.route(
    "/api/campaigns/<int:campaign_id>/posts/<int:post_id>/regenerate", methods=["POST"]
)
@require_auth
def regenerate_campaign_post(campaign_id, post_id):
    from post_generator import PostGenerator

    with get_db() as conn:
        campaign = _verify_campaign_ownership(conn, campaign_id, g.user_id)
        if not campaign:
            return jsonify({"error": "Campaign not found"}), 404

    data = request.get_json() or {}
    feedback = data.get("feedback", "")

    gen = PostGenerator()
    result = gen.regenerate_post(post_id, feedback=feedback)

    if "error" in result:
        return jsonify(result), 404
    return jsonify(result), 200


@campaigns_bp.route("/api/campaigns/<int:campaign_id>/posts/<int:post_id>", methods=["DELETE"])
@require_auth
def delete_campaign_post(campaign_id, post_id):
    with get_db() as conn:
        campaign = _verify_campaign_ownership(conn, campaign_id, g.user_id)
        if not campaign:
            return jsonify({"error": "Campaign not found"}), 404

        conn.execute(
            "DELETE FROM campaign_posts WHERE id = ? AND campaign_id = ?",
            (post_id, campaign_id),
        )
        conn.commit()

    return jsonify({"message": "Post deleted"}), 200


@campaigns_bp.route("/api/campaigns/<int:campaign_id>/posts/reorder", methods=["PUT"])
@require_auth
def reorder_campaign_posts(campaign_id):
    data = request.get_json()
    order = data.get("order", [])
    if not order:
        return jsonify({"error": "order array required"}), 400

    with get_db() as conn:
        campaign = _verify_campaign_ownership(conn, campaign_id, g.user_id)
        if not campaign:
            return jsonify({"error": "Campaign not found"}), 404

        for pos, pid in enumerate(order):
            conn.execute(
                "UPDATE campaign_posts SET position = ? WHERE id = ? AND campaign_id = ?",
                (pos, pid, campaign_id),
            )
        conn.commit()

    return jsonify({"message": "Posts reordered"}), 200


# --- Export ---


@campaigns_bp.route("/api/campaigns/<int:campaign_id>/export", methods=["GET"])
@require_auth
def export_campaign(campaign_id):
    with get_db() as conn:
        campaign = _verify_campaign_ownership(conn, campaign_id, g.user_id)
        if not campaign:
            return jsonify({"error": "Campaign not found"}), 404

        posts = conn.execute(
            "SELECT * FROM campaign_posts WHERE campaign_id = ? ORDER BY position",
            (campaign_id,),
        ).fetchall()

    lines = [
        f"Campaign: {campaign['theme']}",
        f"Audience: {campaign['audience']}",
        f"Tone: {campaign['tone']}",
        f"Posts: {len(posts)}",
        "",
        "=" * 60,
    ]

    for p in posts:
        lines.append("")
        lines.append(f"--- Post {p['position'] + 1}: {p['title']} ---")
        lines.append("")
        lines.append(p["content"] or "[No content yet]")
        if p["hashtags"]:
            lines.append("")
            lines.append(p["hashtags"])
        lines.append("")
        lines.append("-" * 40)

    text = "\n".join(lines)
    return jsonify({"text": text, "post_count": len(posts)}), 200
