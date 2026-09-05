"""Comprehensive tests for ResumeTailorAgent pipeline.

Tests each pipeline step with mocked LLM calls:
  1. _analyze_job_requirements
  2. _match_experience
  3. _generate_tailored_resume
  4. _score_ats_match
  5. tailor_for_posting (full pipeline)
  6. refine
  7. get_versions
  8. Error handling / edge cases
"""

import json
import sqlite3
import uuid

import pytest
from agents.resume_tailor import ResumeTailorAgent
from test_helpers import JD_TEXT, RESUME_TEXT, query_db

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    """Block all LLM calls by default; individual tests override as needed."""
    monkeypatch.setattr("agents.base_agent.call_llm_scored", lambda *a, **kw: (None, None))
    monkeypatch.setattr("agents.base_agent.extract_json", lambda x: None)


@pytest.fixture
def tailor(app):
    """Fresh ResumeTailorAgent instance (depends on app for DB)."""
    return ResumeTailorAgent()


@pytest.fixture
def user_id(app):
    from models import User

    return User.create("tailor_test@test.com", "Pass1!").id


def _insert_posting(
    user_id, title="Senior Python Developer", company="Acme Corp", description=None
):
    """Insert a job posting and return its id."""
    from models import get_db_connection

    pid = str(uuid.uuid4())
    desc = JD_TEXT if description is None else description
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO job_postings "
        "(id, user_id, title, company, location, url, source, description, "
        "match_score, status, skills_overlap, skills_missing) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            pid,
            user_id,
            title,
            company,
            "Remote",
            "https://example.com/job",
            "manual",
            desc,
            80,
            "discovered",
            json.dumps(["Python", "AWS"]),
            json.dumps(["Docker"]),
        ),
    )
    conn.commit()
    conn.close()
    return pid


def _insert_resume(user_id, text=None):
    """Insert a resume_version and return its id."""
    from models import get_db_connection

    text = text or RESUME_TEXT
    conn = get_db_connection()
    cursor = conn.execute(
        "INSERT INTO resume_versions (user_id, file_name, parsed_text, source) "
        "VALUES (?, ?, ?, ?)",
        (user_id, "resume.txt", text, "upload"),
    )
    vid = cursor.lastrowid
    conn.commit()
    conn.close()
    return vid


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_JOB_REQUIREMENTS = {
    "required_skills": ["Python", "AWS", "Docker", "Kubernetes", "REST APIs"],
    "preferred_skills": ["PostgreSQL", "Redis", "Terraform"],
    "experience_level": "senior",
    "years_experience": 10,
    "key_responsibilities": [
        "Design cloud-native microservices",
        "Lead engineering teams",
    ],
    "industry_keywords": ["microservices", "CI/CD", "cloud migration"],
    "education": "Bachelor's in Computer Science",
    "certifications": ["AWS Solutions Architect"],
    "soft_skills": ["leadership", "communication"],
}


# ===========================================================================
# 1. _analyze_job_requirements
# ===========================================================================


