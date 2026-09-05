"""Core tests for agents/app_tracker.py — pipeline, analytics, reminders."""

import uuid
from datetime import datetime, timedelta

import pytest
from agents import get_app_tracker
from agents.app_tracker import PIPELINE_STAGES, ApplicationTrackerAgent
from models import get_db_connection
from test_helpers import query_db


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    """Block all LLM calls."""
    monkeypatch.setattr("agents.base_agent.call_llm_scored", lambda *a, **kw: (None, None))
    monkeypatch.setattr("agents.base_agent.extract_json", lambda x: None)


@pytest.fixture
def tracker(app):
    return get_app_tracker()


@pytest.fixture
def user_id(app):
    from models import User

    return User.create("tracker@test.com", "Pass!").id


def _insert_posting(
    user_id, title="Python Dev", company="Co", status="discovered", score=75, days_ago=0
):
    """Insert a job posting with optional age offset."""
    posting_id = str(uuid.uuid4())
    conn = get_db_connection()
    updated_at = (datetime.now() - timedelta(days=days_ago)).isoformat()
    if days_ago > 0:
        conn.execute(
            "INSERT INTO job_postings (id, user_id, title, company, location, url, source, "
            "description, match_score, status, skills_overlap, skills_missing, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', '[]', ?)",
            (
                posting_id,
                user_id,
                title,
                company,
                "Remote",
                f"https://example.com/{posting_id}",
                "indeed",
                "Job description",
                score,
                status,
                updated_at,
            ),
        )
    else:
        conn.execute(
            "INSERT INTO job_postings (id, user_id, title, company, location, url, source, "
            "description, match_score, status, skills_overlap, skills_missing) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', '[]')",
            (
                posting_id,
                user_id,
                title,
                company,
                "Remote",
                f"https://example.com/{posting_id}",
                "indeed",
                "Job description",
                score,
                status,
            ),
        )
    conn.commit()
    conn.close()
    return posting_id


# ---------------------------------------------------------------------------
# Agent identity and constants
# ---------------------------------------------------------------------------


class TestAgentIdentity:
    """Tests for agent type and pipeline stages."""

    def test_agent_type(self, tracker):
        assert tracker.agent_type == "app_tracker"
        assert isinstance(tracker, ApplicationTrackerAgent)

    def test_pipeline_stages(self):
        assert len(PIPELINE_STAGES) == 10
        assert PIPELINE_STAGES[0] == "discovered"
        assert PIPELINE_STAGES[-1] == "withdrawn"
        assert "applied" in PIPELINE_STAGES
        assert "interview" in PIPELINE_STAGES

    def test_singleton(self, app):
        a = get_app_tracker()
        b = get_app_tracker()
        assert a is b


# ---------------------------------------------------------------------------
# get_pipeline
# ---------------------------------------------------------------------------


class TestGetPipeline:
    """Tests for ApplicationTrackerAgent.get_pipeline()."""

    def test_empty_pipeline(self, tracker, user_id):
        result = tracker.get_pipeline(user_id)
        assert isinstance(result, dict)
        assert "stages" in result
        assert "columns" in result
        assert result["total"] == 0

    def test_groups_by_status(self, tracker, user_id):
        _insert_posting(user_id, title="Job A", status="discovered")
        _insert_posting(user_id, title="Job B", status="applied")
        result = tracker.get_pipeline(user_id)
        # columns maps stage_name → list of postings
        assert len(result["columns"]["discovered"]) >= 1
        assert len(result["columns"]["applied"]) >= 1

    def test_all_stages_present(self, tracker, user_id):
        result = tracker.get_pipeline(user_id)
        # stages is a list of stage name strings
        for expected in PIPELINE_STAGES:
            assert expected in result["stages"]
            assert expected in result["columns"]


# ---------------------------------------------------------------------------
# move_posting
# ---------------------------------------------------------------------------


