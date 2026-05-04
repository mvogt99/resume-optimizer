"""Resume routes — upload, download, optimize, score.

save-version, pdf-export, interview-guide, from-linkedin, skills-gap, gdrive, and
versions routes are in resume_routes_detail.py (side-effect import).
"""

import json
import logging
import os
import uuid

import linkedin_cache
from auth import require_auth
from flask import Blueprint, current_app, g, jsonify, request, send_file
from models import JobDescription, Resume, ResumeVersion, get_db
from nlp_engine import extract_skill_phrases
from utils import optimize_resume, process_linkedin_profile, process_resume
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

resume_bp = Blueprint("resume", __name__)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}
MULTI_RESUME_MAX_FILES = 10


@resume_bp.route("/api/resume/upload", methods=["POST"])
@require_auth
def upload_resume():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return (
            jsonify(
                {
                    "error": "File type not allowed. "
                    f"Accepted: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
                }
            ),
            400,
        )

    if file:
        filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
        file_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
        file.save(file_path)

        resume = Resume.create(g.user_id, filename, file_path)
        return (
            jsonify(
                {
                    "message": "Resume uploaded successfully",
                    "resume_id": str(resume.id),
                }
            ),
            201,
        )


@resume_bp.route("/api/resume/upload-multiple", methods=["POST"])
@require_auth
def upload_multiple_resumes():
    """Upload multiple resume files at once to provide richer context for optimization."""
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files provided. Use 'files' field."}), 400

    if len(files) > MULTI_RESUME_MAX_FILES:
        return (
            jsonify({"error": f"Too many files. Maximum {MULTI_RESUME_MAX_FILES} at once."}),
            400,
        )

    results = []
    errors = []

    for file in files:
        if not file.filename:
            continue

        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            errors.append({"file": file.filename, "error": f"Unsupported type: {ext}"})
            continue

        if file.content_length and file.content_length > 16 * 1024 * 1024:
            errors.append({"file": file.filename, "error": "File exceeds 16MB limit"})
            continue

        filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
        file_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
        file.save(file_path)

        resume = Resume.create(g.user_id, file.filename, file_path)
        results.append({"resume_id": str(resume.id), "filename": file.filename})

    if not results and errors:
        return jsonify({"error": "No valid files uploaded", "details": errors}), 400

    return (
        jsonify(
            {
                "message": f"Uploaded {len(results)} resume(s)",
                "resumes": results,
                "errors": errors if errors else None,
            }
        ),
        201,
    )


@resume_bp.route("/api/job-description/upload", methods=["POST"])
@require_auth
def upload_job_description():
    job_text = None

    if request.is_json:
        data = request.get_json()
        job_text = data.get("job_text")
    elif request.files.get("file"):
        f = request.files["file"]
        job_text = f.read().decode("utf-8", errors="replace").strip()
    elif request.form.get("job_text"):
        job_text = request.form["job_text"]

    if not job_text:
        return jsonify({"error": "Job description is required"}), 400

    if len(job_text.strip()) < 50:
        return jsonify({"error": "Job description too short (minimum 50 characters)"}), 400

    job_desc = JobDescription.create(g.user_id, job_text)
    return (
        jsonify(
            {
                "message": "Job description uploaded successfully",
                "job_id": str(job_desc.id),
            }
        ),
        201,
    )


