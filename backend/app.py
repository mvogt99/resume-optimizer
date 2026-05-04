"""Resume Optimizer — Flask application factory."""

import logging
import os
import time
import uuid

from flask import Flask, g, jsonify, request
from flask_cors import CORS
from flask_limiter.errors import RateLimitExceeded
from rate_limit import limiter  # noqa: F401 — re-exported for backwards compat

_logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)


def create_app(testing=False):
    app = Flask(__name__)
    app.config["UPLOAD_FOLDER"] = "uploads"
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB

    if testing:
        app.config["TESTING"] = True
        app.config["RATELIMIT_ENABLED"] = False

    _cors_allowed = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://localhost:5000")
    _cors_origins = [o.strip() for o in _cors_allowed.split(",") if o.strip()]
    # Support additional origins via CORS_ORIGIN (singular, legacy env var)
    _extra_origins = os.environ.get("CORS_ORIGIN", "")
    for _origin in _extra_origins.split(","):
        _origin = _origin.strip()
        if _origin:
            _cors_origins.append(_origin)
    # Allow all origins when running in local-network mode (CORS_ALLOW_ALL=1)
    if os.environ.get("CORS_ALLOW_ALL", "").lower() in ("1", "true"):
        CORS(app)
    else:
        CORS(app, origins=_cors_origins)

    limiter.init_app(app)

    @app.before_request
    def _before_request():
        g.request_id = str(uuid.uuid4())
        g.request_start = time.time()

    @app.after_request
    def _after_request(response):
        duration_ms = int((time.time() - g.request_start) * 1000)
        _logger.info(
            "%s %s %s %dms rid=%s",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
            g.request_id,
        )
        response.headers["X-Request-ID"] = g.request_id
        return response

    @app.errorhandler(RateLimitExceeded)
    def handle_rate_limit(e):
        _logger.warning(
            "Rate limit exceeded: %s %s — limit: %s",
            request.method,
            request.path,
            e.limit,
        )
        return jsonify({"error": "Rate limit exceeded. Try again later."}), 429

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Phase 3.1: resolve DATABASE_URL from Secrets Manager when CLOUDLIFT_ENV=aws
    # Must run before any blueprint import that transitively imports models.init_db()
    import cloudlift_db_adapter as _db_adapter
    _db_url = _db_adapter.resolve_database_url()
    if _db_url:
        os.environ.setdefault("DATABASE_URL", _db_url)

    # Register blueprints
    from agents_routes import agents_bp
    from routes.analytics_routes import analytics_bp
    from routes.auth_routes import auth_bp
    from routes.builder_routes import builder_bp
    from routes.campaign_trends_routes import campaign_trends_bp
    from routes.campaigns_routes import campaigns_bp
    import routes.campaigns_routes_analytics  # noqa: F401 — registers analytics/graph/engagement routes on campaigns_bp
    from routes.experience_routes import experience_bp
    from routes.jobs_routes import jobs_bp
    from routes.journey_routes import journey_bp
    from routes.linkedin_routes import linkedin_bp
    from routes.new_features_routes import new_features_bp
    from routes.profile_routes import profile_bp
    from routes.projects_routes import projects_bp
    from routes.resume_interview_routes import resume_interview_bp
    from routes.chat_history_routes import chat_history_bp
    from routes.chat_routes import chat_bp
    from routes.alignment_routes import alignment_bp
    from routes.alignment_audit_routes import alignment_audit_bp
    from routes.expert_compare_routes import expert_compare_bp
    from routes.keyword_routes import keyword_bp
    from routes.local_browse_routes import local_browse_bp
    from routes.resume_routes import resume_bp
    import routes.resume_routes_detail  # noqa: F401 — registers interview-guide/linkedin/skills-gap/gdrive/versions routes on resume_bp
    from routes.health_routes import health_bp
    from routes.recommender_routes import recommender_bp
    from routes.sessions_routes import sessions_bp
    from routes.template_routes import template_bp

    for bp in [
        health_bp,
        alignment_bp,
        alignment_audit_bp,
        auth_bp,
        expert_compare_bp,
        local_browse_bp,
        resume_bp,
        recommender_bp,
        resume_interview_bp,
        experience_bp,
        projects_bp,
        journey_bp,
        campaigns_bp,
        campaign_trends_bp,
        profile_bp,
        builder_bp,
        jobs_bp,
        sessions_bp,
        agents_bp,
        template_bp,
        linkedin_bp,
        analytics_bp,
        chat_history_bp,
        chat_bp,
        keyword_bp,
        new_features_bp,
    ]:
        app.register_blueprint(bp)

    # Auto-initialize ArangoDB knowledge graph (non-blocking)
    if not testing and os.environ.get("ARANGO_ENABLED", "").lower() in (
        "1",
        "true",
    ):
        try:
            from arango_client import get_arango_client

            client = get_arango_client()
            if client.initialize():
                logging.getLogger(__name__).info("ArangoDB knowledge graph initialized")
        except Exception as e:
            logging.getLogger(__name__).warning("ArangoDB init skipped: %s", e)

    # Warm up sentence-transformer model at startup so first compare/score
    # request does not pay the cold-start penalty (~3-5 s model load).
    if not testing:
        import threading

        def _warmup_st_model():
            try:
                from nlp_engine import _get_st_model
                model = _get_st_model()
                if model is not None:
                    _logger.info("sentence-transformer model warmed up at startup")
            except Exception as e:
                _logger.warning("sentence-transformer warm-up skipped: %s", e)

        threading.Thread(target=_warmup_st_model, daemon=True).start()

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
        host="0.0.0.0",
        port=5000,
    )
