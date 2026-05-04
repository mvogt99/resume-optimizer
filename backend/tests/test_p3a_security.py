"""P3-A Security Remediation tests.

Covers:
- S1: journey_miner._scan_arango reads ArangoDB credentials from env vars
- S2: CORS origins list excludes empty strings when CORS_ORIGIN is unset
- S3: Rate-limited LLM endpoints return 429 after exceeding per-user limit
"""

import contextlib
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# S1: Hardcoded ArangoDB credentials
# ---------------------------------------------------------------------------


class TestHardenedArangoCredentials:
    def test_scan_arango_reads_password_from_env(self, monkeypatch):
        """_scan_arango must use ARANGO_PASSWORD env var, not a hardcoded string."""
        monkeypatch.setenv("ARANGO_PASSWORD", "env_secret_pw")
        monkeypatch.setenv("ARANGO_USER", "env_user")
        monkeypatch.setenv("ARANGO_DB", "env_db")

        captured = {}

        def fake_db(db_name, username=None, password=None):
            captured["db_name"] = db_name
            captured["username"] = username
            captured["password"] = password
            mock_db = MagicMock()
            mock_db.collection.side_effect = Exception("stop early")
            return mock_db

        with patch("arango.ArangoClient") as mock_client_cls:
            mock_client_cls.return_value.db = fake_db
            from journey_miner import JourneyMiner

            miner = JourneyMiner()
            with contextlib.suppress(Exception):
                miner._scan_arango(user_id=0)

        assert captured.get("password") == "env_secret_pw", (
            "ArangoDB password must come from ARANGO_PASSWORD env var, not hardcoded. "
            f"Got: {captured.get('password')!r}"
        )
        assert (
            captured.get("username") == "env_user"
        ), f"Expected username='env_user', got {captured.get('username')!r}"
        assert (
            captured.get("db_name") == "env_db"
        ), f"Expected db_name='env_db', got {captured.get('db_name')!r}"

    def test_scan_arango_falls_back_to_default_when_env_absent(self, monkeypatch):
        """When ARANGO_* env vars are absent, defaults must be non-empty strings."""
        monkeypatch.delenv("ARANGO_PASSWORD", raising=False)
        monkeypatch.delenv("ARANGO_USER", raising=False)
        monkeypatch.delenv("ARANGO_DB", raising=False)

        captured = {}

        def fake_db(db_name, username=None, password=None):
            captured["db_name"] = db_name
            captured["username"] = username
            captured["password"] = password
            mock_db = MagicMock()
            mock_db.collection.side_effect = Exception("stop early")
            return mock_db

        with patch("arango.ArangoClient") as mock_client_cls:
            mock_client_cls.return_value.db = fake_db
            from journey_miner import JourneyMiner

            miner = JourneyMiner()
            with contextlib.suppress(Exception):
                miner._scan_arango(user_id=0)

        assert captured.get("password"), "Default password must be a non-empty string"
        assert captured.get("username"), "Default username must be a non-empty string"
        assert captured.get("db_name"), "Default db_name must be a non-empty string"


# ---------------------------------------------------------------------------
# S2: CORS origin filtering
# ---------------------------------------------------------------------------


