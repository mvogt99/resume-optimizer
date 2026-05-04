"""Tests for builder routes — sources, start, preview, compile.

Content validation + DB verification for all operations.
No mocks, no skips.
"""

from test_helpers import query_db


def test_builder_sources(client, auth_headers):
    """GET /api/builder/sources → data sources structure with section counts."""
    resp = client.get("/api/builder/sources", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, dict)
    # Builder sources returns sections: linkedin, projects, journey, experiences
    # Each section has 'available' (bool) and 'count' (int)
    for section in ("linkedin", "projects", "journey", "experiences"):
        if section in data:
            assert isinstance(data[section], dict)
            assert "available" in data[section]
            assert isinstance(data[section]["available"], bool)


def test_builder_start_no_job(client, auth_headers):
    """POST /api/builder/start with short job text → 400."""
    resp = client.post(
        "/api/builder/start",
        headers=auth_headers,
        json={"job_text": "short"},
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data
    assert isinstance(data["error"], str)


def test_builder_start_success(client, auth_headers):
    """POST /api/builder/start with valid job text → 201 with session_id, DB row created."""
    job_text = (
        "Senior Python Developer with 5+ years of experience in "
        "Django, REST APIs, AWS cloud, Docker and Kubernetes."
    )
    resp = client.post(
        "/api/builder/start",
        headers=auth_headers,
        json={"job_text": job_text},
    )
    assert resp.status_code == 201, f"Builder start failed: {resp.get_json()}"
    data = resp.get_json()
    assert "session_id" in data
    sid = data["session_id"]
    assert isinstance(sid, str)
    assert len(sid) > 0
    assert "status" in data
    assert data["status"] == "draft"

    # DB: verify builder_sessions row (resume_builder.py creates this table)
    rows = query_db("SELECT * FROM builder_sessions WHERE id = ?", (sid,))
    assert len(rows) == 1, f"No builder_sessions row for {sid}"
    assert rows[0]["user_id"] == 1
    assert len(rows[0]["job_text"]) >= 50
    assert rows[0]["status"] == "draft"


def test_builder_start_creates_unique_sessions(client, auth_headers):
    """Two POST /api/builder/start calls → two distinct sessions in DB."""
    job_text = (
        "Data Engineer with expertise in Apache Spark, Airflow, "
        "dbt, Snowflake, and Python data pipelines."
    )
    resp1 = client.post(
        "/api/builder/start",
        headers=auth_headers,
        json={"job_text": job_text},
    )
    assert resp1.status_code == 201
    sid1 = resp1.get_json()["session_id"]

    resp2 = client.post(
        "/api/builder/start",
        headers=auth_headers,
        json={"job_text": job_text},
    )
    assert resp2.status_code == 201
    sid2 = resp2.get_json()["session_id"]

    assert sid1 != sid2

    # DB: verify both sessions exist
    rows = query_db("SELECT * FROM builder_sessions WHERE user_id = ?", (1,))
    assert len(rows) >= 2
    ids = [r["id"] for r in rows]
    assert sid1 in ids
    assert sid2 in ids


def test_builder_preview_not_found(client, auth_headers):
    """GET /api/builder/preview/<nonexistent> → 404 with error."""
    resp = client.get("/api/builder/preview/nonexistent", headers=auth_headers)
    assert resp.status_code == 404
    data = resp.get_json()
    assert "error" in data
    assert isinstance(data["error"], str)
    assert len(data["error"]) > 0


def test_builder_requires_auth(client):
    """GET /api/builder/sources without auth → 401."""
    resp = client.get("/api/builder/sources")
    assert resp.status_code == 401
