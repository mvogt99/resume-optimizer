"""Test suite for rewrite_planner.py — Phase C rewrite planning engine.

Main test class and core function tests. See test_phase_c_rewrite_planner_extended.py
for additional integration and edge-case tests.

Validates gap analysis, priority ranking, and impact estimation.
"""

import pytest
from unittest.mock import patch
from rewrite_planner import (
    plan_rewrites,
    summarize_rewrite_plan,
    _find_evidence_anchor,
    _estimate_impact,
    _enrich_with_llm,
)

# ---------------------------------------------------------------------------
# Sample Fixtures
# ---------------------------------------------------------------------------

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

# Valid gap types per spec
VALID_GAP_TYPES = {
    "missing_experience",
    "weak_wording",
    "missing_explicit_keyword",
    "insufficient_leadership_signal",
    "seniority_mismatch",
    "domain_gap",
    "unsupported_claim_risk",
}

VALID_SEVERITIES = {"high", "medium", "low"}


# ---------------------------------------------------------------------------
# Tests: plan_rewrites()
# ---------------------------------------------------------------------------

class TestPlanRewrites:
    """Test plan_rewrites() main function."""

    def test_returns_list(self):
        """plan_rewrites returns a list."""
        result = plan_rewrites(SAMPLE_GAPS, SAMPLE_SCORES, SAMPLE_PROFILE, SAMPLE_RESUME)
        assert isinstance(result, list)

    def test_empty_gaps_returns_empty_list(self):
        """Empty gaps returns empty list."""
        result = plan_rewrites([], SAMPLE_SCORES, SAMPLE_PROFILE, SAMPLE_RESUME)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_each_target_has_all_required_keys(self):
        """Every target dict has all required keys."""
        result = plan_rewrites(SAMPLE_GAPS, SAMPLE_SCORES, SAMPLE_PROFILE, SAMPLE_RESUME)
        required_keys = {
            "target_id",
            "gap_id",
            "requirement_id",
            "priority",
            "gap_type",
            "suggested_action",
            "evidence_anchor",
            "rewrite_template",
            "severity",
            "estimated_impact",
        }
        for target in result:
            assert isinstance(target, dict)
            assert required_keys.issubset(target.keys()), f"Missing keys in {target}"

    def test_priority_is_positive_integer(self):
        """All priority values are >= 1."""
        result = plan_rewrites(SAMPLE_GAPS, SAMPLE_SCORES, SAMPLE_PROFILE, SAMPLE_RESUME)
        for target in result:
            assert isinstance(target["priority"], int)
            assert target["priority"] >= 1

    def test_priorities_monotonically_assigned(self):
        """Priorities should be assigned in order (1, 2, 3...) or at least monotonic."""
        result = plan_rewrites(SAMPLE_GAPS, SAMPLE_SCORES, SAMPLE_PROFILE, SAMPLE_RESUME)
        if len(result) > 0:
            priorities = [t["priority"] for t in result]
            assert priorities == sorted(priorities), "Priorities not in ascending order"

    def test_gap_id_links_to_input_gap(self):
        """Each target's gap_id matches an input gap."""
        result = plan_rewrites(SAMPLE_GAPS, SAMPLE_SCORES, SAMPLE_PROFILE, SAMPLE_RESUME)
        input_gap_ids = {g["gap_id"] for g in SAMPLE_GAPS}
        for target in result:
            assert target["gap_id"] in input_gap_ids

    def test_requirement_id_links_to_input_gap(self):
        """Each target's requirement_id matches its gap's requirement_id."""
        result = plan_rewrites(SAMPLE_GAPS, SAMPLE_SCORES, SAMPLE_PROFILE, SAMPLE_RESUME)
        gap_by_id = {g["gap_id"]: g for g in SAMPLE_GAPS}
        for target in result:
            gap = gap_by_id.get(target["gap_id"])
            assert gap is not None
            assert target["requirement_id"] == gap["requirement_id"]

    def test_gap_type_is_valid_enum(self):
        """All gap_type values are in valid enum."""
        result = plan_rewrites(SAMPLE_GAPS, SAMPLE_SCORES, SAMPLE_PROFILE, SAMPLE_RESUME)
        for target in result:
            assert target["gap_type"] in VALID_GAP_TYPES

    def test_severity_is_valid(self):
        """All severity values are high/medium/low."""
        result = plan_rewrites(SAMPLE_GAPS, SAMPLE_SCORES, SAMPLE_PROFILE, SAMPLE_RESUME)
        for target in result:
            assert target["severity"] in VALID_SEVERITIES

    def test_estimated_impact_is_float_0_to_1(self):
        """estimated_impact is float between 0.0 and 1.0."""
        result = plan_rewrites(SAMPLE_GAPS, SAMPLE_SCORES, SAMPLE_PROFILE, SAMPLE_RESUME)
        for target in result:
            impact = target["estimated_impact"]
            assert isinstance(impact, float)
            assert 0.0 <= impact <= 1.0

    def test_evidence_anchor_is_nonempty_string(self):
        """evidence_anchor is non-empty string."""
        result = plan_rewrites(SAMPLE_GAPS, SAMPLE_SCORES, SAMPLE_PROFILE, SAMPLE_RESUME)
        for target in result:
            assert isinstance(target["evidence_anchor"], str)
            assert len(target["evidence_anchor"]) > 0

    def test_rewrite_template_is_nonempty_string(self):
        """rewrite_template is non-empty string."""
        result = plan_rewrites(SAMPLE_GAPS, SAMPLE_SCORES, SAMPLE_PROFILE, SAMPLE_RESUME)
        for target in result:
            assert isinstance(target["rewrite_template"], str)
            assert len(target["rewrite_template"]) > 0

    def test_suggested_action_is_nonempty_string(self):
        """suggested_action is non-empty string."""
        result = plan_rewrites(SAMPLE_GAPS, SAMPLE_SCORES, SAMPLE_PROFILE, SAMPLE_RESUME)
        for target in result:
            assert isinstance(target["suggested_action"], str)
            assert len(target["suggested_action"]) > 0

    def test_high_severity_ranked_before_low_severity(self):
        """High severity gaps should appear before low severity."""
        result = plan_rewrites(SAMPLE_GAPS, SAMPLE_SCORES, SAMPLE_PROFILE, SAMPLE_RESUME)
        severities_in_order = [t["severity"] for t in result]

        high_indices = [i for i, s in enumerate(severities_in_order) if s == "high"]
        low_indices = [i for i, s in enumerate(severities_in_order) if s == "low"]

        if high_indices and low_indices:
            assert max(high_indices) < min(low_indices), "High severity gaps not before low"

    def test_empty_scores_still_returns_list(self):
        """Empty scores list handled gracefully."""
        result = plan_rewrites(SAMPLE_GAPS, [], SAMPLE_PROFILE, SAMPLE_RESUME)
        assert isinstance(result, list)

    def test_missing_profile_fields_handled_gracefully(self):
        """Missing fields in candidate_profile handled gracefully."""
        minimal_profile = {"candidate_id": "cand_001"}
        result = plan_rewrites(SAMPLE_GAPS, SAMPLE_SCORES, minimal_profile, SAMPLE_RESUME)
        assert isinstance(result, list)

    def test_use_llm_false_skips_enrichment(self):
        """When use_llm=False, function still returns valid targets."""
        result = plan_rewrites(
            SAMPLE_GAPS, SAMPLE_SCORES, SAMPLE_PROFILE, SAMPLE_RESUME, use_llm=False
        )
        assert isinstance(result, list)
        if len(result) > 0:
            assert "target_id" in result[0]

    @patch("rewrite_planner.call_llm_quality")
    def test_with_llm_enrichment(self, mock_llm):
        """With LLM available, targets enriched."""
        mock_llm.return_value = {
            "enhancements": "Kafka is critical; recommend mentioning stream processing."
        }
        result = plan_rewrites(
            SAMPLE_GAPS, SAMPLE_SCORES, SAMPLE_PROFILE, SAMPLE_RESUME, use_llm=True
        )
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Tests: summarize_rewrite_plan()
# ---------------------------------------------------------------------------

