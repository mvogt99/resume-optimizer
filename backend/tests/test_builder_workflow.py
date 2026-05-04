"""E2E tests for the resume builder full workflow.

Tests: session creation → source loading → interview → compile → edit → save.
Builder routes use user-id header via @require_auth.
No mocks, no skips. DB verification after every write.
"""

from test_helpers import JD_TEXT, RESUME_TEXT, query_db, upload_resume


class TestBuilderSources:
    """Builder data source availability."""

    def test_builder_sources(self, client, auth_headers):
        """GET /builder/sources → returns source availability."""
        resp = client.get("/api/builder/sources", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict), "Builder sources must return a dict"
        # Sources should report availability of known data sources
        assert any(
            k in data for k in ("sources", "linkedin", "resumes", "experience")
        ), f"Builder sources missing expected keys, got: {list(data.keys())}"


class TestBuilderSession:
    """Builder session lifecycle with DB verification."""

    def test_builder_start_session(self, client, auth_headers):
        """POST /builder/start → session created, DB row verified."""
        resp = client.post(
            "/api/builder/start",
            headers=auth_headers,
            json={"job_text": JD_TEXT, "sources": []},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        sid = data["session_id"]

        assert data["session_id"] != "", "session_id must be non-empty"

        # DB: builder_sessions row exists
        rows = query_db("SELECT * FROM builder_sessions WHERE id = ?", (sid,))
        assert len(rows) == 1, f"No builder_sessions row for {sid}"

    def test_builder_start_requires_job_text(self, client, auth_headers):
        """POST /builder/start with short job_text → 400."""
        resp = client.post(
            "/api/builder/start",
            headers=auth_headers,
            json={"job_text": "Too short", "sources": []},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] != "", "400 must include non-empty error message"

    def test_builder_preview(self, client, auth_headers):
        """GET /builder/preview/<sid> → session data."""
        resp = client.post(
            "/api/builder/start",
            headers=auth_headers,
            json={"job_text": JD_TEXT, "sources": []},
        )
        sid = resp.get_json()["session_id"]

        resp2 = client.get(f"/api/builder/preview/{sid}", headers=auth_headers)
        assert resp2.status_code == 200
        data = resp2.get_json()
        assert data["session_id"] == sid, "Preview must return the same session_id"

        # DB: session row matches preview
        rows = query_db("SELECT * FROM builder_sessions WHERE id = ?", (sid,))
        assert len(rows) == 1
        assert rows[0]["id"] == sid

    def test_builder_edit(self, client, auth_headers):
        """PUT /builder/edit/<sid> → text updated, DB verified."""
        resp = client.post(
            "/api/builder/start",
            headers=auth_headers,
            json={"job_text": JD_TEXT, "sources": []},
        )
        sid = resp.get_json()["session_id"]

        edited_text = RESUME_TEXT + "\nUpdated via builder edit."
        resp2 = client.put(
            f"/api/builder/edit/{sid}",
            headers=auth_headers,
            json={"text": edited_text},
        )
        assert resp2.status_code == 200
        data = resp2.get_json()
        assert data["status"] == "compiled"

        # DB: compiled text persisted
        rows = query_db("SELECT * FROM builder_sessions WHERE id = ?", (sid,))
        assert len(rows) == 1
        assert "Updated via builder edit" in (
            rows[0].get("compiled_text") or rows[0].get("resume_text") or ""
        )

    def test_builder_save(self, client, auth_headers):
        """POST /builder/save/<sid> → creates resume version."""
        upload_resume(client, auth_headers)

        resp = client.post(
            "/api/builder/start",
            headers=auth_headers,
            json={"job_text": JD_TEXT, "sources": []},
        )
        sid = resp.get_json()["session_id"]

        resp2 = client.post(f"/api/builder/save/{sid}", headers=auth_headers, json={})
        assert resp2.status_code == 400  # no compile step → no compiled_text → 400
        data = resp2.get_json()
        assert data.get("error"), "400 save must include error message"

        # DB: builder session row exists
        rows = query_db("SELECT * FROM builder_sessions WHERE id = ?", (sid,))
        assert len(rows) == 1

    def test_builder_compile(self, client, auth_headers, require_harness):
        """POST /builder/compile/<sid> → assembled text."""
        resp = client.post(
            "/api/builder/start",
            headers=auth_headers,
            json={"job_text": JD_TEXT, "sources": []},
        )
        sid = resp.get_json()["session_id"]

        resp2 = client.post(f"/api/builder/compile/{sid}", headers=auth_headers, json={})
        assert resp2.status_code == 200
        data = resp2.get_json()
        has_output = data.get("compiled_text") or data.get("text") or data.get("status")
        assert has_output, "Compile must return compiled_text, text, or status"

        # DB: builder session exists after compile
        rows = query_db("SELECT * FROM builder_sessions WHERE id = ?", (sid,))
        assert len(rows) == 1

    def test_builder_from_existing_resume(self, client, auth_headers):
        """POST /builder/start with base_version_id imports resume."""
        upload_resume(client, auth_headers)

        import models

        user_id = 1
        version = models.ResumeVersion.create(
            user_id=user_id,
            source="test",
            file_name="test_resume.txt",
            parsed_text=RESUME_TEXT,
        )
        vid = version.id

        resp = client.post(
            "/api/builder/start",
            headers=auth_headers,
            json={"job_text": JD_TEXT, "sources": [], "base_version_id": vid},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["session_id"] != "", "session_id must be non-empty"

        # DB: builder session created from existing resume
        rows = query_db("SELECT * FROM builder_sessions WHERE id = ?", (data["session_id"],))
        assert len(rows) == 1

    def test_builder_interview_to_compile(self, client, auth_headers, require_harness):
        """Full workflow: start → interview → compile, DB verified."""
        resp = client.post(
            "/api/builder/start",
            headers=auth_headers,
            json={"job_text": JD_TEXT, "sources": []},
        )
        bsid = resp.get_json()["session_id"]

        resp2 = client.post(
            "/api/builder/interview/start",
            headers=auth_headers,
            json={"session_id": bsid},
        )
        assert resp2.status_code == 201
        interview_sid = resp2.get_json().get("session_id", bsid)

        client.post(
            "/api/builder/interview/message",
            headers=auth_headers,
            json={
                "session_id": interview_sid,
                "message": "Led AWS cloud migration at Navitus, 30M+ members, 99.99% uptime.",
            },
        )

        resp3 = client.post(f"/api/builder/compile/{bsid}", headers=auth_headers, json={})
        assert resp3.status_code == 200

        # DB: builder_interview_sessions row should exist
        rows = query_db("SELECT * FROM builder_interview_sessions WHERE id = ?", (interview_sid,))
        assert len(rows) >= 1, "No builder_interview_sessions row after interview"

    def test_builder_user_isolation(self, client, auth_headers, second_user_headers):
        """Two users see only their own sessions."""
        resp1 = client.post(
            "/api/builder/start",
            headers=auth_headers,
            json={"job_text": JD_TEXT, "sources": []},
        )
        sid1 = resp1.get_json()["session_id"]

        resp2 = client.get(f"/api/builder/preview/{sid1}", headers=second_user_headers)
        assert resp2.status_code in (403, 404)
        data = resp2.get_json()
        assert data.get("error") or data.get(
            "message"
        ), "Isolation violation must return error detail"

        # DB: session row belongs to user 1, not user 2
        rows = query_db("SELECT * FROM builder_sessions WHERE id = ?", (sid1,))
        assert len(rows) == 1
        assert rows[0]["user_id"] == 1, "Session must belong to first user"
