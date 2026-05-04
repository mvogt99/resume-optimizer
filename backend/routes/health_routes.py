import logging
import os
import sqlite3

from flask import Blueprint, jsonify, make_response

logger = logging.getLogger(__name__)

health_bp = Blueprint("health_bp", __name__, url_prefix="")

_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database.db")


@health_bp.route("/api/health", methods=["GET"])
def health_check():
    try:
        conn = sqlite3.connect(_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        conn.close()
        logger.info("health check ok")
        return make_response(jsonify({"status": "ok", "db": "ok", "version": "1.0.0"}), 200)
    except Exception as e:
        logger.error("health check failed: %s", e)
        return make_response(jsonify({"status": "error", "db": "error", "detail": str(e)}), 503)
