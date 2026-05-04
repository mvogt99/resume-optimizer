"""Test suite for artifact_generator.py orchestration and summary.

Tests cover:
  - generate_artifacts orchestration
  - get_artifact_summary aggregation
  - Integration scenarios
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


# ===== TEST GENERATE ARTIFACTS =====

class TestGenerateArtifacts:
    """Test generate_artifacts orchestration."""

    def test_generate_artifacts_default_all_seven(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_artifacts returns all 7 artifact types when artifacts=None."""
        with patch("artifact_generator.call_llm_quality", MagicMock(return_value="content")):
            result = artifact_generator.generate_artifacts(
                candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
            )
            assert len(result) == 7
            assert "tailored_resume" in result
            assert "cover_letter" in result
            assert "gap_report" in result
            assert "keyword_map" in result
            assert "interview_seeds" in result
            assert "linkedin_summary" in result
            assert "one_pager" in result

    def test_generate_artifacts_respects_artifact_list(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_artifacts returns only requested artifact types."""
        with patch("artifact_generator.call_llm_quality", MagicMock(return_value="content")):
            result = artifact_generator.generate_artifacts(
                candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text,
                artifacts=["cover_letter", "gap_report"]
            )
            assert len(result) == 2
            assert "cover_letter" in result
            assert "gap_report" in result
            assert "tailored_resume" not in result

    def test_generate_artifacts_skips_unknown_type(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_artifacts skips unknown artifact types with warning."""
        with patch("artifact_generator.call_llm_quality", MagicMock(return_value="content")):
            with patch("artifact_generator.logger") as mock_logger:
                result = artifact_generator.generate_artifacts(
                    candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text,
                    artifacts=["cover_letter", "unknown_type"]
                )
                assert len(result) == 1
                assert "cover_letter" in result
                assert "unknown_type" not in result
                mock_logger.warning.assert_called()

    def test_generate_artifacts_never_raises(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_artifacts never raises — catches all exceptions."""
        # Even if a generator crashes, orchestration continues
        with patch("artifact_generator.call_llm_quality") as mock_llm:
            mock_llm.side_effect = Exception("Unexpected error")
            result = artifact_generator.generate_artifacts(
                candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
            )
            # Should still return structure, even if all failed
            assert isinstance(result, dict)

    def test_generate_artifacts_handles_generator_crash(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_artifacts logs error and stores it in artifact when generator crashes."""
        with patch("artifact_generator.call_llm_quality") as mock_llm:
            mock_llm.side_effect = Exception("LLM crashed")
            with patch("artifact_generator.logger") as mock_logger:
                result = artifact_generator.generate_artifacts(
                    candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text,
                    artifacts=["cover_letter"]
                )
                # Logger should have error
                mock_logger.error.assert_called()
                # Result should have error field set
                assert result["cover_letter"]["error"]

    def test_generate_artifacts_with_empty_list_defaults_to_all(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_artifacts with artifacts=[] defaults to all 7 types (empty list is falsy)."""
        with patch("artifact_generator.call_llm_quality", MagicMock(return_value="content")):
            result = artifact_generator.generate_artifacts(
                candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text,
                artifacts=[]
            )
            # Empty list is falsy, so it defaults to all ARTIFACT_TYPES
            assert len(result) == 7

    def test_generate_artifacts_single_artifact(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_artifacts returns single artifact when requested."""
        with patch("artifact_generator.call_llm_quality", MagicMock(return_value="content")):
            result = artifact_generator.generate_artifacts(
                candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text,
                artifacts=["gap_report"]
            )
            assert len(result) == 1
            assert "gap_report" in result

    def test_generate_artifacts_partial_success(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_artifacts returns all requested artifacts, some with errors."""
        with patch("artifact_generator.call_llm_quality") as mock_llm:
            # First call succeeds, second fails
            mock_llm.side_effect = [
                "Cover letter content",
                Exception("LLM error"),
            ]
            result = artifact_generator.generate_artifacts(
                candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text,
                artifacts=["cover_letter", "interview_seeds"]
            )
            assert len(result) == 2
            assert result["cover_letter"]["content"]
            assert result["interview_seeds"]["error"]


# ===== TEST GET ARTIFACT SUMMARY =====

class TestGetArtifactSummary:
    """Test get_artifact_summary aggregation."""

    def test_summary_total_count(self):
        """get_artifact_summary counts total artifacts."""
        artifacts = {
            "cover_letter": {"content": "letter", "word_count": 10, "error": "", "artifact_type": "cover_letter"},
            "gap_report": {"content": "report", "word_count": 20, "error": "", "artifact_type": "gap_report"},
            "keyword_map": {"content": "", "word_count": 0, "error": "LLM failed", "artifact_type": "keyword_map"},
        }
        summary = artifact_generator.get_artifact_summary(artifacts)
        assert summary["total"] == 3

    def test_summary_generated_count(self):
        """get_artifact_summary counts artifacts with non-empty content."""
        artifacts = {
            "cover_letter": {"content": "letter", "word_count": 10, "error": "", "artifact_type": "cover_letter"},
            "gap_report": {"content": "", "word_count": 0, "error": "failed", "artifact_type": "gap_report"},
        }
        summary = artifact_generator.get_artifact_summary(artifacts)
        assert summary["generated_count"] == 1

    def test_summary_failed_count(self):
        """get_artifact_summary counts artifacts with error field."""
        artifacts = {
            "cover_letter": {"content": "letter", "word_count": 10, "error": "", "artifact_type": "cover_letter"},
            "gap_report": {"content": "", "word_count": 0, "error": "LLM failed", "artifact_type": "gap_report"},
            "keyword_map": {"content": "", "word_count": 0, "error": "crashed", "artifact_type": "keyword_map"},
        }
        summary = artifact_generator.get_artifact_summary(artifacts)
        assert summary["failed_count"] == 2

    def test_summary_total_word_count(self):
        """get_artifact_summary sums word counts."""
        artifacts = {
            "cover_letter": {"content": "letter", "word_count": 100, "error": "", "artifact_type": "cover_letter"},
            "gap_report": {"content": "report", "word_count": 250, "error": "", "artifact_type": "gap_report"},
            "keyword_map": {"content": "", "word_count": 0, "error": "failed", "artifact_type": "keyword_map"},
        }
        summary = artifact_generator.get_artifact_summary(artifacts)
        assert summary["total_word_count"] == 350

    def test_summary_by_type_structure(self):
        """get_artifact_summary includes by_type with word_count and has_error."""
        artifacts = {
            "cover_letter": {"content": "letter", "word_count": 100, "error": "", "artifact_type": "cover_letter"},
            "gap_report": {"content": "", "word_count": 0, "error": "failed", "artifact_type": "gap_report"},
        }
        summary = artifact_generator.get_artifact_summary(artifacts)
        assert summary["by_type"]["cover_letter"]["word_count"] == 100
        assert summary["by_type"]["cover_letter"]["has_error"] is False
        assert summary["by_type"]["gap_report"]["has_error"] is True

    def test_summary_empty_artifacts(self):
        """get_artifact_summary handles empty artifacts dict."""
        summary = artifact_generator.get_artifact_summary({})
        assert summary["total"] == 0
        assert summary["generated_count"] == 0
        assert summary["failed_count"] == 0
        assert summary["total_word_count"] == 0

    def test_summary_all_successful(self):
        """get_artifact_summary correctly counts all successful artifacts."""
        artifacts = {
            "cover_letter": {"content": "content1", "word_count": 50, "error": "", "artifact_type": "cover_letter"},
            "gap_report": {"content": "content2", "word_count": 75, "error": "", "artifact_type": "gap_report"},
            "keyword_map": {"content": "content3", "word_count": 25, "error": "", "artifact_type": "keyword_map"},
        }
        summary = artifact_generator.get_artifact_summary(artifacts)
        assert summary["total"] == 3
        assert summary["generated_count"] == 3
        assert summary["failed_count"] == 0
        assert summary["total_word_count"] == 150

    def test_summary_all_failed(self):
        """get_artifact_summary correctly counts all failed artifacts."""
        artifacts = {
            "cover_letter": {"content": "", "word_count": 0, "error": "LLM unavailable", "artifact_type": "cover_letter"},
            "gap_report": {"content": "", "word_count": 0, "error": "Error", "artifact_type": "gap_report"},
        }
        summary = artifact_generator.get_artifact_summary(artifacts)
        assert summary["total"] == 2
        assert summary["generated_count"] == 0
        assert summary["failed_count"] == 2


# ===== INTEGRATION TESTS =====

class TestIntegration:
    """Integration tests combining multiple components."""

    def test_full_flow_with_all_artifacts(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """Full flow: generate all artifacts, get summary."""
        with patch("artifact_generator.call_llm_quality") as mock_llm:
            mock_llm.return_value = "Generated content from LLM"
            artifacts = artifact_generator.generate_artifacts(
                candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
            )
            summary = artifact_generator.get_artifact_summary(artifacts)

            assert summary["total"] == 7
            assert summary["generated_count"] == 7
            assert summary["failed_count"] == 0
            assert summary["total_word_count"] > 0

    def test_partial_failure_scenario(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """Scenario: some artifacts succeed, some fail."""
        with patch("artifact_generator.call_llm_quality") as mock_llm:
            # Make LLM succeed for some, fail for others
            mock_llm.side_effect = [
                "Cover letter content",
                Exception("LLM timeout"),
                "Interview seeds content",
            ]
            artifacts = artifact_generator.generate_artifacts(
                candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text,
                artifacts=["cover_letter", "interview_seeds", "linkedin_summary"]
            )
            summary = artifact_generator.get_artifact_summary(artifacts)

            # Exactly 3 artifacts requested
            assert summary["total"] == 3
            # 2 should have content (cover_letter, interview_seeds)
            assert summary["generated_count"] == 2
            # 1 should have error (linkedin_summary)
            assert summary["failed_count"] >= 1

    def test_heuristic_only_flow(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """Request only heuristic artifacts (gap_report, keyword_map) — no LLM needed."""
        # Don't patch call_llm_quality — let it be None
        with patch("artifact_generator.call_llm_quality", None):
            artifacts = artifact_generator.generate_artifacts(
                candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text,
                artifacts=["gap_report", "keyword_map"]
            )
            summary = artifact_generator.get_artifact_summary(artifacts)

            assert summary["total"] == 2
            # Both heuristic artifacts should have content
            assert summary["generated_count"] == 2
            assert summary["failed_count"] == 0

    def test_mixed_heuristic_llm_flow(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """Mixed heuristic + LLM artifacts in one call."""
        with patch("artifact_generator.call_llm_quality") as mock_llm:
            mock_llm.return_value = "LLM generated content"
            artifacts = artifact_generator.generate_artifacts(
                candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text,
                artifacts=["gap_report", "cover_letter", "keyword_map"]
            )
            summary = artifact_generator.get_artifact_summary(artifacts)

            assert summary["total"] == 3
            # gap_report + keyword_map are heuristic (no error)
            # cover_letter is LLM
            assert summary["generated_count"] == 3
            assert summary["failed_count"] == 0

    def test_summary_percentages(self):
        """get_artifact_summary can derive success/failure percentages."""
        artifacts = {
            "a1": {"content": "c1", "word_count": 10, "error": "", "artifact_type": "a1"},
            "a2": {"content": "c2", "word_count": 20, "error": "", "artifact_type": "a2"},
            "a3": {"content": "", "word_count": 0, "error": "err", "artifact_type": "a3"},
            "a4": {"content": "", "word_count": 0, "error": "err", "artifact_type": "a4"},
        }
        summary = artifact_generator.get_artifact_summary(artifacts)
        success_pct = (summary["generated_count"] / summary["total"]) * 100
        failure_pct = (summary["failed_count"] / summary["total"]) * 100
        assert success_pct == 50
        assert failure_pct == 50
