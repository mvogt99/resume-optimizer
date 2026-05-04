"""Tests for skills_optimizer.py — pure logic functions.

Note: analyze_skills_gap() calls nlp_engine.extract_skill_phrases() and
extract_keywords(), so those are replaced via monkeypatch (pytest-native,
no unittest.mock).
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import skills_optimizer
from skills_optimizer import (
    analyze_skills_gap,
    get_endorsement_weighted_skills,
    weighted_skill_match,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def linkedin_with_endorsements():
    return {
        "skills": [
            {"name": "Python", "endorsements": 117},
            {"name": "AWS", "endorsements": 45},
            {"name": "Docker", "endorsements": 30},
            {"name": "Kubernetes", "endorsements": 20},
            {"name": "Java", "endorsements": 5},
            {"name": "Go", "endorsements": 0},
        ]
    }


@pytest.fixture
def linkedin_alt_format():
    """Skills using the 'skill'/'endorsements_count' field names."""
    return {
        "skills": [
            {"skill": "Python", "endorsements_count": 50},
            {"skill": "React", "endorsements_count": 10},
        ]
    }


# ---------------------------------------------------------------------------
# get_endorsement_weighted_skills tests
# ---------------------------------------------------------------------------
class TestGetEndorsementWeightedSkills:
    def test_sorted_by_endorsement_count(self, linkedin_with_endorsements):
        result = get_endorsement_weighted_skills(linkedin_with_endorsements)
        endorsements = [s["endorsements"] for s in result]
        assert endorsements == sorted(endorsements, reverse=True)

    def test_weights_normalized_0_to_1(self, linkedin_with_endorsements):
        result = get_endorsement_weighted_skills(linkedin_with_endorsements)
        assert result[0]["weight"] == 1.0  # Highest endorsed
        for s in result:
            assert 0 <= s["weight"] <= 1.0

    def test_top_n_limits_results(self, linkedin_with_endorsements):
        result = get_endorsement_weighted_skills(linkedin_with_endorsements, top_n=3)
        assert len(result) == 3

    def test_top_n_larger_than_total(self, linkedin_with_endorsements):
        result = get_endorsement_weighted_skills(linkedin_with_endorsements, top_n=100)
        assert len(result) == 6

    def test_empty_skills_returns_empty(self):
        assert get_endorsement_weighted_skills({"skills": []}) == []
        assert get_endorsement_weighted_skills({}) == []

    def test_zero_endorsements_included(self, linkedin_with_endorsements):
        result = get_endorsement_weighted_skills(linkedin_with_endorsements)
        go = next(s for s in result if s["name"] == "Go")
        assert go["endorsements"] == 0
        assert go["weight"] == 0.0

    def test_alt_field_names(self, linkedin_alt_format):
        result = get_endorsement_weighted_skills(linkedin_alt_format)
        assert len(result) == 2
        assert result[0]["name"] == "Python"
        assert result[0]["endorsements"] == 50

    def test_result_structure(self, linkedin_with_endorsements):
        result = get_endorsement_weighted_skills(linkedin_with_endorsements, top_n=1)
        entry = result[0]
        assert "name" in entry
        assert "endorsements" in entry
        assert "weight" in entry
        assert isinstance(entry["endorsements"], int)
        assert isinstance(entry["weight"], float)


# ---------------------------------------------------------------------------
# weighted_skill_match tests
# ---------------------------------------------------------------------------
class TestWeightedSkillMatch:
    def test_exact_match(self, linkedin_with_endorsements):
        result = weighted_skill_match(
            ["Python", "AWS", "Docker"],
            ["Python", "AWS", "Docker"],
            linkedin_with_endorsements,
        )
        assert result["weighted_score"] == 100
        assert len(result["matching_skills"]) == 3
        assert len(result["missing_skills"]) == 0

    def test_partial_match(self, linkedin_with_endorsements):
        result = weighted_skill_match(
            ["Python"],
            ["Python", "Rust", "Elixir"],
            linkedin_with_endorsements,
        )
        assert 0 < result["weighted_score"] < 100
        assert len(result["matching_skills"]) == 1
        assert len(result["missing_skills"]) == 2

    def test_no_match(self):
        result = weighted_skill_match(
            ["Python"],
            ["Haskell", "Erlang"],
        )
        assert result["weighted_score"] == 0
        assert len(result["matching_skills"]) == 0

    def test_empty_inputs(self):
        result = weighted_skill_match([], [], None)
        assert result["weighted_score"] == 0
        assert result["total_job_keywords"] == 0

    def test_case_insensitive(self, linkedin_with_endorsements):
        result = weighted_skill_match(
            ["python", "aws"],
            ["Python", "AWS"],
            linkedin_with_endorsements,
        )
        assert len(result["matching_skills"]) == 2

    def test_substring_matching(self):
        """Skills longer than 3 chars match as substrings."""
        result = weighted_skill_match(
            ["microservices"],  # resume has this
            ["microservice"],  # JD has shorter form
        )
        # "microservice" in "microservices" — substring match
        assert len(result["matching_skills"]) == 1

    def test_endorsement_weight_in_score(self, linkedin_with_endorsements):
        """Higher endorsed matching skill contributes more to score."""
        # Python (117 endorsements) vs Go (0)
        result_python = weighted_skill_match(
            ["Python"], ["Python", "Rust"], linkedin_with_endorsements
        )
        result_go = weighted_skill_match(["Go"], ["Go", "Rust"], linkedin_with_endorsements)
        # Python match should score higher due to endorsement weight
        assert result_python["weighted_score"] >= result_go["weighted_score"]

    def test_missing_skills_priority(self, linkedin_with_endorsements):
        result = weighted_skill_match([], ["Python", "Rust"], linkedin_with_endorsements)
        python_missing = next(s for s in result["missing_skills"] if s["keyword"] == "Python")
        # Python has >10 endorsements → high priority
        assert python_missing["priority"] == "high"

    def test_no_linkedin_profile(self):
        result = weighted_skill_match(["Python"], ["Python"])
        assert len(result["matching_skills"]) == 1
        assert result["weighted_score"] > 0


# ---------------------------------------------------------------------------
# analyze_skills_gap tests (monkeypatched NLP functions)
# ---------------------------------------------------------------------------
class TestAnalyzeSkillsGap:
    def _make_side_effect(self, *returns):
        """Create a callable that returns successive values on each call."""
        calls = iter(returns)

        def _fn(*args, **kwargs):
            return next(calls)

        return _fn

    def test_basic_gap_analysis(self, monkeypatch):
        monkeypatch.setattr(
            skills_optimizer,
            "extract_skill_phrases",
            self._make_side_effect(["Python", "AWS", "Docker"], ["Python", "AWS", "Docker"]),
        )
        monkeypatch.setattr(skills_optimizer, "extract_keywords", lambda *a, **kw: [])
        resume = {"text": "Python developer with AWS experience and Docker", "skills": ["Python"]}
        result = analyze_skills_gap(resume, "Need Python, AWS, Docker, Rust")
        assert "skills_already_shown" in result
        assert "skills_to_emphasize" in result
        assert "skills_to_acquire" in result
        assert "coverage_percent" in result
        assert "gap_summary" in result

    def test_coverage_calculation(self, monkeypatch):
        monkeypatch.setattr(
            skills_optimizer,
            "extract_skill_phrases",
            self._make_side_effect(["Python", "AWS"], ["Python", "AWS"]),
        )
        monkeypatch.setattr(skills_optimizer, "extract_keywords", lambda *a, **kw: [])
        resume = {"text": "Python and AWS expert", "skills": ["Python", "AWS"]}
        result = analyze_skills_gap(resume, "Python and AWS required")
        assert result["coverage_percent"] > 0
        shown = result["gap_summary"]["shown"]
        can_add = result["gap_summary"]["can_add"]
        total = result["total_job_keywords"]
        assert shown + can_add + result["gap_summary"]["need_to_learn"] == total

    def test_linkedin_skills_classified_as_emphasize(self, monkeypatch):
        monkeypatch.setattr(
            skills_optimizer,
            "extract_skill_phrases",
            self._make_side_effect(["Python", "Java", "Kubernetes"], ["Python"]),
        )
        monkeypatch.setattr(skills_optimizer, "extract_keywords", lambda *a, **kw: [])
        resume = {"text": "I use Python", "skills": ["Python"]}
        linkedin = {"skills": [{"name": "Java", "endorsements": 30}]}
        result = analyze_skills_gap(resume, "Python Java Kubernetes", linkedin)
        emphasize_names = [s["skill"] for s in result["skills_to_emphasize"]]
        assert "Java" in emphasize_names

    def test_project_evidence_classified_as_emphasize(self, monkeypatch):
        monkeypatch.setattr(
            skills_optimizer,
            "extract_skill_phrases",
            self._make_side_effect(["Python", "Terraform"], ["Python"]),
        )
        monkeypatch.setattr(skills_optimizer, "extract_keywords", lambda *a, **kw: [])
        resume = {"text": "I use Python", "skills": ["Python"]}
        evidence = [{"source": "Client: OPI", "detail": "Used in infra", "skills": ["Terraform"]}]
        result = analyze_skills_gap(
            resume,
            "Python Terraform",
            project_journey_evidence=evidence,
        )
        emphasize_names = [s["skill"] for s in result["skills_to_emphasize"]]
        assert "Terraform" in emphasize_names

    def test_deep_profile_expert_classified_as_emphasize(self, monkeypatch):
        monkeypatch.setattr(
            skills_optimizer,
            "extract_skill_phrases",
            self._make_side_effect(["Python", "GraphQL"], ["Python"]),
        )
        monkeypatch.setattr(skills_optimizer, "extract_keywords", lambda *a, **kw: [])
        resume = {"text": "I use Python", "skills": ["Python"]}
        deep = {
            "technology_mastery": [
                {"name": "GraphQL", "proficiency": "expert", "contexts": ["API layer"]}
            ],
            "business_impacts": [],
        }
        result = analyze_skills_gap(resume, "Python GraphQL", deep_profile=deep)
        emphasize_names = [s["skill"] for s in result["skills_to_emphasize"]]
        assert "GraphQL" in emphasize_names

    def test_unknown_skill_classified_as_acquire(self, monkeypatch):
        monkeypatch.setattr(
            skills_optimizer,
            "extract_skill_phrases",
            self._make_side_effect(["Rust"], []),
        )
        monkeypatch.setattr(skills_optimizer, "extract_keywords", lambda *a, **kw: [])
        resume = {"text": "Python developer", "skills": ["Python"]}
        result = analyze_skills_gap(resume, "Need Rust expertise")
        acquire_names = [s["skill"] for s in result["skills_to_acquire"]]
        assert "Rust" in acquire_names

    def test_empty_resume_empty_jd(self, monkeypatch):
        monkeypatch.setattr(skills_optimizer, "extract_skill_phrases", lambda *a, **kw: [])
        monkeypatch.setattr(skills_optimizer, "extract_keywords", lambda *a, **kw: [])
        result = analyze_skills_gap({"text": "", "skills": []}, "")
        assert result["coverage_percent"] == 0
        assert result["total_job_keywords"] == 0
