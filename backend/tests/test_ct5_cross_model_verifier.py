"""CT-5: Unit tests for CrossModelVerifier (heuristic path)."""

from __future__ import annotations

import sys

import pytest

sys.path.insert(0, "/home/mike/models/source/hybrid-ai-windows/applications/resume-optimizer/backend")

from agents.cross_model_verifier import CrossModelVerifier, verify_resume

_ORIGINAL = "Experienced engineer. Led projects at Acme Corp. Python developer."
_TAILORED = (
    "Senior Python engineer with 8 years building AWS microservices. "
    "Led team of 12 engineers. Reduced deployment time by 45%. "
    "Designed Kubernetes clusters serving 1M+ users daily."
)
_JD = (
    "Seeking Senior Python Engineer with AWS, Kubernetes, and CI/CD experience. "
    "Must have team leadership and performance optimization background."
)


class TestCrossModelVerifierInit:
    def test_same_models_raises(self):
        with pytest.raises(ValueError, match="different"):
            CrossModelVerifier("model-a", "model-a")

    def test_different_models_ok(self):
        v = CrossModelVerifier("rtx5090", "deepseek-r1-32b")
        assert v.generator_model == "rtx5090"
        assert v.verifier_model == "deepseek-r1-32b"

    def test_get_config(self):
        v = CrossModelVerifier("rtx5090", "deepseek-r1-32b")
        cfg = v.get_config()
        assert cfg["generator_model"] == "rtx5090"
        assert cfg["verifier_model"] == "deepseek-r1-32b"


class TestHeuristicVerification:
    """Test heuristic fallback (no gateway call needed)."""

    def _heuristic(self, original, tailored, jd):
        v = CrossModelVerifier()
        return v._verify_heuristic(original, tailored, jd)

    def test_returns_all_dimensions(self):
        result = self._heuristic(_ORIGINAL, _TAILORED, _JD)
        for dim in ["relevance", "substance", "differentiation", "ats_compliance"]:
            assert dim in result

    def test_scores_in_range(self):
        result = self._heuristic(_ORIGINAL, _TAILORED, _JD)
        for dim in ["relevance", "substance", "differentiation", "ats_compliance"]:
            assert 0.0 <= result[dim] <= 10.0

    def test_average_field_present(self):
        result = self._heuristic(_ORIGINAL, _TAILORED, _JD)
        assert "average" in result
        assert 0.0 <= result["average"] <= 10.0

    def test_passed_field_is_bool(self):
        result = self._heuristic(_ORIGINAL, _TAILORED, _JD)
        assert isinstance(result["passed"], bool)

    def test_well_tailored_passes(self):
        result = self._heuristic(_ORIGINAL, _TAILORED, _JD)
        assert result["passed"] is True

    def test_empty_tailored_fails(self):
        result = self._heuristic(_ORIGINAL, "", _JD)
        assert result["passed"] is False

    def test_issues_list_present(self):
        result = self._heuristic(_ORIGINAL, _TAILORED, _JD)
        assert isinstance(result["issues"], list)


class TestLLMParseScores:
    def test_valid_format_parsed(self):
        v = CrossModelVerifier()
        content = "relevance:8 substance:7 differentiation:6 ats_compliance:9"
        result = v._parse_llm_scores(content)
        assert result is not None
        assert result["relevance"] == pytest.approx(8.0)
        assert result["passed"] is True

    def test_missing_dimension_returns_none(self):
        v = CrossModelVerifier()
        content = "relevance:8 substance:7 differentiation:6"  # missing ats_compliance
        result = v._parse_llm_scores(content)
        assert result is None

    def test_scores_clamped_to_10(self):
        v = CrossModelVerifier()
        content = "relevance:99 substance:7 differentiation:6 ats_compliance:5"
        result = v._parse_llm_scores(content)
        assert result is not None
        assert result["relevance"] == pytest.approx(10.0)

    def test_low_scores_fail(self):
        v = CrossModelVerifier()
        content = "relevance:3 substance:2 differentiation:4 ats_compliance:1"
        result = v._parse_llm_scores(content)
        assert result is not None
        assert result["passed"] is False


class TestVerifyFallsBackToHeuristic:
    def test_gateway_unreachable_falls_back(self, monkeypatch):
        v = CrossModelVerifier()
        # Explicit stub instead of patch.object: the substitute is visible here.
        monkeypatch.setattr(v, "_verify_with_llm", lambda *a, **k: None)
        result = v.verify(_ORIGINAL, _TAILORED, _JD)
        assert "average" in result
        assert isinstance(result["passed"], bool)


class TestConvenienceFunction:
    def test_verify_resume_returns_dict(self, monkeypatch):
        """The LLM leg is stubbed with a plain function rather than unittest.mock:
        an explicit stub states what it returns, and monkeypatch undoes it."""
        from agents.cross_model_verifier import CrossModelVerifier

        def _no_llm(self, *args, **kwargs):
            return None

        monkeypatch.setattr(CrossModelVerifier, "_verify_with_llm", _no_llm)
        result = verify_resume(_ORIGINAL, _TAILORED, _JD)
        assert "average" in result
        assert "passed" in result
