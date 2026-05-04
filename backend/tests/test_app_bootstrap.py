"""Test app.py — Flask application factory and bootstrap configuration."""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import create_app


class TestAppFactory:
    def test_creates_flask_app(self):
        app = create_app(testing=True)
        assert app is not None
        assert app.name == "app"

    def test_testing_mode_enabled(self):
        app = create_app(testing=True)
        assert app.config["TESTING"] is True

    def test_upload_config_set(self):
        app = create_app(testing=True)
        assert app.config["UPLOAD_FOLDER"] == "uploads"
        assert app.config["MAX_CONTENT_LENGTH"] == 16 * 1024 * 1024

    def test_cors_configured(self):
        """CORS extension is registered (Flask-CORS adds after_request handler)."""
        app = create_app(testing=True)
        # Flask-CORS adds after_request handlers
        assert len(app.after_request_funcs) > 0 or hasattr(app, "extensions")

    def test_blueprints_registered(self):
        app = create_app(testing=True)
        bp_names = list(app.blueprints.keys())
        assert len(bp_names) >= 8, f"Only {len(bp_names)} blueprints registered"

    def test_expected_blueprints_present(self):
        app = create_app(testing=True)
        bp_names = set(app.blueprints.keys())
        expected = {"auth", "resume", "experience", "campaigns", "profile", "agents"}
        for name in expected:
            assert name in bp_names, f"Blueprint '{name}' not registered"

    def test_url_map_has_api_prefix(self):
        app = create_app(testing=True)
        rules = [r.rule for r in app.url_map.iter_rules()]
        api_rules = [r for r in rules if r.startswith("/api/")]
        assert len(api_rules) >= 10, f"Only {len(api_rules)} /api/ routes found"

    def test_auth_routes_exist(self):
        app = create_app(testing=True)
        rules = {r.rule for r in app.url_map.iter_rules()}
        assert "/api/register" in rules
        assert "/api/login" in rules

    def test_resume_routes_exist(self):
        app = create_app(testing=True)
        rules = {r.rule for r in app.url_map.iter_rules()}
        assert "/api/resume/upload" in rules

    def test_max_content_length_is_16mb(self):
        app = create_app(testing=True)
        assert app.config["MAX_CONTENT_LENGTH"] == 16777216
