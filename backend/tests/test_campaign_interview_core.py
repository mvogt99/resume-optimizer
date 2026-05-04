"""Core tests for campaign_interview.py — 7-stage state machine, session lifecycle, finalization."""

import json

import campaign_interview
import pytest
from test_helpers import query_db


@pytest.fixture(autouse=True)
def _reset_singleton():
    campaign_interview._interviewer = None
    yield
    campaign_interview._interviewer = None


@pytest.fixture(autouse=True)
def _no_external(monkeypatch):
    """Block LLM and ArangoDB calls."""
    monkeypatch.setattr("llm_helper.call_llm", lambda *a, **kw: None)
    # Mock arango imports to return disconnected client
    mock_client = type(
        "MockArango",
        (),
        {
            "is_connected": False,
            "query": lambda self, *a, **kw: [],
            "get_knowledge_context": lambda self, *a, **kw: {
                "clients": [],
                "skills": [],
                "milestones": [],
            },
        },
    )()
    monkeypatch.setattr(
        "campaign_interview.CampaignInterviewer._get_theme_suggestions",
        lambda self: [],
    )
    monkeypatch.setattr(
        "campaign_interview.CampaignInterviewer._get_stage_suggestions",
        lambda self, stage, ctx: [],
    )
    monkeypatch.setattr(
        "campaign_interview.CampaignInterviewer._generate_seeds",
        lambda self, ctx: [
            {"title": f"Post {i+1}", "key_points": ["Point A"], "source_refs": []}
            for i in range(ctx.get("post_count", 5) or 5)
        ],
    )


@pytest.fixture
def interviewer(app):
    return campaign_interview.get_campaign_interviewer()


@pytest.fixture
def user_id(app):
    from models import User

    return User.create("camp@test.com", "Pass!").id


# ---------------------------------------------------------------------------
# STAGES constant
# ---------------------------------------------------------------------------


class TestStagesConstant:
    """Tests for STAGES list."""

    def test_has_7_stages(self):
        assert len(campaign_interview.STAGES) == 7

    def test_starts_with_theme(self):
        assert campaign_interview.STAGES[0] == "theme"

    def test_ends_with_review(self):
        assert campaign_interview.STAGES[-1] == "review"

    def test_all_stages_present(self):
        expected = {
            "theme",
            "audience",
            "tone",
            "storyline",
            "post_count",
            "content_seeds",
            "review",
        }
        assert set(campaign_interview.STAGES) == expected


# ---------------------------------------------------------------------------
# start_session
# ---------------------------------------------------------------------------


class TestStartSession:
    """Tests for CampaignInterviewer.start_session()."""

    def test_returns_session_id(self, interviewer, user_id):
        result = interviewer.start_session(user_id)
        assert "session_id" in result
        assert len(result["session_id"]) == 36

    def test_returns_opening_message(self, interviewer, user_id):
        result = interviewer.start_session(user_id)
        assert "message" in result
        assert "campaign" in result["message"].lower() or "theme" in result["message"].lower()

    def test_with_initial_theme(self, interviewer, user_id):
        result = interviewer.start_session(user_id, initial_theme="AI Leadership")
        assert "AI Leadership" in result["message"]

    def test_persists_to_db(self, interviewer, user_id):
        result = interviewer.start_session(user_id)
        rows = query_db("SELECT * FROM campaign_sessions WHERE id = ?", (result["session_id"],))
        assert len(rows) == 1

    def test_saves_assistant_message(self, interviewer, user_id):
        result = interviewer.start_session(user_id)
        rows = query_db(
            "SELECT * FROM campaign_messages WHERE session_id = ?",
            (result["session_id"],),
        )
        assert len(rows) == 1
        assert rows[0]["role"] == "assistant"

    def test_stage_is_theme(self, interviewer, user_id):
        result = interviewer.start_session(user_id)
        assert result["stage"] == "theme"


# ---------------------------------------------------------------------------
# process_message
# ---------------------------------------------------------------------------


class TestProcessMessage:
    """Tests for CampaignInterviewer.process_message()."""

    def test_advances_from_theme(self, interviewer, user_id):
        session = interviewer.start_session(user_id)
        result = interviewer.process_message(session["session_id"], "Enterprise Architecture")
        assert result["stage"] == "audience"

    def test_extracts_theme(self, interviewer, user_id):
        session = interviewer.start_session(user_id)
        result = interviewer.process_message(session["session_id"], "AI Innovation")
        assert result["context"]["theme"] == "AI Innovation"

    def test_extracts_audience(self, interviewer, user_id):
        session = interviewer.start_session(user_id)
        interviewer.process_message(session["session_id"], "Tech Leadership")
        result = interviewer.process_message(session["session_id"], "CTOs and VPs of Engineering")
        assert result["context"]["audience"] == "CTOs and VPs of Engineering"

    def test_full_walkthrough_reaches_review(self, interviewer, user_id):
        session = interviewer.start_session(user_id)
        messages = [
            "AI in Healthcare",  # theme → audience
            "Healthcare CIOs",  # audience → tone
            "Thought leader",  # tone → storyline
            "Problem to solution arc",  # storyline → post_count
            "5 posts weekly",  # post_count → content_seeds
            "Looks great",  # content_seeds → review
        ]
        for msg in messages:
            result = interviewer.process_message(session["session_id"], msg)
        assert result["stage"] == "review"
        assert result["is_review"] is True

    def test_saves_user_and_assistant_messages(self, interviewer, user_id):
        session = interviewer.start_session(user_id)
        interviewer.process_message(session["session_id"], "Theme text")
        rows = query_db(
            "SELECT role FROM campaign_messages WHERE session_id = ? ORDER BY created_at",
            (session["session_id"],),
        )
        roles = [r["role"] for r in rows]
        assert "user" in roles
        assert roles.count("assistant") >= 2

    def test_nonexistent_session_returns_error(self, interviewer, user_id):
        result = interviewer.process_message("fake-id", "hello")
        assert "error" in result

    def test_post_count_extraction(self, interviewer, user_id):
        session = interviewer.start_session(user_id)
        for msg in ["Theme", "Audience", "Tone", "Storyline"]:
            interviewer.process_message(session["session_id"], msg)
        result = interviewer.process_message(session["session_id"], "8 posts biweekly")
        assert result["context"]["post_count"] == 8


