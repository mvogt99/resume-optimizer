"""Profile routes — LinkedIn import, deep profile, deep interview, graph queries."""

import logging
import os
import re
import uuid

import linkedin_cache
from auth import require_auth
from flask import Blueprint, current_app, g, jsonify, request
from utils import process_linkedin_profile
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

profile_bp = Blueprint("profile", __name__)

LINKEDIN_ALLOWED_EXTENSIONS = {".json", ".xml", ".docx", ".doc", ".pdf", ".txt"}


@profile_bp.route("/api/import/linkedin", methods=["POST"])
@require_auth
def import_linkedin_profile():
    linkedin_path = None
    if request.is_json:
        data = request.get_json()
        linkedin_path = data.get("linkedin_path")

    try:
        from linkedin_parser import get_default_linkedin_path, parse_linkedin_json

        profile = process_linkedin_profile(linkedin_path)
        raw_path = linkedin_path or get_default_linkedin_path()
        raw = parse_linkedin_json(raw_path)
        linkedin_cache.set_profile(g.user_id, profile, raw)
    except Exception as e:
        logger.exception("Unhandled error in route: %s", e)
        return jsonify({"error": "Internal server error"}), 500

    return (
        jsonify(
            {
                "message": "LinkedIn profile imported successfully",
                "skills_count": len(profile.get("skills", [])),
                "experience_count": len(profile.get("experience", [])),
                "education_count": len(profile.get("education", [])),
                "recommendations_count": len(profile.get("recommendations", [])),
            }
        ),
        200,
    )


