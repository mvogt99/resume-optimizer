"""Routes for semantic keyword grouping and equivalency interview."""

import json
import logging

from auth import require_auth
from flask import Blueprint, g, jsonify, request
from keyword_equivalency import (
    delete_equivalency,
    generate_rewrites,
    get_equivalencies,
    run_equivalency_turn,
    save_equivalencies,
)
from keyword_grouper import apply_persisted_equivalencies, group_keywords
from keyword_matcher import suggest_semantic_matches
from models import JobDescription, get_db

logger = logging.getLogger(__name__)

keyword_bp = Blueprint("keywords", __name__)


@keyword_bp.route("/api/keywords/group", methods=["POST"])
@require_auth
def group_keywords_endpoint():
    """POST /api/keywords/group — semantically group keywords for a job.

    Body: {keywords: [str], job_description: str (optional)}
    Response: {groups: [{name, keywords, description}], auto_resolved: [...]}
    """
    data = request.get_json(silent=True) or {}
    keywords = data.get("keywords") or []
    job_text = (data.get("job_description") or "").strip()

    if not keywords:
        return jsonify({"groups": [], "auto_resolved": []}), 200

    # DoS protection: cap at 100 keywords per request
    if len(keywords) > 100:
        return jsonify({"error": "Too many keywords (max 100 per request)"}), 400

    if not job_text:
        job_desc = JobDescription.get_latest_for_user(g.user_id)
        if job_desc:
            job_text = job_desc.text

    # Load user's ignore list — strip those keywords before any processing
    try:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT keyword FROM keyword_ignores WHERE user_id = ?",
                (g.user_id,),
            ).fetchall()
        ignored_set = {r["keyword"].lower() for r in rows}
    except Exception:
        ignored_set = set()

    keywords = [k for k in keywords if k.lower() not in ignored_set]

    if not keywords:
        return jsonify({"groups": [], "auto_resolved": []}), 200

    # Check for persisted equivalencies and auto-resolve
    try:
        persisted = get_equivalencies(g.user_id)
        still_missing, auto_resolved = apply_persisted_equivalencies(keywords, persisted)
    except Exception:
        still_missing = keywords
        auto_resolved = []

    result = group_keywords(still_missing, job_text)
    result["auto_resolved"] = auto_resolved
    return jsonify(result), 200


@keyword_bp.route("/api/keywords/equivalency/interview", methods=["POST"])
@require_auth
def equivalency_interview_turn():
    """POST /api/keywords/equivalency/interview — one turn of the interview.

    Body: {
      history: [{question, answer, resolved}],
      current_question: str,
      user_answer: str,
      keyword_groups: [{name, keywords}],
      resume_text: str,
      job_description: str,
      user_finished: bool,
    }
    """
    data = request.get_json(silent=True) or {}
    history = data.get("history") or []
    current_question = (data.get("current_question") or "").strip()
    user_answer = (data.get("user_answer") or "").strip()
    keyword_groups = data.get("keyword_groups") or []
    resume_text = (data.get("resume_text") or "").strip()
    job_text = (data.get("job_description") or "").strip()
    user_finished = bool(data.get("user_finished", False))

    if not current_question:
        return jsonify({"error": "current_question is required"}), 400
    if not user_answer:
        return jsonify({"error": "user_answer is required"}), 400

    if not job_text:
        job_desc = JobDescription.get_latest_for_user(g.user_id)
        if job_desc:
            job_text = job_desc.text

    result = run_equivalency_turn(
        history=history,
        current_question=current_question,
        user_answer=user_answer,
        keyword_groups=keyword_groups,
        resume_text=resume_text,
        job_text=job_text,
        user_finished=user_finished,
    )
    return jsonify(result), 200


@keyword_bp.route("/api/keywords/equivalency/rewrite", methods=["POST"])
@require_auth
def generate_rewrites_endpoint():
    """POST /api/keywords/equivalency/rewrite — generate resume section rewrites.

    Body: {resolved_keywords: [...], resume_text: str, job_description: str}
    Response: {rewrites: [{section, original_text, proposed_text, keywords_addressed}]}
    """
    data = request.get_json(silent=True) or {}
    resolved = data.get("resolved_keywords") or []
    resume_text = (data.get("resume_text") or "").strip()
    job_text = (data.get("job_description") or "").strip()
    original_text = (data.get("original_text") or "").strip()

    if not resolved:
        return jsonify({"rewrites": []}), 200
    if not resume_text:
        return jsonify({"error": "resume_text is required"}), 400

    if not job_text:
        job_desc = JobDescription.get_latest_for_user(g.user_id)
        if job_desc:
            job_text = job_desc.text

    result = generate_rewrites(resolved, resume_text, job_text, original_text=original_text)

    # Auto-save to rewrite history so user can browse past suggestions
    resume_id = data.get("resume_id")
    job_id = data.get("job_id")
    if result.get("rewrites"):
        try:
            with get_db() as conn:
                conn.execute(
                    "INSERT INTO rewrite_suggestions_log "
                    "(user_id, resume_id, job_id, rewrites_json, resolved_keywords_json) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        g.user_id,
                        int(resume_id) if resume_id else None,
                        int(job_id) if job_id else None,
                        json.dumps(result["rewrites"]),
                        json.dumps(resolved),
                    ),
                )
                conn.commit()
        except Exception:
            pass  # history is best-effort

    return jsonify(result), 200


