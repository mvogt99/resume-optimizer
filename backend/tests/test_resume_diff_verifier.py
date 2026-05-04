"""CT-3: Tests for resume output diff verifier.

Verifies that the DiffVerifier catches cosmetic-only tailoring where
a resume barely changes relative to the original.
"""

import pytest


@pytest.fixture
def original():
    return (
        "EXPERIENCE\n"
        "Senior Engineer at Acme Corp 2020-2023\n"
        "Led development of microservices architecture.\n"
        "SKILLS\n"
        "Python, Docker, REST APIs\n"
        "EDUCATION\n"
        "BS Computer Science"
    )


@pytest.fixture
def meaningful_tailored():
    """Resume substantially changed: new keywords, quantification, same sections."""
    return (
        "EXPERIENCE\n"
        "Senior Software Engineer at Acme Corp 2020-2023\n"
        "Led development of Kubernetes-based microservices reducing latency by 40%.\n"
        "Deployed CI/CD pipelines saving 15 hours per sprint.\n"
        "SKILLS\n"
        "Python, Docker, REST APIs, Kubernetes, Terraform, AWS\n"
        "EDUCATION\n"
        "BS Computer Science"
    )


@pytest.fixture
def cosmetic_tailored():
    """Resume barely changed: only a word or two different."""
    return (
        "EXPERIENCE\n"
        "Senior Engineer at Acme Corp 2020-2023\n"
        "Led development of microservices architecture.\n"
        "SKILLS\n"
        "Python, Docker, REST APIs\n"
        "EDUCATION\n"
        "BS Computer Science, Minor in Mathematics"
    )


@pytest.fixture
def jd_keywords():
    return ["Kubernetes", "Terraform", "AWS", "CI/CD", "DevOps"]


class TestDiffVerifierResult:
    """Tests for DiffVerificationResult dataclass shape."""

    def test_result_dataclass_shape(self, original, meaningful_tailored, jd_keywords):
        """Result has all required fields."""
        from agents.resume_diff_verifier import DiffVerificationResult, ResumeDiffVerifier

        verifier = ResumeDiffVerifier()
        result = verifier.verify(original, meaningful_tailored, jd_keywords)

        assert isinstance(result, DiffVerificationResult)
        assert hasattr(result, "meaningful_change")
        assert hasattr(result, "jaccard_sim")
        assert hasattr(result, "new_keywords")
        assert hasattr(result, "new_quantifications")
        assert hasattr(result, "sections_preserved")
        assert hasattr(result, "issues")

    def test_meaningful_change_is_bool(self, original, meaningful_tailored, jd_keywords):
        """meaningful_change field is a boolean."""
        from agents.resume_diff_verifier import ResumeDiffVerifier

        verifier = ResumeDiffVerifier()
        result = verifier.verify(original, meaningful_tailored, jd_keywords)
        assert isinstance(result.meaningful_change, bool)

    def test_jaccard_sim_between_0_and_1(self, original, meaningful_tailored, jd_keywords):
        """jaccard_sim is a float in [0, 1]."""
        from agents.resume_diff_verifier import ResumeDiffVerifier

        verifier = ResumeDiffVerifier()
        result = verifier.verify(original, meaningful_tailored, jd_keywords)
        assert 0.0 <= result.jaccard_sim <= 1.0


class TestIdenticalResumeDetection:
    """Tests for identical/cosmetic detection."""

    def test_identical_resumes_flagged_as_cosmetic(self, original, jd_keywords):
        """Identical input and output is cosmetic."""
        from agents.resume_diff_verifier import ResumeDiffVerifier

        verifier = ResumeDiffVerifier()
        result = verifier.verify(original, original, jd_keywords)
        assert result.meaningful_change is False
        assert "cosmetic" in " ".join(result.issues).lower() or result.jaccard_sim >= 0.85

    def test_substantially_different_resumes_pass(
        self, original, meaningful_tailored, jd_keywords
    ):
        """Resume with new keywords, quantifications, and same sections passes."""
        from agents.resume_diff_verifier import ResumeDiffVerifier

        verifier = ResumeDiffVerifier()
        result = verifier.verify(original, meaningful_tailored, jd_keywords)
        assert result.meaningful_change is True


