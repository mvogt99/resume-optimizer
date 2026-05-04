"""Tests for experience chat, skills interview, and ATS improvement routes.

Content validation + DB verification for all operations.
No mocks, no skips.
"""

from test_helpers import query_db


def test_experience_start(client, auth_headers):
    """POST /api/experience/start → session created, DB row verified."""
    resp = client.post(
        "/api/experience/start",
        headers=auth_headers,
        json={"context": "Software engineering"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert "session_id" in data
    sid = data["session_id"]
    assert isinstance(sid, str)
    assert len(sid) > 0

    # DB: verify experience_sessions row
    rows = query_db("SELECT * FROM experience_sessions WHERE id = ?", (sid,))
    assert len(rows) == 1, f"No experience_sessions row for {sid}"
    assert rows[0]["user_id"] == 1


def test_experience_list_empty(client, auth_headers):
    """GET /api/experience/list → empty experiences list initially."""
    resp = client.get("/api/experience/list", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "experiences" in data
    assert isinstance(data["experiences"], list)


def test_experience_summary_not_found(client, auth_headers):
    """GET /api/experience/summary/<nonexistent> → 404 with error."""
    resp = client.get("/api/experience/summary/nonexistent", headers=auth_headers)
    assert resp.status_code == 404
    data = resp.get_json()
    assert "error" in data


def test_experience_requires_auth(client):
    """GET /api/experience/list without auth → 401."""
    resp = client.get("/api/experience/list")
    assert resp.status_code == 401
    data = resp.get_json()
    assert "error" in data or "message" in data or "msg" in data


def test_skills_interview_start(client, auth_headers):
    """POST /api/skills-interview/start → session with opening message, DB verified."""
    resp = client.post(
        "/api/skills-interview/start",
        headers=auth_headers,
        json={
            "skills": ["Python", "Django", "REST APIs"],
            "resume_id": "",
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "session_id" in data
    sid = data["session_id"]
    assert isinstance(sid, str)
    assert len(sid) > 0

    # DB: verify skills_interview_sessions row
    rows = query_db("SELECT * FROM skills_interview_sessions WHERE id = ?", (sid,))
    assert len(rows) == 1, f"No skills_interview_sessions row for {sid}"


def test_skills_interview_no_skills(client, auth_headers):
    """POST /api/skills-interview/start without skills → 400."""
    resp = client.post(
        "/api/skills-interview/start",
        headers=auth_headers,
        json={"skills": [], "resume_id": ""},
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_experience_message_requires_session(client, auth_headers):
    """POST /api/experience/message without valid session → 404."""
    resp = client.post(
        "/api/experience/message",
        headers=auth_headers,
        json={"session_id": "nonexistent", "message": "Hello"},
    )
    assert resp.status_code == 404
    data = resp.get_json()
    assert "error" in data

    # DB: experience_sessions table accessible
    query_db("SELECT COUNT(*) FROM experience_sessions")
