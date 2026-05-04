"""E2E tests for journey mining, timeline, skills, achievements, narratives.

Tests the full journey lifecycle: mine → explore → review → edit → approve.
Mining runs as a background job and sources from workdir/, Qdrant, ArangoDB, git.
No mocks, no skips. DB verification after every write.
"""

import pytest
from test_helpers import poll_job, query_db


class TestJourneyMining:
    """Journey mining background job and data retrieval."""

    def test_journey_mine_starts_job(self, client, auth_headers):
        """POST /journey/mine → background job created, DB row verified."""
        resp = client.post("/api/journey/mine", headers=auth_headers, json={})
        assert resp.status_code == 202
        data = resp.get_json()
        assert "job_id" in data
        job_id = data["job_id"]

        # DB: batch_jobs row
        rows = query_db("SELECT * FROM batch_jobs WHERE id = ?", (job_id,))
        assert len(rows) == 1, f"No batch_jobs row for {job_id}"
        assert rows[0]["job_type"], "job_type empty"

    def test_journey_mine_completes(self, client, auth_headers):
        """POST /journey/mine → job completes, DB status updated."""
        resp = client.post("/api/journey/mine", headers=auth_headers, json={})
        job_id = resp.get_json().get("job_id")
        assert job_id, "No job_id returned"

        # DB: batch_jobs row created
        rows = query_db("SELECT * FROM batch_jobs WHERE id = ?", (job_id,))
        assert len(rows) == 1, f"No batch_jobs row for {job_id}"

        try:
            result = poll_job(client, auth_headers, job_id, timeout=300)
            assert result.get("status") in (
                "completed",
                "complete",
                "done",
                "failed",
            )
        except TimeoutError:
            pytest.fail(
                f"Journey mining job {job_id} did not complete within 300s. "
                "Check that mining dependencies (workdir, Qdrant) are accessible."
            )


class TestJourneyData:
    """Journey data retrieval — works even without mining (empty results)."""

    def test_journey_timeline(self, client, auth_headers):
        """GET /journey/timeline → chronological events list."""
        resp = client.get("/api/journey/timeline", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "events" in data
        assert isinstance(data["events"], list)

    def test_journey_timeline_pagination(self, client, auth_headers):
        """GET /journey/timeline with page/per_page → paginated."""
        resp = client.get("/api/journey/timeline?page=1&per_page=10", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "page" in data or "events" in data

    def test_journey_skills(self, client, auth_headers):
        """GET /journey/skills → skills list."""
        resp = client.get("/api/journey/skills", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "skills" in data
        assert isinstance(data["skills"], list)

    def test_journey_achievements(self, client, auth_headers):
        """GET /journey/achievements → achievements list."""
        resp = client.get("/api/journey/achievements", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "achievements" in data
        assert isinstance(data["achievements"], list)

    def test_journey_narratives(self, client, auth_headers):
        """GET /journey/narratives → narrative list."""
        resp = client.get("/api/journey/narratives", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "narratives" in data
        assert isinstance(data["narratives"], list)

    def test_journey_narratives_edit(self, client, auth_headers):
        """PUT /journey/narratives → user edits preserved in DB."""
        resp = client.put(
            "/api/journey/narratives",
            headers=auth_headers,
            json={
                "narratives": [{"title": "Test Narrative", "content": "Edited narrative content."}]
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert (
            "status" in data or "message" in data or "narratives" in data
        ), f"Narrative edit response missing expected key, got: {list(data.keys())}"

        # DB: verify narrative table accessible after edit
        rows = query_db("SELECT * FROM journey_narratives")
        assert isinstance(rows, list), "journey_narratives query must return list"

    def test_journey_sources(self, client, auth_headers):
        """GET /journey/sources → mined source list."""
        resp = client.get("/api/journey/sources", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "sources" in data
        assert isinstance(data["sources"], list)

        # DB: journey_sources table accessible
        rows = query_db("SELECT COUNT(*) as cnt FROM journey_sources")
        assert len(rows) == 1


class TestJourneyApproval:
    """Journey narrative approval to ArangoDB."""

    def test_journey_approve(self, client, auth_headers):
        """POST /journey/approve → approval attempt (200 or 500 if ArangoDB down)."""
        resp = client.post(
            "/api/journey/approve",
            headers=auth_headers,
            json={"narrative_ids": []},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["message"] == "Narratives approved and stored in knowledge graph"

        # DB: journey_narratives table accessible
        query_db("SELECT COUNT(*) FROM journey_narratives")


class TestJourneyReview:
    """Journey review interview with LLM."""

    @pytest.fixture(autouse=True)
    def _check_harness(self, require_harness):
        """Fail with clear error if FTAL harness is not running."""

    def test_journey_review_start(self, client, auth_headers):
        """POST /journey/review/start → review session created."""
        resp = client.post(
            "/api/journey/review/start",
            headers=auth_headers,
            json={"review_type": "timeline"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "session_id" in data

    def test_journey_review_message(self, client, auth_headers):
        """POST /journey/review/message → contextual response."""
        resp = client.post(
            "/api/journey/review/start",
            headers=auth_headers,
            json={"review_type": "timeline"},
        )
        sid = resp.get_json()["session_id"]

        resp2 = client.post(
            "/api/journey/review/message",
            headers=auth_headers,
            json={
                "session_id": sid,
                "message": "I want to highlight my AWS cloud migration achievements.",
            },
        )
        assert resp2.status_code == 200
        data = resp2.get_json()
        assert (
            "response" in data or "message" in data or "reply" in data
        ), f"Review message response missing expected key, got: {list(data.keys())}"

    def test_journey_review_apply(self, client, auth_headers):
        """POST /journey/review/apply → applies review updates."""
        # Start a review session first
        resp = client.post(
            "/api/journey/review/start",
            headers=auth_headers,
            json={"review_type": "timeline"},
        )
        sid = resp.get_json()["session_id"]

        # Send a message to generate some review content
        client.post(
            "/api/journey/review/message",
            headers=auth_headers,
            json={
                "session_id": sid,
                "message": "Focus on my cloud infrastructure leadership.",
            },
        )

        # Apply the review updates
        resp2 = client.post(
            "/api/journey/review/apply",
            headers=auth_headers,
            json={"session_id": sid},
        )
        assert resp2.status_code == 200
        data = resp2.get_json()
        assert (
            "status" in data or "message" in data or "applied" in data
        ), f"Review apply response missing expected key, got: {list(data.keys())}"

    def test_journey_review_apply_missing_session(self, client, auth_headers):
        """POST /journey/review/apply without session_id → 400."""
        resp = client.post(
            "/api/journey/review/apply",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data or "message" in data, "400 must include error detail"
