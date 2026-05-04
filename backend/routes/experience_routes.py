"""Experience routes — experience chat, skills interview, ATS improvement chat."""

import json
import os
import uuid

from auth import require_auth
from flask import Blueprint, current_app, g, jsonify, request
from models import Resume, ResumeVersion
from werkzeug.utils import secure_filename

experience_bp = Blueprint("experience", __name__)

CONTEXT_ALLOWED_EXTENSIONS = {".json", ".xml", ".docx", ".doc", ".pdf", ".txt"}


# --- Phase 7: Experience chat ---


@experience_bp.route("/api/experience/start", methods=["POST"])
@require_auth
def start_experience_session():
    from experience_chat import get_experience_extractor

    data = request.get_json() or {}
    employer = data.get("employer", "")
    client = data.get("client", "")

    extractor = get_experience_extractor()
    result = extractor.start_session(g.user_id, employer, client)
    return jsonify(result), 201


@experience_bp.route("/api/experience/message", methods=["POST"])
@require_auth
def send_experience_message():
    from experience_chat import get_experience_extractor

    data = request.get_json()
    session_id = data.get("session_id")
    message = data.get("message")

    if not session_id or not message:
        return jsonify({"error": "session_id and message are required"}), 400

    extractor = get_experience_extractor()
    result = extractor.process_message(session_id, message, user_id=g.user_id)

    if "error" in result:
        return jsonify(result), 404

    return jsonify(result), 200


@experience_bp.route("/api/experience/summary/<session_id>", methods=["GET"])
@require_auth
def get_experience_summary(session_id):
    from experience_chat import get_experience_extractor

    extractor = get_experience_extractor()
    result = extractor.get_summary(session_id, user_id=g.user_id)

    if "error" in result:
        return jsonify(result), 404

    return jsonify(result), 200


@experience_bp.route("/api/experience/finalize/<session_id>", methods=["POST"])
@require_auth
def finalize_experience(session_id):
    from experience_chat import get_experience_extractor

    data = request.get_json() or {}
    edits = data.get("edits")

    extractor = get_experience_extractor()
    result = extractor.finalize_session(session_id, g.user_id, edits)

    if "error" in result:
        return jsonify(result), 404

    from deep_profile_staleness import mark_profile_stale

    mark_profile_stale(g.user_id, "Experience session finalized")
    return jsonify(result), 200


@experience_bp.route("/api/experience/apply/<session_id>", methods=["POST"])
@require_auth
def apply_experience_to_resume(session_id):
    """Merge finalized experience into a resume version."""
    from experience_chat import get_experience_extractor

    extractor = get_experience_extractor()
    summary = extractor.get_summary(session_id, user_id=g.user_id)

    if "error" in summary:
        return jsonify(summary), 404

    if not summary.get("is_finalized"):
        return jsonify({"error": "Session not yet finalized"}), 400

    # Build resume text from experience data
    lines = []
    title = summary.get("title", "")
    employer = summary.get("employer", "")
    client = summary.get("client", "")

    header = title
    if employer:
        header += f" | {employer}"
    if client:
        header += f" ({client})"
    lines.append(header)
    lines.append("")

    for bp in summary.get("bullet_points", []):
        lines.append(f"- {bp}")

    if summary.get("technologies"):
        lines.append("")
        lines.append("Technologies: " + ", ".join(summary["technologies"]))

    resume_text = "\n".join(lines)

    # Save as a resume version
    version = ResumeVersion.create(
        user_id=g.user_id,
        source="experience_chat",
        file_name=f"Experience - {employer}" + (f" ({client})" if client else ""),
        parsed_text=resume_text,
        source_id=session_id,
        file_type="txt",
        metadata_json=json.dumps(
            {
                "title": title,
                "employer": employer,
                "client": client,
                "bullet_count": len(summary.get("bullet_points", [])),
            }
        ),
    )

    # Also save as a regular resume file for optimization
    filename = f"{uuid.uuid4()}_experience.txt"
    file_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(resume_text)

    resume = Resume.create(g.user_id, f"Experience - {employer}", file_path)

    return (
        jsonify(
            {
                "message": "Experience applied to resume",
                "resume_id": str(resume.id),
                "version_id": str(version.id),
                "text": resume_text,
            }
        ),
        201,
    )


@experience_bp.route("/api/experience/list", methods=["GET"])
@require_auth
def list_experiences():
    from experience_chat import get_experience_extractor

    extractor = get_experience_extractor()
    experiences = extractor.get_extracted_experiences(g.user_id)
    return jsonify({"experiences": experiences}), 200


@experience_bp.route("/api/experience/upload-context", methods=["POST"])
@require_auth
def upload_experience_context():
    """Upload a document to inject additional context into an active experience session.

    Accepts JSON, XML, DOCX, PDF, or TXT files containing interview transcripts,
    notes, or other context that helps fill gaps in the experience extraction.
    The parsed text is added to the session context so the AI interviewer can
    ask better follow-up questions and produce more complete bullet points.
    """
    from experience_chat import get_experience_extractor

    session_id = request.form.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id is required (form field)"}), 400

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in CONTEXT_ALLOWED_EXTENSIONS:
        return (
            jsonify(
                {
                    "error": "File type not allowed. "
                    f"Accepted: {', '.join(sorted(CONTEXT_ALLOWED_EXTENSIONS))}"
                }
            ),
            400,
        )

    # Save the uploaded file
    filename = secure_filename(f"{uuid.uuid4()}_context{ext}")
    upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
    file_path = os.path.join(upload_folder, filename)
    file.save(file_path)

    try:
        from document_parser import parse_any

        parsed_text = parse_any(file_path)
        if not parsed_text or len(parsed_text.strip()) < 10:
            return jsonify({"error": "Uploaded file contains no usable text"}), 400

        extractor = get_experience_extractor()
        result = extractor.inject_context(
            session_id,
            user_id=g.user_id,
            uploaded_text=parsed_text,
            source_filename=file.filename,
        )

        if "error" in result:
            return jsonify(result), 404

        return (
            jsonify(
                {
                    "message": "Context uploaded and injected into session",
                    "session_id": session_id,
                    "source_file": file.filename,
                    "text_length": len(parsed_text),
                    "fields_updated": result.get("fields_updated", []),
                    "stage": result.get("stage", ""),
                }
            ),
            200,
        )
    except Exception as e:
        return jsonify({"error": f"Failed to process context file: {e}"}), 500


