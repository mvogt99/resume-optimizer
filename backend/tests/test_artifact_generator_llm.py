"""Test suite for artifact_generator.py LLM-dependent generators.

Tests cover:
  - generate_tailored_resume
  - generate_cover_letter
  - generate_interview_seeds
  - generate_linkedin_summary
  - generate_one_pager
"""

import pytest
from unittest.mock import patch, MagicMock
import artifact_generator


# ===== FIXTURES =====

@pytest.fixture
def candidate_profile():
    """Standard candidate profile fixture."""
    return {
        "candidate_id": "test_candidate_123",
        "target_role_families": ["Data Engineering", "ML Ops"],
        "branding_summary": "Experienced data engineer with 10 years in cloud.",
        "skill_inventory": [
            {"canonical_skill": "Python", "aliases": ["python3"], "evidence_refs": ["proj1"]},
            {"canonical_skill": "AWS", "aliases": ["Amazon Web Services"], "evidence_refs": ["proj1"]},
            {"canonical_skill": "Kubernetes", "aliases": ["k8s"], "evidence_refs": ["proj3"]},
        ],
        "experience_units": [
            {"company": "Acme Corp", "title": "Senior Data Engineer", "skills": ["Python", "AWS"]},
        ],
    }


@pytest.fixture
def requirements():
    """Standard requirements list fixture."""
    return [
        {
            "requirement_id": "req_001",
            "requirement_type": "technical",
            "text": "5+ years Python experience",
            "importance": 0.95,
            "canonical_skills": ["Python"],
        },
        {
            "requirement_id": "req_002",
            "requirement_type": "technical",
            "text": "AWS cloud services",
            "importance": 0.85,
            "canonical_skills": ["AWS", "S3"],
        },
    ]


@pytest.fixture
def scores():
    """Standard scores list fixture."""
    return [
        {"requirement_id": "req_001", "composite_score": 0.92},
        {"requirement_id": "req_002", "composite_score": 0.78},
    ]


@pytest.fixture
def gaps():
    """Standard gaps list fixture."""
    return [
        {
            "gap_id": "g1",
            "severity": "high",
            "gap_type": "missing_experience",
            "description": "Lacks ML inference optimization",
            "recommended_action": "Highlight ML optimization work",
        },
    ]


@pytest.fixture
def rewrite_targets():
    """Standard rewrite targets fixture."""
    return [
        {
            "target_id": "t1",
            "priority": 1,
            "gap_type": "missing_experience",
            "suggested_action": "Add ML inference optimization bullet",
            "rewrite_template": "Optimized ML serving latency",
        },
    ]


@pytest.fixture
def resume_text():
    """Standard resume text fixture."""
    return "Senior Data Engineer with Python and AWS experience at Acme Corp. Built data pipelines."


# ===== TEST GENERATE TAILORED RESUME =====

