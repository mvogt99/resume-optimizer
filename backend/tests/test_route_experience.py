"""Route tests for experience_routes.py — experience chat, skills interview, ATS improvement.

Pure API tests. Monkeypatches LLM for deterministic responses.
"""

import json

import pytest
from test_helpers import JD_TEXT, RESUME_TEXT, query_db

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _patch_experience_llm(monkeypatch):
    """Block all LLM calls — experience_chat falls back to template questions."""

    def fake_call_llm(prompt, task_type="coding", max_tokens=2048):
        return None  # triggers template fallback in experience_chat

    monkeypatch.setattr("llm_helper.call_llm", fake_call_llm)


# ---------------------------------------------------------------------------
# Experience Chat — start
# ---------------------------------------------------------------------------


class TestExperienceStart:
    def test_start_session(self, client, auth_headers):
        resp = client.post(
            "/api/experience/start",
            headers=auth_headers,
            json={"employer": "Navitus", "client": "BCBSMA"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert "session_id" in data
        assert isinstance(data["session_id"], str)
        assert len(data["session_id"]) > 0
        # Should have initial question
        assert "question" in data or "message" in data
        # DB: session created
        rows = query_db("SELECT id FROM experience_sessions WHERE user_id = 1")
        assert len(rows) >= 1

    def test_start_session_no_employer(self, client, auth_headers):
        resp = client.post(
            "/api/experience/start",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert "session_id" in data
        # DB: session created even without employer
        rows = query_db("SELECT id FROM experience_sessions WHERE user_id = 1")
        assert len(rows) >= 1

    def test_start_session_auth_required(self, client):
        resp = client.post("/api/experience/start", json={"employer": "X"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Experience Chat — message
# ---------------------------------------------------------------------------


class TestExperienceMessage:
    def _start(self, client, auth_headers):
        resp = client.post(
            "/api/experience/start",
            headers=auth_headers,
            json={"employer": "OPI"},
        )
        return resp.get_json()["session_id"]

    def test_send_message(self, client, auth_headers):
        sid = self._start(client, auth_headers)
        resp = client.post(
            "/api/experience/message",
            headers=auth_headers,
            json={
                "session_id": sid,
                "message": "I led a team of 8 engineers on a microservices migration.",
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        # Should have a follow-up question or status
        assert isinstance(data, dict)
        assert "error" not in data
        # DB: message stored
        rows = query_db("SELECT role FROM experience_messages WHERE session_id = ?", (sid,))
        assert len(rows) >= 1

    def test_send_message_missing_session(self, client, auth_headers):
        resp = client.post(
            "/api/experience/message",
            headers=auth_headers,
            json={"message": "hello"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert data["error"] != ""

    def test_send_message_missing_text(self, client, auth_headers):
        resp = client.post(
            "/api/experience/message",
            headers=auth_headers,
            json={"session_id": "fake-id"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data


# ---------------------------------------------------------------------------
# Experience Chat — summary
# ---------------------------------------------------------------------------


class TestExperienceSummary:
    def test_summary_not_found(self, client, auth_headers):
        resp = client.get("/api/experience/summary/nonexistent", headers=auth_headers)
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data

    def test_summary_of_session(self, client, auth_headers):
        # Start and send a message first
        start = client.post(
            "/api/experience/start",
            headers=auth_headers,
            json={"employer": "AHEAD"},
        )
        sid = start.get_json()["session_id"]
        client.post(
            "/api/experience/message",
            headers=auth_headers,
            json={"session_id": sid, "message": "Built cloud migration framework"},
        )
        resp = client.get(f"/api/experience/summary/{sid}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict)
        # DB: session exists
        rows = query_db("SELECT id FROM experience_sessions WHERE id = ?", (sid,))
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# Experience Chat — finalize
# ---------------------------------------------------------------------------


class TestExperienceFinalize:
    def test_finalize_not_found(self, client, auth_headers):
        resp = client.post("/api/experience/finalize/nonexistent", headers=auth_headers, json={})
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data


# ---------------------------------------------------------------------------
# Experience Chat — list
# ---------------------------------------------------------------------------


class TestExperienceList:
    def test_list_empty(self, client, auth_headers):
        resp = client.get("/api/experience/list", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "experiences" in data
        assert data["experiences"] == []

    def test_list_after_start(self, client, auth_headers):
        client.post(
            "/api/experience/start",
            headers=auth_headers,
            json={"employer": "TechCo"},
        )
        resp = client.get("/api/experience/list", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data["experiences"], list)
        # DB: at least one session exists
        rows = query_db("SELECT id FROM experience_sessions WHERE user_id = 1")
        assert len(rows) >= 1


# ---------------------------------------------------------------------------
# Skills Interview
# ---------------------------------------------------------------------------


class TestSkillsInterview:
    def test_start_skills_interview(self, client, auth_headers):
        resp = client.post(
            "/api/skills-interview/start",
            headers=auth_headers,
            json={"skills": ["Python", "AWS", "Docker"]},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "session_id" in data
        assert isinstance(data["session_id"], str)
        assert len(data["session_id"]) > 0
        # DB: verify session record created
        rows = query_db("SELECT id FROM skills_interview_sessions WHERE user_id = 1")
        assert len(rows) >= 1

    def test_start_skills_interview_no_skills(self, client, auth_headers):
        resp = client.post(
            "/api/skills-interview/start",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert isinstance(data["error"], str)

    def test_skills_message_missing_fields(self, client, auth_headers):
        resp = client.post(
            "/api/skills-interview/message",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_skills_summary_not_found(self, client, auth_headers):
        resp = client.get("/api/skills-interview/nonexistent/summary", headers=auth_headers)
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data

    def test_skills_finalize_not_found(self, client, auth_headers):
        resp = client.post(
            "/api/skills-interview/nonexistent/finalize",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data


# ---------------------------------------------------------------------------
# ATS Improvement Chat
# ---------------------------------------------------------------------------


class TestATSImprovement:
    def test_start_ats_improvement(self, client, auth_headers, resume_and_jd):
        rid, _ = resume_and_jd
        resp = client.post(
            "/api/ats-improve/start",
            headers=auth_headers,
            json={
                "resume_id": rid,
                "score_data": {
                    "weaknesses": ["missing keywords", "weak summary"],
                    "missing_keywords": ["terraform", "kafka"],
                },
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "session_id" in data
        # DB: resume still exists
        rows = query_db("SELECT id FROM resumes WHERE id = ?", (rid,))
        assert len(rows) == 1

    def test_start_ats_no_score_data(self, client, auth_headers):
        resp = client.post(
            "/api/ats-improve/start",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert isinstance(data["error"], str)
        # DB: no session created for invalid request
        rows = query_db("SELECT COUNT(*) as cnt FROM experience_sessions WHERE user_id = 1")
        assert rows[0]["cnt"] == 0

    def test_ats_message_missing_fields(self, client, auth_headers):
        resp = client.post(
            "/api/ats-improve/message",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_ats_resume_not_found(self, client, auth_headers):
        resp = client.get("/api/ats-improve/nonexistent/resume", headers=auth_headers)
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data