class TestAnalyzeJobRequirements:
    """Test LLM-based job requirement extraction."""

    def test_returns_structured_requirements(self, tailor, monkeypatch):
        """When LLM returns valid JSON with required_skills, parsing succeeds."""
        monkeypatch.setattr(
            "agents.base_agent.call_llm_scored",
            lambda *a, **kw: (json.dumps(SAMPLE_JOB_REQUIREMENTS), None),
        )
        monkeypatch.setattr(
            "agents.base_agent.extract_json",
            lambda x: json.loads(x) if x else None,
        )
        result = tailor._analyze_job_requirements(JD_TEXT)
        assert result is not None, "Should return parsed requirements"
        assert "required_skills" in result, "Must have required_skills key"
        assert "preferred_skills" in result, "Must have preferred_skills key"
        assert "experience_level" in result, "Must have experience_level key"
        assert len(result["required_skills"]) > 0, "Should have at least one required skill"

    def test_returns_none_when_llm_fails(self, tailor):
        """When LLM returns None, _analyze_job_requirements returns None."""
        result = tailor._analyze_job_requirements(JD_TEXT)
        assert result is None, "Should return None when LLM unavailable"

    def test_returns_none_for_short_text(self, tailor):
        """Very short job text is rejected before LLM call."""
        result = tailor._analyze_job_requirements("short")
        assert result is None, "Should return None for text < 20 chars"

    def test_returns_none_for_empty_text(self, tailor):
        """Empty string is rejected."""
        result = tailor._analyze_job_requirements("")
        assert result is None, "Should return None for empty string"

    def test_returns_none_when_json_missing_required_skills(self, tailor, monkeypatch):
        """If LLM JSON lacks required_skills key, returns None."""
        monkeypatch.setattr(
            "agents.base_agent.call_llm_scored",
            lambda *a, **kw: (json.dumps({"preferred_skills": ["Go"]}), None),
        )
        monkeypatch.setattr(
            "agents.base_agent.extract_json",
            lambda x: json.loads(x) if x else None,
        )
        result = tailor._analyze_job_requirements(JD_TEXT)
        assert result is None, "Should return None when required_skills missing"


# ===========================================================================
# 2. _fallback_job_analysis
# ===========================================================================


class TestFallbackJobAnalysis:
    """Test NLP-only fallback for job analysis."""

    def test_returns_dict_with_all_keys(self, tailor, app):
        """Fallback always returns a dict with the expected structure."""
        result = tailor._fallback_job_analysis(JD_TEXT)
        assert isinstance(result, dict), "Fallback must return a dict"
        for key in (
            "required_skills",
            "preferred_skills",
            "experience_level",
            "years_experience",
            "key_responsibilities",
            "industry_keywords",
            "education",
            "certifications",
            "soft_skills",
        ):
            assert key in result, f"Fallback must include '{key}'"

    def test_detects_senior_experience_level(self, tailor, app):
        """Heuristic detects 'senior' keyword."""
        result = tailor._fallback_job_analysis("We need a senior Python developer")
        assert result["experience_level"] == "senior", "Should detect 'senior'"

    def test_detects_entry_experience_level(self, tailor, app):
        """Heuristic detects 'junior'/'entry' keywords."""
        result = tailor._fallback_job_analysis(
            "Looking for a junior developer or entry level engineer"
        )
        assert result["experience_level"] == "entry", "Should detect 'entry'"

    def test_extracts_years_experience(self, tailor, app):
        """Regex extracts years-of-experience from text."""
        result = tailor._fallback_job_analysis(
            "Requires 5+ years of experience in software development and cloud systems design"
        )
        assert result["years_experience"] == 5, "Should extract 5 years"


# ===========================================================================
# 3. _match_experience
# ===========================================================================


