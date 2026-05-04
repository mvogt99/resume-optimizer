"""Analytics dashboard routes — SQL aggregations over existing tables (Phase 13.4)."""

import json

from auth import require_auth
from flask import Blueprint, g, jsonify, request
from models import get_db

analytics_bp = Blueprint("analytics", __name__)


def _date_filter():
    """Extract optional date_from / date_to query params."""
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    clauses = []
    params = []
    if date_from:
        clauses.append("discovered_at >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("discovered_at <= ?")
        params.append(date_to + " 23:59:59")
    return clauses, params


@analytics_bp.route("/api/analytics/overview", methods=["GET"])
@require_auth
def overview():
    user_id = g.user_id
    dt_clauses, dt_params = _date_filter()
    date_sql = (" AND " + " AND ".join(dt_clauses)) if dt_clauses else ""
    with get_db() as conn:
        total_apps = conn.execute(
            "SELECT COUNT(*) as c FROM job_postings WHERE user_id = ? AND status NOT IN ('discovered', 'bookmarked')"
            + date_sql,
            (user_id, *dt_params),
        ).fetchone()["c"]
        total_postings = conn.execute(
            "SELECT COUNT(*) as c FROM job_postings WHERE user_id = ?" + date_sql,
            (user_id, *dt_params),
        ).fetchone()["c"]
        avg_score = conn.execute(
            "SELECT COALESCE(AVG(match_score), 0) as avg FROM job_postings WHERE user_id = ?"
            + date_sql,
            (user_id, *dt_params),
        ).fetchone()["avg"]
        interview_count = conn.execute(
            "SELECT COUNT(*) as c FROM application_feedback WHERE user_id = ? AND outcome IN ('interview', 'offer')",
            (user_id,),
        ).fetchone()["c"]
        total_feedback = conn.execute(
            "SELECT COUNT(*) as c FROM application_feedback WHERE user_id = ?", (user_id,)
        ).fetchone()["c"]
        active_campaigns = conn.execute(
            "SELECT COUNT(*) as c FROM campaigns WHERE user_id = ? AND status = 'draft'",
            (user_id,),
        ).fetchone()["c"]
        agent_runs = conn.execute(
            "SELECT COUNT(*) as c FROM agent_runs WHERE user_id = ?", (user_id,)
        ).fetchone()["c"]

    response_rate = round((interview_count / max(total_feedback, 1)) * 100, 1)
    return (
        jsonify(
            {
                "total_postings": total_postings,
                "total_applications": total_apps,
                "average_match_score": round(avg_score, 1),
                "response_rate": response_rate,
                "active_campaigns": active_campaigns,
                "agent_runs": agent_runs,
            }
        ),
        200,
    )


@analytics_bp.route("/api/analytics/funnel", methods=["GET"])
@require_auth
def funnel():
    user_id = g.user_id
    stages = [
        "discovered",
        "bookmarked",
        "tailored",
        "applied",
        "phone_screen",
        "interview",
        "offered",
        "accepted",
    ]
    with get_db() as conn:
        counts = {}
        for stage in stages:
            row = conn.execute(
                "SELECT COUNT(*) as c FROM job_postings WHERE user_id = ? AND status = ?",
                (user_id, stage),
            ).fetchone()
            counts[stage] = row["c"]

    # Calculate conversion rates
    conversions = []
    for i in range(len(stages) - 1):
        from_count = counts[stages[i]]
        to_count = counts[stages[i + 1]]
        rate = round((to_count / max(from_count, 1)) * 100, 1) if from_count > 0 else 0
        conversions.append(
            {
                "from": stages[i],
                "to": stages[i + 1],
                "from_count": from_count,
                "to_count": to_count,
                "conversion_rate": rate,
            }
        )

    return jsonify({"stages": counts, "conversions": conversions}), 200


@analytics_bp.route("/api/analytics/score-trends", methods=["GET"])
@require_auth
def score_trends():
    user_id = g.user_id
    dt_clauses, dt_params = _date_filter()
    date_sql = (" AND " + " AND ".join(dt_clauses)) if dt_clauses else ""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT DATE(discovered_at) as date, AVG(match_score) as avg_score, "
            "COUNT(*) as count FROM job_postings "
            "WHERE user_id = ? AND match_score > 0" + date_sql + " "
            "GROUP BY DATE(discovered_at) ORDER BY date",
            (user_id, *dt_params),
        ).fetchall()

    return (
        jsonify(
            {
                "trends": [
                    {"date": r["date"], "avg_score": round(r["avg_score"], 1), "count": r["count"]}
                    for r in rows
                ]
            }
        ),
        200,
    )