# --- Skills Interview ---


@experience_bp.route("/api/skills-interview/start", methods=["POST"])
@require_auth
def start_skills_interview():
    from skills_interview import get_skills_interviewer

    data = request.get_json() or {}
    skills = data.get("skills", [])
    resume_id = data.get("resume_id", "")

    if not skills:
        return jsonify({"error": "No skills provided"}), 400

    interviewer = get_skills_interviewer()
    result = interviewer.start_session(int(g.user_id), resume_id, skills)
    return jsonify(result), 200


@experience_bp.route("/api/skills-interview/message", methods=["POST"])
@require_auth
def send_skills_interview_message():
    from skills_interview import get_skills_interviewer

    data = request.get_json() or {}
    session_id = data.get("session_id")
    message = data.get("message", "")

    if not session_id or not message:
        return jsonify({"error": "session_id and message required"}), 400

    interviewer = get_skills_interviewer()
    result = interviewer.send_message(session_id, message, user_id=g.user_id)
    if "error" in result:
        return jsonify(result), 404
    return jsonify(result), 200


@experience_bp.route("/api/skills-interview/<session_id>/summary", methods=["GET"])
@require_auth
def get_skills_interview_summary(session_id):
    from skills_interview import get_skills_interviewer

    interviewer = get_skills_interviewer()
    result = interviewer.get_summary(session_id, user_id=g.user_id)
    if isinstance(result, dict) and "error" in result:
        return jsonify(result), 404
    return jsonify({"results": result}), 200


@experience_bp.route("/api/skills-interview/<session_id>/finalize", methods=["POST"])
@require_auth
def finalize_skills_interview(session_id):
    from skills_interview import get_skills_interviewer

    interviewer = get_skills_interviewer()
    result = interviewer.finalize_session(session_id, user_id=g.user_id)
    if isinstance(result, dict) and "error" in result:
        return jsonify(result), 404
    return jsonify({"results": result}), 200


# --- ATS Improvement Chat ---


@experience_bp.route("/api/ats-improve/start", methods=["POST"])
@require_auth
def start_ats_improvement():
    from ats_improvement_chat import get_ats_improvement_chat

    data = request.get_json() or {}
    resume_id = data.get("resume_id")
    score_data = data.get("score_data", {})

    if not score_data:
        return jsonify({"error": "score_data required"}), 400

    chat = get_ats_improvement_chat()
    result = chat.start_session(int(g.user_id), resume_id, score_data)
    return jsonify(result), 200


@experience_bp.route("/api/ats-improve/message", methods=["POST"])
@require_auth
def send_ats_improvement_message():
    from ats_improvement_chat import get_ats_improvement_chat

    data = request.get_json() or {}
    session_id = data.get("session_id")
    message = data.get("message", "")

    if not session_id or not message:
        return jsonify({"error": "session_id and message required"}), 400

    chat = get_ats_improvement_chat()
    result = chat.send_message(session_id, message, user_id=g.user_id)
    return jsonify(result), 200


@experience_bp.route("/api/ats-improve/<session_id>/resume", methods=["GET"])
@require_auth
def get_ats_improved_resume(session_id):
    from ats_improvement_chat import get_ats_improvement_chat

    chat = get_ats_improvement_chat()
    text = chat.get_improved_resume(session_id, user_id=g.user_id)
    if text is None:
        return jsonify({"error": "Session not found"}), 404
    return jsonify({"improved_text": text}), 200


# --- Persistent Corrections (Fix A / Fix E) ---

@experience_bp.route("/api/ats-improve/corrections", methods=["GET"])
@require_auth
def list_corrections():
    from resume_corrections import get_corrections

    resume_id = request.args.get("resume_id")
    corrections = get_corrections(user_id=int(g.user_id), resume_id=resume_id)
    return jsonify({"corrections": corrections}), 200


@experience_bp.route("/api/ats-improve/corrections", methods=["POST"])
@require_auth
def add_correction():
    from resume_corrections import save_correction

    data = request.get_json() or {}
    old_text = (data.get("old_text") or "").strip()
    # new_text may be "" (deletion correction — remove the phrase entirely)
    raw_new = data.get("new_text", "")
    new_text = str(raw_new).strip() if raw_new is not None else ""
    resume_id = data.get("resume_id")  # None = user-global

    if not old_text:
        return jsonify({"error": "old_text is required"}), 400

    correction_id = save_correction(
        user_id=int(g.user_id),
        old_text=old_text,
        new_text=new_text,
        resume_id=str(resume_id) if resume_id is not None else None,
    )
    return jsonify({"id": correction_id, "status": "saved"}), 201


@experience_bp.route("/api/ats-improve/corrections/<int:correction_id>", methods=["DELETE"])
@require_auth
def delete_correction(correction_id):
    from resume_corrections import delete_correction as _delete

    success = _delete(correction_id=correction_id, user_id=int(g.user_id))
    if not success:
        return jsonify({"error": "Correction not found or not owned by user"}), 404
    return jsonify({"status": "deleted"}), 200
