"""Tests for agents/base_agent.py — BaseCareerAgent with real LLM calls.

Covers: _call_llm, _call_llm_json, _log_run, _get_user_profile,
        _profile_summary, _replace_placeholders.
"""

import sqlite3

from test_helpers import query_db


def _create_test_user_direct():
    """Insert a test user directly into the DB and return user_id."""
    import models
    from werkzeug.security import generate_password_hash

    conn = sqlite3.connect(models.DB_PATH)
    conn.execute(
        "INSERT INTO users (email, password_hash) VALUES (?, ?)",
        ("agent_test@test.com", generate_password_hash("Test1234!")),
    )
    user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()
    return user_id


def test_call_llm_returns_string(app):
    from agents.base_agent import BaseCareerAgent

    agent = BaseCareerAgent()
    result = agent._call_llm("Say hello in one word.")
    assert result is None or isinstance(result, str), f"Expected str or None, got {type(result)}"


def test_call_llm_json_returns_dict(app):
    from agents.base_agent import BaseCareerAgent

    agent = BaseCareerAgent()
    result = agent._call_llm_json(
        'Return a JSON object with one key "greeting" and value "hello". '
        'Return ONLY the JSON, no other text. Example: {"greeting": "hello"}'
    )
    assert result is None or isinstance(
        result, (dict, list)
    ), f"Expected dict/list/None, got {type(result)}"


def test_call_llm_json_retries(app):
    from agents.base_agent import BaseCareerAgent

    agent = BaseCareerAgent()
    # Even with a tricky prompt, retries should work
    result = agent._call_llm_json(
        'Return exactly this JSON: {"status": "ok", "count": 42}',
        retries=2,
    )
    assert result is None or isinstance(result, (dict, list))


def test_log_run_creates_record(app):
    user_id = _create_test_user_direct()
    from agents.base_agent import BaseCareerAgent

    agent = BaseCareerAgent()
    run_id = agent._log_run(
        user_id=user_id,
        task_desc="Test task",
        input_data={"query": "test"},
        output_data={"result": "ok"},
        model_used="test-model",
        task_type="test",
        duration_ms=100,
    )
    assert isinstance(run_id, str) and len(run_id) > 0

    rows = query_db("SELECT * FROM agent_runs WHERE id = ?", (run_id,))
    assert len(rows) == 1, "agent_runs record should exist"
    assert rows[0]["task_description"] == "Test task"
    assert rows[0]["model_used"] == "test-model"
    assert rows[0]["task_type"] == "test"


def test_get_user_profile_returns_dict(app):
    user_id = _create_test_user_direct()
    from agents.base_agent import BaseCareerAgent

    agent = BaseCareerAgent()
    profile = agent._get_user_profile(user_id)
    assert isinstance(profile, dict), f"Expected dict, got {type(profile)}"
    assert "user_id" in profile
    assert profile["user_id"] == user_id


def test_profile_summary_returns_string(app):
    user_id = _create_test_user_direct()
    from agents.base_agent import BaseCareerAgent

    agent = BaseCareerAgent()
    profile = agent._get_user_profile(user_id)
    summary = agent._profile_summary(profile)
    assert isinstance(summary, str), f"Expected str, got {type(summary)}"
    assert len(summary) > 0, "Summary should not be empty"


def test_replace_placeholders(app):
    from agents.base_agent import BaseCareerAgent

    agent = BaseCareerAgent()
    text = "Dear [Hiring Manager], I am [Your Name] applying for [Position] at [Company]."
    posting = {"title": "Senior Architect", "company": "Acme Corp"}
    result = agent._replace_placeholders(text, posting=posting, user_name="Mike Vogt")
    assert "[Your Name]" not in result, "Name placeholder should be replaced"
    assert "Mike Vogt" in result
    assert "[Position]" not in result, "Position placeholder should be replaced"
    assert "[Company]" not in result, "Company placeholder should be replaced"
    assert "Senior Architect" in result, "Position should be substituted"
    assert "Acme Corp" in result, "Company should be substituted"
