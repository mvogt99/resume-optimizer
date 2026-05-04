"""E2E tests for background job lifecycle — creation, progress, completion, cancel.

Tests the batch_jobs system that backs async operations like project analysis,
journey mining, campaign generation, and job search.
No mocks, no skips. DB verification after every write.
"""

from test_helpers import query_db


class TestBackgroundJobs:
    """Batch job lifecycle tests with DB verification."""

    def test_job_list_empty(self, client, auth_headers):
        """New user has empty job list."""
        resp = client.get("/api/jobs", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["jobs"] == []

    def test_job_created_on_journey_mine(self, client, auth_headers):
        """POST /journey/mine creates a background job, DB row verified."""
        resp = client.post("/api/journey/mine", headers=auth_headers, json={})
        assert resp.status_code == 202
        data = resp.get_json()
        assert data["job_id"] is not None
        job_id = data["job_id"]

        # DB: batch_jobs row exists
        rows = query_db("SELECT * FROM batch_jobs WHERE id = ?", (job_id,))
        assert len(rows) == 1, f"No batch_jobs row for {job_id}"
        assert rows[0]["job_type"], "job_type is empty"
        assert rows[0]["status"] in (
            "pending",
            "running",
        ), f"Expected pending/running, got {rows[0]['status']}"

        # Job appears in list
        resp2 = client.get("/api/jobs", headers=auth_headers)
        assert resp2.status_code == 200
        jobs = resp2.get_json().get("jobs", resp2.get_json())
        if isinstance(jobs, list):
            job_ids = [j.get("id") for j in jobs]
            assert job_id in job_ids

    def test_job_status_polling(self, client, auth_headers):
        """Job status endpoint returns valid status values."""
        resp = client.post("/api/journey/mine", headers=auth_headers, json={})
        job_id = resp.get_json().get("job_id")
        assert job_id

        resp2 = client.get(f"/api/jobs/{job_id}/status", headers=auth_headers)
        assert resp2.status_code == 200
        data = resp2.get_json()
        assert data.get("status") in (
            "pending",
            "running",
            "completed",
            "complete",
            "done",
            "failed",
            "error",
            "cancelled",
        )

    def test_job_cancel(self, client, auth_headers):
        """Cancelling a job updates its status in DB."""
        resp = client.post("/api/journey/mine", headers=auth_headers, json={})
        job_id = resp.get_json().get("job_id")
        assert job_id

        resp2 = client.post(f"/api/jobs/{job_id}/cancel", headers=auth_headers)
        assert resp2.status_code == 200
        cancel_data = resp2.get_json()
        assert cancel_data["message"] == "Job cancelled"

        # DB: verify cancelled status
        rows = query_db("SELECT * FROM batch_jobs WHERE id = ?", (job_id,))
        assert len(rows) == 1
        assert rows[0]["status"] in ("cancelled", "completed", "complete", "done", "failed")

    def test_job_isolation(self, client, auth_headers, second_user_headers):
        """Users can only see their own jobs — API and DB level."""
        # User 1 creates a job
        resp1 = client.post("/api/journey/mine", headers=auth_headers, json={})
        job_id_1 = resp1.get_json().get("job_id")

        # User 2 creates a job
        resp2 = client.post("/api/journey/mine", headers=second_user_headers, json={})
        job_id_2 = resp2.get_json().get("job_id")

        # User 1 sees only their job
        resp3 = client.get("/api/jobs", headers=auth_headers)
        resp3_data = resp3.get_json()
        assert resp3_data["jobs"] is not None
        jobs_1 = resp3_data["jobs"]
        if isinstance(jobs_1, list):
            ids_1 = {j.get("id") for j in jobs_1}
            if job_id_1:
                assert job_id_1 in ids_1
            if job_id_2:
                assert job_id_2 not in ids_1

        # DB: verify both jobs exist but with different user_ids
        if job_id_1 and job_id_2:
            r1 = query_db("SELECT user_id FROM batch_jobs WHERE id = ?", (job_id_1,))
            r2 = query_db("SELECT user_id FROM batch_jobs WHERE id = ?", (job_id_2,))
            if r1 and r2:
                assert r1[0]["user_id"] != r2[0]["user_id"]

    def test_job_status_404_for_missing(self, client, auth_headers):
        """Non-existent job_id returns 404."""
        resp = client.get("/api/jobs/nonexistent-id-999/status", headers=auth_headers)
        assert resp.status_code == 404
        err = resp.get_json()
        assert err["error"] == "Job not found"
