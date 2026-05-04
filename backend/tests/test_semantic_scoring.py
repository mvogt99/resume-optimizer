"""TDD tests for LLM-based semantic alignment scoring (Fix C).

Tests verify:
1. score_semantic_alignment() returns float 0-100
2. Clearly relevant text scores higher than irrelevant text
3. Falls back to chunked cosine similarity when LLM unavailable
4. resume_scorer uses score_semantic_alignment for the semantic_similarity signal

Run from backend/: pytest tests/test_semantic_scoring.py -v
"""
import os
import sys
from unittest.mock import patch

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

JD_TEXT = (
    "Principal Data Platform Architect to design event-driven near-real-time data ecosystems. "
    "Requirements: Kafka, design stewardship, canonical data modeling, data governance, "
    "cloud-native architecture (AWS/Azure/GCP), healthcare domain expertise, HIPAA compliance."
)

RELEVANT_RESUME = (
    "Principal Data Platform Architect with 20+ years designing event-driven near-real-time "
    "data ecosystems on AWS, Azure, and GCP. Expert in Kafka streaming, canonical data modeling, "
    "data governance frameworks, and HIPAA compliance across healthcare domains. "
    "Proven design stewardship for complex architecture decisions."
)

IRRELEVANT_RESUME = (
    "Marketing Manager with 5 years experience managing social media campaigns, "
    "brand strategy, and influencer partnerships. Proficient in Instagram, TikTok, and Canva. "
    "Led a team of 3 content creators."
)


class TestScoreSemanticAlignment:
    def test_returns_float_0_to_100(self):
        from nlp_engine import score_semantic_alignment
        score = score_semantic_alignment(RELEVANT_RESUME, JD_TEXT)
        assert isinstance(score, float)
        assert 0.0 <= score <= 100.0

    def test_relevant_resume_scores_higher_than_irrelevant(self):
        from nlp_engine import score_semantic_alignment
        relevant_score = score_semantic_alignment(RELEVANT_RESUME, JD_TEXT)
        irrelevant_score = score_semantic_alignment(IRRELEVANT_RESUME, JD_TEXT)
        assert relevant_score > irrelevant_score, (
            f"Relevant ({relevant_score:.1f}) should beat irrelevant ({irrelevant_score:.1f})"
        )

    def test_empty_resume_returns_zero(self):
        from nlp_engine import score_semantic_alignment
        score = score_semantic_alignment("", JD_TEXT)
        assert score == 0.0

    def test_empty_jd_returns_zero(self):
        from nlp_engine import score_semantic_alignment
        score = score_semantic_alignment(RELEVANT_RESUME, "")
        assert score == 0.0

    def test_llm_fallback_when_unavailable(self):
        """When LLM call returns None, falls back to chunked cosine similarity (still 0-100).
        Cosine of the highly-relevant resume vs JD should be meaningfully > 0."""
        from nlp_engine import score_semantic_alignment
        with patch("nlp_similarity._call_llm_for_semantic", return_value=None):
            score = score_semantic_alignment(RELEVANT_RESUME, JD_TEXT)
            assert isinstance(score, float)
            assert 0.0 <= score <= 100.0
            # Cosine similarity of closely related texts must be > 0; catches fallback broken
            assert score > 5.0, f"Cosine fallback returned near-zero ({score:.2f}) — not computing similarity"

    def test_llm_result_used_when_available(self):
        """When LLM returns a valid score, that value is used (not cosine)."""
        from nlp_engine import score_semantic_alignment
        with patch("nlp_similarity._call_llm_for_semantic", return_value=88.5):
            score = score_semantic_alignment(RELEVANT_RESUME, JD_TEXT)
            assert score == 88.5

    def test_llm_out_of_range_clamped(self):
        """LLM hallucinating a value > 100 or < 0 is clamped."""
        from nlp_engine import score_semantic_alignment
        with patch("nlp_similarity._call_llm_for_semantic", return_value=150.0):
            score = score_semantic_alignment(RELEVANT_RESUME, JD_TEXT)
            assert score <= 100.0
        with patch("nlp_similarity._call_llm_for_semantic", return_value=-5.0):
            score = score_semantic_alignment(RELEVANT_RESUME, JD_TEXT)
            assert score >= 0.0


class TestResumeScorerUsesSemantic:
    def test_score_resume_semantic_comes_from_score_semantic_alignment(self, app):
        """resume_scorer.score_resume() must call score_semantic_alignment for semantic signal."""
        with app.app_context():
            from resume_scorer import score_resume
            with patch("resume_scorer.score_semantic_alignment", return_value=82.0) as mock_fn:
                resume_data = {"text": RELEVANT_RESUME, "skills": [], "experience": [], "education": []}
                result = score_resume(resume_data, ["kafka", "data governance"], job_text=JD_TEXT)
                mock_fn.assert_called_once()
                # semantic_similarity in breakdown should reflect the mocked value (scaled to %)
                assert result["score_breakdown"]["semantic_similarity"] == 82.0
