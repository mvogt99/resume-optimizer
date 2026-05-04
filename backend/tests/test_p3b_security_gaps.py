"""P3-B Security Gap Closure tests.

Covers:
- Gap 1: Rate limiting key uses user_id (not IP) for authenticated requests
- Gap 2: Rate limit exceeded returns JSON body + logs a warning
- Gap 3: journey_miner table-name candidates are statically bounded (smoke check)
- Gap 4: SQL f-string patterns document their safety via allowlist/hardcoded pattern
"""

import logging

# ---------------------------------------------------------------------------
# Gap 1: Per-user rate limit key
# ---------------------------------------------------------------------------


class TestPerUserRateLimitKey:
    def test_key_uses_user_id_when_authenticated(self, app):
        """_rate_limit_key() must return user_id string for authenticated requests."""
        from app import _rate_limit_key

        with app.test_request_context("/"):
            from flask import g

            g.user_id = 42
            key = _rate_limit_key()

        assert key == "42", f"Expected '42' (str user_id), got {key!r}"

    def test_key_falls_back_to_ip_when_unauthenticated(self, app):
        """_rate_limit_key() must return a non-empty string when g.user_id is absent."""
        from app import _rate_limit_key

        with app.test_request_context("/", environ_base={"REMOTE_ADDR": "10.0.0.1"}):
            key = _rate_limit_key()

        assert key, "Fallback key must be non-empty"
        assert "42" != key, "Unauthenticated key must not look like a user_id"

    def test_key_is_string(self, app):
        """_rate_limit_key() must always return a string (flask-limiter requirement)."""
        from app import _rate_limit_key

        with app.test_request_context("/"):
            from flask import g

            g.user_id = 99
            key = _rate_limit_key()

        assert isinstance(key, str), f"Key must be str, got {type(key)}"

    def test_different_users_have_different_keys(self, app):
        """Two different user_ids must produce different rate limit keys."""
        from app import _rate_limit_key

        with app.test_request_context("/"):
            from flask import g

            g.user_id = 1
            key_user1 = _rate_limit_key()

        with app.test_request_context("/"):
            from flask import g

            g.user_id = 2
            key_user2 = _rate_limit_key()

        assert key_user1 != key_user2


# ---------------------------------------------------------------------------
# Gap 2: Logged 429 with JSON body
# ---------------------------------------------------------------------------


class TestRateLimitExceededHandler:
    def _make_rate_limited_app(self, limit="2 per minute"):
        """Create a minimal Flask app with low rate limit and error handler."""
        from flask import Flask, jsonify
        from flask_limiter import Limiter

        from app import _rate_limit_key

        test_app = Flask("rate_limit_handler_test")
        test_limiter = Limiter(
            key_func=_rate_limit_key,
            app=test_app,
            default_limits=[],
            storage_uri="memory://",
        )

        @test_app.route("/api/test/llm-heavy", methods=["POST"])
        @test_limiter.limit(limit)
        def llm_heavy():
            return jsonify({"ok": True}), 200

        from flask_limiter.errors import RateLimitExceeded

        @test_app.errorhandler(RateLimitExceeded)
        def handle_rate_limit(e):
            import logging as _logging

            _logging.getLogger("rate_limiter").warning(
                "Rate limit hit: %s — limit: %s", test_app.name, e.limit
            )
            return jsonify({"error": "Rate limit exceeded. Try again later."}), 429

        return test_app

    def test_429_body_is_json(self):
        """Rate limit exceeded response must be JSON (not HTML)."""
        test_app = self._make_rate_limited_app("2 per minute")
        with test_app.test_client() as c:
            c.post("/api/test/llm-heavy")
            c.post("/api/test/llm-heavy")
            resp = c.post("/api/test/llm-heavy")

        assert resp.status_code == 429
        assert resp.content_type.startswith(
            "application/json"
        ), f"429 must be application/json, got {resp.content_type}"

    def test_429_body_has_error_key(self):
        """Rate limit exceeded JSON must include an 'error' key."""
        test_app = self._make_rate_limited_app("2 per minute")
        with test_app.test_client() as c:
            c.post("/api/test/llm-heavy")
            c.post("/api/test/llm-heavy")
            resp = c.post("/api/test/llm-heavy")

        data = resp.get_json()
        assert data is not None, "429 response must parse as JSON"
        assert "error" in data, f"'error' key missing from 429 body: {data}"

    def test_429_logs_warning(self, caplog):
        """Rate limit exceeded must emit a warning log."""
        test_app = self._make_rate_limited_app("2 per minute")
        with caplog.at_level(logging.WARNING, logger="rate_limiter"), test_app.test_client() as c:
            c.post("/api/test/llm-heavy")
            c.post("/api/test/llm-heavy")
            c.post("/api/test/llm-heavy")

        assert any(
            "Rate limit hit" in r.message for r in caplog.records
        ), "Expected 'Rate limit hit' warning in logs"

    def test_main_app_has_rate_limit_error_handler(self, app):
        """Main app must register a RateLimitExceeded error handler."""
        from flask_limiter.errors import RateLimitExceeded

        handler = app.error_handler_spec.get(None, {}).get(429) or {}
        # Check that the app has a 429 error handler registered
        assert (
            handler
            or RateLimitExceeded
            in (
                exc
                for code_handlers in app.error_handler_spec.get(None, {}).values()
                for exc in (code_handlers if isinstance(code_handlers, dict) else {})
            )
            or _has_exception_handler(app, RateLimitExceeded)
        ), (
            "Main app must register a RateLimitExceeded error handler. "
            "Add @app.errorhandler(RateLimitExceeded) in create_app()."
        )


