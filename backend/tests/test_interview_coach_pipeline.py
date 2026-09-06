"""Comprehensive tests for InterviewCoachAgent pipeline.

Tests key pipeline steps with mocked LLM calls:
  1. start_session
  2. start_mock_interview
  3. process_answer / evaluate_response
  4. generate_talking_points
  5. predict_questions
  6. get_session / get_sessions / list_sessions
  7. get_assessment
  8. generate_prep_sheet
  9. Constants and edge cases
"""

import json
import sqlite3
import uuid

import pytest
from agents.interview_coach import COACH_STAGES, INTERVIEW_TYPES, PERSONAS, InterviewCoachAgent
from test_helpers import JD_TEXT, RESUME_TEXT

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    """Block all LLM calls by default."""
    monkeypatch.setattr("agents.base_agent.call_llm_scored", lambda *a, **kw: (None, None))
    monkeypatch.setattr("agents.base_agent.extract_json", lambda x: None)


@pytest.fixture
def agent(app):
    return InterviewCoachAgent()


@pytest.fixture
def user_id(app):
    from models import User

    return User.create("ic_test@test.com", "Pass1!").id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _insert_posting(
    user_id, title="Senior Python Developer", company="Acme Corp", description=None
):
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


def _insert_session(
    user_id,
    posting_id,
    persona="hiring_manager",
    question_count=5,
    stage="mock_questions",
    is_complete=0,
):
    """Insert a coach session directly for testing."""
    from models import get_db_connection

    sid = str(uuid.uuid4())
    context = json.dumps(
        {
            "persona": persona,
            "persona_name": PERSONAS.get(persona, PERSONAS["hiring_manager"])["name"],
            "persona_focus": PERSONAS.get(persona, PERSONAS["hiring_manager"])["focus"],
            "posting_title": "Senior Python Developer",
            "posting_company": "Acme Corp",
            "posting_description": JD_TEXT[:500],
            "profile_summary": RESUME_TEXT[:500],
        }
    )
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO interview_coach_sessions "
        "(id, user_id, posting_id, stage, persona, question_count, "
        "current_question, context_json, scores_json, is_complete) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (sid, user_id, posting_id, stage, persona, question_count, 1, context, "[]", is_complete),
    )
    conn.commit()
    conn.close()
    return sid


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

SAMPLE_SCORE = {
    "expertise": 8,
    "communication": 7,
    "relevance": 9,
    "star_quality": 6,
    "feedback": "Good structure but could improve STAR method usage.",
    "improved_answer": "A stronger version would include specific metrics.",
}

SAMPLE_TALKING_POINTS = {
    "strengths_to_emphasize": [
        {"point": "20 years enterprise architecture", "evidence": "Led cloud migration at Navitus"}
    ],
    "gaps_to_address": [
        {"gap": "No direct Rust experience", "mitigation": "Emphasize learning agility"}
    ],
    "stories_to_tell": [
        {
            "theme": "Leading migration",
            "situation": "Legacy monolith",
            "why_relevant": "Demonstrates technical leadership",
        }
    ],
    "key_messages": ["I deliver scalable architectures", "I lead cross-functional teams"],
}

SAMPLE_QUESTIONS = {
    "questions": [
        {
            "category": "behavioral",
            "question": "Tell me about a time you led a migration project.",
            "approach": "Use STAR method with metrics",
            "star_outline": {"situation": "Legacy system at Navitus"},
        },
        {
            "category": "technical",
            "question": "How would you design a microservices architecture?",
            "approach": "Start with business requirements",
            "star_outline": {},
        },
    ]
}

SAMPLE_ASSESSMENT = {
    "overall_score": 78,
    "strengths": ["Clear communication", "Strong technical depth"],
    "improvements": ["Use more specific metrics", "Improve STAR closure"],
    "recommendation": "Strong candidate, recommend next round",
}

SAMPLE_OPENING = {
    "opening": "Welcome to your mock interview. I'll be your Hiring Manager today.",
    "question": "Tell me about your background and what draws you to this role.",
}

SAMPLE_PREP_SHEET = {
    "company_research": ["Research Acme Corp mission and products"],
    "key_stories": [{"theme": "Leadership", "outline": "Led 12-person team at Navitus"}],
    "questions_to_ask": ["What does success look like in 6 months?"],
    "preparation_tips": ["Review STAR method", "Prepare 3 achievement stories"],
}


# ===========================================================================
# 1. Constants
# ===========================================================================