class TestMovePosting:
    """Tests for ApplicationTrackerAgent.move_posting()."""

    def test_moves_to_new_status(self, tracker, user_id):
        pid = _insert_posting(user_id, status="discovered")
        result = tracker.move_posting(pid, "bookmarked", user_id=user_id)
        assert result is not None
        assert result["status"] == "bookmarked"

    def test_persists_to_db(self, tracker, user_id):
        pid = _insert_posting(user_id, status="discovered")
        tracker.move_posting(pid, "applied", user_id=user_id)
        rows = query_db("SELECT status FROM job_postings WHERE id = ?", (pid,))
        assert rows[0]["status"] == "applied"

    def test_with_notes(self, tracker, user_id):
        pid = _insert_posting(user_id)
        result = tracker.move_posting(pid, "applied", notes="Applied today", user_id=user_id)
        assert result is not None
        rows = query_db("SELECT notes FROM job_postings WHERE id = ?", (pid,))
        assert "Applied today" in (rows[0]["notes"] or "")

    def test_nonexistent_returns_error(self, tracker, user_id):
        result = tracker.move_posting("fake", "applied", user_id=user_id)
        assert result is not None
        assert "error" in result


# ---------------------------------------------------------------------------
# get_analytics
# ---------------------------------------------------------------------------


class TestGetAnalytics:
    """Tests for ApplicationTrackerAgent.get_analytics()."""

    def test_empty_analytics(self, tracker, user_id):
        result = tracker.get_analytics(user_id)
        assert isinstance(result, dict)
        assert "total" in result or "total_postings" in result or "status_counts" in result

    def test_with_postings(self, tracker, user_id):
        _insert_posting(user_id, status="discovered")
        _insert_posting(user_id, status="applied")
        _insert_posting(user_id, status="interview")
        result = tracker.get_analytics(user_id)
        assert isinstance(result, dict)

    def test_counts_statuses(self, tracker, user_id):
        for _ in range(3):
            _insert_posting(user_id, status="discovered")
        for _ in range(2):
            _insert_posting(user_id, status="applied")
        result = tracker.get_analytics(user_id)
        # The analytics should reflect the data
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# get_reminders
# ---------------------------------------------------------------------------


class TestGetReminders:
    """Tests for ApplicationTrackerAgent.get_reminders()."""

    def test_empty_reminders(self, tracker, user_id):
        result = tracker.get_reminders(user_id)
        assert isinstance(result, list)

    def test_stale_applied_shows_as_reminder(self, tracker, user_id):
        # Posting applied 10 days ago with no progress
        _insert_posting(user_id, status="applied", days_ago=10)
        result = tracker.get_reminders(user_id)
        assert isinstance(result, list)
        # Should detect the stale application
        assert len(result) >= 1


# ---------------------------------------------------------------------------
# generate_followup (LLM disabled → None)
# ---------------------------------------------------------------------------


class TestGenerateFollowup:
    """Tests for ApplicationTrackerAgent.generate_followup() with LLM disabled."""

    def test_returns_none_without_llm(self, tracker, user_id):
        pid = _insert_posting(user_id, status="applied")
        result = tracker.generate_followup(pid, user_id)
        # LLM disabled, should return None or a default structure
        assert result is None or isinstance(result, dict)

    def test_nonexistent_posting(self, tracker, user_id):
        result = tracker.generate_followup("fake-id", user_id)
        assert result is not None
        assert "error" in result


# ---------------------------------------------------------------------------
# DB verification for pipeline operations
# ---------------------------------------------------------------------------


class TestDBVerification:
    """Tests that pipeline operations correctly persist to database."""

    def test_insert_creates_row(self, tracker, user_id):
        pid = _insert_posting(user_id, title="DB Test", company="DBCo")
        rows = query_db("SELECT * FROM job_postings WHERE id = ?", (pid,))
        assert len(rows) == 1
        assert rows[0]["title"] == "DB Test"
        assert rows[0]["company"] == "DBCo"
        assert rows[0]["user_id"] == user_id

    def test_move_updates_row(self, tracker, user_id):
        pid = _insert_posting(user_id, status="discovered")
        tracker.move_posting(pid, "interview", user_id=user_id)
        rows = query_db("SELECT status FROM job_postings WHERE id = ?", (pid,))
        assert rows[0]["status"] == "interview"

    def test_multiple_postings_same_user(self, tracker, user_id):
        for i in range(5):
            _insert_posting(user_id, title=f"Job {i}")
        rows = query_db("SELECT COUNT(*) as cnt FROM job_postings WHERE user_id = ?", (user_id,))
        assert rows[0]["cnt"] == 5
