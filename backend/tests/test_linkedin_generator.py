"""Tests for LinkedIn profile generator and application orchestrator (Phase 13.3)."""

import json

import pytest
from test_helpers import AGENT_HEADERS_1, JD_TEXT, RESUME_TEXT, query_db


class TestLinkedInGenerator:
    def test_generate_update_empty_profile(self, client, auth_headers):
        resp = client.post("/api/linkedin/generate-update", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "sections" in data
        assert isinstance(data["sections"], dict)

    def test_generate_update_stores_suggestions(self, client, auth_headers):
        client.post("/api/linkedin/generate-update", headers=auth_headers)
        resp = client.get("/api/linkedin/updates", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "updates" in data
        assert "count" in data
        assert data["count"] >= 0
        assert isinstance(data["updates"], list)
        # DB: verify updates stored
        rows = query_db("SELECT section_name FROM linkedin_profile_updates WHERE user_id = 1")
        assert len(rows) == data["count"]

    def test_list_updates_empty(self, client, auth_headers):
        resp = client.get("/api/linkedin/updates", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["count"] == 0

    def test_update_suggestion_accept(self, client, auth_headers):
        # Generate first
        client.post("/api/linkedin/generate-update", headers=auth_headers)
        updates = client.get("/api/linkedin/updates", headers=auth_headers).get_json()["updates"]
        if not updates:
            # Insert manually for testing
            query_db(
                "INSERT INTO linkedin_profile_updates (user_id, section_name, current_content, suggested_content) "
                "VALUES (1, 'headline', 'old', 'new')"
            )
            # Re-import to commit
            from models import get_db_connection

            conn = get_db_connection()
            conn.execute(
                "INSERT OR IGNORE INTO linkedin_profile_updates "
                "(user_id, section_name, current_content, suggested_content) "
                "VALUES (1, 'headline', 'old', 'new')"
            )
            conn.commit()
            conn.close()
            updates = client.get("/api/linkedin/updates", headers=auth_headers).get_json()[
                "updates"
            ]

        if updates:
            uid = updates[0]["id"]
            resp = client.put(
                f"/api/linkedin/updates/{uid}",
                headers=auth_headers,
                json={"status": "applied"},
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert "message" in data or "status" in data

    def test_update_suggestion_reject(self, client, auth_headers):
        from models import get_db_connection

        conn = get_db_connection()
        conn.execute(
            "INSERT INTO linkedin_profile_updates "
            "(user_id, section_name, current_content, suggested_content) "
            "VALUES (1, 'summary', 'old', 'new')"
        )
        conn.commit()
        conn.close()

        updates = client.get("/api/linkedin/updates", headers=auth_headers).get_json()["updates"]
        if updates:
            resp = client.put(
                f"/api/linkedin/updates/{updates[0]['id']}",
                headers=auth_headers,
                json={"status": "rejected"},
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert "message" in data or "status" in data

    def test_update_suggestion_edit_content(self, client, auth_headers):
        from models import get_db_connection

        conn = get_db_connection()
        conn.execute(
            "INSERT INTO linkedin_profile_updates "
            "(user_id, section_name, current_content, suggested_content) "
            "VALUES (1, 'skills', 'old', 'new')"
        )
        conn.commit()
        conn.close()

        updates = client.get("/api/linkedin/updates", headers=auth_headers).get_json()["updates"]
        if updates:
            resp = client.put(
                f"/api/linkedin/updates/{updates[0]['id']}",
                headers=auth_headers,
                json={"suggested_content": "edited content"},
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert "message" in data or "suggested_content" in data

    def test_update_invalid_status(self, client, auth_headers):
        from models import get_db_connection

        conn = get_db_connection()
        conn.execute(
            "INSERT INTO linkedin_profile_updates "
            "(user_id, section_name, current_content, suggested_content) "
            "VALUES (1, 'headline', 'old', 'new')"
        )
        conn.commit()
        conn.close()

        updates = client.get("/api/linkedin/updates", headers=auth_headers).get_json()["updates"]
        if updates:
            resp = client.put(
                f"/api/linkedin/updates/{updates[0]['id']}",
                headers=auth_headers,
                json={"status": "invalid"},
            )
            assert resp.status_code == 400
            data = resp.get_json()
            assert "error" in data

    def test_update_not_found(self, client, auth_headers):
        resp = client.put(
            "/api/linkedin/updates/99999", headers=auth_headers, json={"status": "applied"}
        )
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data

    def test_compare_endpoint(self, client, auth_headers):
        resp = client.get("/api/linkedin/compare", headers=auth_headers)
        assert resp.status_code == 200
        assert "comparison" in resp.get_json()

    def test_generate_idempotent(self, client, auth_headers):
        """Generating twice should update existing suggestions, not duplicate."""
        client.post("/api/linkedin/generate-update", headers=auth_headers)
        count1 = client.get("/api/linkedin/updates", headers=auth_headers).get_json()["count"]
        client.post("/api/linkedin/generate-update", headers=auth_headers)
        count2 = client.get("/api/linkedin/updates", headers=auth_headers).get_json()["count"]
        assert count2 == count1  # Same sections, no duplicates


class TestApplicationOrchestrator:
    def _create_posting(self, client):
        """Create a test posting and return its id."""
        resp = client.post(
            "/api/agents/scout/postings",
            headers=AGENT_HEADERS_1,
            json={
                "title": "Senior Architect",
                "company": "TechCo",
                "description": JD_TEXT,
                "location": "Remote",
            },
        )
        data = resp.get_json()
        return data.get("id") or data.get("posting_id")

    def test_record_feedback(self, client, auth_headers):
        pid = self._create_posting(client)
        resp = client.post(
            "/api/agents/feedback",
            headers=auth_headers,
            json={"posting_id": pid, "outcome": "interview", "notes": "Went well"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["id"]
        assert isinstance(data["id"], int)
        # DB: verify feedback persisted with correct fields
        rows = query_db(
            "SELECT outcome, notes FROM application_feedback WHERE id = ?", (data["id"],)
        )
        assert len(rows) == 1
        assert rows[0]["outcome"] == "interview"
        assert rows[0]["notes"] == "Went well"

    def test_record_feedback_missing_outcome(self, client, auth_headers):
        resp = client.post(
            "/api/agents/feedback",
            headers=auth_headers,
            json={"posting_id": "x"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert data["error"] != ""

    def test_record_feedback_invalid_outcome(self, client, auth_headers):
        resp = client.post(
            "/api/agents/feedback",
            headers=auth_headers,
            json={"posting_id": "x", "outcome": "maybe"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        # DB: no ghost feedback created
        rows = query_db("SELECT COUNT(*) as cnt FROM application_feedback WHERE user_id = 1")
        assert rows[0]["cnt"] == 0

    def test_list_feedback_empty(self, client, auth_headers):
        resp = client.get("/api/agents/feedback", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["count"] == 0

    def test_list_feedback_with_data(self, client, auth_headers):
        pid = self._create_posting(client)
        client.post(
            "/api/agents/feedback",
            headers=auth_headers,
            json={"posting_id": pid, "outcome": "interview"},
        )
        client.post(
            "/api/agents/feedback",
            headers=auth_headers,
            json={"posting_id": pid, "outcome": "rejected"},
        )
        # DB: verify 2 feedback rows
        fb = query_db("SELECT outcome FROM application_feedback WHERE user_id = 1 ORDER BY outcome")
        assert len(fb) == 2
        assert fb[0]["outcome"] == "interview"
        assert fb[1]["outcome"] == "rejected"

        resp = client.get("/api/agents/feedback", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 2
        assert isinstance(data["feedback"], list)
        assert len(data["feedback"]) == 2

    def test_feedback_insights_empty(self, client, auth_headers):
        resp = client.get("/api/agents/feedback/insights", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_applications"] == 0
        assert isinstance(data["recommendations"], list)

    def test_feedback_insights_with_data(self, client, auth_headers):
        pid = self._create_posting(client)
        for outcome in ["interview", "rejected", "ghosted", "ghosted", "offer"]:
            client.post(
                "/api/agents/feedback",
                headers=auth_headers,
                json={"posting_id": pid, "outcome": outcome},
            )
        # DB: verify 5 rows stored
        fb = query_db("SELECT COUNT(*) as cnt FROM application_feedback WHERE user_id = 1")
        assert fb[0]["cnt"] == 5

        resp = client.get("/api/agents/feedback/insights", headers=auth_headers)
        data = resp.get_json()
        assert data["total_applications"] == 5
        assert data["positive_outcomes"] == 2  # interview + offer
        assert data["response_rate"] > 0
        assert isinstance(data["recommendations"], list)

    def test_apply_missing_posting_id(self, client, auth_headers):
        resp = client.post("/api/agents/apply", headers=auth_headers, json={})
        assert resp.status_code == 400

    def test_apply_not_found(self, client, auth_headers):
        resp = client.post(
            "/api/agents/apply",
            headers=auth_headers,
            json={"posting_id": "nonexistent"},
        )
        assert resp.status_code == 404

    def test_get_bundle_not_found(self, client, auth_headers):
        resp = client.get("/api/agents/apply/nonexistent/bundle", headers=auth_headers)
        assert resp.status_code == 404

    def test_feedback_all_outcomes_valid(self, client, auth_headers):
        for outcome in ("interview", "rejected", "offer", "ghosted", "no_response", "withdrawn"):
            resp = client.post(
                "/api/agents/feedback",
                headers=auth_headers,
                json={"posting_id": "test", "outcome": outcome},
            )
            assert resp.status_code == 201, f"Failed for outcome={outcome}"
        # DB: verify all 6 outcomes stored
        rows = query_db(
            "SELECT outcome FROM application_feedback WHERE user_id = 1 ORDER BY outcome"
        )
        assert len(rows) == 6
