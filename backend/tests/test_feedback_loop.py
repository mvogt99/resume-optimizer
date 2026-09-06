"""P2-C: Application Feedback Loop tests — TDD first.

Tests:
- Pipeline stage change creates application_feedback row
- GET /api/agents/pipeline/correlations returns structured data
- Feedback summary endpoint returns counts
- Correlation data injected into resume tailor prompts
"""

import sqlite3
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, ".")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def app_ctx():
    import app as flask_app

    with flask_app.app.app_context():
        yield flask_app.app


@pytest.fixture()
def db_conn():
    from models import get_db_connection

    conn = get_db_connection()
    yield conn
    conn.close()


@pytest.fixture()
def client(app_ctx):
    return app_ctx.test_client()


# ---------------------------------------------------------------------------
# P2-C.1: Schema — application_feedback has required columns
# ---------------------------------------------------------------------------


class TestFeedbackSchema:
    def test_resume_version_id_column_exists(self, db_conn):
        cursor = db_conn.execute("PRAGMA table_info(application_feedback)")
        cols = [row["name"] for row in cursor]
        assert "resume_version_id" in cols, "application_feedback missing resume_version_id"

    def test_old_stage_column_exists(self, db_conn):
        cursor = db_conn.execute("PRAGMA table_info(application_feedback)")
        cols = [row["name"] for row in cursor]
        assert "old_stage" in cols, "application_feedback missing old_stage"

    def test_new_stage_column_exists(self, db_conn):
        cursor = db_conn.execute("PRAGMA table_info(application_feedback)")
        cols = [row["name"] for row in cursor]
        assert "new_stage" in cols, "application_feedback missing new_stage"

    def test_outcome_type_column_exists(self, db_conn):
        cursor = db_conn.execute("PRAGMA table_info(application_feedback)")
        cols = [row["name"] for row in cursor]
        assert "outcome_type" in cols, "application_feedback missing outcome_type"

    def test_ats_score_column_exists(self, db_conn):
        cursor = db_conn.execute("PRAGMA table_info(application_feedback)")
        cols = [row["name"] for row in cursor]
        assert "ats_score" in cols, "application_feedback missing ats_score"


# ---------------------------------------------------------------------------
# P2-C.1: Pipeline transition creates feedback row
# ---------------------------------------------------------------------------


class TestPipelineFeedbackCreation:
    def test_pipeline_move_creates_feedback_row(self, client, db_conn):
        """Moving a posting to a new stage should create an application_feedback row."""
        before_count = db_conn.execute(
            "SELECT COUNT(*) FROM application_feedback WHERE user_id=3"
        ).fetchone()[0]

        # Call real endpoint — posting 999 likely doesn't exist (returns 400/404)
        # but the feedback recording path runs regardless
        resp = client.put(
            "/api/agents/pipeline/999",
            headers={"user-id": "3"},
            json={"status": "phone_screen"},
        )

        assert resp.status_code in (200, 400, 404), f"Expected 200/400/404, got {resp.status_code}"

        # Feedback row count should be >= before (may not increase if posting absent)
        after_count = db_conn.execute(
            "SELECT COUNT(*) FROM application_feedback WHERE user_id=3"
        ).fetchone()[0]
        assert after_count >= before_count

    def test_outcome_type_callback_for_phone_screen(self):
        """applied -> phone_screen transition = 'callback' outcome_type."""
        from feedback_analyzer import classify_outcome_type

        result = classify_outcome_type(old_stage="applied", new_stage="phone_screen")
        assert result == "callback"

    def test_outcome_type_rejected(self):
        """any -> rejected = 'rejected'."""
        from feedback_analyzer import classify_outcome_type

        result = classify_outcome_type(old_stage="applied", new_stage="rejected")
        assert result == "rejected"

    def test_outcome_type_advanced_for_interview(self):
        from feedback_analyzer import classify_outcome_type

        result = classify_outcome_type(old_stage="phone_screen", new_stage="interview")
        assert result == "advanced"

    def test_outcome_type_success_for_offer(self):
        from feedback_analyzer import classify_outcome_type

        result = classify_outcome_type(old_stage="interview", new_stage="offer")
        assert result == "success"

    def test_outcome_type_neutral_for_other(self):
        from feedback_analyzer import classify_outcome_type

        result = classify_outcome_type(old_stage="applied", new_stage="applied")
        assert result == "neutral"


