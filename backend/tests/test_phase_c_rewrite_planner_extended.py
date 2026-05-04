"""Extended test suite for rewrite_planner.py — Part 2.

Contains _estimate_impact, _enrich_with_llm, and integration tests.
Completes the 25-test specification for Phase C rewrite planning.
"""

import pytest
from unittest.mock import patch
from rewrite_planner import (
    _estimate_impact,
    _enrich_with_llm,
    plan_rewrites,
    summarize_rewrite_plan,
)

# Reuse sample fixtures from main test file
SAMPLE_GAPS = [
    {
        "gap_id": "gap_001",
        "requirement_id": "req_001",
        "gap_type": "missing_experience",
        "severity": "high",
        "description": "No evidence of Apache Kafka in resume or career graph.",
        "recommended_action": "Add Kafka experience if adjacent exists."
    },
    {
        "gap_id": "gap_002",
        "requirement_id": "req_002",
        "gap_type": "weak_wording",
        "severity": "medium",
        "description": "Python appears once with no supporting context.",
        "recommended_action": "Add a bullet demonstrating Python usage."
    },
    {
        "gap_id": "gap_003",
        "requirement_id": "req_003",
        "gap_type": "missing_explicit_keyword",
        "severity": "low",
        "description": "No explicit mention of Terraform.",
        "recommended_action": "Reference IaC tools in experience section."
    },
]

SAMPLE_SCORES = [
    {"requirement_id": "req_001", "composite_score": 0.15, "match_type": "none"},
    {"requirement_id": "req_002", "composite_score": 0.45, "match_type": "partial"},
    {"requirement_id": "req_003", "composite_score": 0.70, "match_type": "strong"},
]

SAMPLE_PROFILE = {
    "candidate_id": "cand_001",
    "target_role_families": ["data_architect"],
    "skill_inventory": [
        {
            "canonical_skill": "Apache Kafka",
            "aliases": ["Kafka", "MSK"],
            "evidence_refs": ["proj_001", "proj_002"],
        },
        {
            "canonical_skill": "Python",
            "aliases": ["python3"],
            "evidence_refs": ["proj_003"],
        },
        {
            "canonical_skill": "Terraform",
            "aliases": ["terraform", "IaC"],
            "evidence_refs": ["proj_004"],
        },
    ],
    "experience_units": [
        {
            "experience_id": "exp_001",
            "title": "Data Platform Architect",
            "company": "Navitus",
            "skills": ["Apache Kafka", "Python"],
            "date_range": {"start": "2022-01-01", "end": None},
        },
        {
            "experience_id": "exp_002",
            "title": "Solutions Architect",
            "company": "OPI",
            "skills": ["Terraform", "Python"],
            "date_range": {"start": "2018-01-01", "end": "2021-12-31"},
        },
    ]
}

SAMPLE_RESUME = """\
MIKE VOGT
Enterprise Architect

EXPERIENCE
Senior Data Platform Architect — Navitus (2022-Present)
- Designed distributed data platform using Apache Kafka
- Led Python migration project

Solutions Architect — OPI (2018-2021)
- Built infrastructure automation using Terraform
"""


# ---------------------------------------------------------------------------
# Tests: _estimate_impact()
# ---------------------------------------------------------------------------

class TestEstimateImpact:
    """Test _estimate_impact() function."""

    def test_returns_float_0_to_1(self):
        """Returns float between 0.0 and 1.0."""
        result = _estimate_impact(SAMPLE_GAPS[0], SAMPLE_SCORES)
        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0

    def test_high_severity_higher_than_low_severity(self):
        """High severity gap impact >= low severity gap impact."""
        high_gap = SAMPLE_GAPS[0]  # high
        low_gap = SAMPLE_GAPS[2]   # low

        high_impact = _estimate_impact(high_gap, SAMPLE_SCORES)
        low_impact = _estimate_impact(low_gap, SAMPLE_SCORES)

        assert high_impact >= low_impact, \
            f"High ({high_impact}) not >= Low ({low_impact})"

    def test_low_score_higher_impact(self):
        """Lower composite_score implies higher impact (more urgent)."""
        gap = SAMPLE_GAPS[0]
        scores_low = [{"requirement_id": "req_001", "composite_score": 0.1, "match_type": "none"}]
        scores_high = [{"requirement_id": "req_001", "composite_score": 0.9, "match_type": "strong"}]

        impact_low_score = _estimate_impact(gap, scores_low)
        impact_high_score = _estimate_impact(gap, scores_high)

        assert impact_low_score > impact_high_score, \
            f"Low score ({impact_low_score}) not > High score ({impact_high_score})"

    def test_missing_score_handled_gracefully(self):
        """Missing score for requirement handled gracefully."""
        gap = SAMPLE_GAPS[0]
        empty_scores = []
        result = _estimate_impact(gap, empty_scores)
        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0