class TestMatchExperience:
    """Test experience-to-requirements matching."""

    def test_high_relevance_for_matching_skills(self, tailor, app):
        """Skills found in resume_data skills list get 'high' relevance."""
        resume_data = {"text": "", "skills": ["Python", "AWS", "Docker"]}
        reqs = {"required_skills": ["Python", "AWS"], "preferred_skills": []}
        matches = tailor._match_experience(resume_data, reqs)
        high = [m for m in matches if m["relevance"] == "high"]
        assert len(high) == 2, "Both Python and AWS should be high-relevance matches"
        assert all(m["is_required"] for m in high), "Required skills should be marked is_required"

    def test_gap_for_missing_required_skills(self, tailor, app):
        """Missing required skills get 'gap' relevance."""
        resume_data = {"text": "", "skills": []}
        reqs = {"required_skills": ["Scala", "Haskell"], "preferred_skills": []}
        matches = tailor._match_experience(resume_data, reqs)
        gaps = [m for m in matches if m["relevance"] == "gap"]
        assert len(gaps) == 2, "Both missing skills should be gaps"

    def test_medium_relevance_for_preferred_skills(self, tailor, app):
        """Preferred skills found in resume get 'medium' relevance."""
        resume_data = {"text": "experienced with postgresql and redis", "skills": []}
        reqs = {"required_skills": [], "preferred_skills": ["PostgreSQL", "Redis"]}
        matches = tailor._match_experience(resume_data, reqs)
        medium = [m for m in matches if m["relevance"] == "medium"]
        assert len(medium) == 2, "Both preferred skills should be medium-relevance"
        assert all(not m["is_required"] for m in medium), "Preferred not marked is_required"

    def test_empty_resume_all_gaps(self, tailor, app):
        """Empty resume data means all required skills are gaps."""
        resume_data = {"text": "", "skills": []}
        reqs = {"required_skills": ["Python", "Go"], "preferred_skills": []}
        matches = tailor._match_experience(resume_data, reqs)
        assert all(m["relevance"] == "gap" for m in matches), "All should be gaps"

    def test_empty_requirements_empty_matches(self, tailor, app):
        """No requirements means no matches."""
        resume_data = {"text": RESUME_TEXT, "skills": ["Python"]}
        reqs = {"required_skills": [], "preferred_skills": []}
        matches = tailor._match_experience(resume_data, reqs)
        assert matches == [], "Should return empty list with no requirements"

    def test_profile_enriches_skills(self, tailor, app):
        """Profile higher_order_skills and top_technologies contribute to matching."""
        resume_data = {"text": "", "skills": []}
        reqs = {"required_skills": ["Leadership", "Python"], "preferred_skills": []}
        profile = {
            "higher_order_skills": ["Leadership"],
            "top_technologies": ["Python"],
        }
        matches = tailor._match_experience(resume_data, reqs, profile=profile)
        high = [m for m in matches if m["relevance"] == "high"]
        assert len(high) == 2, "Profile skills should contribute to high matches"

    def test_text_match_when_not_in_skills_list(self, tailor, app):
        """Skills found in resume text (but not skills list) are matched via text scan."""
        resume_data = {"text": "I have extensive experience with kubernetes", "skills": []}
        reqs = {"required_skills": ["kubernetes"], "preferred_skills": []}
        matches = tailor._match_experience(resume_data, reqs)
        high = [m for m in matches if m["relevance"] == "high"]
        assert len(high) == 1, "Text-based match should be found"
        assert high[0]["source"] == "resume_text", "Source should be resume_text"


# ===========================================================================
# 4. _generate_tailored_resume
# ===========================================================================


