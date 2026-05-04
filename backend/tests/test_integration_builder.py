"""Integration tests — builder flow with actual data."""

import io

from test_helpers import query_db


def _upload_resume_and_jd(client, auth_headers):
    """Helper: upload a resume and job description, return (resume_id, jd_id)."""
    data = {
        "file": (
            io.BytesIO(
                b"Mike Vogt\nEnterprise Architect\n"
                b"20 years experience in integration, SOA, API management\n"
                b"Python, Java, AWS, Docker, Kubernetes\n"
                b"Led teams of 10+ engineers"
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

    resp = client.post(
        "/api/job-description/upload",
        headers=auth_headers,
        json={
            "job_text": "Senior Solutions Architect with 10+ years experience in "
            "cloud architecture, microservices, API design, Python, "
            "Java, AWS, Kubernetes, and team leadership."
        },
    )
    assert resp.status_code == 201
    jd_id = resp.get_json()["job_id"]
    return resume_id, jd_id


def test_builder_full_flow(client, auth_headers):
    """Sources → start → compile → edit → save."""
    # 1. Check available sources
    resp = client.get("/api/builder/sources", headers=auth_headers)
    assert resp.status_code == 200
    sources = resp.get_json()
    assert "linkedin" in sources or "projects" in sources

    # 2. Start builder session with JD
    resp = client.post(
        "/api/builder/start",
        headers=auth_headers,
        json={
            "job_text": "Senior Python Developer with 5+ years experience in "
            "Django, REST APIs, AWS cloud infrastructure, Docker, "
            "and Kubernetes orchestration."
        },
    )
    assert resp.status_code == 201
    session = resp.get_json()
    session_id = session["session_id"]

    # 3. Compile (preview needs LinkedIn/sources which aren't available in test)
    resp = client.post(
        f"/api/builder/compile/{session_id}",
        headers=auth_headers,
        json={},
    )
    assert resp.status_code == 200  # compile with LLM mock should succeed
    compile_data = resp.get_json()
    assert isinstance(compile_data, dict)

    # 4. Edit — always works with valid text
    resp = client.put(
        f"/api/builder/edit/{session_id}",
        headers=auth_headers,
        json={"text": "Mike Vogt\nSenior Python Developer\nDjango, AWS, Docker"},
    )
    assert resp.status_code == 200
    assert "ats_score" in resp.get_json()

    # 5. Save as resume version
    resp = client.post(
        f"/api/builder/save/{session_id}",
        headers=auth_headers,
        json={},
    )
    assert resp.status_code == 201  # Edit step above populated compiled_text
    saved = resp.get_json()
    assert isinstance(saved, dict)
    assert "version_id" in saved
    assert "resume_id" in saved
    # DB: verify resume version row created
    rows = query_db("SELECT * FROM resume_versions WHERE id = ?", (saved["version_id"],))
    assert len(rows) == 1, f"No resume_versions row for {saved['version_id']}"


def test_builder_interview_flow(client, auth_headers):
    """Start builder → start interview → send messages → check status."""
    # Start builder session
    resp = client.post(
        "/api/builder/start",
        headers=auth_headers,
        json={
            "job_text": "Cloud Solutions Architect requiring AWS, Azure, "
            "Terraform, Kubernetes, and Python automation skills "
            "with 8+ years of enterprise experience."
        },
    )
    assert resp.status_code == 201
    builder_session_id = resp.get_json()["session_id"]

    # Start builder interview to fill gaps
    resp = client.post(
        "/api/builder/interview/start",
        headers=auth_headers,
        json={"session_id": builder_session_id},
    )
    assert resp.status_code == 201  # session exists from line above
    data = resp.get_json()
    assert isinstance(data, dict)

    interview_session_id = data.get("session_id")
    assert interview_session_id, "201 response must include session_id"

    # Send interview message
    resp = client.post(
        "/api/builder/interview/message",
        headers=auth_headers,
        json={
            "session_id": interview_session_id,
            "message": "I have extensive experience with AWS including "
            "EC2, Lambda, S3, and CloudFormation.",
        },
    )
    assert resp.status_code == 200

    # Check interview status
    resp = client.get(
        f"/api/builder/interview/status/{interview_session_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200


def test_builder_edit_validation(client, auth_headers):
    """Edit requires text field."""
    resp = client.post(
        "/api/builder/start",
        headers=auth_headers,
        json={
            "job_text": "Data Engineer with Python, Spark, Airflow, "
            "and cloud data warehousing experience required."
        },
    )
    session_id = resp.get_json()["session_id"]

    resp = client.put(
        f"/api/builder/edit/{session_id}",
        headers=auth_headers,
        json={},  # missing "text"
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data, "400 edit must include error message"


def test_builder_save_without_compile(client, auth_headers):
    """Save should fail if resume hasn't been compiled yet."""
    resp = client.post(
        "/api/builder/start",
        headers=auth_headers,
        json={
            "job_text": "DevOps Engineer with CI/CD, Docker, Kubernetes, "
            "and infrastructure automation experience."
        },
    )
    session_id = resp.get_json()["session_id"]

    resp = client.post(f"/api/builder/save/{session_id}", headers=auth_headers)
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data

    # DB: builder_sessions row should exist
    rows = query_db("SELECT * FROM builder_sessions WHERE id = ?", (session_id,))
    assert len(rows) == 1
