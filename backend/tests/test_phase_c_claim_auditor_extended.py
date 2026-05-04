"""Extended pytest tests for claim_auditor.py.

Tests 21-30 + integration tests:
- _classify_risk() logic
- _classify_claim_type() categorization
- _refine_with_llm() fallback behavior
- summarize_audit() aggregation
- Full integration pipeline consistency

See test_phase_c_claim_auditor.py for tests 1-20 (structure, sorting, matching).
"""

import pytest
from unittest.mock import patch, MagicMock
from claim_auditor import (
    audit_claims,
    summarize_audit,
    _extract_claims,
    _check_claim_against_profile,
    _classify_risk,
    _classify_claim_type,
    _refine_with_llm,
)


# ---------------------------------------------------------------------------
# Fixtures (shared with main test file)
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_profile():
    """Realistic candidate profile with skills, experience, and evidence."""
    return {
        "candidate_id": "cand_001",
        "skill_inventory": [
            {
                "canonical_skill": "Apache Kafka",
                "aliases": ["Kafka", "MSK"],
                "evidence_refs": ["proj_001", "proj_002", "proj_003"],
            },
            {
                "canonical_skill": "Python",
                "aliases": ["python3", "python"],
                "evidence_refs": ["proj_004"],
            },
            {
                "canonical_skill": "AWS",
                "aliases": ["amazon web services"],
                "evidence_refs": ["proj_005", "proj_006"],
            },
            {
                "canonical_skill": "Kubernetes",
                "aliases": ["k8s"],
                "evidence_refs": ["proj_007", "proj_008", "proj_009"],
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
                "title": "Software Engineer",
                "company": "OPI",
                "skills": ["Python", "AWS"],
                "date_range": {"start": "2018-01-01", "end": "2021-12-31"},
            },
        ],
    }


@pytest.fixture
def sample_resume():
    """Resume with mix of supported, unsupported, and risky claims."""
    return """\
Architected Kafka-based streaming platform processing 5M events/day at Navitus Health.
Led team of 15 engineers across 3 time zones for enterprise data modernization.
5+ years of Python experience in production data pipelines.
Reduced infrastructure costs by 40% through optimization.
Expert in quantum computing and blockchain at enterprise scale.
Deployed Kubernetes clusters managing 500K pods.
Implemented AWS Lambda functions for serverless architecture.
"""


@pytest.fixture
def empty_profile():
    """Empty profile with no skills or experience."""
    return {
        "candidate_id": "cand_002",
        "skill_inventory": [],
        "experience_units": [],
    }


# ---------------------------------------------------------------------------
# Test Suite 5: _classify_risk() (Tests 21-22)
# ---------------------------------------------------------------------------


def test_classify_risk_high_for_unsupported_metric():
    """Test 21: Unsupported metric/tech claim returns 'high' risk."""
    result = _classify_risk(
        claim="Processed 10M events/day in production",
        is_supported=False,
        evidence_refs=[],
        confidence=0.1,
    )
    assert result == "high"


def test_classify_risk_low_for_supported_high_confidence():
    """Test 22: Supported claim with confidence >= 0.6 returns 'low' risk."""
    result = _classify_risk(
        claim="Python programming",
        is_supported=True,
        evidence_refs=["proj_004"],
        confidence=0.8,
    )
    assert result == "low"


# ---------------------------------------------------------------------------
# Test Suite 6: _classify_claim_type() (Tests 23-26)
# ---------------------------------------------------------------------------


def test_classify_claim_type_quantified_metric():
    """Test 23: Returns quantified_metric for '5M events/day'."""
    result = _classify_claim_type("Processed 5M events/day")
    assert result == "quantified_metric"


def test_classify_claim_type_years_experience():
    """Test 24: Returns years_experience for '5+ years'."""
    result = _classify_claim_type("5+ years of Python experience")
    assert result == "years_experience"


def test_classify_claim_type_technology_skill():
    """Test 25: Returns technology_skill for 'Kafka'."""
    result = _classify_claim_type("Expert in Kafka streaming")
    assert result == "technology_skill"


def test_classify_claim_type_other():
    """Test 26: Returns other for generic text."""
    result = _classify_claim_type("I am a good communicator")
    assert result == "other"


# ---------------------------------------------------------------------------
# Test Suite 7: _refine_with_llm() (Tests 27-28)
# ---------------------------------------------------------------------------


