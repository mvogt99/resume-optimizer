"""Tests for POST /api/keywords/equivalency/match and keyword_matcher.suggest_semantic_matches.

Mutation targets:
  MM1: 401 when unauthenticated
  MM2: empty missing_keywords returns empty result without calling LLM
  MM3: exact matches are found before LLM is called (exact-match path)
  MM4: suggest_semantic_matches returns unmatched list when LLM fails
  MM5: not_applicable status is accepted by save_equivalencies endpoint (confidence=1.0)
  MM6: match endpoint calls suggest_semantic_matches for still-missing keywords
"""

from unittest.mock import patch

import pytest

_MATCH_URL = "/api/keywords/equivalency/match"

_STUB_MATCH_RESULT = {
    "exact_matches": [
        {"keyword": "Kafka", "equivalent_phrase": "event streaming", "confidence": 0.9, "status": "equivalent"}
    ],
    "suggestions": [
        {
            "keyword": "stateful processing",
            "saved_keyword": "integration streaming pipeline",
            "equivalent_phrase": "FIFO queues and extended transactions",
            "confidence": 0.75,
            "rationale": "Both describe stateful stream processing guarantees",
            "status": "equivalent",
        }
    ],
    "unmatched": ["ambiguous problem independently"],
}


class TestMatchEndpoint:
    # MM1: auth guard
    def test_unauthenticated_returns_401(self, client):
        """No auth → 401 (MM1)."""
        resp = client.post(_MATCH_URL, json={"missing_keywords": ["Kafka"]})
        assert resp.status_code == 401

    # MM2: empty keywords → empty result, no LLM call
    def test_empty_keywords_returns_empty(self, client, auth_headers):
        """Empty missing_keywords → 200 with empty lists, no LLM called (MM2)."""
        with patch("routes.keyword_routes.suggest_semantic_matches") as mock_sugg, \
             patch("routes.keyword_routes.get_equivalencies", return_value=[]):
            resp = client.post(_MATCH_URL, json={"missing_keywords": []}, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["exact_matches"] == []
        assert data["suggestions"] == []
        assert data["unmatched"] == []
        mock_sugg.assert_not_called()

    # MM3: exact match path — apply_persisted_equivalencies resolves keywords
    def test_exact_matches_resolved_before_llm(self, client, auth_headers):
        """Keywords in saved equivalencies are exact-matched before LLM runs (MM3)."""
        saved = [{"job_keyword": "Kafka", "equivalent_phrase": "event streaming", "confidence": 0.9, "status": "equivalent"}]
        with patch("routes.keyword_routes.get_equivalencies", return_value=saved), \
             patch("routes.keyword_routes.apply_persisted_equivalencies", return_value=([], [{"keyword": "Kafka", "equivalent": "event streaming", "confidence": 0.9}])) as mock_exact, \
             patch("routes.keyword_routes.suggest_semantic_matches", return_value={"suggestions": [], "unmatched": []}) as mock_sugg:
            resp = client.post(_MATCH_URL, json={"missing_keywords": ["Kafka"]}, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["exact_matches"]) == 1
        assert data["exact_matches"][0]["keyword"] == "Kafka"
        # LLM was called with empty still_missing
        mock_sugg.assert_called_once()

    # MM6: suggest_semantic_matches called for still-missing
    def test_suggest_called_for_unresolved(self, client, auth_headers):
        """Keywords not exact-matched are passed to suggest_semantic_matches (MM6)."""
        with patch("routes.keyword_routes.get_equivalencies", return_value=[]), \
             patch("routes.keyword_routes.apply_persisted_equivalencies", return_value=(["stateful processing"], [])), \
             patch("routes.keyword_routes.suggest_semantic_matches", return_value={"suggestions": _STUB_MATCH_RESULT["suggestions"], "unmatched": ["stateful processing"]}) as mock_sugg:
            resp = client.post(_MATCH_URL, json={"missing_keywords": ["stateful processing"]}, headers=auth_headers)
        assert resp.status_code == 200
        # Verify suggest was called with the still-missing keyword
        call_args = mock_sugg.call_args
        assert "stateful processing" in call_args[0][0]

    def test_response_has_all_three_keys(self, client, auth_headers):
        """Response always includes exact_matches, suggestions, unmatched."""
        with patch("routes.keyword_routes.get_equivalencies", return_value=[]), \
             patch("routes.keyword_routes.apply_persisted_equivalencies", return_value=(["x"], [])), \
             patch("routes.keyword_routes.suggest_semantic_matches", return_value={"suggestions": [], "unmatched": ["x"]}):
            resp = client.post(_MATCH_URL, json={"missing_keywords": ["x"]}, headers=auth_headers)
        data = resp.get_json()
        for key in ("exact_matches", "suggestions", "unmatched"):
            assert key in data


class TestSuggestSemanticMatches:
    """Unit tests for keyword_matcher.suggest_semantic_matches."""

    def test_returns_empty_when_no_keywords(self):
        """Empty missing_keywords → no suggestions, no unmatched (MM2 unit)."""
        from keyword_matcher import suggest_semantic_matches
        result = suggest_semantic_matches([], [{"job_keyword": "Kafka", "equivalent_phrase": "streaming"}])
        assert result == {"suggestions": [], "unmatched": []}

    def test_returns_empty_when_no_saved(self):
        """No saved equivalencies → all keywords go to unmatched."""
        from keyword_matcher import suggest_semantic_matches
        result = suggest_semantic_matches(["Kafka", "Kinesis"], [])
        assert result["suggestions"] == []
        assert set(result["unmatched"]) == {"Kafka", "Kinesis"}

    # MM4: LLM failure → all keywords returned as unmatched
    def test_llm_failure_returns_all_as_unmatched(self):
        """When LLM call raises, all missing keywords appear in unmatched (MM4)."""
        from keyword_matcher import suggest_semantic_matches
        # call_direct is imported locally inside the function — patch at source
        with patch("smart_llm.call_direct", side_effect=RuntimeError("LLM down")):
            result = suggest_semantic_matches(
                ["kw1", "kw2"],
                [{"job_keyword": "Kafka", "equivalent_phrase": "streaming", "confidence": 0.9, "status": "equivalent"}],
            )
        assert set(result["unmatched"]) == {"kw1", "kw2"}
        assert result["suggestions"] == []

    def test_llm_non_json_returns_all_as_unmatched(self):
        """Non-JSON LLM response → all keywords returned as unmatched."""
        from keyword_matcher import suggest_semantic_matches
        with patch("smart_llm.call_direct", return_value="I cannot help with that."):
            result = suggest_semantic_matches(
                ["kw1"],
                [{"job_keyword": "Kafka", "equivalent_phrase": "streaming", "confidence": 0.9, "status": "equivalent"}],
            )
        assert "kw1" in result["unmatched"]


class TestNotApplicableSave:
    # MM5: not_applicable status accepted
    def test_not_applicable_status_accepted(self, client, auth_headers):
        """status='not_applicable' with confidence=1.0 is saved without error (MM5)."""
        with patch("routes.keyword_routes.save_equivalencies", return_value=1):
            resp = client.post("/api/keywords/equivalencies", json={
                "resolved": [{"keyword": "employer-sponsored insurance", "equivalent": "not_applicable", "confidence": 1.0, "status": "not_applicable"}]
            }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["saved"] == 1
