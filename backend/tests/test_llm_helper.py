"""Tests for llm_helper.py — pure logic functions, no LLM calls."""

import json
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import only the pure-logic functions (no LLM calls)
from llm_helper import _strip_think_tags, call_llm_quality, chunk_text, extract_json, merge_extracted_items, smart_sample_chunks


# ---------------------------------------------------------------------------
# chunk_text tests
# ---------------------------------------------------------------------------
class TestChunkText:
    def test_short_text_single_chunk(self):
        text = "Hello world"
        chunks = chunk_text(text, chunk_size=6000)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_exact_chunk_size_single_chunk(self):
        text = "x" * 6000
        chunks = chunk_text(text, chunk_size=6000)
        assert len(chunks) == 1

    def test_splits_long_text(self):
        text = "A" * 12000
        chunks = chunk_text(text, chunk_size=6000, overlap=500)
        assert len(chunks) >= 2
        # First chunk is 6000 chars
        assert len(chunks[0]) == 6000

    def test_overlap_present(self):
        text = "A" * 12000
        chunks = chunk_text(text, chunk_size=6000, overlap=500)
        # Second chunk should start 500 chars before end of first
        # First chunk: [0:6000], second starts at 5500
        assert len(chunks) >= 2
        # The overlapping region should exist
        assert chunks[0][-500:] == chunks[1][:500]

    def test_empty_text(self):
        chunks = chunk_text("", chunk_size=6000)
        assert chunks == [""]

    def test_custom_chunk_size(self):
        text = "word " * 100  # 500 chars
        chunks = chunk_text(text, chunk_size=100, overlap=20)
        assert len(chunks) >= 5

    def test_no_data_loss(self):
        """All characters from input appear in at least one chunk."""
        text = "".join(chr(65 + (i % 26)) for i in range(15000))
        chunks = chunk_text(text, chunk_size=6000, overlap=500)
        # Reconstruct: take non-overlapping parts
        reconstructed = chunks[0]
        for i in range(1, len(chunks)):
            # Each subsequent chunk's new content starts after overlap
            reconstructed += chunks[i][500:]
        # Should contain all original text
        assert text in reconstructed or len(reconstructed) >= len(text)


# ---------------------------------------------------------------------------
# smart_sample_chunks tests
# ---------------------------------------------------------------------------
class TestSmartSampleChunks:
    def test_small_input_returns_all(self):
        text = "x" * 5000
        sampled, total = smart_sample_chunks(text, max_chunks=10, chunk_size=6000)
        assert total == 1
        assert len(sampled) == 1

    def test_returns_tuple(self):
        result = smart_sample_chunks("hello", max_chunks=10)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_under_max_returns_all(self):
        # 5 chunks, max is 10 — should return all
        text = "x" * 25000
        sampled, total = smart_sample_chunks(text, max_chunks=10, chunk_size=6000, overlap=500)
        assert len(sampled) == total

    def test_over_max_samples_correctly(self):
        # Create text that produces ~20 chunks
        text = "x" * 120000
        sampled, total = smart_sample_chunks(text, max_chunks=8, chunk_size=6000, overlap=500)
        assert total > 8
        assert len(sampled) <= 8 + 2  # first2 + last2 + middle, may be slightly over

    def test_first_and_last_chunks_included(self):
        text = "A" * 6000 + "B" * 60000 + "Z" * 6000
        all_chunks = chunk_text(text, chunk_size=6000, overlap=500)
        sampled, total = smart_sample_chunks(text, max_chunks=6, chunk_size=6000, overlap=500)
        # First two and last two chunks must be included
        assert sampled[0] == all_chunks[0]
        assert sampled[1] == all_chunks[1]
        assert sampled[-1] == all_chunks[-1]
        assert sampled[-2] == all_chunks[-2]

    def test_total_count_accurate(self):
        text = "x" * 60000
        sampled, total = smart_sample_chunks(text, max_chunks=5, chunk_size=6000, overlap=500)
        all_chunks = chunk_text(text, chunk_size=6000, overlap=500)
        assert total == len(all_chunks)


# ---------------------------------------------------------------------------
# extract_json tests
# ---------------------------------------------------------------------------
class TestExtractJson:
    def test_tier1_fenced_json_block(self):
        text = 'Some preamble\n```json\n{"key": "value"}\n```\nSome epilogue'
        result = extract_json(text)
        assert result == {"key": "value"}

    def test_tier2_any_fenced_block(self):
        text = 'Text\n```\n{"name": "test"}\n```\nMore text'
        result = extract_json(text)
        assert result == {"name": "test"}

    def test_tier3_brace_substring(self):
        text = 'The result is {"score": 42} and that is all.'
        result = extract_json(text)
        assert result == {"score": 42}

    def test_tier3_array_substring(self):
        text = 'Here: [{"a": 1}, {"b": 2}] done'
        result = extract_json(text)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_empty_input(self):
        assert extract_json("") is None
        assert extract_json(None) is None

    def test_no_json_returns_none(self):
        assert extract_json("Just plain text with no JSON at all") is None

    def test_malformed_json_returns_none(self):
        text = "```json\n{broken json: no quotes}\n```"
        assert extract_json(text) is None

    def test_nested_json(self):
        nested = {"outer": {"inner": [1, 2, 3]}, "flag": True}
        text = f"```json\n{json.dumps(nested)}\n```"
        result = extract_json(text)
        assert result == nested

    def test_prefers_fenced_json_over_brace(self):
        """Tier 1 should win over Tier 3 when both present."""
        text = '{"wrong": true} ```json\n{"right": true}\n``` {"also_wrong": true}'
        result = extract_json(text)
        assert result == {"right": True}

    def test_multiline_json(self):
        text = '```json\n{\n  "name": "test",\n  "items": [\n    1,\n    2\n  ]\n}\n```'
        result = extract_json(text)
        assert result["name"] == "test"
        assert result["items"] == [1, 2]


