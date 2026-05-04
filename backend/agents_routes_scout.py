"""Job Scout and Application Tracker routes."""

import logging
import os
import uuid

from agents import get_app_tracker, get_job_scout
from agents_routes_common import _LLM_LIMIT, agents_bp
from auth import require_auth
from flask import current_app, g, jsonify, request
from job_scraper import scrape_job_url, scrape_multiple
from models import ResumeVersion, get_db
from nlp_engine import extract_skill_phrases
from werkzeug.utils import secure_filename

from rate_limit import limiter

_RESUME_ALLOWED = {".pdf", ".docx", ".doc", ".txt"}

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Job Scout routes
# ──────────────────────────────────────────────


@agents_bp.route("/api/agents/scout/search", methods=["POST"])
@require_auth
@limiter.limit(_LLM_LIMIT)
def scout_search():
    user_id = g.user_id

    data = request.get_json(silent=True) or {}
    criteria_id = data.get("criteria_id")

    scout = get_job_scout()
    job_id = scout.search_jobs(user_id, criteria_id=criteria_id)
    return jsonify({"message": "Job search started", "job_id": job_id}), 202


@agents_bp.route("/api/agents/scout/postings", methods=["GET"])
@require_auth
def scout_list_postings():
    user_id = g.user_id

    status = request.args.get("status")
    try:
        min_score = float(request.args.get("min_score", 0))
        limit = int(request.args.get("limit", 50))
    except ValueError:
        return jsonify({"error": "Invalid min_score or limit"}), 400

    scout = get_job_scout()
    postings = scout.get_postings(user_id, status=status, min_score=min_score, limit=limit)
    return jsonify({"postings": postings, "count": len(postings)}), 200


@agents_bp.route("/api/agents/scout/postings/<posting_id>", methods=["GET"])
@require_auth
def scout_get_posting(posting_id):
    user_id = g.user_id

    scout = get_job_scout()
    posting = scout.get_posting(posting_id, user_id=user_id)
    if not posting:
        return jsonify({"error": "Posting not found"}), 404
    return jsonify(posting), 200


@agents_bp.route("/api/agents/scout/postings/<posting_id>", methods=["PUT"])
@require_auth
def scout_update_posting(posting_id):
    user_id = g.user_id

    data = request.get_json(silent=True) or {}
    scout = get_job_scout()
    result = scout.update_posting(posting_id, data, user_id=user_id)
    if not result:
        return jsonify({"error": "No valid fields to update"}), 400
    return jsonify(result), 200


@agents_bp.route("/api/agents/scout/postings/<posting_id>", methods=["DELETE"])
@require_auth
def scout_delete_posting(posting_id):
    user_id = g.user_id

    scout = get_job_scout()
    scout.delete_posting(posting_id, user_id=user_id)
    return jsonify({"message": "Posting deleted"}), 200


@agents_bp.route("/api/agents/scout/postings", methods=["POST"])
@require_auth
def scout_add_posting():
    user_id = g.user_id

    data = request.get_json(silent=True) or {}
    if not data.get("title"):
        return jsonify({"error": "Title is required"}), 400

    scout = get_job_scout()
    posting = scout.add_posting(user_id, data)
    return jsonify(posting), 201


@agents_bp.route("/api/agents/scout/postings/<posting_id>/rescore", methods=["POST"])
@require_auth
@limiter.limit(_LLM_LIMIT)
def scout_rescore_posting(posting_id):
    user_id = g.user_id

    scout = get_job_scout()
    result = scout.rescore_posting(posting_id, user_id)
    if not result:
        return jsonify({"error": "Posting not found"}), 404
    return jsonify(result), 200


@agents_bp.route("/api/agents/scout/criteria", methods=["POST"])
@require_auth
def scout_save_criteria():
    user_id = g.user_id

    data = request.get_json(silent=True) or {}
    scout = get_job_scout()
    criteria = scout.save_criteria(user_id, data)
    return jsonify(criteria), 201


@agents_bp.route("/api/agents/scout/criteria", methods=["GET"])
@require_auth
def scout_list_criteria():
    user_id = g.user_id

    scout = get_job_scout()
    criteria = scout.get_criteria(user_id)
    return jsonify({"criteria": criteria}), 200


@agents_bp.route("/api/agents/scout/skill-demand", methods=["GET"])
@require_auth
def scout_skill_demand():
    """Aggregate NLP skill extraction across all postings for demand analysis."""
    user_id = g.user_id

    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, title, description FROM job_postings "
            "WHERE user_id = ? AND description IS NOT NULL AND description != ''",
            (user_id,),
        ).fetchall()

    if not rows:
        return (
            jsonify(
                {
                    "skills": [],
                    "total_postings": 0,
                    "user_skills_count": 0,
                    "coverage_pct": 0,
                }
            ),
            200,
        )

    skill_postings = {}  # skill → set of posting_ids
    total = len(rows)

    for row in rows:
        desc = row["description"] or ""
        if len(desc) < 20:
            continue
        phrases = extract_skill_phrases(desc, use_llm_fallback=False)
        for phrase in phrases:
            p = phrase.strip().lower()
            if p:
                skill_postings.setdefault(p, set()).add(row["id"])

    # Load user's resume skills for coverage comparison
    user_skills = set()
    with get_db() as conn:
        rrow = conn.execute(
            "SELECT parsed_text FROM resume_versions WHERE user_id = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    if rrow and rrow["parsed_text"]:
        user_skills = {
            p.lower() for p in extract_skill_phrases(rrow["parsed_text"], use_llm_fallback=False)
        }

    sorted_skills = sorted(skill_postings.items(), key=lambda x: -len(x[1]))[:40]

    return (
        jsonify(
            {
                "skills": [
                    {
                        "skill": s,
                        "posting_count": len(pids),
                        "pct_of_postings": round(len(pids) / total * 100, 1),
                        "user_has": s in user_skills,
                    }
                    for s, pids in sorted_skills
                ],
                "total_postings": total,
                "user_skills_count": len(user_skills),
                "coverage_pct": (
                    round(
                        sum(1 for s, _ in sorted_skills if s in user_skills)
                        / len(sorted_skills)
                        * 100,
                        1,
                    )
                    if sorted_skills
                    else 0
                ),
            }
        ),
        200,
    )


# ──────────────────────────────────────────────
# Job URL Scraper (Phase 13.2)
# ──────────────────────────────────────────────


@agents_bp.route("/api/agents/scout/scrape-url", methods=["POST"])
@require_auth
def scout_scrape_url():
    """Scrape a single job URL and return structured data."""
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "url is required"}), 400

    result = scrape_job_url(url)
    if result.get("error"):
        return jsonify({"posting": result, "warning": result["error"]}), 422
    return jsonify({"posting": result}), 200


