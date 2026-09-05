"""Core tests for deep_profile.py — source aggregation, fallback profile, persistence, role synthesis."""

import json

import deep_profile_sources as dpsrc
import deep_profile_synthesis as dps
import deep_profile
import pytest
from test_helpers import query_db


@pytest.fixture(autouse=True)
def _reset_singleton():
    deep_profile._engine = None
    yield
    deep_profile._engine = None


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    """Block all LLM calls — force fallback profile."""
    monkeypatch.setattr("llm_helper.call_llm", lambda *a, **kw: None)
    monkeypatch.setattr("llm_helper.extract_json", lambda x: None)


@pytest.fixture
def engine(app):
    return deep_profile.get_deep_profile_engine()


@pytest.fixture
def user_id(app):
    from models import User

    return User.create("deep@test.com", "Pass!").id


# ---------------------------------------------------------------------------
# _init_deep_profile_tables
# ---------------------------------------------------------------------------


class TestInitTables:
    """Verify deep profile tables are created."""

    def test_deep_profiles_table_exists(self, app):
        rows = query_db(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='deep_profiles'"
        )
        assert len(rows) == 1

    def test_role_syntheses_table_exists(self, app):
        rows = query_db(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='role_syntheses'"
        )
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# _build_source_summary
# ---------------------------------------------------------------------------


class TestBuildSourceSummary:
    """Tests for _build_source_summary() — human-readable data summary."""

    def test_empty_data(self, engine):
        result = dps.build_source_summary({})
        assert result == "No data sources found"

    def test_linkedin_data(self, engine):
        raw = {
            "linkedin": {"skills": [{"name": "Python"}], "experience": [], "recommendations": []}
        }
        result = dps.build_source_summary(raw)
        assert "LinkedIn" in result
        assert "1 skills" in result

    def test_projects_data(self, engine):
        raw = {"projects": [{"client_name": "Acme"}, {"client_name": "BigCo"}]}
        result = dps.build_source_summary(raw)
        assert "2 analyzed clients" in result

    def test_journey_data(self, engine):
        raw = {"journey": {"events": [{}] * 10, "narratives": [{}] * 3}}
        result = dps.build_source_summary(raw)
        assert "10 events" in result
        assert "3 narratives" in result

    def test_multiple_sources(self, engine):
        raw = {
            "linkedin": {"skills": [{"name": "Python"}]},
            "projects": [{"client_name": "Co"}],
            "experiences": [{"employer": "X"}],
            "resumes": [{"file_name": "r.pdf"}],
        }
        result = dps.build_source_summary(raw)
        assert "LinkedIn" in result
        assert "Projects" in result
        assert "Experiences" in result
        assert "Resumes" in result


# ---------------------------------------------------------------------------
# _build_fallback_profile
# ---------------------------------------------------------------------------


class TestBuildFallbackProfile:
    """Tests for _build_fallback_profile() — non-LLM profile construction."""

    def test_returns_expected_keys(self, engine):
        raw = {"linkedin": {}}
        profile = dps.build_fallback_profile(raw)
        assert "professional_summary" in profile
        assert "career_arc" in profile
        assert "technology_mastery" in profile
        assert "business_impacts" in profile
        assert "leadership_profile" in profile
        assert "differentiators" in profile

    def test_builds_tech_mastery_from_linkedin_skills(self, engine):
        raw = {
            "linkedin": {
                "skills": [
                    {"name": "Python", "endorsements": 80},
                    {"name": "Docker", "endorsements": 25},
                    {"name": "React", "endorsements": 3},
                ]
            }
        }
        profile = dps.build_fallback_profile(raw)
        techs = profile["technology_mastery"]
        assert len(techs) == 3
        python_tech = next(t for t in techs if t["name"] == "Python")
        assert python_tech["proficiency"] == "expert"
        docker_tech = next(t for t in techs if t["name"] == "Docker")
        assert docker_tech["proficiency"] == "advanced"
        react_tech = next(t for t in techs if t["name"] == "React")
        assert react_tech["proficiency"] == "beginner"

    def test_builds_career_arc_from_experience(self, engine):
        raw = {
            "linkedin": {
                "experience": [
                    {
                        "title": "Senior Dev",
                        "company": "Acme",
                        "start_date": "2020",
                        "end_date": "2023",
                    },
                    {"title": "Lead", "company": "BigCo", "start_date": "2023"},
                ]
            }
        }
        profile = dps.build_fallback_profile(raw)
        phases = profile["career_arc"]["phases"]
        assert len(phases) == 2
        assert phases[0]["title"] == "Senior Dev"
        assert phases[0]["focus"] == "Acme"

    def test_empty_linkedin_still_returns_structure(self, engine):
        raw = {"linkedin": {}}
        profile = dps.build_fallback_profile(raw)
        assert profile["technology_mastery"] == []
        assert profile["career_arc"]["phases"] == []


# ---------------------------------------------------------------------------
# build_profile (integration — LLM disabled, uses fallback)
# ---------------------------------------------------------------------------


