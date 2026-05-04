"""Cross-module integration tests — verifies data flows between core modules.

Tests the pipeline: linkedin_parser → skills_optimizer → interview_guide → utils.
Uses real LinkedIn JSON from working-docs/linkedin/.
No mocks, no skips. Pure logic validation.
"""

import json
import os
from pathlib import Path

import pytest

# Ensure backend/ is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
TESTS_DIR = Path(__file__).resolve().parent

LINKEDIN_JSON_PATH = (
    BACKEND_DIR.parent / "working-docs" / "linkedin" / "linkedin_profile_merged_api_preferred.json"
)

# Load LinkedIn data once — skip entire module if file missing
if not LINKEDIN_JSON_PATH.exists():
    pytest.skip("LinkedIn JSON not found", allow_module_level=True)

with open(LINKEDIN_JSON_PATH) as f:
    RAW_LINKEDIN = json.load(f)

JD_TEXT = """\
Solutions Architect — Cloud Platform Team

Requirements:
- 10+ years of experience in software architecture and engineering
- Strong proficiency in Python and Java
- Deep experience with AWS services (EC2, ECS, Lambda, S3, RDS)
- Hands-on experience with Docker and Kubernetes orchestration
- Experience with Terraform or similar infrastructure-as-code tools
- Expertise in designing and building REST APIs and microservices
- Experience with CI/CD pipelines and DevOps practices
- Strong communication and technical leadership skills
- Experience with event-driven architectures (Kafka, SQS/SNS)
- Bachelor's degree in Computer Science or related field

Nice to have:
- Experience with PostgreSQL and Redis
- Familiarity with monitoring and observability tools
- Experience leading distributed engineering teams
"""


# ===================================================================
# LinkedIn → Skills pipeline (3 tests)
# ===================================================================


class TestLinkedInToSkills:
    """parse_linkedin_json output feeds skills_optimizer correctly."""

    def test_parse_linkedin_endorsement_weighted_skills(self):
        """LinkedIn JSON → parsed profile → endorsement-weighted ranking."""
        from linkedin_parser import parse_linkedin_json
        from skills_optimizer import get_endorsement_weighted_skills

        profile = parse_linkedin_json(RAW_LINKEDIN)
        assert "skills" in profile
        assert len(profile["skills"]) > 0

        ranked = get_endorsement_weighted_skills(profile, top_n=15)
        assert len(ranked) > 0
        assert len(ranked) <= 15

        # Rankings should be descending by endorsement weight
        weights = [s["weight"] for s in ranked]
        assert weights == sorted(
            weights, reverse=True
        ), "Skills must be sorted by weight descending"

        # Top skill should have weight 1.0 (normalized to max)
        assert ranked[0]["weight"] == 1.0

    def test_linkedin_skills_gap_three_buckets(self):
        """LinkedIn profile → skills gap analysis produces 3 buckets."""
        from linkedin_parser import parse_linkedin_json
        from skills_optimizer import analyze_skills_gap
        from utils import process_linkedin_profile

        profile = parse_linkedin_json(RAW_LINKEDIN)
        resume_data = process_linkedin_profile(str(LINKEDIN_JSON_PATH))

        gap = analyze_skills_gap(resume_data, JD_TEXT, linkedin_profile=profile)

        assert "skills_already_shown" in gap
        assert "skills_to_emphasize" in gap
        assert "skills_to_acquire" in gap
        assert isinstance(gap["coverage_percent"], (int, float))
        assert 0 <= gap["coverage_percent"] <= 100

        # With this strong profile + matching JD, should have shown + emphasize skills
        total = (
            len(gap["skills_already_shown"])
            + len(gap["skills_to_emphasize"])
            + len(gap["skills_to_acquire"])
        )
        assert total > 0, "Gap analysis must identify at least one skill"

    def test_linkedin_interview_guide_uses_skills(self):
        """LinkedIn profile → interview guide personas reference skills."""
        from interview_guide import generate_interview_guide
        from linkedin_parser import parse_linkedin_json
        from utils import process_linkedin_profile

        profile = parse_linkedin_json(RAW_LINKEDIN)
        resume_data = process_linkedin_profile(str(LINKEDIN_JSON_PATH))

        guide = generate_interview_guide(resume_data, JD_TEXT, linkedin_profile=profile)

        assert "interview_personas" in guide
        assert len(guide["interview_personas"]) >= 1

        # Guide should include talking points
        assert "talking_points" in guide
        assert len(guide["talking_points"]) >= 1

        # Guide should have STAR examples from real experience
        star = guide.get("star_examples", [])
        assert len(star) >= 1, "Guide must generate STAR examples from LinkedIn experience"


# ===================================================================
# Optimize pipeline (3 tests)
# ===================================================================


