"""Round 2 Gate — MEDIUM severity issue tests.

M1: Unsafe float()/int() on query params — should return 400, not 500
M2: Scraper error returns HTTP 200 — should return 422
M3: _persist_acceptance logs at WARNING on failure — should be ERROR
M4: Coach answer has misleading retry loop — should call process_answer once
M5: agent_status() missing @require_auth — should require auth
"""

import logging
from unittest.mock import MagicMock, patch

import pytest


# ── M1: Input validation ───────────────────────────────────────────────────


class TestM1InputValidation:
    """Garbage query params must return 400, not 500."""

    def test_scout_postings_invalid_min_score(self, client, auth_headers):
        """GET /agents/scout/postings?min_score=abc → 400."""
        resp = client.get(
            "/api/agents/scout/postings?min_score=abc",
            headers=auth_headers,
        )
        assert resp.status_code == 400, (
            f"Expected 400 for invalid min_score, got {resp.status_code}"
        )

    def test_scout_postings_invalid_limit(self, client, auth_headers):
        """GET /agents/scout/postings?limit=xyz → 400."""
        resp = client.get(
            "/api/agents/scout/postings?limit=xyz",
            headers=auth_headers,
        )
        assert resp.status_code == 400, (
            f"Expected 400 for invalid limit, got {resp.status_code}"
        )

    def test_agent_runs_invalid_limit(self, client, auth_headers):
        """GET /agents/runs?limit=xyz → 400."""
        resp = client.get(
            "/api/agents/runs?limit=xyz",
            headers=auth_headers,
        )
        assert resp.status_code == 400, (
            f"Expected 400 for invalid limit, got {resp.status_code}"
        )


# ── M2: Scraper error status code ─────────────────────────────────────────


class TestM2ScraperErrorCode:
    """Scraper errors must NOT return 200."""

    @patch("job_scraper.scrape_job_url")
    def test_scrape_url_error_returns_422(self, mock_scrape, client, auth_headers):
        """POST /agents/scout/scrape-url with error → 422, not 200."""
        mock_scrape.return_value = {
            "error": "Could not access URL",
            "title": "",
            "description": "",
        }
        resp = client.post(
            "/api/agents/scout/scrape-url",
            headers=auth_headers,
            json={"url": "https://example.com/job/123"},
        )
        assert resp.status_code == 422, (
            f"Expected 422 for scraper error, got {resp.status_code}. "
            "Scraper errors must not return 200."
        )


# ── M3: Error log level ───────────────────────────────────────────────────


class TestM3ErrorLogLevel:
    """_persist_acceptance must log at ERROR level on failure, not WARNING."""

    def test_persist_acceptance_logs_error_on_failure(self):
        """When DB write fails, log level should be ERROR."""
        from agents_routes_common import _persist_acceptance

        # Create a mock acceptance
        mock_acceptance = MagicMock()
        mock_acceptance.passed = True
        mock_acceptance.a_score_penalty = 0
        mock_acceptance.to_json.return_value = "{}"

        with patch("agents_routes_common.get_db_connection") as mock_conn:
            # Force an exception
            mock_conn.side_effect = RuntimeError("DB unavailable")

            with patch("agents_routes_common.logger") as mock_logger:
                _persist_acceptance(1, "test_agent", mock_acceptance, 1)

                # Should have called logger.error, not logger.warning
                assert mock_logger.error.called, (
                    "_persist_acceptance logged at WARNING instead of ERROR "
                    "when DB write failed. Silent data loss is an ERROR."
                )
                assert not mock_logger.warning.called, (
                    "_persist_acceptance still uses logger.warning for DB failures"
                )


# ── M4: Coach answer no retry scaffolding ──────────────────────────────────


class TestM4CoachAnswerNoRetry:
    """Coach answer must not have retry loop scaffolding."""

    def test_coach_answer_no_loop(self):
        """coach_answer function should not contain a for loop."""
        import inspect
        import agents_routes_coach

        source = inspect.getsource(agents_routes_coach.coach_answer)

        # Should NOT have a for loop — non-idempotent function runs exactly once
        assert "for attempt in range" not in source, (
            "coach_answer still contains a retry loop. "
            "Non-idempotent function must call process_answer exactly once."
        )

    def test_coach_answer_no_should_retry(self):
        """coach_answer should not call should_retry."""
        import inspect
        import agents_routes_coach

        source = inspect.getsource(agents_routes_coach.coach_answer)

        assert "should_retry" not in source, (
            "coach_answer still calls should_retry(). "
            "Non-idempotent function has no retry — remove dead code."
        )

    def test_coach_answer_no_retrying_log(self):
        """coach_answer should not log 'retrying'."""
        import inspect
        import agents_routes_coach

        source = inspect.getsource(agents_routes_coach.coach_answer)

        assert "retrying" not in source.lower(), (
            "coach_answer still logs 'retrying'. "
            "Remove dead retry log message."
        )


# ── M5: agent_status requires auth ────────────────────────────────────────


class TestM5AgentStatusAuth:
    """agent_status endpoint must require authentication."""

    def test_agent_status_requires_auth(self, client):
        """GET /agents/status without auth → 401."""
        resp = client.get("/api/agents/status")
        assert resp.status_code == 401, (
            f"Expected 401 for unauthenticated /agents/status, got {resp.status_code}. "
            "agent_status() is missing @require_auth."
        )
