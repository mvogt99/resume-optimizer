"""Tests for per-agent acceptance criteria definitions.

Validates that each criterion correctly distinguishes passing from failing
agent output, and that the CRITERIA_REGISTRY has entries for all four agents.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.acceptance.criteria_types import AcceptanceCriterion
from agents.acceptance.resume_criteria import (
    CAREER_ADVISOR_CRITERIA,
    COVER_LETTER_CRITERIA,
    CRITERIA_REGISTRY,
    INTERVIEW_COACH_CRITERIA,
    RESUME_TAILOR_CRITERIA,
)


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _run_all(criteria, output):
    return [c.check(output) for c in criteria]


# ──────────────────────────────────────────────────────────────
# CRITERIA_REGISTRY
# ──────────────────────────────────────────────────────────────

class TestCriteriaRegistry:
    def test_all_agents_registered(self):
        for agent in ("resume_tailor", "cover_letter", "interview_coach", "career_advisor"):
            assert agent in CRITERIA_REGISTRY, f"{agent} missing from registry"

    def test_each_agent_has_at_least_two_criteria(self):
        for agent, criteria in CRITERIA_REGISTRY.items():
            assert len(criteria) >= 2, f"{agent} has <2 criteria"

    def test_all_criteria_are_correct_type(self):
        for agent, criteria in CRITERIA_REGISTRY.items():
            for c in criteria:
                assert isinstance(c, AcceptanceCriterion), f"{agent}: bad criterion type"


# ──────────────────────────────────────────────────────────────
# Resume Tailor
# ──────────────────────────────────────────────────────────────

GOOD_TAILOR = {
    "optimized_text": "A" * 200,
    "ats_score": 75,
    "version_id": "abc-123",
    "matching_keywords": ["python", "cloud"],
    "added_keywords": ["kubernetes"],
}

class TestResumeTailorCriteria:
    def test_passing_output_all_pass(self):
        results = _run_all(RESUME_TAILOR_CRITERIA, GOOD_TAILOR)
        assert all(results), f"Expected all pass, got: {results}"

    def test_missing_optimized_text_fails(self):
        bad = {**GOOD_TAILOR, "optimized_text": ""}
        results = _run_all(RESUME_TAILOR_CRITERIA, bad)
        assert results[0] is False  # optimized_text_present

    def test_short_optimized_text_fails(self):
        bad = {**GOOD_TAILOR, "optimized_text": "Short text."}
        results = _run_all(RESUME_TAILOR_CRITERIA, bad)
        assert results[0] is False

    def test_low_ats_score_fails(self):
        bad = {**GOOD_TAILOR, "ats_score": 30}
        results = _run_all(RESUME_TAILOR_CRITERIA, bad)
        assert results[1] is False  # ats_score_nonzero

    def test_zero_ats_score_fails(self):
        bad = {**GOOD_TAILOR, "ats_score": 0}
        results = _run_all(RESUME_TAILOR_CRITERIA, bad)
        assert results[1] is False

    def test_missing_version_id_fails(self):
        bad = {**GOOD_TAILOR, "version_id": ""}
        results = _run_all(RESUME_TAILOR_CRITERIA, bad)
        assert results[2] is False  # version_id_written

    def test_placeholder_in_text_fails(self):
        bad = {**GOOD_TAILOR, "optimized_text": "Dear [Company], I am [Your Name]." + "x" * 200}
        results = _run_all(RESUME_TAILOR_CRITERIA, bad)
        assert results[3] is False  # no_placeholders

    def test_clean_text_with_none_version_fails_version_criterion(self):
        bad = {**GOOD_TAILOR, "version_id": None}
        results = _run_all(RESUME_TAILOR_CRITERIA, bad)
        assert results[2] is False


# ──────────────────────────────────────────────────────────────
# Cover Letter
# ──────────────────────────────────────────────────────────────

GOOD_COVER = {
    "id": "cl-001",
    "body": "I am excited to apply for the Senior Engineer role. " * 8,
    "greeting": "Dear Hiring Manager,",
    "closing": "Sincerely, Jane Doe",
    "company": "Acme Corp",
    "role_title": "Senior Engineer",
}

class TestCoverLetterCriteria:
    def test_passing_output_all_pass(self):
        results = _run_all(COVER_LETTER_CRITERIA, GOOD_COVER)
        assert all(results), f"Expected all pass, got: {results}"

    def test_missing_body_fails(self):
        bad = {**GOOD_COVER, "body": ""}
        results = _run_all(COVER_LETTER_CRITERIA, bad)
        assert results[0] is False

    def test_short_body_fails(self):
        bad = {**GOOD_COVER, "body": "Short."}
        results = _run_all(COVER_LETTER_CRITERIA, bad)
        assert results[0] is False

    def test_missing_greeting_fails(self):
        bad = {**GOOD_COVER, "greeting": ""}
        results = _run_all(COVER_LETTER_CRITERIA, bad)
        assert results[1] is False

    def test_missing_closing_fails(self):
        bad = {**GOOD_COVER, "closing": None}
        results = _run_all(COVER_LETTER_CRITERIA, bad)
        assert results[2] is False

    def test_placeholder_in_body_fails(self):
        bad = {**GOOD_COVER, "body": "Dear [Company], I am [Your Name]." + "x" * 200}
        results = _run_all(COVER_LETTER_CRITERIA, bad)
        assert results[3] is False

    def test_company_name_placeholder_fails(self):
        bad = {**GOOD_COVER, "body": "I want to work at [Company Name]. " * 6}
        results = _run_all(COVER_LETTER_CRITERIA, bad)
        assert results[3] is False


# ──────────────────────────────────────────────────────────────
# Interview Coach
# ──────────────────────────────────────────────────────────────

GOOD_COACH = {
    "session_id": "sess-abc-123",
    "message": "Tell me about a time you led a cross-functional team to deliver a complex project.",
    "persona": "hiring_manager",
}

class TestInterviewCoachCriteria:
    def test_passing_output_all_pass(self):
        results = _run_all(INTERVIEW_COACH_CRITERIA, GOOD_COACH)
        assert all(results), f"Expected all pass, got: {results}"

    def test_missing_session_id_fails(self):
        bad = {**GOOD_COACH, "session_id": ""}
        results = _run_all(INTERVIEW_COACH_CRITERIA, bad)
        assert results[0] is False

    def test_none_session_id_fails(self):
        bad = {**GOOD_COACH, "session_id": None}
        results = _run_all(INTERVIEW_COACH_CRITERIA, bad)
        assert results[0] is False

    def test_missing_message_fails(self):
        bad = {**GOOD_COACH, "message": ""}
        results = _run_all(INTERVIEW_COACH_CRITERIA, bad)
        assert results[1] is False

    def test_short_message_fails(self):
        bad = {**GOOD_COACH, "message": "Hi."}
        results = _run_all(INTERVIEW_COACH_CRITERIA, bad)
        assert results[1] is False

    def test_error_key_fails(self):
        bad = {**GOOD_COACH, "error": "Session creation failed"}
        results = _run_all(INTERVIEW_COACH_CRITERIA, bad)
        assert results[2] is False


# ──────────────────────────────────────────────────────────────
# Career Advisor
# ──────────────────────────────────────────────────────────────

GOOD_ADVISOR = {
    "trajectory": "10 years in enterprise architecture",
    "skill_gaps": ["data engineering", "MLOps"],
    "recommendations": ["Pursue AWS certification", "Lead a data platform initiative"],
    "strengths": ["stakeholder management", "system design"],
}

class TestCareerAdvisorCriteria:
    def test_passing_output_all_pass(self):
        results = _run_all(CAREER_ADVISOR_CRITERIA, GOOD_ADVISOR)
        assert all(results), f"Expected all pass, got: {results}"

    def test_empty_dict_fails_substance(self):
        bad = {}
        results = _run_all(CAREER_ADVISOR_CRITERIA, bad)
        assert results[0] is False  # result_is_dict (len < 2)

    def test_none_result_fails(self):
        bad = None
        results = _run_all(CAREER_ADVISOR_CRITERIA, bad)
        assert results[0] is False

    def test_no_substance_keys_fails(self):
        bad = {"llm_output": "some text", "model": "qwen3"}
        results = _run_all(CAREER_ADVISOR_CRITERIA, bad)
        assert results[1] is False  # substance_fields_present

    def test_error_key_fails(self):
        bad = {**GOOD_ADVISOR, "error": "LLM unavailable"}
        results = _run_all(CAREER_ADVISOR_CRITERIA, bad)
        assert results[2] is False

    def test_alternate_substance_key_passes(self):
        alt = {"phases": ["phase 1", "phase 2"], "next_roles": ["VP Eng"], "gaps": ["ML"]}
        results = _run_all(CAREER_ADVISOR_CRITERIA, alt)
        # first criterion: len >= 2 ✓, substance ✓, no error ✓
        assert results[0] is True
        assert results[1] is True
        assert results[2] is True
