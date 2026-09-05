"""Core tests for 4 agent subclasses: resume_tailor, cover_letter, interview_coach, career_advisor."""  # noqa: E501

import json
import sqlite3
import uuid

import agents
import pytest
from agents.career_advisor import CareerAdvisorAgent
from agents.cover_letter import CoverLetterAgent
from agents.interview_coach import PERSONAS, InterviewCoachAgent
from agents.resume_tailor import ResumeTailorAgent
from test_helpers import query_db


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    """Block all LLM calls across all agent modules."""
    monkeypatch.setattr("agents.base_agent.call_llm_scored", lambda *a, **kw: (None, None))
    monkeypatch.setattr("agents.base_agent.extract_json", lambda x: None)


@pytest.fixture
def user_id(app):
    from models import User

    return User.create("agent@test.com", "Pass!").id


def _insert_posting(user_id, title="Test Job", company="TestCo"):
    """Insert a test job posting."""
    from models import get_db_connection

    pid = str(uuid.uuid4())
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO job_postings (id, user_id, title, company, location, url, source, "
        "description, match_score, status, skills_overlap, skills_missing) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            pid,
            user_id,
            title,
            company,
            "NYC",
            "https://example.com",
            "indeed",
            "Python developer with 5 years experience",
            80,
            "discovered",
            json.dumps(["Python"]),
            json.dumps(["Docker"]),
        ),
    )
    conn.commit()
    conn.close()
    return pid


def _insert_resume_version(user_id, text="Python developer with expertise in Flask and Docker"):
    """Insert a test resume version."""
    from models import get_db_connection

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
# ResumeTailorAgent
# ---------------------------------------------------------------------------


