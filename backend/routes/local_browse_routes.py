"""Local filesystem browse/import and optimize-from-version endpoints."""

import json
import logging
import os
from pathlib import Path

import linkedin_cache
from auth import require_auth
from flask import Blueprint, g, jsonify, request
from models import JobDescription, ResumeVersion, get_db
from nlp_engine import extract_skill_phrases
from utils import optimize_resume, process_resume

logger = logging.getLogger(__name__)

local_browse_bp = Blueprint("local_browse", __name__)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}
HOME = Path.home()


def _safe_resolve(path_str: str) -> Path | None:
    """Resolve path and verify it stays within HOME. Returns None on violation."""
    try:
        resolved = Path(path_str).expanduser().resolve()
    except Exception:
        return None
    if not resolved.is_relative_to(HOME):
        return None
    return resolved


def _default_browse_path() -> Path:
    """Return the best default starting directory for resume browsing."""
    for candidate in ("Downloads", "Documents", "Desktop"):
        p = HOME / candidate
        if p.is_dir():
            return p
    return HOME


# ── GET /api/resumes/local-browse ─────────────────────────────────────────────


@local_browse_bp.route("/api/resumes/local-browse", methods=["GET"])
@require_auth
def browse_local_folder():
    """List directories and resume files within a local path (must be under HOME).

    Query params:
      path  — absolute or ~ path to browse (default: ~/Downloads or ~/Documents)

    Returns JSON:
      {path, parent_path, dirs: [{name, path}], files: [{name, path, size_kb}]}
    """
    path_param = request.args.get("path", "")
    if path_param:
        target = _safe_resolve(path_param)
        if target is None:
            return jsonify({"error": "Path is outside your home directory"}), 403
        if not target.is_dir():
            return jsonify({"error": "Path is not a directory"}), 400
    else:
        target = _default_browse_path()

    dirs = []
    files = []
    try:
        entries = sorted(target.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
        for entry in entries:
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                dirs.append({"name": entry.name, "path": str(entry)})
            elif entry.is_file() and entry.suffix.lower() in ALLOWED_EXTENSIONS:
                size_kb = round(entry.stat().st_size / 1024, 1)
                files.append({"name": entry.name, "path": str(entry), "size_kb": size_kb})
    except PermissionError:
        return jsonify({"error": "Permission denied reading directory"}), 403

    parent = str(target.parent) if target != HOME else None

    return jsonify({
        "path": str(target),
        "parent_path": parent,
        "home_path": str(HOME),
        "dirs": dirs,
        "files": files,
    }), 200


# ── POST /api/resumes/local-import ────────────────────────────────────────────


@local_browse_bp.route("/api/resumes/local-import", methods=["POST"])
@require_auth
def import_local_file():
    """Import a resume file from the local filesystem into the database.

    Body JSON:
      file_path  — absolute path to the file (must be under HOME)

    Returns:
      {version_id, file_name, text_preview}
    """
    data = request.get_json(silent=True) or {}
    file_path_str = data.get("file_path", "")
    if not file_path_str:
        return jsonify({"error": "file_path is required"}), 400

    resolved = _safe_resolve(file_path_str)
    if resolved is None:
        return jsonify({"error": "Path is outside your home directory"}), 403
    if not resolved.is_file():
        return jsonify({"error": "File not found"}), 404
    if resolved.suffix.lower() not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"Unsupported file type: {resolved.suffix}"}), 400

    try:
        parsed = process_resume(str(resolved))
    except Exception as exc:
        logger.error("Failed to parse local file %s: %s", resolved, exc)
        return jsonify({"error": "Failed to parse file"}), 500

    metadata = {"local_path": str(resolved), "size_kb": round(resolved.stat().st_size / 1024, 1)}
    version = ResumeVersion.create(
        user_id=g.user_id,
        source="local_file",
        source_id=str(resolved),
        file_name=resolved.name,
        file_type=resolved.suffix.lstrip("."),
        parsed_text=parsed.get("text", ""),
        metadata_json=json.dumps(metadata),
    )

    return jsonify({
        "version_id": version.id,
        "file_name": version.file_name,
        "text_preview": (version.parsed_text or "")[:200],
    }), 201


# ── POST /api/optimize-resume/from-version/<version_id> ───────────────────────


@local_browse_bp.route(
    "/api/optimize-resume/from-version/<int:version_id>", methods=["POST"]
)
@require_auth
def optimize_from_version(version_id):
    """Optimize a resume version against the user's current job description.

    Uses parsed_text from resume_versions — no file path needed.
    Returns the same response shape as POST /api/optimize-resume/<resume_id>.
    """
    try:
        version = ResumeVersion.get_by_id(version_id)
        if not version or int(version.user_id) != g.user_id:
            return jsonify({"error": "Resume version not found or unauthorized"}), 404

        job_desc = JobDescription.get_latest_for_user(g.user_id)
        if not job_desc:
            return jsonify({"error": "No job description found. Please submit a job description first."}), 404

        # Build resume_data from already-parsed text (skip file parsing)
        resume_data = {
            "text": version.parsed_text or "",
            "skills": [],
            "experience": [],
            "education": [],
        }

        job_keywords = extract_skill_phrases(job_desc.text, use_llm_fallback=False)

        # Enrich with confirmed skills from skills interviews
        try:
            from skills_enrichment import enrich_resume_data_with_confirmed_skills
            resume_data = enrich_resume_data_with_confirmed_skills(resume_data, g.user_id)
        except Exception:
            pass

        # Load deep profile for LLM rewrite enrichment
        deep_profile = None
        try:
            from deep_profile import get_deep_profile_engine
            dp = get_deep_profile_engine().get_profile_with_meta(g.user_id)
            if dp:
                deep_profile = dp.get("profile", dp)
        except Exception:
            pass

        cached_raw = linkedin_cache.get_raw(g.user_id)

        optimized = optimize_resume(
            resume_data,
            job_keywords,
            job_text=job_desc.text,
            linkedin_profile=cached_raw,
            deep_profile=deep_profile,
        )

        return jsonify({
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
            "resume_source": version.source,
            "resume_name": version.file_name,
        }), 200

    except Exception as exc:
        logger.exception("optimize_from_version failed for version %s: %s", version_id, exc)
        return jsonify({"error": f"Optimization failed: {exc}"}), 500
