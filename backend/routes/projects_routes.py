"""Phase 9 client project analysis routes — list, create, analyze, approve."""

from auth import require_auth
from flask import Blueprint, g, jsonify, request

projects_bp = Blueprint("projects", __name__)


@projects_bp.route("/api/projects", methods=["GET"])
@require_auth
def list_projects():
    from project_analyzer import get_project_analyzer

    analyzer = get_project_analyzer()
    clients = analyzer.get_clients_for_user(g.user_id)
    return jsonify({"projects": clients}), 200


@projects_bp.route("/api/projects", methods=["POST"])
@require_auth
def create_project():
    from project_analyzer import get_project_analyzer

    data = request.get_json()
    client_name = data.get("client_name")
    folder_id = data.get("folder_id")
    folder_name = data.get("folder_name", "")

    if not client_name or not folder_id:
        return jsonify({"error": "client_name and folder_id are required"}), 400

    analyzer = get_project_analyzer()
    client_id = analyzer.create_client(g.user_id, client_name, folder_id, folder_name)
    return jsonify({"message": "Client project created", "project_id": client_id}), 201


@projects_bp.route("/api/projects/<int:project_id>/analyze", methods=["POST"])
@require_auth
def start_project_analysis(project_id):
    from project_analyzer import get_project_analyzer

    analyzer = get_project_analyzer()
    client = analyzer.get_client(project_id, user_id=g.user_id)
    if not client:
        return jsonify({"error": "Project not found"}), 404

    job_id = analyzer.start_analysis(project_id, g.user_id)
    return jsonify({"message": "Analysis started", "job_id": job_id}), 202


@projects_bp.route("/api/projects/<int:project_id>/analysis", methods=["GET"])
@require_auth
def get_project_analysis(project_id):
    from project_analyzer import get_project_analyzer

    analyzer = get_project_analyzer()
    analysis = analyzer.get_analysis(project_id, user_id=g.user_id)
    if not analysis:
        return jsonify({"error": "Project not found"}), 404

    return jsonify(analysis), 200


@projects_bp.route("/api/projects/<int:project_id>/analysis", methods=["PUT"])
@require_auth
def update_project_analysis(project_id):
    from project_analyzer import get_project_analyzer

    analyzer = get_project_analyzer()
    client = analyzer.get_client(project_id, user_id=g.user_id)
    if not client:
        return jsonify({"error": "Project not found"}), 404

    data = request.get_json()
    analyzer.update_analysis(project_id, data)
    return jsonify({"message": "Analysis updated"}), 200


@projects_bp.route("/api/projects/<int:project_id>/approve", methods=["POST"])
@require_auth
def approve_project_analysis(project_id):
    from project_analyzer import get_project_analyzer

    analyzer = get_project_analyzer()
    client = analyzer.get_client(project_id, user_id=g.user_id)
    if not client:
        return jsonify({"error": "Project not found"}), 404

    ok = analyzer.approve_analysis(project_id)
    if ok:
        from deep_profile_staleness import mark_profile_stale

        mark_profile_stale(g.user_id, "New client project approved")
        return jsonify({"message": "Analysis approved and stored in knowledge graph"}), 200
    return jsonify({"error": "Approval failed"}), 500


@projects_bp.route("/api/projects/<int:project_id>/documents", methods=["GET"])
@require_auth
def list_project_documents(project_id):
    from project_analyzer import get_project_analyzer

    analyzer = get_project_analyzer()
    client = analyzer.get_client(project_id, user_id=g.user_id)
    if not client:
        return jsonify({"error": "Project not found"}), 404

    docs = analyzer.get_documents(project_id)
    return jsonify({"documents": docs}), 200


@projects_bp.route("/api/projects/folders", methods=["GET"])
@require_auth
def list_drive_folders():
    from project_analyzer import get_project_analyzer

    parent_id = request.args.get("parent_id")
    analyzer = get_project_analyzer()
    result = analyzer.list_drive_folders(parent_id)
    return jsonify(result), 200


@projects_bp.route("/api/projects/<int:project_id>/reanalyze", methods=["POST"])
@require_auth
def reanalyze_project(project_id):
    """Re-run LLM extraction on already-ingested documents (skip crawl + ingest).
    Pass force=true to reset ALL docs (not just empty ones) for full re-extraction."""
    from project_analyzer import get_project_analyzer

    analyzer = get_project_analyzer()
    client = analyzer.get_client(project_id, user_id=g.user_id)
    if not client:
        return jsonify({"error": "Project not found"}), 404

    force = False
    reextract_only = False
    if request.is_json:
        force = request.json.get("force", False)
        reextract_only = request.json.get("reextract_only", False)
    elif request.args.get("force"):
        force = request.args.get("force", "").lower() in ("true", "1", "yes")

    job_id = analyzer.start_reanalysis(
        project_id, g.user_id, force=force, reextract_only=reextract_only
    )
    if reextract_only:
        mode = "skills+outcomes re-extraction only"
    elif force:
        mode = "full re-extraction"
    else:
        mode = "re-analysis of empty docs"
    return jsonify({"message": f"Re-analysis started ({mode})", "job_id": job_id}), 202


@projects_bp.route("/api/projects/<int:project_id>/reset-status", methods=["POST"])
@require_auth
def reset_project_status(project_id):
    """Reset a stuck project status (e.g., 'analyzing' -> 'completed' or 'failed')."""
    from models import get_db
    from project_analyzer import get_project_analyzer

    analyzer = get_project_analyzer()
    client = analyzer.get_client(project_id, user_id=g.user_id)
    if not client:
        return jsonify({"error": "Project not found"}), 404

    # If docs have analysis data, mark completed; otherwise failed
    with get_db() as conn:
        analyzed_count = conn.execute(
            "SELECT COUNT(*) FROM project_documents WHERE client_id = ? AND status = 'analyzed'",
            (project_id,),
        ).fetchone()[0]

    new_status = "completed" if analyzed_count > 0 else "failed"
    analyzer._update_client_status(project_id, new_status)

    return jsonify({"project_id": project_id, "analysis_status": new_status}), 200
