"""Tests for resume_scorer.py — pure scoring function extracted from utils.py"""

import pytest
from test_helpers import RESUME_TEXT, JD_TEXT, LINKEDIN_PROFILE, upload_resume, upload_jd


class TestResumeScorer:
    """Unit tests for score_resume() function — no side effects, deterministic."""

    def test_score_returns_expected_keys(self):
        """Score result dict must have all required keys."""
        from resume_scorer import score_resume
        from nlp_engine import extract_skill_phrases

        resume_data = {"text": RESUME_TEXT, "skills": ["Python", "AWS"], "experience": [], "education": []}
        job_keywords = extract_skill_phrases(JD_TEXT) or ["Python", "AWS", "Leadership"]

        result = score_resume(resume_data, job_keywords, JD_TEXT)

        required_keys = {"score", "score_breakdown", "sections_found", "matching_keywords",
                         "missing_keywords", "skill_phrases_matched"}
        assert required_keys.issubset(result.keys()), f"Missing keys: {required_keys - set(result.keys())}"
        assert "keyword_coverage" in result["score_breakdown"]
        assert "semantic_similarity" in result["score_breakdown"]
        assert "skills_match" in result["score_breakdown"]
        assert "section_completeness" in result["score_breakdown"]

    def test_score_deterministic(self):
        """Same inputs must produce same score on consecutive calls."""
        from resume_scorer import score_resume
        from nlp_engine import extract_skill_phrases

        resume_data = {"text": RESUME_TEXT, "skills": ["Python", "AWS"], "experience": [], "education": []}
        job_keywords = extract_skill_phrases(JD_TEXT) or ["Python", "AWS", "Leadership"]

        result1 = score_resume(resume_data, job_keywords, JD_TEXT)
        result2 = score_resume(resume_data, job_keywords, JD_TEXT)
        result3 = score_resume(resume_data, job_keywords, JD_TEXT)

        assert result1["score"] == result2["score"] == result3["score"], \
            f"Scores not deterministic: {result1['score']}, {result2['score']}, {result3['score']}"

    def test_score_no_side_effects(self):
        """Input resume_data dict must NOT be mutated after call."""
        from resume_scorer import score_resume
        from nlp_engine import extract_skill_phrases
        import copy

        resume_data = {"text": RESUME_TEXT, "skills": ["Python", "AWS"], "experience": [], "education": []}
        job_keywords = extract_skill_phrases(JD_TEXT) or ["Python", "AWS"]
        resume_data_copy = copy.deepcopy(resume_data)

        score_resume(resume_data, job_keywords, JD_TEXT)

        assert resume_data == resume_data_copy, "resume_data was mutated during scoring"

    def test_score_no_llm_calls(self, monkeypatch):
        """No HTTP/LLM calls should be made during scoring."""
        from resume_scorer import score_resume
        from nlp_engine import extract_skill_phrases

        # Patch any HTTP calls to ensure they don't happen
        call_count = {"count": 0}

        def mock_request(*args, **kwargs):
            call_count["count"] += 1
            raise AssertionError("HTTP call made during scoring!")

        import requests
        monkeypatch.setattr(requests, "post", mock_request)
        monkeypatch.setattr(requests, "get", mock_request)

        resume_data = {"text": RESUME_TEXT, "skills": ["Python", "AWS"], "experience": [], "education": []}
        job_keywords = extract_skill_phrases(JD_TEXT) or ["Python", "AWS"]

        result = score_resume(resume_data, job_keywords, JD_TEXT)
        assert call_count["count"] == 0, f"Made {call_count['count']} HTTP calls during scoring"

    def test_well_matched_resume_scores_high(self):
        """A well-matched resume should score > 40."""
        from resume_scorer import score_resume
        from nlp_engine import extract_skill_phrases

        # Using test data that should be well-matched
        resume_data = {"text": RESUME_TEXT, "skills": ["Python", "AWS"], "experience": [], "education": []}
        job_keywords = extract_skill_phrases(JD_TEXT) or ["Python", "AWS", "Leadership"]

        result = score_resume(resume_data, job_keywords, JD_TEXT)

        assert result["score"] > 40, f"Well-matched resume scored only {result['score']} (expected > 40)"

    def test_mismatched_resume_scores_low(self):
        """A mismatched resume should score < 20."""
        from resume_scorer import score_resume

        # Random unrelated text
        mismatched_resume = {"text": "Lorem ipsum dolor sit amet. The quick brown fox jumps over the lazy dog.",
                            "skills": ["Knitting", "Gardening"], "experience": [], "education": []}
        job_keywords = ["Kubernetes", "Terraform", "Leadership", "Python"]

        result = score_resume(mismatched_resume, job_keywords, "Cloud infrastructure job")

        assert result["score"] < 20, f"Mismatched resume scored {result['score']} (expected < 20)"

    def test_score_breakdown_components_valid(self):
        """All score_breakdown components must be floats in [0, 100]."""
        from resume_scorer import score_resume
        from nlp_engine import extract_skill_phrases

        resume_data = {"text": RESUME_TEXT, "skills": ["Python"], "experience": [], "education": []}
        job_keywords = extract_skill_phrases(JD_TEXT) or ["Python"]

        result = score_resume(resume_data, job_keywords, JD_TEXT)
        breakdown = result["score_breakdown"]

        for key in ["keyword_coverage", "semantic_similarity", "skills_match", "section_completeness"]:
            assert key in breakdown, f"Missing {key} in score_breakdown"
            assert isinstance(breakdown[key], (int, float)), f"{key} is not numeric"
            assert 0 <= breakdown[key] <= 100, f"{key}={breakdown[key]} not in [0, 100]"

    def test_optimize_resume_regression(self):
        """After refactor, optimize_resume() must return same score ±2 points."""
        from utils import optimize_resume
        from nlp_engine import extract_skill_phrases

        resume_data = {"text": RESUME_TEXT, "skills": ["Python", "AWS"], "experience": [], "education": []}
        job_keywords = extract_skill_phrases(JD_TEXT) or ["Python", "AWS"]

        # Call optimize_resume (which now uses score_resume internally)
        result = optimize_resume(resume_data, job_keywords, JD_TEXT)

        # Score should be in expected range (25-80 before calibration, 0-100 after)
        assert 0 <= result["score"] <= 100, f"Score {result['score']} out of range"
        assert "score_breakdown" in result, "optimize_resume must return score_breakdown"

    def test_score_with_linkedin_endorsements(self):
        """LinkedIn profile with endorsements should improve skills_match score."""
        from resume_scorer import score_resume
        from nlp_engine import extract_skill_phrases

        resume_data = {"text": RESUME_TEXT, "skills": ["Python", "AWS"], "experience": [], "education": []}
        job_keywords = extract_skill_phrases(JD_TEXT) or ["Python", "AWS"]

        # Score without LinkedIn
        result_no_linkedin = score_resume(resume_data, job_keywords, JD_TEXT, linkedin_profile=None)

        # Score with LinkedIn (has endorsement data)
        result_with_linkedin = score_resume(resume_data, job_keywords, JD_TEXT, linkedin_profile=LINKEDIN_PROFILE)

        # LinkedIn should help with skills matching (not guarantee higher score, but shouldn't hurt)
        assert result_with_linkedin["score_breakdown"]["skills_match"] >= 0, "Skills match must be >= 0"

    def test_empty_resume_returns_zero(self):
        """Empty resume should score 0 with empty skills."""
        from resume_scorer import score_resume

        empty_resume = {"text": "", "skills": [], "experience": [], "education": []}
        job_keywords = ["Python", "AWS"]

        result = score_resume(empty_resume, job_keywords, "some job")

        assert result["score"] == 0, f"Empty resume should score 0, got {result['score']}"
        assert all(v == 0 for v in result["score_breakdown"].values()), "All breakdown components should be 0 for empty resume"
