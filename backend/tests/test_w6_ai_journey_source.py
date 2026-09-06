"""Tests for W6: ai_journey_source.py.

Verifies event structure, graceful failure when DB unavailable,
and that collect_all returns a list.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch

import ai_journey_source as ajs


# ──────────────────────────────────────────────────────────────
# collect_agent_run_events
# ──────────────────────────────────────────────────────────────

def _make_mock_row(agent_type="resume_tailor", total=10, completed=9,
                   first="2026-01-01 10:00:00", last="2026-03-15 12:00:00",
                   avg_gap=20.0, accept_pass=8, accept_total=9, avg_ms=2500):
    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "agent_type": agent_type,
        "total_runs": total,
        "completed": completed,
        "first_used": first,
        "last_used": last,
        "avg_gap": avg_gap,
        "accept_pass": accept_pass,
        "accept_total": accept_total,
        "avg_duration_ms": avg_ms,
    }[key]
    return row


class TestCollectAgentRunEvents:
    def _mock_db(self, rows):
        """Stand in for models.get_db, which is a CONTEXT MANAGER.

        collect_agent_run_events does `with get_db() as conn:` and then assigns
        `conn.execute(...).fetchall()` to `rows`. The earlier version stubbed
        fetchall correctly but patched get_db_connection, which this code path
        does not use, so the patch never took effect.
        """
        mock_conn = MagicMock()
        # The caller does conn.execute(...).fetchall(); both parts must be stubbed.
        mock_conn.execute.return_value.fetchall.return_value = rows
        mock_ctx = MagicMock()
        mock_ctx.__enter__.return_value = mock_conn
        mock_ctx.__exit__.return_value = False
        return mock_ctx

    def test_returns_list(self):
        with patch("models.get_db", return_value=self._mock_db([])):
            result = ajs.collect_agent_run_events(1)
        assert isinstance(result, list)

    def test_empty_when_no_rows(self):
        with patch("models.get_db", return_value=self._mock_db([])):
            result = ajs.collect_agent_run_events(1)
        assert result == []

    def test_event_emitted_for_sufficient_runs(self):
        rows = [_make_mock_row(agent_type="resume_tailor", total=10)]
        with patch("models.get_db", return_value=self._mock_db(rows)):
            result = ajs.collect_agent_run_events(1)
        assert len(result) == 1

    def test_no_event_for_few_runs(self):
        rows = [_make_mock_row(agent_type="resume_tailor", total=2)]
        with patch("models.get_db", return_value=self._mock_db(rows)):
            result = ajs.collect_agent_run_events(1)
        assert result == []

    def test_event_has_required_keys(self):
        rows = [_make_mock_row()]
        with patch("models.get_db", return_value=self._mock_db(rows)):
            result = ajs.collect_agent_run_events(1)
        ev = result[0]
        for key in ("source_type", "category", "title", "description", "event_date", "metadata"):
            assert key in ev

    def test_event_category_is_ai_tooling(self):
        rows = [_make_mock_row()]
        with patch("models.get_db", return_value=self._mock_db(rows)):
            result = ajs.collect_agent_run_events(1)
        assert result[0]["category"] == "ai_tooling"

    def test_metadata_has_agent_type(self):
        rows = [_make_mock_row(agent_type="cover_letter")]
        with patch("models.get_db", return_value=self._mock_db(rows)):
            result = ajs.collect_agent_run_events(1)
        assert result[0]["metadata"]["agent_type"] == "cover_letter"

    def test_graceful_on_db_error(self):
        with patch("models.get_db", side_effect=Exception("DB down")):
            result = ajs.collect_agent_run_events(1)
        assert result == []

    def test_multiple_agent_types(self):
        rows = [
            _make_mock_row(agent_type="resume_tailor", total=5),
            _make_mock_row(agent_type="cover_letter", total=4),
            _make_mock_row(agent_type="career_advisor", total=3),
        ]
        with patch("models.get_db", return_value=self._mock_db(rows)):
            result = ajs.collect_agent_run_events(1)
        assert len(result) == 3


# ──────────────────────────────────────────────────────────────
# collect_ftal_harness_events
# ──────────────────────────────────────────────────────────────

class TestCollectFtalHarnessEvents:
    def test_returns_list(self):
        with patch("httpx.get", side_effect=Exception("offline")):
            result = ajs.collect_ftal_harness_events()
        assert isinstance(result, list)

    def test_empty_when_harness_offline(self):
        with patch("httpx.get", side_effect=Exception("connection refused")):
            result = ajs.collect_ftal_harness_events()
        assert result == []

    def test_empty_when_bad_status(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        with patch("httpx.get", return_value=mock_resp):
            result = ajs.collect_ftal_harness_events()
        assert result == []

    def test_event_emitted_when_sufficient_runs(self):
        mock_stats = {"total_runs": 50, "pass_rate_pct": 85.0, "avg_gap": 22.0}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_stats
        with patch("httpx.get", return_value=mock_resp):
            result = ajs.collect_ftal_harness_events()
        assert len(result) == 1
        assert result[0]["category"] == "ai_tooling"

    def test_no_event_for_few_runs(self):
        mock_stats = {"total_runs": 2}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_stats
        with patch("httpx.get", return_value=mock_resp):
            result = ajs.collect_ftal_harness_events()
        assert result == []

    def test_event_date_is_today_isoformat(self):
        import datetime
        mock_stats = {"total_runs": 50}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_stats
        with patch("httpx.get", return_value=mock_resp):
            result = ajs.collect_ftal_harness_events()
        assert result[0]["event_date"] == datetime.date.today().isoformat()


# ──────────────────────────────────────────────────────────────
# collect_all
# ──────────────────────────────────────────────────────────────

class TestCollectAll:
    def test_returns_list(self):
        with patch("ai_journey_source.collect_agent_run_events", return_value=[]):
            with patch("ai_journey_source.collect_ftal_harness_events", return_value=[]):
                result = ajs.collect_all(user_id=1)
        assert isinstance(result, list)

    def test_combines_both_sources(self):
        ev1 = {"source_type": "ai_platform_agent", "category": "ai_tooling", "title": "A"}
        ev2 = {"source_type": "ftal_harness_stats", "category": "ai_tooling", "title": "B"}
        with patch("ai_journey_source.collect_agent_run_events", return_value=[ev1]):
            with patch("ai_journey_source.collect_ftal_harness_events", return_value=[ev2]):
                result = ajs.collect_all(user_id=1)
        assert len(result) == 2

    def test_empty_when_no_data(self):
        with patch("ai_journey_source.collect_agent_run_events", return_value=[]):
            with patch("ai_journey_source.collect_ftal_harness_events", return_value=[]):
                result = ajs.collect_all(user_id=1)
        assert result == []
