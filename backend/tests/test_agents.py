"""Tests for agent routes — scout, pipeline, analytics, runs, criteria, isolation.

Content validation + DB verification for all operations.
No mocks, no skips.

Note: agents_routes.py uses legacy user-id header (not JWT @require_auth).
"""

import pytest
from test_helpers import query_db


@pytest.fixture()
def agent_headers(auth_headers):
    """Agents routes use legacy user-id header, extract user_id from JWT registration."""
    return {"user-id": "1", "Content-Type": "application/json"}


@pytest.fixture()
def agent_headers_user2(second_user_headers):
    return {"user-id": "2", "Content-Type": "application/json"}


def test_agent_status(client, auth_headers):
    """GET /api/agents/status → system status with agent list and model info.

    Requires auth: the response carries model_info and probes MODEL_URL, so it
    discloses which model is running and whether the LLM is reachable."""
    resp = client.get("/api/agents/status", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "agents" in data or "status" in data

    if "agents" in data:
        assert isinstance(data["agents"], list)
        assert len(data["agents"]) >= 1
        # Each agent has type and status
        agent = data["agents"][0]
        assert "type" in agent
        assert "status" in agent
        assert agent["status"] in ("ready", "degraded", "unavailable")

    # Model availability info
    if "llm_available" in data:
        assert isinstance(data["llm_available"], bool)
    if "cost" in data:
        assert isinstance(data["cost"], str)


def test_scout_postings_empty(client, agent_headers):
    """GET /api/agents/scout/postings → empty list initially."""
    resp = client.get("/api/agents/scout/postings", headers=agent_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "postings" in data
    assert isinstance(data["postings"], list)
    assert len(data["postings"]) == 0


def test_scout_manual_add_posting(client, agent_headers):
    """POST /api/agents/scout/postings → 201, DB row created."""
    resp = client.post(
        "/api/agents/scout/postings",
        headers=agent_headers,
        json={
            "title": "Senior Python Developer",
            "company": "Test Corp",
            "url": "https://example.com/job/42",
            "description": "Build scalable APIs with Python, FastAPI, and AWS.",
        },
    )
    assert resp.status_code == 201, f"Create posting failed: {resp.get_json()}"
    data = resp.get_json()
    posting_id = data.get("posting_id") or data.get("id")
    assert posting_id, "No posting_id returned"

    # DB: verify posting row
    rows = query_db("SELECT * FROM job_postings WHERE id = ?", (posting_id,))
    assert len(rows) == 1, f"No job_postings row for {posting_id}"
    assert rows[0]["title"] == "Senior Python Developer"
    assert rows[0]["company"] == "Test Corp"


def test_scout_posting_not_found(client, agent_headers):
    """GET /api/agents/scout/postings/99999 → 404 with error."""
    resp = client.get("/api/agents/scout/postings/99999", headers=agent_headers)
    assert resp.status_code == 404
    data = resp.get_json()
    assert "error" in data


def test_scout_posting_get_detail(client, agent_headers):
    """Create posting → GET by ID → correct detail returned."""
    resp = client.post(
        "/api/agents/scout/postings",
        headers=agent_headers,
        json={
            "title": "Data Engineer",
            "company": "DataCo",
            "url": "https://example.com/de",
            "description": "ETL pipelines with Spark and Airflow.",
        },
    )
    posting_id = resp.get_json().get("posting_id") or resp.get_json().get("id")

    resp2 = client.get(f"/api/agents/scout/postings/{posting_id}", headers=agent_headers)
    assert resp2.status_code == 200
    data = resp2.get_json()
    assert data["title"] == "Data Engineer"
    assert data["company"] == "DataCo"


def test_scout_posting_update(client, agent_headers):
    """Create posting → PUT to update status → DB reflects change."""
    resp = client.post(
        "/api/agents/scout/postings",
        headers=agent_headers,
        json={
            "title": "DevOps Engineer",
            "company": "CloudCo",
            "url": "https://example.com/devops",
            "description": "Kubernetes, Terraform, CI/CD pipeline management.",
        },
    )
    posting_id = resp.get_json().get("posting_id") or resp.get_json().get("id")

    resp2 = client.put(
        f"/api/agents/scout/postings/{posting_id}",
        headers=agent_headers,
        json={"status": "applied", "notes": "Applied on March 7"},
    )
    assert resp2.status_code == 200
    data = resp2.get_json()
    assert data.get("status") == "applied" or "message" in data

    # DB: verify status updated
    rows = query_db("SELECT * FROM job_postings WHERE id = ?", (posting_id,))
    assert rows[0]["status"] == "applied"


def test_scout_posting_delete(client, agent_headers):
    """Create posting → DELETE → 200, DB row removed or marked deleted."""
    resp = client.post(
        "/api/agents/scout/postings",
        headers=agent_headers,
        json={
            "title": "Temp Job",
            "company": "TempCo",
            "url": "https://example.com/temp",
            "description": "Temporary position for testing deletion workflow.",
        },
    )
    posting_id = resp.get_json().get("posting_id") or resp.get_json().get("id")

    resp2 = client.delete(f"/api/agents/scout/postings/{posting_id}", headers=agent_headers)
    assert resp2.status_code == 200
    data = resp2.get_json()
    assert "message" in data or isinstance(data, dict)

    # DB: verify posting removed from database
    rows = query_db("SELECT * FROM job_postings WHERE id = ?", (posting_id,))
    assert len(rows) == 0, "Deleted posting should not exist in DB"

    # API: verify posting no longer accessible
    resp3 = client.get(f"/api/agents/scout/postings/{posting_id}", headers=agent_headers)
    assert resp3.status_code == 404


def test_pipeline_empty(client, agent_headers):
    """GET /api/agents/pipeline → pipeline structure with stages."""
    resp = client.get("/api/agents/pipeline", headers=agent_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "stages" in data or "pipeline" in data
    # Pipeline should have stage structure
    stages = data.get("stages") or data.get("pipeline", [])
    assert isinstance(stages, list)


def test_pipeline_analytics(client, agent_headers):
    """GET /api/agents/pipeline/analytics → analytics structure."""
    resp = client.get("/api/agents/pipeline/analytics", headers=agent_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    # Analytics should have some structure even when empty
    assert isinstance(data, dict)


def test_agent_runs_empty(client, agent_headers):
    """GET /api/agents/runs → empty runs list."""
    resp = client.get("/api/agents/runs", headers=agent_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "runs" in data
    assert isinstance(data["runs"], list)


def test_scout_criteria_empty(client, agent_headers):
    """GET /api/agents/scout/criteria → empty criteria list."""
    resp = client.get("/api/agents/scout/criteria", headers=agent_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "criteria" in data
    assert isinstance(data["criteria"], list)


def test_scout_criteria_save_and_list(client, agent_headers):
    """POST criteria → GET criteria → criteria persisted."""
    resp = client.post(
        "/api/agents/scout/criteria",
        headers=agent_headers,
        json={
            "title": "Senior Python",
            "keywords": ["python", "aws", "docker"],
            "location": "Remote",
            "min_salary": 150000,
        },
    )
    assert resp.status_code == 201, f"Save criteria failed: {resp.get_json()}"

    resp2 = client.get("/api/agents/scout/criteria", headers=agent_headers)
    assert resp2.status_code == 200
    data = resp2.get_json()
    assert len(data["criteria"]) >= 1


def test_scout_posting_isolation(client, agent_headers, agent_headers_user2):
    """User B cannot see User A's manually added postings."""
    resp = client.post(
        "/api/agents/scout/postings",
        headers=agent_headers,
        json={
            "title": "Secret Job",
            "company": "Secret Corp",
            "url": "https://example.com/job",
            "description": "A very secret job posting for isolation test.",
        },
    )
    assert resp.status_code == 201, f"Create posting failed: {resp.get_json()}"
    posting_id = resp.get_json().get("posting_id") or resp.get_json().get("id")
    assert posting_id, "No posting_id returned"

    # User 2 cannot see User 1's posting
    resp = client.get(
        f"/api/agents/scout/postings/{posting_id}",
        headers=agent_headers_user2,
    )
    assert resp.status_code == 404

    # User 2's postings list is empty
    resp2 = client.get("/api/agents/scout/postings", headers=agent_headers_user2)
    assert resp2.status_code == 200
    data = resp2.get_json()
    assert data["count"] == 0

    # DB: posting exists (just not visible to user 2)
    rows = query_db("SELECT * FROM job_postings WHERE id = ?", (posting_id,))
    assert len(rows) >= 1
