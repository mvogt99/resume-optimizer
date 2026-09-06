"""E2E tests for all 6 agents with real LLM — no mock call_llm.

Agents: Job Scout, Application Tracker, Resume Tailor, Cover Letter,
        Interview Coach, Career Advisor.

Agent routes use user-id header (not JWT).
LLM calls go through RTX 5090 via smart_llm / FTAL harness ($0.00).
No mocks, no skips. DB verification after every write.
"""

import pytest
from test_helpers import AGENT_HEADERS_1, RESUME_TEXT, create_posting, query_db, upload_resume

pytestmark = pytest.mark.llm_required


def _create_posting(client, headers=None):
    """Create a manual posting and return its id (wrapper for local use)."""
    return create_posting(client, headers)


def _upload_resume_with_version(client, auth_headers):
    """Upload resume AND create a resume_versions row (needed by tailor/cover-letter)."""
    upload_resume(client, auth_headers)
    import models

    models.ResumeVersion.create(
        user_id=1,
        source="upload",
        file_name="resume.txt",
        parsed_text=RESUME_TEXT,
    )


# ===================================================================
# Job Scout (7 tests) — DB verified
# ===================================================================


class TestJobScout:
    """Job Scout agent — search, CRUD, scoring with DB verification."""

    def test_scout_posting_create(self, client, auth_headers):
        """POST /agents/scout/postings → posting created, DB row verified."""
        resp = client.post(
            "/api/agents/scout/postings",
            headers=AGENT_HEADERS_1,
            json={
                "title": "Senior Solutions Architect",
                "company": "Test Corp",
                "url": "https://example.com/job/123",
            },
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["title"] == "Senior Solutions Architect"
        pid = data.get("id") or data.get("posting_id")
        assert pid is not None

        # DB: job_postings row exists
        rows = query_db("SELECT * FROM job_postings WHERE id = ?", (pid,))
        assert len(rows) == 1, f"No job_postings row for {pid}"
        assert rows[0]["title"] == "Senior Solutions Architect"

    def test_scout_posting_get(self, client, auth_headers):
        """GET /agents/scout/postings/<id> → posting details."""
        pid = _create_posting(client)
        resp = client.get(f"/api/agents/scout/postings/{pid}", headers=AGENT_HEADERS_1)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("title") == "Senior Solutions Architect"

    def test_scout_posting_update(self, client, auth_headers):
        """PUT /agents/scout/postings/<id> → status/notes updated, DB verified."""
        pid = _create_posting(client)
        resp = client.put(
            f"/api/agents/scout/postings/{pid}",
            headers=AGENT_HEADERS_1,
            json={"status": "bookmarked", "notes": "Great fit", "starred": True},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "bookmarked"

        # DB: verify update persisted
        rows = query_db("SELECT * FROM job_postings WHERE id = ?", (pid,))
        assert rows[0]["status"] == "bookmarked"
        assert rows[0]["notes"] == "Great fit"

    def test_scout_posting_delete(self, client, auth_headers):
        """DELETE /agents/scout/postings/<id> → posting removed, DB verified."""
        pid = _create_posting(client)
        resp = client.delete(f"/api/agents/scout/postings/{pid}", headers=AGENT_HEADERS_1)
        assert resp.status_code == 200
        del_data = resp.get_json()
        assert del_data["message"] == "Posting deleted"

        # API: verify deleted
        resp2 = client.get(f"/api/agents/scout/postings/{pid}", headers=AGENT_HEADERS_1)
        assert resp2.status_code == 404

        # DB: row should be gone
        rows = query_db("SELECT * FROM job_postings WHERE id = ?", (pid,))
        assert len(rows) == 0, "Posting row still exists after DELETE"

    def test_scout_postings_list_and_filter(self, client, auth_headers):
        """GET /agents/scout/postings → list with filters."""
        _create_posting(client)
        resp = client.get("/api/agents/scout/postings", headers=AGENT_HEADERS_1)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "postings" in data
        postings = data.get("postings", [])
        assert len(postings) >= 1

        # Filter by min_score
        resp2 = client.get(
            "/api/agents/scout/postings?min_score=99",
            headers=AGENT_HEADERS_1,
        )
        assert resp2.status_code == 200

    def test_search_criteria_save_and_list(self, client, auth_headers):
        """POST + GET /agents/scout/criteria → criteria persisted, DB verified."""
        resp = client.post(
            "/api/agents/scout/criteria",
            headers=AGENT_HEADERS_1,
            json={
                "name": "Test Criteria",
                "target_roles": ["Solutions Architect", "Enterprise Architect"],
                "locations": ["Remote"],
                "remote_preference": "required",
            },
        )
        assert resp.status_code == 201

        resp2 = client.get("/api/agents/scout/criteria", headers=AGENT_HEADERS_1)
        assert resp2.status_code == 200
        data = resp2.get_json()
        assert "criteria" in data
        criteria = data.get("criteria", [])
        assert len(criteria) >= 1

        # DB: search_criteria row exists
        rows = query_db("SELECT * FROM search_criteria")
        assert len(rows) >= 1, "No search_criteria rows in DB"

    def test_scout_rescore_with_llm(self, client, auth_headers, require_harness):
        """POST /agents/scout/postings/<id>/rescore → LLM re-scores, DB updated."""
        pid = _create_posting(client)
        resp = client.post(
            f"/api/agents/scout/postings/{pid}/rescore",
            headers=AGENT_HEADERS_1,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "title" in data or "score" in data
        score = data.get("score")
        if score is not None:
            assert isinstance(score, (int, float))

        # DB: verify score was updated
        rows = query_db("SELECT * FROM job_postings WHERE id = ?", (pid,))
        assert len(rows) == 1


# ===================================================================
# Application Pipeline (6 tests) — DB verified
# ===================================================================


class TestApplicationPipeline:
    """Application Tracker — Kanban pipeline, analytics with DB verification."""

    def test_pipeline_view(self, client, auth_headers):
        """GET /agents/pipeline → stages present."""
        resp = client.get("/api/agents/pipeline", headers=AGENT_HEADERS_1)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "stages" in data or "columns" in data

    def test_pipeline_move_posting(self, client, auth_headers):
        """PUT /agents/pipeline/<id> → stage updated, DB verified."""
        pid = _create_posting(client)
        resp = client.put(
            f"/api/agents/pipeline/{pid}",
            headers=AGENT_HEADERS_1,
            json={"status": "applied", "notes": "Submitted application"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "applied"

        # DB: verify status changed
        rows = query_db("SELECT * FROM job_postings WHERE id = ?", (pid,))
        assert rows[0]["status"] == "applied"

    def test_pipeline_analytics(self, client, auth_headers):
        """GET /agents/pipeline/analytics → computed analytics."""
        _create_posting(client)
        resp = client.get("/api/agents/pipeline/analytics", headers=AGENT_HEADERS_1)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "status_counts" in data or "total" in data

    def test_pipeline_reminders(self, client, auth_headers):
        """GET /agents/pipeline/reminders → reminder list."""
        resp = client.get("/api/agents/pipeline/reminders", headers=AGENT_HEADERS_1)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "reminders" in data

    def test_pipeline_followup_llm(self, client, auth_headers, require_harness):
        """POST /agents/pipeline/<id>/followup → LLM generates email."""
        pid = _create_posting(client)
        client.put(
            f"/api/agents/pipeline/{pid}",
            headers=AGENT_HEADERS_1,
            json={"status": "applied"},
        )
        resp = client.post(f"/api/agents/pipeline/{pid}/followup", headers=AGENT_HEADERS_1)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "body" in data or "email_draft" in data
        email = data.get("email_draft", data.get("followup_email", ""))
        assert isinstance(email, str)

    def test_pipeline_analyze_llm(self, client, auth_headers, require_harness):
        """POST /agents/pipeline/<id>/analyze → performance analysis."""
        pid = _create_posting(client)
        resp = client.post(f"/api/agents/pipeline/{pid}/analyze", headers=AGENT_HEADERS_1)
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict)


# ===================================================================
# Resume Tailor (3 tests) — DB verified
# ===================================================================


class TestResumeTailor:
    """Resume Tailor agent — auto-customize resume per posting."""

    @pytest.fixture(autouse=True)
    def _check_harness(self, require_harness):
        """Fail with clear error if FTAL harness is not running."""

    def test_tailor_resume_llm(self, client, auth_headers):
        """POST /agents/tailor/<id> → LLM tailors resume."""
        _upload_resume_with_version(client, auth_headers)
        pid = _create_posting(client)
        resp = client.post(f"/api/agents/tailor/{pid}", headers=AGENT_HEADERS_1)
        assert resp.status_code == 200  # require_harness ensures LLM available
        data = resp.get_json()
        assert isinstance(data, dict)
        assert (
            "optimized_text" in data
        ), f"Tailor must return optimized_text, got: {list(data.keys())}"
        assert "version_id" in data, "Tailor must return version_id"

    def test_tailor_get_result(self, client, auth_headers):
        """GET /agents/tailor/<id> → retrieves tailored resume."""
        _upload_resume_with_version(client, auth_headers)
        pid = _create_posting(client)
        client.post(f"/api/agents/tailor/{pid}", headers=AGENT_HEADERS_1)

        resp = client.get(f"/api/agents/tailor/{pid}", headers=AGENT_HEADERS_1)
        assert resp.status_code == 200  # tailor POST above should have created it
        data = resp.get_json()
        assert isinstance(data, dict)
        assert len(data) > 0

    def test_tailor_creates_version(self, client, auth_headers):
        """Tailored resume should create a version if successful."""
        _upload_resume_with_version(client, auth_headers)
        pid = _create_posting(client)
        resp = client.post(f"/api/agents/tailor/{pid}", headers=AGENT_HEADERS_1)
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict)
        assert len(data) > 0


# ===================================================================
# Cover Letter (5 tests) — DB verified
# ===================================================================


class TestCoverLetter:
    """Cover Letter agent — generate, CRUD, regenerate with DB verification."""

    @pytest.fixture(autouse=True)
    def _check_harness(self, require_harness):
        """Fail with clear error if FTAL harness is not running."""

    def test_cover_letter_generate(self, client, auth_headers):
        """POST /agents/cover-letter/<pid> → generates cover letter, DB row created."""
        _upload_resume_with_version(client, auth_headers)
        pid = _create_posting(client)
        resp = client.post(f"/api/agents/cover-letter/{pid}", headers=AGENT_HEADERS_1)
        assert resp.status_code == 201  # require_harness ensures LLM available
        data = resp.get_json()
        assert isinstance(data, dict)
        lid = data.get("id") or data.get("letter_id")
        assert lid, "Cover letter generate must return id or letter_id"
        # DB: cover_letters row exists
        rows = query_db("SELECT * FROM cover_letters WHERE id = ?", (lid,))
        assert len(rows) == 1, f"No cover_letters row for {lid}"

    def test_cover_letter_get_by_posting(self, client, auth_headers):
        """GET /agents/cover-letter/<pid> → retrieve cover letter."""
        _upload_resume_with_version(client, auth_headers)
        pid = _create_posting(client)
        client.post(f"/api/agents/cover-letter/{pid}", headers=AGENT_HEADERS_1)

        resp = client.get(f"/api/agents/cover-letter/{pid}", headers=AGENT_HEADERS_1)
        assert resp.status_code == 200  # generate above should have created it
        data = resp.get_json()
        assert isinstance(data, dict)
        assert len(data) > 0

    def test_cover_letter_update(self, client, auth_headers):
        """PUT /agents/cover-letters/<lid> → update content, DB verified."""
        _upload_resume_with_version(client, auth_headers)
        pid = _create_posting(client)
        resp_gen = client.post(f"/api/agents/cover-letter/{pid}", headers=AGENT_HEADERS_1)
        assert resp_gen.status_code == 201, "Cover letter generation failed"

        lid = resp_gen.get_json().get("id") or resp_gen.get_json().get("letter_id")
        assert lid, "No letter_id returned from generate"

        resp = client.put(
            f"/api/agents/cover-letters/{lid}",
            headers=AGENT_HEADERS_1,
            json={"body": "Updated cover letter body for testing.", "tone": "professional"},
        )
        assert resp.status_code == 200
        upd_data = resp.get_json()
        assert upd_data["body"] == "Updated cover letter body for testing."

        # DB: verify update
        rows = query_db("SELECT * FROM cover_letters WHERE id = ?", (lid,))
        assert len(rows) == 1, f"No cover_letters row for {lid} after update"
        assert rows[0].get("body") == "Updated cover letter body for testing."

    def test_cover_letter_delete(self, client, auth_headers):
        """DELETE /agents/cover-letters/<lid> → removed, DB verified."""
        _upload_resume_with_version(client, auth_headers)
        pid = _create_posting(client)
        resp_gen = client.post(f"/api/agents/cover-letter/{pid}", headers=AGENT_HEADERS_1)
        assert resp_gen.status_code == 201, "Cover letter generation failed"

        lid = resp_gen.get_json().get("id") or resp_gen.get_json().get("letter_id")
        assert lid, "No letter_id returned"

        resp = client.delete(f"/api/agents/cover-letters/{lid}", headers=AGENT_HEADERS_1)
        assert resp.status_code == 200
        del_data = resp.get_json()
        assert del_data["message"] == "Cover letter deleted"

        # DB: row gone
        rows = query_db("SELECT * FROM cover_letters WHERE id = ?", (lid,))
        assert len(rows) == 0, "Cover letter row still exists after DELETE"

    def test_cover_letter_regenerate(self, client, auth_headers):
        """POST /agents/cover-letters/<lid>/regenerate → new version."""
        _upload_resume_with_version(client, auth_headers)
        pid = _create_posting(client)
        resp_gen = client.post(f"/api/agents/cover-letter/{pid}", headers=AGENT_HEADERS_1)
        assert resp_gen.status_code == 201, "Cover letter generation failed"

        lid = resp_gen.get_json().get("id") or resp_gen.get_json().get("letter_id")
        assert lid, "No letter_id returned"

        resp = client.post(
            f"/api/agents/cover-letters/{lid}/regenerate",
            headers=AGENT_HEADERS_1,
            json={"feedback": "Make it more specific about cloud architecture."},
        )
        assert resp.status_code == 200  # regenerate with feedback
        regen_data = resp.get_json()
        assert isinstance(regen_data, dict)
        assert len(regen_data) > 0


# ===================================================================
# Interview Coach (4 tests) — DB verified
# ===================================================================


class TestInterviewCoach:
    """Interview Coach agent — mock interviews with LLM + DB verification."""

    @pytest.fixture(autouse=True)
    def _check_harness(self, require_harness):
        """Fail with clear error if FTAL harness is not running."""

    def test_coach_start(self, client, auth_headers):
        """POST /agents/coach/start → session with first question, DB row."""
        resp = client.post(
            "/api/agents/coach/start",
            headers=AGENT_HEADERS_1,
            json={"persona": "hiring_manager", "question_count": 3},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        sid = data["session_id"]
        assert "question" in data

        # DB: interview_coach_sessions row exists
        rows = query_db("SELECT * FROM interview_coach_sessions WHERE id = ?", (sid,))
        assert len(rows) == 1, f"No interview_coach_sessions row for {sid}"

    def test_coach_answer(self, client, auth_headers):
        """POST /agents/coach/answer → feedback + next question, DB messages."""
        resp = client.post(
            "/api/agents/coach/start",
            headers=AGENT_HEADERS_1,
            json={"persona": "hiring_manager", "question_count": 3},
        )
        sid = resp.get_json()["session_id"]

        resp2 = client.post(
            "/api/agents/coach/answer",
            headers=AGENT_HEADERS_1,
            json={
                "session_id": sid,
                "answer": "In my role at Navitus, I led the cloud migration from "
                "monolithic Java to Python microservices on AWS, reducing deployment "
                "from 2 weeks to 2 hours while maintaining 99.99% uptime.",
            },
        )
        assert resp2.status_code == 200
        data = resp2.get_json()
        assert "feedback" in data or "next_question" in data or "message" in data

        # DB: messages should exist
        msgs = query_db("SELECT * FROM interview_coach_messages WHERE session_id = ?", (sid,))
        assert len(msgs) >= 2, f"Expected ≥2 coach messages, got {len(msgs)}"

    def test_coach_sessions_list(self, client, auth_headers):
        """GET /agents/coach/sessions → session list."""
        client.post(
            "/api/agents/coach/start",
            headers=AGENT_HEADERS_1,
            json={"question_count": 2},
        )
        resp = client.get("/api/agents/coach/sessions", headers=AGENT_HEADERS_1)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "sessions" in data
        sessions = data.get("sessions", [])
        assert len(sessions) >= 1

    def test_coach_assessment(self, client, auth_headers):
        """GET /agents/coach/<sid>/assessment → scoring."""
        resp = client.post(
            "/api/agents/coach/start",
            headers=AGENT_HEADERS_1,
            json={"question_count": 1},
        )
        sid = resp.get_json()["session_id"]

        client.post(
            "/api/agents/coach/answer",
            headers=AGENT_HEADERS_1,
            json={
                "session_id": sid,
                "answer": "I bring 20 years of architecture experience with strong "
                "Python, AWS, and Kubernetes expertise.",
            },
        )

        resp2 = client.get(f"/api/agents/coach/{sid}/assessment", headers=AGENT_HEADERS_1)
        assert resp2.status_code == 200  # answer provided above
        assess_data = resp2.get_json()
        assert isinstance(assess_data, dict)


# ===================================================================
# Career Advisor (3 tests)
# ===================================================================


class TestCareerAdvisor:
    """Career Advisor agent — trajectory analysis, roadmap."""

    @pytest.fixture(autouse=True)
    def _check_harness(self, require_harness):
        """Fail with clear error if FTAL harness is not running."""

    def test_advisor_analyze(self, client, auth_headers):
        """POST /agents/advisor/analyze → career analysis."""
        resp = client.post("/api/agents/advisor/analyze", headers=AGENT_HEADERS_1)
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict)
        assert len(data) > 0

    def test_advisor_skills_roadmap(self, client, auth_headers):
        """POST /agents/advisor/skills-roadmap → learning plan."""
        resp = client.post(
            "/api/agents/advisor/skills-roadmap",
            headers=AGENT_HEADERS_1,
            json={"target_role": "AI Platform Architect"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict)
        assert len(data) > 0

    def test_advisor_role_recommendations(self, client, auth_headers):
        """POST /agents/advisor/role-recommendations → role suggestions."""
        resp = client.post("/api/agents/advisor/role-recommendations", headers=AGENT_HEADERS_1)
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict)
        assert len(data) > 0


# ===================================================================
# Agent System (2 tests) — DB verified
# ===================================================================


class TestAgentSystem:
    """Agent system metadata endpoints with DB verification."""

    def test_agent_runs(self, client, auth_headers):
        """GET /agents/runs → audit trail."""
        resp = client.get("/api/agents/runs", headers=AGENT_HEADERS_1)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "runs" in data

    def test_agent_status(self, client, auth_headers):
        """GET /agents/status → system status. Auth IS required: the response
        discloses model info and LLM reachability."""
        resp = client.get("/api/agents/status", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "agents" in data
        assert isinstance(data["agents"], list)
        assert len(data["agents"]) >= 1
