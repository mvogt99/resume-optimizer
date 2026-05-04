"""Resume interview routes — guided resume building from scratch."""

from auth import require_auth
from flask import Blueprint, g, jsonify, request

resume_interview_bp = Blueprint("resume_interview", __name__)


@resume_interview_bp.route("/api/resume-interview/start", methods=["POST"])
@require_auth
def resume_interview_start():
    """Start a new resume interview session."""
    from resume_interview import get_resume_interviewer

    interviewer = get_resume_interviewer()
    result = interviewer.start_session(g.user_id)

    return jsonify(result), 201


@resume_interview_bp.route("/api/resume-interview/message", methods=["POST"])
@require_auth
def resume_interview_message():
    """Send a message in the resume interview."""
    from resume_interview import get_resume_interviewer

    data = request.get_json() or {}
    session_id = data.get("session_id")
    message = data.get("message", "").strip()

    if not session_id or not message:
        return jsonify({"error": "session_id and message required"}), 400

    interviewer = get_resume_interviewer()
    result = interviewer.process_message(session_id, message, user_id=g.user_id)

    if "error" in result:
        return jsonify(result), 404

    return jsonify(result), 200


@resume_interview_bp.route("/api/resume-interview/state/<session_id>", methods=["GET"])
@require_auth
def resume_interview_state(session_id):
    """Get the current state of a resume interview session."""
    from resume_interview import get_resume_interviewer

    interviewer = get_resume_interviewer()
    result = interviewer.get_session_state(session_id, user_id=g.user_id)

    if "error" in result:
        return jsonify(result), 404

    return jsonify(result), 200


@resume_interview_bp.route("/api/resume-interview/preview/<session_id>", methods=["GET"])
@require_auth
def resume_interview_preview(session_id):
    """Get a preview of the compiled resume without saving."""
    from resume_interview import get_resume_interviewer

    interviewer = get_resume_interviewer()
    result = interviewer.compile_preview(session_id, user_id=g.user_id)

    if "error" in result:
        return jsonify(result), 404

    return jsonify(result), 200


@resume_interview_bp.route("/api/resume-interview/finalize/<session_id>", methods=["POST"])
@require_auth
def resume_interview_finalize(session_id):
    """Finalize the interview and save as a resume version."""
    from resume_interview import get_resume_interviewer

    data = request.get_json() or {}
    edits = data.get("edits", {})

    interviewer = get_resume_interviewer()
    result = interviewer.finalize_to_resume(session_id, edits, user_id=g.user_id)

    if "error" in result:
        return jsonify(result), 404

    return jsonify(result), 201