@keyword_bp.route("/api/keywords/equivalencies", methods=["POST"])
@require_auth
def save_equivalencies_endpoint():
    """POST /api/keywords/equivalencies — persist resolved equivalencies.

    Body: {resolved: [{keyword, equivalent, confidence, status}]}
    Response: {saved: int}
    """
    data = request.get_json(silent=True) or {}
    resolved = data.get("resolved") or []

    # Validate confidence field range for each entry
    for entry in resolved:
        conf = entry.get("confidence")
        if conf is not None:
            try:
                conf_f = float(conf)
            except (TypeError, ValueError):
                return jsonify({"error": "confidence must be a number between 0.5 and 1.0"}), 400
            if not (0.0 <= conf_f <= 1.0):
                return jsonify({"error": "confidence must be between 0.0 and 1.0"}), 400

    count = save_equivalencies(g.user_id, resolved)
    return jsonify({"saved": count}), 200


@keyword_bp.route("/api/keywords/equivalencies", methods=["GET"])
@require_auth
def get_equivalencies_endpoint():
    """GET /api/keywords/equivalencies — list all persisted equivalencies."""
    equivs = get_equivalencies(g.user_id)
    return jsonify({"equivalencies": equivs}), 200


@keyword_bp.route("/api/keywords/equivalency/match", methods=["POST"])
@require_auth
def match_equivalencies_endpoint():
    """POST /api/keywords/equivalency/match — exact + semantic match of missing keywords.

    Body: {missing_keywords: [str], job_description: str (optional)}
    Response: {
      exact_matches: [{keyword, equivalent_phrase, confidence, status}],
      suggestions:   [{keyword, saved_keyword, equivalent_phrase, confidence, rationale, status}],
      unmatched:     [str],
    }
    """
    data = request.get_json(silent=True) or {}
    missing = data.get("missing_keywords") or []
    job_text = (data.get("job_description") or "").strip()

    if not missing:
        return jsonify({"exact_matches": [], "suggestions": [], "unmatched": []}), 200

    if not job_text:
        job_desc = JobDescription.get_latest_for_user(g.user_id)
        if job_desc:
            job_text = job_desc.text

    # Step 1: exact match against saved equivalencies
    saved = get_equivalencies(g.user_id)
    still_missing, exact_resolved = apply_persisted_equivalencies(missing, saved)

    # Convert exact_resolved to consistent format
    exact_matches = [
        {
            "keyword": r["keyword"],
            "equivalent_phrase": r["equivalent"],
            "confidence": r.get("confidence", 0.9),
            "status": "equivalent",
        }
        for r in exact_resolved
    ]

    # Step 2: LLM semantic matching for keywords that didn't exact-match
    sem_result = suggest_semantic_matches(still_missing, saved, job_text)

    return jsonify({
        "exact_matches": exact_matches,
        "suggestions": sem_result.get("suggestions", []),
        "unmatched": sem_result.get("unmatched", still_missing),
    }), 200


@keyword_bp.route("/api/keywords/equivalencies/<keyword>", methods=["DELETE"])
@require_auth
def delete_equivalency_endpoint(keyword):
    """DELETE /api/keywords/equivalencies/<keyword> — remove one mapping."""
    deleted = delete_equivalency(g.user_id, keyword)
    if not deleted:
        return jsonify({"error": "Equivalency not found"}), 404
    return jsonify({"deleted": True}), 200


@keyword_bp.route("/api/keywords/rewrite-history", methods=["GET"])
@require_auth
def get_rewrite_history():
    """GET /api/keywords/rewrite-history — list past rewrite suggestion sets.

    Returns the 20 most recent rewrite sessions for this user.
    Response: {history: [{id, created_at, rewrite_count, keywords_addressed, rewrites}]}
    """
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, resume_id, job_id, rewrites_json, resolved_keywords_json, "
            "label, created_at "
            "FROM rewrite_suggestions_log WHERE user_id = ? "
            "ORDER BY created_at DESC LIMIT 20",
            (g.user_id,),
        ).fetchall()

    history = []
    for row in rows:
        try:
            rewrites = json.loads(row["rewrites_json"] or "[]")
            resolved = json.loads(row["resolved_keywords_json"] or "[]")
        except (json.JSONDecodeError, ValueError):
            rewrites, resolved = [], []
        history.append({
            "id": row["id"],
            "resume_id": row["resume_id"],
            "job_id": row["job_id"],
            "label": row["label"] or "",
            "created_at": row["created_at"],
            "rewrite_count": len(rewrites),
            "keywords_addressed": sorted({
                kw for r in resolved for kw in ([r.get("keyword")] if r.get("keyword") else [])
            }),
            "rewrites": rewrites,
        })
    return jsonify({"history": history}), 200


