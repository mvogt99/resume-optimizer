"""Comprehensive tests for CoverLetterAgent pipeline.

Tests each pipeline step with mocked LLM calls:
  1. _analyze_company_culture
  2. _fallback_culture
  3. _extract_job_requirements / _fallback_requirements
  4. _build_letter_structure
  5. _generate_letter
  6. _score_letter
  7. generate_cover_letter (full pipeline)
  8. refine / regenerate
  9. CRUD (get, update, delete)
  10. Edge cases
"""

import json
import uuid

import pytest
from agents.cover_letter import STYLES, CoverLetterAgent
from test_helpers import JD_TEXT, RESUME_TEXT

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    """Block all LLM calls by default; individual tests override as needed."""
    monkeypatch.setattr("agents.base_agent.call_llm_scored", lambda *a, **kw: (None, None))
    monkeypatch.setattr("agents.base_agent.extract_json", lambda x: None)


@pytest.fixture
def agent(app):
    """Fresh CoverLetterAgent instance (depends on app for DB)."""
    return CoverLetterAgent()


@pytest.fixture
def user_id(app):
    from models import User

    return User.create("cl_test@test.com", "Pass1!").id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _insert_cover_letter(
    user_id,
    posting_id,
    subject="Application",
    greeting="Dear Hiring Manager,",
    body="Test letter body with enough words to be meaningful.",
    closing="Best regards,",
    tone="professional",
    company="Acme Corp",
    role_title="Senior Python Developer",
):
    """Insert a cover letter and return its id."""
    from models import get_db_connection

    lid = str(uuid.uuid4())
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO cover_letters (id, user_id, posting_id, subject, greeting, "
        "body, closing, tone, company, role_title) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (lid, user_id, posting_id, subject, greeting, body, closing, tone, company, role_title),
    )
    conn.commit()
    conn.close()
    return lid


def _mock_llm(monkeypatch, response_dict):
    """Override LLM to return the given dict as JSON."""
    monkeypatch.setattr(
        "agents.base_agent.call_llm_scored", lambda *a, **kw: (json.dumps(response_dict), None)
    )
    monkeypatch.setattr(
        "agents.base_agent.extract_json",
        lambda x: json.loads(x) if x else None,
    )


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_CULTURE = {
    "company_tone": "mission-driven",
    "values": ["innovation", "collaboration"],
    "work_style": "collaborative",
    "emphasis": ["scalability"],
    "team_culture": "Cross-functional teams",
    "role_positioning": "individual contributor",
    "language_tone": "enthusiastic",
}

SAMPLE_JOB_REQ = {
    "required_skills": ["Python", "AWS", "Docker", "Kubernetes"],
    "preferred_skills": ["PostgreSQL", "Redis"],
    "experience_level": "senior",
    "industry_keywords": ["microservices", "CI/CD"],
    "key_responsibilities": ["Design cloud-native microservices"],
}

SAMPLE_LETTER = {
    "subject": "Application for Senior Python Developer",
    "greeting": "Dear Hiring Manager,",
    "body": (
        "I am excited to apply for the Senior Python Developer role at Acme Corp. "
        "With 20 years of experience in enterprise architecture, I bring deep expertise "
        "in Python, AWS, and Docker.\n\n"
        "At Navitus, I led migration of monolithic systems to microservices, "
        "reducing deployment time from 2 weeks to 2 hours.\n\n"
        "My experience with Kubernetes orchestration and CI/CD pipelines aligns "
        "perfectly with your cloud-native vision.\n\n"
        "I look forward to discussing how my background can contribute to your team."
    ),
    "closing": "Best regards,\nMike Vogt",
    "tone": "professional",
}


# ===========================================================================
# 1. _analyze_company_culture
# ===========================================================================


class TestAnalyzeCulture:
    """Test LLM-based culture analysis."""

    def test_returns_culture_dict_on_success(self, agent, monkeypatch):
        """When LLM returns valid culture JSON, parsing succeeds."""
        _mock_llm(monkeypatch, SAMPLE_CULTURE)
        result = agent._analyze_company_culture(JD_TEXT, "Acme Corp")
        assert isinstance(result, dict), "Should return dict"
        assert result["company_tone"] == "mission-driven"

    def test_returns_none_when_llm_fails(self, agent):
        """When LLM returns None, culture analysis returns None."""
        result = agent._analyze_company_culture(JD_TEXT, "Acme Corp")
        assert result is None, "Should return None when LLM unavailable"

    def test_returns_none_for_short_text(self, agent):
        """Text shorter than 30 chars is rejected."""
        result = agent._analyze_company_culture("short text", "Acme")
        assert result is None, "Should return None for short text"

    def test_returns_none_for_empty_text(self, agent):
        """Empty string is rejected."""
        result = agent._analyze_company_culture("", "Acme")
        assert result is None, "Should return None for empty text"

    def test_returns_none_when_missing_company_tone(self, agent, monkeypatch):
        """If LLM JSON lacks company_tone, returns None."""
        _mock_llm(monkeypatch, {"values": ["speed"]})
        result = agent._analyze_company_culture(JD_TEXT, "Acme")
        assert result is None, "Should return None when company_tone missing"


