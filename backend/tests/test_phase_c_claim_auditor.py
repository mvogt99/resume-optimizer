"""Pytest tests for claim_auditor.py — claim verification and risk assessment.

Phase C: Claim Auditor
- audit_claims() main entry point with LLM refinement
- _extract_claims() resume text parsing
- _check_claim_against_profile() profile matching
- _classify_risk() risk categorization
- _classify_claim_type() claim type classification
- _refine_with_llm() LLM-based refinement
- summarize_audit() audit result aggregation

Tests 1-20: Structure validation, sorting, and profile matching.
Tests 21-30: Risk/type classification and aggregation (see test_phase_c_claim_auditor_extended.py).
"""

import re
import pytest
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
# Fixtures
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
# Test Suite 1: audit_claims() — Structure + Sorting (Tests 1-10)
# ---------------------------------------------------------------------------


def test_audit_claims_returns_list(sample_resume, sample_profile):
    """Test 1: audit_claims returns a list."""
    result = audit_claims(sample_resume, sample_profile, use_llm=False)
    assert isinstance(result, list)
    assert len(result) > 0


def test_audit_claims_each_has_all_required_keys(sample_resume, sample_profile):
    """Test 2: Each audit dict has all 8 required keys."""
    result = audit_claims(sample_resume, sample_profile, use_llm=False)
    required_keys = {
        "audit_id",
        "claim_text",
        "claim_type",
        "is_supported",
        "evidence_refs",
        "risk_level",
        "confidence",
        "suggested_revision",
    }
    for audit in result:
        assert isinstance(audit, dict), f"Expected dict, got {type(audit)}"
        assert required_keys.issubset(
            audit.keys()
        ), f"Missing keys in audit: {audit.keys()}"


def test_audit_claims_audit_id_is_12_char_hex(sample_resume, sample_profile):
    """Test 3: audit_id is 12-char hex string."""
    result = audit_claims(sample_resume, sample_profile, use_llm=False)
    for audit in result:
        audit_id = audit["audit_id"]
        assert isinstance(audit_id, str)
        assert len(audit_id) == 12, f"Expected 12 chars, got {len(audit_id)}"
        assert re.match(r"^[0-9a-f]{12}$", audit_id), f"Not hex: {audit_id}"


def test_audit_claims_claim_type_is_valid_enum(sample_resume, sample_profile):
    """Test 4: claim_type is one of the valid enum values."""
    result = audit_claims(sample_resume, sample_profile, use_llm=False)
    valid_types = {
        "quantified_metric",
        "technology_skill",
        "role_scope",
        "years_experience",
        "other",
    }
    for audit in result:
        assert audit["claim_type"] in valid_types, f"Invalid type: {audit['claim_type']}"


def test_audit_claims_risk_level_is_valid(sample_resume, sample_profile):
    """Test 5: risk_level is one of high/medium/low."""
    result = audit_claims(sample_resume, sample_profile, use_llm=False)
    for audit in result:
        assert audit["risk_level"] in ("high", "medium", "low")


def test_audit_claims_confidence_is_float_0_to_1(sample_resume, sample_profile):
    """Test 6: confidence is a float between 0.0 and 1.0."""
    result = audit_claims(sample_resume, sample_profile, use_llm=False)
    for audit in result:
        conf = audit["confidence"]
        assert isinstance(conf, (int, float)), f"Not numeric: {type(conf)}"
        assert 0.0 <= conf <= 1.0, f"Out of range: {conf}"


def test_audit_claims_is_supported_is_bool(sample_resume, sample_profile):
    """Test 7: is_supported is a boolean."""
    result = audit_claims(sample_resume, sample_profile, use_llm=False)
    for audit in result:
        assert isinstance(audit["is_supported"], bool)


def test_audit_claims_evidence_refs_is_list(sample_resume, sample_profile):
    """Test 8: evidence_refs is a list."""
    result = audit_claims(sample_resume, sample_profile, use_llm=False)
    for audit in result:
        assert isinstance(audit["evidence_refs"], list)


def test_audit_claims_suggested_revision_is_str(sample_resume, sample_profile):
    """Test 9: suggested_revision is a non-empty string."""
    result = audit_claims(sample_resume, sample_profile, use_llm=False)
    for audit in result:
        assert isinstance(audit["suggested_revision"], str)
        assert len(audit["suggested_revision"]) > 0


