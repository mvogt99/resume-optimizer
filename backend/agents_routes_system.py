"""Agent system routes: runs log and status."""

import contextlib
import json
import logging

from agents_routes_common import agents_bp
from auth import require_auth
from flask import g, jsonify, request
from models import get_db

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Agent system routes
# ──────────────────────────────────────────────


@agents_bp.route("/api/agents/runs", methods=["GET"])
@require_auth
def agent_runs():
    user_id = g.user_id

    try:
        limit = int(request.args.get("limit", 50))
    except ValueError:
        return jsonify({"error": "Invalid limit"}), 400
    agent_type = request.args.get("agent_type")

    with get_db() as conn:
        if agent_type:
            rows = conn.execute(
                "SELECT * FROM agent_runs WHERE user_id = ? AND agent_type = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (user_id, agent_type, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM agent_runs WHERE user_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()

    runs = []
    for row in rows:
        d = dict(row)
        for key in ("result_json", "metadata_json"):
            if isinstance(d.get(key), str) and d[key]:
                with contextlib.suppress(json.JSONDecodeError, TypeError):
                    d[key] = json.loads(d[key])
        # Decode acceptance_details JSON if present
        if isinstance(d.get("acceptance_details"), str) and d["acceptance_details"]:
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                d["acceptance_details"] = json.loads(d["acceptance_details"])
        runs.append(d)

    return jsonify({"runs": runs, "count": len(runs)}), 200


@agents_bp.route("/api/agents/status", methods=["GET"])
def agent_status():
    """Agent system status + model info + LLM availability."""
    import httpx
    from smart_llm import MODEL_URL, get_current_model

    model_info = get_current_model()

    # Probe LLM availability
    llm_available = False
    try:
        r = httpx.get(
            MODEL_URL.replace("/chat/completions", "/models"),
            timeout=2,
        )
        llm_available = r.status_code == 200
    except Exception:
        pass

    agent_status_val = "ready" if llm_available else "degraded"
    llm_note = "" if llm_available else " (LLM offline — NLP-only)"

    return (
        jsonify(
            {
                "agents": [
                    {
                        "type": "job_scout",
                        "status": agent_status_val,
                        "description": "Job board scraper + LLM scorer" + llm_note,
                    },
                    {
                        "type": "app_tracker",
                        "status": "ready",
                        "description": "Application pipeline + analytics",
                    },
                    {
                        "type": "resume_tailor",
                        "status": agent_status_val,
                        "description": "Auto-customize resume per job posting" + llm_note,
                    },
                    {
                        "type": "cover_letter",
                        "status": agent_status_val,
                        "description": "Generate targeted cover letters" + llm_note,
                    },
                    {
                        "type": "interview_coach",
                        "status": agent_status_val,
                        "description": "Mock interviews with per-answer scoring" + llm_note,
                    },
                    {
                        "type": "career_advisor",
                        "status": agent_status_val,
                        "description": "Career trajectory analysis"
                        " + role recommendations" + llm_note,
                    },
                ],
                "model": model_info,
                "llm_available": llm_available,
                "cost": "$0.00 (RTX 5090 local)",
            }
        ),
        200,
    )