@resume_bp.route("/api/optimize-resume/<resume_id>", methods=["POST"])
@require_auth
def optimize_resume_endpoint(resume_id):
    resume = Resume.get_by_id(resume_id)
    if not resume or int(resume.user_id) != g.user_id:
        return jsonify({"error": "Resume not found or unauthorized"}), 404

    job_desc = JobDescription.get_latest_for_user(g.user_id)
    if not job_desc:
        return jsonify({"error": "No job description found"}), 404

    processed_resume = process_resume(resume.file_path)
    job_keywords = extract_skill_phrases(job_desc.text, use_llm_fallback=False)

    additional_resume_ids = []
    if request.is_json:
        data = request.get_json() or {}
        additional_resume_ids = data.get("additional_resume_ids", [])

    if additional_resume_ids:
        for extra_id in additional_resume_ids:
            extra_resume = Resume.get_by_id(extra_id)
            if extra_resume and int(extra_resume.user_id) == g.user_id:
                extra_processed = process_resume(extra_resume.file_path)
                processed_resume["text"] += (
                    f"\n\n--- Additional Resume: {extra_resume.filename} ---\n"
                    + extra_processed.get("text", "")
                )
                existing_skills = {s.lower() for s in processed_resume.get("skills", [])}
                for skill in extra_processed.get("skills", []):
                    if skill.lower() not in existing_skills:
                        processed_resume["skills"].append(skill)
                        existing_skills.add(skill.lower())
                processed_resume.setdefault("experience", []).extend(
                    extra_processed.get("experience", [])
                )
                processed_resume.setdefault("education", []).extend(
                    extra_processed.get("education", [])
                )

    try:
        from skills_enrichment import enrich_resume_data_with_confirmed_skills
        processed_resume = enrich_resume_data_with_confirmed_skills(processed_resume, g.user_id)
    except Exception:
        pass

    deep_profile = None
    try:
        from deep_profile import get_deep_profile_engine
        dp = get_deep_profile_engine().get_profile_with_meta(g.user_id)
        if dp:
            deep_profile = dp.get("profile", dp)
    except Exception:
        pass

    cached_raw = linkedin_cache.get_raw(g.user_id)

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
        processed_resume,
        job_keywords,
        job_text=job_desc.text,
        linkedin_profile=cached_raw,
        deep_profile=deep_profile,
        equivalencies=user_equivalencies,
        ignored_keywords=user_ignored,
    )

    resume_source = "upload"
    if "linkedin" in (resume.filename or "").lower():
        resume_source = "linkedin"

    response_data = {
        "resume_id": resume.id,
        "optimized_resume": optimized,
        "keywords_added": len(optimized.get("added_keywords", [])),
        "relevance_score": optimized.get("score", 0),
        "ats_compliance_score": optimized.get("score", 0),
        "score_breakdown": optimized.get("score_breakdown", {}),
        "accomplishments": optimized.get("accomplishments", []),
        "recommendations": optimized.get("recommendations", []),
        "original_resume_text": optimized.get("original_text", ""),
        "job_description_text": job_desc.text,
        "sections_found": optimized.get("sections_found", {}),
        "skill_phrases_matched": optimized.get("skill_phrases_matched", []),
        "resume_source": resume_source,
        "resume_name": resume.filename,
    }
    if additional_resume_ids:
        response_data["additional_resumes_merged"] = len(additional_resume_ids)

    return jsonify(response_data), 200


@resume_bp.route("/api/resume/download/<resume_id>", methods=["GET"])
@require_auth
def download_resume_endpoint(resume_id):
    """Download optimized resume as PDF or DOCX."""
    fmt = request.args.get("format", "pdf").lower()
    if fmt not in ("pdf", "docx"):
        return jsonify({"error": "Format must be 'pdf' or 'docx'"}), 400

    version = ResumeVersion.get_by_id(resume_id)
    if version and int(version.user_id) == g.user_id:
        text = version.parsed_text
    else:
        resume = Resume.get_by_id(resume_id)
        if not resume or int(resume.user_id) != g.user_id:
            return jsonify({"error": "Resume not found"}), 404
        if resume.file_path:
            parsed = process_resume(resume.file_path)
            text = parsed.get("text", "") if isinstance(parsed, dict) else str(parsed)
        else:
            text = ""

    if not text:
        return jsonify({"error": "No resume text available"}), 404

    try:
        if fmt == "pdf":
            from resume_export import export_resume_pdf
            buffer = export_resume_pdf(text)
            mimetype = "application/pdf"
            filename = f"resume_{resume_id}.pdf"
        else:
            from resume_export import export_resume_docx
            buffer = export_resume_docx(text)
            mimetype = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            filename = f"resume_{resume_id}.docx"

        return send_file(buffer, mimetype=mimetype, as_attachment=True, download_name=filename)
    except ImportError as e:
        return jsonify({"error": f"Export dependency missing: {e}"}), 500
    except Exception as e:
        return jsonify({"error": f"Export failed: {e}"}), 500


@resume_bp.route("/api/resume/export-text", methods=["POST"])
@require_auth
def export_text_endpoint():
    """Export arbitrary resume text as PDF or DOCX (text lives only in browser)."""
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    fmt = (data.get("format") or "pdf").lower()

    if not text:
        return jsonify({"error": "text is required"}), 400
    if fmt not in ("pdf", "docx"):
        return jsonify({"error": "format must be 'pdf' or 'docx'"}), 400

    try:
        if fmt == "pdf":
            from resume_export import export_resume_pdf
            buffer = export_resume_pdf(text)
            mimetype = "application/pdf"
            filename = "optimized_resume.pdf"
        else:
            from resume_export import export_resume_docx
            buffer = export_resume_docx(text)
            mimetype = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            filename = "optimized_resume.docx"

        return send_file(buffer, mimetype=mimetype, as_attachment=True, download_name=filename)
    except ImportError as e:
        return jsonify({"error": f"Export dependency missing: {e}"}), 500
    except Exception as e:
        logger.exception("export_text_endpoint failed: %s", e)
        return jsonify({"error": f"Export failed: {e}"}), 500


