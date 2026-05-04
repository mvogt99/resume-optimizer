"""Tests for analysis_worker.py — handle_chunk() and _get_extractor() logic.

Extractor functions are replaced via monkeypatch (pytest-native).
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import analysis_worker
from analysis_worker import _EXTRACTOR_KEYS, _extractors, handle_chunk


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def clear_extractor_cache():
    """Clear the lazy-loaded extractor cache before each test."""
    _extractors.clear()
    yield
    _extractors.clear()


def _mock_extractor(text, context_summary=""):
    """Fake extractor that returns a list based on input."""
    return [{"item": f"extracted from chunk: {text[:20]}"}]


def _failing_extractor(text, context_summary=""):
    """Extractor that raises an exception."""
    raise RuntimeError("Extractor crashed")


# ---------------------------------------------------------------------------
# handle_chunk tests
# ---------------------------------------------------------------------------
class TestHandleChunk:
    def test_basic_extraction(self, monkeypatch):
        monkeypatch.setattr(analysis_worker, "_get_extractor", lambda name: _mock_extractor)
        payload = {
            "doc_id": "doc-1",
            "chunk_idx": 0,
            "chunk_text": "Sample document text for analysis",
            "context": "Project context",
            "extractors": ["tech"],
        }
        result = handle_chunk(payload)
        assert result["doc_id"] == "doc-1"
        assert result["chunk_idx"] == 0
        assert len(result["technical"]) == 1

    def test_multiple_extractors(self, monkeypatch):
        monkeypatch.setattr(analysis_worker, "_get_extractor", lambda name: _mock_extractor)
        payload = {
            "doc_id": "doc-2",
            "chunk_idx": 1,
            "chunk_text": "More text",
            "extractors": ["tech", "gov", "role"],
        }
        result = handle_chunk(payload)
        assert len(result["technical"]) >= 1
        assert len(result["governance"]) >= 1
        assert len(result["role"]) >= 1

    def test_extractor_failure_returns_empty(self, monkeypatch):
        monkeypatch.setattr(analysis_worker, "_get_extractor", lambda name: _failing_extractor)
        payload = {
            "doc_id": "doc-3",
            "chunk_idx": 0,
            "chunk_text": "Text",
            "extractors": ["tech"],
        }
        result = handle_chunk(payload)
        # Failed extractor → empty list, not crash
        assert result["technical"] == []

    def test_unknown_extractor_skipped(self, monkeypatch):
        monkeypatch.setattr(analysis_worker, "_get_extractor", lambda name: None)
        payload = {
            "doc_id": "doc-4",
            "chunk_idx": 0,
            "chunk_text": "Text",
            "extractors": ["nonexistent"],
        }
        result = handle_chunk(payload)
        # Should not crash, just skip
        assert result["doc_id"] == "doc-4"

    def test_default_extractors(self, monkeypatch):
        monkeypatch.setattr(analysis_worker, "_get_extractor", lambda name: _mock_extractor)
        payload = {
            "doc_id": "doc-5",
            "chunk_idx": 0,
            "chunk_text": "Text",
            # No "extractors" key → defaults to ["tech", "gov", "role"]
        }
        result = handle_chunk(payload)
        assert len(result["technical"]) >= 1
        assert len(result["governance"]) >= 1
        assert len(result["role"]) >= 1

    def test_result_structure_has_all_keys(self, monkeypatch):
        monkeypatch.setattr(analysis_worker, "_get_extractor", lambda name: _mock_extractor)
        payload = {
            "doc_id": "doc-6",
            "chunk_idx": 2,
            "chunk_text": "Text",
            "extractors": ["tech"],
        }
        result = handle_chunk(payload)
        assert "doc_id" in result
        assert "chunk_idx" in result
        assert "technical" in result
        assert "governance" in result
        assert "role" in result
        assert "skills" in result
        assert "outcomes" in result

    def test_context_passed_to_extractor(self, monkeypatch):
        def capturing_extractor(text, context_summary=""):
            return [{"context_received": context_summary}]

        monkeypatch.setattr(analysis_worker, "_get_extractor", lambda name: capturing_extractor)
        payload = {
            "doc_id": "doc-7",
            "chunk_idx": 0,
            "chunk_text": "Text",
            "context": "Important project context",
            "extractors": ["tech"],
        }
        result = handle_chunk(payload)
        assert result["technical"][0]["context_received"] == "Important project context"

    def test_empty_text(self, monkeypatch):
        monkeypatch.setattr(analysis_worker, "_get_extractor", lambda name: _mock_extractor)
        payload = {
            "doc_id": "doc-8",
            "chunk_idx": 0,
            "chunk_text": "",
            "extractors": ["tech"],
        }
        result = handle_chunk(payload)
        assert result["doc_id"] == "doc-8"

    def test_mixed_success_and_failure(self, monkeypatch):
        """Some extractors succeed, one fails — partial results preserved."""
        call_count = [0]

        def alternating_extractor(text, context_summary=""):
            call_count[0] += 1
            if call_count[0] == 2:
                raise RuntimeError("Second extractor fails")
            return [{"ok": True}]

        monkeypatch.setattr(analysis_worker, "_get_extractor", lambda name: alternating_extractor)
        payload = {
            "doc_id": "doc-9",
            "chunk_idx": 0,
            "chunk_text": "Text",
            "extractors": ["tech", "gov", "role"],
        }
        result = handle_chunk(payload)
        # tech succeeds, gov fails, role succeeds
        assert len(result["technical"]) == 1
        assert result["governance"] == []
        assert len(result["role"]) == 1


# ---------------------------------------------------------------------------
# _EXTRACTOR_KEYS mapping tests
# ---------------------------------------------------------------------------
class TestExtractorKeys:
    def test_all_known_keys_mapped(self):
        expected = {"tech", "gov", "role", "skills", "outcomes"}
        assert set(_EXTRACTOR_KEYS.keys()) == expected

    def test_values_are_result_fields(self):
        expected_values = {"technical", "governance", "role", "skills", "outcomes"}
        assert set(_EXTRACTOR_KEYS.values()) == expected_values
