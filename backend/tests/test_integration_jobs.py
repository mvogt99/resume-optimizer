"""Integration tests — batch job lifecycle."""

import sqlite3

from test_helpers import query_db


def test_batch_job_lifecycle(client, auth_headers, app):
    """Create job in DB → check status → cancel → verify cancelled."""
    # We can't easily trigger a real background job via API without
    # a running worker, so we'll create a job directly in the DB
    # and test the status/cancel endpoints.
    import models

    conn = sqlite3.connect(models.DB_PATH)
    conn.execute(
        "INSERT INTO batch_jobs (id, job_type, user_id, status) " "VALUES (?, ?, ?, ?)",
        ("test-job-001", "project_analysis", 1, "running"),
    )
    conn.commit()
    conn.close()

    # Check status
    resp = client.get("/api/jobs/test-job-001/status", headers=auth_headers)
    assert resp.status_code == 200
    job = resp.get_json()
    assert job["status"] == "running"
    assert job["job_type"] == "project_analysis"

    # Cancel
    resp = client.post("/api/jobs/test-job-001/cancel", headers=auth_headers)
    assert resp.status_code == 200

    # Verify cancelled
    resp = client.get("/api/jobs/test-job-001/status", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "cancelled"

    # DB: verify status in database
    rows = query_db("SELECT status FROM batch_jobs WHERE id = ?", ("test-job-001",))
    assert rows[0]["status"] == "cancelled"


def test_batch_job_list_filtered(client, auth_headers, app):
    """List jobs filtered by type."""
    import models

    conn = sqlite3.connect(models.DB_PATH)
    conn.execute(
        "INSERT INTO batch_jobs (id, job_type, user_id, status) VALUES (?, ?, ?, ?)",
        ("job-a", "campaign_posts", 1, "completed"),
    )
    conn.execute(
        "INSERT INTO batch_jobs (id, job_type, user_id, status) VALUES (?, ?, ?, ?)",
        ("job-b", "project_analysis", 1, "completed"),
    )
    conn.execute(
        "INSERT INTO batch_jobs (id, job_type, user_id, status) VALUES (?, ?, ?, ?)",
        ("job-c", "campaign_posts", 1, "pending"),
    )
    conn.commit()
    conn.close()

    # List all
    resp = client.get("/api/jobs", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.get_json()["jobs"]) >= 3

    # Filter by type
    resp = client.get("/api/jobs?type=campaign_posts", headers=auth_headers)
    assert resp.status_code == 200
    jobs = resp.get_json()["jobs"]
    assert all(j["job_type"] == "campaign_posts" for j in jobs)
    assert len(jobs) >= 2


def test_batch_job_isolation(client, auth_headers, second_user_headers, app):
    """User B cannot cancel User A's jobs."""
    import models

    conn = sqlite3.connect(models.DB_PATH)
    conn.execute(
        "INSERT INTO batch_jobs (id, job_type, user_id, status) VALUES (?, ?, ?, ?)",
        ("user1-job", "campaign_posts", 1, "running"),
    )
    conn.commit()
    conn.close()

    # User B tries to cancel User A's job
    resp = client.post("/api/jobs/user1-job/cancel", headers=second_user_headers)
    assert resp.status_code == 404

    # Job should still be running
    resp = client.get("/api/jobs/user1-job/status", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "running"
