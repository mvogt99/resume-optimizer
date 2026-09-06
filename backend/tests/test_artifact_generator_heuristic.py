"""Test suite for artifact_generator.py heuristic generators.

Tests cover:
  - generate_gap_report (no LLM needed)
  - generate_keyword_map (no LLM needed)
"""

import pytest
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
            "text": "AWS cloud services (EC2, S3, RDS)",
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
            "description": "Lacks 2+ years in ML inference optimization",
            "recommended_action": "Highlight ML optimization work",
        },
        {
            "gap_id": "g2",
            "severity": "medium",
            "gap_type": "weak_wording",
            "description": "Resume lacks quantification",
            "recommended_action": "Add throughput metrics",
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
            "rewrite_template": "Optimized ML model serving latency",
        },
    ]


@pytest.fixture
def resume_text():
    """Standard resume text fixture."""
    return "Senior Data Engineer with Python and AWS experience at Acme Corp. Built data pipelines."


# ===== TEST GENERATE GAP REPORT =====

class TestGenerateGapReport:
    """Test generate_gap_report (heuristic, no LLM needed)."""

    def test_gap_report_structure(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_gap_report returns artifact with required keys."""
        result = artifact_generator.generate_gap_report(
            candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
        )
        assert result["artifact_type"] == "gap_report"
        assert "content" in result
        assert "word_count" in result
        assert "error" in result

    def test_gap_report_with_gaps(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_gap_report produces markdown content when gaps present."""
        result = artifact_generator.generate_gap_report(
            candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
        )
        assert result["content"]
        assert "Gap Analysis Report" in result["content"]
        assert result["error"] == ""

    def test_gap_report_empty_gaps(self, candidate_profile, requirements, scores, rewrite_targets, resume_text):
        """generate_gap_report returns 'No gaps identified.' for empty gaps."""
        result = artifact_generator.generate_gap_report(
            candidate_profile, requirements, scores, [], rewrite_targets, resume_text
        )
        assert result["content"] == "No gaps identified."
        assert result["error"] == ""

    def test_gap_report_groups_by_severity(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_gap_report organizes gaps by severity."""
        result = artifact_generator.generate_gap_report(
            candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
        )
        assert "HIGH" in result["content"]
        assert "MEDIUM" in result["content"]

    def test_gap_report_includes_gap_descriptions(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_gap_report includes gap descriptions and actions."""
        result = artifact_generator.generate_gap_report(
            candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
        )
        assert "Lacks 2+ years in ML inference" in result["content"]
        assert "Highlight ML optimization work" in result["content"]

    def test_gap_report_includes_rewrite_targets(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_gap_report includes rewrite targets section."""
        result = artifact_generator.generate_gap_report(
            candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
        )
        assert "Rewrite Targets" in result["content"]
        assert "Add ML inference optimization bullet" in result["content"]

    def test_gap_report_word_count_nonzero(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_gap_report has non-zero word count when gaps present."""
        result = artifact_generator.generate_gap_report(
            candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
        )
        assert result["word_count"] > 0

    def test_gap_report_never_raises(self):
        """generate_gap_report never raises — even with None/empty inputs."""
        # Should not raise
        result = artifact_generator.generate_gap_report(None, None, None, None, None, None)
        assert "artifact_type" in result

    def test_gap_report_shows_all_severities(self, candidate_profile, requirements, scores):
        """generate_gap_report includes high, medium, and low severity gaps."""
        gaps_with_low = [
            {"gap_id": "g1", "severity": "high", "gap_type": "test", "description": "High severity", "recommended_action": "act1"},
            {"gap_id": "g2", "severity": "medium", "gap_type": "test", "description": "Medium severity", "recommended_action": "act2"},
            {"gap_id": "g3", "severity": "low", "gap_type": "test", "description": "Low severity", "recommended_action": "act3"},
        ]
        result = artifact_generator.generate_gap_report(
            candidate_profile, requirements, scores, gaps_with_low, [], ""
        )
        assert "HIGH" in result["content"]
        assert "MEDIUM" in result["content"]
        assert "LOW" in result["content"]


# ===== TEST GENERATE KEYWORD MAP =====

class TestGenerateKeywordMap:
    """Test generate_keyword_map (heuristic, no LLM needed)."""

    def test_keyword_map_structure(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_keyword_map returns artifact with required keys."""
        result = artifact_generator.generate_keyword_map(
            candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
        )
        assert result["artifact_type"] == "keyword_map"
        assert "content" in result
        assert "word_count" in result
        assert "error" in result

    def test_keyword_map_markdown_table(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_keyword_map produces markdown table."""
        result = artifact_generator.generate_keyword_map(
            candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
        )
        assert "| Keyword | Status | Match Score |" in result["content"]
        assert "|---------|--------|-------------|" in result["content"]

    def test_keyword_map_marks_present_skills(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_keyword_map marks skills in resume as '✓ Present'."""
        result = artifact_generator.generate_keyword_map(
            candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
        )
        # Python is in resume_text
        assert "✓ Present" in result["content"]

    def test_keyword_map_marks_missing_skills(self, candidate_profile, requirements, scores, gaps, rewrite_targets):
        """generate_keyword_map marks missing skills as '✗ Missing'."""
        result = artifact_generator.generate_keyword_map(
            candidate_profile, requirements, scores, gaps, rewrite_targets, "Only Python mentioned"
        )
        # S3 not in "Only Python mentioned"
        assert "✗ Missing" in result["content"]

    def test_keyword_map_case_insensitive(self, candidate_profile, requirements, scores, gaps, rewrite_targets):
        """generate_keyword_map checks skills case-insensitively."""
        result = artifact_generator.generate_keyword_map(
            candidate_profile, requirements, scores, gaps, rewrite_targets, "I use PYTHON and AWS"
        )
        assert "✓ Present" in result["content"]

    def test_keyword_map_includes_match_scores(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_keyword_map includes composite scores from requirements."""
        result = artifact_generator.generate_keyword_map(
            candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
        )
        # Should include match score from scores fixture
        assert "0.92" in result["content"]  # req_001 score
        assert "0.78" in result["content"]  # req_002 score

    def test_keyword_map_never_raises(self):
        """generate_keyword_map never raises."""
        result = artifact_generator.generate_keyword_map(None, None, None, None, None, None)
        assert "artifact_type" in result

    def test_keyword_map_limits_skills_per_requirement(self, candidate_profile, requirements):
        """generate_keyword_map limits to 3 skills per requirement."""
        req_with_many_skills = {
            "requirement_id": "req_001",
            "requirement_type": "technical",
            "text": "Many skills",
            "importance": 0.9,
            "canonical_skills": ["Skill1", "Skill2", "Skill3", "Skill4", "Skill5"],
        }
        scores = [{"requirement_id": "req_001", "composite_score": 0.8}]
        result = artifact_generator.generate_keyword_map(
            candidate_profile, [req_with_many_skills], scores, [], [], "Skill1 Skill2"
        )
        # Should only include first 3 skills
        assert "Skill1" in result["content"]
        assert "Skill2" in result["content"]
        assert "Skill3" in result["content"]
        # Skill4, Skill5 should not be in table (limited to 3)
        content_lines = result["content"].split("\n")
        skill_rows = [l for l in content_lines if l.startswith("| Skill")]
        assert len(skill_rows) == 3

    def test_keyword_map_word_count_accurate(self, candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text):
        """generate_keyword_map word_count matches content."""
        result = artifact_generator.generate_keyword_map(
            candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text
        )
        # Word count should be split by whitespace
        expected_word_count = len(result["content"].split())
        assert result["word_count"] == expected_word_count

    def test_keyword_map_empty_requirements_canonical_skills(self, candidate_profile, scores):
        """generate_keyword_map skips requirements with no canonical_skills."""
        req_no_skills = {
            "requirement_id": "req_001",
            "requirement_type": "soft_skill",
            "text": "Leadership",
            "importance": 0.8,
            "canonical_skills": [],
        }
        result = artifact_generator.generate_keyword_map(
            candidate_profile, [req_no_skills], scores, [], [], "leadership"
        )
        # Should have table header but no data rows (no canonical skills)
        assert "| Keyword | Status | Match Score |" in result["content"]