@keyword_bp.route("/api/keywords/ignores", methods=["GET"])
@require_auth
def get_ignored_keywords():
    """GET /api/keywords/ignores — list all ignored keywords for this user.

    Response: {ignored: [str]}
    """
    with get_db() as conn:
        rows = conn.execute(
            "SELECT keyword FROM keyword_ignores WHERE user_id = ? ORDER BY keyword",
            (g.user_id,),
        ).fetchall()
    return jsonify({"ignored": [r["keyword"] for r in rows]}), 200


@keyword_bp.route("/api/keywords/ignore", methods=["POST"])
@require_auth
def ignore_keywords():
    """POST /api/keywords/ignore — add keywords to the ignore list.

    Body: {keywords: [str]}
    Response: {saved: int}
    """
    data = request.get_json(silent=True) or {}
    keywords = [k.strip().lower() for k in (data.get("keywords") or []) if k and k.strip()]
    if not keywords:
        return jsonify({"saved": 0}), 200

    saved = 0
    with get_db() as conn:
        for kw in keywords:
            try:
                result = conn.execute(
                    "INSERT INTO keyword_ignores (user_id, keyword) VALUES (?, ?) "
                    "ON CONFLICT DO NOTHING",
                    (g.user_id, kw),
                )
                saved += result.rowcount
            except Exception:
                pass
        conn.commit()
    return jsonify({"saved": saved}), 200


@keyword_bp.route("/api/keywords/ignore/<path:keyword>", methods=["DELETE"])
@require_auth
def unignore_keyword(keyword):
    """DELETE /api/keywords/ignore/<keyword> — remove a keyword from the ignore list.

    Response: {deleted: bool}
    """
    kw = keyword.strip().lower()
    with get_db() as conn:
        conn.execute(
            "DELETE FROM keyword_ignores WHERE user_id = ? AND keyword = ?",
            (g.user_id, kw),
        )
        conn.commit()
    return jsonify({"deleted": True}), 200


@keyword_bp.route("/api/keywords/dispute", methods=["POST"])
@require_auth
def dispute_keyword():
    """POST /api/keywords/dispute — user disputes a keyword as already covered.

    Body: {keyword: str, resume_text: str, job_description: str (optional)}
    Response: {
      covered: bool,
      confidence: float,
      needs_interview: bool,
      rationale: str,
      suggested_equivalent: str | null,
    }
    """
    data = request.get_json(silent=True) or {}
    keyword = (data.get("keyword") or "").strip()
    resume_text = (data.get("resume_text") or "").strip()
    job_text = (data.get("job_description") or "").strip()

    if not keyword:
        return jsonify({"error": "keyword is required"}), 400
    if not resume_text:
        return jsonify({"error": "resume_text is required"}), 400

    if not job_text:
        job_desc = JobDescription.get_latest_for_user(g.user_id)
        if job_desc:
            job_text = job_desc.text

    fallback = {
        "covered": False,
        "confidence": 0.3,
        "needs_interview": True,
        "rationale": "Unable to evaluate automatically — please describe your experience.",
        "suggested_equivalent": None,
    }

    try:
        from smart_llm import call_direct

        prompt = f"""A resume reviewer is checking whether the keyword "{keyword}" is already \
covered by the candidate's resume using different terminology.

KEYWORD TO EVALUATE: {keyword}

JOB CONTEXT:
{job_text[:600]}

CANDIDATE RESUME (abbreviated):
{resume_text[:1500]}

Determine if the resume demonstrates equivalent experience for "{keyword}" even if \
that exact term isn't used.

Respond with ONLY valid JSON:
{{
  "covered": true/false,
  "confidence": 0.0-1.0,
  "needs_interview": true/false,
  "rationale": "<2-3 sentences explaining what you found or what's missing>",
  "suggested_equivalent": "<phrase from resume that is equivalent, or null>"
}}

Rules:
- covered=true only if resume clearly demonstrates the capability
- needs_interview=true if coverage is uncertain (confidence < 0.7)
- suggested_equivalent should be the actual phrase/technology from the resume"""

        raw = call_direct(prompt, max_tokens=300) or ""
        # Parse JSON response
        cleaned = raw.strip()
        for fence in ("```json", "```"):
            if fence in cleaned:
                start = cleaned.find(fence) + len(fence)
                end = cleaned.find("```", start)
                if end > start:
                    cleaned = cleaned[start:end].strip()
                    break
        import json as _json
        result = _json.loads(cleaned)

        # If covered with high confidence, auto-save the equivalency
        if result.get("covered") and result.get("confidence", 0) >= 0.75 and result.get("suggested_equivalent"):
            try:
                save_equivalencies(g.user_id, [{
                    "keyword": keyword,
                    "equivalent": result["suggested_equivalent"],
                    "confidence": result["confidence"],
                    "status": "equivalent",
                }])
            except Exception:
                pass

        return jsonify(result), 200

    except Exception as exc:
        logger.warning("dispute keyword evaluation failed: %s", exc)
        return jsonify(fallback), 200