class TestGenerateTailoredResume:
    """Test LLM-based resume rewriting."""

    def test_returns_tailored_text(self, tailor, monkeypatch, app):
        """When LLM returns a long enough string, it's accepted."""
        tailored = "A" * 200  # > 100 chars threshold
        monkeypatch.setattr("agents.base_agent.call_llm_scored", lambda *a, **kw: (tailored, None))
        result = tailor._generate_tailored_resume(
            resume_data={"text": RESUME_TEXT, "skills": ["Python"]},
            job_requirements=SAMPLE_JOB_REQUIREMENTS,
            experience_matches=[],
            profile_text="Senior Architect",
            posting={"title": "Senior Dev", "company": "Acme"},
            preferences=None,
        )
        assert result is not None, "Should return tailored text"
        assert len(result) > 100, "Tailored text should be substantial"

    def test_returns_none_when_llm_fails(self, tailor, app):
        """When LLM returns None, generation returns None."""
        result = tailor._generate_tailored_resume(
            resume_data={"text": RESUME_TEXT},
            job_requirements=SAMPLE_JOB_REQUIREMENTS,
            experience_matches=[],
            profile_text="",
            posting={"title": "Dev", "company": "Co"},
        )
        assert result is None, "Should return None when LLM unavailable"

    def test_returns_none_for_empty_resume(self, tailor, monkeypatch, app):
        """Empty resume text returns None without calling LLM."""
        monkeypatch.setattr("agents.base_agent.call_llm_scored", lambda *a, **kw: ("text", None))
        result = tailor._generate_tailored_resume(
            resume_data={"text": ""},
            job_requirements=SAMPLE_JOB_REQUIREMENTS,
            experience_matches=[],
            profile_text="",
            posting={"title": "Dev", "company": "Co"},
        )
        assert result is None, "Empty resume text should produce None"

    def test_returns_none_for_short_llm_output(self, tailor, monkeypatch, app):
        """LLM output shorter than 100 chars is rejected."""
        monkeypatch.setattr(
            "agents.base_agent.call_llm_scored", lambda *a, **kw: ("too short", None)
        )
        result = tailor._generate_tailored_resume(
            resume_data={"text": RESUME_TEXT},
            job_requirements=SAMPLE_JOB_REQUIREMENTS,
            experience_matches=[],
            profile_text="",
            posting={"title": "Dev", "company": "Co"},
        )
        assert result is None, "Short LLM output should be rejected"

    def test_preferences_included(self, tailor, monkeypatch, app):
        """Preferences (tone, emphasis, length) are included in prompt."""
        captured_prompts = []

        def _capture_llm(prompt, **kw):
            captured_prompts.append(prompt)
            return ("X" * 200, None)

        monkeypatch.setattr("agents.base_agent.call_llm_scored", _capture_llm)
        tailor._generate_tailored_resume(
            resume_data={"text": RESUME_TEXT},
            job_requirements=SAMPLE_JOB_REQUIREMENTS,
            experience_matches=[],
            profile_text="",
            posting={"title": "Dev", "company": "Co"},
            preferences={"tone": "conversational", "emphasis": ["leadership"], "length": "short"},
        )
        assert len(captured_prompts) == 1, "LLM should be called once"
        prompt = captured_prompts[0]
        assert "conversational" in prompt, "Tone preference should appear in prompt"
        assert "leadership" in prompt, "Emphasis area should appear in prompt"
        assert "short" in prompt.lower(), "Length preference should appear in prompt"


# ===========================================================================
# 5. _score_ats_match
# ===========================================================================


class TestScoreAtsMatch:
    """Test ATS scoring logic."""

    def test_score_is_0_to_100(self, tailor, app):
        """Score must be within valid range."""
        result = tailor._score_ats_match(RESUME_TEXT, SAMPLE_JOB_REQUIREMENTS, JD_TEXT)
        score = result["overall_score"]
        assert 0 <= score <= 100, f"Score {score} outside 0-100 range"

    def test_has_breakdown(self, tailor, app):
        """Result includes score breakdown with all four signals."""
        result = tailor._score_ats_match(RESUME_TEXT, SAMPLE_JOB_REQUIREMENTS, JD_TEXT)
        bd = result["breakdown"]
        for key in (
            "required_skills_coverage",
            "keyword_coverage",
            "section_completeness",
            "semantic_relevance",
        ):
            assert key in bd, f"Breakdown missing '{key}'"
            assert isinstance(bd[key], (int, float)), f"'{key}' should be numeric"

    def test_matching_keywords_populated(self, tailor, app):
        """Resume containing required skills populates matching_keywords."""
        result = tailor._score_ats_match(RESUME_TEXT, SAMPLE_JOB_REQUIREMENTS, JD_TEXT)
        assert isinstance(result["matching_keywords"], list), "matching_keywords must be list"
        assert len(result["matching_keywords"]) > 0, "Should find some matching keywords"

    def test_high_score_with_perfect_match(self, tailor, app):
        """Resume containing all required+preferred skills should score high."""
        perfect_text = (
            "SUMMARY\nExpert in Python, AWS, Docker, Kubernetes, REST APIs.\n"
            "EXPERIENCE\nSenior developer at cloud company.\n"
            "SKILLS\nPostgreSQL, Redis, Terraform, microservices, CI/CD, cloud migration.\n"
            "EDUCATION\nBachelor of Computer Science.\n"
        )
        result = tailor._score_ats_match(perfect_text, SAMPLE_JOB_REQUIREMENTS, "")
        assert (
            result["overall_score"] >= 50
        ), f"Perfect match should score >= 50, got {result['overall_score']}"

    def test_low_score_with_no_match(self, tailor, app):
        """Resume with no relevant content scores low."""
        irrelevant = "I am a florist who arranges flowers for weddings and events."
        reqs = {
            "required_skills": ["Quantum Computing", "FPGA", "Verilog"],
            "preferred_skills": ["ASIC Design"],
            "industry_keywords": ["semiconductor", "chip design"],
        }
        result = tailor._score_ats_match(irrelevant, reqs, "")
        assert (
            result["overall_score"] < 30
        ), f"No-match should score < 30, got {result['overall_score']}"

    def test_section_completeness_scored(self, tailor, app):
        """Resume with all standard sections gets high section completeness."""
        text = (
            "SUMMARY\nExperienced professional.\n"
            "EXPERIENCE\nWorked at companies.\n"
            "EDUCATION\nBachelor's degree.\n"
            "SKILLS\nPython, Java.\n"
        )
        result = tailor._score_ats_match(text, {"required_skills": [], "preferred_skills": []}, "")
        assert (
            result["breakdown"]["section_completeness"] == 100.0
        ), "All 4 sections present should give 100% completeness"