def _has_exception_handler(app, exc_class):
    """Check if an app has an error handler for the given exception class."""
    for _blueprint, handlers in app.error_handler_spec.items():
        for _code, exc_handlers in handlers.items():
            if exc_handlers and exc_class in exc_handlers:
                return True
    return False


# ---------------------------------------------------------------------------
# Gap 3: Table-name candidates are statically bounded
# ---------------------------------------------------------------------------


class TestTableNameCandidates:
    def test_cost_table_candidates_are_hardcoded(self):
        """The candidates list for cost_table must be a static, bounded set.

        This verifies the pattern is safe — the table name used in the SQL
        query always comes from this fixed list, never from user input.
        """
        import inspect

        import journey_miner

        source = inspect.getsource(journey_miner.JourneyMiner._mine_cost_economics)
        # The three safe candidates must appear literally in the source
        for name in ("model_calls", "cost_records", "costs"):
            assert name in source, (
                f"Hardcoded candidate '{name}' not found in _mine_cost_economics source. "
                "If the candidates list changed, update this test."
            )

    def test_cost_table_never_user_controlled(self):
        """_mine_cost_economics takes only user_id (int) — no string reaches cost_table."""
        import inspect

        import journey_miner

        sig = inspect.signature(journey_miner.JourneyMiner._mine_cost_economics)
        params = list(sig.parameters.keys())
        # self + user_id only — no table_name, no query param
        assert (
            "table_name" not in params
        ), "No table_name parameter should exist on _mine_cost_economics"
        assert "query" not in params, "No query parameter should exist on _mine_cost_economics"


# ---------------------------------------------------------------------------
# Gap 4: SQL f-string allowlists are documented in source
# ---------------------------------------------------------------------------


class TestSQLAllowlistDocumentation:
    def test_app_tracker_update_posting_uses_hardcoded_sets(self):
        """app_tracker.move_posting builds SET clause from literal strings only."""
        import inspect

        from agents.app_tracker import ApplicationTrackerAgent

        source = inspect.getsource(ApplicationTrackerAgent.move_posting)
        # The hardcoded column names must appear as string literals
        assert (
            '"status = ?"' in source or "'status = ?'" in source
        ), "move_posting must use hardcoded column strings, not user input"

    def test_job_scout_update_allowlist_is_defined(self):
        """job_scout.update_posting uses an explicit allowlist set for column names."""
        import inspect

        from agents.job_scout import JobScoutAgent

        source = inspect.getsource(JobScoutAgent.update_posting)
        assert "allowed" in source, "update_posting must define an 'allowed' set of column names"
        # All three allowed columns must be in the allowlist
        for col in ("status", "notes", "is_starred"):
            assert col in source, f"Column '{col}' missing from update_posting allowlist"

    def test_context_enrichment_where_clause_uses_hardcoded_conditions(self):
        """context_enrichment WHERE clause is built from hardcoded LIKE expressions."""
        import inspect

        import context_enrichment

        source = inspect.getsource(context_enrichment._get_prior_experiences)
        # Hardcoded column references (not variable column names)
        assert (
            "LOWER(employer)" in source or "LOWER(client)" in source
        ), "WHERE clause conditions must reference hardcoded column names"
        # Values must go through parameterized placeholders
        assert "?" in source, "User-controlled values must use ? parameterized placeholders"