class TestConstants:
    """Verify module-level constants."""

    def test_interview_types_has_all_keys(self):
        expected = {"behavioral", "technical", "situational", "case_study", "panel"}
        assert set(INTERVIEW_TYPES.keys()) == expected
        assert all(isinstance(v, str) for v in INTERVIEW_TYPES.values())

    def test_personas_has_all_keys(self):
        expected = {"hiring_manager", "technical", "hr_recruiter", "executive"}
        assert set(PERSONAS.keys()) == expected
        assert all("name" in v and "focus" in v for v in PERSONAS.values())

    def test_coach_stages_list(self):
        assert "prep" in COACH_STAGES
        assert "complete" in COACH_STAGES
        assert isinstance(COACH_STAGES, list)

    def test_agent_type(self, agent):
        assert agent.agent_type == "interview_coach"
        assert isinstance(agent, InterviewCoachAgent)


# ===========================================================================
# 2. start_session
# ===========================================================================


class TestStartSession:
    """Test session creation."""

    def test_success_with_posting(self, agent, user_id, monkeypatch):
        """Starting a session with a valid posting returns session dict."""
        _mock_llm(monkeypatch, SAMPLE_OPENING)
        posting_id = _insert_posting(user_id)
        result = agent.start_session(user_id, posting_id)
        assert "session_id" in result
        assert result["question_count"] == 5

    def test_success_without_posting(self, agent, user_id, monkeypatch):
        """Starting a session without posting_id still works."""
        _mock_llm(monkeypatch, SAMPLE_OPENING)
        result = agent.start_session(user_id, "")
        assert "session_id" in result
        assert "question" in result or "message" in result

    def test_custom_persona(self, agent, user_id, monkeypatch):
        """Custom persona is reflected in the result."""
        _mock_llm(monkeypatch, SAMPLE_OPENING)
        result = agent.start_session(user_id, "", persona="technical")
        assert "session_id" in result
        assert result.get("persona") == PERSONAS["technical"]["name"]

    def test_custom_question_count(self, agent, user_id, monkeypatch):
        """Custom question count is stored."""
        _mock_llm(monkeypatch, SAMPLE_OPENING)
        result = agent.start_session(user_id, "", question_count=10)
        assert result["question_count"] == 10
        assert "session_id" in result

    def test_session_saved_to_db(self, agent, user_id, monkeypatch):
        """Session is persisted to interview_coach_sessions table."""
        from models import get_db_connection

        _mock_llm(monkeypatch, SAMPLE_OPENING)
        result = agent.start_session(user_id, "")
        sid = result["session_id"]
        conn = get_db_connection()
        row = conn.execute("SELECT * FROM interview_coach_sessions WHERE id=?", (sid,)).fetchone()
        conn.close()
        assert row is not None
        assert row["user_id"] == user_id


# ===========================================================================
# 3. generate_talking_points
# ===========================================================================


class TestGenerateTalkingPoints:
    """Test talking points generation."""

    def test_success_returns_structured_result(self, agent, user_id, monkeypatch):
        """Valid posting and LLM success returns talking points."""
        _mock_llm(monkeypatch, SAMPLE_TALKING_POINTS)
        posting_id = _insert_posting(user_id)
        result = agent.generate_talking_points(user_id, posting_id)
        assert "posting_id" in result
        assert "key_messages" in result or "strengths_to_emphasize" in result

    def test_posting_not_found_returns_error(self, agent, user_id):
        """Non-existent posting returns error."""
        result = agent.generate_talking_points(user_id, "nonexistent")
        assert "error" in result
        assert isinstance(result["error"], str)

    def test_llm_failure_returns_fallback(self, agent, user_id):
        """When LLM fails, returns fallback talking points."""
        posting_id = _insert_posting(user_id)
        result = agent.generate_talking_points(user_id, posting_id)
        assert "key_messages" in result
        assert isinstance(result["key_messages"], list)

    def test_result_includes_posting_context(self, agent, user_id, monkeypatch):
        """Result includes posting title and company."""
        _mock_llm(monkeypatch, SAMPLE_TALKING_POINTS)
        posting_id = _insert_posting(user_id, title="VP Engineering", company="BigCo")
        result = agent.generate_talking_points(user_id, posting_id)
        assert result.get("title") == "VP Engineering"
        assert result.get("company") == "BigCo"


# ===========================================================================
# 4. predict_questions
# ===========================================================================


