"""Career Advisor routes including salary insights."""

import logging

from agents import get_career_advisor
from agents.acceptance import MAX_ATTEMPTS, build_failure_teaching, record_acceptance, should_retry, verify
from agents_routes_common import _LLM_LIMIT, _persist_acceptance, agents_bp
from auth import require_auth
from deep_profile import get_deep_profile_engine
from flask import g, jsonify, request
from models import get_db

from rate_limit import limiter

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Career Advisor routes
# ──────────────────────────────────────────────


@agents_bp.route("/api/agents/advisor/analyze", methods=["POST"])
@require_auth
@limiter.limit(_LLM_LIMIT)
def advisor_analyze():
    user_id = g.user_id

    advisor = get_career_advisor()
    acceptance = None
    attempts = 0

    for attempt in range(MAX_ATTEMPTS):
        attempts = attempt + 1
        result = advisor.analyze_career(user_id)
        if "error" in result:
            return jsonify(result), 400
        acceptance = verify("career_advisor", result)
        teaching = build_failure_teaching(acceptance, {"user_id": user_id}, output=result)
        record_acceptance("", acceptance, attempt, teaching)
        if not should_retry(acceptance, attempt):
            break
        advisor._pending_retry_teaching = teaching  # W1
        logger.warning("[Route/advisor] Attempt %d failed — retrying.\n%s", attempt + 1, teaching)

    _persist_acceptance(user_id, "career_advisor", acceptance, attempts)
    if isinstance(result, dict):
        result["acceptance"] = acceptance.to_dict() if acceptance else {}  # W5
        result["acceptance_attempts"] = attempts  # W5
    return jsonify(result), 200


@agents_bp.route("/api/agents/advisor/skills-roadmap", methods=["POST"])
@require_auth
@limiter.limit(_LLM_LIMIT)
def advisor_skills_roadmap():
    user_id = g.user_id

    data = request.get_json(silent=True) or {}
    target_role = data.get("target_role", "")
    if not target_role:
        return jsonify({"error": "target_role is required"}), 400

    advisor = get_career_advisor()
    acceptance = None
    attempts = 0

    for attempt in range(MAX_ATTEMPTS):
        attempts = attempt + 1
        result = advisor.get_skills_roadmap(user_id, target_role)
        if "error" in result:
            return jsonify(result), 400
        acceptance = verify("advisor_roadmap", result)
        teaching = build_failure_teaching(acceptance, {"target_role": target_role}, output=result)
        record_acceptance("", acceptance, attempt, teaching)
        if not should_retry(acceptance, attempt):
            break
        advisor._pending_retry_teaching = teaching  # W1
        logger.warning(
            "[Route/roadmap] Attempt %d failed — retrying.\n%s", attempt + 1, teaching
        )

    _persist_acceptance(user_id, "career_advisor", acceptance, attempts)
    result["acceptance"] = acceptance.to_dict() if acceptance else {}
    result["acceptance_attempts"] = attempts
    return jsonify(result), 200


@agents_bp.route("/api/agents/advisor/role-recommendations", methods=["POST"])
@require_auth
@limiter.limit(_LLM_LIMIT)
def advisor_role_recommendations():
    user_id = g.user_id

    advisor = get_career_advisor()
    acceptance = None
    attempts = 0

    for attempt in range(MAX_ATTEMPTS):
        attempts = attempt + 1
        result = advisor.get_role_recommendations(user_id)
        if "error" in result:
            return jsonify(result), 400
        acceptance = verify("advisor_roles", result)
        teaching = build_failure_teaching(acceptance, {"user_id": user_id}, output=result)
        record_acceptance("", acceptance, attempt, teaching)
        if not should_retry(acceptance, attempt):
            break
        advisor._pending_retry_teaching = teaching  # W1
        logger.warning(
            "[Route/roles] Attempt %d failed — retrying.\n%s", attempt + 1, teaching
        )

    _persist_acceptance(user_id, "career_advisor", acceptance, attempts)
    result["acceptance"] = acceptance.to_dict() if acceptance else {}
    result["acceptance_attempts"] = attempts
    return jsonify(result), 200


@agents_bp.route("/api/agents/advisor/history", methods=["GET"])
@require_auth
def advisor_history():
    user_id = g.user_id
    analysis_type = request.args.get("type")

    advisor = get_career_advisor()
    results = advisor.get_history(user_id, analysis_type=analysis_type)
    return jsonify({"analyses": results}), 200


# ──────────────────────────────────────────────
# Agent Enhancements (Phase 13.5) — advisor
# ──────────────────────────────────────────────


@agents_bp.route("/api/agents/advisor/market-insights", methods=["GET"])
@require_auth
def advisor_market_insights():
    """Market analysis from scraped job descriptions."""
    advisor = get_career_advisor()
    insights = advisor.market_insights(g.user_id)
    return jsonify(insights), 200


@agents_bp.route("/api/agents/advisor/feedback-analysis", methods=["GET"])
@require_auth
def advisor_feedback_analysis():
    """Application outcome analysis."""
    advisor = get_career_advisor()
    analysis = advisor.feedback_analysis(g.user_id)
    return jsonify(analysis), 200


