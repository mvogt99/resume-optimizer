"""Campaign analytics, graph traversal, and engagement routes.

Side-effect import: registers routes on campaigns_bp from campaigns_routes.py.
app.py needs no changes.
"""

import json

from auth import require_auth
from flask import g, jsonify, request
from models import get_db

from routes.campaigns_routes import campaigns_bp  # noqa: F401 — side-effect registration

# --- Analytics ---


@campaigns_bp.route("/api/campaigns/analytics", methods=["GET"])
@require_auth
def get_campaign_analytics():
    from arango_client import get_arango_client

    arango = get_arango_client()
    if not arango.is_connected:
        return jsonify({"error": "ArangoDB not available"}), 503

    result = arango.get_campaign_coverage(user_id=g.user_id)
    return jsonify(result), 200


# --- Update interview (re-plan existing campaign) ---


@campaigns_bp.route("/api/campaigns/<int:campaign_id>/update-interview", methods=["POST"])
@require_auth
def update_campaign_interview(campaign_id):
    from campaign_interview import get_campaign_interviewer

    with get_db() as conn:
        campaign = conn.execute(
            "SELECT * FROM campaigns WHERE id = ? AND user_id = ?",
            (campaign_id, g.user_id),
        ).fetchone()
        if not campaign:
            return jsonify({"error": "Campaign not found"}), 404

        interviewer = get_campaign_interviewer()
        session_data = interviewer.start_session(g.user_id, initial_theme=campaign["theme"])
        session_id = session_data["session_id"]

        context = {
            "theme": campaign["theme"] or "",
            "audience": campaign["audience"] or "",
            "tone": campaign["tone"] or "",
            "storyline": campaign["storyline"] or "",
            "post_count": campaign["post_count"] or 5,
            "cadence": campaign["cadence"] or "",
        }
        conn.execute(
            """UPDATE campaign_sessions
               SET context_json = ?, campaign_id = ?, stage = 'theme'
               WHERE id = ?""",
            (json.dumps(context), campaign_id, session_id),
        )
        conn.commit()

    return (
        jsonify(
            {
                "session_id": session_id,
                "message": session_data.get("message", ""),
                "stage": "theme",
                "context": context,
                "suggestions": session_data.get("suggestions", []),
            }
        ),
        200,
    )


# --- Graph traversal routes ---


@campaigns_bp.route("/api/graph/technologies", methods=["GET"])
@require_auth
def get_technology_summary():
    from arango_client import get_arango_client

    arango = get_arango_client()
    if not arango.is_connected:
        return jsonify({"error": "ArangoDB not available"}), 503

    techs = arango.get_technology_summary()
    return jsonify({"technologies": techs}), 200


@campaigns_bp.route("/api/graph/clients-by-tech", methods=["GET"])
@require_auth
def get_clients_by_technology():
    from arango_client import get_arango_client

    tech_name = request.args.get("tech_name")
    if not tech_name:
        return jsonify({"error": "tech_name query parameter required"}), 400

    arango = get_arango_client()
    if not arango.is_connected:
        return jsonify({"error": "ArangoDB not available"}), 503

    clients = arango.get_clients_by_technology(tech_name)
    return jsonify({"clients": clients}), 200


@campaigns_bp.route("/api/graph/knowledge-context", methods=["GET"])
@require_auth
def get_knowledge_context():
    from arango_client import get_arango_client

    theme = request.args.get("theme")
    if not theme:
        return jsonify({"error": "theme query parameter required"}), 400
    limit = request.args.get("limit", 10, type=int)

    arango = get_arango_client()
    if not arango.is_connected:
        return jsonify({"error": "ArangoDB not available"}), 503

    context = arango.get_knowledge_context(theme, limit=limit)
    return jsonify(context), 200


@campaigns_bp.route("/api/graph/evidence-coverage", methods=["GET"])
@require_auth
def get_evidence_coverage():
    """Return evidence coverage stats: total/used/untapped evidence with ArangoDB edges."""
    from graph_traceability import get_evidence_coverage as _get_coverage

    result = _get_coverage()
    return jsonify(result), 200


# --- Phase 17.14: Post Engagement Tracking ---

ENGAGEMENT_FIELDS = {"impressions", "reactions", "comments_count", "shares", "published_url"}


@campaigns_bp.route(
    "/api/campaigns/<int:campaign_id>/posts/<int:post_id>/engagement", methods=["PUT"]
)
@require_auth
def update_post_engagement(campaign_id, post_id):
    """Record engagement metrics for a published post (5090-generated, expert-validated)."""
    with get_db() as conn:
        campaign = conn.execute(
            "SELECT id FROM campaigns WHERE id = ? AND user_id = ?",
            (campaign_id, g.user_id),
        ).fetchone()
        if not campaign:
            return jsonify({"error": "Campaign not found"}), 404

        post = conn.execute(
            "SELECT id FROM campaign_posts WHERE id = ? AND campaign_id = ?",
            (post_id, campaign_id),
        ).fetchone()
        if not post:
            return jsonify({"error": "Post not found"}), 404

        data = request.get_json() or {}
        updates, values = [], []
        for field in ENGAGEMENT_FIELDS:
            if field in data:
                updates.append(f"{field} = ?")
                values.append(data[field])

        if not updates:
            return jsonify({"error": "No engagement fields provided"}), 400

        updates.append("updated_at = CURRENT_TIMESTAMP")
        values.append(post_id)
        conn.execute(
            f"UPDATE campaign_posts SET {', '.join(updates)} WHERE id = ?",
            values,
        )
        conn.commit()

        updated = conn.execute(
            "SELECT id, title, impressions, reactions, comments_count, shares, published_url "
            "FROM campaign_posts WHERE id = ?",
            (post_id,),
        ).fetchone()

    return jsonify(dict(updated)), 200


@campaigns_bp.route("/api/campaigns/<int:campaign_id>/engagement-summary", methods=["GET"])
@require_auth
def campaign_engagement_summary(campaign_id):
    """Aggregated engagement stats across all posts in a campaign."""
    with get_db() as conn:
        campaign = conn.execute(
            "SELECT id FROM campaigns WHERE id = ? AND user_id = ?",
            (campaign_id, g.user_id),
        ).fetchone()
        if not campaign:
            return jsonify({"error": "Campaign not found"}), 404

        posts = conn.execute(
            "SELECT id, title, impressions, reactions, comments_count, shares "
            "FROM campaign_posts WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchall()

    total_impressions = sum(p["impressions"] or 0 for p in posts)
    total_reactions = sum(p["reactions"] or 0 for p in posts)
    total_comments = sum(p["comments_count"] or 0 for p in posts)
    total_shares = sum(p["shares"] or 0 for p in posts)
    total_engagement = total_reactions + total_comments + total_shares

    avg_engagement_rate = 0
    if total_impressions > 0:
        avg_engagement_rate = round(total_engagement / total_impressions * 100, 2)

    top_post = None
    for p in sorted(posts, key=lambda x: (x["reactions"] or 0), reverse=True):
        if (p["impressions"] or 0) > 0:
            top_post = {"id": p["id"], "title": p["title"], "reactions": p["reactions"]}
            break

    posts_with_engagement = sum(1 for p in posts if (p["impressions"] or 0) > 0)

    return (
        jsonify(
            {
                "total_impressions": total_impressions,
                "total_reactions": total_reactions,
                "total_comments": total_comments,
                "total_shares": total_shares,
                "avg_engagement_rate": avg_engagement_rate,
                "top_performing_post": top_post,
                "posts_with_engagement": posts_with_engagement,
                "total_posts": len(posts),
            }
        ),
        200,
    )
