"""Phase 6b: Retry logic for call_llm_quality().

Tests verify retry fires on text=None (harness unreachable), does NOT fire on gap
failure, respects max_attempts, and succeeds on first attempt without retry.
"""

from unittest.mock import patch

from llm_helper import call_llm_quality


def test_call_llm_quality_retries_on_none_result():
    """Verify: Retry fires when first attempt returns text=None, succeeds on second."""
    with patch("llm_helper.call_llm_scored") as mock_scored, \
         patch("llm_helper.time") as mock_time:
        mock_scored.side_effect = [(None, None), ("good_text", {"gap": 10})]

        result = call_llm_quality("task")

        assert mock_scored.call_count == 2
        mock_time.sleep.assert_called_once_with(2)
        assert result == "good_text"


def test_call_llm_quality_no_retry_on_gap_failure():
    """Verify: Gap failure falls back to call_direct() immediately — no sleep/retry."""
    with patch("llm_helper.call_llm_scored") as mock_scored, \
         patch("llm_helper.call_direct") as mock_direct, \
         patch("llm_helper.time") as mock_time:
        mock_scored.return_value = ("text", {"gap": 40})
        mock_direct.return_value = "direct_fallback"

        result = call_llm_quality("task")

        assert mock_scored.call_count == 1
        mock_time.sleep.assert_not_called()
        assert result == "direct_fallback"


def test_call_llm_quality_exhausts_all_attempts_returns_none():
    """Verify: Returns None after all attempts return text=None."""
    with patch("llm_helper.call_llm_scored") as mock_scored, \
         patch("llm_helper.time"):
        mock_scored.side_effect = [(None, None), (None, None)]

        result = call_llm_quality("task", max_attempts=2)

        assert mock_scored.call_count == 2
        assert result is None


def test_call_llm_quality_succeeds_on_first_attempt_no_retry():
    """Verify: Successful first attempt returns immediately with no sleep."""
    with patch("llm_helper.call_llm_scored") as mock_scored, \
         patch("llm_helper.time") as mock_time:
        mock_scored.return_value = ("text", {"gap": 10})

        result = call_llm_quality("task")

        assert mock_scored.call_count == 1
        mock_time.sleep.assert_not_called()
        assert result == "text"
