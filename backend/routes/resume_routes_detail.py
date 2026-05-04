"""Resume detail routes — interview guide, from-linkedin, skills-gap, gdrive, versions.

Side-effect import: registers routes on resume_bp from resume_routes.py.
app.py needs no changes.
"""

import json
import logging
import os
import uuid

import linkedin_cache
from auth import require_auth
from flask import current_app, g, jsonify, request
from models import JobDescription, Resume, ResumeVersion, get_db
from utils import process_linkedin_profile, process_resume

from routes.resume_routes import resume_bp  # noqa: F401 — side-effect registration

logger = logging.getLogger(__name__)


@resume_bp.route("/api/interview-guide/<resume_id>", methods=["GET"])
@require_auth
def get_interview_guide_endpoint(resume_id):
    from interview_guide import generate_interview_guide

    resume = Resume.get_by_id(resume_id)
    if not resume or int(resume.user_id) != g.user_id:
        return jsonify({"error": "Resume not found or unauthorized"}), 404

    job_desc = JobDescription.get_latest_for_user(g.user_id)
    if not job_desc:
        return jsonify({"error": "No job description found"}), 404

    processed_resume = process_resume(resume.file_path)
    raw = linkedin_cache.get_raw(g.user_id)

    guide = generate_interview_guide(processed_resume, job_desc.text, raw)
    return jsonify(guide), 200


@resume_bp.route("/api/resume/from-linkedin", methods=["POST"])
@require_auth
def create_resume_from_linkedin():
    """Import LinkedIn profile and create a resume record from it."""
    try:
        profile = linkedin_cache.get_profile(g.user_id) or process_linkedin_profile()
    except Exception as e:
        logger.exception("Unhandled error in route: %s", e)
        return jsonify({"error": "Internal server error"}), 500

    filename = f"{uuid.uuid4()}_linkedin_profile.txt"
    file_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(profile["text"])

    resume = Resume.create(g.user_id, "LinkedIn Profile", file_path)
    return (
        jsonify(
            {
                "message": "Resume created from LinkedIn profile",
                "resume_id": str(resume.id),
                "profile_summary": {
                    "skills_count": len(profile.get("skills", [])),
                    "experience_count": len(profile.get("experience", [])),
                    "education_count": len(profile.get("education", [])),
                },
            }
        ),
        201,
    )


# --- Skills gap analysis ---


def _gather_project_journey_evidence(user_id):
    """Gather skill evidence from client projects and AI journey events."""
    evidence = []

    try:
        from project_analyzer import get_project_analyzer

        analyzer = get_project_analyzer()
        clients = analyzer.get_clients_for_user(user_id)
        for client in clients:
            if client.get("analysis_status") != "completed":
                continue
            skills_data = client.get("skills_json") or {}
            if isinstance(skills_data, str):
                skills_data = json.loads(skills_data) if skills_data else {}
            tech_skills = []
            for cat_skills in skills_data.values():
                if isinstance(cat_skills, list):
                    tech_skills.extend(
                        [s if isinstance(s, str) else s.get("name", "") for s in cat_skills]
                    )
            if tech_skills:
                evidence.append(
                    {
                        "source": f"Client Project: {client['client_name']}",
                        "detail": "Used in project documentation",
                        "skills": tech_skills,
                    }
                )
    except Exception:
        pass

    try:  # noqa: SIM105
        with get_db() as conn:
            events = conn.execute(
                "SELECT technologies, title FROM journey_events "
                "WHERE technologies != '[]' AND user_id = ?",
                (user_id,),
            ).fetchall()
            for evt in events:
                techs = json.loads(evt["technologies"] or "[]")
                if techs:
                    evidence.append(
                        {
                            "source": f"AI Journey: {evt['title']}",
                            "detail": "Demonstrated in development history",
                            "skills": techs,
                        }
                    )
    except Exception:
        pass

    return evidence