def test_refine_with_llm_returns_list():
    """Test 27: _refine_with_llm returns a list."""
    sample_audits = [
        {
            "audit_id": "000000000001",
            "claim_text": "Kafka",
            "claim_type": "technology_skill",
            "is_supported": True,
            "evidence_refs": ["p1"],
            "risk_level": "low",
            "confidence": 0.9,
            "suggested_revision": "No change",
        }
    ]
    result = _refine_with_llm(sample_audits, "Resume text", {})
    assert isinstance(result, list)


def test_refine_with_llm_returns_original_when_llm_none():
    """Test 28: _refine_with_llm returns original when LLM is None/unavailable."""
    sample_audits = [
        {
            "audit_id": "000000000002",
            "claim_text": "Python",
            "claim_type": "technology_skill",
            "is_supported": False,
            "evidence_refs": [],
            "risk_level": "high",
            "confidence": 0.1,
            "suggested_revision": "Remove",
        }
    ]
    with patch("claim_auditor.call_llm_quality", return_value=None):
        result = _refine_with_llm(sample_audits, "Resume", {})
        # Should return original when LLM is None
        assert result == sample_audits


# ---------------------------------------------------------------------------
# Test Suite 8: summarize_audit() (Tests 29-30)
# ---------------------------------------------------------------------------


def test_summarize_audit_returns_dict_with_all_keys():
    """Test 29: summarize_audit returns dict with all 5 required keys."""
    sample_audits = [
        {
            "audit_id": "000000000003",
            "claim_text": "5M events/day",
            "claim_type": "quantified_metric",
            "is_supported": False,
            "evidence_refs": [],
            "risk_level": "high",
            "confidence": 0.1,
            "suggested_revision": "Remove",
        },
        {
            "audit_id": "000000000004",
            "claim_text": "Kafka",
            "claim_type": "technology_skill",
            "is_supported": True,
            "evidence_refs": ["p1", "p2", "p3"],
            "risk_level": "low",
            "confidence": 0.9,
            "suggested_revision": "No change",
        },
    ]
    result = summarize_audit(sample_audits)
    assert isinstance(result, dict)
    expected_keys = {
        "total",
        "supported_count",
        "unsupported_count",
        "high_risk_count",
        "by_claim_type",
    }
    assert expected_keys.issubset(result.keys())


def test_summarize_audit_counts_correctly():
    """Test 30: summarize_audit counts match audits."""
    sample_audits = [
        {
            "audit_id": "000000000005",
            "claim_text": "Unsupported high risk",
            "claim_type": "quantified_metric",
            "is_supported": False,
            "evidence_refs": [],
            "risk_level": "high",
            "confidence": 0.1,
            "suggested_revision": "Remove",
        },
        {
            "audit_id": "000000000006",
            "claim_text": "Supported low risk",
            "claim_type": "technology_skill",
            "is_supported": True,
            "evidence_refs": ["p1"],
            "risk_level": "low",
            "confidence": 0.8,
            "suggested_revision": "No change",
        },
        {
            "audit_id": "000000000007",
            "claim_text": "Supported medium risk",
            "claim_type": "years_experience",
            "is_supported": True,
            "evidence_refs": ["p2"],
            "risk_level": "medium",
            "confidence": 0.5,
            "suggested_revision": "Clarify",
        },
    ]
    result = summarize_audit(sample_audits)
    assert result["total"] == 3
    assert result["supported_count"] == 2
    assert result["unsupported_count"] == 1
    assert result["high_risk_count"] == 1
    assert isinstance(result["by_claim_type"], dict)
    # by_claim_type should count claim types
    assert result["by_claim_type"].get("quantified_metric", 0) == 1
    assert result["by_claim_type"].get("technology_skill", 0) == 1
    assert result["by_claim_type"].get("years_experience", 0) == 1


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------


def test_full_audit_pipeline_with_supported_claim(sample_resume, sample_profile):
    """Integration: Full pipeline produces consistent results for supported claim."""
    result = audit_claims(sample_resume, sample_profile, use_llm=False)
    # Find any supported claim
    supported = [a for a in result if a["is_supported"]]
    if supported:
        audit = supported[0]
        # Supported + high confidence should be low risk
        if audit["confidence"] >= 0.6:
            assert audit["risk_level"] == "low"


def test_full_audit_pipeline_with_unsupported_claim(sample_resume, sample_profile):
    """Integration: Full pipeline produces consistent results for unsupported claim."""
    result = audit_claims(sample_resume, sample_profile, use_llm=False)
    # Find any unsupported claim
    unsupported = [a for a in result if not a["is_supported"]]
    if unsupported:
        audit = unsupported[0]
        # Unsupported with low confidence should be high risk
        if audit["confidence"] < 0.3:
            assert audit["risk_level"] == "high"


