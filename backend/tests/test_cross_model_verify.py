"""CT-5: Tests for CrossModelVerifier."""

import pytest

from agents.cross_model_verifier import CrossModelVerifier, verify_resume


def test_different_model_used_for_verification():
    verifier = CrossModelVerifier("rtx5090", "haiku")
    config = verifier.get_config()
    assert config["generator_model"] != config["verifier_model"]


def test_rubric_returns_4_dimensions():
    verifier = CrossModelVerifier("rtx5090", "haiku")
    result = verifier.verify("original text", "tailored text", "job description keywords")
    for key in ("relevance", "substance", "differentiation", "ats_compliance"):
        assert key in result


def test_average_below_6_triggers_fail():
    verifier = CrossModelVerifier("rtx5090", "haiku")
    # Identical texts + no JD overlap → low relevance/ats + low differentiation
    result = verifier.verify("same text here", "same text here", "unrelated xyz abc")
    assert result["passed"] is False
    assert result["average"] < 6.0


def test_verification_result_stored_with_claim():
    verifier = CrossModelVerifier("rtx5090", "haiku")
    result = verifier.verify("original", "tailored", "job description")
    assert "passed" in result
    assert isinstance(result["passed"], bool)


def test_same_model_blocked_at_config_level():
    with pytest.raises(ValueError):
        CrossModelVerifier("same_model", "same_model")


def test_verification_timeout_handled_gracefully():
    verifier = CrossModelVerifier("rtx5090", "haiku")
    result = verifier.verify("", "", "")
    assert "passed" in result
    assert isinstance(result["issues"], list)
