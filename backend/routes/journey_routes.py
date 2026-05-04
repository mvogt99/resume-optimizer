"""Journey routes — mining, timeline, skills, achievements, narratives, review."""

from auth import require_auth
from flask import Blueprint, g, jsonify, request  # noqa: F401 — request used by mine endpoint

journey_bp = Blueprint("journey", __name__)


# --- Phase 10: Journey mining ---


@journey_bp.route("/api/journey/reset", methods=["DELETE"])
@require_auth
def reset_journey_data():
    from journey_miner import get_journey_miner

    miner = get_journey_miner()
    result = miner.reset_sources(g.user_id)
    return jsonify({"message": "Journey data reset", **result}), 200


@journey_bp.route("/api/journey/mine", methods=["POST"])
@require_auth
def start_journey_mining():
    from journey_miner import get_journey_miner

    data = request.get_json(silent=True) or {}
    opts = {
        "since_date": data.get("since_date") or "",
        "until_date": data.get("until_date") or "",
        "project_scope": data.get("project_scope") or ["all"],
        "sources": data.get("sources") or ["files", "git", "arango", "enrichment"],
    }
    miner = get_journey_miner()
    job_id = miner.start_mining(g.user_id, opts=opts)
    return jsonify({"message": "Mining started", "job_id": job_id}), 202


@journey_bp.route("/api/journey/timeline", methods=["GET"])
@require_auth
def get_journey_timeline():
    from journey_miner import get_journey_miner

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    category = request.args.get("category")
    min_significance = request.args.get("min_significance", 1, type=int)

    miner = get_journey_miner()
    result = miner.get_timeline(
        page=page, per_page=per_page, category=category, user_id=g.user_id,
        min_significance=min_significance
    )
    return jsonify(result), 200


@journey_bp.route("/api/journey/skills", methods=["GET"])
@require_auth
def get_journey_skills():
    from journey_miner import get_journey_miner

    miner = get_journey_miner()
    skills = miner.get_skills(user_id=g.user_id)
    return jsonify({"skills": skills}), 200


@journey_bp.route("/api/journey/achievements", methods=["GET"])
@require_auth
def get_journey_achievements():
    from journey_miner import get_journey_miner

    miner = get_journey_miner()
    achievements = miner.get_achievements(user_id=g.user_id)
    return jsonify({"achievements": achievements}), 200


@journey_bp.route("/api/journey/narratives", methods=["GET"])
@require_auth
def get_journey_narratives():
    from journey_miner import get_journey_miner

    miner = get_journey_miner()
    narratives = miner.get_narratives(g.user_id)
    return jsonify({"narratives": narratives}), 200


@journey_bp.route("/api/journey/narratives", methods=["PUT"])
@require_auth
def update_journey_narratives():
    from journey_miner import get_journey_miner

    data = request.get_json()
    narratives = data.get("narratives", [])

    miner = get_journey_miner()
    miner.update_narratives(g.user_id, narratives)
    return jsonify({"message": "Narratives updated"}), 200


@journey_bp.route("/api/journey/approve", methods=["POST"])
@require_auth
def approve_journey_narratives():
    from journey_miner import get_journey_miner

    data = request.get_json() or {}
    narrative_ids = data.get("narrative_ids")

    miner = get_journey_miner()
    ok = miner.approve_narratives(g.user_id, narrative_ids)
    if ok:
        from deep_profile_staleness import mark_profile_stale

        mark_profile_stale(g.user_id, "Journey narratives approved")
        return jsonify({"message": "Narratives approved and stored in knowledge graph"}), 200
    return jsonify({"error": "Approval failed"}), 500


@journey_bp.route("/api/journey/sources", methods=["GET"])
@require_auth
def get_journey_sources():
    from journey_miner import get_journey_miner

    source_type = request.args.get("type")
    limit = request.args.get("limit", 50, type=int)

    miner = get_journey_miner()
    sources = miner.get_sources(source_type=source_type, limit=limit, user_id=g.user_id)
    return jsonify({"sources": sources}), 200


# --- Journey Review / Narrative Interview ---


@journey_bp.route("/api/journey/review/start", methods=["POST"])
@require_auth
def start_journey_review():
    from journey_miner import get_journey_miner

    data = request.get_json() or {}
    review_type = data.get("review_type", "timeline")

    miner = get_journey_miner()
    result = miner.start_review_session(int(g.user_id), review_type)
    return jsonify(result), 200


@journey_bp.route("/api/journey/review/message", methods=["POST"])
@require_auth
def send_journey_review_message():
    from journey_miner import get_journey_miner

    data = request.get_json() or {}
    session_id = data.get("session_id")
    message = data.get("message", "")

    if not session_id or not message:
        return jsonify({"error": "session_id and message required"}), 400

    miner = get_journey_miner()
    result = miner.send_review_message(session_id, message, user_id=g.user_id)
    if "error" in result:
        return jsonify(result), 404
    return jsonify(result), 200


@journey_bp.route("/api/journey/review/apply", methods=["POST"])
@require_auth
def apply_journey_review():
    from journey_miner import get_journey_miner

    data = request.get_json() or {}
    session_id = data.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id required"}), 400

    miner = get_journey_miner()
    result = miner.apply_review_updates(session_id, user_id=g.user_id)
    if "error" in result:
        return jsonify(result), 404
    return jsonify(result), 200


# --- Phase 1.5: Mining history ---


@journey_bp.route("/api/journey/mining-history", methods=["GET"])
@require_auth
def get_mining_history():
    """Get recent mining runs with stats."""
    from models import get_db

    limit = request.args.get("limit", 10, type=int)
    with get_db() as conn:
        rows = conn.execute(
            """SELECT id, started_at, completed_at, status, sources_scanned, events_added,
                      events_updated, events_deduplicated, error_message
               FROM journey_mining_runs WHERE user_id = ? ORDER BY started_at DESC LIMIT ?""",
            (g.user_id, limit)
        ).fetchall()

    runs = []
    for row in rows:
        runs.append({
            "id": row["id"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            "status": row["status"],
            "sources_scanned": row["sources_scanned"],
            "events_added": row["events_added"],
            "events_updated": row["events_updated"],
            "events_deduplicated": row["events_deduplicated"],
            "error_message": row["error_message"],
        })
    return jsonify({"runs": runs}), 200


# --- Phase 3.4: Significance scoring ---


@journey_bp.route("/api/journey/rescore", methods=["POST"])
@require_auth
def rescore_journey_events():
    """Re-score all journey events without re-mining."""
    from models import get_db
    from journey_scorer import score_event, classify_event
    import json

    with get_db() as conn:
        events = conn.execute(
            "SELECT id, source_ids, technologies FROM journey_events WHERE user_id = ?",
            (g.user_id,)
        ).fetchall()

        for event in events:
            # Get the first source for scoring context
            try:
                source_ids = json.loads(event["source_ids"]) if event["source_ids"] else []
            except (json.JSONDecodeError, TypeError):
                source_ids = []

            if source_ids:
                source = conn.execute(
                    "SELECT * FROM journey_sources WHERE id = ?",
                    (source_ids[0],)
                ).fetchone()
                if source:
                    source_dict = dict(source)
                    techs = json.loads(event["technologies"]) if event["technologies"] else []
                    event_dict = {"technologies": techs}
                    new_score = score_event(source_dict, event_dict)
                    new_category = classify_event(source_dict)

                    conn.execute(
                        "UPDATE journey_events SET significance_score = ?, category = ? WHERE id = ?",
                        (new_score, new_category, event["id"])
                    )

        conn.commit()

    return jsonify({"message": "Journey events re-scored", "count": len(events)}), 200