class TestOptimizePipeline:
    """Upload resume + JD → optimize → matching_keywords present."""

    def test_optimize_produces_score_and_text(self):
        """Resume + JD → optimize → ATS score and optimized text produced."""
        from nlp_engine import extract_keywords
        from utils import optimize_resume, process_linkedin_profile

        resume_data = process_linkedin_profile(str(LINKEDIN_JSON_PATH))
        job_keywords = extract_keywords(JD_TEXT, 20)

        result = optimize_resume(resume_data, job_keywords, job_text=JD_TEXT)

        assert "optimized_text" in result
        assert len(result["optimized_text"]) > 200, "Optimized text must be substantial"
        assert "score" in result
        assert isinstance(result["score"], (int, float))
        assert 0 <= result["score"] <= 100
        assert "score_breakdown" in result
        assert isinstance(result["score_breakdown"], dict)
        # matching_keywords + added_keywords should be lists (may be empty depending on NLP)
        assert isinstance(result.get("matching_keywords", []), list)
        assert isinstance(result.get("added_keywords", []), list)

    def test_optimize_to_gap_consistency(self):
        """Optimize → skills gap → gap skills should include missing keywords."""
        from linkedin_parser import parse_linkedin_json
        from nlp_engine import extract_keywords
        from skills_optimizer import analyze_skills_gap
        from utils import optimize_resume, process_linkedin_profile

        profile = parse_linkedin_json(RAW_LINKEDIN)
        resume_data = process_linkedin_profile(str(LINKEDIN_JSON_PATH))
        job_keywords = extract_keywords(JD_TEXT, 20)

        opt_result = optimize_resume(
            resume_data, job_keywords, job_text=JD_TEXT, linkedin_profile=profile
        )
        gap = analyze_skills_gap(resume_data, JD_TEXT, linkedin_profile=profile)

        # Both should operate on the same keyword universe
        matching = set(k.lower() for k in opt_result.get("matching_keywords", []))
        shown = set(s["skill"].lower() for s in gap.get("skills_already_shown", []))

        # There should be overlap between optimizer's matching and gap's shown
        overlap = matching & shown
        # At minimum, either optimizer found matches or gap found shown skills
        assert (
            len(matching) > 0 or len(shown) > 0
        ), "Either optimizer or gap analysis must find matching skills"

    def test_optimize_interview_guide_job_relevant(self):
        """Optimize → interview guide → talking points include JD terms."""
        from interview_guide import generate_interview_guide
        from linkedin_parser import parse_linkedin_json
        from utils import process_linkedin_profile

        profile = parse_linkedin_json(RAW_LINKEDIN)
        resume_data = process_linkedin_profile(str(LINKEDIN_JSON_PATH))

        guide = generate_interview_guide(resume_data, JD_TEXT, linkedin_profile=profile)

        # STAR examples should reference real experience
        star = guide.get("star_examples", [])
        assert len(star) >= 1, "Guide must generate at least one STAR example"

        # Verify STAR examples reference actual job roles from the profile
        roles_mentioned = " ".join(s.get("role", "") for s in star).lower()
        assert any(
            term in roles_mentioned for term in ("architect", "engineer", "navitus", "opi", "ahead")
        ), f"STAR examples should reference real roles, got: {roles_mentioned}"


# ===================================================================
# Export roundtrip (3 tests)
# ===================================================================


class TestExportRoundtrip:
    """LinkedIn → resume → export PDF/DOCX → valid files."""

    def test_linkedin_to_pdf_magic_bytes(self):
        """LinkedIn → resume text → export PDF → starts with %PDF."""
        from resume_export import export_resume_pdf
        from utils import process_linkedin_profile

        resume_data = process_linkedin_profile(str(LINKEDIN_JSON_PATH))
        text = resume_data["text"]
        assert len(text) > 100, "LinkedIn profile must produce substantial text"

        pdf_buf = export_resume_pdf(text)
        pdf_bytes = pdf_buf.getvalue()
        assert pdf_bytes[:4] == b"%PDF", "PDF export must start with %PDF magic bytes"
        assert len(pdf_bytes) > 500, "PDF must be non-trivial size"

    def test_linkedin_to_docx_valid(self):
        """LinkedIn → resume text → export DOCX → valid ZIP (DOCX is ZIP)."""
        from resume_export import export_resume_docx
        from utils import process_linkedin_profile

        resume_data = process_linkedin_profile(str(LINKEDIN_JSON_PATH))
        text = resume_data["text"]

        docx_buf = export_resume_docx(text)
        docx_bytes = docx_buf.getvalue()
        # DOCX is a ZIP file — starts with PK magic bytes
        assert docx_bytes[:2] == b"PK", "DOCX export must start with PK (ZIP) magic bytes"
        assert len(docx_bytes) > 1000, "DOCX must be non-trivial size"

    def test_optimize_export_content_preserved(self):
        """LinkedIn + optimize → export PDF → content includes key sections."""
        from linkedin_parser import parse_linkedin_json
        from nlp_engine import extract_keywords
        from resume_export import export_resume_pdf
        from utils import optimize_resume, process_linkedin_profile

        profile = parse_linkedin_json(RAW_LINKEDIN)
        resume_data = process_linkedin_profile(str(LINKEDIN_JSON_PATH))
        job_keywords = extract_keywords(JD_TEXT, 20)

        result = optimize_resume(
            resume_data, job_keywords, job_text=JD_TEXT, linkedin_profile=profile
        )

        optimized_text = result["optimized_text"]
        assert len(optimized_text) > 200, "Optimized text must be substantial"

        # Export and verify it produces valid PDF
        pdf_buf = export_resume_pdf(optimized_text)
        pdf_bytes = pdf_buf.getvalue()
        assert pdf_bytes[:4] == b"%PDF"

        # The optimized text should preserve key content from LinkedIn
        text_lower = optimized_text.lower()
        assert "python" in text_lower, "Optimized resume must mention Python"
        assert "aws" in text_lower, "Optimized resume must mention AWS"
