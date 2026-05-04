"""Tests for background job routes — list, status, cancel.

Content validation + DB verification for all operations.
No mocks, no skips.
"""

from test_helpers import query_db


def test_list_jobs_empty(client, auth_headers):
    """GET /api/jobs with no jobs → empty list."""
    resp = client.get("/api/jobs", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "jobs" in data
    assert isinstance(data["jobs"], list)
    assert len(data["jobs"]) == 0


def test_list_jobs_with_data(client, auth_headers):
    """GET /api/jobs after creating a job → job visible in list."""
    import batch_jobs

    mgr = batch_jobs.get_batch_manager()
    job_id = mgr.create_job("test_type", user_id=1, params={"key": "value"})

    # DB: verify job row created
    rows = query_db("SELECT * FROM batch_jobs WHERE id = ?", (job_id,))
    assert len(rows) == 1, f"No batch_jobs row for {job_id}"
    assert rows[0]["job_type"] == "test_type"
    assert rows[0]["status"] == "pending"
    assert rows[0]["user_id"] == 1

    resp = client.get("/api/jobs", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "jobs" in data
    assert isinstance(data["jobs"], list)
    assert len(data["jobs"]) >= 1

    # Verify job structure
    job = next((j for j in data["jobs"] if j.get("id") == job_id), None)
    assert job is not None, f"Job {job_id} not in list"
    assert job["job_type"] == "test_type"
    assert job["status"] == "pending"


def test_job_status_found(client, auth_headers):
    """GET /api/jobs/<id>/status for existing job → returns job details."""
    import batch_jobs

    mgr = batch_jobs.get_batch_manager()
    job_id = mgr.create_job("status_check", user_id=1)

    resp = client.get(f"/api/jobs/{job_id}/status", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == job_id
    assert data["job_type"] == "status_check"
    assert data["status"] == "pending"


def test_job_status_not_found(client, auth_headers):
    """GET /api/jobs/<id>/status for nonexistent job → 404."""
    resp = client.get("/api/jobs/nonexistent/status", headers=auth_headers)
    assert resp.status_code == 404
    data = resp.get_json()
    assert "error" in data


def test_cancel_existing_job(client, auth_headers):
    """POST /api/jobs/<id>/cancel for existing job → cancelled."""
    import batch_jobs

    mgr = batch_jobs.get_batch_manager()
    job_id = mgr.create_job("cancel_test", user_id=1)

    resp = client.post(f"/api/jobs/{job_id}/cancel", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["message"] == "Job cancelled"

    # DB: verify status changed to cancelled
    rows = query_db("SELECT * FROM batch_jobs WHERE id = ?", (job_id,))
    assert len(rows) == 1
    assert rows[0]["status"] == "cancelled"


def test_cancel_nonexistent_job(client, auth_headers):
    """POST /api/jobs/<id>/cancel for nonexistent → 404."""
    resp = client.post("/api/jobs/nonexistent/cancel", headers=auth_headers)
    assert resp.status_code == 404
    data = resp.get_json()
    assert "error" in data
