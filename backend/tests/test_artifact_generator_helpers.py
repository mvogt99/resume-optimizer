"""Test suite for artifact_generator.py helper functions.

Tests cover:
  - _word_count
  - _make_artifact
  - _profile_summary
  - _top_requirements
  - _high_gaps
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
        "branding_summary": "Experienced data engineer with 10 years in cloud platforms and ML infrastructure.",
        "skill_inventory": [
            {"canonical_skill": "Python", "aliases": ["python3"], "evidence_refs": ["proj1", "proj2"]},
            {"canonical_skill": "AWS", "aliases": ["Amazon Web Services"], "evidence_refs": ["proj1"]},
            {"canonical_skill": "Kubernetes", "aliases": ["k8s"], "evidence_refs": ["proj3"]},
            {"canonical_skill": "Spark", "aliases": ["Apache Spark"], "evidence_refs": ["proj2"]},
            {"canonical_skill": "SQL", "aliases": ["T-SQL", "PostgreSQL"], "evidence_refs": ["proj1", "proj3"]},
        ],
        "experience_units": [
            {
                "company": "Acme Corp",
                "title": "Senior Data Engineer",
                "skills": ["Python", "AWS", "Spark"],
                "description": "Led data platform modernization"
            },
            {
                "company": "TechStart Inc",
                "title": "ML Infrastructure Engineer",
                "skills": ["Kubernetes", "Python", "SQL"],
                "description": "Built ML serving platform"
            },
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
        {
            "requirement_id": "req_003",
            "requirement_type": "technical",
            "text": "Kubernetes orchestration",
            "importance": 0.75,
            "canonical_skills": ["Kubernetes"],
        },
        {
            "requirement_id": "req_004",
            "requirement_type": "soft_skill",
            "text": "Strong communication and mentoring",
            "importance": 0.7,
            "canonical_skills": [],
        },
    ]


@pytest.fixture
def scores():
    """Standard scores list fixture."""
    return [
        {"requirement_id": "req_001", "composite_score": 0.92},
        {"requirement_id": "req_002", "composite_score": 0.78},
        {"requirement_id": "req_003", "composite_score": 0.65},
        {"requirement_id": "req_004", "composite_score": 0.70},
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
            "recommended_action": "Highlight any ML optimization work; add inference tuning projects",
        },
        {
            "gap_id": "g2",
            "severity": "medium",
            "gap_type": "weak_wording",
            "description": "Resume lacks quantification in data pipeline achievements",
            "recommended_action": "Add throughput metrics (10M events/day, latency <100ms)",
        },
        {
            "gap_id": "g3",
            "severity": "low",
            "gap_type": "missing_skill",
            "description": "No GCP experience mentioned",
            "recommended_action": "Note if any cross-cloud experience exists",
        },
    ]


# ===== TEST WORD COUNT =====

class TestWordCount:
    """Test _word_count helper."""

    def test_word_count_empty_string(self):
        """_word_count("") returns 0."""
        assert artifact_generator._word_count("") == 0

    def test_word_count_single_word(self):
        """_word_count("hello") returns 1."""
        assert artifact_generator._word_count("hello") == 1

    def test_word_count_multiple_words(self):
        """_word_count counts split by whitespace correctly."""
        assert artifact_generator._word_count("hello world test") == 3

    def test_word_count_with_newlines(self):
        """_word_count treats newlines as whitespace."""
        text = "hello\nworld\ntest"
        assert artifact_generator._word_count(text) == 3

    def test_word_count_with_tabs(self):
        """_word_count treats tabs as whitespace."""
        text = "hello\tworld\ttest"
        assert artifact_generator._word_count(text) == 3

    def test_word_count_punctuation(self):
        """_word_count counts punctuation as part of words."""
        text = "hello, world! test?"
        assert artifact_generator._word_count(text) == 3


# ===== TEST MAKE ARTIFACT =====

class TestMakeArtifact:
    """Test _make_artifact helper."""

    def test_make_artifact_basic(self):
        """_make_artifact returns dict with all required keys."""
        result = artifact_generator._make_artifact("test content", "cover_letter")
        assert result["artifact_type"] == "cover_letter"
        assert result["content"] == "test content"
        assert result["word_count"] == 2
        assert result["error"] == ""

    def test_make_artifact_with_error(self):
        """_make_artifact includes error field when provided."""
        result = artifact_generator._make_artifact("", "gap_report", "LLM failed")
        assert result["error"] == "LLM failed"
        assert result["content"] == ""

    def test_make_artifact_word_count_accurate(self):
        """_make_artifact word_count matches content words."""
        content = "The quick brown fox jumps over the lazy dog"
        result = artifact_generator._make_artifact(content, "one_pager")
        assert result["word_count"] == 9

    def test_make_artifact_empty_content(self):
        """_make_artifact handles empty content."""
        result = artifact_generator._make_artifact("", "keyword_map")
        assert result["word_count"] == 0
        assert result["content"] == ""

    def test_make_artifact_long_content(self):
        """_make_artifact word_count accurate for long content."""
        content = " ".join(["word"] * 100)
        result = artifact_generator._make_artifact(content, "tailored_resume")
        assert result["word_count"] == 100


# ===== TEST PROFILE SUMMARY =====

class TestProfileSummary:
    """Test _profile_summary helper."""

    def test_profile_summary_includes_role_families(self, candidate_profile):
        """_profile_summary includes target role families."""
        summary = artifact_generator._profile_summary(candidate_profile)
        assert "Data Engineering" in summary
        assert "ML Ops" in summary

    def test_profile_summary_includes_branding(self, candidate_profile):
        """_profile_summary includes branding_summary (truncated)."""
        summary = artifact_generator._profile_summary(candidate_profile)
        assert "Experienced data engineer" in summary

    def test_profile_summary_includes_skills(self, candidate_profile):
        """_profile_summary includes top skills from skill_inventory."""
        summary = artifact_generator._profile_summary(candidate_profile)
        assert "Python" in summary
        assert "AWS" in summary

    def test_profile_summary_includes_companies(self, candidate_profile):
        """_profile_summary includes company and title from experience_units."""
        summary = artifact_generator._profile_summary(candidate_profile)
        assert "Acme Corp" in summary
        assert "Senior Data Engineer" in summary

    def test_profile_summary_handles_empty_profile(self):
        """_profile_summary handles empty candidate profile gracefully."""
        summary = artifact_generator._profile_summary({})
        assert "Role families:" in summary
        assert len(summary) > 0

    def test_profile_summary_limits_skills(self, candidate_profile):
        """_profile_summary limits skill_inventory to top 15."""
        profile = candidate_profile.copy()
        profile["skill_inventory"] = [
            {"canonical_skill": f"Skill{i}", "aliases": [], "evidence_refs": []}
            for i in range(20)
        ]
        summary = artifact_generator._profile_summary(profile)
        # Should include max 15 skills
        assert "Skill0" in summary
        assert "Skill14" in summary
        # Skill19 should not appear (beyond limit)
        assert "Skill19" not in summary


# ===== TEST TOP REQUIREMENTS =====

class TestTopRequirements:
    """Test _top_requirements helper."""

    def test_top_requirements_includes_requirement_text(self, requirements, scores):
        """_top_requirements includes requirement text and scores."""
        top = artifact_generator._top_requirements(requirements, scores, n=2)
        assert "5+ years Python" in top
        assert "AWS" in top

    def test_top_requirements_sorts_by_importance(self, requirements, scores):
        """_top_requirements sorts by importance (descending)."""
        # First requirement has highest importance (0.95)
        top = artifact_generator._top_requirements(requirements, scores, n=1)
        assert "5+ years Python" in top

    def test_top_requirements_includes_match_score(self, requirements, scores):
        """_top_requirements includes composite_score as match=X.XX."""
        top = artifact_generator._top_requirements(requirements, scores, n=1)
        assert "match=" in top
        assert "0.92" in top

    def test_top_requirements_respects_n_limit(self, requirements, scores):
        """_top_requirements returns at most n requirements."""
        top = artifact_generator._top_requirements(requirements, scores, n=2)
        lines = [l for l in top.split("\n") if l.strip()]
        assert len(lines) <= 2

    def test_top_requirements_empty_requirements(self, scores):
        """_top_requirements handles empty requirements list."""
        result = artifact_generator._top_requirements([], scores)
        assert result == ""

    def test_top_requirements_missing_scores(self, requirements):
        """_top_requirements handles missing scores gracefully."""
        result = artifact_generator._top_requirements(requirements, [], n=2)
        assert "match=0.00" in result


# ===== TEST HIGH GAPS =====

class TestHighGaps:
    """Test _high_gaps helper."""

    def test_high_gaps_includes_high_severity(self, gaps):
        """_high_gaps includes high severity gaps first."""
        high = artifact_generator._high_gaps(gaps)
        assert "HIGH" in high
        assert "Lacks 2+ years in ML inference" in high

    def test_high_gaps_includes_medium_severity(self, gaps):
        """_high_gaps includes medium severity gaps after high."""
        high = artifact_generator._high_gaps(gaps)
        assert "MEDIUM" in high

    def test_high_gaps_no_low_priority(self, gaps):
        """_high_gaps excludes low severity gaps."""
        high = artifact_generator._high_gaps(gaps, n=10)
        assert "GCP" not in high

    def test_high_gaps_empty_list(self):
        """_high_gaps returns 'No critical gaps' for empty list."""
        result = artifact_generator._high_gaps([])
        assert "No critical gaps" in result

    def test_high_gaps_respects_n_limit(self, gaps):
        """_high_gaps returns at most n gaps."""
        result = artifact_generator._high_gaps(gaps, n=1)
        lines = [l for l in result.split("\n") if l.strip()]
        assert len(lines) <= 1

    def test_high_gaps_only_high_medium(self, gaps):
        """_high_gaps includes only high+medium, excludes low."""
        result = artifact_generator._high_gaps(gaps, n=10)
        # Should have HIGH and MEDIUM markers
        assert "HIGH" in result
        assert "MEDIUM" in result
        # Should not include low severity gap
        assert "GCP" not in result