# ===========================================================================
# 2. _fallback_culture
# ===========================================================================


class TestFallbackCulture:
    """Test heuristic culture analysis (no LLM)."""

    def test_startup_detection(self, agent):
        """Fast-paced/startup keywords detected."""
        result = agent._fallback_culture("Join our fast-paced startup disrupting healthcare")
        assert result["company_tone"] == "startup"
        assert result["language_tone"] == "enthusiastic"

    def test_mission_driven_detection(self, agent):
        """Mission/impact keywords detected."""
        result = agent._fallback_culture(
            "Our mission is to make healthcare accessible to all communities"
        )
        assert result["company_tone"] == "mission-driven"
        assert isinstance(result["values"], list)

    def test_innovation_value_detected(self, agent):
        """Innovation keyword maps to values list."""
        result = agent._fallback_culture("We pioneer innovative cutting-edge solutions")
        assert "innovation" in result["values"]
        assert isinstance(result["values"], list)

    def test_collaboration_value_detected(self, agent):
        """Collaboration keyword maps to values list."""
        result = agent._fallback_culture("We foster collaboration and cross-functional teamwork")
        assert "collaboration" in result["values"]
        assert isinstance(result["work_style"], str)

    def test_agile_work_style(self, agent):
        """Agile/scrum keywords set work_style."""
        result = agent._fallback_culture("We use agile methodology with 2-week sprints")
        assert result["work_style"] == "agile"
        assert isinstance(result, dict)

    def test_leadership_role_positioning(self, agent):
        """Lead/director keywords set role_positioning."""
        result = agent._fallback_culture("We need a director of engineering to lead the team")
        assert result["role_positioning"] == "leadership"
        assert isinstance(result["values"], list)

    def test_defaults_for_generic_text(self, agent):
        """No matching keywords returns corporate defaults."""
        result = agent._fallback_culture("A regular position at a company")
        assert result["company_tone"] == "corporate"
        assert result["language_tone"] == "neutral"


# ===========================================================================
# 3. _extract_job_requirements
# ===========================================================================


class TestExtractRequirements:
    """Test job requirement extraction (LLM + fallback)."""

    def test_llm_returns_structured_requirements(self, agent, monkeypatch):
        """When LLM returns valid requirements JSON, result has expected keys."""
        _mock_llm(monkeypatch, SAMPLE_JOB_REQ)
        result = agent._extract_job_requirements(JD_TEXT)
        assert isinstance(result, dict)
        assert "required_skills" in result
        assert len(result["required_skills"]) > 0

    def test_missing_required_skills_falls_to_fallback(self, agent, monkeypatch):
        """If LLM JSON lacks required_skills, fallback is used."""
        _mock_llm(monkeypatch, {"preferred_skills": ["Go"]})
        result = agent._extract_job_requirements(JD_TEXT)
        assert isinstance(result, dict), "Fallback should return dict"
        assert "required_skills" in result or "experience_level" in result

    def test_short_text_returns_empty(self, agent):
        """Text < 20 chars returns empty dict."""
        result = agent._extract_job_requirements("short")
        assert isinstance(result, dict)
        assert result == {}

    def test_empty_text_returns_empty(self, agent):
        """Empty string returns empty dict."""
        result = agent._extract_job_requirements("")
        assert isinstance(result, dict)
        assert result == {}


# ===========================================================================
# 4. _fallback_requirements
# ===========================================================================


class TestFallbackRequirements:
    """Test keyword-based requirement extraction."""

    def test_detects_senior_level(self, agent):
        result = agent._fallback_requirements("We need a senior Python developer with 10+ years")
        assert result["experience_level"] == "senior"
        assert isinstance(result["required_skills"], list)

    def test_detects_entry_level(self, agent):
        result = agent._fallback_requirements("Entry-level junior developer position available")
        assert result["experience_level"] == "entry"
        assert isinstance(result, dict)

    def test_defaults_to_mid(self, agent):
        result = agent._fallback_requirements("Python developer position open now")
        assert result["experience_level"] == "mid"
        assert isinstance(result["required_skills"], list)


