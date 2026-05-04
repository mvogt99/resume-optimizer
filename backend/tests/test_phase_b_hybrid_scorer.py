"""Pytest tests for hybrid_scorer.py — 7-dimension requirement scoring.

Main test suite covering:
  - _classify_match_type: all 5 types + threshold boundaries
  - score_requirement: schema, happy path, error handling, edge cases
  - score_all_requirements: sorting, empty inputs
  - build_alignment_summary: distribution, coverage %, weighted scoring, critical gaps
  - Dimension tests in test_phase_b_hybrid_scorer_dims.py
"""

import pytest
from unittest.mock import patch

from hybrid_scorer import (
    score_requirement,
    score_all_requirements,
    build_alignment_summary,
    _classify_match_type,
    DIMENSION_WEIGHTS,
)
from test_helpers import RESUME_TEXT
from test_phase_b_hybrid_scorer_fixtures import (
    sample_requirement,
    sample_requirement_domain,
    sample_requirement_leadership,
    sample_candidate_senior,
    sample_candidate_junior,
    sample_candidate_healthcare,
    empty_candidate,
)


# ---------------------------------------------------------------------------
# Tests: _classify_match_type (10 tests)
# ---------------------------------------------------------------------------


class TestClassifyMatchType:
    """Tests for match type classification thresholds."""

    def test_direct_at_threshold_80(self):
        """Score at 0.80 should classify as 'direct'."""
        assert _classify_match_type(0.80) == "direct"

    def test_direct_above_threshold(self):
        """Score > 0.80 should classify as 'direct'."""
        assert _classify_match_type(0.95) == "direct"

    def test_direct_plus_inferred_at_threshold_65(self):
        """Score at 0.65 should classify as 'direct_plus_inferred'."""
        assert _classify_match_type(0.65) == "direct_plus_inferred"

    def test_direct_plus_inferred_mid_range(self):
        """Score between 0.65-0.80 should classify as 'direct_plus_inferred'."""
        assert _classify_match_type(0.72) == "direct_plus_inferred"

    def test_partial_at_threshold_40(self):
        """Score at 0.40 should classify as 'partial'."""
        assert _classify_match_type(0.40) == "partial"

    def test_partial_mid_range(self):
        """Score between 0.40-0.65 should classify as 'partial'."""
        assert _classify_match_type(0.50) == "partial"

    def test_weak_at_threshold_20(self):
        """Score at 0.20 should classify as 'weak'."""
        assert _classify_match_type(0.20) == "weak"

    def test_weak_mid_range(self):
        """Score between 0.20-0.40 should classify as 'weak'."""
        assert _classify_match_type(0.30) == "weak"

    def test_none_below_threshold(self):
        """Score < 0.20 should classify as 'none'."""
        assert _classify_match_type(0.15) == "none"

    def test_none_at_zero(self):
        """Score at 0.0 should classify as 'none'."""
        assert _classify_match_type(0.0) == "none"


# ---------------------------------------------------------------------------
# Tests: score_requirement (13 tests)
# ---------------------------------------------------------------------------


