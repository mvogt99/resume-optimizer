"""Core tests for agents/job_scout.py — scraping, NLP scoring, LLM scoring, criteria CRUD."""

import json

import pytest
from agents import get_job_scout
from agents.job_scout import JobScoutAgent
from models import get_db_connection
from test_helpers import query_db


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    """Block all LLM calls and external scraping."""
    # call_llm_scored returns (text, scores) — mock must match that signature.
    monkeypatch.setattr("agents.base_agent.call_llm_scored", lambda *a, **kw: ("", {}))
    monkeypatch.setattr("agents.base_agent.extract_json", lambda x: None)


@pytest.fixture
def scout(app):
    return get_job_scout()


@pytest.fixture
def user_id(app):
    from models import User

    return User.create("scout@test.com", "Pass!").id


def _insert_posting(user_id, title="Python Developer", company="Acme Corp", score=75):
    """Insert a job posting directly for testing."""
    import uuid

    posting_id = str(uuid.uuid4())
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO job_postings (id, user_id, title, company, location, url, source, "
        "description, match_score, status, skills_overlap, skills_missing) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            posting_id,
            user_id,
            title,
            company,
            "Remote",
            "https://example.com/job",
            "indeed",
            "Python developer role",
            score,
            "discovered",
            json.dumps(["Python", "Docker"]),
            json.dumps(["Kubernetes"]),
        ),
    )
    conn.commit()
    conn.close()
    return posting_id


# ---------------------------------------------------------------------------
# Agent identity
# ---------------------------------------------------------------------------


class TestAgentIdentity:
    """Tests for agent type and singleton pattern."""

    def test_agent_type(self, scout):
        assert scout.agent_type == "job_scout"
        assert isinstance(scout, JobScoutAgent)

    def test_singleton_returns_same(self, app):
        a = get_job_scout()
        b = get_job_scout()
        assert a is b

    def test_has_base_methods(self, scout):
        assert hasattr(scout, "_call_llm")
        assert hasattr(scout, "_call_llm_json")
        assert hasattr(scout, "_log_run")


# ---------------------------------------------------------------------------
# get_postings
# ---------------------------------------------------------------------------


class TestGetPostings:
    """Tests for JobScoutAgent.get_postings()."""

    def test_empty_returns_list(self, scout, user_id):
        result = scout.get_postings(user_id)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_returns_inserted_posting(self, scout, user_id):
        _insert_posting(user_id, title="Data Engineer", company="DataCo", score=80)
        result = scout.get_postings(user_id)
        assert len(result) == 1
        assert result[0]["title"] == "Data Engineer"
        assert result[0]["company"] == "DataCo"
        assert result[0]["match_score"] == 80

    def test_filter_by_status(self, scout, user_id):
        _insert_posting(user_id)
        # Default status is "discovered"
        result = scout.get_postings(user_id, status="bookmarked")
        assert len(result) == 0
        result = scout.get_postings(user_id, status="discovered")
        assert len(result) == 1

    def test_filter_by_min_score(self, scout, user_id):
        _insert_posting(user_id, score=30)
        _insert_posting(user_id, score=80)
        result = scout.get_postings(user_id, min_score=50)
        assert len(result) == 1
        assert result[0]["match_score"] == 80

    def test_limit(self, scout, user_id):
        for i in range(5):
            _insert_posting(user_id, title=f"Job {i}")
        result = scout.get_postings(user_id, limit=3)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# get_posting
# ---------------------------------------------------------------------------


class TestGetPosting:
    """Tests for JobScoutAgent.get_posting()."""

    def test_returns_posting(self, scout, user_id):
        pid = _insert_posting(user_id, title="ML Engineer")
        result = scout.get_posting(pid, user_id)
        assert result is not None
        assert result["title"] == "ML Engineer"
        assert result["id"] == pid

    def test_nonexistent_returns_none(self, scout, user_id):
        result = scout.get_posting("fake-id", user_id)
        assert result is None

    def test_wrong_user_returns_none(self, scout, user_id):
        pid = _insert_posting(user_id)
        result = scout.get_posting(pid, 99999)
        assert result is None


# ---------------------------------------------------------------------------
# update_posting
# ---------------------------------------------------------------------------


class TestUpdatePosting:
    """Tests for JobScoutAgent.update_posting()."""

    def test_update_status(self, scout, user_id):
        pid = _insert_posting(user_id)
        result = scout.update_posting(pid, {"status": "bookmarked"}, user_id)
        assert result is not None
        assert result["status"] == "bookmarked"

    def test_update_notes(self, scout, user_id):
        pid = _insert_posting(user_id)
        result = scout.update_posting(pid, {"notes": "Good match"}, user_id)
        assert result["notes"] == "Good match"

    def test_update_starred(self, scout, user_id):
        pid = _insert_posting(user_id)
        result = scout.update_posting(pid, {"is_starred": True}, user_id)
        assert result["is_starred"] in (True, 1)  # SQLite stores bool as int

    def test_persists_to_db(self, scout, user_id):
        pid = _insert_posting(user_id)
        scout.update_posting(pid, {"status": "applied"}, user_id)
        rows = query_db("SELECT status FROM job_postings WHERE id = ?", (pid,))
        assert rows[0]["status"] == "applied"

    def test_nonexistent_returns_none(self, scout, user_id):
        result = scout.update_posting("fake", {"status": "applied"}, user_id)
        assert result is None


