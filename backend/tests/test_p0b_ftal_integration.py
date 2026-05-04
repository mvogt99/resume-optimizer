"""Phase P0-B tests: FTAL harness integration — call_llm_scored() and agent_runs FTAL columns."""

import os
import sqlite3
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import smart_llm  # noqa: E402

# ---------------------------------------------------------------------------
# P0-B.1: call_llm_scored() — returns (result, ftal_scores)
# ---------------------------------------------------------------------------


class TestCallLlmScored:
    """call_llm_scored(task, task_type, max_tokens) -> (str, dict | None)"""

    def _mock_harness_response(self, result="test output", f=22, t=20, a=18, gap=35):
        """Build a mock requests.Response for a successful harness call.

        Matches real harness response format: top-level ftal_* keys.
        """
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "result": result,
            "ftal_f": f,
            "ftal_t": t,
            "ftal_a": a,
            "ftal_gap": gap,
            "job_id": "test-job-123",
        }
        return mock_resp

    def test_returns_tuple(self):
        from llm_helper import call_llm_scored

        with patch.object(
            smart_llm._http_client, "post", return_value=self._mock_harness_response()
        ):
            result = call_llm_scored("summarize this", task_type="analysis")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_result_is_string(self):
        from llm_helper import call_llm_scored

        with patch.object(
            smart_llm._http_client, "post", return_value=self._mock_harness_response("hello")
        ):
            text, _ = call_llm_scored("summarize this", task_type="analysis")
        assert text == "hello"

    def test_scores_dict_has_required_keys(self):
        from llm_helper import call_llm_scored

        with patch.object(
            smart_llm._http_client,
            "post",
            return_value=self._mock_harness_response(f=22, t=20, a=18, gap=35),
        ):
            _, scores = call_llm_scored("summarize this", task_type="analysis")
        assert isinstance(scores, dict)
        for key in ("f", "t", "a", "gap"):
            assert key in scores, f"Missing key: {key}"

    def test_scores_values_match_harness_response(self):
        from llm_helper import call_llm_scored

        with patch.object(
            smart_llm._http_client,
            "post",
            return_value=self._mock_harness_response(f=25, t=24, a=23, gap=20),
        ):
            _, scores = call_llm_scored("plan architecture", task_type="planning")
        assert scores["f"] == 25
        assert scores["t"] == 24
        assert scores["a"] == 23
        assert scores["gap"] == 20

    def test_pass_when_gap_below_30(self):
        from llm_helper import call_llm_scored

        with patch.object(
            smart_llm._http_client,
            "post",
            return_value=self._mock_harness_response(f=25, t=24, a=23, gap=25),
        ):
            _, scores = call_llm_scored("write narrative", task_type="reasoning")
        assert scores["gap"] < 30

    def test_fallback_on_harness_unreachable(self):
        """When harness is unreachable, falls back to call_direct; scores is None."""
        from llm_helper import call_llm_scored

        with patch.object(smart_llm._http_client, "post", side_effect=ConnectionError("refused")):
            text, scores = call_llm_scored("write narrative", task_type="reasoning")
        # Result may be None (if direct also fails in test env) but scores must be None
        assert scores is None

    def test_fallback_on_harness_500(self):
        """When harness returns non-200, falls back; scores is None."""
        from llm_helper import call_llm_scored

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        with patch.object(smart_llm._http_client, "post", return_value=mock_resp):
            _, scores = call_llm_scored("write narrative", task_type="reasoning")
        assert scores is None

    def test_accepts_custom_max_tokens(self):
        """max_tokens parameter is passed through."""
        from llm_helper import call_llm_scored

        with patch.object(
            smart_llm._http_client, "post", return_value=self._mock_harness_response()
        ) as mock:
            call_llm_scored("task", task_type="coding", max_tokens=2048)
        call_kwargs = mock.call_args
        # The POST json payload should include max_tokens=2048
        payload = call_kwargs[1].get("json") or call_kwargs[0][1]
        assert payload.get("max_tokens") == 2048

    def test_default_task_type_is_reasoning(self):
        """Default task_type is 'reasoning' — appropriate for narrative generation."""
        from llm_helper import call_llm_scored

        with patch.object(
            smart_llm._http_client, "post", return_value=self._mock_harness_response()
        ) as mock:
            call_llm_scored("write a story")
        # Use first call — subsequent calls may be inference/harness fallback with different type
        first_call = mock.call_args_list[0]
        payload = first_call[1].get("json") or first_call[0][1]
        assert payload.get("task_type") == "reasoning"


# ---------------------------------------------------------------------------
# call_llm_quality() gap-threshold fallback
# ---------------------------------------------------------------------------