@agents_bp.route("/api/agents/scout/import-url", methods=["POST"])
@require_auth
def scout_import_url():
    """Scrape a URL, score against profile, and save as posting."""
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "url is required"}), 400

    scraped = scrape_job_url(url)
    if not scraped.get("title") and not scraped.get("description"):
        return jsonify({"error": "Could not extract job data from URL"}), 400

    scout = get_job_scout()
    posting_id = scout.import_scraped_posting(g.user_id, scraped)
    return jsonify({"posting_id": posting_id, "scraped": scraped}), 201


@agents_bp.route("/api/agents/scout/bulk-import", methods=["POST"])
@require_auth
def scout_bulk_import():
    """Scrape and import multiple URLs."""
    data = request.get_json(silent=True) or {}
    urls = data.get("urls", [])
    if not urls or not isinstance(urls, list):
        return jsonify({"error": "urls array is required"}), 400

    scraped_list = scrape_multiple(urls[:20])  # Cap at 20
    scout = get_job_scout()
    imported = []
    errors = []
    for scraped in scraped_list:
        if not scraped.get("title") and not scraped.get("description"):
            errors.append({"url": scraped.get("url"), "error": scraped.get("error", "No data")})
            continue
        pid = scout.import_scraped_posting(g.user_id, scraped)
        imported.append({"posting_id": pid, "title": scraped.get("title")})

    return (
        jsonify({"imported": imported, "errors": errors, "count": len(imported)}),
        201,
    )


# ──────────────────────────────────────────────
# Applied-resume attachment
# ──────────────────────────────────────────────

@agents_bp.route("/api/agents/scout/postings/<posting_id>/resume", methods=["POST"])
@require_auth
def attach_posting_resume(posting_id):
    """Upload the resume used for this application.

    Parses the file, stores it as a ResumeVersion, and saves the version ID
    in job_postings.tailored_version_id.  Replaces any previously attached resume.
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM job_postings WHERE id = ? AND user_id = ?",
            (posting_id, g.user_id),
        ).fetchone()
    if not row:
        return jsonify({"error": "Posting not found"}), 404

    if "file" not in request.files:
        return jsonify({"error": "No file provided (field name: 'file')"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in _RESUME_ALLOWED:
        return jsonify({"error": f"Unsupported type. Use: {', '.join(sorted(_RESUME_ALLOWED))}"}), 400

    # Save to uploads folder
    filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
    upload_dir = current_app.config.get("UPLOAD_FOLDER", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, filename)
    file.save(file_path)

    # Parse text
    try:
        from utils import process_resume
        parsed = process_resume(file_path)
        resume_text = parsed.get("text", "")
    except Exception as e:
        logger.warning("Resume parse failed: %s", e)
        resume_text = ""

    version = ResumeVersion.create(
        user_id=g.user_id,
        source="applied_resume",
        file_name=file.filename,
        parsed_text=resume_text,
        source_id=posting_id,
        file_type=ext.lstrip("."),
    )

    with get_db() as conn:
        conn.execute(
            "UPDATE job_postings SET tailored_version_id = ? WHERE id = ? AND user_id = ?",
            (str(version.id), posting_id, g.user_id),
        )
        conn.commit()

    return jsonify({
        "version_id": version.id,
        "file_name": version.file_name,
        "file_type": version.file_type,
        "has_text": bool(resume_text),
        "char_count": len(resume_text),
    }), 201


@agents_bp.route("/api/agents/scout/postings/<posting_id>/resume", methods=["GET"])
@require_auth
def get_posting_resume(posting_id):
    """Return metadata for the resume attached to this posting (if any)."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT tailored_version_id FROM job_postings WHERE id = ? AND user_id = ?",
            (posting_id, g.user_id),
        ).fetchone()
    if not row:
        return jsonify({"error": "Posting not found"}), 404

    vid = row["tailored_version_id"]
    if not vid:
        return jsonify({"resume": None}), 200

    rv = ResumeVersion.get_by_id(int(vid))
    if not rv:
        return jsonify({"resume": None}), 200

    return jsonify({"resume": {
        "version_id": rv.id,
        "file_name": rv.file_name,
        "file_type": rv.file_type,
        "char_count": len(rv.parsed_text or ""),
    }}), 200