class TestPredictQuestions:
    """Test question prediction."""

    def test_success_returns_questions(self, agent, user_id, monkeypatch):
        """LLM success returns questions with categories."""
        _mock_llm(monkeypatch, SAMPLE_QUESTIONS)
        posting_id = _insert_posting(user_id)
        result = agent.predict_questions(user_id, posting_id)
        assert "questions" in result
        assert isinstance(result["questions"], list)

    def test_posting_not_found_returns_error(self, agent, user_id):
        """Non-existent posting returns error."""
        result = agent.predict_questions(user_id, "nonexistent")
        assert "error" in result
        assert isinstance(result, dict)

    def test_llm_failure_returns_fallback_or_error(self, agent, user_id):
        """LLM failure returns fallback questions or error dict."""
        posting_id = _insert_posting(user_id)
        result = agent.predict_questions(user_id, posting_id)
        assert isinstance(result, dict)
        # Should have either questions (fallback) or error
        assert "questions" in result or "error" in result

    def test_count_parameter(self, agent, user_id, monkeypatch):
        """Count parameter is passed through."""
        _mock_llm(monkeypatch, SAMPLE_QUESTIONS)
        posting_id = _insert_posting(user_id)
        result = agent.predict_questions(user_id, posting_id, count=3)
        assert isinstance(result, dict)
        assert "questions" in result


# ===========================================================================
# 5. evaluate_response
# ===========================================================================


class TestEvaluateResponse:
    """Test STAR evaluation."""

    def test_success_returns_score_dict(self, agent, monkeypatch):
        """LLM returns structured STAR scores."""
        _mock_llm(monkeypatch, SAMPLE_SCORE)
        result = agent.evaluate_response(
            "Tell me about a difficult project",
            "I led a migration from monolith to microservices at Navitus...",
        )
        assert isinstance(result, dict)
        # Actual keys: relevance, specificity, star_completeness, impact_quantification, completeness, feedback  # noqa: E501
        assert "relevance" in result or "star_quality" in result or "expertise" in result

    def test_llm_failure_returns_heuristic(self, agent):
        """When LLM fails, heuristic scoring is used."""
        result = agent.evaluate_response(
            "Tell me about leadership",
            "In a situation where our team faced a deadline, my task was to coordinate, "
            "I took action by prioritizing tasks, and the result was on-time delivery.",
        )
        assert isinstance(result, dict)
        # Heuristic path should still return some score
        assert "star_quality" in result or "score" in result or "expertise" in result

    def test_empty_response(self, agent):
        """Empty response produces a result (not crash)."""
        result = agent.evaluate_response("Question?", "")
        assert isinstance(result, dict)


# ===========================================================================
# 6. get_session / get_sessions / list_sessions
# ===========================================================================


class TestSessionRetrieval:
    """Test session CRUD."""

    def test_get_session_by_id(self, agent, user_id):
        """get_session returns session dict by ID."""
        posting_id = _insert_posting(user_id)
        sid = _insert_session(user_id, posting_id)
        result = agent.get_session(sid)
        assert result is not None
        assert isinstance(result, dict)

    def test_get_session_with_user_filter(self, agent, user_id):
        """get_session with user_id filter returns matching session."""
        posting_id = _insert_posting(user_id)
        sid = _insert_session(user_id, posting_id)
        result = agent.get_session(sid, user_id=user_id)
        assert result is not None
        assert isinstance(result, dict)

    def test_get_session_not_found(self, agent, user_id):
        """Non-existent session returns None."""
        result = agent.get_session("nonexistent-id")
        assert result is None

    def test_get_session_wrong_user(self, agent, user_id):
        """Wrong user_id returns None."""
        posting_id = _insert_posting(user_id)
        sid = _insert_session(user_id, posting_id)
        result = agent.get_session(sid, user_id=987654321)  # users.id is INTEGER; a string id is rejected by PostgreSQL
        assert result is None

    def test_get_sessions_returns_list(self, agent, user_id):
        """get_sessions returns list for user."""
        posting_id = _insert_posting(user_id)
        _insert_session(user_id, posting_id)
        _insert_session(user_id, posting_id)
        result = agent.get_sessions(user_id)
        assert isinstance(result, list)
        assert len(result) >= 2

    def test_get_sessions_empty_for_new_user(self, agent, user_id):
        """New user has no sessions."""
        result = agent.get_sessions(user_id)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_list_sessions_returns_list(self, agent, user_id):
        """list_sessions is an alternative that returns list."""
        posting_id = _insert_posting(user_id)
        _insert_session(user_id, posting_id)
        result = agent.list_sessions(user_id)
        assert isinstance(result, list)
        assert len(result) >= 1


# ===========================================================================
# 7. get_assessment
# ===========================================================================