@agents_bp.route("/api/agents/advisor/salary-insights", methods=["GET"])
@require_auth
def advisor_salary_insights():
    """Salary intelligence from job postings and deep profile."""
    user_id = g.user_id

    with get_db() as conn:
        # Get all postings with salary data
        rows = conn.execute(
            "SELECT title, company, salary_min, salary_max, match_score, status "
            "FROM job_postings WHERE user_id = ? AND (salary_min > 0 OR salary_max > 0)",
            (user_id,),
        ).fetchall()

        # Also get postings without salary for count
        total_postings = conn.execute(
            "SELECT COUNT(*) FROM job_postings WHERE user_id = ?", (user_id,)
        ).fetchone()[0]

    if not rows:
        return (
            jsonify(
                {
                    "salary_data_available": False,
                    "total_postings": total_postings,
                    "postings_with_salary": 0,
                    "message": (
                        "No salary data in your postings. "
                        "Salary info depends on job board data availability."
                    ),
                    "by_role": [],
                    "overall": {},
                    "negotiation_points": [],
                }
            ),
            200,
        )

    # Aggregate salary stats
    all_mins = [r["salary_min"] for r in rows if r["salary_min"] > 0]
    all_maxes = [r["salary_max"] for r in rows if r["salary_max"] > 0]
    all_salaries = all_mins + all_maxes

    overall = {}
    if all_salaries:
        overall = {
            "min": min(all_salaries),
            "max": max(all_salaries),
            "median": sorted(all_salaries)[len(all_salaries) // 2],
            "avg": round(sum(all_salaries) / len(all_salaries)),
        }

    # Group by role keyword
    role_salary = {}
    for r in rows:
        title = (r["title"] or "").lower()
        role_key = _extract_role_keyword_from_title(title)
        bucket = role_salary.setdefault(role_key, {"mins": [], "maxes": [], "count": 0})
        bucket["count"] += 1
        if r["salary_min"] > 0:
            bucket["mins"].append(r["salary_min"])
        if r["salary_max"] > 0:
            bucket["maxes"].append(r["salary_max"])

    by_role = []
    for role, data in sorted(role_salary.items(), key=lambda x: -x[1]["count"]):
        salaries = data["mins"] + data["maxes"]
        if salaries:
            by_role.append(
                {
                    "role": role,
                    "count": data["count"],
                    "min": min(salaries),
                    "max": max(salaries),
                    "median": sorted(salaries)[len(salaries) // 2],
                }
            )

    # Generate negotiation talking points
    negotiation_points = _build_negotiation_points(user_id, overall, by_role)

    return (
        jsonify(
            {
                "salary_data_available": True,
                "total_postings": total_postings,
                "postings_with_salary": len(rows),
                "overall": overall,
                "by_role": by_role[:10],
                "top_paying": [
                    {
                        "title": r["title"],
                        "company": r["company"],
                        "salary_range": f"${r['salary_min']:,.0f} - ${r['salary_max']:,.0f}",
                        "match_score": r["match_score"],
                    }
                    for r in sorted(rows, key=lambda x: x["salary_max"], reverse=True)[:5]
                ],
                "negotiation_points": negotiation_points,
            }
        ),
        200,
    )


def _extract_role_keyword_from_title(title):
    """Extract role category from job title."""
    keywords = [
        "engineer",
        "developer",
        "architect",
        "manager",
        "director",
        "lead",
        "analyst",
        "scientist",
        "consultant",
        "designer",
        "devops",
        "sre",
        "admin",
        "vp",
        "principal",
    ]
    for kw in keywords:
        if kw in title:
            return kw
    words = title.split()
    return words[0] if words else "other"


def _build_negotiation_points(user_id, overall, by_role):
    """Generate negotiation talking points from salary data + deep profile."""
    points = []

    if overall:
        median = overall.get("median", 0)
        points.append(
            f"Market median for your target roles: ${median:,.0f}. "
            "Use this as your baseline — don't accept below without strong reason."
        )

    # Load deep profile differentiators for leverage
    try:
        engine = get_deep_profile_engine()
        profile = engine.get_profile(user_id)
        if profile:
            diffs = profile.get("differentiators", [])[:3]
            if diffs:
                diff_names = [d.get("label", d) if isinstance(d, dict) else str(d) for d in diffs]
                points.append(
                    f"Your unique differentiators ({', '.join(diff_names)}) "
                    "justify positioning above median. Quantify these in negotiation."
                )

            impacts = profile.get("business_impacts", [])[:2]
            if impacts:
                for imp in impacts:
                    desc = (
                        imp.get("description", imp.get("impact", str(imp)))
                        if isinstance(imp, dict)
                        else str(imp)
                    )
                    points.append(f'Leverage past impact: "{desc[:150]}"')
    except Exception:
        pass

    if by_role:
        top = max(by_role, key=lambda r: r.get("max", 0))
        points.append(
            f"Highest-paying role type: '{top['role']}' "
            f"(up to ${top['max']:,.0f}). Consider targeting these."
        )

    return points
