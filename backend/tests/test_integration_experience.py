"""Integration tests — experience chat full lifecycle with actual data."""

import io

from test_helpers import query_db


def test_experience_full_flow(client, auth_headers):
    """Start session → send messages → get summary → finalize → apply to resume."""
    # 1. Start session
    resp = client.post(
        "/api/experience/start",
        headers=auth_headers,
        json={"employer": "Acme Corp", "client": "BigBank"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert "session_id" in data
    session_id = data["session_id"]

    # DB: verify session row created
    rows = query_db("SELECT * FROM experience_sessions WHERE id = ?", (session_id,))
    assert len(rows) == 1, f"No experience_sessions row for {session_id}"

    # 2. Send first message (describe role)
    resp = client.post(
        "/api/experience/message",
        headers=auth_headers,
        json={
            "session_id": session_id,
            "message": "I was a Senior Python Developer leading a team of 5. "
            "We built REST APIs with Django and deployed to AWS ECS.",
        },
    )
    assert resp.status_code == 200

    # 3. Send second message (technologies)
    resp = client.post(
        "/api/experience/message",
        headers=auth_headers,
        json={
            "session_id": session_id,
            "message": "We used Python 3.11, Django 4.2, PostgreSQL, Redis, "
            "Docker, Kubernetes, and Terraform for IaC.",
        },
    )
    assert resp.status_code == 200

    # 4. Get summary
    resp = client.get(f"/api/experience/summary/{session_id}", headers=auth_headers)
    assert resp.status_code == 200
    summary = resp.get_json()
    assert "employer" in summary or "session_id" in summary

    # 5. Finalize (send empty JSON body to avoid 400 from get_json())
    resp = client.post(
        f"/api/experience/finalize/{session_id}",
        headers=auth_headers,
        json={},
    )
    assert resp.status_code == 200

    # 6. List should now contain our session
    resp = client.get("/api/experience/list", headers=auth_headers)
    assert resp.status_code == 200

    # 7. Apply to resume — should create a resume version
    resp = client.post(
        f"/api/experience/apply/{session_id}",
        headers=auth_headers,
        json={},
    )
    assert resp.status_code == 201  # session finalized above; apply creates version
    data = resp.get_json()
    assert isinstance(data, dict)
    assert "resume_id" in data or "version_id" in data


def test_experience_message_validation(client, auth_headers):
    """Message endpoint requires session_id and message."""
    resp = client.post(
        "/api/experience/message",
        headers=auth_headers,
        json={"message": "hello"},
    )
    assert resp.status_code == 400
    err = resp.get_json()
    assert err["error"] == "session_id and message are required"

    resp = client.post(
        "/api/experience/message",
        headers=auth_headers,
        json={"session_id": "fake-id"},
    )
    assert resp.status_code == 400


def test_experience_isolation(client, auth_headers, second_user_headers):
    """User B cannot see User A's experience sessions."""
    # User A creates session
    resp = client.post(
        "/api/experience/start",
        headers=auth_headers,
        json={"employer": "Secret Corp"},
    )
    assert resp.status_code == 201
    session_id = resp.get_json()["session_id"]

    # DB: verify session belongs to user 1
    rows = query_db("SELECT * FROM experience_sessions WHERE id = ?", (session_id,))
    assert len(rows) == 1
    assert rows[0]["user_id"] == 1, "Session must belong to user 1"

    # User B cannot see it
    resp = client.get(f"/api/experience/summary/{session_id}", headers=second_user_headers)
    assert resp.status_code == 404, f"Isolation breach: expected 404, got {resp.status_code}"
    err_data = resp.get_json()
    assert err_data["error"] == "Session not found"


def test_skills_interview_flow(client, auth_headers):
    """Start skills interview → send messages → finalize → get summary."""
    # Start with skills list
    resp = client.post(
        "/api/skills-interview/start",
        headers=auth_headers,
        json={"skills": ["Python", "AWS", "Docker"], "resume_id": ""},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "session_id" in data
    session_id = data["session_id"]

    # Send a message
    resp = client.post(
        "/api/skills-interview/message",
        headers=auth_headers,
        json={
            "session_id": session_id,
            "message": "I have 8 years of Python including Django and FastAPI.",
        },
    )
    assert resp.status_code == 200

    # Finalize first (summary requires finalized session)
    resp = client.post(
        f"/api/skills-interview/{session_id}/finalize",
        headers=auth_headers,
        json={},
    )
    assert resp.status_code == 200

    # Get summary (now that session is finalized)
    resp = client.get(f"/api/skills-interview/{session_id}/summary", headers=auth_headers)
    assert resp.status_code == 200


def test_ats_improvement_flow(client, auth_headers):
    """Start ATS improvement chat → send message → get improved resume."""
    # First upload a resume
    data = {
        "file": (
            io.BytesIO(
                b"Jane Smith\nSoftware Engineer\n"
                b"Python, Django, REST APIs, AWS, Docker\n"
                b"5 years enterprise development"
            ),
            "resume.txt",
        )
    }
    resp = client.post(
        "/api/resume/upload",
        headers={"Authorization": auth_headers["Authorization"]},
        data=data,
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201
    resume_id = resp.get_json()["resume_id"]

    # Start ATS improvement with score data
    resp = client.post(
        "/api/ats-improve/start",
        headers=auth_headers,
        json={
            "resume_id": resume_id,
            "score_data": {
                "score": 65.0,
                "score_breakdown": {
                    "keywords": 50,
                    "format": 80,
                },
                "keywords_matched": ["Python", "Django"],
                "keywords_missing": ["Kubernetes", "CI/CD"],
            },
        },
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "session_id" in data
    session_id = data["session_id"]

    # Send improvement message
    resp = client.post(
        "/api/ats-improve/message",
        headers=auth_headers,
        json={
            "session_id": session_id,
            "message": "Focus on adding Kubernetes experience.",
        },
    )
    assert resp.status_code == 200

    # Get improved resume text
    resp = client.get(f"/api/ats-improve/{session_id}/resume", headers=auth_headers)
    assert resp.status_code == 200