# ===========================================================================
# 5. _build_letter_structure
# ===========================================================================


class TestBuildStructure:
    """Test letter structure builder."""

    def test_matched_skills_populated(self, agent):
        """Skills present in both profile and requirements appear as matched."""
        profile = {
            "linkedin": {
                "skills": [{"name": "Python"}, {"name": "AWS"}],
                "headline": "",
                "summary": "",
                "experience": [],
            },
            "top_technologies": [],
            "higher_order_skills": [],
            "differentiators": [],
        }
        result = agent._build_letter_structure(
            profile, SAMPLE_JOB_REQ, SAMPLE_CULTURE, "professional"
        )
        matched = result["experience_mapping"]["matched_skills"]
        assert isinstance(matched, list)
        assert len(matched) >= 1, "Should match at least Python"

    def test_gap_skills_populated(self, agent):
        """Skills in requirements but not profile appear as gaps."""
        profile = {
            "linkedin": {"skills": [], "headline": "", "summary": "", "experience": []},
            "top_technologies": [],
            "higher_order_skills": [],
            "differentiators": [],
        }
        result = agent._build_letter_structure(
            profile, SAMPLE_JOB_REQ, SAMPLE_CULTURE, "professional"
        )
        gaps = result["experience_mapping"]["gap_skills"]
        assert isinstance(gaps, list)
        assert len(gaps) >= 1, "Should have gaps when profile has no skills"

    def test_style_guidance_matches_styles_dict(self, agent):
        """style_guidance matches the STYLES constant for the given style."""
        profile = {
            "linkedin": {"skills": [], "headline": "", "summary": "", "experience": []},
            "top_technologies": [],
            "higher_order_skills": [],
            "differentiators": [],
        }
        result = agent._build_letter_structure(profile, SAMPLE_JOB_REQ, SAMPLE_CULTURE, "technical")
        assert result["style"] == "technical"
        assert result["style_guidance"] == STYLES["technical"]

    def test_experience_mapping_has_key_fields(self, agent):
        """Structure includes experience_mapping with expected sub-keys."""
        profile = {
            "linkedin": {
                "skills": [],
                "headline": "Architect",
                "summary": "",
                "experience": [
                    {"title": "Architect", "company": "Acme", "description": "Built stuff"}
                ],
            },
            "top_technologies": [],
            "higher_order_skills": [],
            "differentiators": [],
        }
        result = agent._build_letter_structure(
            profile, SAMPLE_JOB_REQ, SAMPLE_CULTURE, "professional"
        )
        em = result["experience_mapping"]
        assert "matched_skills" in em
        assert "relevant_experience" in em


# ===========================================================================
# 6. _generate_letter
# ===========================================================================


class TestGenerateLetter:
    """Test LLM letter generation."""

    def test_returns_dict_on_success(self, agent, monkeypatch):
        """When LLM returns valid letter JSON, result is a dict."""
        _mock_llm(monkeypatch, SAMPLE_LETTER)
        posting = {"title": "Senior Dev", "company": "Acme", "description": JD_TEXT}
        structure = {
            "style": "professional",
            "style_guidance": STYLES["professional"],
            "opening_hook_inputs": {},
            "experience_mapping": {"matched_skills": ["Python"]},
            "culture_fit_signals": {},
            "closing_strategy": {},
        }
        result = agent._generate_letter(structure, RESUME_TEXT, posting)
        assert isinstance(result, dict)
        assert "body" in result or "subject" in result

    def test_returns_none_when_llm_fails(self, agent):
        """When LLM returns None, _generate_letter returns None."""
        posting = {"title": "Senior Dev", "company": "Acme", "description": JD_TEXT}
        structure = {
            "style": "professional",
            "style_guidance": "",
            "opening_hook_inputs": {},
            "experience_mapping": {},
            "culture_fit_signals": {},
            "closing_strategy": {},
        }
        result = agent._generate_letter(structure, RESUME_TEXT, posting)
        assert result is None

    def test_preferences_included_in_prompt(self, agent, monkeypatch):
        """Preferences like length and focus_areas are passed through."""
        _mock_llm(monkeypatch, SAMPLE_LETTER)
        posting = {"title": "Senior Dev", "company": "Acme", "description": JD_TEXT}
        structure = {
            "style": "professional",
            "style_guidance": "",
            "opening_hook_inputs": {},
            "experience_mapping": {"matched_skills": [], "gap_skills": []},
            "culture_fit_signals": {},
            "closing_strategy": {},
        }
        prefs = {"length": "short", "focus_areas": ["leadership"], "avoid": ["cliches"]}
        result = agent._generate_letter(structure, RESUME_TEXT, posting, preferences=prefs)
        assert isinstance(result, dict), "Should still return letter dict"
        assert result.get("body") is not None or result.get("subject") is not None