class TestScoreRequirement:
    """Tests for score_requirement function."""

    def test_schema_happy_path(self, sample_requirement, sample_candidate_senior):
        """Returns dict with required schema keys."""
        result = score_requirement(sample_requirement, sample_candidate_senior, RESUME_TEXT)
        assert isinstance(result, dict)
        assert "requirement_id" in result
        assert "composite_score" in result
        assert "match_type" in result
        assert "dimension_scores" in result

    def test_requirement_id_preserved(self, sample_requirement, sample_candidate_senior):
        """requirement_id from input is preserved in output."""
        result = score_requirement(sample_requirement, sample_candidate_senior, RESUME_TEXT)
        assert result["requirement_id"] == "req_kafka_001"

    def test_composite_score_is_float_0_to_1(
        self, sample_requirement, sample_candidate_senior
    ):
        """composite_score is float between 0.0 and 1.0."""
        result = score_requirement(sample_requirement, sample_candidate_senior, RESUME_TEXT)
        assert isinstance(result["composite_score"], float)
        assert 0.0 <= result["composite_score"] <= 1.0

    def test_composite_score_respects_weights(
        self, sample_requirement, sample_candidate_senior
    ):
        """Composite score is weighted average of dimension scores."""
        result = score_requirement(sample_requirement, sample_candidate_senior, RESUME_TEXT)
        dimensions = result["dimension_scores"]
        expected = sum(
            dimensions[dim] * DIMENSION_WEIGHTS[dim] for dim in DIMENSION_WEIGHTS
        )
        assert abs(result["composite_score"] - expected) < 0.01

    def test_match_type_matches_threshold(
        self, sample_requirement, sample_candidate_senior
    ):
        """match_type matches composite_score threshold."""
        result = score_requirement(sample_requirement, sample_candidate_senior, RESUME_TEXT)
        composite = result["composite_score"]
        match_type = result["match_type"]

        if composite >= 0.80:
            assert match_type == "direct"
        elif composite >= 0.65:
            assert match_type == "direct_plus_inferred"
        elif composite >= 0.40:
            assert match_type == "partial"
        elif composite >= 0.20:
            assert match_type == "weak"
        else:
            assert match_type == "none"

    def test_dimension_scores_all_present(
        self, sample_requirement, sample_candidate_senior
    ):
        """dimension_scores contains all 7 dimensions."""
        result = score_requirement(sample_requirement, sample_candidate_senior, RESUME_TEXT)
        dims = result["dimension_scores"]
        for key in DIMENSION_WEIGHTS:
            assert key in dims

    def test_dimension_scores_are_floats_0_to_1(
        self, sample_requirement, sample_candidate_senior
    ):
        """Each dimension score is float between 0.0 and 1.0."""
        result = score_requirement(sample_requirement, sample_candidate_senior, RESUME_TEXT)
        for score in result["dimension_scores"].values():
            assert isinstance(score, float)
            assert 0.0 <= score <= 1.0

    def test_missing_resume_text(self, sample_requirement, sample_candidate_senior):
        """Handles missing resume_text gracefully."""
        result = score_requirement(sample_requirement, sample_candidate_senior, "")
        assert result["composite_score"] >= 0.0
        assert result["match_type"] in (
            "direct",
            "direct_plus_inferred",
            "partial",
            "weak",
            "none",
        )

    def test_zero_score_on_exception(self, sample_requirement):
        """Returns zero scores if exception occurs."""
        candidate_bad = None  # Will trigger exception
        result = score_requirement(sample_requirement, candidate_bad, RESUME_TEXT)
        assert result["composite_score"] == 0.0
        assert result["match_type"] == "none"
        assert all(v == 0.0 for v in result["dimension_scores"].values())

    def test_rounded_to_4_decimals(
        self, sample_requirement, sample_candidate_senior
    ):
        """Scores are rounded to 4 decimal places."""
        result = score_requirement(sample_requirement, sample_candidate_senior, RESUME_TEXT)
        # Check composite_score has max 4 decimals
        score_str = str(result["composite_score"])
        if "." in score_str:
            decimals = len(score_str.split(".")[-1])
            assert decimals <= 4

    def test_empty_requirement_id(self, sample_candidate_senior):
        """Missing requirement_id defaults to empty string."""
        req = {
            "requirement_type": "must_have",
            "text": "some requirement",
            "canonical_skills": [],
        }
        result = score_requirement(req, sample_candidate_senior, RESUME_TEXT)
        assert result["requirement_id"] == ""

    def test_leadership_requirement(
        self, sample_requirement_leadership, sample_candidate_senior
    ):
        """Leadership requirement scores non-zero for qualified candidate."""
        result = score_requirement(
            sample_requirement_leadership, sample_candidate_senior, RESUME_TEXT
        )
        assert result["composite_score"] > 0.0
        assert result["match_type"] in (
            "weak",
            "partial",
            "direct_plus_inferred",
            "direct",
        )

    def test_domain_requirement(
        self, sample_requirement_domain, sample_candidate_healthcare
    ):
        """Domain requirement scores high for domain-experienced candidate."""
        result = score_requirement(
            sample_requirement_domain, sample_candidate_healthcare, RESUME_TEXT
        )
        assert result["composite_score"] > 0.3


