"""Phase 6d: skip_rag parameter passthrough.

Tests verify that skip_rag is threaded from call_llm_quality → call_llm_scored →
call_harness_scored → HTTP payload, with True as the default at every level.
"""

from unittest.mock import patch

from smart_llm import call_harness_scored
from llm_helper import call_llm_scored, call_llm_quality


def test_call_harness_scored_forwards_skip_rag_true():
    """Verify: skip_rag=True is included in the HTTP request JSON payload."""
    with patch("smart_llm._http_client") as mock_http:
        mock_http.post.return_value.status_code = 200
        mock_http.post.return_value.json.return_value = {
            "ftal_f": 20, "ftal_t": 20, "ftal_a": 20, "ftal_gap": 10, "output": "result"
        }

        call_harness_scored("task", skip_rag=True)

        payload = mock_http.post.call_args.kwargs["json"]
        assert "skip_rag" in payload
        assert payload["skip_rag"] is True


def test_call_harness_scored_forwards_skip_rag_false():
    """Verify: skip_rag=False is correctly forwarded (not overridden to True)."""
    with patch("smart_llm._http_client") as mock_http:
        mock_http.post.return_value.status_code = 200
        mock_http.post.return_value.json.return_value = {
            "ftal_f": 20, "ftal_t": 20, "ftal_a": 20, "ftal_gap": 10, "output": "result"
        }

        call_harness_scored("task", skip_rag=False)

        payload = mock_http.post.call_args.kwargs["json"]
        assert "skip_rag" in payload
        assert payload["skip_rag"] is False


def test_call_llm_scored_default_skip_rag_is_true():
    """Verify: call_llm_scored() defaults skip_rag=True when not specified."""
    with patch("llm_helper.call_harness_scored") as mock_harness:
        mock_harness.return_value = ("result", {"gap": 10})

        call_llm_scored("task")

        assert mock_harness.call_args.kwargs.get("skip_rag") is True


def test_call_llm_quality_forwards_skip_rag_to_scored():
    """Verify: call_llm_quality(skip_rag=False) passes False through to call_llm_scored."""
    with patch("llm_helper.call_llm_scored") as mock_scored:
        mock_scored.return_value = ("result", {"gap": 10})

        call_llm_quality("task", skip_rag=False)

        assert mock_scored.call_args.kwargs.get("skip_rag") is False