class TestBuildProfile:
    """Tests for build_profile() — full aggregation pipeline."""

    def test_returns_dict(self, engine, user_id):
        profile = engine.build_profile(user_id)
        assert isinstance(profile, dict)
        assert "professional_summary" in profile

    def test_persists_to_db(self, engine, user_id):
        engine.build_profile(user_id)
        rows = query_db("SELECT * FROM deep_profiles WHERE user_id = ?", (user_id,))
        assert len(rows) == 1
        assert rows[0]["source_summary"] is not None

    def test_get_profile_returns_saved(self, engine, user_id):
        engine.build_profile(user_id)
        profile = engine.get_profile(user_id)
        assert profile is not None
        assert "professional_summary" in profile

    def test_get_profile_returns_none_when_empty(self, engine, user_id):
        assert engine.get_profile(user_id) is None

    def test_get_profile_with_meta(self, engine, user_id):
        engine.build_profile(user_id)
        meta = engine.get_profile_with_meta(user_id)
        assert meta is not None
        assert "id" in meta
        assert "profile" in meta
        assert "source_summary" in meta
        assert "created_at" in meta

    def test_update_overwrites_existing(self, engine, user_id):
        engine.build_profile(user_id)
        engine.build_profile(user_id)
        rows = query_db("SELECT * FROM deep_profiles WHERE user_id = ?", (user_id,))
        assert len(rows) == 1  # Updated, not duplicated


# ---------------------------------------------------------------------------
# _get_project_data, _get_experience_data, etc.
# ---------------------------------------------------------------------------


class TestDataAggregation:
    """Tests for individual data source retrieval methods."""

    def test_get_linkedin_data_empty(self, engine, user_id, monkeypatch):
        # No linkedin_cache module available
        result = dpsrc.get_linkedin_data()
        assert result == {}

    def test_get_project_data_empty(self, engine, user_id):
        result = dpsrc.get_project_data(user_id)
        assert result == []

    def test_get_journey_data_empty(self, engine, user_id):
        result = dpsrc.get_journey_data()
        assert isinstance(result, dict)
        assert "events" in result

    def test_get_experience_data_empty(self, engine, user_id):
        result = dpsrc.get_experience_data(user_id)
        assert result == []

    def test_get_resume_data_empty(self, engine, user_id):
        result = dpsrc.get_resume_data(user_id)
        assert result == []

    def test_get_skills_interview_data_empty(self, engine, user_id):
        result = dpsrc.get_skills_interview_data()
        assert result == []

    def test_get_wip_projects_returns_list(self, engine, user_id):
        result = dpsrc.get_wip_projects()
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# get_role_synthesis
# ---------------------------------------------------------------------------


class TestRoleSynthesis:
    """Tests for get_role_synthesis() — role-specific profile tailoring."""

    def test_returns_none_without_profile(self, engine, user_id):
        result = engine.get_role_synthesis(user_id, "Python developer needed")
        assert result is None

    def test_returns_none_with_profile_but_no_llm(self, engine, user_id):
        # Build a fallback profile first
        engine.build_profile(user_id)
        result = engine.get_role_synthesis(user_id, "Solutions Architect role")
        # LLM is mocked to return None, so synthesis fails
        assert result is None


# ---------------------------------------------------------------------------
# _condense_raw_for_llm
# ---------------------------------------------------------------------------


class TestCondenseRawForLLM:
    """Tests for _condense_raw_for_llm() — pre-summarization."""

    def test_preserves_linkedin(self, engine):
        raw = {"linkedin": {"summary": "test"}}
        condensed = dps.condense_raw_for_llm(raw)
        assert condensed["linkedin"]["summary"] == "test"

    def test_condenses_journey_events(self, engine):
        raw = {
            "journey": {
                "events": [
                    {"event_date": "2025-01-01", "title": f"E{i}", "category": "development"}
                    for i in range(50)
                ]
            }
        }
        condensed = dps.condense_raw_for_llm(raw)
        assert condensed["journey"]["event_count"] == 50
        assert len(condensed["journey"]["events"]) <= 20

    def test_limits_resume_preview(self, engine):
        raw = {"resumes": [{"source": "upload", "file_name": "r.pdf", "parsed_text": "x" * 1000}]}
        condensed = dps.condense_raw_for_llm(raw)
        assert len(condensed["resumes"][0]["text_preview"]) <= 500


# ---------------------------------------------------------------------------
# update_profile_from_interview
# ---------------------------------------------------------------------------


class TestUpdateProfileFromInterview:
    """Tests for update_profile_from_interview() — merge interview insights."""

    def test_returns_none_without_profile(self, engine, user_id):
        result = engine.update_profile_from_interview(user_id, [])
        assert result is None

    def test_updates_simple_field(self, engine, user_id):
        engine.build_profile(user_id)
        result = engine.update_profile_from_interview(
            user_id,
            [{"field": "professional_summary", "value": "Updated summary"}],
        )
        assert result is not None
        assert result["professional_summary"] == "Updated summary"

    def test_appends_to_list_field(self, engine, user_id):
        engine.build_profile(user_id)
        result = engine.update_profile_from_interview(
            user_id,
            [
                {
                    "field": "differentiators",
                    "value": {"theme": "AI", "evidence": ["built AI system"]},
                }
            ],
        )
        assert any(d.get("theme") == "AI" for d in result["differentiators"])

    def test_persists_updates(self, engine, user_id):
        engine.build_profile(user_id)
        engine.update_profile_from_interview(
            user_id,
            [{"field": "professional_summary", "value": "Persistent update"}],
        )
        profile = engine.get_profile(user_id)
        assert profile["professional_summary"] == "Persistent update"