# ---------------------------------------------------------------------------
# Tests: score_all_requirements (5 tests)
# ---------------------------------------------------------------------------


class TestScoreAllRequirements:
    """Tests for score_all_requirements function."""

    def test_returns_list(self, sample_candidate_senior):
        """Returns a list."""
        reqs = [
            {
                "requirement_id": "req1",
                "text": "skill1",
                "canonical_skills": [],
                "requirement_type": "must_have",
            },
            {
                "requirement_id": "req2",
                "text": "skill2",
                "canonical_skills": [],
                "requirement_type": "must_have",
            },
        ]
        result = score_all_requirements(reqs, sample_candidate_senior, RESUME_TEXT)
        assert isinstance(result, list)

    def test_empty_requirements_list(self, sample_candidate_senior):
        """Empty requirements list returns empty list."""
        result = score_all_requirements([], sample_candidate_senior, RESUME_TEXT)
        assert result == []

    def test_sorted_by_composite_score_descending(self, sample_candidate_senior):
        """Results sorted by composite_score descending."""
        reqs = [
            {
                "requirement_id": "req1",
                "text": "Apache Kafka",
                "canonical_skills": ["Apache Kafka"],
                "requirement_type": "must_have",
            },
            {
                "requirement_id": "req2",
                "text": "Obscure skill nobody has",
                "canonical_skills": ["ObscureSkill9999"],
                "requirement_type": "must_have",
            },
        ]
        result = score_all_requirements(reqs, sample_candidate_senior, RESUME_TEXT)
        assert len(result) == 2
        # First should have higher or equal score
        assert result[0]["composite_score"] >= result[1]["composite_score"]

    def test_all_results_have_valid_schema(self, sample_candidate_senior):
        """All returned dicts have valid schema."""
        reqs = [
            {
                "requirement_id": f"req_{i}",
                "text": f"skill {i}",
                "canonical_skills": [],
                "requirement_type": "must_have",
            }
            for i in range(5)
        ]
        results = score_all_requirements(reqs, sample_candidate_senior, RESUME_TEXT)
        for result in results:
            assert "requirement_id" in result
            assert "composite_score" in result
            assert "match_type" in result
            assert "dimension_scores" in result

    def test_count_equals_input_count(self, sample_candidate_senior):
        """Output count equals input count."""
        reqs = [
            {
                "requirement_id": f"req_{i}",
                "text": f"skill {i}",
                "canonical_skills": [],
                "requirement_type": "must_have",
            }
            for i in range(10)
        ]
        results = score_all_requirements(reqs, sample_candidate_senior, RESUME_TEXT)
        assert len(results) == len(reqs)


# ---------------------------------------------------------------------------
# Tests: build_alignment_summary (7 tests)
# ---------------------------------------------------------------------------