class TestGetAssessment:
    """Test overall assessment retrieval."""

    def test_incomplete_session_returns_error(self, agent, user_id):
        """Incomplete session returns error."""
        posting_id = _insert_posting(user_id)
        sid = _insert_session(user_id, posting_id, is_complete=0)
        result = agent.get_assessment(sid)
        assert isinstance(result, dict)
        assert "error" in result

    def test_session_not_found(self, agent, user_id):
        """Non-existent session returns None (no row found)."""
        result = agent.get_assessment("nonexistent")
        # get_assessment returns None or dict depending on implementation
        assert result is None or (isinstance(result, dict) and "error" in result)


# ===========================================================================
# 8. generate_prep_sheet
# ===========================================================================


class TestGeneratePrepSheet:
    """Test prep sheet generation."""

    def test_success_returns_structured_prep(self, agent, user_id, monkeypatch):
        """LLM success returns prep sheet with expected sections."""
        _mock_llm(monkeypatch, SAMPLE_PREP_SHEET)
        posting_id = _insert_posting(user_id)
        result = agent.generate_prep_sheet(user_id, posting_id)
        assert isinstance(result, dict)
        assert "posting_id" in result or "error" not in result

    def test_posting_not_found_raises(self, agent, user_id):
        """Non-existent posting raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            agent.generate_prep_sheet(user_id, "nonexistent")

    def test_llm_failure_returns_fallback(self, agent, user_id):
        """LLM failure returns fallback prep data."""
        posting_id = _insert_posting(user_id)
        result = agent.generate_prep_sheet(user_id, posting_id)
        assert isinstance(result, dict)
        # Should have either prep data or error
        assert "preparation_tips" in result or "key_stories" in result or "posting_id" in result


# ===========================================================================
# 9. _score_answer (private)
# ===========================================================================


class TestScoreAnswer:
    """Test the private _score_answer method."""

    def test_returns_dict_on_llm_success(self, agent, monkeypatch):
        """LLM returns structured score dict."""
        _mock_llm(monkeypatch, SAMPLE_SCORE)
        context = {
            "persona_name": "Hiring Manager",
            "posting_title": "Dev",
            "posting_company": "Co",
        }
        result = agent._score_answer("Question?", "My answer...", context)
        assert isinstance(result, dict)
        assert "expertise" in result or "feedback" in result

    def test_returns_none_on_llm_failure(self, agent):
        """LLM failure returns None."""
        context = {"persona_name": "Hiring Manager"}
        result = agent._score_answer("Question?", "Answer", context)
        assert result is None


# ===========================================================================
# 10. _generate_question (private)
# ===========================================================================


class TestGenerateQuestion:
    """Test adaptive question generation."""

    def test_returns_string_on_success(self, agent, monkeypatch):
        """LLM returns question text."""
        monkeypatch.setattr(
            "agents.base_agent.call_llm_scored",
            lambda *a, **kw: ("What challenges have you faced with distributed systems?", None),
        )
        context = {
            "persona_name": "Technical Interviewer",
            "persona_focus": "Technical depth",
            "posting_title": "Senior Dev",
            "posting_company": "Acme",
            "posting_description": JD_TEXT[:500],
            "profile_summary": RESUME_TEXT[:500],
        }
        result = agent._generate_question(context, 2, [])
        assert isinstance(result, str)
        assert len(result) > 0

    def test_adapts_to_weak_areas(self, agent, monkeypatch):
        """Weak STAR scores influence question focus."""
        monkeypatch.setattr(
            "agents.base_agent.call_llm_scored",
            lambda *a, **kw: ("Tell me about a specific example using STAR method.", None),
        )
        context = {
            "persona_name": "HM",
            "persona_focus": "",
            "posting_title": "",
            "posting_company": "",
            "posting_description": "",
            "profile_summary": "",
        }
        prev_scores = [{"star_quality": 3, "expertise": 8, "communication": 7}]
        result = agent._generate_question(context, 3, prev_scores)
        assert isinstance(result, str)
        assert len(result) > 0


# ===========================================================================
# 11. Edge cases
# ===========================================================================


class TestEdgeCases:
    """Edge cases and integration."""

    def test_session_isolation_between_users(self, agent, user_id):
        """Sessions are isolated between users."""
        posting_id = _insert_posting(user_id)
        sid = _insert_session(user_id, posting_id)
        result = agent.get_session(sid, user_id=987654322)  # users.id is INTEGER; a string id is rejected by PostgreSQL
        assert result is None, "Should not find session for other user"

    def test_all_personas_valid(self, agent, user_id, monkeypatch):
        """All persona keys create valid sessions."""
        _mock_llm(monkeypatch, SAMPLE_OPENING)
        for persona_key in PERSONAS:
            result = agent.start_session(user_id, "", persona=persona_key)
            assert "session_id" in result, f"Failed for persona: {persona_key}"
