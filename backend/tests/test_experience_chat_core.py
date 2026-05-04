"""Core tests for experience_chat.py — 6-stage state machine, session lifecycle, extraction."""

import experience_chat
import pytest
import smart_llm
from test_helpers import query_db


@pytest.fixture(autouse=True)
def _reset_singleton():
    experience_chat._extractor = None
    yield
    experience_chat._extractor = None


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    """Block all LLM calls — force template fallback."""
    monkeypatch.setattr(
        smart_llm._http_client,
        "post",
        lambda *a, **kw: type("R", (), {"status_code": 500, "json": lambda self: {}})(),
    )


@pytest.fixture
def extractor(app):
    return experience_chat.get_experience_extractor()


@pytest.fixture
def user_id(app):
    from models import User

    return User.create("exp@test.com", "Pass!").id


# ---------------------------------------------------------------------------
# start_session
# ---------------------------------------------------------------------------


class TestStartSession:
    """Tests for ExperienceExtractor.start_session()."""

    def test_returns_session_id(self, extractor, user_id):
        result = extractor.start_session(user_id)
        assert "session_id" in result
        assert len(result["session_id"]) == 36  # UUID

    def test_returns_opening_message(self, extractor, user_id):
        result = extractor.start_session(user_id)
        assert "message" in result
        assert len(result["message"]) > 10

    def test_with_employer_and_client(self, extractor, user_id):
        result = extractor.start_session(user_id, employer="Acme Corp", client="BigCo")
        assert "Acme Corp" in result["message"]
        assert "BigCo" in result["message"]
        assert result["stage"] == "role"

    def test_with_employer_only(self, extractor, user_id):
        result = extractor.start_session(user_id, employer="Acme Corp")
        assert "Acme Corp" in result["message"]
        assert result["stage"] == "intro"

    def test_persists_session_to_db(self, extractor, user_id):
        result = extractor.start_session(user_id, employer="TestCo")
        rows = query_db("SELECT * FROM experience_sessions WHERE id = ?", (result["session_id"],))
        assert len(rows) == 1
        assert rows[0]["user_id"] == user_id
        assert rows[0]["employer"] == "TestCo"

    def test_saves_opening_message(self, extractor, user_id):
        result = extractor.start_session(user_id)
        rows = query_db(
            "SELECT * FROM experience_messages WHERE session_id = ?",
            (result["session_id"],),
        )
        assert len(rows) == 1
        assert rows[0]["role"] == "assistant"


# ---------------------------------------------------------------------------
# process_message
# ---------------------------------------------------------------------------


class TestProcessMessage:
    """Tests for ExperienceExtractor.process_message()."""

    def test_returns_response(self, extractor, user_id):
        session = extractor.start_session(user_id, employer="TestCo", client="ClientCo")
        result = extractor.process_message(session["session_id"], "Senior Developer")
        assert "message" in result
        assert "session_id" in result
        assert result["session_id"] == session["session_id"]

    def test_advances_stage(self, extractor, user_id):
        session = extractor.start_session(user_id, employer="Co", client="Cl")
        # Stage starts at "role" when employer+client provided
        result = extractor.process_message(session["session_id"], "Lead Engineer")
        # Should advance past role
        assert result["stage"] != "role"

    def test_extracts_title_at_role_stage(self, extractor, user_id):
        session = extractor.start_session(user_id, employer="Co", client="Cl")
        result = extractor.process_message(session["session_id"], "Solutions Architect")
        assert result["context"]["title"] == "Solutions Architect"

    def test_saves_both_messages(self, extractor, user_id):
        session = extractor.start_session(user_id)
        extractor.process_message(session["session_id"], "I worked at Google")
        rows = query_db(
            "SELECT role FROM experience_messages WHERE session_id = ? ORDER BY created_at",
            (session["session_id"],),
        )
        roles = [r["role"] for r in rows]
        assert "user" in roles
        # assistant messages: opening + response
        assert roles.count("assistant") >= 2

    def test_nonexistent_session_returns_error(self, extractor, user_id):
        result = extractor.process_message("fake-id", "hello")
        assert "error" in result

    def test_finalized_session_returns_error(self, extractor, user_id):
        session = extractor.start_session(user_id)
        extractor.finalize_session(session["session_id"], user_id)
        result = extractor.process_message(session["session_id"], "more input")
        assert "error" in result


# ---------------------------------------------------------------------------
# _extract_from_message
# ---------------------------------------------------------------------------


class TestExtractFromMessage:
    """Tests for _extract_from_message() — stage-based extraction."""

    def test_intro_extracts_employer(self, extractor):
        ctx = {"employer": "", "client": "", "title": ""}
        ctx = extractor._extract_from_message(ctx, "intro", "I worked at Microsoft")
        assert ctx["employer"] != ""

    def test_role_extracts_title(self, extractor):
        ctx = {"employer": "Co", "title": ""}
        ctx = extractor._extract_from_message(ctx, "role", "Senior Developer")
        assert ctx["title"] == "Senior Developer"

    def test_responsibilities_appends(self, extractor):
        ctx = {"responsibilities": []}
        ctx = extractor._extract_from_message(ctx, "responsibilities", "API design, code review")
        assert len(ctx["responsibilities"]) >= 2

    def test_technologies_appends(self, extractor):
        ctx = {"technologies": []}
        ctx = extractor._extract_from_message(ctx, "technologies", "Python, Docker, AWS")
        assert len(ctx["technologies"]) >= 2

    def test_outcomes_appends(self, extractor):
        ctx = {"outcomes": []}
        ctx = extractor._extract_from_message(
            ctx, "outcomes", "Reduced latency by 40%, increased throughput 3x"
        )
        assert len(ctx["outcomes"]) >= 1


