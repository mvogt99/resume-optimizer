"""Resume template CRUD routes."""

from auth import require_auth
from flask import Blueprint, g, jsonify, request, send_file
from resume_export import export_resume_docx, export_resume_pdf
from resume_templates import VALID_ROLE_TYPES, ResumeTemplate, customize_for_job

template_bp = Blueprint("templates", __name__)


@template_bp.route("/api/templates", methods=["POST"])
@require_auth
def create_template():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    role_type = data.get("role_type", "general")
    base_content = data.get("base_content", "")
    from_resume_id = data.get("from_resume_id")

    if not name:
        return jsonify({"error": "name is required"}), 400
    if role_type not in VALID_ROLE_TYPES:
        return (
            jsonify({"error": f"Invalid role_type. Must be one of: {list(VALID_ROLE_TYPES)}"}),
            400,
        )

    if from_resume_id:
        from models import Resume
        from utils import process_resume

        resume = Resume.get_by_id(from_resume_id)
        if not resume:
            return jsonify({"error": "Resume not found"}), 404
        try:
            parsed = process_resume(resume.file_path)
            base_content = parsed.get("text", "")
        except Exception as exc:
            return jsonify({"error": f"Failed to parse resume: {exc}"}), 400

    if not base_content:
        return jsonify({"error": "base_content is required (or provide from_resume_id)"}), 400

    try:
        template = ResumeTemplate.create(g.user_id, name, role_type, base_content)
        return jsonify(template.to_dict()), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@template_bp.route("/api/templates", methods=["GET"])
@require_auth
def list_templates():
    templates = ResumeTemplate.get_all_for_user(g.user_id)
    return jsonify({"templates": [t.to_dict() for t in templates], "count": len(templates)}), 200


@template_bp.route("/api/templates/<int:template_id>", methods=["GET"])
@require_auth
def get_template(template_id):
    template = ResumeTemplate.get_by_id(template_id, g.user_id)
    if not template:
        return jsonify({"error": "Template not found"}), 404
    return jsonify(template.to_dict()), 200


@template_bp.route("/api/templates/<int:template_id>", methods=["PUT"])
@require_auth
def update_template(template_id):
    data = request.get_json(silent=True) or {}
    updates = {}
    for key in ("name", "role_type", "base_content"):
        if key in data:
            updates[key] = data[key]
    if not updates:
        return jsonify({"error": "No fields to update"}), 400
    try:
        updated = ResumeTemplate.update(template_id, g.user_id, **updates)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if not updated:
        return jsonify({"error": "Template not found"}), 404
    template = ResumeTemplate.get_by_id(template_id, g.user_id)
    return jsonify(template.to_dict()), 200


@template_bp.route("/api/templates/<int:template_id>", methods=["DELETE"])
@require_auth
def delete_template(template_id):
    deleted = ResumeTemplate.delete(template_id, g.user_id)
    if not deleted:
        return jsonify({"error": "Template not found"}), 404
    return jsonify({"message": "Template deleted"}), 200


@template_bp.route("/api/templates/<int:template_id>/customize", methods=["POST"])
@require_auth
def customize_template(template_id):
    data = request.get_json(silent=True) or {}
    job_description = data.get("job_description", "").strip()
    if not job_description or len(job_description) < 50:
        return jsonify({"error": "job_description must be at least 50 characters"}), 400
    try:
        result = customize_for_job(template_id, g.user_id, job_description)
        return jsonify(result), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@template_bp.route("/api/templates/<int:template_id>/download/<fmt>", methods=["POST"])
@require_auth
def download_customized(template_id, fmt):
    """Download customized resume as PDF or DOCX. Body: {text: "optimized text"}."""
    if fmt not in ("pdf", "docx"):
        return jsonify({"error": "Format must be pdf or docx"}), 400
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    if not text:
        return jsonify({"error": "text is required"}), 400
    if fmt == "pdf":
        buf = export_resume_pdf(text)
        return send_file(
            buf, mimetype="application/pdf", as_attachment=True, download_name="resume.pdf"
        )
    else:
        buf = export_resume_docx(text)
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument" ".wordprocessingml.document",
            as_attachment=True,
            download_name="resume.docx",
        )