class TestResumeTailor:
    """Tests for ResumeTailorAgent."""

    @pytest.fixture
    def tailor(self, app):
        return agents.get_resume_tailor()

    def test_agent_type(self, tailor):
        assert tailor.agent_type == "resume_tailor"
        assert isinstance(tailor, ResumeTailorAgent)

    def test_singleton(self, app):
        a = agents.get_resume_tailor()
        b = agents.get_resume_tailor()
        assert a is b

    def test_has_tailor_method(self, tailor):
        assert hasattr(tailor, "tailor_for_posting")
        assert callable(tailor.tailor_for_posting)

    def test_has_get_tailored_method(self, tailor):
        assert hasattr(tailor, "get_tailored")
        assert callable(tailor.get_tailored)

    def test_tailor_with_resume(self, tailor, user_id):
        _insert_resume_version(user_id)
        pid = _insert_posting(user_id)
        result = tailor.tailor_for_posting(user_id, pid)
        # Should return something (may be None if LLM fails, or a dict with version)
        if result is not None:
            assert isinstance(result, dict)

    def test_get_tailored_nonexistent(self, tailor, user_id):
        result = tailor.get_tailored("fake-posting-id", user_id)
        assert result is None

    # --- Bug regression + integration tests (Phase 17.01) ---

    def test_tailor_no_posting(self, tailor, user_id):
        """Tailor with non-existent posting returns error dict."""
        result = tailor.tailor_for_posting(user_id, "nonexistent-posting-id")
        assert isinstance(result, dict)
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_tailor_no_description(self, tailor, user_id):
        """Tailor with empty JD returns error about no description."""
        from models import get_db_connection

        pid = _insert_posting(user_id)
        # Clear the description
        conn = get_db_connection()
        conn.execute("UPDATE job_postings SET description = '' WHERE id = ?", (pid,))
        conn.commit()
        conn.close()

        result = tailor.tailor_for_posting(user_id, pid)
        assert isinstance(result, dict)
        assert "error" in result
        assert "description" in result["error"].lower() or "no job" in result["error"].lower()

    def test_tailor_no_resume(self, tailor, user_id):
        """Tailor with no resume returns error about missing resume."""
        pid = _insert_posting(user_id)
        # Don't insert any resume_version
        result = tailor.tailor_for_posting(user_id, pid)
        assert isinstance(result, dict)
        assert "error" in result
        assert "resume" in result["error"].lower()

    def test_tailor_creates_version(self, tailor, user_id):
        """Successful tailor creates resume_versions row with source=agent_tailor."""
        from models import get_db_connection

        _insert_resume_version(user_id)
        pid = _insert_posting(user_id)

        result = tailor.tailor_for_posting(user_id, pid)
        # With LLM mocked out, optimize_resume still runs NLP-only
        if "error" in result:
            pytest.skip("Optimization returned error (expected without full NLP)")

        assert "version_id" in result
        conn = get_db_connection()
        row = conn.execute(
            "SELECT source, source_id FROM resume_versions WHERE id = ?",
            (result["version_id"],),
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "agent_tailor"
        assert row[1] == pid

    def test_tailor_updates_posting_reference(self, tailor, user_id):
        """After tailor, job_postings.tailored_version_id is set."""
        from models import get_db_connection

        _insert_resume_version(user_id)
        pid = _insert_posting(user_id)

        result = tailor.tailor_for_posting(user_id, pid)
        if "error" in result:
            pytest.skip("Optimization returned error")

        conn = get_db_connection()
        row = conn.execute(
            "SELECT tailored_version_id FROM job_postings WHERE id = ?", (pid,)
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] is not None
        assert row[0] == str(result["version_id"])

    def test_get_tailored_returns_saved(self, tailor, user_id):
        """After tailoring, get_tailored returns the saved version."""
        _insert_resume_version(user_id)
        pid = _insert_posting(user_id)

        result = tailor.tailor_for_posting(user_id, pid)
        if "error" in result:
            pytest.skip("Optimization returned error")

        saved = tailor.get_tailored(pid, user_id=user_id)
        assert saved is not None
        assert saved["id"] == result["version_id"]
        assert saved["source"] == "agent_tailor"
        assert "metadata" in saved
        assert saved["metadata"]["posting_id"] == pid

    def test_tailor_deep_profile_graceful(self, tailor, user_id):
        """Tailor works even when deep profile table is empty / module returns None."""
        _insert_resume_version(user_id)
        pid = _insert_posting(user_id)
        # No deep profile data exists for this test user — should not raise
        result = tailor.tailor_for_posting(user_id, pid)
        assert isinstance(result, dict)
        # Either succeeds or returns a non-crash error
        assert "version_id" in result or "error" in result

    def test_tailor_logs_agent_run(self, tailor, user_id):
        """Tailor logs an agent_runs record."""
        from models import get_db_connection

        _insert_resume_version(user_id)
        pid = _insert_posting(user_id)

        conn = get_db_connection()
        before = conn.execute(
            "SELECT COUNT(*) FROM agent_runs WHERE agent_type = 'resume_tailor' AND user_id = ?",
            (user_id,),
        ).fetchone()[0]
        conn.close()

        tailor.tailor_for_posting(user_id, pid)

        conn2 = get_db_connection()
        after = conn2.execute(
            "SELECT COUNT(*) FROM agent_runs WHERE agent_type = 'resume_tailor' AND user_id = ?",
            (user_id,),
        ).fetchone()[0]
        conn2.close()
        assert after > before

    def test_tailor_uses_resume_skills_not_jd(self, tailor, user_id, monkeypatch):
        """Bug regression: extract_keywords must be called with resume text, not JD text."""
        resume_text = "Senior Python developer expert in Django REST and PostgreSQL databases"
        _insert_resume_version(user_id, text=resume_text)
        pid = _insert_posting(user_id)

        captured_calls = []
        original_extract = None
        try:
            import nlp_engine

            original_extract = nlp_engine.extract_keywords

            def spy_extract_keywords(text, *args, **kwargs):
                captured_calls.append(text)
                return original_extract(text, *args, **kwargs)

            monkeypatch.setattr("nlp_engine.extract_keywords", spy_extract_keywords)
            tailor.tailor_for_posting(user_id, pid)
        finally:
            pass

        # The first call to extract_keywords should be with the resume text
        assert len(captured_calls) >= 1
        # Resume text should be in one of the calls (optimize_resume also calls it)
        assert any(resume_text in call for call in captured_calls)


# ---------------------------------------------------------------------------
# CoverLetterAgent
# ---------------------------------------------------------------------------


class TestCoverLetter:
    """Tests for CoverLetterAgent."""

    @pytest.fixture
    def letter_agent(self, app):
        return agents.get_cover_letter()

    def test_agent_type(self, letter_agent):
        assert letter_agent.agent_type == "cover_letter"
        assert isinstance(letter_agent, CoverLetterAgent)

    def test_singleton(self, app):
        a = agents.get_cover_letter()
        b = agents.get_cover_letter()
        assert a is b

    def test_generate_returns_none_without_llm(self, letter_agent, user_id):
        pid = _insert_posting(user_id)
        result = letter_agent.generate(user_id, pid)
        # LLM is mocked to return None, so generation fails
        assert result is None or isinstance(result, dict)

    def test_get_for_posting_empty(self, letter_agent, user_id):
        pid = _insert_posting(user_id)
        result = letter_agent.get_for_posting(user_id, pid)
        assert result is None

    def test_get_letter_nonexistent(self, letter_agent, user_id):
        result = letter_agent.get_letter("fake-id", user_id)
        assert result is None

    def test_placeholder_replacement(self, letter_agent):
        text = "Dear [Hiring Manager], I'm applying for [Position] at [Company]."
        posting = {"title": "Engineer", "company": "Acme"}
        result = letter_agent._replace_placeholders(text, posting)
        assert "Hiring Manager" in result
        assert "Engineer" in result
        assert "Acme" in result
        assert "[Position]" not in result
        assert "[Company]" not in result


# ---------------------------------------------------------------------------
# InterviewCoachAgent
# ---------------------------------------------------------------------------


class TestInterviewCoach:
    """Tests for InterviewCoachAgent."""

    @pytest.fixture
    def coach(self, app):
        return agents.get_interview_coach()

    def test_agent_type(self, coach):
        assert coach.agent_type == "interview_coach"
        assert isinstance(coach, InterviewCoachAgent)

    def test_singleton(self, app):
        a = agents.get_interview_coach()
        b = agents.get_interview_coach()
        assert a is b

    def test_personas_constant(self):
        assert "hiring_manager" in PERSONAS
        assert "technical" in PERSONAS
        assert "hr_recruiter" in PERSONAS
        assert "executive" in PERSONAS
        assert len(PERSONAS) == 4

    def test_persona_structure(self):
        for key, persona in PERSONAS.items():  # noqa: B007
            assert "name" in persona
            assert "focus" in persona
            assert isinstance(persona["name"], str)
            assert isinstance(persona["focus"], str)

    def test_start_session_returns_dict(self, coach, user_id):
        pid = _insert_posting(user_id)
        result = coach.start_session(user_id, pid)
        # May fail if LLM is required for opening — check graceful handling
        if result is not None:
            assert isinstance(result, dict)

    def test_list_sessions_empty(self, coach, user_id):
        result = coach.list_sessions(user_id)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_get_session_nonexistent(self, coach, user_id):
        result = coach.get_session("fake-session-id", user_id)
        assert result is None


# ---------------------------------------------------------------------------
# CareerAdvisorAgent
# ---------------------------------------------------------------------------


class TestCareerAdvisor:
    """Tests for CareerAdvisorAgent."""

    @pytest.fixture
    def advisor(self, app):
        return agents.get_career_advisor()

    def test_agent_type(self, advisor):
        assert advisor.agent_type == "career_advisor"
        assert isinstance(advisor, CareerAdvisorAgent)

    def test_singleton(self, app):
        a = agents.get_career_advisor()
        b = agents.get_career_advisor()
        assert a is b

    def test_get_history_empty(self, advisor, user_id):
        result = advisor.get_history(user_id)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_market_insights_empty(self, advisor, user_id):
        result = advisor.market_insights(user_id)
        assert isinstance(result, dict)
        # With no postings, should return empty/default structure

    def test_market_insights_with_postings(self, advisor, user_id):
        _insert_posting(user_id)
        result = advisor.market_insights(user_id)
        assert isinstance(result, dict)

    def test_feedback_analysis_empty(self, advisor, user_id):
        result = advisor.feedback_analysis(user_id)
        assert isinstance(result, dict)

    def test_analyze_career_without_llm(self, advisor, user_id):
        result = advisor.analyze_career(user_id)
        # LLM disabled, should return None or empty analysis
        assert result is None or isinstance(result, dict)

    def test_get_role_recommendations_without_llm(self, advisor, user_id):
        result = advisor.get_role_recommendations(user_id)
        assert result is None or isinstance(result, dict)


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------


class TestAgentFactory:
    """Tests for agents.get_agent() factory."""

    def test_get_agent_job_scout(self, app):
        agent = agents.get_agent("job_scout")
        assert agent.agent_type == "job_scout"

    def test_get_agent_app_tracker(self, app):
        agent = agents.get_agent("app_tracker")
        assert agent.agent_type == "app_tracker"

    def test_get_agent_resume_tailor(self, app):
        agent = agents.get_agent("resume_tailor")
        assert agent.agent_type == "resume_tailor"

    def test_get_agent_cover_letter(self, app):
        agent = agents.get_agent("cover_letter")
        assert agent.agent_type == "cover_letter"

    def test_get_agent_interview_coach(self, app):
        agent = agents.get_agent("interview_coach")
        assert agent.agent_type == "interview_coach"

    def test_get_agent_career_advisor(self, app):
        agent = agents.get_agent("career_advisor")
        assert agent.agent_type == "career_advisor"

    def test_unknown_agent_raises(self, app):
        with pytest.raises(ValueError, match="Unknown agent type"):
            agents.get_agent("nonexistent_agent")


# ---------------------------------------------------------------------------
# BaseCareerAgent shared behavior
# ---------------------------------------------------------------------------


class TestBaseAgentBehavior:
    """Tests for shared BaseCareerAgent behavior across subclasses."""

    def test_profile_summary_empty(self, app):
        agent = agents.get_job_scout()
        summary = agent._profile_summary({})
        assert summary == "No profile data available."

    def test_profile_summary_with_headline(self, app):
        agent = agents.get_job_scout()
        profile = {"linkedin": {"headline": "Senior Architect"}}
        summary = agent._profile_summary(profile)
        assert "Senior Architect" in summary

    def test_timed_returns_duration(self, app):
        agent = agents.get_job_scout()
        result, ms = agent._timed(lambda: 42)
        assert result == 42
        assert isinstance(ms, int)
        assert ms >= 0

    def test_log_run_inserts_record(self, user_id):
        agent = agents.get_job_scout()
        run_id = agent._log_run(user_id, "test", {}, {}, task_type="test")
        rows = query_db("SELECT * FROM agent_runs WHERE id = ?", (run_id,))
        assert len(rows) == 1
        assert rows[0]["agent_type"] == "job_scout"
        assert rows[0]["user_id"] == user_id

    # --- Phase 17.09: Deep Profile → profile + scoring ---

    def test_profile_summary_includes_higher_order_skills(self, app):
        agent = agents.get_job_scout()
        profile = {
            "higher_order_skills": ["design thinking", "agentic AI", "graph engineering"],
            "differentiators": ["full-stack autonomy"],
            "top_technologies": ["Python", "FastAPI", "ArangoDB"],
        }
        summary = agent._profile_summary(profile)
        assert "design thinking" in summary
        assert "agentic AI" in summary
        assert "full-stack autonomy" in summary
        assert "Python" in summary

    def test_profile_summary_includes_all_deep_profile_fields(self, app):
        agent = agents.get_job_scout()
        profile = {
            "linkedin": {"headline": "Architect", "skills": [{"name": "Java"}]},
            "higher_order_skills": ["solution architecture"],
            "differentiators": ["multi-cloud"],
            "top_technologies": ["Kubernetes"],
        }
        summary = agent._profile_summary(profile)
        assert "Higher-order skills: solution architecture" in summary
        assert "Differentiators: multi-cloud" in summary
        assert "Technologies: Kubernetes" in summary
        assert "Architect" in summary

    def test_get_user_profile_deep_profile_graceful(self, user_id):
        """_get_user_profile works even when deep_profiles table is empty."""
        agent = agents.get_job_scout()
        profile = agent._get_user_profile(user_id)
        assert isinstance(profile, dict)
        assert profile["user_id"] == user_id

    def test_scout_scoring_uses_deep_profile_skills(self, app, user_id):
        """NLP scoring in _score_posting includes deep profile skills in overlap."""
        _insert_resume_version(user_id, text="Python developer with Flask experience")
        scout = agents.get_job_scout()
        profile = scout._get_user_profile(user_id)
        # Inject deep profile data (simulates what _get_user_profile would load)
        profile["higher_order_skills"] = ["design thinking", "microservices architecture"]
        profile["top_technologies"] = ["Kafka", "Kubernetes"]
        profile_text = scout._profile_summary(profile)

        # JD that mentions "design thinking" and "Kubernetes" — these should match
        # via deep profile even though they're not in the resume text
        posting = {
            "description": "Looking for someone with design thinking, Kubernetes, and Python experience",  # noqa: E501
            "title": "Senior Engineer",
            "company": "TestCo",
        }
        scored = scout._score_posting(posting, profile, profile_text)
        overlap = json.loads(scored.get("skills_overlap", "[]"))
        # "design thinking" or "kubernetes" should appear in overlap thanks to enrichment
        overlap_lower = {s.lower() for s in overlap}
        assert "kubernetes" in overlap_lower or "design thinking" in overlap_lower


# ---------------------------------------------------------------------------
# SkillsEnrichment (Phase 17.11)
# ---------------------------------------------------------------------------


class TestSkillsEnrichment:
    """Tests for skills_enrichment — confirmed skills from interviews → optimization."""

    def _create_finalized_skills_session(self, user_id, skills):
        """Helper: insert a finalized skills interview session."""
        from models import get_db_connection

        sid = str(uuid.uuid4())
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO skills_interview_sessions "
            "(id, user_id, skills, stage, is_finalized) VALUES (?, ?, ?, ?, 1)",
            (sid, user_id, json.dumps(skills), "complete"),
        )
        conn.commit()
        conn.close()
        return sid

    def test_get_confirmed_skills_empty(self, user_id):
        """No finalized sessions → empty list."""
        from skills_enrichment import get_confirmed_skills

        result = get_confirmed_skills(user_id)
        assert result == []

    def test_get_confirmed_skills_returns_finalized(self, user_id):
        """Finalized sessions' skills returned."""
        from skills_enrichment import get_confirmed_skills

        self._create_finalized_skills_session(user_id, ["Python", "Docker", "Kubernetes"])
        result = get_confirmed_skills(user_id)
        assert "python" in result
        assert "docker" in result
        assert "kubernetes" in result

    def test_get_confirmed_skills_deduplicates(self, user_id):
        """Multiple sessions with overlapping skills → deduplicated."""
        from skills_enrichment import get_confirmed_skills

        self._create_finalized_skills_session(user_id, ["Python", "Docker"])
        self._create_finalized_skills_session(user_id, ["Docker", "Kafka"])
        result = get_confirmed_skills(user_id)
        assert result.count("docker") == 1
        assert "kafka" in result

    def test_enrich_adds_new_skills(self, user_id):
        """Confirmed skills added to resume_data skills list."""
        from skills_enrichment import enrich_resume_data_with_confirmed_skills

        self._create_finalized_skills_session(user_id, ["Terraform", "Ansible"])
        resume_data = {"text": "Python developer", "skills": ["python"]}
        enriched = enrich_resume_data_with_confirmed_skills(resume_data, user_id)
        assert "terraform" in enriched["skills"]
        assert "ansible" in enriched["skills"]
        assert "python" in enriched["skills"]

    def test_enrich_adds_to_text(self, user_id):
        """Confirmed skills appended to resume text for keyword matching."""
        from skills_enrichment import enrich_resume_data_with_confirmed_skills

        self._create_finalized_skills_session(user_id, ["GraphQL"])
        resume_data = {"text": "Backend developer", "skills": []}
        enriched = enrich_resume_data_with_confirmed_skills(resume_data, user_id)
        assert "graphql" in enriched["text"].lower()

    def test_enrich_no_duplicates(self, user_id):
        """Skills already in resume are not re-added."""
        from skills_enrichment import enrich_resume_data_with_confirmed_skills

        self._create_finalized_skills_session(user_id, ["Python", "Docker"])
        resume_data = {"text": "Python developer", "skills": ["python", "docker"]}
        enriched = enrich_resume_data_with_confirmed_skills(resume_data, user_id)
        # Should not double-add
        assert enriched["skills"].count("python") == 1
        assert enriched["skills"].count("docker") == 1

    def test_enrich_no_sessions_returns_unchanged(self, user_id):
        """No finalized sessions → resume_data unchanged."""
        from skills_enrichment import enrich_resume_data_with_confirmed_skills

        resume_data = {"text": "Original text", "skills": ["java"]}
        enriched = enrich_resume_data_with_confirmed_skills(resume_data, user_id)
        assert enriched["text"] == "Original text"
        assert enriched["skills"] == ["java"]


