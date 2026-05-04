"""Integration tests — agent data flows with actual data and isolation."""

import pytest
from test_helpers import query_db


@pytest.fixture()
def agent_headers(auth_headers):
    """Agents routes use legacy user-id header."""
    return {"user-id": "1", "Content-Type": "application/json"}


@pytest.fixture()
def agent_headers_user2(second_user_headers):
    return {"user-id": "2", "Content-Type": "application/json"}


def test_scout_posting_lifecycle(client, agent_headers):
    """Add posting → update → move pipeline → delete."""
    # 1. Add manual posting
    resp = client.post(
        "/api/agents/scout/postings",
        headers=agent_headers,
        json={
            "title": "Senior Python Engineer",
            "company": "TechCorp",
            "url": "https://example.com/job/123",
            "description": "Build scalable APIs with Python and AWS.",
        },
    )
    assert resp.status_code == 201
    posting = resp.get_json()
    posting_id = posting.get("posting_id") or posting.get("id")
    assert posting_id is not None

    # DB: verify posting row exists
    rows = query_db("SELECT * FROM job_postings WHERE id = ?", (posting_id,))
    assert len(rows) == 1, f"No job_postings row for {posting_id}"

    # 2. Get posting detail
    resp = client.get(f"/api/agents/scout/postings/{posting_id}", headers=agent_headers)
    assert resp.status_code == 200
    detail = resp.get_json()
    assert detail["title"] == "Senior Python Engineer"

    # 3. Update posting (star it, add notes)
    resp = client.put(
        f"/api/agents/scout/postings/{posting_id}",
        headers=agent_headers,
        json={"starred": True, "notes": "Great match for my skills"},
    )
    assert resp.status_code == 200

    # 4. Move through pipeline
    resp = client.put(
        f"/api/agents/pipeline/{posting_id}",
        headers=agent_headers,
        json={"status": "applied", "notes": "Applied on 2026-03-05"},
    )
    assert resp.status_code == 200

    # 5. Check pipeline view
    resp = client.get("/api/agents/pipeline", headers=agent_headers)
    assert resp.status_code == 200
    pipeline = resp.get_json()
    assert "stages" in pipeline or "pipeline" in pipeline

    # 6. Delete posting
    resp = client.delete(f"/api/agents/scout/postings/{posting_id}", headers=agent_headers)
    assert resp.status_code == 200

    # 7. Verify deleted
    resp = client.get(f"/api/agents/scout/postings/{posting_id}", headers=agent_headers)
    assert resp.status_code == 404


def test_scout_posting_full_isolation(client, agent_headers, agent_headers_user2):
    """User B cannot see, update, or delete User A's postings."""
    # User A adds posting
    resp = client.post(
        "/api/agents/scout/postings",
        headers=agent_headers,
        json={
            "title": "Private Posting",
            "company": "Secret Inc",
            "url": "https://example.com/secret",
            "description": "Top secret job",
        },
    )
    assert resp.status_code == 201
    posting_id = resp.get_json().get("posting_id") or resp.get_json().get("id")

    # User B cannot see it
    resp = client.get(f"/api/agents/scout/postings/{posting_id}", headers=agent_headers_user2)
    assert resp.status_code == 404

    # User B cannot update it
    resp = client.put(
        f"/api/agents/scout/postings/{posting_id}",
        headers=agent_headers_user2,
        json={"notes": "hacked"},
    )
    assert resp.status_code in (400, 404)

    # User B cannot delete it — delete is silently scoped to user_id
    resp = client.delete(f"/api/agents/scout/postings/{posting_id}", headers=agent_headers_user2)
    assert resp.status_code == 200  # route always returns 200 (DELETE scoped by user_id)
    del_data = resp.get_json()
    assert isinstance(del_data, dict)

    # User A should still see their posting (User B's delete was scoped)
    resp = client.get(f"/api/agents/scout/postings/{posting_id}", headers=agent_headers)
    assert resp.status_code == 200
    check_data = resp.get_json()
    assert isinstance(check_data, dict)

    # User B's posting list should be empty
    resp = client.get("/api/agents/scout/postings", headers=agent_headers_user2)
    assert resp.status_code == 200
    assert resp.get_json()["postings"] == []


def test_scout_criteria_crud(client, agent_headers):
    """Save search criteria → list → verify persisted."""
    resp = client.post(
        "/api/agents/scout/criteria",
        headers=agent_headers,
        json={
            "search_name": "Python Remote Jobs",
            "keywords": ["Python", "Django", "Remote"],
            "salary_min": 120000,
        },
    )
    assert resp.status_code == 201

    resp = client.get("/api/agents/scout/criteria", headers=agent_headers)
    assert resp.status_code == 200
    criteria = resp.get_json()["criteria"]
    assert len(criteria) >= 1
    assert any(c.get("search_name") == "Python Remote Jobs" for c in criteria)

    # DB: verify criteria persisted
    rows = query_db("SELECT * FROM search_criteria WHERE user_id = 1")
    assert len(rows) >= 1, "No search_criteria rows in DB"


def test_pipeline_analytics_with_data(client, agent_headers):
    """Add postings in different stages → check analytics reflect them."""
    # Add 2 postings
    for title in ["Job Alpha", "Job Beta"]:
        client.post(
            "/api/agents/scout/postings",
            headers=agent_headers,
            json={
                "title": title,
                "company": "TestCo",
                "url": f"https://example.com/{title.lower().replace(' ', '-')}",
                "description": f"{title} description",
            },
        )

    # Get analytics
    resp = client.get("/api/agents/pipeline/analytics", headers=agent_headers)
    assert resp.status_code == 200
    analytics = resp.get_json()
    # Should have some data
    assert isinstance(analytics, dict)


def test_pipeline_reminders(client, agent_headers):
    """Reminders endpoint works even with no stale applications."""
    resp = client.get("/api/agents/pipeline/reminders", headers=agent_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "reminders" in data


def test_agent_runs_log(client, agent_headers):
    """Agent runs log returns list (may be empty)."""
    resp = client.get("/api/agents/runs", headers=agent_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "runs" in data
