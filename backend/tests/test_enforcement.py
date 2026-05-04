"""Tests for the enforcement module: retry decisions and teaching text generation.

Does not test the route handler retry loop — that belongs in integration tests.
Tests here are pure unit tests over enforcement.py logic.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch

from agents.acceptance.criteria_types import AcceptanceResult, CriteriaFailure
from agents.acceptance.enforcement import (
    MAX_ATTEMPTS,
    _enrich_teaching_with_llm,
    build_failure_teaching,
    record_acceptance,
    should_retry,
)


# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────

def _passing_result(agent_type="resume_tailor"):
    return AcceptanceResult(
        agent_type=agent_type,
        passed=True,
        criteria_total=4,
        criteria_passed=4,
        failures=[],
        a_score_penalty=0,
    )


def _failing_result(agent_type="cover_letter", failures=None):
    if failures is None:
        failures = [
            CriteriaFailure(name="body_present", hint="body is empty"),
            CriteriaFailure(name="no_placeholders_in_body", hint="placeholder found"),
        ]
    return AcceptanceResult(
        agent_type=agent_type,
        passed=False,
        criteria_total=4,
        criteria_passed=2,
        failures=failures,
        a_score_penalty=20,
    )


# ──────────────────────────────────────────────────────────────
# should_retry()
# ──────────────────────────────────────────────────────────────

class TestShouldRetry:
    def test_passing_result_never_retries(self):
        r = _passing_result()
        for attempt in range(MAX_ATTEMPTS + 2):
            assert should_retry(r, attempt) is False

    def test_failing_on_first_attempt_retries(self):
        r = _failing_result()
        assert should_retry(r, attempt=0) is True

    def test_failing_on_last_attempt_does_not_retry(self):
        r = _failing_result()
        # attempt = MAX_ATTEMPTS - 1 means we've already used all retries
        assert should_retry(r, attempt=MAX_ATTEMPTS - 1) is False

    def test_max_attempts_is_at_least_2(self):
        assert MAX_ATTEMPTS >= 2

    def test_retry_exhausted_after_max_minus_one(self):
        r = _failing_result()
        retried = sum(1 for a in range(MAX_ATTEMPTS) if should_retry(r, a))
        # should retry on all attempts except the last
        assert retried == MAX_ATTEMPTS - 1


# ──────────────────────────────────────────────────────────────
# build_failure_teaching()
# ──────────────────────────────────────────────────────────────

class TestBuildFailureTeaching:
    def test_passing_result_returns_empty_string(self):
        r = _passing_result()
        text = build_failure_teaching(r)
        assert text == ""

    def test_failing_result_returns_nonempty_string(self):
        r = _failing_result()
        text = build_failure_teaching(r)
        assert isinstance(text, str)
        assert len(text) > 0

    def test_teaching_contains_agent_type(self):
        r = _failing_result(agent_type="cover_letter")
        text = build_failure_teaching(r)
        assert "cover_letter" in text

    def test_teaching_contains_failure_names(self):
        r = _failing_result()
        text = build_failure_teaching(r)
        assert "body_present" in text
        assert "no_placeholders_in_body" in text

    def test_teaching_contains_failure_hints(self):
        r = _failing_result()
        text = build_failure_teaching(r)
        assert "body is empty" in text
        assert "placeholder found" in text

    def test_teaching_contains_remediation_guidance(self):
        r = _failing_result()
        text = build_failure_teaching(r)
        assert "Remediation" in text

    def test_context_injected_into_teaching(self):
        r = _failing_result()
        ctx = {"posting_id": "post-42", "user_id": "7"}
        text = build_failure_teaching(r, context=ctx)
        assert "post-42" in text
        assert "user_id" in text

    def test_no_context_does_not_crash(self):
        r = _failing_result()
        text = build_failure_teaching(r, context=None)
        assert isinstance(text, str)

    def test_single_failure(self):
        r = _failing_result(
            failures=[CriteriaFailure(name="only_one", hint="Only failure")]
        )
        r.passed = False
        text = build_failure_teaching(r)
        assert "only_one" in text
        assert "Only failure" in text

    def test_empty_failures_list_with_passed_false(self):
        r = AcceptanceResult(
            agent_type="interview_coach",
            passed=False,
            criteria_total=3,
            criteria_passed=3,
            failures=[],
            a_score_penalty=0,
        )
        text = build_failure_teaching(r)
        # passed=False but no failures is an edge case — should still return teaching
        assert isinstance(text, str)


# ──────────────────────────────────────────────────────────────
# record_acceptance()
# ──────────────────────────────────────────────────────────────

class TestRecordAcceptance:
    def test_does_not_raise_on_pass(self):
        r = _passing_result()
        record_acceptance("run-id-1", r, attempt=0, teaching="")

    def test_does_not_raise_on_fail(self):
        r = _failing_result()
        teaching = build_failure_teaching(r)
        record_acceptance("run-id-2", r, attempt=1, teaching=teaching)

    def test_does_not_raise_with_empty_run_id(self):
        r = _passing_result()
        record_acceptance("", r, attempt=0, teaching="")

    def test_does_not_raise_with_long_teaching(self):
        r = _failing_result()
        long_teaching = "x" * 5000
        record_acceptance("run-99", r, attempt=0, teaching=long_teaching)


# ──────────────────────────────────────────────────────────────
# LLM-enriched teaching (RTX 5090 call_direct integration)
# ──────────────────────────────────────────────────────────────

class TestLLMEnrichedTeaching:
    """Tests for the RTX 5090 enrichment path in build_failure_teaching.

    Mocks smart_llm.call_direct so tests run without a live GPU.
    """

    def test_no_output_skips_llm(self):
        """Without output=, no LLM call is made; rule-based text is returned."""
        r = _failing_result()
        with patch("agents.acceptance.enforcement._enrich_teaching_with_llm") as mock_enrich:
            text = build_failure_teaching(r, output=None)
        mock_enrich.assert_not_called()
        assert isinstance(text, str)
        assert len(text) > 0

    def test_output_triggers_enrichment_attempt(self):
        """When output is provided, enrichment is attempted."""
        r = _failing_result()
        with patch("agents.acceptance.enforcement._enrich_teaching_with_llm", return_value=None) as mock_enrich:
            build_failure_teaching(r, output={"body": ""})
        mock_enrich.assert_called_once()

    def test_enriched_text_appended_when_llm_returns(self):
        r = _failing_result()
        with patch("agents.acceptance.enforcement._enrich_teaching_with_llm", return_value="• Fill body field with ≥150 chars."):
            text = build_failure_teaching(r, output={"body": ""})
        assert "RTX 5090 Targeted Instructions" in text
        assert "Fill body field" in text

    def test_falls_back_to_rule_based_on_llm_none(self):
        r = _failing_result()
        with patch("agents.acceptance.enforcement._enrich_teaching_with_llm", return_value=None):
            text = build_failure_teaching(r, output={"body": ""})
        assert "Remediation guidance" in text
        assert "RTX 5090" not in text

    def test_rule_based_prefix_always_present(self):
        r = _failing_result()
        with patch("agents.acceptance.enforcement._enrich_teaching_with_llm", return_value="• specific fix"):
            text = build_failure_teaching(r, output={"body": ""})
        # Rule-based teaching must still be present as preamble
        assert "body_present" in text or "no_placeholders_in_body" in text

    def test_passing_result_still_returns_empty_with_output(self):
        r = _passing_result()
        with patch("agents.acceptance.enforcement._enrich_teaching_with_llm") as mock_enrich:
            text = build_failure_teaching(r, output={"body": "content"})
        assert text == ""
        mock_enrich.assert_not_called()


class TestEnrichTeachingWithLlm:
    """Unit tests for _enrich_teaching_with_llm directly."""

    def _failing(self):
        return _failing_result()

    def test_returns_none_on_import_error(self):
        r = self._failing()
        with patch.dict("sys.modules", {"smart_llm": None}):
            result = _enrich_teaching_with_llm(r, "base text", {"body": ""})
        assert result is None

    def test_returns_none_on_call_direct_exception(self):
        r = self._failing()
        mock_module = type(sys)("smart_llm")
        mock_module.call_direct = lambda *a, **kw: (_ for _ in ()).throw(Exception("GPU busy"))
        with patch.dict("sys.modules", {"smart_llm": mock_module}):
            result = _enrich_teaching_with_llm(r, "base text", {"body": ""})
        assert result is None

    def test_returns_none_when_llm_returns_empty(self):
        r = self._failing()
        mock_module = type(sys)("smart_llm")
        mock_module.call_direct = lambda *a, **kw: ""
        with patch.dict("sys.modules", {"smart_llm": mock_module}):
            result = _enrich_teaching_with_llm(r, "base text", {"body": ""})
        assert result is None

    def test_returns_string_when_llm_succeeds(self):
        r = self._failing()
        mock_module = type(sys)("smart_llm")
        mock_module.call_direct = lambda *a, **kw: "• Ensure body has at least 150 characters."
        with patch.dict("sys.modules", {"smart_llm": mock_module}):
            result = _enrich_teaching_with_llm(r, "base text", {"body": ""})
        assert isinstance(result, str)
        assert len(result) > 0

    def test_handles_non_serializable_output_gracefully(self):
        r = self._failing()
        mock_module = type(sys)("smart_llm")
        mock_module.call_direct = lambda *a, **kw: "• Ensure body field contains at least 150 characters of substantive content."

        class Unserializable:
            pass

        with patch.dict("sys.modules", {"smart_llm": mock_module}):
            # Should not raise even with unserializable output
            result = _enrich_teaching_with_llm(r, "base text", Unserializable())
        assert result is not None
