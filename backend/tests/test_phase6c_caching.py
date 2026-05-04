"""Phase 6c: LRU cache for call_llm_quality_cached().

Tests verify: first call invokes underlying function, second identical call hits cache,
different args bypass cache, and cache management methods exist.
"""

from unittest.mock import patch

from llm_helper import call_llm_quality_cached


def test_cached_function_returns_result_on_first_call():
    """Verify: First call delegates to call_llm_quality and returns its result."""
    call_llm_quality_cached.cache_clear()
    with patch("llm_helper.call_llm_quality") as mock_call:
        mock_call.return_value = "result_text"

        result = call_llm_quality_cached("my_task")

        assert result == "result_text"
        assert mock_call.call_count == 1


def test_cached_function_returns_cached_result_on_second_identical_call():
    """Verify: Second call with same args hits cache — call_llm_quality called only once."""
    call_llm_quality_cached.cache_clear()
    with patch("llm_helper.call_llm_quality") as mock_call:
        mock_call.return_value = "cached_result"

        result1 = call_llm_quality_cached("same_task")
        result2 = call_llm_quality_cached("same_task")

        assert result1 == "cached_result"
        assert result2 == "cached_result"
        assert mock_call.call_count == 1  # Only called once despite two invocations


def test_cached_function_bypasses_cache_for_different_args():
    """Verify: Different task strings result in separate calls (cache miss per key)."""
    call_llm_quality_cached.cache_clear()
    with patch("llm_helper.call_llm_quality") as mock_call:
        mock_call.side_effect = ["result_a", "result_b"]

        result_a = call_llm_quality_cached("task_a")
        result_b = call_llm_quality_cached("task_b")

        assert result_a == "result_a"
        assert result_b == "result_b"
        assert mock_call.call_count == 2


def test_cached_function_has_cache_clear_method():
    """Verify: lru_cache decorator adds cache_clear and cache_info to the function."""
    assert hasattr(call_llm_quality_cached, "cache_clear")
    assert hasattr(call_llm_quality_cached, "cache_info")
    # Should not raise
    call_llm_quality_cached.cache_clear()
    info = call_llm_quality_cached.cache_info()
    assert info.maxsize == 128