@analytics_bp.route("/api/analytics/skills-demand", methods=["GET"])
@require_auth
def skills_demand():
    user_id = g.user_id
    dt_clauses, dt_params = _date_filter()
    date_sql = (" AND " + " AND ".join(dt_clauses)) if dt_clauses else ""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT skills_missing, skills_overlap, description "
            "FROM job_postings WHERE user_id = ?" + date_sql,
            (user_id, *dt_params),
        ).fetchall()

    total_postings = len(rows)
    missing_counts = {}
    overlap_counts = {}
    all_jd_skills = {}

    for row in rows:
        # Missing skills (user doesn't have)
        try:
            missing = json.loads(row["skills_missing"] or "[]")
        except (json.JSONDecodeError, TypeError):
            missing = []
        for skill in missing:
            s = skill.strip().lower() if isinstance(skill, str) else str(skill).lower()
            if s:
                missing_counts[s] = missing_counts.get(s, 0) + 1
                all_jd_skills[s] = all_jd_skills.get(s, 0) + 1

        # Overlap skills (user has)
        try:
            overlap = json.loads(row["skills_overlap"] or "[]")
        except (json.JSONDecodeError, TypeError):
            overlap = []
        for skill in overlap:
            s = skill.strip().lower() if isinstance(skill, str) else str(skill).lower()
            if s:
                overlap_counts[s] = overlap_counts.get(s, 0) + 1
                all_jd_skills[s] = all_jd_skills.get(s, 0) + 1

    # Top missing (skills to learn)
    sorted_missing = sorted(missing_counts.items(), key=lambda x: -x[1])[:20]
    # Top overlap (strengths in demand)
    sorted_overlap = sorted(overlap_counts.items(), key=lambda x: -x[1])[:20]
    # All skills by demand (combined)
    sorted_all = sorted(all_jd_skills.items(), key=lambda x: -x[1])[:30]

    return (
        jsonify(
            {
                "skills_to_learn": [
                    {
                        "skill": s,
                        "demand_count": c,
                        "pct_of_postings": (
                            round(c / total_postings * 100, 1) if total_postings else 0
                        ),
                    }
                    for s, c in sorted_missing
                ],
                "strengths_in_demand": [
                    {
                        "skill": s,
                        "demand_count": c,
                        "pct_of_postings": (
                            round(c / total_postings * 100, 1) if total_postings else 0
                        ),
                    }
                    for s, c in sorted_overlap
                ],
                "all_skills_by_demand": [
                    {
                        "skill": s,
                        "demand_count": c,
                        "pct_of_postings": (
                            round(c / total_postings * 100, 1) if total_postings else 0
                        ),
                        "user_has": s in overlap_counts,
                    }
                    for s, c in sorted_all
                ],
                "total_postings_analyzed": total_postings,
                # Backwards-compatible: keep "skills" key for existing consumers
                "skills": [{"skill": s, "demand_count": c} for s, c in sorted_missing],
            }
        ),
        200,
    )


@analytics_bp.route("/api/analytics/agent-usage", methods=["GET"])
@require_auth
def agent_usage():
    user_id = g.user_id
    with get_db() as conn:
        rows = conn.execute(
            "SELECT agent_type, COUNT(*) as total, "
            "SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as success, "
            "SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed, "
            "AVG(duration_ms) as avg_duration_ms "
            "FROM agent_runs WHERE user_id = ? GROUP BY agent_type",
            (user_id,),
        ).fetchall()

    return (
        jsonify(
            {
                "agents": [
                    {
                        "agent_type": r["agent_type"],
                        "total_runs": r["total"],
                        "success_count": r["success"],
                        "failed_count": r["failed"],
                        "success_rate": round((r["success"] / max(r["total"], 1)) * 100, 1),
                        "avg_duration_ms": round(r["avg_duration_ms"] or 0),
                    }
                    for r in rows
                ]
            }
        ),
        200,
    )


@analytics_bp.route("/api/analytics/feedback-summary", methods=["GET"])
@require_auth
def feedback_summary():
    user_id = g.user_id
    with get_db() as conn:
        rows = conn.execute(
            "SELECT outcome, COUNT(*) as count FROM application_feedback "
            "WHERE user_id = ? GROUP BY outcome",
            (user_id,),
        ).fetchall()

    total = sum(r["count"] for r in rows)
    distribution = [
        {
            "outcome": r["outcome"],
            "count": r["count"],
            "percentage": round((r["count"] / max(total, 1)) * 100, 1),
        }
        for r in rows
    ]

    return jsonify({"distribution": distribution, "total": total}), 200