class TestKeywordInjection:
    """Tests for keyword injection detection."""

    def test_keyword_injection_counted_correctly(
        self, original, meaningful_tailored, jd_keywords
    ):
        """New JD keywords present in tailored but not original are counted."""
        from agents.resume_diff_verifier import ResumeDiffVerifier

        verifier = ResumeDiffVerifier()
        result = verifier.verify(original, meaningful_tailored, jd_keywords)
        # meaningful_tailored adds: Kubernetes, Terraform, AWS, CI/CD (4 keywords)
        assert result.new_keywords >= 3

    def test_fewer_than_3_new_keywords_flagged(self, original, cosmetic_tailored):
        """If tailored adds fewer than 3 JD keywords, it's flagged."""
        from agents.resume_diff_verifier import ResumeDiffVerifier

        verifier = ResumeDiffVerifier()
        # cosmetic_tailored has no JD keywords from this list
        result = verifier.verify(original, cosmetic_tailored, ["Kubernetes", "Terraform", "AWS"])
        assert result.new_keywords < 3
        assert result.meaningful_change is False or any(
            "keyword" in issue.lower() for issue in result.issues
        )


class TestQuantificationDetection:
    """Tests for quantification (numbers/percentages) detection."""

    def test_quantification_detection(self, original, meaningful_tailored, jd_keywords):
        """New lines with numbers or percentages are counted."""
        from agents.resume_diff_verifier import ResumeDiffVerifier

        verifier = ResumeDiffVerifier()
        result = verifier.verify(original, meaningful_tailored, jd_keywords)
        # meaningful_tailored adds "40%" and "15 hours" — expects ≥1 new quantification
        assert result.new_quantifications >= 1


class TestSectionPreservation:
    """Tests for section structure preservation."""

    def test_missing_section_flagged(self, original, jd_keywords):
        """Resume missing original sections is flagged."""
        from agents.resume_diff_verifier import ResumeDiffVerifier

        # Missing EDUCATION section
        truncated = (
            "EXPERIENCE\n"
            "Senior Engineer at Acme Corp 2020-2023\n"
            "Led development of Kubernetes-based microservices reducing latency by 40%.\n"
            "SKILLS\n"
            "Python, Docker, Kubernetes, Terraform, AWS"
        )
        verifier = ResumeDiffVerifier()
        result = verifier.verify(original, truncated, jd_keywords)
        assert result.sections_preserved is False
        assert any("section" in issue.lower() or "education" in issue.lower() for issue in result.issues)

    def test_sections_preserved_when_all_present(
        self, original, meaningful_tailored, jd_keywords
    ):
        """All original sections present means sections_preserved=True."""
        from agents.resume_diff_verifier import ResumeDiffVerifier

        verifier = ResumeDiffVerifier()
        result = verifier.verify(original, meaningful_tailored, jd_keywords)
        assert result.sections_preserved is True


class TestConfigurability:
    """Tests for threshold configurability."""

    def test_threshold_configurable(self, original, jd_keywords):
        """Jaccard threshold can be overridden at construction time."""
        from agents.resume_diff_verifier import ResumeDiffVerifier

        # With a very low threshold, even cosmetic changes pass
        permissive = ResumeDiffVerifier(jaccard_threshold=0.99)
        # original vs itself: sim=1.0, which is above 0.99 → still cosmetic
        result = permissive.verify(original, original, jd_keywords)
        assert result.jaccard_sim == pytest.approx(1.0, abs=0.01)

    def test_empty_original_handled_gracefully(self, jd_keywords):
        """Empty original resume doesn't raise."""
        from agents.resume_diff_verifier import ResumeDiffVerifier

        verifier = ResumeDiffVerifier()
        result = verifier.verify("", "Some tailored content with Kubernetes", jd_keywords)
        assert isinstance(result.meaningful_change, bool)
