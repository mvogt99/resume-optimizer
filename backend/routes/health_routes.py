import logging

from flask import Blueprint, jsonify, make_response

from models import get_db

logger = logging.getLogger(__name__)

health_bp = Blueprint("health_bp", __name__, url_prefix="")


@health_bp.route("/api/health", methods=["GET"])
def health_check():
    try:
        with get_db() as conn:
            conn.execute("SELECT 1").fetchone()
        logger.info("health check ok")
        return make_response(jsonify({"status": "ok", "db": "ok", "version": "1.0.0"}), 200)
    except Exception as e:
        logger.error("health check failed: %s", e)
        return make_response(jsonify({"status": "error", "db": "error", "detail": str(e)}), 503)
