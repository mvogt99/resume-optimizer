"""
Feedback analyzer — correlates application outcomes with skills, resume scores,
and posting characteristics to generate actionable insights.

Answers: "What skills are correlated with rejections?", "What resume score
threshold leads to interviews?", "Which role types are working/not working?"
"""

import contextlib
import json

from models import get_db


def analyze_outcomes(user_id):
    """Comprehensive outcome analysis correlating feedback with posting data.

    Returns dict with:
      - skills_correlated_with_rejection: skills that appear in rejected postings
      - skills_correlated_with_success: skills in postings that got interviews/offers
      - score_vs_outcome: avg ATS score per outcome category
      - role_performance: outcomes grouped by job title keywords
      - actionable_insights: plain-text recommendations
    """
    with get_db() as conn:
        # Join feedback with posting data and session scores
        rows = conn.execute(
            """
            SELECT af.outcome, af.posting_id,
                   jp.title, jp.company, jp.match_score,
                   jp.skills_missing, jp.skills_overlap, jp.description
            FROM application_feedback af
            LEFT JOIN job_postings jp ON af.posting_id = jp.id
            WHERE af.user_id = ?
            ORDER BY af.created_at DESC
            """,
            (user_id,),
        ).fetchall()

        # Also get session ATS scores
        session_scores = {}
        score_rows = conn.execute(
            "SELECT job_description_text, ats_score FROM job_sessions "
            "WHERE user_id = ? AND ats_score > 0",
            (user_id,),
        ).fetchall()

        for sr in score_rows:
            jd = (sr["job_description_text"] or "")[:200]
            if jd:
                session_scores[jd] = sr["ats_score"]

    if not rows:
        return {
            "skills_correlated_with_rejection": [],
            "skills_correlated_with_success": [],
            "score_vs_outcome": {},
            "role_performance": [],
            "actionable_insights": [
                "No application feedback recorded yet. Record outcomes to get insights."
            ],
            "total_analyzed": 0,
        }

    # Categorize outcomes
    positive = {"interview", "offer", "accepted"}
    negative = {"rejected", "ghosted", "no_response"}

    rejection_skills = {}  # skill → count
    success_skills = {}
    score_by_outcome = {}  # outcome → [scores]
    role_outcomes = {}  # role_keyword → {positive: N, negative: N}

    for row in rows:
        outcome = row["outcome"] or ""
        is_positive = outcome in positive
        is_negative = outcome in negative

        # Skills correlation
        missing = _parse_json_list(row["skills_missing"])
        overlap = _parse_json_list(row["skills_overlap"])

        if is_negative:
            for skill in missing:
                rejection_skills[skill] = rejection_skills.get(skill, 0) + 1
        if is_positive:
            for skill in overlap:
                success_skills[skill] = success_skills.get(skill, 0) + 1

        # Score vs outcome
        score = row["match_score"]
        if score and score > 0:
            score_by_outcome.setdefault(outcome, []).append(score)

        # Role performance
        title = (row["title"] or "").lower()
        role_key = _extract_role_keyword(title)
        if role_key:
            bucket = role_outcomes.setdefault(role_key, {"positive": 0, "negative": 0, "total": 0})
            bucket["total"] += 1
            if is_positive:
                bucket["positive"] += 1
            elif is_negative:
                bucket["negative"] += 1

    # Build results
    sorted_rejection = sorted(rejection_skills.items(), key=lambda x: -x[1])[:15]
    sorted_success = sorted(success_skills.items(), key=lambda x: -x[1])[:15]

    avg_scores = {}
    for outcome, scores in score_by_outcome.items():
        avg_scores[outcome] = round(sum(scores) / len(scores), 1)

    role_perf = []
    for role, counts in sorted(role_outcomes.items(), key=lambda x: -x[1]["total"]):
        rate = round(counts["positive"] / max(counts["total"], 1) * 100, 1)
        role_perf.append(
            {
                "role": role,
                "total": counts["total"],
                "positive": counts["positive"],
                "negative": counts["negative"],
                "success_rate": rate,
            }
        )

    # Generate actionable insights
    insights = _generate_insights(
        sorted_rejection, sorted_success, avg_scores, role_perf, len(rows)
    )

    return {
        "skills_correlated_with_rejection": [
            {"skill": s, "rejection_count": c} for s, c in sorted_rejection
        ],
        "skills_correlated_with_success": [
            {"skill": s, "success_count": c} for s, c in sorted_success
        ],
        "score_vs_outcome": avg_scores,
        "role_performance": role_perf,
        "actionable_insights": insights,
        "total_analyzed": len(rows),
    }