class TestGenerateTailoredResume:
    """Test generate_tailored_resume (LLM-dependent)."""

    def test_tailored_resume_llm_unavailable(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_tailored_resume returns error when call_llm_quality is None."""
        with patch("artifact_generator.call_llm_quality", None):
            result = artifact_generator.generate_tailored_resume(
                candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
            )
            assert result["error"] == "LLM unavailable"
            assert result["content"] == ""

    def test_tailored_resume_with_llm(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_tailored_resume calls LLM and returns content."""
        with patch("artifact_generator.call_llm_quality") as mock_llm:
            mock_llm.return_value = "Tailored resume content here."
            result = artifact_generator.generate_tailored_resume(
                candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
            )
            assert result["content"] == "Tailored resume content here."
            assert result["error"] == ""
            mock_llm.assert_called_once()

    def test_tailored_resume_llm_called_with_generation_task(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_tailored_resume calls LLM with task_type='generation'."""
        with patch("artifact_generator.call_llm_quality") as mock_llm:
            mock_llm.return_value = "content"
            artifact_generator.generate_tailored_resume(
                candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
            )
            call_kwargs = mock_llm.call_args[1]
            assert call_kwargs.get("task_type") == "generation"

    def test_tailored_resume_handles_llm_exception(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_tailored_resume catches LLM exception and returns error."""
        with patch("artifact_generator.call_llm_quality") as mock_llm:
            mock_llm.side_effect = Exception("LLM connection failed")
            result = artifact_generator.generate_tailored_resume(
                candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
            )
            assert "LLM connection failed" in result["error"]
            assert result["content"] == ""

    def test_tailored_resume_artifact_type_correct(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_tailored_resume artifact_type is 'tailored_resume'."""
        with patch("artifact_generator.call_llm_quality", MagicMock(return_value="content")):
            result = artifact_generator.generate_tailored_resume(
                candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
            )
            assert result["artifact_type"] == "tailored_resume"

    def test_tailored_resume_includes_rewrite_targets(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_tailored_resume includes rewrite targets in prompt."""
        with patch("artifact_generator.call_llm_quality") as mock_llm:
            mock_llm.return_value = "content"
            artifact_generator.generate_tailored_resume(
                candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
            )
            prompt = mock_llm.call_args[0][0]
            assert "Add ML inference optimization bullet" in prompt


# ===== TEST GENERATE COVER LETTER =====

class TestGenerateCoverLetter:
    """Test generate_cover_letter (LLM-dependent)."""

    def test_cover_letter_llm_unavailable(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_cover_letter returns error when LLM unavailable."""
        with patch("artifact_generator.call_llm_quality", None):
            result = artifact_generator.generate_cover_letter(
                candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
            )
            assert result["error"] == "LLM unavailable"

    def test_cover_letter_with_llm(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_cover_letter generates cover letter via LLM."""
        with patch("artifact_generator.call_llm_quality") as mock_llm:
            mock_llm.return_value = "Dear Hiring Manager..."
            result = artifact_generator.generate_cover_letter(
                candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
            )
            assert "Dear Hiring Manager" in result["content"]
            assert result["error"] == ""

    def test_cover_letter_artifact_type_correct(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_cover_letter artifact_type is 'cover_letter'."""
        with patch("artifact_generator.call_llm_quality", MagicMock(return_value="content")):
            result = artifact_generator.generate_cover_letter(
                candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
            )
            assert result["artifact_type"] == "cover_letter"

    def test_cover_letter_includes_top_skills(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_cover_letter mentions top skills in prompt."""
        with patch("artifact_generator.call_llm_quality") as mock_llm:
            mock_llm.return_value = "content"
            artifact_generator.generate_cover_letter(
                candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
            )
            prompt = mock_llm.call_args[0][0]
            assert "Python" in prompt
            assert "AWS" in prompt

    def test_cover_letter_llm_exception_handling(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_cover_letter handles LLM exception."""
        with patch("artifact_generator.call_llm_quality") as mock_llm:
            mock_llm.side_effect = ValueError("Invalid prompt")
            result = artifact_generator.generate_cover_letter(
                candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
            )
            assert "Invalid prompt" in result["error"]


# ===== TEST GENERATE INTERVIEW SEEDS =====

class TestGenerateInterviewSeeds:
    """Test generate_interview_seeds (LLM-dependent)."""

    def test_interview_seeds_llm_unavailable(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_interview_seeds returns error when LLM unavailable."""
        with patch("artifact_generator.call_llm_quality", None):
            result = artifact_generator.generate_interview_seeds(
                candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
            )
            assert result["error"] == "LLM unavailable"

    def test_interview_seeds_with_llm(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_interview_seeds generates STAR bullets via LLM."""
        with patch("artifact_generator.call_llm_quality") as mock_llm:
            mock_llm.return_value = "STAR bullet 1...\nSTAR bullet 2..."
            result = artifact_generator.generate_interview_seeds(
                candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
            )
            assert "STAR bullet" in result["content"]

    def test_interview_seeds_artifact_type_correct(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_interview_seeds artifact_type is 'interview_seeds'."""
        with patch("artifact_generator.call_llm_quality", MagicMock(return_value="content")):
            result = artifact_generator.generate_interview_seeds(
                candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
            )
            assert result["artifact_type"] == "interview_seeds"

    def test_interview_seeds_uses_star_format_in_prompt(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_interview_seeds prompt mentions STAR format."""
        with patch("artifact_generator.call_llm_quality") as mock_llm:
            mock_llm.return_value = "content"
            artifact_generator.generate_interview_seeds(
                candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
            )
            prompt = mock_llm.call_args[0][0]
            assert "STAR" in prompt


# ===== TEST GENERATE LINKEDIN SUMMARY =====

class TestGenerateLinkedInSummary:
    """Test generate_linkedin_summary (LLM-dependent)."""

    def test_linkedin_summary_llm_unavailable(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_linkedin_summary returns error when LLM unavailable."""
        with patch("artifact_generator.call_llm_quality", None):
            result = artifact_generator.generate_linkedin_summary(
                candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
            )
            assert result["error"] == "LLM unavailable"

    def test_linkedin_summary_with_llm(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_linkedin_summary generates LinkedIn About via LLM."""
        with patch("artifact_generator.call_llm_quality") as mock_llm:
            mock_llm.return_value = "I am a passionate data engineer..."
            result = artifact_generator.generate_linkedin_summary(
                candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
            )
            assert "passionate data engineer" in result["content"]

    def test_linkedin_summary_artifact_type_correct(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_linkedin_summary artifact_type is 'linkedin_summary'."""
        with patch("artifact_generator.call_llm_quality", MagicMock(return_value="content")):
            result = artifact_generator.generate_linkedin_summary(
                candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
            )
            assert result["artifact_type"] == "linkedin_summary"

    def test_linkedin_summary_includes_branding_summary(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_linkedin_summary includes existing branding in prompt."""
        with patch("artifact_generator.call_llm_quality") as mock_llm:
            mock_llm.return_value = "content"
            artifact_generator.generate_linkedin_summary(
                candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
            )
            prompt = mock_llm.call_args[0][0]
            assert "Experienced data engineer" in prompt


# ===== TEST GENERATE ONE PAGER =====

class TestGenerateOnePager:
    """Test generate_one_pager (LLM-dependent)."""

    def test_one_pager_llm_unavailable(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_one_pager returns error when LLM unavailable."""
        with patch("artifact_generator.call_llm_quality", None):
            result = artifact_generator.generate_one_pager(
                candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
            )
            assert result["error"] == "LLM unavailable"

    def test_one_pager_with_llm(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_one_pager generates one-pager via LLM."""
        with patch("artifact_generator.call_llm_quality") as mock_llm:
            mock_llm.return_value = "Value Proposition...\nCapabilities...\nHighlights..."
            result = artifact_generator.generate_one_pager(
                candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
            )
            assert "Value Proposition" in result["content"]

    def test_one_pager_artifact_type_correct(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_one_pager artifact_type is 'one_pager'."""
        with patch("artifact_generator.call_llm_quality", MagicMock(return_value="content")):
            result = artifact_generator.generate_one_pager(
                candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
            )
            assert result["artifact_type"] == "one_pager"

    def test_one_pager_prompt_mentions_format(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_one_pager prompt mentions 4-section format."""
        with patch("artifact_generator.call_llm_quality") as mock_llm:
            mock_llm.return_value = "content"
            artifact_generator.generate_one_pager(
                candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
            )
            prompt = mock_llm.call_args[0][0]
            assert "Value Proposition" in prompt
            assert "Capabilities" in prompt
            assert "Highlights" in prompt
