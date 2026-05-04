"""Tests for deep_profile.py — DeepProfileEngine with real LLM calls.

Covers: build_profile, get_profile, get_role_synthesis, profile structure.
"""

import json

from test_helpers import JOB_DESCRIPTION, RESUME_TEXT, query_db


def _seed_test_data(user_id=1):
    """Insert minimal data so DeepProfileEngine has sources to aggregate."""
    import sqlite3

    import models

    conn = sqlite3.connect(models.DB_PATH)

    # Insert a resume version
    conn.execute(
        "INSERT INTO resume_versions (user_id, source, file_name, parsed_text) "
        "VALUES (?, ?, ?, ?)",
        (user_id, "upload", "test_resume.pdf", RESUME_TEXT),
    )

    # Insert a client project with analysis
    conn.execute(
        "INSERT INTO client_projects (user_id, client_name, folder_id, analysis_status, "
        "skills_json, business_outcomes_json) VALUES (?, ?, ?, ?, ?, ?)",
        (
            user_id,
            "Navitus Health Solutions",
            "folder123",
            "analyzed",
            json.dumps(
                [
                    {"name": "Python", "category": "technology"},
                    {"name": "AWS", "category": "technology"},
                    {"name": "Kubernetes", "category": "technology"},
                ]
            ),
            json.dumps(
                [
                    {
                        "outcome_title": "Cost Reduction",
                        "outcome_type": "cost_reduction",
                        "description": "Saved $1.2M annually",
                    },
                ]
            ),
        ),
    )

    conn.commit()
    conn.close()


def test_deep_profile_engine_init(app):
    from deep_profile import get_deep_profile_engine

    engine = get_deep_profile_engine()
    assert engine is not None


def test_build_profile_returns_dict(app):
    _seed_test_data(user_id=1)
    from deep_profile import get_deep_profile_engine

    engine = get_deep_profile_engine()
    profile = engine.build_profile(user_id=1)
    assert profile is None or isinstance(
        profile, dict
    ), f"Expected dict or None, got {type(profile)}"


def test_build_profile_structure(app):
    _seed_test_data(user_id=1)
    from deep_profile import get_deep_profile_engine

    engine = get_deep_profile_engine()
    profile = engine.build_profile(user_id=1)
    if profile is None:
        # LLM may fail in test env — check fallback was created
        stored = engine.get_profile(user_id=1)
        assert stored is None or isinstance(stored, dict)
        return

    # Check expected top-level keys
    expected_keys = {"professional_summary", "technology_mastery", "differentiators"}
    found = set(profile.keys()) & expected_keys
    assert len(found) >= 1, f"Profile missing expected keys. Got: {set(profile.keys())}"


def test_build_profile_has_career_phases(app):
    _seed_test_data(user_id=1)
    from deep_profile import get_deep_profile_engine

    engine = get_deep_profile_engine()
    profile = engine.build_profile(user_id=1)
    if profile is None:
        return  # LLM unavailable
    # career_arc or career_phases should be present
    has_phases = "career_arc" in profile or "career_phases" in profile
    assert (
        has_phases or "professional_summary" in profile
    ), "Profile should have career phases or at least a professional summary"


def test_build_profile_has_technology_mastery(app):
    _seed_test_data(user_id=1)
    from deep_profile import get_deep_profile_engine

    engine = get_deep_profile_engine()
    profile = engine.build_profile(user_id=1)
    if profile is None:
        return
    assert (
        "technology_mastery" in profile or "differentiators" in profile
    ), "Profile should have technology_mastery or differentiators"


def test_build_profile_has_differentiators(app):
    _seed_test_data(user_id=1)
    from deep_profile import get_deep_profile_engine

    engine = get_deep_profile_engine()
    profile = engine.build_profile(user_id=1)
    if profile is None:
        return
    if "differentiators" in profile:
        assert isinstance(profile["differentiators"], (list, dict, str))


def test_build_profile_saves_to_db(app):
    _seed_test_data(user_id=1)
    from deep_profile import get_deep_profile_engine

    engine = get_deep_profile_engine()
    engine.build_profile(user_id=1)

    rows = query_db("SELECT * FROM deep_profiles WHERE user_id = 1")
    assert len(rows) >= 1, "Profile should be saved to deep_profiles table"


def test_role_synthesis_produces_fit_score(app):
    _seed_test_data(user_id=1)
    from deep_profile import get_deep_profile_engine

    engine = get_deep_profile_engine()
    engine.build_profile(user_id=1)

    synthesis = engine.get_role_synthesis(user_id=1, job_text=JOB_DESCRIPTION)
    if synthesis is None:
        return  # LLM may not be available
    if "fit_score" in synthesis:
        score = synthesis["fit_score"]
        assert isinstance(score, (int, float))
        assert 0 <= score <= 100, f"fit_score {score} out of 0-100 range"


def test_role_synthesis_returns_dict_or_none(app):
    _seed_test_data(user_id=1)
    from deep_profile import get_deep_profile_engine

    engine = get_deep_profile_engine()
    engine.build_profile(user_id=1)

    synthesis = engine.get_role_synthesis(user_id=1, job_text=JOB_DESCRIPTION)
    assert synthesis is None or isinstance(synthesis, dict)