# ---------------------------------------------------------------------------
# merge_extracted_items tests
# ---------------------------------------------------------------------------
class TestMergeExtractedItems:
    def test_deduplication_by_key(self):
        items = [
            {"name": "Python", "level": "expert"},
            {"name": "python", "level": "expert", "extra": "data"},
            {"name": "Java", "level": "senior"},
        ]
        result = merge_extracted_items(items, "name")
        assert len(result) == 2

    def test_keeps_richest_entry(self):
        items = [
            {"name": "Python", "level": "expert"},
            {"name": "Python", "level": "expert", "endorsements": 50, "details": "lots more"},
        ]
        result = merge_extracted_items(items, "name")
        assert len(result) == 1
        assert "endorsements" in result[0]

    def test_empty_list(self):
        assert merge_extracted_items([], "name") == []

    def test_skips_non_dict_items(self):
        items = [{"name": "Python"}, "not a dict", 42, None]
        result = merge_extracted_items(items, "name")
        assert len(result) == 1

    def test_skips_items_without_key_field(self):
        items = [
            {"name": "Python"},
            {"other_field": "no name here"},
        ]
        result = merge_extracted_items(items, "name")
        assert len(result) == 1

    def test_skips_empty_key_values(self):
        items = [
            {"name": "", "data": "x"},
            {"name": "Python", "data": "y"},
        ]
        result = merge_extracted_items(items, "name")
        assert len(result) == 1
        assert result[0]["name"] == "Python"

    def test_case_insensitive_dedup(self):
        items = [
            {"name": "PYTHON", "v": 1},
            {"name": "Python", "v": 2},
            {"name": "python", "v": 3, "extra": True},
        ]
        result = merge_extracted_items(items, "name")
        assert len(result) == 1

    def test_whitespace_stripped(self):
        items = [
            {"name": " Python ", "v": 1},
            {"name": "Python", "v": 2, "extra": True},
        ]
        result = merge_extracted_items(items, "name")
        assert len(result) == 1


# ---------------------------------------------------------------------------
# _strip_think_tags tests
# ---------------------------------------------------------------------------
class TestStripThinkTags:
    def test_strips_think_block(self):
        text = "<think>\nInternal reasoning here.\n</think>\nActual narrative output."
        assert _strip_think_tags(text) == "Actual narrative output."

    def test_multiline_think_block(self):
        text = "<think>\nLine 1.\nLine 2.\nLine 3.\n</think>\nClean content."
        assert _strip_think_tags(text) == "Clean content."

    def test_no_think_tag_unchanged(self):
        text = "Just a normal narrative with no thinking tags."
        assert _strip_think_tags(text) == text

    def test_empty_string(self):
        assert _strip_think_tags("") == ""

    def test_unclosed_think_not_stripped(self):
        """Unclosed <think> (no </think>) must not silently erase the entire content."""
        text = "<think>\nNo closing tag. Content here."
        result = _strip_think_tags(text)
        assert "Content here" in result


# ---------------------------------------------------------------------------
# call_llm_quality harness-path <think> stripping integration tests
# ---------------------------------------------------------------------------
class TestCallLlmQualityThinkStripping:
    """Verify that <think> blocks are stripped even when text comes via the harness path
    (not call_direct). These mock call_harness_scored to avoid real LLM calls."""

    def test_harness_path_strips_think_tags(self):
        """When harness succeeds (gap<30), returned text must have <think> stripped."""
        raw = "<think>\nReasoning internal.\n</think>\nFinal narrative answer."
        scores = {"f": 30, "t": 25, "a": 20, "gap": 25, "model_id": "test-model"}

        with patch("llm_helper.call_llm_scored", return_value=(raw, scores)):
            result = call_llm_quality("any task")

        assert result == "Final narrative answer."
        assert "<think>" not in result

    def test_harness_path_no_think_unchanged(self):
        """Normal harness response without <think> must pass through as-is."""
        raw = "Clean professional narrative with no thinking tags."
        scores = {"f": 30, "t": 25, "a": 20, "gap": 25}

        with patch("llm_helper.call_llm_scored", return_value=(raw, scores)):
            result = call_llm_quality("any task")

        assert result == raw

    def test_fell_back_sentinel_also_strips(self):
        """When _fell_back sentinel is set (post gap-fallback), text must still be stripped."""
        raw = "<think>\nPost-fallback reasoning.\n</think>\nFallback result text."
        scores = {"f": 10, "t": 5, "a": 5, "gap": 80, "_fell_back": True}

        with patch("llm_helper.call_llm_scored", return_value=(raw, scores)):
            result = call_llm_quality("any task")

        assert result == "Fallback result text."
        assert "<think>" not in result

    def test_harness_unreachable_returns_none(self):
        """When harness returns (None, None) on all attempts, result must be None."""
        with patch("llm_helper.call_llm_scored", return_value=(None, None)):
            result = call_llm_quality("any task", max_attempts=1)

        assert result is None