# ---------------------------------------------------------------------------
# delete_posting
# ---------------------------------------------------------------------------


class TestDeletePosting:
    """Tests for JobScoutAgent.delete_posting()."""

    def test_deletes_from_db(self, scout, user_id):
        pid = _insert_posting(user_id)
        scout.delete_posting(pid, user_id)
        rows = query_db("SELECT * FROM job_postings WHERE id = ?", (pid,))
        assert len(rows) == 0

    def test_multiple_delete_safe(self, scout, user_id):
        pid = _insert_posting(user_id)
        scout.delete_posting(pid, user_id)
        # Should not raise on second delete
        scout.delete_posting(pid, user_id)


# ---------------------------------------------------------------------------
# add_posting
# ---------------------------------------------------------------------------


class TestAddPosting:
    """Tests for JobScoutAgent.add_posting()."""

    def test_creates_posting(self, scout, user_id):
        result = scout.add_posting(
            user_id,
            {
                "title": "Manual Job",
                "company": "ManualCo",
                "url": "https://manual.com/job",
                "description": "A job I found manually",
            },
        )
        assert result is not None
        assert result["title"] == "Manual Job"
        assert result["company"] == "ManualCo"

    def test_persists_to_db(self, scout, user_id):
        scout.add_posting(
            user_id,
            {
                "title": "DB Check",
                "company": "TestCo",
            },
        )
        rows = query_db("SELECT title, company FROM job_postings WHERE user_id = ?", (user_id,))
        assert len(rows) == 1
        assert rows[0]["title"] == "DB Check"
        assert rows[0]["company"] == "TestCo"

    def test_default_status_discovered(self, scout, user_id):
        result = scout.add_posting(user_id, {"title": "T", "company": "C"})
        assert result["status"] == "discovered"


# ---------------------------------------------------------------------------
# save_criteria / get_criteria
# ---------------------------------------------------------------------------


class TestCriteria:
    """Tests for criteria CRUD."""

    def test_save_and_get(self, scout, user_id):
        scout.save_criteria(
            user_id,
            {
                "search_name": "Remote Python",
                "target_roles": "Python Developer",
                "locations": "Remote",
                "remote_preference": "remote",
            },
        )
        criteria = scout.get_criteria(user_id)
        assert len(criteria) == 1
        assert criteria[0]["search_name"] == "Remote Python"
        assert criteria[0]["target_roles"] == "Python Developer"

    def test_persists_to_db(self, scout, user_id):
        scout.save_criteria(user_id, {"search_name": "Test"})
        rows = query_db("SELECT * FROM search_criteria WHERE user_id = ?", (user_id,))
        assert len(rows) == 1
        assert rows[0]["search_name"] == "Test"

    def test_empty_criteria(self, scout, user_id):
        result = scout.get_criteria(user_id)
        assert result == []


# ---------------------------------------------------------------------------
# _score_posting (NLP scoring path)
# ---------------------------------------------------------------------------


class TestScorePosting:
    """Tests for _score_posting() NLP path (LLM disabled)."""

    def test_returns_score_dict(self, scout, user_id):
        posting = {
            "title": "Python Developer",
            "company": "Co",
            "description": "Python, Docker, AWS, microservices, REST APIs",
        }
        profile = {"resume_text": "Python, Docker, REST APIs, Flask, PostgreSQL"}
        profile_text = "Python, Docker, REST APIs"
        result = scout._score_posting(posting, profile, profile_text)
        assert isinstance(result, dict)
        assert "match_score" in result
        assert isinstance(result["match_score"], (int, float))

    def test_score_between_0_and_100(self, scout, user_id):
        posting = {"title": "Job", "company": "Co", "description": "Python Docker"}
        result = scout._score_posting(posting, {}, "Python Docker")
        assert 0 <= result["match_score"] <= 100

    def test_high_overlap_scores_higher(self, scout, user_id):
        posting = {
            "title": "Dev",
            "company": "Co",
            "description": "Python, Docker, Flask, REST API, PostgreSQL",
        }
        profile = {"resume_text": "Python, Docker, Flask, REST API, PostgreSQL"}
        result = scout._score_posting(
            posting, profile, "Python, Docker, Flask, REST API, PostgreSQL"
        )
        assert result["match_score"] >= 50


# ---------------------------------------------------------------------------
# _log_run (inherited from BaseCareerAgent)
# ---------------------------------------------------------------------------


class TestLogRun:
    """Tests for _log_run() audit trail."""

    def test_creates_agent_run_record(self, scout, user_id):
        run_id = scout._log_run(user_id, "test search", {"query": "python"}, {"count": 5})
        assert isinstance(run_id, str)
        assert len(run_id) == 36  # UUID

    def test_persists_to_db(self, scout, user_id):
        scout._log_run(user_id, "test task", {"in": 1}, {"out": 2}, task_type="analysis")
        rows = query_db(
            "SELECT * FROM agent_runs WHERE user_id = ? AND agent_type = 'job_scout'", (user_id,)
        )
        assert len(rows) == 1
        assert rows[0]["task_description"] == "test task"
        assert rows[0]["task_type"] == "analysis"
        assert rows[0]["agent_type"] == "job_scout"