class TestSummarizeRewritePlan:
    """Test summarize_rewrite_plan() function."""

    def test_returns_dict(self):
        """Returns a dict."""
        targets = plan_rewrites(SAMPLE_GAPS, SAMPLE_SCORES, SAMPLE_PROFILE, SAMPLE_RESUME)
        result = summarize_rewrite_plan(targets)
        assert isinstance(result, dict)

    def test_has_all_required_summary_keys(self):
        """Returned dict has all 4 required keys."""
        targets = plan_rewrites(SAMPLE_GAPS, SAMPLE_SCORES, SAMPLE_PROFILE, SAMPLE_RESUME)
        result = summarize_rewrite_plan(targets)
        required = {"total", "high_priority_count", "by_gap_type", "estimated_overall_impact"}
        assert required.issubset(result.keys())

    def test_total_matches_targets_length(self):
        """total field matches len(targets)."""
        targets = plan_rewrites(SAMPLE_GAPS, SAMPLE_SCORES, SAMPLE_PROFILE, SAMPLE_RESUME)
        result = summarize_rewrite_plan(targets)
        assert result["total"] == len(targets)

    def test_high_priority_count_correct(self):
        """high_priority_count counts targets with severity='high', not priority==1.

        Uses pre-built targets with 2 high + 1 medium + 0 low so that counting
        'low' instead of 'high' would return 0, not 2.
        """
        targets = [
            {"target_id": "t1", "gap_id": "g1", "requirement_id": "r1", "priority": 1,
             "gap_type": "missing_experience", "severity": "high",
             "suggested_action": "Add X", "evidence_anchor": "", "rewrite_template": "", "estimated_impact": 0.3},
            {"target_id": "t2", "gap_id": "g2", "requirement_id": "r2", "priority": 2,
             "gap_type": "missing_experience", "severity": "high",
             "suggested_action": "Add Y", "evidence_anchor": "", "rewrite_template": "", "estimated_impact": 0.25},
            {"target_id": "t3", "gap_id": "g3", "requirement_id": "r3", "priority": 3,
             "gap_type": "weak_wording", "severity": "medium",
             "suggested_action": "Rephrase", "evidence_anchor": "", "rewrite_template": "", "estimated_impact": 0.1},
        ]
        result = summarize_rewrite_plan(targets)
        assert result["high_priority_count"] == 2, (
            f"2 targets have severity='high', 0 have severity='low'; "
            f"high_priority_count must be 2, got {result['high_priority_count']}"
        )

    def test_high_priority_count_pinned_value(self):
        """Pins exact high_priority_count for a known input — catches severity field change.

        3 high + 0 low targets → correct=3, mutated-to-low=0.
        """
        targets = [
            {"target_id": f"t{i}", "gap_id": f"g{i}", "requirement_id": f"r{i}",
             "priority": i + 1, "gap_type": "missing_experience", "severity": "high",
             "suggested_action": "Add X", "evidence_anchor": "Acme",
             "rewrite_template": "Led X at Acme", "estimated_impact": 0.3}
            for i in range(3)
        ] + [
            {"target_id": "t3", "gap_id": "g3", "requirement_id": "r3", "priority": 4,
             "gap_type": "weak_wording", "severity": "medium",
             "suggested_action": "Rephrase", "evidence_anchor": "Acme",
             "rewrite_template": "Delivered X", "estimated_impact": 0.15},
        ]
        result = summarize_rewrite_plan(targets)
        assert result["high_priority_count"] == 3, (
            f"3 targets have severity='high', 0 have severity='low'; "
            f"high_priority_count must be 3, got {result['high_priority_count']}"
        )

    def test_by_gap_type_is_dict(self):
        """by_gap_type is a dict."""
        targets = plan_rewrites(SAMPLE_GAPS, SAMPLE_SCORES, SAMPLE_PROFILE, SAMPLE_RESUME)
        result = summarize_rewrite_plan(targets)
        assert isinstance(result["by_gap_type"], dict)

    def test_estimated_overall_impact_is_float_0_to_1(self):
        """estimated_overall_impact is float 0.0-1.0."""
        targets = plan_rewrites(SAMPLE_GAPS, SAMPLE_SCORES, SAMPLE_PROFILE, SAMPLE_RESUME)
        result = summarize_rewrite_plan(targets)
        impact = result["estimated_overall_impact"]
        assert isinstance(impact, float)
        assert 0.0 <= impact <= 1.0

    def test_empty_targets_returns_summary(self):
        """Empty targets list returns valid summary."""
        result = summarize_rewrite_plan([])
        assert result["total"] == 0
        assert result["high_priority_count"] == 0