def get_skills_to_prioritize(user_id):
    """Return skills that are frequently missing in rejected applications.

    Designed to be injected into skills_gap analysis as high-priority items.
    Threshold scales with data volume: 1+ rejection when <5 outcomes, 2+ otherwise.
    """
    analysis = analyze_outcomes(user_id)
    rejection_skills = analysis.get("skills_correlated_with_rejection", [])
    total = analysis.get("total_analyzed", 0)

    # Scale threshold: with few data points, even 1 rejection is signal
    threshold = 1 if total < 5 else 2

    return [s["skill"] for s in rejection_skills if s["rejection_count"] >= threshold]


# --- Internal helpers ---


def _parse_json_list(val):
    """Safely parse a JSON list from a DB field."""
    if not val:
        return []
    if isinstance(val, list):
        return [str(s).lower().strip() for s in val if s]
    if isinstance(val, str):
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return [str(s).lower().strip() for s in parsed if s]
    return []


def _extract_role_keyword(title):
    """Extract a role category from a job title."""
    title = title.lower()
    role_keywords = [
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
        "coordinator",
        "specialist",
    ]
    for kw in role_keywords:
        if kw in title:
            return kw
    return title.split()[0] if title.split() else ""


def _generate_insights(rejection_skills, success_skills, avg_scores, role_perf, total):
    """Generate plain-text actionable insights from analysis."""
    insights = []

    if total == 0:
        insights.append(
            "No outcomes recorded yet. Record application results to unlock pattern analysis."
        )
        return insights

    if total < 3:
        insights.append(
            f"{total} outcome(s) recorded — early data. Patterns become more reliable "
            "with 5+ outcomes. Keep recording results."
        )

    # Skills insight
    if rejection_skills:
        top3 = [s for s, _ in rejection_skills[:3]]
        insights.append(
            f"Skills most correlated with rejections: {', '.join(top3)}. "
            "Consider upskilling or emphasizing these more in your resume."
        )

    if success_skills:
        top3 = [s for s, _ in success_skills[:3]]
        insights.append(
            f"Your strongest differentiators (correlated with interviews): {', '.join(top3)}. "
            "Emphasize these prominently in all applications."
        )

    # Score insight
    if avg_scores:
        interview_avg = avg_scores.get("interview", avg_scores.get("offer", 0))
        rejected_avg = avg_scores.get("rejected", avg_scores.get("ghosted", 0))
        if interview_avg and rejected_avg and interview_avg > rejected_avg:
            insights.append(
                f"Postings where you got interviews had avg score {interview_avg} "
                f"vs {rejected_avg} for rejections. Aim for score >{int(interview_avg - 5)} "
                "before applying."
            )

    # Role insight
    if role_perf:
        best = max(role_perf, key=lambda r: r["success_rate"]) if role_perf else None
        worst = min(
            (r for r in role_perf if r["total"] >= 2),
            key=lambda r: r["success_rate"],
            default=None,
        )
        if best and best["success_rate"] > 0:
            insights.append(
                f"Best performing role type: '{best['role']}' "
                f"({best['success_rate']}% success rate). "
                "Consider focusing your search here."
            )
        if worst and worst["success_rate"] < 30 and worst != best:
            insights.append(
                f"Struggling with '{worst['role']}' roles ({worst['success_rate']}% success rate). "
                "Consider tailoring your resume differently for these."
            )

    return insights


# ---------------------------------------------------------------------------
# Phase P2-C: Stage-transition feedback
# ---------------------------------------------------------------------------

_OUTCOME_MAP = {
    ("applied", "phone_screen"): "callback",
    ("phone_screen", "interview"): "advanced",
    ("interview", "offer"): "success",
}


def classify_outcome_type(old_stage: str, new_stage: str) -> str:
    """Map an old->new stage pair to a semantic outcome type."""
    if new_stage == "rejected":
        return "rejected"
    return _OUTCOME_MAP.get((old_stage, new_stage), "neutral")


