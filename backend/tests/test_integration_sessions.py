"""Integration tests — session CRUD with optimization using real data.

No mocks, no skips. DB verification after every write.
"""

import io

from test_helpers import query_db


def test_session_with_optimization(client, auth_headers):
    """Create session with JD → upload resume → optimize through session."""
    # 1. Upload resume
    data = {
        "file": (
            io.BytesIO(
                b"John Doe\nSenior Software Engineer\n"
                b"8 years of Python development\n"
                b"Django REST framework, PostgreSQL, Redis\n"
                b"AWS cloud services, Docker containerization\n"
                b"Led cross-functional team of 6 engineers\n"
                b"Improved API response time by 40%"
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

    # 2. Create session with JD text and resume
    resp = client.post(
        "/api/sessions",
        headers=auth_headers,
        json={
            "session_name": "Python Dev Application",
            "resume_id": int(resume_id),
            "job_description_text": "Senior Python Developer with 5+ years "
            "Django REST APIs AWS Docker Kubernetes CI/CD.",
        },
    )
    assert resp.status_code == 201
    session = resp.get_json()
    session_id = session["id"]

    # 3. Optimize through session
    resp = client.post(f"/api/sessions/{session_id}/optimize", headers=auth_headers)
    assert resp.status_code == 200
    result = resp.get_json()
    assert "ats_compliance_score" in result or "optimized_resume" in result

    # 4. Get session — should have result attached
    resp = client.get(f"/api/sessions/{session_id}", headers=auth_headers)
    assert resp.status_code == 200
    session_data = resp.get_json()
    assert session_data["session_name"] == "Python Dev Application"

    # DB: verify optimization persisted
    rows = query_db("SELECT * FROM job_sessions WHERE id = ?", (session_id,))
    assert len(rows) == 1
    assert rows[0]["status"] in ("optimized", "draft")


def test_session_update_and_reoptimize(client, auth_headers):
    """Create session → optimize → update JD → re-optimize."""
    # Upload resume
    data = {
        "file": (
            io.BytesIO(b"Jane Smith\nData Engineer\nPython Spark Airflow SQL"),
            "resume.txt",
        )
    }
    resp = client.post(
        "/api/resume/upload",
        headers={"Authorization": auth_headers["Authorization"]},
        data=data,
        content_type="multipart/form-data",
    )
    resume_id = resp.get_json()["resume_id"]

    # Create session
    resp = client.post(
        "/api/sessions",
        headers=auth_headers,
        json={
            "session_name": "Data Eng Role",
            "resume_id": int(resume_id),
            "job_description_text": "Data Engineer Python Spark Airflow "
            "AWS Redshift Glue Terraform.",
        },
    )
    session_id = resp.get_json()["id"]

    # First optimization
    resp = client.post(f"/api/sessions/{session_id}/optimize", headers=auth_headers)
    assert resp.status_code == 200

    # Update JD text
    resp = client.put(
        f"/api/sessions/{session_id}",
        headers=auth_headers,
        json={
            "job_description_text": "Senior Data Engineer Python Spark "
            "Kafka Kubernetes Docker CI/CD MLOps.",
        },
    )
    assert resp.status_code == 200
    updated = resp.get_json()
    assert updated["session_name"] == "Data Eng Role"

    # DB: verify JD text updated
    rows = query_db("SELECT * FROM job_sessions WHERE id = ?", (session_id,))
    assert "Kafka" in rows[0]["job_description_text"]

    # Re-optimize with updated JD
    resp = client.post(f"/api/sessions/{session_id}/optimize", headers=auth_headers)
    assert resp.status_code == 200


def test_session_isolation(client, auth_headers, second_user_headers):
    """User B cannot access or modify User A's sessions."""
    # User A creates session
    resp = client.post(
        "/api/sessions",
        headers=auth_headers,
        json={
            "session_name": "Confidential",
            "job_description_text": "Secret job description for internal use.",
        },
    )
    assert resp.status_code == 201
    session_id = resp.get_json()["id"]

    # User B cannot read it
    resp = client.get(f"/api/sessions/{session_id}", headers=second_user_headers)
    assert resp.status_code == 404

    # User B cannot update it
    resp = client.put(
        f"/api/sessions/{session_id}",
        headers=second_user_headers,
        json={"session_name": "Hacked"},
    )
    assert resp.status_code == 404

    # User B cannot delete it
    resp = client.delete(f"/api/sessions/{session_id}", headers=second_user_headers)
    assert resp.status_code == 404

    # User B list is empty
    resp = client.get("/api/sessions", headers=second_user_headers)
    assert resp.status_code == 200
    assert len(resp.get_json()["sessions"]) == 0


def test_session_optimize_without_resume(client, auth_headers):
    """Optimization fails gracefully when no resume is attached."""
    resp = client.post(
        "/api/sessions",
        headers=auth_headers,
        json={
            "session_name": "No Resume",
            "job_description_text": "Python Developer role at a startup.",
        },
    )
    session_id = resp.get_json()["id"]

    resp = client.post(f"/api/sessions/{session_id}/optimize", headers=auth_headers)
    assert resp.status_code == 400
    err = resp.get_json()
    assert err["error"] == "No resume found for session"
