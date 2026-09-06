"""Multi-session job application routes — CRUD + per-session optimize."""

import json

import linkedin_cache
from auth import require_auth
from flask import Blueprint, g, jsonify, request
from models import JobSession, Resume, ResumeVersion, get_db
from nlp_engine import extract_skill_phrases
from utils import optimize_resume, process_resume
from db_engine import as_datetime

sessions_bp = Blueprint("sessions", __name__)


@sessions_bp.route("/api/sessions", methods=["POST"])
@require_auth
def create_session():
    data = request.get_json() or {}
    session = JobSession.create(
        user_id=g.user_id,
        session_name=data.get("session_name", ""),
        resume_id=data.get("resume_id"),
        resume_version_id=data.get("resume_version_id"),
        job_description_text=data.get("job_description_text", ""),
    )
    return jsonify(session.to_dict()), 201


@sessions_bp.route("/api/sessions", methods=["GET"])
@require_auth
def list_sessions():
    sessions = JobSession.get_all_for_user(g.user_id)
    return jsonify({"sessions": [s.to_dict() for s in sessions]}), 200


@sessions_bp.route("/api/sessions/<session_id>", methods=["GET"])
@require_auth
def get_session(session_id):
    session = JobSession.get_by_id(session_id, user_id=g.user_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    return jsonify(session.to_dict(include_result=True)), 200


@sessions_bp.route("/api/sessions/<session_id>", methods=["PUT"])
@require_auth
def update_session(session_id):
    session = JobSession.get_by_id(session_id, user_id=g.user_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    data = request.get_json() or {}
    updates = {}
    for field in (
        "session_name",
        "job_description_text",
        "resume_id",
        "resume_version_id",
        "optimization_result_json",
        "ats_score",
        "status",
        "posting_id",
    ):
        if field in data:
            updates[field] = data[field]

    if updates:
        JobSession.update(session_id, **updates)

    updated = JobSession.get_by_id(session_id)
    return jsonify(updated.to_dict()), 200


@sessions_bp.route("/api/sessions/posting-statuses", methods=["GET"])
@require_auth
def all_session_posting_statuses():
    """Bulk: return pipeline posting for every session owned by this user.

    Returns {session_id: {id, title, company, status}} for sessions that
    have a linked posting (via posting_id) or a fuzzy title match.
    Auto-links sessions where a match is found.
    """
    with get_db() as conn:
        sessions = conn.execute(
            "SELECT id, session_name, posting_id FROM job_sessions WHERE user_id = ?",
            (g.user_id,),
        ).fetchall()

        # Load all postings for this user into a dict keyed by id and by lower title
        postings_by_id = {}
        postings_by_title = {}
        for row in conn.execute(
            "SELECT id, title, company, status FROM job_postings WHERE user_id = ?",
            (g.user_id,),
        ).fetchall():
            postings_by_id[row["id"]] = dict(row)
            postings_by_title[row["title"].lower()] = dict(row)

        result = {}
        links_to_save = []

        for s in sessions:
            sid = s["id"]
            pid = s["posting_id"]
            match = None

            if pid and pid in postings_by_id:
                match = postings_by_id[pid]
            else:
                raw_name = s["session_name"] or ""
                title = raw_name.replace("Position:", "").strip().lower()
                if title and title in postings_by_title:
                    match = postings_by_title[title]
                    if not pid:
                        links_to_save.append((match["id"], sid))

            if match:
                result[sid] = match

        for posting_id, session_id in links_to_save:
            conn.execute(
                "UPDATE job_sessions SET posting_id = ? WHERE id = ?",
                (posting_id, session_id),
            )
        if links_to_save:
            conn.commit()

    return jsonify({"statuses": result}), 200


@sessions_bp.route("/api/sessions/<session_id>/posting-status", methods=["GET"])
@require_auth
def session_posting_status(session_id):
    """Return the linked pipeline posting (by posting_id or fuzzy title match)."""
    session = JobSession.get_by_id(session_id, user_id=g.user_id)
    if not session:
        return jsonify({"posting": None}), 200

    with get_db() as conn:
        # Prefer explicit link
        if session.posting_id:
            row = conn.execute(
                "SELECT id, title, company, status FROM job_postings WHERE id = ? AND user_id = ?",
                (session.posting_id, g.user_id),
            ).fetchone()
            if row:
                return jsonify({"posting": dict(row)}), 200

        # Fuzzy match: extract title from session_name "Position: XXX" or use raw name
        raw_name = session.session_name or ""
        title = raw_name.replace("Position:", "").strip()
        if title:
            row = conn.execute(
                "SELECT id, title, company, status FROM job_postings "
                "WHERE user_id = ? AND LOWER(title) = LOWER(?) LIMIT 1",
                (g.user_id, title),
            ).fetchone()
            if row:
                # Auto-link for next time
                conn.execute(
                    "UPDATE job_sessions SET posting_id = ? WHERE id = ?",
                    (row["id"], session_id),
                )
                conn.commit()
                return jsonify({"posting": dict(row)}), 200

    return jsonify({"posting": None}), 200


@sessions_bp.route("/api/sessions/<session_id>", methods=["DELETE"])
@require_auth
def delete_session(session_id):
    session = JobSession.get_by_id(session_id, user_id=g.user_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    JobSession.delete(session_id)
    return jsonify({"message": "Session deleted"}), 200


@sessions_bp.route("/api/sessions/<session_id>/optimize", methods=["POST"])
@require_auth
def optimize_session(session_id):
    session = JobSession.get_by_id(session_id, user_id=g.user_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    if not session.job_description_text:
        return jsonify({"error": "No job description in session"}), 400

    # Get resume data from whichever source is set
    resume_data = None
    resume_source = "upload"
    resume_name = ""

    if session.resume_version_id:
        rv = ResumeVersion.get_by_id(session.resume_version_id)
        if rv:
            resume_data = {
                "text": rv.parsed_text or "",
                "skills": extract_skill_phrases(rv.parsed_text or "", use_llm_fallback=False),
            }
            resume_source = rv.source
            resume_name = rv.file_name
    elif session.resume_id:
        resume = Resume.get_by_id(session.resume_id)
        if resume:
            resume_data = process_resume(resume.file_path)
            if "linkedin" in (resume.filename or "").lower():
                resume_source = "linkedin"
            resume_name = resume.filename

    if not resume_data or not resume_data.get("text"):
        return jsonify({"error": "No resume found for session"}), 400

    job_keywords = extract_skill_phrases(session.job_description_text, use_llm_fallback=False)

    # Load equivalencies and ignore list so scoring credits resolved keywords
    user_equivalencies = []
    try:
        from keyword_equivalency import get_equivalencies
        user_equivalencies = get_equivalencies(g.user_id)
    except Exception:
        pass

    user_ignored: set = set()
    try:
        with get_db() as _conn:
            _rows = _conn.execute(
                "SELECT keyword FROM keyword_ignores WHERE user_id = ?", (g.user_id,)
            ).fetchall()
        user_ignored = {r["keyword"].lower() for r in _rows}
    except Exception:
        pass

    optimized = optimize_resume(
        resume_data,
        job_keywords,
        job_text=session.job_description_text,
        linkedin_profile=linkedin_cache.get_raw(g.user_id),
        equivalencies=user_equivalencies,
        ignored_keywords=user_ignored,
    )

    # Build full result
    result = {
        "optimized_resume": optimized,
        "keywords_added": len(optimized.get("added_keywords", [])),
        "relevance_score": optimized.get("score", 0),
        "ats_compliance_score": optimized.get("score", 0),
        "score_breakdown": optimized.get("score_breakdown", {}),
        "accomplishments": optimized.get("accomplishments", []),
        "recommendations": optimized.get("recommendations", []),
        "original_resume_text": optimized.get("original_text", ""),
        "job_description_text": session.job_description_text,
        "sections_found": optimized.get("sections_found", {}),
        "skill_phrases_matched": optimized.get("skill_phrases_matched", []),
        "resume_source": resume_source,
        "resume_name": resume_name,
    }

    # Save result to session
    JobSession.update(
        session_id,
        optimization_result_json=json.dumps(result),
        ats_score=optimized.get("score", 0),
        status="optimized",
    )

    return jsonify(result), 200


@sessions_bp.route("/api/sessions/insights", methods=["GET"])
@require_auth
def sessions_insights():
    """Cross-session optimization learning — aggregates patterns across sessions."""
    from collections import Counter, defaultdict
    from datetime import datetime

    from models import get_db

    def _extract_role(name):
        if not name:
            return "other"
        lower = name.lower()
        for kw in [
            "engineer",
            "architect",
            "developer",
            "manager",
            "director",
            "lead",
            "analyst",
            "scientist",
            "consultant",
            "designer",
            "devops",
            "sre",
            "principal",
            "vp",
        ]:
            if kw in lower:
                return kw
        # Fallback: first word before @ or first word
        return lower.split("@")[0].strip().split()[-1] if lower else "other"

    with get_db() as conn:
        rows = conn.execute(
            "SELECT session_name, resume_version_id, optimization_result_json, "
            "ats_score, created_at FROM job_sessions "
            "WHERE user_id = ? AND ats_score > 0 ORDER BY created_at",
            (g.user_id,),
        ).fetchall()

    if not rows:
        return (
            jsonify(
                {
                    "total_sessions": 0,
                    "avg_score": 0,
                    "max_score": 0,
                    "min_score": 0,
                    "avg_score_by_role": [],
                    "score_trend": [],
                    "best_resume_per_role": [],
                    "top_keywords": [],
                }
            ),
            200,
        )

    scores = [r["ats_score"] for r in rows]
    role_scores = defaultdict(list)
    role_best = {}  # role → {resume_version_id, score}
    keyword_counter = Counter()
    period_data = defaultdict(lambda: {"total": 0, "count": 0})

    for row in rows:
        score = row["ats_score"]
        role = _extract_role(row["session_name"])
        role_scores[role].append(score)

        # Track best resume per role
        vid = row["resume_version_id"]
        if role not in role_best or score > role_best[role]["score"]:
            role_best[role] = {"resume_version_id": vid, "score": score}

        # Aggregate keywords from optimization result
        try:
            opt = json.loads(row["optimization_result_json"] or "{}")
            for kw in opt.get("matching_keywords", []):
                if isinstance(kw, str):
                    keyword_counter[kw.lower()] += 1
        except (json.JSONDecodeError, TypeError):
            pass

        # Score trend by month — handle multiple date formats
        # psycopg2 returns TIMESTAMP columns as datetime objects; sqlite3 returned
        # ISO strings. as_datetime absorbs the difference -- do not reintroduce
        # string slicing here, which raised "datetime has no len()" and 500'd the
        # whole endpoint on PostgreSQL.
        try:
            created_dt = as_datetime(row["created_at"])
            period = created_dt.strftime("%Y-%m") if created_dt else "unknown"
        except (TypeError, ValueError):
            # One malformed timestamp must not fail the entire insights response.
            period = "unknown"
        period_data[period]["total"] += score
        period_data[period]["count"] += 1

    # Cross-reference with feedback outcomes if available
    outcome_by_role = {}
    try:
        from feedback_analyzer import analyze_outcomes

        analysis = analyze_outcomes(g.user_id)
        for rp in analysis.get("role_performance", []):
            outcome_by_role[rp["role"]] = rp["success_rate"]
    except Exception:
        pass

    avg_by_role = sorted(
        [
            {
                "role": role,
                "avg_score": round(sum(s) / len(s), 1),
                "count": len(s),
                "success_rate": outcome_by_role.get(role),
            }
            for role, s in role_scores.items()
        ],
        key=lambda x: -x["avg_score"],
    )

    trend = sorted(
        [
            {"period": p, "avg_score": round(d["total"] / d["count"], 1), "count": d["count"]}
            for p, d in period_data.items()
            if p != "unknown"
        ],
        key=lambda x: x["period"],
    )[-6:]

    best_per_role = [
        {"role": role, "resume_version_id": info["resume_version_id"], "score": info["score"]}
        for role, info in sorted(role_best.items(), key=lambda x: -x[1]["score"])
    ]

    return (
        jsonify(
            {
                "total_sessions": len(rows),
                "avg_score": round(sum(scores) / len(scores), 1),
                "max_score": max(scores),
                "min_score": min(scores),
                "avg_score_by_role": avg_by_role,
                "score_trend": trend,
                "best_resume_per_role": best_per_role,
                "top_keywords": [
                    {"keyword": k, "count": c} for k, c in keyword_counter.most_common(15)
                ],
            }
        ),
        200,
    )