@resume_bp.route("/api/resume/score-text", methods=["POST"])
@require_auth
def score_text_endpoint():
    """Score arbitrary resume text against a job description."""
    from nlp_engine import analyze_resume_vs_job, extract_skill_phrases
    from resume_scorer import score_resume

    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    job_text = (data.get("job_description") or "").strip()

    if not text:
        return jsonify({"error": "text is required"}), 400

    if not job_text:
        job_desc = JobDescription.get_latest_for_user(g.user_id)
        if not job_desc:
            return jsonify({"error": "No job description found"}), 400
        job_text = job_desc.text or ""

    user_equivalencies = []
    try:
        from keyword_equivalency import get_equivalencies
        user_equivalencies = get_equivalencies(g.user_id)
    except Exception:
        pass

    ignored_keywords: set = set()
    try:
        from models import get_db as _get_db
        with _get_db() as _conn:
            _rows = _conn.execute(
                "SELECT keyword FROM keyword_ignores WHERE user_id = ?", (g.user_id,)
            ).fetchall()
        ignored_keywords = {r["keyword"].lower() for r in _rows}
    except Exception:
        pass

    linkedin_raw = linkedin_cache.get_raw(g.user_id)

    try:
        job_keywords = extract_skill_phrases(job_text)
        resume_data = {"text": text, "skills": [], "experience": [], "education": []}
        result = score_resume(resume_data, job_keywords, job_text=job_text,
                              linkedin_profile=linkedin_raw,
                              equivalencies=user_equivalencies,
                              ignored_keywords=ignored_keywords)
        return jsonify({
            "ats_score": result.get("score", 0),
            "score_breakdown": result.get("score_breakdown", {}),
            "matching_keywords": result.get("matching_keywords", []),
            "missing_keywords": result.get("missing_keywords", []),
            "missing_skills": result.get("missing_skills", []),
        }), 200
    except Exception as e:
        logger.exception("score_text_endpoint failed: %s", e)
        return jsonify({"error": f"Scoring failed: {e}"}), 500


@resume_bp.route("/api/resume/save-version", methods=["POST"])
@require_auth
def save_version_endpoint():
    """Save arbitrary resume text as a new resume version in the database."""
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    label = (data.get("label") or "ATS Improved").strip()
    source = (data.get("source") or "ats_improvement").strip()

    if not text:
        return jsonify({"error": "text is required"}), 400

    try:
        version = ResumeVersion.create(
            user_id=g.user_id,
            source=source,
            source_id=None,
            file_name=f"{label}.txt",
            file_type="txt",
            parsed_text=text,
            metadata_json=json.dumps({"label": label, "char_count": len(text)}),
        )
        return jsonify({"version_id": version.id, "message": "Resume version saved."}), 201
    except Exception as e:
        logger.exception("save_version_endpoint failed: %s", e)
        return jsonify({"error": f"Save failed: {e}"}), 500


@resume_bp.route("/api/resumes/<resume_id>/export/pdf", methods=["GET"])
@require_auth
def export_resume_as_pdf(resume_id):
    """Export a resume version (or uploaded resume) as a PDF attachment."""
    version = ResumeVersion.get_by_id(resume_id)
    if version and int(version.user_id) == g.user_id:
        text = version.parsed_text
    else:
        resume = Resume.get_by_id(resume_id)
        if not resume or int(resume.user_id) != g.user_id:
            return jsonify({"error": "Resume not found or unauthorized"}), 404
        if resume.file_path:
            parsed = process_resume(resume.file_path)
            text = parsed.get("text", "") if isinstance(parsed, dict) else str(parsed)
        else:
            text = ""

    if not text:
        return jsonify({"error": "No resume text available for export"}), 404

    try:
        from resume_export import export_resume_pdf

        buffer = export_resume_pdf(text)
        return send_file(
            buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"resume_{resume_id}.pdf",
        )
    except ImportError as e:
        return jsonify({"error": f"PDF export dependency missing: {e}"}), 500
    except Exception as e:
        logger.exception("PDF export failed for resume %s: %s", resume_id, e)
        return jsonify({"error": "PDF export failed"}), 500