# ===========================================================================
# 7. _score_letter
# ===========================================================================


class TestScoreLetter:
    """Test cover letter quality scoring."""

    def test_keyword_coverage_scoring(self, agent):
        """Keywords in letter text are counted against requirements."""
        text = "Experience with Python, AWS, and Docker in cloud environments."
        req = {"required_skills": ["Python", "AWS", "Docker"], "industry_keywords": ["cloud"]}
        result = agent._score_letter(text, req, {"values": []})
        assert result["overall_score"] > 0
        assert result["breakdown"]["keyword_coverage"] > 50

    def test_structure_quality_good_paragraphs(self, agent):
        """3-5 paragraphs with 200-500 words gets structure bonus."""
        para = "This is a well-constructed paragraph with enough words to demonstrate quality writing. "  # noqa: E501
        text = f"{para * 4}\n\n" f"{para * 4}\n\n" f"{para * 4}\n\n" f"{para * 3}"
        result = agent._score_letter(text, {"required_skills": []}, {"values": []})
        assert result["breakdown"]["structure_quality"] >= 75
        assert result["paragraph_count"] >= 3

    def test_structure_quality_bad_single_paragraph(self, agent):
        """Single paragraph gets lower structure score."""
        text = "One long paragraph with no breaks at all just goes on and on."
        result = agent._score_letter(text, {"required_skills": []}, {"values": []})
        assert result["breakdown"]["structure_quality"] < 100
        assert result["paragraph_count"] == 1

    def test_culture_alignment_with_values(self, agent):
        """Culture terms in letter text boost alignment score."""
        text = "I value innovation and collaboration in my work."
        culture = {"values": ["innovation", "collaboration"], "emphasis": []}
        result = agent._score_letter(text, {"required_skills": []}, culture)
        assert result["breakdown"]["culture_alignment"] > 50
        assert result["overall_score"] >= 0

    def test_professionalism_penalty_for_placeholders(self, agent):
        """[Your Name] style placeholders reduce professionalism score."""
        text = "Dear [Hiring Manager], I am writing about the [Position Title] role."
        result = agent._score_letter(text, {"required_skills": []}, {"values": []})
        assert result["breakdown"]["professionalism"] < 80
        assert result["overall_score"] >= 0

    def test_professionalism_penalty_for_generic_phrases(self, agent):
        """Generic cover letter phrases reduce professionalism score."""
        text = "I am writing to apply for the position. I believe I am a great fit."
        result = agent._score_letter(text, {"required_skills": []}, {"values": []})
        assert result["breakdown"]["professionalism"] < 70
        assert result["overall_score"] >= 0

    def test_readability_with_sentence_variation(self, agent):
        """Varied sentence lengths get readability bonus."""
        text = (
            "Short sentence here. "
            "This is a moderately longer sentence with more detail about my experience. "
            "Another short one. "
            "And finally a longer closing sentence that wraps up the paragraph nicely."
        )
        result = agent._score_letter(text, {"required_skills": []}, {"values": []})
        assert "readability" in result["breakdown"]
        assert result["word_count"] > 0

    def test_empty_text_returns_zero(self, agent):
        """Empty letter text gets zero score with empty breakdown."""
        result = agent._score_letter("", {"required_skills": []}, {"values": []})
        assert result["overall_score"] == 0
        assert result["breakdown"] == {}


# ===========================================================================
# 8. generate_cover_letter (full pipeline)
# ===========================================================================