class TestBuildAlignmentSummary:
    """Tests for build_alignment_summary function."""

    def test_empty_requirements_returns_zero_summary(self):
        """Empty requirements returns zero-valued summary."""
        result = build_alignment_summary([], [], [])
        assert result["overall_score"] == 0.0
        assert result["coverage_pct"] == 0.0
        assert result["critical_gaps"] == 0
        assert result["top_matches"] == []

    def test_schema_has_required_keys(self, sample_requirement, sample_candidate_senior):
        """Returns dict with required schema keys."""
        scores = score_all_requirements(
            [sample_requirement], sample_candidate_senior, RESUME_TEXT
        )
        result = build_alignment_summary([sample_requirement], scores, [])
        assert "overall_score" in result
        assert "match_distribution" in result
        assert "coverage_pct" in result
        assert "critical_gaps" in result
        assert "top_matches" in result

    def test_overall_score_weighted_by_importance(self):
        """overall_score weighted by requirement importance."""
        req1 = {
            "requirement_id": "req1",
            "text": "Python",
            "canonical_skills": ["Python"],
            "requirement_type": "must_have",
            "importance": 1.0,
        }
        req2 = {
            "requirement_id": "req2",
            "text": "Ruby",
            "canonical_skills": ["Ruby"],
            "requirement_type": "nice_to_have",
            "importance": 0.1,
        }
        scores = [
            {
                "requirement_id": "req1",
                "composite_score": 1.0,
                "match_type": "direct",
                "dimension_scores": {},
            },
            {
                "requirement_id": "req2",
                "composite_score": 0.0,
                "match_type": "none",
                "dimension_scores": {},
            },
        ]
        result = build_alignment_summary([req1, req2], scores, [])
        # Weighted: (1.0 * 1.0 + 0.0 * 0.1) / (1.0 + 0.1) ≈ 0.909
        assert result["overall_score"] > 0.8

    def test_match_distribution_counts(self, sample_requirement, sample_candidate_senior):
        """match_distribution counts match types."""
        scores = score_all_requirements(
            [sample_requirement] * 5, sample_candidate_senior, RESUME_TEXT
        )
        result = build_alignment_summary([sample_requirement] * 5, scores, [])
        dist = result["match_distribution"]
        assert sum(dist.values()) == 5
        assert all(
            k in dist for k in ("direct", "direct_plus_inferred", "partial", "weak", "none")
        )

    def test_critical_gaps_count(self, sample_requirement):
        """critical_gaps counts gaps with severity='high'."""
        gaps = [
            {"id": "gap1", "severity": "high"},
            {"id": "gap2", "severity": "high"},
            {"id": "gap3", "severity": "medium"},
        ]
        result = build_alignment_summary([sample_requirement], [], gaps)
        assert result["critical_gaps"] == 2

    def test_top_matches_limited_to_10(self, sample_candidate_senior):
        """top_matches includes only direct + direct_plus_inferred, max 10."""
        reqs = [
            {
                "requirement_id": f"req_{i}",
                "text": f"skill {i}",
                "canonical_skills": [],
                "requirement_type": "must_have",
                "importance": 0.5,
            }
            for i in range(15)
        ]
        scores = score_all_requirements(reqs, sample_candidate_senior, RESUME_TEXT)
        result = build_alignment_summary(reqs, scores, [])
        # Only direct + direct_plus_inferred included, max 10
        assert len(result["top_matches"]) <= 10
        for match in result["top_matches"]:
            assert match["match_type"] in ("direct", "direct_plus_inferred")


# ---------------------------------------------------------------------------
# Integration Tests (2 tests)
# ---------------------------------------------------------------------------