@profile_bp.route("/api/import/linkedin/upload", methods=["POST"])
@require_auth
def upload_linkedin_profile():
    """Import LinkedIn profile from an uploaded file (JSON, XML, DOCX, PDF, TXT)."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    # Handle browser download duplicates like "resume.docx-1", "resume.pdf (2)", etc.
    if ext not in LINKEDIN_ALLOWED_EXTENSIONS:
        stripped = re.sub(r'[-\s]\(?\d+\)?$', '', ext)
        if stripped in LINKEDIN_ALLOWED_EXTENSIONS:
            ext = stripped
    if ext not in LINKEDIN_ALLOWED_EXTENSIONS:
        return (
            jsonify(
                {
                    "error": "File type not allowed. "
                    f"Accepted: {', '.join(sorted(LINKEDIN_ALLOWED_EXTENSIONS))}"
                }
            ),
            400,
        )

    # Save uploaded file (use cleaned ext so parser gets correct extension)
    filename = secure_filename(f"{uuid.uuid4()}_linkedin{ext}")
    upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
    file_path = os.path.join(upload_folder, filename)
    file.save(file_path)

    try:
        from linkedin_profile_upload import parse_linkedin_upload

        profile = parse_linkedin_upload(file_path)

        # Also set as raw for endorsement-weighted features
        linkedin_cache.set_profile(g.user_id, profile, profile)
    except Exception as e:
        logger.exception("LinkedIn profile upload parse failed: %s", e)
        # Clean up on failure
        if os.path.exists(file_path):
            os.remove(file_path)
        return jsonify({"error": "Internal server error"}), 500

    return (
        jsonify(
            {
                "message": "LinkedIn profile uploaded and imported successfully",
                "format": ext.lstrip("."),
                "skills_count": len(profile.get("skills", [])),
                "experience_count": len(profile.get("experience", [])),
                "education_count": len(profile.get("education", [])),
                "recommendations_count": len(profile.get("recommendations", [])),
            }
        ),
        200,
    )


@profile_bp.route("/api/profile/linkedin", methods=["GET"])
@require_auth
def get_linkedin_profile():
    cached = linkedin_cache.get_profile(g.user_id)
    if cached is not None:
        return jsonify(cached), 200

    try:
        profile = process_linkedin_profile()
        return jsonify(profile), 200
    except Exception as e:
        logger.exception("Unhandled error in route: %s", e)
        return jsonify({"error": "Internal server error"}), 500


# --- Deep Profile ---


@profile_bp.route("/api/deep-profile/build", methods=["POST"])
@require_auth
def build_deep_profile():
    from deep_profile import get_deep_profile_engine

    engine = get_deep_profile_engine()
    profile = engine.build_profile(g.user_id)
    meta = engine.get_profile_with_meta(g.user_id)
    return (
        jsonify(
            {
                "profile": profile,
                "source_summary": meta.get("source_summary", "") if meta else "",
                "updated_at": meta.get("updated_at", "") if meta else "",
            }
        ),
        200,
    )


@profile_bp.route("/api/deep-profile", methods=["GET"])
@require_auth
def get_deep_profile():
    from deep_profile import get_deep_profile_engine

    engine = get_deep_profile_engine()
    meta = engine.get_profile_with_meta(g.user_id)
    if not meta:
        return jsonify({"error": "No deep profile found. Build one first."}), 404
    return jsonify(meta), 200


@profile_bp.route("/api/deep-profile/status", methods=["GET"])
@require_auth
def deep_profile_status():
    """Return staleness info for the current deep profile."""
    from deep_profile_staleness import get_profile_status

    status = get_profile_status(g.user_id)
    if not status:
        return jsonify({"error": "No deep profile found. Build one first."}), 404
    return jsonify(status), 200


@profile_bp.route("/api/deep-profile/refresh", methods=["POST"])
@require_auth
def deep_profile_refresh():
    """Rebuild deep profile if stale; return 200 (rebuilt) or 200 fresh=True."""
    from deep_profile import get_deep_profile_engine
    from deep_profile_staleness import check_staleness, clear_staleness, compute_source_hash

    status = check_staleness(g.user_id)
    if not status.get("is_stale") and status.get("stored_hash"):
        return jsonify({"fresh": True, "message": "Profile is up-to-date"}), 200

    engine = get_deep_profile_engine()
    profile = engine.build_profile(g.user_id)
    new_hash = compute_source_hash(g.user_id)
    clear_staleness(g.user_id, new_hash)
    return jsonify({"fresh": False, "rebuilt": True, "profile": profile}), 200


@profile_bp.route("/api/deep-profile/role-synthesis", methods=["POST"])
@require_auth
def deep_profile_role_synthesis():
    from deep_profile import get_deep_profile_engine

    data = request.get_json() or {}
    job_text = data.get("job_text", "")
    if not job_text or len(job_text) < 50:
        return jsonify({"error": "job_text required (min 50 chars)"}), 400

    engine = get_deep_profile_engine()
    synthesis = engine.get_role_synthesis(g.user_id, job_text)
    if not synthesis:
        return jsonify({"error": "No deep profile found. Build one first."}), 404
    return jsonify(synthesis), 200


# --- Deep Interview ---


@profile_bp.route("/api/deep-interview/start", methods=["POST"])
@require_auth
def start_deep_interview():
    from deep_interview import get_deep_interviewer

    data = request.get_json() or {}
    mode = data.get("mode", "comprehensive")
    job_text = data.get("job_text")

    interviewer = get_deep_interviewer()
    result = interviewer.start_session(g.user_id, mode=mode, job_text=job_text)
    return jsonify(result), 200


@profile_bp.route("/api/deep-interview/message", methods=["POST"])
@require_auth
def send_deep_interview_message():
    from deep_interview import get_deep_interviewer

    data = request.get_json() or {}
    session_id = data.get("session_id")
    message = data.get("message", "")
    if not session_id or not message:
        return jsonify({"error": "session_id and message required"}), 400

    interviewer = get_deep_interviewer()
    result = interviewer.send_message(session_id, message, user_id=g.user_id)
    if "error" in result:
        return jsonify(result), 404
    return jsonify(result), 200


@profile_bp.route("/api/deep-interview/<session_id>/status", methods=["GET"])
@require_auth
def get_deep_interview_status(session_id):
    from deep_interview import get_deep_interviewer

    interviewer = get_deep_interviewer()
    result = interviewer.get_status(session_id, user_id=g.user_id)
    if "error" in result:
        return jsonify(result), 404
    return jsonify(result), 200


@profile_bp.route("/api/deep-interview/<session_id>/finalize", methods=["POST"])
@require_auth
def finalize_deep_interview(session_id):
    from deep_interview import get_deep_interviewer

    interviewer = get_deep_interviewer()
    result = interviewer.finalize_session(session_id, user_id=g.user_id)
    if "error" in result:
        return jsonify(result), 404
    return jsonify(result), 200


@profile_bp.route("/api/deep-interview/<session_id>/insights", methods=["GET"])
@require_auth
def get_deep_interview_insights(session_id):
    from deep_interview import get_deep_interviewer

    interviewer = get_deep_interviewer()
    result = interviewer.get_insights(session_id)
    if "error" in result:
        return jsonify(result), 404
    return jsonify(result), 200