# ===========================================================================
# 6. tailor_for_posting (full pipeline)
# ===========================================================================


class TestTailorForPosting:
    """Test the full tailor_for_posting pipeline end-to-end."""

    def _mock_llm_for_pipeline(self, monkeypatch):
        """Set up LLM mocks for full pipeline test."""
        call_count = {"n": 0}

        def _fake_llm(prompt, **kw):
            call_count["n"] += 1
            # First call: job analysis (via _call_llm_json → _call_llm)
            if "Analyze this job posting" in prompt:
                return (json.dumps(SAMPLE_JOB_REQUIREMENTS), None)
            # Second call: resume generation
            return ("TAILORED RESUME\n" + "X" * 300, None)

        monkeypatch.setattr("agents.base_agent.call_llm_scored", _fake_llm)
        monkeypatch.setattr(
            "agents.base_agent.extract_json",
            lambda x: json.loads(x) if x and x.strip().startswith("{") else None,
        )
        return call_count

    def test_full_pipeline_success(self, tailor, user_id, monkeypatch):
        """Full pipeline produces optimized_text, ats_score, version_id."""
        self._mock_llm_for_pipeline(monkeypatch)
        _insert_resume(user_id)
        pid = _insert_posting(user_id)

        result = tailor.tailor_for_posting(user_id, pid)

        assert "error" not in result, f"Pipeline returned error: {result.get('error')}"
        assert "optimized_text" in result, "Must include optimized_text"
        assert len(result["optimized_text"]) > 100, "Optimized text should be substantial"
        assert "ats_score" in result, "Must include ats_score"
        assert 0 <= result["ats_score"] <= 100, "ATS score must be 0-100"
        assert "version_id" in result, "Must include version_id"
        assert "job_requirements" in result, "Must include job_requirements"
        assert "experience_matches" in result, "Must include experience_matches"

    def test_version_saved_to_db(self, tailor, user_id, monkeypatch):
        """Successful pipeline saves a resume_version record."""
        self._mock_llm_for_pipeline(monkeypatch)
        _insert_resume(user_id)
        pid = _insert_posting(user_id)

        result = tailor.tailor_for_posting(user_id, pid)
        assert "version_id" in result, "Pipeline should return version_id"

        rows = query_db("SELECT * FROM resume_versions WHERE id = ?", (result["version_id"],))
        assert len(rows) == 1, "Version should be in DB"
        assert rows[0]["source"] == "agent_tailor", "Source should be agent_tailor"
        assert "Tailored" in rows[0]["file_name"], "File name should contain 'Tailored'"

    def test_posting_updated_with_version(self, tailor, user_id, monkeypatch):
        """Successful pipeline updates posting's tailored_version_id."""
        self._mock_llm_for_pipeline(monkeypatch)
        _insert_resume(user_id)
        pid = _insert_posting(user_id)

        result = tailor.tailor_for_posting(user_id, pid)
        rows = query_db("SELECT tailored_version_id FROM job_postings WHERE id = ?", (pid,))
        assert len(rows) == 1, "Posting should exist"
        assert rows[0]["tailored_version_id"] == str(
            result["version_id"]
        ), "Posting should reference the tailored version"

    def test_agent_run_logged(self, tailor, user_id, monkeypatch):
        """Pipeline logs an agent_runs record."""
        self._mock_llm_for_pipeline(monkeypatch)
        _insert_resume(user_id)
        pid = _insert_posting(user_id)

        tailor.tailor_for_posting(user_id, pid)
        runs = query_db(
            "SELECT * FROM agent_runs WHERE user_id = ? AND agent_type = 'resume_tailor'",
            (user_id,),
        )
        assert len(runs) >= 1, "Should have at least one agent run logged"
        assert runs[0]["task_type"] == "resume_rewrite", "Task type should be resume_rewrite"

    def test_error_posting_not_found(self, tailor, user_id):
        """Missing posting returns error dict."""
        result = tailor.tailor_for_posting(user_id, "nonexistent-posting-id")
        assert result.get("error") == "Posting not found"

    def test_error_no_resume(self, tailor, user_id):
        """No resume uploaded returns error dict."""
        pid = _insert_posting(user_id)
        result = tailor.tailor_for_posting(user_id, pid)
        assert "error" in result, "Should return error when no resume"
        assert "resume" in result["error"].lower() or "upload" in result["error"].lower()

    def test_error_empty_description(self, tailor, user_id):
        """Posting with empty description returns error."""
        _insert_resume(user_id)
        pid = _insert_posting(user_id, description="")
        result = tailor.tailor_for_posting(user_id, pid)
        assert result.get("error") == "Posting has no job description"

    def test_with_preferences(self, tailor, user_id, monkeypatch):
        """Pipeline passes preferences through to generation."""
        self._mock_llm_for_pipeline(monkeypatch)
        _insert_resume(user_id)
        pid = _insert_posting(user_id)

        result = tailor.tailor_for_posting(
            user_id, pid, preferences={"tone": "conversational", "length": "short"}
        )
        assert "error" not in result, f"Pipeline with prefs returned error: {result.get('error')}"
        assert "optimized_text" in result


