"""Batch job routes — list, status, cancel."""

from auth import require_auth
from flask import Blueprint, g, jsonify, request

jobs_bp = Blueprint("jobs", __name__)


@jobs_bp.route("/api/jobs", methods=["GET"])
@require_auth
def list_jobs():
    from batch_jobs import get_batch_manager

    job_type = request.args.get("type")
    manager = get_batch_manager()
    jobs = manager.get_jobs_for_user(g.user_id, job_type=job_type)
    return jsonify({"jobs": jobs}), 200


@jobs_bp.route("/api/jobs/<job_id>/status", methods=["GET"])
@require_auth
def get_job_status(job_id):
    from batch_jobs import get_batch_manager

    manager = get_batch_manager()
    job = manager.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job), 200


@jobs_bp.route("/api/jobs/<job_id>/cancel", methods=["POST"])
@require_auth
def cancel_job(job_id):
    from batch_jobs import get_batch_manager

    manager = get_batch_manager()
    result = manager.cancel_job(job_id, user_id=g.user_id)
    if "error" in result:
        return jsonify(result), 404
    return jsonify(result), 200