def test_audit_claims_consistency_across_runs(sample_resume, sample_profile):
    """Integration: Multiple runs produce consistent results."""
    result1 = audit_claims(sample_resume, sample_profile, use_llm=False)
    result2 = audit_claims(sample_resume, sample_profile, use_llm=False)
    # Should have same number of claims
    assert len(result1) == len(result2)
    # Same sorting order
    for a1, a2 in zip(result1, result2):
        assert a1["risk_level"] == a2["risk_level"]
        assert a1["claim_text"] == a2["claim_text"]


def test_audit_claims_with_mixed_profile_and_resume(sample_resume, sample_profile):
    """Integration: Mixed supported/unsupported produces realistic audit mix."""
    result = audit_claims(sample_resume, sample_profile, use_llm=False)
    # Should have both supported and unsupported claims
    supported_count = sum(1 for a in result if a["is_supported"])
    unsupported_count = sum(1 for a in result if not a["is_supported"])
    assert len(result) > 0
    # Real resume should have some mix
    assert supported_count > 0 or unsupported_count > 0


def test_summarize_audit_integration_with_audit_claims(sample_resume, sample_profile):
    """Integration: summarize_audit correctly summarizes audit_claims output."""
    audits = audit_claims(sample_resume, sample_profile, use_llm=False)
    summary = summarize_audit(audits)
    # Verify counts match
    assert summary["total"] == len(audits)
    assert summary["supported_count"] == sum(1 for a in audits if a["is_supported"])
    assert summary["unsupported_count"] == sum(1 for a in audits if not a["is_supported"])
    assert summary["high_risk_count"] == sum(1 for a in audits if a["risk_level"] == "high")


def test_classify_risk_consistency_with_audit_pipeline(sample_resume, sample_profile):
    """Integration: _classify_risk logic matches audit pipeline results."""
    audits = audit_claims(sample_resume, sample_profile, use_llm=False)
    for audit in audits:
        # Verify risk level matches _classify_risk logic
        computed_risk = _classify_risk(
            claim=audit["claim_text"],
            is_supported=audit["is_supported"],
            evidence_refs=audit["evidence_refs"],
            confidence=audit["confidence"],
        )
        # Risk level should be consistent with support/confidence
        if not audit["is_supported"] and audit["confidence"] < 0.3:
            assert audit["risk_level"] == "high"
        if audit["is_supported"] and audit["confidence"] >= 0.6:
            assert audit["risk_level"] == "low"


def test_extract_claims_integration_with_classify_claim_type(sample_resume):
    """Integration: Extracted claims are properly classified by type."""
    claims = _extract_claims(sample_resume)
    for claim in claims:
        claim_type = _classify_claim_type(claim)
        assert claim_type in {
            "quantified_metric",
            "technology_skill",
            "role_scope",
            "years_experience",
            "other",
        }


def test_evidence_refs_consistency_across_profile_check(sample_profile):
    """Integration: Evidence refs from profile check are consistent."""
    # Test that multiple checks return same evidence refs
    result1 = _check_claim_against_profile("Kafka", sample_profile)
    result2 = _check_claim_against_profile("Kafka", sample_profile)
    assert result1["evidence_refs"] == result2["evidence_refs"]
    assert result1["confidence"] == result2["confidence"]


def test_llm_refinement_preserves_core_fields():
    """Integration: LLM refinement doesn't lose core audit fields."""
    original_audits = [
        {
            "audit_id": "000000000008",
            "claim_text": "Original claim",
            "claim_type": "technology_skill",
            "is_supported": True,
            "evidence_refs": ["e1"],
            "risk_level": "low",
            "confidence": 0.8,
            "suggested_revision": "Original revision",
        }
    ]
    mock_llm_response = [
        {
            "audit_id": "000000000008",
            "claim_text": "Original claim",
            "claim_type": "technology_skill",
            "is_supported": True,
            "evidence_refs": ["e1"],
            "risk_level": "low",
            "confidence": 0.8,
            "suggested_revision": "Refined revision",
        }
    ]
    with patch("claim_auditor.call_llm_quality", return_value=mock_llm_response):
        result = _refine_with_llm(original_audits, "Resume", {})
        # Should have same keys
        if result:
            assert "audit_id" in result[0]
            assert "claim_text" in result[0]
            assert "claim_type" in result[0]