@resume_bp.route("/api/skills-gap/<resume_id>", methods=["GET"])
@require_auth
def get_skills_gap(resume_id):
    from skills_optimizer import (
        analyze_skills_gap,
        get_relevant_accomplishments,
        match_recommendations,
    )

    resume = Resume.get_by_id(resume_id)
    if not resume or int(resume.user_id) != g.user_id:
        return jsonify({"error": "Resume not found or unauthorized"}), 404

    job_desc = JobDescription.get_latest_for_user(g.user_id)
    if not job_desc:
        return jsonify({"error": "No job description found"}), 404

    processed_resume = process_resume(resume.file_path)
    raw = linkedin_cache.get_raw(g.user_id)

    project_journey_evidence = _gather_project_journey_evidence(g.user_id)
    gap_analysis = analyze_skills_gap(
        processed_resume, job_desc.text, raw, project_journey_evidence
    )

    result = {"skills_gap": gap_analysis}

    if raw:
        result["relevant_accomplishments"] = get_relevant_accomplishments(raw, job_desc.text)
        result["relevant_recommendations"] = match_recommendations(raw, job_desc.text)

    # Enrich with feedback-based skill prioritization (Phase 17.05)
    try:
        from feedback_analyzer import get_skills_to_prioritize

        priority_skills = get_skills_to_prioritize(g.user_id)
        if priority_skills:
            result["priority_skills"] = priority_skills
            # Mark skills_to_acquire entries that are rejection-correlated
            priority_set = {s.lower() for s in priority_skills}
            for entry in gap_analysis.get("skills_to_acquire", []):
                skill_name = entry.get("skill", "").lower()
                if skill_name in priority_set:
                    entry["priority"] = "high"
                    entry["priority_reason"] = "Frequently missing in rejected applications"
    except Exception:
        pass

    return jsonify(result), 200


@resume_bp.route("/api/skills-gap/<resume_id>/rescore", methods=["POST"])
@require_auth
def rescore_skills_gap(resume_id):
    """Re-score skills gap with user-adjusted skill lists."""
    from skills_optimizer import (
        analyze_skills_gap,
        get_relevant_accomplishments,
        match_recommendations,
    )

    resume = Resume.get_by_id(resume_id)
    if not resume or int(resume.user_id) != g.user_id:
        return jsonify({"error": "Resume not found or unauthorized"}), 404

    job_desc = JobDescription.get_latest_for_user(g.user_id)
    if not job_desc:
        return jsonify({"error": "No job description found"}), 404

    data = request.get_json() or {}
    confirmed_skills = data.get("confirmed_skills", [])
    removed_skills = data.get("removed_skills", [])
    added_skills = data.get("added_skills", [])

    processed_resume = process_resume(resume.file_path)
    raw = linkedin_cache.get_raw(g.user_id)

    if confirmed_skills or added_skills:
        extra_skills = confirmed_skills + added_skills
        existing_skills = processed_resume.get("skills", [])
        processed_resume["skills"] = list(set(existing_skills + [s.lower() for s in extra_skills]))
        processed_resume["text"] = (
            processed_resume.get("text", "") + "\n\nAdditional Skills: " + ", ".join(extra_skills)
        )

    project_journey_evidence = _gather_project_journey_evidence(g.user_id)
    gap_analysis = analyze_skills_gap(
        processed_resume, job_desc.text, raw, project_journey_evidence
    )

    if removed_skills:
        removed_lower = {s.lower() for s in removed_skills}
        for key in ("skills_already_shown", "skills_to_emphasize", "skills_to_acquire"):
            gap_analysis[key] = [
                s for s in gap_analysis[key] if s["skill"].lower() not in removed_lower
            ]
        total = gap_analysis["total_job_keywords"] - len(removed_lower)
        shown = len(gap_analysis["skills_already_shown"])
        can_add = len(gap_analysis["skills_to_emphasize"])
        coverage = ((shown + can_add) / total * 100) if total > 0 else 0
        gap_analysis["coverage_percent"] = round(coverage, 1)
        gap_analysis["total_job_keywords"] = total
        gap_analysis["gap_summary"] = {
            "shown": shown,
            "can_add": can_add,
            "need_to_learn": len(gap_analysis["skills_to_acquire"]),
        }

    result = {"skills_gap": gap_analysis}

    if raw:
        result["relevant_accomplishments"] = get_relevant_accomplishments(raw, job_desc.text)
        result["relevant_recommendations"] = match_recommendations(raw, job_desc.text)

    return jsonify(result), 200


# --- Google Drive ---