class TestIntegration:
    """Integration tests combining multiple functions."""

    def test_full_scoring_workflow(
        self, sample_requirement, sample_candidate_senior
    ):
        """Full workflow: score single → score all → build summary."""
        reqs = [sample_requirement]
        scores = score_all_requirements(reqs, sample_candidate_senior, RESUME_TEXT)
        summary = build_alignment_summary(reqs, scores, [])

        assert len(scores) == 1
        assert scores[0]["composite_score"] >= 0.0
        assert summary["overall_score"] >= 0.0
        assert summary["coverage_pct"] >= 0.0

    def test_dimension_weights_sum_to_one(self):
        """DIMENSION_WEIGHTS must sum to exactly 1.0 — catches any weight drift."""
        total = sum(DIMENSION_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9, f"Weights sum to {total}, expected 1.0"

    def test_dimension_weights_pinned_values(self):
        """Each weight must match the documented design — catches silent rebalancing."""
        assert DIMENSION_WEIGHTS["semantic_similarity"] == pytest.approx(0.35)
        assert DIMENSION_WEIGHTS["keyword_alignment"] == pytest.approx(0.20)
        assert DIMENSION_WEIGHTS["evidence_strength"] == pytest.approx(0.20)
        assert DIMENSION_WEIGHTS["seniority_alignment"] == pytest.approx(0.10)
        assert DIMENSION_WEIGHTS["domain_alignment"] == pytest.approx(0.05)
        assert DIMENSION_WEIGHTS["leadership_alignment"] == pytest.approx(0.05)
        assert DIMENSION_WEIGHTS["recency_alignment"] == pytest.approx(0.05)

    def test_semantic_weight_contributes_to_composite(self, sample_requirement, empty_candidate):
        """Semantic dimension at 1.0 with all others at 0.0 → composite ≈ 0.35.

        Pins the semantic_similarity weight independent of what DIMENSION_WEIGHTS says.
        This test WILL fail if the weight is changed to 0.
        """
        dim_return_values = {
            "semantic_similarity": 1.0,
            "keyword_alignment": 0.0,
            "evidence_strength": 0.0,
            "seniority_alignment": 0.0,
            "domain_alignment": 0.0,
            "leadership_alignment": 0.0,
            "recency_alignment": 0.0,
        }
        with (
            patch("hybrid_scorer._score_semantic_similarity", return_value=1.0),
            patch("hybrid_scorer._score_keyword_alignment", return_value=0.0),
            patch("hybrid_scorer._score_evidence_strength", return_value=0.0),
            patch("hybrid_scorer._score_seniority_alignment", return_value=0.0),
            patch("hybrid_scorer._score_domain_alignment", return_value=0.0),
            patch("hybrid_scorer._score_leadership_alignment", return_value=0.0),
            patch("hybrid_scorer._score_recency_alignment", return_value=0.0),
        ):
            result = score_requirement(sample_requirement, empty_candidate, "test text")
        assert result["composite_score"] == pytest.approx(0.35, abs=0.01), (
            "semantic_similarity at 1.0 with all others 0 should produce composite ≈ 0.35"
        )

    def test_keyword_weight_contributes_to_composite(self, sample_requirement, empty_candidate):
        """keyword_alignment at 1.0, all others 0 → composite ≈ 0.20."""
        with (
            patch("hybrid_scorer._score_semantic_similarity", return_value=0.0),
            patch("hybrid_scorer._score_keyword_alignment", return_value=1.0),
            patch("hybrid_scorer._score_evidence_strength", return_value=0.0),
            patch("hybrid_scorer._score_seniority_alignment", return_value=0.0),
            patch("hybrid_scorer._score_domain_alignment", return_value=0.0),
            patch("hybrid_scorer._score_leadership_alignment", return_value=0.0),
            patch("hybrid_scorer._score_recency_alignment", return_value=0.0),
        ):
            result = score_requirement(sample_requirement, empty_candidate, "test text")
        assert result["composite_score"] == pytest.approx(0.20, abs=0.01)

    def test_multiple_requirements_heterogeneous(self, sample_candidate_senior):
        """Scoring multiple requirement types together."""
        reqs = [
            {
                "requirement_id": "req_kafka",
                "requirement_type": "must_have",
                "text": "Apache Kafka experience",
                "canonical_skills": ["Apache Kafka"],
                "importance": 1.0,
            },
            {
                "requirement_id": "req_lead",
                "requirement_type": "leadership",
                "text": "Led teams of 5+ engineers",
                "canonical_skills": [],
                "importance": 0.7,
            },
        ]
        scores = score_all_requirements(reqs, sample_candidate_senior, RESUME_TEXT)
        assert len(scores) == 2
        # Both should be scored successfully
        assert all(s["composite_score"] >= 0.0 for s in scores)