def test_audit_claims_sorted_high_risk_first(sample_resume, sample_profile):
    """Test 10: Results are sorted with high-risk claims first."""
    result = audit_claims(sample_resume, sample_profile, use_llm=False)
    risk_levels = [audit["risk_level"] for audit in result]
    risk_order = {"high": 0, "medium": 1, "low": 2}
    risk_indices = [risk_order[level] for level in risk_levels]
    assert risk_indices == sorted(risk_indices), (
        f"Not sorted by risk: {risk_levels}"
    )


# ---------------------------------------------------------------------------
# Test Suite 2: Empty & Garbage Input (Tests 11-13)
# ---------------------------------------------------------------------------


def test_audit_claims_empty_resume_returns_empty_list(sample_profile):
    """Test 11: Empty resume returns empty list."""
    result = audit_claims("", sample_profile, use_llm=False)
    assert isinstance(result, list)
    assert len(result) == 0


def test_audit_claims_empty_profile_returns_list(sample_resume, empty_profile):
    """Test 12: Empty profile is handled gracefully."""
    result = audit_claims(sample_resume, empty_profile, use_llm=False)
    assert isinstance(result, list)
    # Should still extract claims, just all unsupported
    if result:
        for audit in result:
            assert audit["is_supported"] is False


def test_audit_claims_garbage_input_does_not_raise(empty_profile):
    """Test 13: Garbage input doesn't crash the function."""
    garbage_inputs = [
        "!@#$%^&*()",
        "\x00\x01\x02 binary garbage",
        "   " * 100,  # Whitespace only
        "",
    ]
    for garbage in garbage_inputs:
        try:
            result = audit_claims(garbage, empty_profile, use_llm=False)
            assert isinstance(result, list)
        except Exception as e:
            pytest.fail(f"audit_claims raised on garbage input: {e}")


# ---------------------------------------------------------------------------
# Test Suite 3: _extract_claims() (Tests 14-16)
# ---------------------------------------------------------------------------


def test_extract_claims_returns_list():
    """Test 14: _extract_claims returns a list."""
    result = _extract_claims("Some resume text with claims.")
    assert isinstance(result, list)


def test_extract_claims_empty_string_returns_empty_list():
    """Test 15: _extract_claims returns [] for empty string."""
    result = _extract_claims("")
    assert isinstance(result, list)
    assert len(result) == 0


def test_extract_claims_finds_claims_in_resume(sample_resume):
    """Test 16: _extract_claims finds claims in sample resume."""
    result = _extract_claims(sample_resume)
    assert isinstance(result, list)
    assert len(result) > 0
    # Should find at least some sentence-like claims
    assert any(
        "Kafka" in claim or "events" in claim or "Python" in claim
        for claim in result
    )


# ---------------------------------------------------------------------------
# Test Suite 4: _check_claim_against_profile() (Tests 17-20)
# ---------------------------------------------------------------------------


def test_check_claim_against_profile_returns_dict():
    """Test 17: _check_claim_against_profile returns dict with 3 keys."""
    profile = {"skill_inventory": [], "experience_units": []}
    result = _check_claim_against_profile("Some claim", profile)
    assert isinstance(result, dict)
    expected_keys = {"is_supported", "evidence_refs", "confidence"}
    assert expected_keys.issubset(result.keys())


def test_check_claim_against_profile_finds_kafka(sample_profile):
    """Test 18: Finds Kafka in SAMPLE_PROFILE."""
    result = _check_claim_against_profile("Kafka", sample_profile)
    assert result["is_supported"] is True
    assert len(result["evidence_refs"]) > 0


def test_check_claim_against_profile_unknown_skill_confidence_0_1(sample_profile):
    """Test 19: Unknown skill gets confidence 0.1."""
    result = _check_claim_against_profile("QuantumComputing", sample_profile)
    assert result["is_supported"] is False
    # Confidence for unknown skill should be low (0.1 or close)
    assert result["confidence"] < 0.2, f"Unexpected confidence: {result['confidence']}"


def test_check_claim_against_profile_3_refs_confidence_high(sample_profile):
    """Test 20: Skill with 3+ refs gets confidence >= 0.6."""
    # Kafka has 3 refs, Kubernetes has 3 refs
    result = _check_claim_against_profile("Kafka", sample_profile)
    assert len(result["evidence_refs"]) >= 3
    assert result["confidence"] >= 0.6, (
        f"Expected >=0.6 for 3+ refs, got {result['confidence']}"
    )
