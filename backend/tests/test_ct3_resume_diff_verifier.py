"""CT-3: Unit tests for ResumeDiffVerifier."""

from __future__ import annotations

import sys

import pytest

sys.path.insert(0, "/home/mike/models/source/hybrid-ai-windows/applications/resume-optimizer/backend")

from agents.resume_diff_verifier import DiffVerificationResult, ResumeDiffVerifier

_ORIGINAL = (
    "SUMMARY\nExperienced software engineer.\n\n"
    "EXPERIENCE\nEngineer at Acme. Led projects.\n\n"
    "SKILLS\nPython, SQL\n"
)

_JD_KEYWORDS = ["Python", "AWS", "CI/CD", "Kubernetes", "distributed systems"]


class TestJaccardSimilarity:
    def test_identical_texts_similarity_one(self):
        v = ResumeDiffVerifier()
        result = v.verify(_ORIGINAL, _ORIGINAL, _JD_KEYWORDS)
        assert result.jaccard_sim == pytest.approx(1.0, abs=0.01)

    def test_completely_different_text_low_similarity(self):
        v = ResumeDiffVerifier()
        tailored = "Quantum physics researcher. Astrophysics. CERN experiments. EDUCATION\nPhD Physics."
        result = v.verify(_ORIGINAL, tailored, _JD_KEYWORDS)
        assert result.jaccard_sim < 0.3

    def test_slightly_changed_text_high_similarity(self):
        v = ResumeDiffVerifier()
        tailored = _ORIGINAL.replace("Led projects", "Led cross-functional projects")
        result = v.verify(_ORIGINAL, tailored, _JD_KEYWORDS)
        assert result.jaccard_sim > 0.85


class TestKeywordInjection:
    def test_no_new_keywords_flags_issue(self):
        v = ResumeDiffVerifier()
        result = v.verify(_ORIGINAL, _ORIGINAL, _JD_KEYWORDS)
        assert result.new_keywords == 0
        assert any("keyword" in issue for issue in result.issues)

    def test_many_new_keywords_passes(self):
        v = ResumeDiffVerifier(jaccard_threshold=0.99)  # disable Jaccard check
        tailored = _ORIGINAL + "\nAWS CI/CD Kubernetes distributed systems microservices Docker"
        result = v.verify(_ORIGINAL, tailored, _JD_KEYWORDS)
        assert result.new_keywords >= 3

    def test_min_new_keywords_configurable(self):
        v = ResumeDiffVerifier(min_new_keywords=1)
        tailored = _ORIGINAL + "\nAWS"
        result = v.verify(_ORIGINAL, tailored, ["AWS"])
        assert result.new_keywords >= 1


class TestQuantification:
    def test_original_without_numbers_flags_missing_quantifications(self):
        v = ResumeDiffVerifier()
        # tailored same as original — no new numbers
        result = v.verify(_ORIGINAL, _ORIGINAL, _JD_KEYWORDS)
        assert result.new_quantifications == 0

    def test_added_numbers_detected(self):
        v = ResumeDiffVerifier(jaccard_threshold=0.99)
        tailored = _ORIGINAL + "\nIncreased efficiency by 40% for 50 engineers over 3 years."
        result = v.verify(_ORIGINAL, tailored, _JD_KEYWORDS)
        assert result.new_quantifications > 0

    def test_dollar_amounts_count(self):
        v = ResumeDiffVerifier(jaccard_threshold=0.99)
        tailored = _ORIGINAL + "\nManaged $2M budget and $500K contracts."
        result = v.verify(_ORIGINAL, tailored, _JD_KEYWORDS)
        assert result.new_quantifications > 0


class TestSectionPreservation:
    def test_all_sections_preserved_passes(self):
        v = ResumeDiffVerifier(jaccard_threshold=0.99, min_new_keywords=0)
        result = v.verify(_ORIGINAL, _ORIGINAL, [])
        assert result.sections_preserved is True

    def test_missing_section_flags_issue(self):
        v = ResumeDiffVerifier()
        tailored_no_skills = _ORIGINAL.replace("SKILLS\nPython, SQL\n", "")
        result = v.verify(_ORIGINAL, tailored_no_skills, _JD_KEYWORDS)
        assert result.sections_preserved is False
        assert any("section" in issue.lower() for issue in result.issues)


class TestMeaningfulChange:
    def test_identical_resume_not_meaningful(self):
        v = ResumeDiffVerifier()
        result = v.verify(_ORIGINAL, _ORIGINAL, _JD_KEYWORDS)
        assert result.meaningful_change is False

    def test_well_tailored_resume_is_meaningful(self):
        v = ResumeDiffVerifier()
        # Include "projects" so section detection (which also matches body text) doesn't flag it
        tailored = (
            "SUMMARY\nExperienced Python + AWS engineer specializing in distributed systems.\n\n"
            "EXPERIENCE\nSenior Engineer at Acme. Led CI/CD migration for 80 engineers, "
            "reducing deployment time by 60%. Built Kubernetes clusters serving 500K users. "
            "Delivered 3 major infrastructure projects on schedule.\n\n"
            "SKILLS\nPython, SQL, AWS, Kubernetes, CI/CD, distributed systems\n"
        )
        result = v.verify(_ORIGINAL, tailored, _JD_KEYWORDS)
        assert result.meaningful_change is True

    def test_result_is_dataclass(self):
        v = ResumeDiffVerifier()
        result = v.verify(_ORIGINAL, _ORIGINAL, _JD_KEYWORDS)
        assert isinstance(result, DiffVerificationResult)
        assert isinstance(result.issues, list)