def record_stage_transition(
    user_id: int,
    posting_id: str,
    old_stage: str,
    new_stage: str,
    ats_score: float = 0.0,
    resume_version_id: str = "",
    cover_letter_id: str = "",
    cover_letter_score: float = 0.0,
) -> None:
    """Insert an application_feedback row for a pipeline stage change."""
    import sqlite3
    from datetime import datetime, timezone

    from models import get_db

    outcome_type = classify_outcome_type(old_stage, new_stage)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO application_feedback "
                "(user_id, posting_id, old_stage, new_stage, outcome_type, "
                "ats_score, resume_version_id, cover_letter_id, "
                "cover_letter_score, transitioned_at, outcome) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    user_id,
                    posting_id,
                    old_stage,
                    new_stage,
                    outcome_type,
                    ats_score,
                    resume_version_id,
                    cover_letter_id,
                    cover_letter_score,
                    now,
                    outcome_type,
                ),
            )
            conn.commit()
    except sqlite3.Error as e:
        import logging

        logging.getLogger(__name__).warning("record_stage_transition failed: %s", e)


def get_correlations(user_id: int) -> dict:
    """ATS score distribution and callback rate for stage-transition feedback rows."""
    from models import get_db

    empty: dict = {
        "ats_score_distribution": {"callback": [], "rejected": [], "neutral": []},
        "callback_rate": 0.0,
        "success_rate": 0.0,
        "total_applications": 0,
        "avg_ats_callback": None,
        "avg_ats_rejected": None,
    }

    try:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT ats_score, outcome_type, resume_version_id, new_stage "
                "FROM application_feedback WHERE user_id=? "
                "AND outcome_type != '' "
                "ORDER BY transitioned_at DESC",
                (user_id,),
            ).fetchall()
    except Exception as e:
        import logging

        logging.getLogger(__name__).warning("get_correlations query failed: %s", e)
        return empty

    if not rows:
        return empty

    dist: dict = {
        "callback": [],
        "rejected": [],
        "neutral": [],
        "advanced": [],
        "success": [],
    }
    for r in rows:
        ot = (r["outcome_type"] or "neutral") if hasattr(r, "__getitem__") else "neutral"
        score = (r["ats_score"] or 0.0) if hasattr(r, "__getitem__") else 0.0
        dist.setdefault(ot, []).append(score)

    total = len(rows)
    callbacks = len(dist.get("callback", [])) + len(dist.get("advanced", []))
    successes = len(dist.get("success", []))

    def _avg(lst):
        return round(sum(lst) / len(lst), 3) if lst else None

    cb_scores = dist.get("callback", []) + dist.get("advanced", [])
    rej_scores = dist.get("rejected", [])

    return {
        "ats_score_distribution": {
            "callback": dist.get("callback", []),
            "rejected": dist.get("rejected", []),
            "neutral": dist.get("neutral", []),
        },
        "callback_rate": round(callbacks / total * 100, 1) if total else 0.0,
        "success_rate": round(successes / total * 100, 1) if total else 0.0,
        "total_applications": total,
        "avg_ats_callback": _avg(cb_scores),
        "avg_ats_rejected": _avg(rej_scores),
    }


def get_feedback_summary(user_id: int) -> dict:
    """High-level feedback counts for dashboard."""
    from models import get_db

    try:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT outcome_type, COUNT(*) as cnt "
                "FROM application_feedback WHERE user_id=? GROUP BY outcome_type",
                (user_id,),
            ).fetchall()
    except Exception as e:
        import logging

        logging.getLogger(__name__).warning("get_feedback_summary failed: %s", e)
        return {
            "total_applications": 0,
            "callbacks": 0,
            "advanced": 0,
            "success": 0,
            "rejected": 0,
            "success_rate": 0.0,
        }

    counts: dict = {}
    for row in rows:
        counts[row["outcome_type"]] = row["cnt"]

    total = sum(counts.values())
    callbacks = counts.get("callback", 0) + counts.get("advanced", 0)
    successes = counts.get("success", 0)

    return {
        "total_applications": total,
        "callbacks": callbacks,
        "advanced": counts.get("advanced", 0),
        "success": successes,
        "rejected": counts.get("rejected", 0),
        "success_rate": round(successes / total * 100, 1) if total else 0.0,
    }


def build_success_context(rows: list) -> str:
    """Build a prompt injection snippet from successful feedback rows."""
    if not rows:
        return ""

    successful = [
        r
        for r in rows
        if (r.get("outcome_type") if isinstance(r, dict) else None)
        in ("callback", "advanced", "success")
    ]
    if not successful:
        return ""

    scores = [(r.get("ats_score") or 0) if isinstance(r, dict) else 0 for r in successful]
    avg_score = sum(scores) / len(scores) if scores else 0

    lines = [
        f"Based on {len(successful)} successful application(s):",
        f"  - Average ATS score that led to callbacks: {avg_score:.0%}",
        "  - Emphasize quantified outcomes and relevant keywords.",
    ]
    return "\n".join(lines)