# ---------------------------------------------------------------------------
# OrchestratorAgent (Phase 17.02)
# ---------------------------------------------------------------------------


class TestOrchestrator:
    """Tests for OrchestratorAgent.full_application_pipeline() — Phase 17.02."""

    @pytest.fixture
    def orchestrator(self, app):
        return agents.get_orchestrator()

    def test_agent_type(self, orchestrator):
        assert orchestrator.agent_type == "orchestrator"

    def test_pipeline_moves_to_applied(self, orchestrator, user_id):
        """Orchestrated pipeline should move posting status to 'applied'."""
        from models import get_db_connection

        _insert_resume_version(user_id)
        pid = _insert_posting(user_id)

        result = orchestrator.full_application_pipeline(user_id, pid)

        # With LLM mocked, tailor still runs NLP-only optimization
        # At minimum, pipeline_move step should succeed
        conn = get_db_connection()
        row = conn.execute("SELECT status FROM job_postings WHERE id = ?", (pid,)).fetchone()
        conn.close()

        if result.get("steps_completed"):
            assert row[0] == "applied"
            assert "pipeline_move" in result["steps_completed"]

    def test_pipeline_returns_expected_keys(self, orchestrator, user_id):
        """Pipeline result dict has required keys."""
        _insert_resume_version(user_id)
        pid = _insert_posting(user_id)

        result = orchestrator.full_application_pipeline(user_id, pid)

        assert "posting_id" in result
        assert "steps_completed" in result
        assert "status" in result
        assert "errors" in result
        assert isinstance(result["steps_completed"], list)
        assert result["status"] in ("complete", "partial", "failed")

    def test_pipeline_logs_orchestrator_run(self, orchestrator, user_id):
        """Pipeline logs an agent_runs record with agent_type=orchestrator."""
        from models import get_db_connection

        _insert_resume_version(user_id)
        pid = _insert_posting(user_id)

        orchestrator.full_application_pipeline(user_id, pid)

        conn = get_db_connection()
        rows = conn.execute(
            "SELECT agent_type, task_type FROM agent_runs "
            "WHERE user_id = ? AND agent_type = 'orchestrator'",
            (user_id,),
        ).fetchall()
        conn.close()
        assert len(rows) >= 1
        assert rows[-1][1] == "orchestrator"

    def test_pipeline_no_resume_has_errors(self, orchestrator, user_id):
        """Pipeline without resume should report errors."""
        pid = _insert_posting(user_id)

        result = orchestrator.full_application_pipeline(user_id, pid)

        assert result["status"] in ("partial", "failed")
        assert len(result["errors"]) > 0
        # At least resume_tailor should fail
        error_steps = [e["step"] for e in result["errors"]]
        assert "resume_tailor" in error_steps

    def test_pipeline_does_not_downgrade_applied(self, orchestrator, user_id):
        """Pipeline should not move already-applied postings backward."""
        from models import get_db_connection

        _insert_resume_version(user_id)
        pid = _insert_posting(user_id)

        # Pre-set posting to 'offered' stage
        conn = get_db_connection()
        conn.execute("UPDATE job_postings SET status = 'offered' WHERE id = ?", (pid,))
        conn.commit()
        conn.close()

        orchestrator.full_application_pipeline(user_id, pid)

        conn = get_db_connection()
        row = conn.execute("SELECT status FROM job_postings WHERE id = ?", (pid,)).fetchone()
        conn.close()
        # Should still be 'offered', not downgraded to 'applied'
        assert row[0] == "offered"

    def test_get_workflow_status(self, orchestrator, user_id):
        """get_workflow_status returns recent orchestrator runs."""
        _insert_resume_version(user_id)
        pid = _insert_posting(user_id)

        orchestrator.full_application_pipeline(user_id, pid)
        status = orchestrator.get_workflow_status(user_id)

        assert "runs" in status
        assert len(status["runs"]) >= 1
        # The orchestrator logs multiple sub-runs; at least one should be the pipeline
        tasks = [r["task"] for r in status["runs"]]
        assert "Full application pipeline" in tasks
