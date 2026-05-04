"""Tests for W2: COACH_ANSWER_CRITERIA, ADVISOR_ROADMAP_CRITERIA, ADVISOR_ROLES_CRITERIA,
and COVER_REGEN_CRITERIA.

Validates that the new criteria correctly pass/fail on representative outputs.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.acceptance.resume_verifier import verify


# ──────────────────────────────────────────────────────────────
# COVER_LETTER_REGEN (cover_letter_regen)
# ──────────────────────────────────────────────────────────────

class TestCoverLetterRegen:
    def test_good_regen_passes(self):
        good = {
            "body": "I am excited to apply for this role at TechCorp. " * 6,
            "greeting": "Dear Hiring Manager,",
            "closing": "Best regards, Jane",
        }
        result = verify("cover_letter_regen", good)
        assert result.passed is True

    def test_short_body_fails(self):
        bad = {"body": "Too short.", "greeting": "Hi", "closing": "Thanks"}
        result = verify("cover_letter_regen", bad)
        assert result.passed is False
        names = [f.name for f in result.failures]
        assert "body_present" in names

    def test_placeholder_in_body_fails(self):
        bad = {
            "body": "[Company] is a great company and I would love to join. " * 5,
            "greeting": "Dear Hiring Manager,",
            "closing": "Best regards",
        }
        result = verify("cover_letter_regen", bad)
        assert result.passed is False
        names = [f.name for f in result.failures]
        assert "no_placeholders_in_body" in names

    def test_missing_greeting_fails(self):
        bad = {
            "body": "I am a strong candidate for this role. " * 5,
            "greeting": "",
            "closing": "Regards",
        }
        result = verify("cover_letter_regen", bad)
        assert result.passed is False
        names = [f.name for f in result.failures]
        assert "greeting_present" in names

    def test_missing_closing_fails(self):
        bad = {
            "body": "I am a strong candidate for this role. " * 5,
            "greeting": "Dear Hiring Manager,",
            "closing": "",
        }
        result = verify("cover_letter_regen", bad)
        assert result.passed is False
        names = [f.name for f in result.failures]
        assert "closing_present" in names


# ──────────────────────────────────────────────────────────────
# COACH_ANSWER_CRITERIA (coach_answer)
# ──────────────────────────────────────────────────────────────

GOOD_ANSWER_CONTINUING = {
    "score": {"expertise": 7, "communication": 8, "feedback": "Good STAR structure."},
    "is_complete": False,
    "next_question": "Describe a project where you had to resolve a team conflict.",
    "current_question": 2,
    "total_questions": 5,
}

GOOD_ANSWER_FINAL = {
    "score": {"expertise": 8, "communication": 9, "feedback": "Excellent."},
    "is_complete": True,
    "assessment": {"recommendation": "Strong candidate", "overall": "pass"},
    "current_question": 5,
    "total_questions": 5,
}


class TestCoachAnswerCriteria:
    def test_continuing_session_passes(self):
        result = verify("coach_answer", GOOD_ANSWER_CONTINUING)
        assert result.passed is True

    def test_final_session_passes(self):
        result = verify("coach_answer", GOOD_ANSWER_FINAL)
        assert result.passed is True

    def test_missing_score_fails(self):
        bad = {**GOOD_ANSWER_CONTINUING, "score": {}}
        result = verify("coach_answer", bad)
        assert result.passed is False
        names = [f.name for f in result.failures]
        assert "score_present" in names

    def test_missing_is_complete_fails(self):
        bad = {k: v for k, v in GOOD_ANSWER_CONTINUING.items() if k != "is_complete"}
        result = verify("coach_answer", bad)
        assert result.passed is False
        names = [f.name for f in result.failures]
        assert "is_complete_is_bool" in names

    def test_no_question_or_assessment_fails(self):
        bad = {
            "score": {"expertise": 7},
            "is_complete": False,
            # no next_question, no assessment
        }
        result = verify("coach_answer", bad)
        assert result.passed is False
        names = [f.name for f in result.failures]
        assert "continuation_or_assessment" in names

    def test_error_key_fails(self):
        bad = {**GOOD_ANSWER_CONTINUING, "error": "DB write failed"}
        result = verify("coach_answer", bad)
        assert result.passed is False
        names = [f.name for f in result.failures]
        assert "no_error_key" in names

    def test_none_output_does_not_raise(self):
        result = verify("coach_answer", None)
        assert result is not None

    def test_wrong_type_does_not_raise(self):
        result = verify("coach_answer", "not a dict")
        assert result is not None


# ──────────────────────────────────────────────────────────────
# ADVISOR_ROADMAP_CRITERIA (advisor_roadmap)
# ──────────────────────────────────────────────────────────────

GOOD_ROADMAP = {
    "target_role": "VP of Engineering",
    "current_readiness": 65,
    "timeline_months": 18,
    "phases": [
        {"phase": 1, "name": "Foundation", "skills": ["leadership"], "milestone": "Lead a team"},
        {"phase": 2, "name": "Scale", "skills": ["strategy"], "milestone": "OKR ownership"},
    ],
    "quick_wins": ["Read 'An Elegant Puzzle'"],
    "key_gap": "Organizational design experience",
}


class TestAdvisorRoadmapCriteria:
    def test_good_roadmap_passes(self):
        result = verify("advisor_roadmap", GOOD_ROADMAP)
        assert result.passed is True

    def test_missing_target_role_fails(self):
        bad = {**GOOD_ROADMAP, "target_role": ""}
        result = verify("advisor_roadmap", bad)
        assert result.passed is False
        names = [f.name for f in result.failures]
        assert "target_role_present" in names

    def test_empty_phases_fails(self):
        bad = {**GOOD_ROADMAP, "phases": []}
        result = verify("advisor_roadmap", bad)
        assert result.passed is False
        names = [f.name for f in result.failures]
        assert "phases_present" in names

    def test_missing_key_gap_fails(self):
        bad = {**GOOD_ROADMAP, "key_gap": ""}
        result = verify("advisor_roadmap", bad)
        assert result.passed is False
        names = [f.name for f in result.failures]
        assert "key_gap_present" in names

    def test_error_key_fails(self):
        bad = {**GOOD_ROADMAP, "error": "LLM unavailable"}
        result = verify("advisor_roadmap", bad)
        assert result.passed is False

    def test_none_output_does_not_raise(self):
        result = verify("advisor_roadmap", None)
        assert result is not None


# ──────────────────────────────────────────────────────────────
# ADVISOR_ROLES_CRITERIA (advisor_roles)
# ──────────────────────────────────────────────────────────────

GOOD_ROLES = {
    "recommendations": [
        {
            "title": "VP of Engineering",
            "industry": "Technology",
            "fit_score": 82,
            "salary_range": "$250k-$300k",
            "reasoning": "Strong technical background with leadership trajectory.",
            "growth_potential": "CTO path",
            "key_requirements": ["team management", "roadmap ownership"],
            "gaps_to_address": ["board presentation experience"],
        },
        {"title": "Director of Architecture", "industry": "Finance", "fit_score": 75},
    ]
}


class TestAdvisorRolesCriteria:
    def test_good_recommendations_passes(self):
        result = verify("advisor_roles", GOOD_ROLES)
        assert result.passed is True

    def test_empty_recommendations_fails(self):
        bad = {"recommendations": []}
        result = verify("advisor_roles", bad)
        assert result.passed is False
        names = [f.name for f in result.failures]
        assert "recommendations_present" in names

    def test_missing_title_fails(self):
        bad = {"recommendations": [{"industry": "Tech", "fit_score": 80}]}
        result = verify("advisor_roles", bad)
        assert result.passed is False
        names = [f.name for f in result.failures]
        assert "each_rec_has_title" in names

    def test_error_key_fails(self):
        bad = {"recommendations": GOOD_ROLES["recommendations"], "error": "failed"}
        result = verify("advisor_roles", bad)
        assert result.passed is False

    def test_none_output_does_not_raise(self):
        result = verify("advisor_roles", None)
        assert result is not None

    def test_non_dict_output_does_not_raise(self):
        result = verify("advisor_roles", [])
        assert result is not None