# ---------------------------------------------------------------------------
# _advance_stage
# ---------------------------------------------------------------------------


class TestAdvanceStage:
    """Tests for _advance_stage() — stage progression logic."""

    def test_intro_to_role(self, extractor):
        result = extractor._advance_stage("intro", {}, "I worked at Google")
        assert result == "role"

    def test_role_to_responsibilities(self, extractor):
        result = extractor._advance_stage("role", {}, "Senior Engineer")
        assert result == "responsibilities"

    def test_complete_stays_complete(self, extractor):
        result = extractor._advance_stage("complete", {}, "anything")
        assert result == "complete"

    def test_sparse_response_skips_two_stages(self, extractor):
        # From "responsibilities" with "skip" → should jump 2 stages
        result = extractor._advance_stage("responsibilities", {}, "skip")
        assert result == "outcomes"  # skipped technologies

    def test_sparse_response_at_intro_no_skip(self, extractor):
        # intro/role never skip
        result = extractor._advance_stage("intro", {}, "skip")
        assert result == "role"


# ---------------------------------------------------------------------------
# _is_sparse_response
# ---------------------------------------------------------------------------


class TestIsSparseResponse:
    """Tests for _is_sparse_response() — skip detection."""

    def test_skip_phrases(self, extractor):
        for phrase in ["skip", "n/a", "none", "pass", "next"]:
            assert extractor._is_sparse_response(phrase) is True

    def test_substantive_text_not_sparse(self, extractor):
        assert extractor._is_sparse_response("Python, Docker, Kubernetes") is False

    def test_very_short_non_numeric(self, extractor):
        assert extractor._is_sparse_response("no") is True

    def test_short_with_number(self, extractor):
        assert extractor._is_sparse_response("5yrs") is False


# ---------------------------------------------------------------------------
# get_summary
# ---------------------------------------------------------------------------


class TestGetSummary:
    """Tests for ExperienceExtractor.get_summary()."""

    def test_returns_structured_summary(self, extractor, user_id):
        session = extractor.start_session(user_id, employer="TestCo", client="ClientCo")
        extractor.process_message(session["session_id"], "Lead Developer")
        summary = extractor.get_summary(session["session_id"])
        assert "employer" in summary
        assert "title" in summary
        assert "bullet_points" in summary
        assert summary["session_id"] == session["session_id"]

    def test_nonexistent_returns_error(self, extractor):
        result = extractor.get_summary("fake-id")
        assert "error" in result


# ---------------------------------------------------------------------------
# finalize_session
# ---------------------------------------------------------------------------


class TestFinalizeSession:
    """Tests for ExperienceExtractor.finalize_session()."""

    def test_creates_extracted_experience(self, extractor, user_id):
        session = extractor.start_session(user_id, employer="TestCo", client="ClientCo")
        extractor.process_message(session["session_id"], "Lead Developer")
        result = extractor.finalize_session(session["session_id"], user_id)
        assert result["status"] == "finalized"
        assert "experience_id" in result
        rows = query_db(
            "SELECT * FROM extracted_experiences WHERE session_id = ?",
            (session["session_id"],),
        )
        assert len(rows) == 1

    def test_marks_session_finalized(self, extractor, user_id):
        session = extractor.start_session(user_id)
        extractor.finalize_session(session["session_id"], user_id)
        rows = query_db(
            "SELECT is_finalized FROM experience_sessions WHERE id = ?",
            (session["session_id"],),
        )
        assert rows[0]["is_finalized"] == 1

    def test_applies_edits(self, extractor, user_id):
        session = extractor.start_session(user_id, employer="OldCo")
        extractor.finalize_session(
            session["session_id"], user_id, edits={"employer": "NewCo", "title": "Architect"}
        )
        rows = query_db(
            "SELECT employer, title FROM extracted_experiences WHERE session_id = ?",
            (session["session_id"],),
        )
        assert rows[0]["employer"] == "NewCo"
        assert rows[0]["title"] == "Architect"

    def test_nonexistent_returns_error(self, extractor, user_id):
        result = extractor.finalize_session("fake-id", user_id)
        assert "error" in result


# ---------------------------------------------------------------------------
# get_extracted_experiences
# ---------------------------------------------------------------------------


class TestGetExtractedExperiences:
    """Tests for ExperienceExtractor.get_extracted_experiences()."""

    def test_returns_list(self, extractor, user_id):
        result = extractor.get_extracted_experiences(user_id)
        assert isinstance(result, list)

    def test_includes_finalized(self, extractor, user_id):
        session = extractor.start_session(user_id, employer="Co")
        extractor.finalize_session(session["session_id"], user_id)
        result = extractor.get_extracted_experiences(user_id)
        assert len(result) == 1
        assert result[0]["employer"] == "Co"


# ---------------------------------------------------------------------------
# STAGES constant
# ---------------------------------------------------------------------------


class TestStagesConstant:
    """Tests for the STAGES list."""

    def test_stages_order(self):
        assert experience_chat.STAGES[0] == "intro"
        assert experience_chat.STAGES[-1] == "complete"
        assert len(experience_chat.STAGES) == 7

    def test_all_stages_present(self):
        expected = {
            "intro",
            "role",
            "responsibilities",
            "technologies",
            "outcomes",
            "challenges",
            "complete",
        }
        assert set(experience_chat.STAGES) == expected
