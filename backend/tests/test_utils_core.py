"""Core tests for utils.py — resume processing, JD analysis, optimization, format validation."""

import os
import tempfile

import pytest
from test_helpers import JD_TEXT, RESUME_TEXT

# ---------------------------------------------------------------------------
# process_resume
# ---------------------------------------------------------------------------


class TestProcessResume:
    """Tests for process_resume() — file reading and text extraction."""

    def test_process_txt_file(self):
        from utils import process_resume

        with tempfile.NamedTemporaryFile(
            suffix=".txt", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write(RESUME_TEXT)
            f.flush()
            path = f.name

        try:
            result = process_resume(path)
            assert "text" in result
            assert "skills" in result
            assert "experience" in result
            assert "education" in result
            assert len(result["text"]) > 100
        finally:
            os.unlink(path)

    def test_process_txt_returns_skills(self):
        from utils import process_resume

        with tempfile.NamedTemporaryFile(
            suffix=".txt", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write(RESUME_TEXT)
            f.flush()
            path = f.name

        try:
            result = process_resume(path)
            assert isinstance(result["skills"], list)
            assert len(result["skills"]) > 0
        finally:
            os.unlink(path)

    def test_process_txt_extracts_experience(self):
        from utils import process_resume

        text = (
            "EXPERIENCE\n"
            "Senior Developer at Acme Corp 2018-2022\n"
            "Lead Engineer at BigCo 2015-2018\n"
        )
        with tempfile.NamedTemporaryFile(
            suffix=".txt", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write(text)
            f.flush()
            path = f.name

        try:
            result = process_resume(path)
            assert len(result["experience"]) >= 1
            found_titles = [e["title"] for e in result["experience"]]
            assert any("Developer" in t or "Engineer" in t for t in found_titles)
        finally:
            os.unlink(path)

    def test_process_txt_extracts_education(self):
        from utils import process_resume

        text = (
            "EDUCATION\n"
            "Master of Engineering — Stevens Institute of Technology\n"
            "Bachelor of Science — US Merchant Marine Academy\n"
        )
        with tempfile.NamedTemporaryFile(
            suffix=".txt", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write(text)
            f.flush()
            path = f.name

        try:
            result = process_resume(path)
            assert len(result["education"]) >= 1
            assert any("Master" in e["degree"] for e in result["education"])
        finally:
            os.unlink(path)

    def test_process_nonexistent_file_raises(self):
        from utils import process_resume

        with pytest.raises(FileNotFoundError):
            process_resume("/tmp/nonexistent_resume_xyz123.txt")

    def test_process_empty_file(self):
        from utils import process_resume

        with tempfile.NamedTemporaryFile(
            suffix=".txt", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write("")
            f.flush()
            path = f.name

        try:
            result = process_resume(path)
            assert result["text"] == ""
            assert result["skills"] == []
            assert result["experience"] == []
            assert result["education"] == []
        finally:
            os.unlink(path)

    def test_process_unknown_extension_reads_as_text(self):
        from utils import process_resume

        with tempfile.NamedTemporaryFile(
            suffix=".log", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write("Python developer resume with AWS skills")
            f.flush()
            path = f.name

        try:
            result = process_resume(path)
            assert "Python" in result["text"]
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# _extract_experience_from_text
# ---------------------------------------------------------------------------


class TestExtractExperience:
    """Tests for _extract_experience_from_text() — heuristic experience extraction."""

    def test_finds_title_with_date_range(self):
        from utils import _extract_experience_from_text

        text = "Senior Developer at Acme Corp 2018-2022\nLead Analyst at BigCo 2015-Present"
        result = _extract_experience_from_text(text)
        assert len(result) >= 2
        assert any("Developer" in e["title"] for e in result)
        assert any("Analyst" in e["title"] for e in result)

    def test_extracts_company_from_at_separator(self):
        from utils import _extract_experience_from_text

        text = "Manager at Google 2020-2023"
        result = _extract_experience_from_text(text)
        assert len(result) == 1
        assert result[0]["company"] == "Google 2020-2023"  # takes everything after " at "

    def test_extracts_duration(self):
        from utils import _extract_experience_from_text

        text = "Senior Engineer at Foo Inc 2019-2023"
        result = _extract_experience_from_text(text)
        assert len(result) == 1
        assert "2019" in result[0]["duration"]
        assert "2023" in result[0]["duration"]

    def test_no_match_returns_empty(self):
        from utils import _extract_experience_from_text

        text = "This text has no experience entries"
        result = _extract_experience_from_text(text)
        assert result == []

    def test_present_date_recognized(self):
        from utils import _extract_experience_from_text

        text = "Lead Architect at Corp 2020-Present"
        result = _extract_experience_from_text(text)
        assert len(result) == 1
        assert "Present" in result[0]["duration"]

    def test_resume_text_finds_experience(self):
        from utils import _extract_experience_from_text

        result = _extract_experience_from_text(RESUME_TEXT)
        assert len(result) >= 1, f"Should find experience in resume, got {result}"


# ---------------------------------------------------------------------------
# _extract_education_from_text
# ---------------------------------------------------------------------------


class TestExtractEducation:
    """Tests for _extract_education_from_text() — heuristic education extraction."""

    def test_finds_degree_keywords(self):
        from utils import _extract_education_from_text

        text = "B.S. Computer Science\nM.S. Data Science\nPh.D. Physics"
        result = _extract_education_from_text(text)
        assert len(result) >= 3

    def test_finds_full_degree_names(self):
        from utils import _extract_education_from_text

        text = "Bachelor of Science in Engineering\nMaster of Arts in History"
        result = _extract_education_from_text(text)
        assert len(result) >= 2
        assert any("Bachelor" in e["degree"] for e in result)
        assert any("Master" in e["degree"] for e in result)

    def test_finds_mba(self):
        from utils import _extract_education_from_text

        text = "MBA from Wharton School of Business"
        result = _extract_education_from_text(text)
        assert len(result) == 1
        assert "MBA" in result[0]["degree"]

    def test_no_education_returns_empty(self):
        from utils import _extract_education_from_text

        text = "10 years Python developer, AWS expert"
        result = _extract_education_from_text(text)
        assert result == []

    def test_resume_text_finds_education(self):
        from utils import _extract_education_from_text

        result = _extract_education_from_text(RESUME_TEXT)
        assert len(result) >= 1
        assert any("Master" in e["degree"] or "Bachelor" in e["degree"] for e in result)


# ---------------------------------------------------------------------------
# analyze_job_description
# ---------------------------------------------------------------------------


class TestAnalyzeJobDescription:
    """Tests for analyze_job_description() — JD section parsing and keyword extraction."""

    def test_returns_expected_keys(self):
        from utils import analyze_job_description

        result = analyze_job_description(JD_TEXT)
        assert "required_skills" in result
        assert "responsibilities" in result
        assert "qualifications" in result
        assert "companies_mentioned" in result

    def test_extracts_required_skills(self):
        from utils import analyze_job_description

        result = analyze_job_description(JD_TEXT)
        assert isinstance(result["required_skills"], list)
        assert len(result["required_skills"]) > 0

    def test_parses_qualifications_section(self):
        from utils import analyze_job_description

        jd = (
            "About the role:\n"
            "Join our team.\n\n"
            "Requirements:\n"
            "- 5+ years Python experience\n"
            "- AWS certification preferred\n"
            "- Strong communication skills\n"
        )
        result = analyze_job_description(jd)
        assert len(result["qualifications"]) >= 2
        assert any("Python" in q for q in result["qualifications"])

    def test_parses_responsibilities_section(self):
        from utils import analyze_job_description

        jd = (
            "What you'll do:\n"
            "- Design scalable APIs\n"
            "- Lead engineering team\n"
            "- Review code and mentor juniors\n"
        )
        result = analyze_job_description(jd)
        assert len(result["responsibilities"]) >= 2

    def test_empty_jd_returns_empty_sections(self):
        from utils import analyze_job_description

        result = analyze_job_description("")
        assert result["responsibilities"] == []
        assert result["qualifications"] == []


# ---------------------------------------------------------------------------
# optimize_resume
# ---------------------------------------------------------------------------


class TestOptimizeResume:
    """Tests for optimize_resume() — multi-signal ATS scoring and content enhancement."""

    @pytest.fixture(autouse=True)
    def _patch_llm(self, monkeypatch):
        """Patch LLM rewrite to return None (avoid network calls)."""
        import utils

        monkeypatch.setattr(utils, "_llm_rewrite_resume", lambda *a, **kw: None)

    def test_returns_expected_keys(self):
        from utils import optimize_resume

        resume_data = {"text": RESUME_TEXT, "skills": ["python", "aws", "docker"]}
        job_keywords = ["python", "aws", "docker", "kubernetes"]
        result = optimize_resume(resume_data, job_keywords, job_text=JD_TEXT)
        assert "score" in result
        assert "optimized_text" in result
        assert "matching_keywords" in result
        assert "added_keywords" in result
        assert "ats_compliance" in result
        assert "score_breakdown" in result
        assert "sections_found" in result

    def test_score_is_integer(self):
        from utils import optimize_resume

        resume_data = {"text": RESUME_TEXT, "skills": ["python", "aws"]}
        result = optimize_resume(resume_data, ["python", "aws"], job_text=JD_TEXT)
        assert isinstance(result["score"], int)
        assert 0 <= result["score"] <= 100

    def test_score_breakdown_has_four_signals(self):
        from utils import optimize_resume

        resume_data = {"text": RESUME_TEXT, "skills": ["python"]}
        result = optimize_resume(resume_data, ["python"], job_text=JD_TEXT)
        breakdown = result["score_breakdown"]
        assert "keyword_coverage" in breakdown
        assert "semantic_similarity" in breakdown
        assert "skills_match" in breakdown
        assert "section_completeness" in breakdown

    def test_sections_found_dict(self):
        from utils import optimize_resume

        resume_data = {"text": RESUME_TEXT, "skills": []}
        result = optimize_resume(resume_data, [], job_text=JD_TEXT)
        sf = result["sections_found"]
        assert "skills" in sf
        assert "experience" in sf
        assert "education" in sf
        assert "summary" in sf
        # RESUME_TEXT has all four sections
        assert sf["skills"] is True
        assert sf["experience"] is True
        assert sf["education"] is True
        assert sf["summary"] is True

    def test_matching_keywords_populated(self):
        from utils import optimize_resume

        resume_data = {"text": RESUME_TEXT, "skills": ["python", "aws", "docker"]}
        result = optimize_resume(resume_data, ["python", "aws", "docker"], job_text=JD_TEXT)
        assert isinstance(result["matching_keywords"], list)

    def test_ats_compliance_bool(self):
        from utils import optimize_resume

        resume_data = {"text": RESUME_TEXT, "skills": ["python", "aws"]}
        result = optimize_resume(resume_data, ["python", "aws"], job_text=JD_TEXT)
        assert isinstance(result["ats_compliance"], bool)

    def test_optimized_text_not_empty(self):
        from utils import optimize_resume

        resume_data = {"text": RESUME_TEXT, "skills": ["python"]}
        result = optimize_resume(resume_data, ["python"], job_text=JD_TEXT)
        assert len(result["optimized_text"]) > 0

    def test_missing_section_detected(self):
        from utils import optimize_resume

        # Resume with only experience, no skills/education/summary
        resume_data = {"text": "Developer at Acme Corp 2020-2023", "skills": []}
        result = optimize_resume(resume_data, ["python"], job_text="Python developer")
        sf = result["sections_found"]
        assert sf["skills"] is False
        assert sf["education"] is False

    def test_well_matched_resume_scores_higher(self):
        from utils import optimize_resume

        good_match = {"text": RESUME_TEXT, "skills": ["python", "aws", "docker", "kubernetes"]}
        bad_match = {
            "text": "Chef specializing in French cuisine and pastry arts",
            "skills": ["cooking", "baking"],
        }
        score_good = optimize_resume(good_match, ["python", "aws"], job_text=JD_TEXT)["score"]
        score_bad = optimize_resume(bad_match, ["python", "aws"], job_text=JD_TEXT)["score"]
        assert (
            score_good > score_bad
        ), f"Good match ({score_good}) should outscore bad match ({score_bad})"

    def test_with_linkedin_profile(self):
        from test_helpers import LINKEDIN_PROFILE
        from utils import optimize_resume

        resume_data = {"text": RESUME_TEXT, "skills": ["python", "aws"]}
        result = optimize_resume(
            resume_data,
            ["python", "aws"],
            job_text=JD_TEXT,
            linkedin_profile=LINKEDIN_PROFILE,
        )
        assert "accomplishments" in result
        assert "recommendations" in result
        assert isinstance(result["accomplishments"], list)

    def test_without_job_text_uses_keywords(self):
        from utils import optimize_resume

        resume_data = {"text": RESUME_TEXT, "skills": ["python"]}
        result = optimize_resume(resume_data, ["python", "aws", "docker"], job_text="")
        # Should still produce a score
        assert result["score"] >= 0

    def test_skill_phrases_matched_key(self):
        from utils import optimize_resume

        resume_data = {"text": RESUME_TEXT, "skills": ["python", "kubernetes"]}
        result = optimize_resume(resume_data, ["python"], job_text=JD_TEXT)
        assert "skill_phrases_matched" in result
        assert isinstance(result["skill_phrases_matched"], list)


# ---------------------------------------------------------------------------
# validate_resume_format
# ---------------------------------------------------------------------------


class TestValidateResumeFormat:
    """Tests for validate_resume_format() — ATS compliance checking."""

    def test_full_resume_is_compliant(self):
        from utils import validate_resume_format

        result = validate_resume_format(RESUME_TEXT)
        assert result["is_ats_compliant"] is True
        assert result["issues"] == []

    def test_missing_skills_section(self):
        from utils import validate_resume_format

        text = "Experience\nDeveloper at Acme 2020-2023\nEducation\nBS Computer Science"
        result = validate_resume_format(text)
        assert "Missing skills section" in result["issues"]

    def test_missing_experience_section(self):
        from utils import validate_resume_format

        text = "Skills\nPython, Java, AWS\nEducation\nBS CS"
        result = validate_resume_format(text)
        assert "Missing experience section" in result["issues"]

    def test_missing_education_section(self):
        from utils import validate_resume_format

        text = "Skills\nPython, Java\nExperience\nDeveloper 2020-2023"
        result = validate_resume_format(text)
        assert "Missing education section" in result["issues"]

    def test_all_sections_missing(self):
        from utils import validate_resume_format

        text = "John Doe — Software Professional"
        result = validate_resume_format(text)
        assert result["is_ats_compliant"] is False
        assert len(result["issues"]) == 3


# ---------------------------------------------------------------------------
# generate_ats_guidelines
# ---------------------------------------------------------------------------


class TestGenerateAtsGuidelines:
    """Tests for generate_ats_guidelines() — static guideline generation."""

    def test_returns_expected_keys(self):
        from utils import generate_ats_guidelines

        result = generate_ats_guidelines()
        assert "formatting" in result
        assert "content" in result
        assert "best_practices" in result

    def test_formatting_has_entries(self):
        from utils import generate_ats_guidelines

        result = generate_ats_guidelines()
        assert len(result["formatting"]) >= 2
        assert all(isinstance(item, str) for item in result["formatting"])

    def test_content_mentions_keywords(self):
        from utils import generate_ats_guidelines

        result = generate_ats_guidelines()
        joined = " ".join(result["content"]).lower()
        assert "keyword" in joined

    def test_best_practices_mentions_action_verbs(self):
        from utils import generate_ats_guidelines

        result = generate_ats_guidelines()
        joined = " ".join(result["best_practices"]).lower()
        assert "action" in joined or "verb" in joined
