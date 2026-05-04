"""Tests for the resume_verifier engine.

Verifies that AcceptanceResult is correctly computed from criteria checks,
that penalty calculation is bounded, and that unknown agent types degrade
gracefully (pass with 0 criteria rather than crash).
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.acceptance.criteria_types import AcceptanceResult
from agents.acceptance.resume_verifier import apply_penalty, verify


# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────

GOOD_TAILOR = {
    "optimized_text": "B" * 300,
    "ats_score": 82,
    "version_id": "v-001",
    "matching_keywords": ["cloud"],
    "added_keywords": ["terraform"],
}

BAD_TAILOR_EMPTY = {}

BAD_TAILOR_PLACEHOLDER = {
    "optimized_text": "[Your Name] applies to [Company]. " + "x" * 200,
    "ats_score": 78,
    "version_id": "v-002",
}

GOOD_COVER = {
    "id": "cl-1",
    "body": "I am excited to bring my expertise in cloud architecture. " * 5,
    "greeting": "Dear Hiring Manager,",
    "closing": "Best regards, Jane",
    "company": "TechCorp",
}


# ──────────────────────────────────────────────────────────────
# verify() — return type and structure
# ──────────────────────────────────────────────────────────────

class TestVerifyReturnType:
    def test_returns_acceptance_result(self):
        result = verify("resume_tailor", GOOD_TAILOR)
        assert isinstance(result, AcceptanceResult)

    def test_result_has_agent_type(self):
        result = verify("cover_letter", GOOD_COVER)
        assert result.agent_type == "cover_letter"

    def test_unknown_agent_type_returns_passing_result(self):
        result = verify("nonexistent_agent", {"anything": "goes"})
        assert result.passed is True
        assert result.criteria_total == 0
        assert result.criteria_passed == 0

    def test_to_dict_is_serialisable(self):
        result = verify("resume_tailor", GOOD_TAILOR)
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "passed" in d
        assert "failures" in d
        assert isinstance(d["failures"], list)

    def test_to_json_returns_string(self):
        result = verify("resume_tailor", GOOD_TAILOR)
        s = result.to_json()
        assert isinstance(s, str)
        assert '"passed"' in s


# ──────────────────────────────────────────────────────────────
# verify() — correct pass/fail decisions
# ──────────────────────────────────────────────────────────────

class TestVerifyPassFail:
    def test_good_tailor_passes(self):
        result = verify("resume_tailor", GOOD_TAILOR)
        assert result.passed is True
        assert result.criteria_passed == result.criteria_total
        assert result.failures == []
        assert result.a_score_penalty == 0

    def test_empty_tailor_fails(self):
        result = verify("resume_tailor", BAD_TAILOR_EMPTY)
        assert result.passed is False
        assert len(result.failures) > 0
        assert result.a_score_penalty > 0

    def test_placeholder_tailor_fails(self):
        result = verify("resume_tailor", BAD_TAILOR_PLACEHOLDER)
        # no_placeholders criterion fails + possibly ats_score passes but text is tainted
        assert result.passed is False
        failure_names = [f.name for f in result.failures]
        assert "no_placeholders" in failure_names

    def test_good_cover_letter_passes(self):
        result = verify("cover_letter", GOOD_COVER)
        assert result.passed is True

    def test_cover_letter_missing_body_fails(self):
        bad = {**GOOD_COVER, "body": ""}
        result = verify("cover_letter", bad)
        assert result.passed is False
        names = [f.name for f in result.failures]
        assert "body_present" in names

    def test_interview_coach_valid_session_passes(self):
        good = {
            "session_id": "s-abc",
            "message": "Describe a challenging project where you led a team through ambiguity.",
        }
        result = verify("interview_coach", good)
        assert result.passed is True

    def test_interview_coach_with_error_key_fails(self):
        bad = {"session_id": "s-abc", "message": "Hello", "error": "DB write failed"}
        result = verify("interview_coach", bad)
        assert result.passed is False

    def test_career_advisor_substance_passes(self):
        good = {
            "trajectory": "CTO track",
            "skill_gaps": ["MLOps"],
            "recommendations": ["Mentor engineers"],
        }
        result = verify("career_advisor", good)
        assert result.passed is True

    def test_career_advisor_empty_fails(self):
        result = verify("career_advisor", {})
        assert result.passed is False


# ──────────────────────────────────────────────────────────────
# verify() — penalty calculation
# ──────────────────────────────────────────────────────────────

class TestVerifyPenalty:
    def test_no_failure_no_penalty(self):
        result = verify("resume_tailor", GOOD_TAILOR)
        assert result.a_score_penalty == 0

    def test_one_failure_penalty_10(self):
        bad = {**GOOD_TAILOR, "version_id": ""}
        result = verify("resume_tailor", bad)
        assert result.a_score_penalty == 10

    def test_two_failures_penalty_20(self):
        bad = {**GOOD_TAILOR, "version_id": "", "ats_score": 0}
        result = verify("resume_tailor", bad)
        assert result.a_score_penalty == 20

    def test_penalty_capped_at_40(self):
        # All 4 criteria fail
        result = verify("resume_tailor", {})
        assert result.a_score_penalty <= 40

    def test_failure_count_matches_penalty(self):
        result = verify("resume_tailor", {})
        expected_penalty = min(len(result.failures) * 10, 40)
        assert result.a_score_penalty == expected_penalty


# ──────────────────────────────────────────────────────────────
# verify() — criteria exception safety
# ──────────────────────────────────────────────────────────────

class TestVerifyExceptionSafety:
    def test_none_output_does_not_raise(self):
        # All criteria must handle None output gracefully
        for agent in ("resume_tailor", "cover_letter", "interview_coach", "career_advisor"):
            result = verify(agent, None)
            assert isinstance(result, AcceptanceResult)

    def test_wrong_type_output_does_not_raise(self):
        for agent in ("resume_tailor", "cover_letter"):
            result = verify(agent, "not a dict")
            assert isinstance(result, AcceptanceResult)


# ──────────────────────────────────────────────────────────────
# apply_penalty()
# ──────────────────────────────────────────────────────────────

class TestApplyPenalty:
    def test_passing_acceptance_no_change(self):
        result = verify("resume_tailor", GOOD_TAILOR)
        scores = {"f": 25, "t": 25, "a": 25, "gap": 0}
        updated = apply_penalty(scores, result)
        assert updated["a"] == 25
        assert updated["gap"] == 0

    def test_penalty_reduces_a_score(self):
        bad = {**GOOD_TAILOR, "version_id": ""}  # 1 failure → penalty 10
        result = verify("resume_tailor", bad)
        scores = {"f": 25, "t": 25, "a": 25, "gap": 0}
        updated = apply_penalty(scores, result)
        assert updated["a"] == 15

    def test_a_score_not_below_zero(self):
        result = verify("resume_tailor", {})  # 4 failures → penalty 40
        scores = {"f": 20, "t": 20, "a": 10, "gap": 30}
        updated = apply_penalty(scores, result)
        assert updated["a"] >= 0

    def test_original_scores_not_mutated(self):
        bad = {**GOOD_TAILOR, "version_id": ""}
        result = verify("resume_tailor", bad)
        scores = {"f": 25, "t": 25, "a": 25, "gap": 0}
        original_a = scores["a"]
        apply_penalty(scores, result)
        assert scores["a"] == original_a  # original unchanged