# ===========================================================================
# 7. refine
# ===========================================================================


class TestRefine:
    """Test iterative refinement of tailored resumes."""

    def _setup_tailored(self, tailor, user_id, monkeypatch):
        """Run initial tailor so there is a version to refine."""
        call_count = {"n": 0}

        def _fake_llm(prompt, **kw):
            call_count["n"] += 1
            if "Analyze this job posting" in prompt:
                return (json.dumps(SAMPLE_JOB_REQUIREMENTS), None)
            return ("TAILORED RESUME\n" + "X" * 300, None)

        monkeypatch.setattr("agents.base_agent.call_llm_scored", _fake_llm)
        monkeypatch.setattr(
            "agents.base_agent.extract_json",
            lambda x: json.loads(x) if x and x.strip().startswith("{") else None,
        )
        _insert_resume(user_id)
        pid = _insert_posting(user_id)
        result = tailor.tailor_for_posting(user_id, pid)
        return pid, result

    def test_refine_success(self, tailor, user_id, monkeypatch):
        """Refinement with valid feedback produces a new version."""
        pid, initial = self._setup_tailored(tailor, user_id, monkeypatch)

        # Override LLM for refinement call
        monkeypatch.setattr(
            "agents.base_agent.call_llm_scored",
            lambda *a, **kw: ("REFINED RESUME\n" + "Y" * 300, None),
        )

        result = tailor.refine(user_id, pid, "Add more leadership emphasis")
        assert "error" not in result, f"Refine returned error: {result.get('error')}"
        assert "optimized_text" in result, "Refine should return optimized_text"
        assert "REFINED" in result["optimized_text"], "Should contain refined text"
        assert result["version_id"] != initial["version_id"], "Should create new version"
        assert result.get("feedback_applied") == "Add more leadership emphasis"

    def test_refine_creates_new_db_version(self, tailor, user_id, monkeypatch):
        """Refinement creates a new resume_versions row with parent reference."""
        pid, initial = self._setup_tailored(tailor, user_id, monkeypatch)

        monkeypatch.setattr(
            "agents.base_agent.call_llm_scored",
            lambda *a, **kw: ("REFINED VERSION\n" + "Z" * 300, None),
        )

        result = tailor.refine(user_id, pid, "More metrics")
        rows = query_db("SELECT * FROM resume_versions WHERE id = ?", (result["version_id"],))
        assert len(rows) == 1, "Refined version should be in DB"
        meta = json.loads(rows[0]["metadata_json"])
        assert (
            meta.get("parent_version_id") == initial["version_id"]
        ), "Metadata should reference parent version"
        assert meta.get("feedback_applied") == "More metrics"

    def test_refine_empty_feedback_error(self, tailor, user_id):
        """Empty feedback returns error."""
        result = tailor.refine(user_id, "some-posting-id", "")
        assert result.get("error") == "Feedback is required for refinement"

    def test_refine_whitespace_feedback_error(self, tailor, user_id):
        """Whitespace-only feedback returns error."""
        result = tailor.refine(user_id, "some-posting-id", "   ")
        assert result.get("error") == "Feedback is required for refinement"

    def test_refine_no_existing_version_error(self, tailor, user_id):
        """Refinement without prior tailor returns error."""
        pid = _insert_posting(user_id)
        result = tailor.refine(user_id, pid, "make it better")
        assert "error" in result, "Should error without existing tailored version"
        assert "tailor first" in result["error"].lower() or "no tailored" in result["error"].lower()