@resume_bp.route("/api/resumes/gdrive", methods=["GET"])
@require_auth
def list_gdrive_files():
    from gdrive_service import get_gdrive_service

    folder_name = request.args.get("folder")
    folder_id = request.args.get("folder_id")

    try:
        gdrive = get_gdrive_service()
        if folder_id:
            result = gdrive.list_folder_by_id(folder_id)
        elif folder_name:
            result = gdrive.list_resume_folder(folder_name)
        else:
            result = gdrive.get_root_folders()
        return jsonify(result), 200
    except Exception as e:
        logger.exception("Unhandled error in route: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@resume_bp.route("/api/resumes/gdrive/import", methods=["POST"])
@require_auth
def import_gdrive_file():
    from gdrive_service import get_gdrive_service

    data = request.get_json()
    file_id = data.get("file_id")
    if not file_id:
        return jsonify({"error": "file_id is required"}), 400

    try:
        gdrive = get_gdrive_service()
        imported = gdrive.import_file(file_id)

        version = ResumeVersion.create(
            user_id=g.user_id,
            source="google_drive",
            file_name=imported["file_name"],
            parsed_text=imported["text"],
            source_id=imported["file_id"],
            file_type=imported["file_type"],
            metadata_json=json.dumps(
                {
                    "mime_type": imported["mime_type"],
                    "modified_time": imported["modified_time"],
                }
            ),
        )

        filename = f"{uuid.uuid4()}_{imported['file_name']}.txt"
        file_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(imported["text"])

        resume = Resume.create(g.user_id, imported["file_name"], file_path)

        return (
            jsonify(
                {
                    "message": "File imported from Google Drive",
                    "resume_id": str(resume.id),
                    "version_id": str(version.id),
                    "file_name": imported["file_name"],
                    "file_type": imported["file_type"],
                    "text_length": len(imported["text"]),
                }
            ),
            201,
        )
    except Exception as e:
        logger.exception("Unhandled error in route: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@resume_bp.route("/api/resumes/versions", methods=["GET"])
@require_auth
def list_resume_versions():
    versions = ResumeVersion.get_all_for_user(g.user_id)
    return (
        jsonify(
            {
                "versions": [
                    {
                        "id": v.id,
                        "source": v.source,
                        "file_name": v.file_name,
                        "file_type": v.file_type,
                        "text_preview": v.parsed_text[:200] if v.parsed_text else "",
                        "metadata": json.loads(v.metadata_json) if v.metadata_json else {},
                    }
                    for v in versions
                ]
            }
        ),
        200,
    )


@resume_bp.route("/api/resumes/versions/<int:version_id>", methods=["GET"])
@require_auth
def get_resume_version(version_id):
    version = ResumeVersion.get_by_id(version_id)
    if not version or int(version.user_id) != g.user_id:
        return jsonify({"error": "Version not found or unauthorized"}), 404

    return (
        jsonify(
            {
                "id": version.id,
                "source": version.source,
                "file_name": version.file_name,
                "file_type": version.file_type,
                "parsed_text": version.parsed_text,
                "metadata": json.loads(version.metadata_json) if version.metadata_json else {},
            }
        ),
        200,
    )


@resume_bp.route("/api/resumes/gdrive/reimport/<int:version_id>", methods=["POST"])
@require_auth
def reimport_gdrive_file(version_id):
    """Re-fetch a file from Google Drive to pick up upstream changes."""
    from gdrive_service import get_gdrive_service

    version = ResumeVersion.get_by_id(version_id)
    if not version or int(version.user_id) != g.user_id:
        return jsonify({"error": "Version not found or unauthorized"}), 404

    if version.source != "google_drive" or not version.source_id:
        return jsonify({"error": "Version is not from Google Drive"}), 400

    try:
        gdrive = get_gdrive_service()
        imported = gdrive.import_file(version.source_id)

        with get_db() as conn:
            conn.execute(
                "UPDATE resume_versions SET parsed_text = ?, "
                "metadata_json = ?, file_name = ? WHERE id = ?",
                (
                    imported["text"],
                    json.dumps(
                        {
                            "mime_type": imported["mime_type"],
                            "modified_time": imported["modified_time"],
                            "reimported": True,
                        }
                    ),
                    imported["file_name"],
                    version_id,
                ),
            )
            conn.commit()

        return (
            jsonify(
                {
                    "message": "File re-imported from Google Drive",
                    "version_id": version_id,
                    "file_name": imported["file_name"],
                    "text_length": len(imported["text"]),
                }
            ),
            200,
        )
    except Exception as e:
        logger.exception("Unhandled error in route: %s", e)
        return jsonify({"error": "Internal server error"}), 500


@resume_bp.route("/api/resumes/versions/<int:version_id>", methods=["PUT"])
@require_auth
def update_resume_version(version_id):
    version = ResumeVersion.get_by_id(version_id)
    if not version or int(version.user_id) != g.user_id:
        return jsonify({"error": "Version not found or unauthorized"}), 404

    data = request.get_json()
    new_text = data.get("parsed_text")
    if new_text is None:
        return jsonify({"error": "parsed_text is required"}), 400

    with get_db() as conn:
        conn.execute(
            "UPDATE resume_versions SET parsed_text = ? WHERE id = ?",
            (new_text, version_id),
        )
        conn.commit()

    return jsonify({"message": "Version updated", "id": version_id}), 200
