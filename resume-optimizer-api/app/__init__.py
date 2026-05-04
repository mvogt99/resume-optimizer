"""Flask app factory for resume-optimizer-api."""
from flask import Flask


def create_app() -> Flask:
    app = Flask(__name__)
    from app.routes import register_routes  # noqa: PLC0415
    register_routes(app)
    return app