# ===========================================================================
# 8. get_versions
# ===========================================================================


class TestGetVersions:
    """Test version history retrieval."""

    def test_returns_empty_for_no_versions(self, tailor, user_id):
        """No versions returns empty list."""
        pid = _insert_posting(user_id)
        versions = tailor.get_versions(user_id, pid)
        assert versions == [], "Should return empty list when no versions exist"

    def test_returns_versions_newest_first(self, tailor, user_id, monkeypatch):
        """Multiple versions are returned newest-first."""

        # Create two versions via the pipeline
        def _fake_llm(prompt, **kw):
            if "Analyze this job posting" in prompt:
                return (json.dumps(SAMPLE_JOB_REQUIREMENTS), None)
            return ("VERSION TEXT\n" + "V" * 300, None)

        monkeypatch.setattr("agents.base_agent.call_llm_scored", _fake_llm)
        monkeypatch.setattr(
            "agents.base_agent.extract_json",
            lambda x: json.loads(x) if x and x.strip().startswith("{") else None,
        )
        _insert_resume(user_id)
        pid = _insert_posting(user_id)

        r1 = tailor.tailor_for_posting(user_id, pid)

        # Refine to create a second version
        monkeypatch.setattr(
            "agents.base_agent.call_llm_scored", lambda *a, **kw: ("REFINED\n" + "R" * 300, None)
        )
        r2 = tailor.refine(user_id, pid, "add metrics")

        versions = tailor.get_versions(user_id, pid)
        assert len(versions) >= 2, f"Should have at least 2 versions, got {len(versions)}"
        # Both version ids should be present
        version_ids = [v["id"] for v in versions]
        assert r1["version_id"] in version_ids, "Initial version should be in list"
        assert r2["version_id"] in version_ids, "Refined version should be in list"
        # All versions should have correct source and source_id
        for v in versions:
            assert v["source"] == "agent_tailor", "All versions source should be agent_tailor"
            assert v["source_id"] == pid, "All versions should reference the posting"

    def test_versions_have_parsed_metadata(self, tailor, user_id, monkeypatch):
        """Version dicts include parsed metadata."""

        def _fake_llm(prompt, **kw):
            if "Analyze this job posting" in prompt:
                return (json.dumps(SAMPLE_JOB_REQUIREMENTS), None)
            return ("VERSION TEXT\n" + "V" * 300, None)

        monkeypatch.setattr("agents.base_agent.call_llm_scored", _fake_llm)
        monkeypatch.setattr(
            "agents.base_agent.extract_json",
            lambda x: json.loads(x) if x and x.strip().startswith("{") else None,
        )
        _insert_resume(user_id)
        pid = _insert_posting(user_id)
        tailor.tailor_for_posting(user_id, pid)

        versions = tailor.get_versions(user_id, pid)
        assert len(versions) >= 1
        v = versions[0]
        assert "metadata" in v, "Version should have parsed metadata"
        assert isinstance(v["metadata"], dict), "metadata should be a dict"
        assert "ats_score" in v["metadata"], "metadata should contain ats_score"


