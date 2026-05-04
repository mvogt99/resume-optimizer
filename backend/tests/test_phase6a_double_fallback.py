"""Phase 6a: Fix double-fallback bug in llm_helper.py.

Tests verify that call_llm_scored() sets the _fell_back sentinel on gap-threshold
fallback, and that call_llm_quality() skips its own call_direct() when the sentinel
is present — preventing two GPU inference calls for one request.
"""

from unittest.mock import patch

from llm_helper import call_llm_scored, call_llm_quality


def test_call_llm_scored_sets_fell_back_sentinel_on_gap_fallback():
    """Verify: _fell_back sentinel set in scores copy when gap >= threshold triggers fallback."""
    with patch("llm_helper.call_harness_scored") as mock_harness, \
         patch("llm_helper.call_direct") as mock_direct, \
         patch("llm_helper._record_governance_outcome"):
        mock_harness.return_value = ("harness_text", {"gap": 35, "f": 10, "t": 10, "a": 10})
        mock_direct.return_value = "direct_result"

        text, scores = call_llm_scored("task")

        assert scores["_fell_back"] is True
        assert text == "direct_result"
        mock_direct.assert_called_once()


def test_call_llm_quality_skips_second_fallback_when_sentinel_set():
    """Verify: call_llm_quality() does NOT call call_direct() when _fell_back sentinel present."""
    with patch("llm_helper.call_llm_scored") as mock_scored, \
         patch("llm_helper.call_direct") as mock_direct:
        mock_scored.return_value = ("already_direct", {"gap": 35, "_fell_back": True})

        text = call_llm_quality("task")

        mock_direct.assert_not_called()
        assert text == "already_direct"


def test_call_llm_quality_still_falls_back_without_sentinel():
    """Verify: call_llm_quality() still calls call_direct() when no _fell_back sentinel."""
    with patch("llm_helper.call_llm_scored") as mock_scored, \
         patch("llm_helper.call_direct") as mock_direct:
        mock_scored.return_value = ("harness_text", {"gap": 35})
        mock_direct.return_value = "fallback_result"

        text = call_llm_quality("task")

        mock_direct.assert_called_once()
        assert text == "fallback_result"


def test_call_llm_scored_no_sentinel_on_passing_gap():
    """Verify: No _fell_back sentinel added when gap < threshold (no fallback needed).

    call_direct is mocked to return a non-empty string so that IF the threshold guard
    is broken (mutation), the sentinel would be set and this test would fail.
    """
    with patch("llm_helper.call_harness_scored") as mock_harness, \
         patch("llm_helper.call_direct") as mock_direct, \
         patch("llm_helper._record_governance_outcome"):
        mock_harness.return_value = ("harness_text", {"gap": 15})
        mock_direct.return_value = "should_not_be_called"

        text, scores = call_llm_scored("task")

        assert "_fell_back" not in scores
        assert text == "harness_text"
        mock_direct.assert_not_called()