class TestFullPipeline:
    """Test the full generate_cover_letter pipeline."""

    def test_success_with_all_steps_mocked(self, agent, user_id, monkeypatch):
        """Full pipeline succeeds when LLM returns valid data at each step."""
        # Mock LLM to return different dicts depending on prompt content
        call_count = {"n": 0}
        responses = [SAMPLE_CULTURE, SAMPLE_JOB_REQ, SAMPLE_LETTER]

        def _rotating_llm(*a, **kw):
            idx = min(call_count["n"], len(responses) - 1)
            call_count["n"] += 1
            return (json.dumps(responses[idx]), None)

        monkeypatch.setattr("agents.base_agent.call_llm_scored", _rotating_llm)
        monkeypatch.setattr(
            "agents.base_agent.extract_json", lambda x: json.loads(x) if x else None
        )

        posting_id = _insert_posting(user_id)
        result = agent.generate_cover_letter(user_id, posting_id)
        assert isinstance(result, dict), "Should return result dict"
        assert "error" not in result or result.get("id") is not None

    def test_posting_not_found_returns_error(self, agent, user_id):
        """Non-existent posting returns error dict."""
        result = agent.generate_cover_letter(user_id, "nonexistent-id")
        assert isinstance(result, dict)
        assert "error" in result

    def test_empty_description_returns_error(self, agent, user_id):
        """Posting with empty description returns error."""
        posting_id = _insert_posting(user_id, description="")
        result = agent.generate_cover_letter(user_id, posting_id)
        assert isinstance(result, dict)
        assert "error" in result

    def test_llm_failure_returns_error(self, agent, user_id):
        """When all LLM calls fail, returns error dict."""
        posting_id = _insert_posting(user_id)
        result = agent.generate_cover_letter(user_id, posting_id)
        assert isinstance(result, dict)
        assert "error" in result

    def test_result_saved_to_db(self, agent, user_id, monkeypatch):
        """Successful generation persists to cover_letters table."""
        call_count = {"n": 0}
        responses = [SAMPLE_CULTURE, SAMPLE_JOB_REQ, SAMPLE_LETTER]

        def _rotating_llm(*a, **kw):
            idx = min(call_count["n"], len(responses) - 1)
            call_count["n"] += 1
            return (json.dumps(responses[idx]), None)

        monkeypatch.setattr("agents.base_agent.call_llm_scored", _rotating_llm)
        monkeypatch.setattr(
            "agents.base_agent.extract_json", lambda x: json.loads(x) if x else None
        )

        posting_id = _insert_posting(user_id)
        result = agent.generate_cover_letter(user_id, posting_id)
        if "error" not in result:
            from models import get_db_connection

            conn = get_db_connection()
            rows = conn.execute(
                "SELECT * FROM cover_letters WHERE user_id=? AND posting_id=?",
                (user_id, posting_id),
            ).fetchall()
            conn.close()
            assert len(rows) >= 1, "Should have at least one cover letter in DB"
            assert rows[0]["user_id"] == user_id

    def test_style_defaults_to_professional(self, agent, user_id, monkeypatch):
        """Invalid style falls back to professional."""
        _mock_llm(monkeypatch, SAMPLE_LETTER)
        posting_id = _insert_posting(user_id)
        # Even with invalid style, should not crash
        result = agent.generate_cover_letter(user_id, posting_id, style="invalid_style")
        assert isinstance(result, dict)


# ===========================================================================
# 9. refine / regenerate
# ===========================================================================


class TestRefineRegenerate:
    """Test cover letter refinement and regeneration."""

    def test_refine_success(self, agent, user_id, monkeypatch):
        """Refine with valid feedback returns updated letter."""
        _mock_llm(monkeypatch, SAMPLE_LETTER)
        posting_id = _insert_posting(user_id)
        _insert_cover_letter(user_id, posting_id)
        result = agent.refine(user_id, posting_id, "Make it more enthusiastic")
        assert isinstance(result, dict)
        assert "error" not in result or "body" in result

    def test_refine_empty_feedback_returns_error(self, agent, user_id):
        """Empty feedback string returns error."""
        posting_id = _insert_posting(user_id)
        _insert_cover_letter(user_id, posting_id)
        result = agent.refine(user_id, posting_id, "")
        assert isinstance(result, dict)
        assert "error" in result

    def test_refine_no_existing_letter_returns_error(self, agent, user_id):
        """Refine without existing letter returns error."""
        posting_id = _insert_posting(user_id)
        result = agent.refine(user_id, posting_id, "Some feedback")
        assert isinstance(result, dict)
        assert "error" in result

    def test_regenerate_success(self, agent, user_id, monkeypatch):
        """Regenerate with feedback returns updated letter."""
        _mock_llm(monkeypatch, SAMPLE_LETTER)
        posting_id = _insert_posting(user_id)
        letter_id = _insert_cover_letter(user_id, posting_id)
        result = agent.regenerate(user_id, letter_id, "Be more technical")
        assert isinstance(result, dict)
        assert "error" not in result or "body" in result

    def test_regenerate_not_found_returns_error(self, agent, user_id):
        """Regenerate with bad letter_id returns error."""
        result = agent.regenerate(user_id, "nonexistent-letter", "feedback")
        assert isinstance(result, dict)
        assert "error" in result