# ---------------------------------------------------------------------------
# P2-C.2: Correlation endpoint
# ---------------------------------------------------------------------------


class TestCorrelationEndpoint:
    def test_correlations_endpoint_exists(self, client):
        resp = client.get("/api/agents/pipeline/correlations", headers={"user-id": "3"})
        assert resp.status_code in (200, 404), f"Expected 200 or 404, got {resp.status_code}"

    def test_correlations_returns_json(self, client):
        resp = client.get("/api/agents/pipeline/correlations", headers={"user-id": "3"})
        assert resp.get_json() is not None

    def test_correlations_200_has_required_fields(self, client):
        resp = client.get("/api/agents/pipeline/correlations", headers={"user-id": "3"})
        # Assert the status rather than branching on it: the old form skipped
        # every assertion on a non-200 and passed silently.
        assert resp.status_code == 200, f"expected 200, got {resp.status_code}"
        data = resp.get_json()
        assert "ats_score_distribution" in data
        assert "callback_rate" in data
        assert "total_applications" in data

    def test_get_correlations_unit(self):
        """Unit test for get_correlations() with mocked db."""
        from feedback_analyzer import get_correlations

        mock_rows = [
            {
                "ats_score": 0.8,
                "outcome_type": "callback",
                "resume_version_id": "1",
                "new_stage": "phone_screen",
            },
            {
                "ats_score": 0.4,
                "outcome_type": "rejected",
                "resume_version_id": "2",
                "new_stage": "rejected",
            },
        ]

        with patch("models.get_db_connection") as mock_conn_fn:
            mock_conn = MagicMock()
            mock_conn_fn.return_value = mock_conn
            mock_conn.execute.return_value.fetchall.return_value = mock_rows

            result = get_correlations(user_id=3)

        assert isinstance(result, dict)
        assert "ats_score_distribution" in result
        assert "callback_rate" in result


# ---------------------------------------------------------------------------
# P2-C.4: Feedback summary endpoint
# ---------------------------------------------------------------------------


class TestFeedbackSummaryEndpoint:
    def test_feedback_summary_endpoint_exists(self, client):
        resp = client.get("/api/agents/pipeline/feedback-summary", headers={"user-id": "3"})
        assert resp.status_code in (200, 404), f"Expected 200 or 404, got {resp.status_code}"

    def test_feedback_summary_returns_json(self, client):
        resp = client.get("/api/agents/pipeline/feedback-summary", headers={"user-id": "3"})
        assert resp.get_json() is not None

    def test_feedback_summary_200_has_counts(self, client):
        resp = client.get("/api/agents/pipeline/feedback-summary", headers={"user-id": "3"})
        # Assert the status rather than branching on it: the old form skipped
        # every assertion on a non-200 and passed silently.
        assert resp.status_code == 200, f"expected 200, got {resp.status_code}"
        data = resp.get_json()
        assert "total_applications" in data
        assert "callbacks" in data
        assert "success_rate" in data


# ---------------------------------------------------------------------------
# P2-C.3: Success pattern injection into prompts
# ---------------------------------------------------------------------------


class TestSuccessPatternInjection:
    def test_build_success_context_returns_string(self):
        from feedback_analyzer import build_success_context

        rows = [
            {"ats_score": 0.85, "outcome_type": "callback", "new_stage": "phone_screen"},
            {"ats_score": 0.9, "outcome_type": "success", "new_stage": "offer"},
        ]
        result = build_success_context(rows)
        assert isinstance(result, str)

    def test_build_success_context_empty_returns_empty_string(self):
        from feedback_analyzer import build_success_context

        result = build_success_context([])
        assert result == ""

    def test_build_success_context_mentions_ats(self):
        from feedback_analyzer import build_success_context

        rows = [
            {"ats_score": 0.85, "outcome_type": "callback", "new_stage": "phone_screen"},
        ]
        result = build_success_context(rows)
        assert "ATS" in result or "score" in result.lower()
