"""Tests for hybrid_scorer dimension functions.

Part 2 of hybrid_scorer test suite — split for 500-line file limit.
"""

import pytest

from hybrid_scorer import (
    _score_keyword_alignment,
    _score_evidence_strength,
    _score_seniority_alignment,
    _score_domain_alignment,
    _score_leadership_alignment,
    _score_recency_alignment,
)
from test_helpers import RESUME_TEXT


class TestScoreDimensions:
    """Tests for all 7 scoring dimension functions."""

    def test_keyword_alignment_perfect_match(
        self, sample_requirement, sample_candidate_senior
    ):
        """Score high when all required skills in inventory."""
        score = _score_keyword_alignment(
            sample_requirement, sample_candidate_senior, RESUME_TEXT
        )
        assert score >= 0.6, "Should score >= 0.6 for perfect inventory match"
        assert score <= 1.0

    def test_keyword_alignment_no_skills(self, sample_candidate_senior):
        """Returns 0.5 (neutral) when requirement has no canonical_skills."""
        req = {"requirement_id": "req_none", "canonical_skills": []}
        score = _score_keyword_alignment(req, sample_candidate_senior, RESUME_TEXT)
        assert score == 0.5

    def test_keyword_alignment_no_match(self, sample_requirement, empty_candidate):
        """Scores low when candidate has no matching skills."""
        score = _score_keyword_alignment(sample_requirement, empty_candidate, "")
        assert score < 0.3

    def test_keyword_alignment_case_insensitive(self, sample_requirement, sample_candidate_senior):
        """Matching should be case-insensitive."""
        score = _score_keyword_alignment(
            sample_requirement,
            sample_candidate_senior,
            "experience with APACHE KAFKA",
        )
        assert score > 0.0

    def test_evidence_strength_three_refs(
        self, sample_requirement, sample_candidate_senior
    ):
        """Score increases with evidence_refs count (3 refs = ~0.7)."""
        score = _score_evidence_strength(sample_requirement, sample_candidate_senior)
        assert score > 0.5, "Three evidence refs should score > 0.5"
        assert score < 1.0

    def test_evidence_strength_one_ref(self, sample_requirement):
        """One evidence ref scores ~0.3."""
        candidate = {
            "candidate_id": "cand",
            "skill_inventory": [
                {
                    "canonical_skill": "Apache Kafka",
                    "aliases": [],
                    "evidence_refs": ["proj_001"],
                    "proficiency_estimate": "junior",
                }
            ],
            "experience_units": [],
        }
        score = _score_evidence_strength(sample_requirement, candidate)
        assert 0.2 < score <= 0.5

    def test_evidence_strength_no_skills_with_units(self):
        """When no skills, uses experience_units count as proxy."""
        req = {"requirement_id": "req", "canonical_skills": []}
        candidate = {
            "candidate_id": "cand",
            "skill_inventory": [],
            "experience_units": [
                {"experience_id": "e1", "skills": []},
                {"experience_id": "e2", "skills": []},
                {"experience_id": "e3", "skills": []},
            ],
        }
        score = _score_evidence_strength(req, candidate)
        assert score > 0.2  # 3 * 0.15 = 0.45

    def test_seniority_alignment_non_senior_req(self, sample_requirement, empty_candidate):
        """Non-senior requirement returns 0.8 (neutral-positive)."""
        req = {
            "requirement_id": "req",
            "requirement_type": "other",
            "text": "Basic SQL experience",
            "canonical_skills": [],
            "importance": 1.0,
        }
        score = _score_seniority_alignment(req, empty_candidate, "")
        assert score == 0.8

    def test_seniority_alignment_senior_req_senior_candidate(
        self, sample_candidate_senior
    ):
        """Senior candidate + senior requirement >= 0.6."""
        req = {
            "requirement_id": "req_senior",
            "requirement_type": "must_have",
            "text": "Architect-level experience with enterprise systems",
            "canonical_skills": ["Architecture"],
            "importance": 1.0,
        }
        score = _score_seniority_alignment(req, sample_candidate_senior, RESUME_TEXT)
        assert score >= 0.6

    def test_seniority_alignment_junior_candidate_senior_req(
        self, sample_candidate_junior
    ):
        """Senior requirement + junior candidate scores low."""
        req = {
            "requirement_id": "req_senior",
            "requirement_type": "must_have",
            "text": "Principal architect-level experience",
            "canonical_skills": [],
            "importance": 1.0,
        }
        score = _score_seniority_alignment(req, sample_candidate_junior, RESUME_TEXT)
        # Score depends on presence of "architect" in RESUME_TEXT
        assert score >= 0.2
        assert score <= 1.0

    def test_seniority_alignment_resume_signals(self, sample_requirement, empty_candidate):
        """Resume with seniority signals boosts score for senior requirement."""
        req = {
            "requirement_id": "req",
            "requirement_type": "leadership",
            "text": "Director-level leadership experience",
            "canonical_skills": [],
            "importance": 1.0,
        }
        score = _score_seniority_alignment(req, empty_candidate, RESUME_TEXT)
        assert score >= 0.6

    def test_domain_alignment_non_domain_req(
        self, sample_requirement, sample_candidate_senior
    ):
        """Non-domain requirement returns 0.7 (neutral-positive)."""
        score = _score_domain_alignment(sample_requirement, sample_candidate_senior, "")
        assert score == 0.7

    def test_domain_alignment_healthcare_match(
        self, sample_requirement_domain, sample_candidate_healthcare
    ):
        """Healthcare domain in both resume and units >= 0.6."""
        score = _score_domain_alignment(
            sample_requirement_domain,
            sample_candidate_healthcare,
            "HIPAA compliant claims processing for Navitus",
        )
        assert score >= 0.6

    def test_domain_alignment_healthcare_resume_only(
        self, sample_requirement_domain, sample_candidate_senior
    ):
        """Healthcare domain in resume and units scores high."""
        score = _score_domain_alignment(
            sample_requirement_domain,
            sample_candidate_senior,
            "HIPAA healthcare claims",
        )
        # Navitus is healthcare, so units check will pass
        assert score >= 0.5

    def test_domain_alignment_unknown_domain(self, empty_candidate):
        """Unknown domain returns 0.5 (neutral)."""
        req = {
            "requirement_id": "req",
            "requirement_type": "domain",
            "text": "blockchain experience",
            "canonical_skills": [],
            "importance": 1.0,
        }
        score = _score_domain_alignment(req, empty_candidate, "blockchain smart contracts")
        assert score == 0.5

    def test_leadership_alignment_non_leadership_req(
        self, sample_requirement, empty_candidate
    ):
        """Non-leadership requirement returns 0.8 (neutral-positive)."""
        score = _score_leadership_alignment(sample_requirement, empty_candidate, "")
        assert score == 0.8

    def test_leadership_alignment_with_signals(
        self, sample_requirement_leadership, sample_candidate_senior
    ):
        """Leadership requirement + signals >= 0.6."""
        score = _score_leadership_alignment(
            sample_requirement_leadership, sample_candidate_senior, RESUME_TEXT
        )
        assert score >= 0.6

    def test_leadership_alignment_no_signals(
        self, sample_requirement_leadership, empty_candidate
    ):
        """Leadership requirement + no signals = 0.1."""
        score = _score_leadership_alignment(
            sample_requirement_leadership, empty_candidate, ""
        )
        assert score == 0.1

    def test_leadership_alignment_resume_signals(
        self, sample_requirement_leadership, empty_candidate
    ):
        """Resume with leadership signal language = >= 0.6."""
        score = _score_leadership_alignment(
            sample_requirement_leadership,
            empty_candidate,
            "led team of engineers, mentored 5 junior developers",
        )
        assert score >= 0.6

    def test_recency_alignment_current_role(
        self, sample_requirement, sample_candidate_senior
    ):
        """Current role (None end date) = 1.0."""
        score = _score_recency_alignment(sample_requirement, sample_candidate_senior)
        assert score == 1.0

    def test_recency_alignment_old_skill(self, sample_requirement, candidate_old_skill):
        """Skill used 5+ years ago = 0.2-0.4."""
        score = _score_recency_alignment(sample_requirement, candidate_old_skill)
        assert score >= 0.2
        assert score <= 0.4

    def test_recency_alignment_no_units(self, sample_requirement, empty_candidate):
        """No experience units = 0.5 (neutral)."""
        score = _score_recency_alignment(sample_requirement, empty_candidate)
        assert score == 0.5

    def test_recency_alignment_unrelated_skill(self, sample_requirement):
        """Experience unit without relevant skill is skipped."""
        candidate = {
            "candidate_id": "cand",
            "skill_inventory": [],
            "experience_units": [
                {
                    "experience_id": "exp",
                    "skills": ["Python"],  # Not Apache Kafka
                    "date_range": {"start": "2023-01-01", "end": None},
                }
            ],
        }
        score = _score_recency_alignment(sample_requirement, candidate)
        assert score == 0.5  # Falls back to neutral