# ---------------------------------------------------------------------------
# get_session_state
# ---------------------------------------------------------------------------


class TestGetSessionState:
    """Tests for CampaignInterviewer.get_session_state()."""

    def test_returns_current_state(self, interviewer, user_id):
        session = interviewer.start_session(user_id)
        state = interviewer.get_session_state(session["session_id"])
        assert state["stage"] == "theme"
        assert state["is_finalized"] is False
        assert "messages" in state
        assert len(state["messages"]) >= 1

    def test_nonexistent_returns_error(self, interviewer, user_id):
        result = interviewer.get_session_state("fake-id")
        assert "error" in result


# ---------------------------------------------------------------------------
# finalize_to_campaign
# ---------------------------------------------------------------------------


class TestFinalizeToCampaign:
    """Tests for CampaignInterviewer.finalize_to_campaign()."""

    def _drive_to_review(self, interviewer, user_id):
        session = interviewer.start_session(user_id)
        messages = [
            "AI Theme",
            "Developers",
            "Technical",
            "Journey arc",
            "3 posts weekly",
            "Confirmed",
        ]
        for msg in messages:
            interviewer.process_message(session["session_id"], msg)
        return session["session_id"]

    def test_creates_campaign_row(self, interviewer, user_id):
        sid = self._drive_to_review(interviewer, user_id)
        result = interviewer.finalize_to_campaign(sid, user_id)
        assert "campaign_id" in result
        rows = query_db("SELECT * FROM campaigns WHERE id = ?", (result["campaign_id"],))
        assert len(rows) == 1
        assert rows[0]["theme"] == "AI Theme"
        assert rows[0]["status"] == "draft"

    def test_creates_post_stubs(self, interviewer, user_id):
        sid = self._drive_to_review(interviewer, user_id)
        result = interviewer.finalize_to_campaign(sid, user_id)
        rows = query_db(
            "SELECT * FROM campaign_posts WHERE campaign_id = ? ORDER BY position",
            (result["campaign_id"],),
        )
        assert len(rows) >= 1  # At least one post stub

    def test_marks_session_finalized(self, interviewer, user_id):
        sid = self._drive_to_review(interviewer, user_id)
        interviewer.finalize_to_campaign(sid, user_id)
        rows = query_db("SELECT is_finalized FROM campaign_sessions WHERE id = ?", (sid,))
        assert rows[0]["is_finalized"] == 1

    def test_nonexistent_returns_error(self, interviewer, user_id):
        result = interviewer.finalize_to_campaign("fake-id", user_id)
        assert "error" in result


# ---------------------------------------------------------------------------
# _advance_stage
# ---------------------------------------------------------------------------


class TestAdvanceStage:
    """Tests for _advance_stage() — stage progression."""

    def test_theme_to_audience(self, interviewer):
        result = interviewer._advance_stage("theme", {})
        assert result == "audience"

    def test_review_stays_review(self, interviewer):
        result = interviewer._advance_stage("review", {})
        assert result == "review"

    def test_invalid_stage_resets(self, interviewer):
        result = interviewer._advance_stage("nonexistent", {})
        assert result == "theme"


# ---------------------------------------------------------------------------
# _extract_from_message
# ---------------------------------------------------------------------------


class TestExtractFromMessage:
    """Tests for _extract_from_message() — per-stage extraction."""

    def test_theme_extraction(self, interviewer):
        ctx = {"theme": "", "audience": "", "tone": ""}
        ctx = interviewer._extract_from_message(ctx, "theme", "AI Innovation")
        assert ctx["theme"] == "AI Innovation"

    def test_audience_extraction(self, interviewer):
        ctx = {"audience": ""}
        ctx = interviewer._extract_from_message(ctx, "audience", "CTOs and VPs")
        assert ctx["audience"] == "CTOs and VPs"

    def test_post_count_numeric(self, interviewer):
        ctx = {"post_count": 0, "cadence": ""}
        ctx = interviewer._extract_from_message(ctx, "post_count", "7 posts weekly")
        assert ctx["post_count"] == 7

    def test_post_count_default_when_no_number(self, interviewer):
        ctx = {"post_count": 0, "cadence": ""}
        ctx = interviewer._extract_from_message(ctx, "post_count", "a few posts")
        assert ctx["post_count"] == 5  # default

    def test_post_count_capped_at_20(self, interviewer):
        ctx = {"post_count": 0, "cadence": ""}
        ctx = interviewer._extract_from_message(ctx, "post_count", "50 posts")
        assert ctx["post_count"] == 20