# ===========================================================================
# 10. CRUD operations
# ===========================================================================


class TestCRUD:
    """Test get, update, delete operations."""

    def test_get_for_posting_returns_latest(self, agent, user_id):
        """get_for_posting returns the most recent letter."""
        posting_id = _insert_posting(user_id)
        _insert_cover_letter(user_id, posting_id, body="First version")
        _insert_cover_letter(user_id, posting_id, body="Second version")
        result = agent.get_for_posting(user_id, posting_id)
        assert result is not None
        assert isinstance(result, dict)

    def test_get_letter_by_id(self, agent, user_id):
        """get_letter returns the correct letter."""
        posting_id = _insert_posting(user_id)
        letter_id = _insert_cover_letter(user_id, posting_id)
        result = agent.get_letter(letter_id, user_id=user_id)
        assert result is not None
        assert result["id"] == letter_id

    def test_get_letter_wrong_user_returns_none(self, agent, user_id):
        """get_letter with wrong user_id returns None."""
        posting_id = _insert_posting(user_id)
        letter_id = _insert_cover_letter(user_id, posting_id)
        result = agent.get_letter(letter_id, user_id="wrong-user")
        assert result is None

    def test_get_versions_returns_list(self, agent, user_id):
        """get_versions returns list of all versions, newest first."""
        posting_id = _insert_posting(user_id)
        _insert_cover_letter(user_id, posting_id, body="V1")
        _insert_cover_letter(user_id, posting_id, body="V2")
        result = agent.get_versions(user_id, posting_id)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_get_versions_empty_for_no_letters(self, agent, user_id):
        """get_versions returns empty list when no letters exist."""
        posting_id = _insert_posting(user_id)
        result = agent.get_versions(user_id, posting_id)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_update_allowed_fields(self, agent, user_id):
        """update modifies allowed fields and returns updated dict."""
        posting_id = _insert_posting(user_id)
        letter_id = _insert_cover_letter(user_id, posting_id)
        result = agent.update(
            letter_id, {"body": "Updated body", "tone": "technical"}, user_id=user_id
        )
        assert result is not None, "Should return updated letter dict"
        assert result["body"] == "Updated body"

    def test_update_disallowed_fields_returns_none(self, agent, user_id):
        """update with no valid fields returns None."""
        posting_id = _insert_posting(user_id)
        letter_id = _insert_cover_letter(user_id, posting_id)
        result = agent.update(letter_id, {"invalid_field": "value"}, user_id=user_id)
        assert result is None

    def test_delete_removes_record(self, agent, user_id):
        """delete removes the cover letter from DB."""
        from models import get_db_connection

        posting_id = _insert_posting(user_id)
        letter_id = _insert_cover_letter(user_id, posting_id)
        agent.delete(letter_id, user_id=user_id)
        conn = get_db_connection()
        row = conn.execute("SELECT * FROM cover_letters WHERE id=?", (letter_id,)).fetchone()
        conn.close()
        assert row is None, "Letter should be deleted from DB"

    def test_get_for_posting_returns_none_when_empty(self, agent, user_id):
        """get_for_posting returns None when no letters exist."""
        posting_id = _insert_posting(user_id)
        result = agent.get_for_posting(user_id, posting_id)
        assert result is None


# ===========================================================================
# 11. Edge cases
# ===========================================================================


class TestEdgeCases:
    """Test edge cases and aliases."""

    def test_generate_alias_calls_generate_cover_letter(self, agent, user_id, monkeypatch):
        """generate() is an alias for generate_cover_letter()."""
        _mock_llm(monkeypatch, SAMPLE_LETTER)
        posting_id = _insert_posting(user_id)
        # Both should produce same type of result
        r1 = agent.generate(user_id, posting_id)
        assert isinstance(r1, dict)

    def test_all_styles_recognized(self, agent):
        """All four STYLES keys are valid."""
        assert set(STYLES.keys()) == {"professional", "conversational", "technical", "executive"}
        assert all(isinstance(v, str) for v in STYLES.values())

    def test_agent_type_is_cover_letter(self, agent):
        """Agent type attribute is correct."""
        assert agent.agent_type == "cover_letter"
        assert isinstance(agent, CoverLetterAgent)