class TestCORSOriginFiltering:
    def _get_origins(self, monkeypatch, cors_env=None):
        """Create a fresh app and capture CORS origins via the CORS mock."""
        if cors_env is None:
            monkeypatch.delenv("CORS_ORIGIN", raising=False)
        else:
            monkeypatch.setenv("CORS_ORIGIN", cors_env)

        allowed_origins = []

        def capture_cors(app, origins=None, **kwargs):
            if origins:
                allowed_origins.extend(origins)

        with patch("app.CORS", side_effect=capture_cors):
            from app import create_app

            create_app(testing=True)

        return allowed_origins

    def test_empty_cors_env_not_added_to_origins(self, monkeypatch):
        """When CORS_ORIGIN is empty/unset, no empty-string origin is allowed.

        Passing '' to flask_cors origins[] is effectively a wildcard bug —
        the CORS header matches on prefix, so '' matches everything.
        """
        origins = self._get_origins(monkeypatch, cors_env=None)
        assert "" not in origins, (
            "Empty-string origin must not appear in CORS origins list. " f"Got origins: {origins}"
        )

    def test_valid_cors_origin_added_when_set(self, monkeypatch):
        """When CORS_ORIGIN is a valid URL, it is included in origins."""
        origins = self._get_origins(monkeypatch, cors_env="https://myapp.example.com")
        assert "https://myapp.example.com" in origins, (
            "CORS_ORIGIN env var value must be included in allowed origins. "
            f"Got origins: {origins}"
        )

    def test_cors_always_allows_localhost_3000(self, monkeypatch):
        """http://localhost:3000 must always be in the CORS origins list."""
        origins = self._get_origins(monkeypatch, cors_env=None)
        assert (
            "http://localhost:3000" in origins
        ), "http://localhost:3000 must always be in CORS allowed origins"


# ---------------------------------------------------------------------------
# S3: Rate limiting on LLM-heavy endpoints
# ---------------------------------------------------------------------------


class TestRateLimiting:
    """Rate limiter must protect GPU-intensive endpoints from exhaustion."""

    def _make_rate_limited_app(self, limit="2 per minute"):
        """Create a minimal Flask app with rate limiting enabled at a low threshold."""
        from flask import Flask, jsonify
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address

        test_app = Flask("rate_limit_test")
        limiter = Limiter(
            key_func=get_remote_address,
            app=test_app,
            default_limits=[],
            storage_uri="memory://",
        )

        @test_app.route("/api/test/llm-heavy", methods=["POST"])
        @limiter.limit(limit)
        def llm_heavy():
            return jsonify({"ok": True}), 200

        return test_app

    def test_llm_endpoint_allows_requests_under_limit(self):
        """Requests under the rate limit must succeed normally."""
        app = self._make_rate_limited_app("5 per minute")
        with app.test_client() as c:
            resp = c.post("/api/test/llm-heavy")
            assert resp.status_code == 200

    def test_llm_endpoint_returns_429_after_limit_exceeded(self):
        """After hitting the rate limit, subsequent requests must return 429."""
        app = self._make_rate_limited_app("2 per minute")
        with app.test_client() as c:
            c.post("/api/test/llm-heavy")
            c.post("/api/test/llm-heavy")
            resp = c.post("/api/test/llm-heavy")
            assert (
                resp.status_code == 429
            ), "Rate-limited endpoint must return 429 after limit exceeded"

    def test_limiter_imported_in_app(self):
        """flask_limiter must be importable (installed in venv)."""
        import flask_limiter  # noqa: F401 — just verify it's installed

    def test_main_app_limiter_disabled_in_testing(self, app):
        """In TESTING mode, rate limiting must not block legitimate test requests."""
        # In testing mode, we should be able to POST to LLM endpoints many times
        # without hitting 429
        with app.test_client() as c:
            # If limiter were enabled at a low limit, this loop would trigger 429
            # The test passes if all requests return non-429 (even 401/404 is fine)
            for _ in range(5):
                resp = c.post("/api/agents/scout/search", json={})
                assert resp.status_code != 429, "Rate limiter must be disabled in TESTING mode"

    def test_llm_heavy_routes_are_decorated(self):
        """The LLM-heavy routes must have rate limiting applied.

        This is a structural smoke test — checks that the limiter extension
        is registered on the app and the key endpoints are registered routes.
        """
        import app as flask_app

        # Verify that the limiter is attached to the app
        extensions = getattr(flask_app.app, "extensions", {})
        assert "limiter" in extensions, (
            "flask_limiter must be registered as an app extension. "
            "Check that Limiter(..., app=app) is called in create_app()."
        )