class TestCallLlmQualityFallback:
    """call_llm_quality() falls back to call_direct() when harness gap >= 30."""

    def _mock_harness_response(self, result="harness output", gap=35):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "result": result,
            "ftal_f": 20,
            "ftal_t": 20,
            "ftal_a": 10,
            "ftal_gap": gap,
            "job_id": "test-job-quality",
        }
        return mock_resp

    def test_returns_direct_output_when_gap_above_threshold(self):
        """When harness gap >= 30, call_direct() output is returned instead."""
        from llm_helper import call_llm_quality

        with (
            patch.object(
                smart_llm._http_client, "post", return_value=self._mock_harness_response(gap=35)
            ),
            patch("smart_llm._call_inference", return_value="direct output") as mock_direct,
        ):
            result = call_llm_quality("write a STAR bullet", task_type="reasoning")
        # called by both call_llm_scored gap-fallback and call_llm_quality
        mock_direct.assert_called()
        assert result == "direct output"

    def test_returns_harness_output_when_gap_below_threshold(self):
        """When harness gap < 30, harness output is returned directly."""
        from llm_helper import call_llm_quality

        with (
            patch.object(
                smart_llm._http_client,
                "post",
                return_value=self._mock_harness_response(result="good harness output", gap=20),
            ),
            patch("smart_llm._call_inference") as mock_direct,
        ):
            result = call_llm_quality("write a STAR bullet", task_type="reasoning")
        mock_direct.assert_not_called()
        assert result == "good harness output"

    def test_gap_exactly_at_threshold_triggers_fallback(self):
        """Gap == 30 (at threshold) triggers fallback."""
        from llm_helper import call_llm_quality

        with (
            patch.object(
                smart_llm._http_client, "post", return_value=self._mock_harness_response(gap=30)
            ),
            patch("smart_llm._call_inference", return_value="direct fallback") as mock_direct,
        ):
            result = call_llm_quality("task", task_type="reasoning")
        # called by both call_llm_scored gap-fallback and call_llm_quality
        mock_direct.assert_called()
        assert result == "direct fallback"

    def test_no_fallback_when_harness_unreachable(self):
        """When harness is unreachable, call_llm_scored() already fell back — no double fallback."""
        from llm_helper import call_llm_quality

        with patch.object(smart_llm._http_client, "post", side_effect=ConnectionError("refused")):
            # Should not raise; result may be None if direct also fails
            result = call_llm_quality("task", task_type="reasoning")
        # No assertion on value — just verify no exception raised
        assert result is None or isinstance(result, str)


# ---------------------------------------------------------------------------
# P0-B.4: agent_runs table — FTAL score columns
# ---------------------------------------------------------------------------


@pytest.fixture
def db_conn_with_agent_runs():
    """In-memory DB with agent_runs table including FTAL columns."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    # Simulate the migration adding FTAL columns
    conn.execute(
        """CREATE TABLE agent_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_type TEXT,
            action TEXT,
            model_used TEXT,
            duration_seconds REAL,
            success INTEGER,
            error TEXT,
            created_at TEXT,
            ftal_f INTEGER,
            ftal_t INTEGER,
            ftal_a INTEGER,
            ftal_gap INTEGER
        )"""
    )
    conn.commit()
    return conn


class TestAgentRunsFtalColumns:
    def test_ftal_columns_exist(self, db_conn_with_agent_runs):
        conn = db_conn_with_agent_runs
        conn.execute(
            """INSERT INTO agent_runs
               (agent_type, action, model_used, duration_seconds, success,
                ftal_f, ftal_t, ftal_a, ftal_gap)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("job_scout", "rescore", "qwen3-coder-30b", 2.5, 1, 22, 20, 18, 40),
        )
        conn.commit()
        row = conn.execute(
            "SELECT ftal_f, ftal_t, ftal_a, ftal_gap FROM agent_runs LIMIT 1"
        ).fetchone()
        assert row["ftal_f"] == 22
        assert row["ftal_t"] == 20
        assert row["ftal_a"] == 18
        assert row["ftal_gap"] == 40

    def test_ftal_columns_nullable(self, db_conn_with_agent_runs):
        """Existing rows without FTAL scores should have NULL for those columns."""
        conn = db_conn_with_agent_runs
        conn.execute(
            "INSERT INTO agent_runs (agent_type, action, success) VALUES (?, ?, ?)",
            ("app_tracker", "followup", 1),
        )
        conn.commit()
        row = conn.execute(
            "SELECT ftal_f, ftal_t, ftal_a, ftal_gap FROM agent_runs LIMIT 1"
        ).fetchone()
        assert row["ftal_f"] is None
        assert row["ftal_gap"] is None

    def test_pass_threshold_query(self, db_conn_with_agent_runs):
        """Can query for runs that passed (gap < 30)."""
        conn = db_conn_with_agent_runs
        conn.executemany(
            """INSERT INTO agent_runs (agent_type, action, success, ftal_gap)
               VALUES (?, ?, ?, ?)""",
            [
                ("job_scout", "rescore", 1, 25),
                ("job_scout", "rescore", 1, 45),
                ("job_scout", "rescore", 1, 15),
            ],
        )
        conn.commit()
        rows = conn.execute(
            "SELECT COUNT(*) FROM agent_runs WHERE ftal_gap IS NOT NULL AND ftal_gap < 30"
        ).fetchone()
        assert rows[0] == 2