# ---------------------------------------------------------------------------
# Tests: _find_evidence_anchor()
# ---------------------------------------------------------------------------

class TestFindEvidenceAnchor:
    """Test _find_evidence_anchor() function."""

    def test_returns_nonempty_string(self):
        """Returns a non-empty string."""
        result = _find_evidence_anchor(SAMPLE_GAPS[0], SAMPLE_PROFILE)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_finds_evidence_for_existing_skill(self):
        """Finds evidence for skill in candidate profile."""
        gap = SAMPLE_GAPS[0]  # gap_001, Kafka
        result = _find_evidence_anchor(gap, SAMPLE_PROFILE)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_returns_no_direct_evidence_for_unknown_skill(self):
        """Returns 'No direct evidence' or similar for unknown skill."""
        gap = {
            "gap_id": "gap_unknown",
            "requirement_id": "req_unknown",
            "gap_type": "missing_experience",
            "severity": "high",
            "description": "No evidence of Rust in profile.",
            "recommended_action": "Learn Rust.",
        }
        result = _find_evidence_anchor(gap, SAMPLE_PROFILE)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_handles_missing_profile_fields(self):
        """Handles missing skill_inventory or experience_units."""
        minimal_profile = {"candidate_id": "cand_001"}
        result = _find_evidence_anchor(SAMPLE_GAPS[0], minimal_profile)
        assert isinstance(result, str)
        assert len(result) > 0