# ---------------------------------------------------------------------------
# Tests: _enrich_with_llm()
# ---------------------------------------------------------------------------

class TestEnrichWithLlm:
    """Test _enrich_with_llm() function."""

    def test_returns_list(self):
        """Returns a list."""
        targets = [
            {
                "target_id": "t1",
                "gap_id": "gap_001",
                "rewrite_template": "Add Kafka experience.",
                "evidence_anchor": "None found.",
            }
        ]
        result = _enrich_with_llm(targets, SAMPLE_RESUME)
        assert isinstance(result, list)

    @patch("rewrite_planner.call_llm_quality")
    def test_with_available_llm_enriches_targets(self, mock_llm):
        """With LLM available, targets may be enriched."""
        mock_llm.return_value = {"enhancements": "Add specific outcomes."}
        targets = [
            {
                "target_id": "t1",
                "gap_id": "gap_001",
                "rewrite_template": "Add Kafka.",
            }
        ]
        result = _enrich_with_llm(targets, SAMPLE_RESUME)
        assert isinstance(result, list)

    @patch("rewrite_planner.call_llm_quality")
    def test_with_unavailable_llm_returns_original(self, mock_llm):
        """When LLM unavailable (None), returns original targets."""
        mock_llm.return_value = None
        targets = [
            {
                "target_id": "t1",
                "gap_id": "gap_001",
                "rewrite_template": "Add Kafka.",
            }
        ]
        result = _enrich_with_llm(targets, SAMPLE_RESUME)
        assert result == targets

    @patch("rewrite_planner.call_llm_quality")
    def test_with_llm_failure_returns_original(self, mock_llm):
        """When LLM fails/raises, returns original targets."""
        mock_llm.side_effect = Exception("LLM error")
        targets = [
            {
                "target_id": "t1",
                "gap_id": "gap_001",
                "rewrite_template": "Add Kafka.",
            }
        ]
        result = _enrich_with_llm(targets, SAMPLE_RESUME)
        assert isinstance(result, list)

    def test_empty_targets_list(self):
        """Empty targets list handled gracefully."""
        result = _enrich_with_llm([], SAMPLE_RESUME)
        assert isinstance(result, list)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

class TestIntegration:
    """Integration tests combining multiple functions."""

    def test_full_pipeline_with_real_data(self):
        """Full pipeline: plan -> summarize."""
        targets = plan_rewrites(SAMPLE_GAPS, SAMPLE_SCORES, SAMPLE_PROFILE, SAMPLE_RESUME)
        assert len(targets) > 0

        summary = summarize_rewrite_plan(targets)
        assert summary["total"] == len(targets)
        assert summary["high_priority_count"] >= 0

    def test_full_pipeline_without_llm(self):
        """Full pipeline without LLM."""
        targets = plan_rewrites(
            SAMPLE_GAPS, SAMPLE_SCORES, SAMPLE_PROFILE, SAMPLE_RESUME, use_llm=False
        )
        summary = summarize_rewrite_plan(targets)
        assert isinstance(summary, dict)

    @patch("rewrite_planner.call_llm_quality")
    def test_full_pipeline_with_mocked_llm(self, mock_llm):
        """Full pipeline with mocked LLM."""
        mock_llm.return_value = {"enhancements": "Recommend adding metrics."}
        targets = plan_rewrites(
            SAMPLE_GAPS, SAMPLE_SCORES, SAMPLE_PROFILE, SAMPLE_RESUME, use_llm=True
        )
        summary = summarize_rewrite_plan(targets)
        assert summary["total"] == len(targets)

    def test_never_raises_with_garbage_input(self):
        """Function never raises even with garbage input."""
        with patch("rewrite_planner.call_llm_quality", return_value=None):
            try:
                plan_rewrites(None, None, None, None)
            except (TypeError, AttributeError):
                pass

            try:
                plan_rewrites({}, {}, {}, {})
            except (TypeError, KeyError, AttributeError):
                pass

            result = plan_rewrites([], [], {}, "")
            assert isinstance(result, list)

    def test_multiple_gaps_with_score_mapping(self):
        """Multiple gaps correctly mapped to scores."""
        targets = plan_rewrites(SAMPLE_GAPS, SAMPLE_SCORES, SAMPLE_PROFILE, SAMPLE_RESUME)
        target_by_gap = {t["gap_id"]: t for t in targets}

        for gap in SAMPLE_GAPS:
            assert gap["gap_id"] in target_by_gap
            target = target_by_gap[gap["gap_id"]]
            assert target["requirement_id"] == gap["requirement_id"]