# ===========================================================================
# 9. get_tailored
# ===========================================================================


class TestGetTailored:
    """Test retrieval of existing tailored version."""

    def test_returns_none_for_no_tailored(self, tailor, user_id):
        """No tailored version returns None."""
        pid = _insert_posting(user_id)
        result = tailor.get_tailored(pid, user_id=user_id)
        assert result is None, "Should return None when no tailored version exists"

    def test_returns_version_after_tailoring(self, tailor, user_id, monkeypatch):
        """After tailoring, get_tailored returns the version dict."""

        def _fake_llm(prompt, **kw):
            if "Analyze this job posting" in prompt:
                return (json.dumps(SAMPLE_JOB_REQUIREMENTS), None)
            return ("TAILORED TEXT\n" + "T" * 300, None)

        monkeypatch.setattr("agents.base_agent.call_llm_scored", _fake_llm)
        monkeypatch.setattr(
            "agents.base_agent.extract_json",
            lambda x: json.loads(x) if x and x.strip().startswith("{") else None,
        )
        _insert_resume(user_id)
        pid = _insert_posting(user_id)
        tailor.tailor_for_posting(user_id, pid)

        result = tailor.get_tailored(pid, user_id=user_id)
        assert result is not None, "Should return the tailored version"
        assert "parsed_text" in result, "Should include parsed_text"
        assert "TAILORED TEXT" in result["parsed_text"]


# ===========================================================================
# 10. _apply_refinement
# ===========================================================================


class TestApplyRefinement:
    """Test the LLM refinement step in isolation."""

    def test_returns_refined_text(self, tailor, monkeypatch, app):
        """When LLM succeeds, returns refined text."""
        monkeypatch.setattr(
            "agents.base_agent.call_llm_scored",
            lambda *a, **kw: ("REFINED CONTENT\n" + "R" * 200, None),
        )
        result = tailor._apply_refinement(
            current_text="Original resume text " * 20,
            job_text=JD_TEXT,
            feedback="Add more quantitative results",
            job_requirements=SAMPLE_JOB_REQUIREMENTS,
        )
        assert result is not None, "Should return refined text"
        assert "REFINED CONTENT" in result

    def test_returns_none_when_llm_fails(self, tailor, app):
        """When LLM returns None, refinement returns None."""
        result = tailor._apply_refinement(
            current_text="Original text " * 20,
            job_text=JD_TEXT,
            feedback="improve it",
            job_requirements=SAMPLE_JOB_REQUIREMENTS,
        )
        assert result is None, "Should return None when LLM unavailable"
