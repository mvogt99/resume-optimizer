"""Route tests for builder_routes.py — sources, start, preview, compile, edit, save.

Pure API tests. Tests the resume builder workflow end-to-end.
"""

import io
import json

import pytest
from test_helpers import JD_TEXT, RESUME_TEXT, query_db

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def builder_session_id(client, auth_headers):
    """Create a builder session with base resume and return its ID."""
    import sqlite3

    import models

    # Create a base resume version so the builder has content to compile
    conn = models.get_db_connection()
    conn.execute(
        "INSERT INTO resume_versions (user_id, file_name, source, parsed_text) "
        "VALUES (?, ?, ?, ?)",
        (1, "base_resume.txt", "upload", RESUME_TEXT),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id FROM resume_versions WHERE user_id = 1 ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    base_version_id = row[0]

    resp = client.post(
        "/api/builder/start",
        headers=auth_headers,
        json={"job_text": JD_TEXT, "sources": ["linkedin"], "base_version_id": base_version_id},
    )
    assert resp.status_code == 201
    return resp.get_json()["session_id"]


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------


class TestBuilderSources:
    def test_get_sources(self, client, auth_headers):
        resp = client.get("/api/builder/sources", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict)
        # Should list available data sources
        assert "linkedin" in data or "projects" in data or "journey" in data
        # LinkedIn source should indicate availability
        if "linkedin" in data:
            assert "available" in data["linkedin"]

    def test_get_sources_auth_required(self, client):
        resp = client.get("/api/builder/sources")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------------


class TestBuilderStart:
    def test_start_session(self, client, auth_headers):
        resp = client.post(
            "/api/builder/start",
            headers=auth_headers,
            json={"job_text": JD_TEXT, "sources": ["linkedin", "projects"]},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert "session_id" in data
        assert isinstance(data["session_id"], str)
        assert data["status"] == "draft"
        assert "message" in data
        # DB: no resume versions yet (builder session is in-memory)
        rows = query_db("SELECT id FROM resume_versions WHERE user_id = 1 AND source = 'builder'")
        assert len(rows) == 0

    def test_start_session_short_jd(self, client, auth_headers):
        resp = client.post(
            "/api/builder/start",
            headers=auth_headers,
            json={"job_text": "too short", "sources": []},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert "50" in data["error"] or "character" in data["error"].lower()
        # DB: no ghost records created
        rows = query_db("SELECT id FROM resume_versions WHERE user_id = 1 AND source = 'builder'")
        assert len(rows) == 0

    def test_start_session_no_jd(self, client, auth_headers):
        resp = client.post(
            "/api/builder/start",
            headers=auth_headers,
            json={"sources": []},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------


class TestBuilderPreview:
    def test_preview_session(self, client, auth_headers, builder_session_id):
        resp = client.get(
            f"/api/builder/preview/{builder_session_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "text" in data
        assert isinstance(data["text"], str)
        assert "ats_score" in data
        assert isinstance(data["ats_score"], (int, float))
        assert "session_id" in data
        assert data["session_id"] == builder_session_id

    def test_preview_not_found(self, client, auth_headers):
        resp = client.get("/api/builder/preview/nonexistent", headers=auth_headers)
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data


# ---------------------------------------------------------------------------
# Compile
# ---------------------------------------------------------------------------


class TestBuilderCompile:
    def test_compile_session(self, client, auth_headers, builder_session_id):
        resp = client.post(
            f"/api/builder/compile/{builder_session_id}",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "compiled_text" in data
        assert isinstance(data["compiled_text"], str)
        assert len(data["compiled_text"]) > 0
        assert "status" in data
        assert data["status"] == "compiled"
        assert "compilation_method" in data
        assert data["session_id"] == builder_session_id
        # DB: compilation is in-memory — no resume versions yet
        rows = query_db("SELECT id FROM resume_versions WHERE user_id = 1 AND source = 'builder'")
        assert len(rows) == 0

    def test_compile_not_found(self, client, auth_headers):
        resp = client.post(
            "/api/builder/compile/nonexistent",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data


# ---------------------------------------------------------------------------
# Edit
# ---------------------------------------------------------------------------


class TestBuilderEdit:
    def test_edit_compiled_text(self, client, auth_headers, builder_session_id):
        # Compile first
        client.post(
            f"/api/builder/compile/{builder_session_id}",
            headers=auth_headers,
            json={},
        )
        # Edit
        resp = client.put(
            f"/api/builder/edit/{builder_session_id}",
            headers=auth_headers,
            json={"text": RESUME_TEXT + "\nAdditional experience in cloud architecture."},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "ats_score" in data
        assert isinstance(data["ats_score"], (int, float))
        assert data["session_id"] == builder_session_id
        # DB: edit is in-memory — no resume persisted yet
        rows = query_db("SELECT id FROM resume_versions WHERE user_id = 1 AND source = 'builder'")
        assert len(rows) == 0

    def test_edit_empty_text(self, client, auth_headers, builder_session_id):
        resp = client.put(
            f"/api/builder/edit/{builder_session_id}",
            headers=auth_headers,
            json={"text": ""},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_edit_not_found(self, client, auth_headers):
        resp = client.put(
            "/api/builder/edit/nonexistent",
            headers=auth_headers,
            json={"text": "some text"},
        )
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------


class TestBuilderSave:
    def test_save_compiled_resume(self, client, auth_headers, builder_session_id):
        # Compile first
        client.post(
            f"/api/builder/compile/{builder_session_id}",
            headers=auth_headers,
            json={},
        )
        # Save
        resp = client.post(
            f"/api/builder/save/{builder_session_id}",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert "version_id" in data
        assert "resume_id" in data
        assert data["status"] == "saved"
        # DB: verify resume version created
        rows = query_db("SELECT source FROM resume_versions WHERE id = ?", (data["version_id"],))
        assert len(rows) == 1
        assert rows[0]["source"] == "builder"
        # DB: verify resume created
        resume_rows = query_db("SELECT id FROM resumes WHERE id = ?", (data["resume_id"],))
        assert len(resume_rows) == 1

    def test_save_not_compiled(self, client, auth_headers, builder_session_id):
        """Save without compiling first — should fail."""
        resp = client.post(
            f"/api/builder/save/{builder_session_id}",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        # DB: no resume version created from failed save
        rows = query_db("SELECT id FROM resume_versions WHERE user_id = 1 AND source = 'builder'")
        assert len(rows) == 0

    def test_save_not_found(self, client, auth_headers):
        resp = client.post(
            "/api/builder/save/nonexistent",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data
        # DB: no ghost resume versions
        rows = query_db("SELECT id FROM resume_versions WHERE user_id = 1 AND source = 'builder'")
        assert len(rows) == 0


# ---------------------------------------------------------------------------
# Interview
# ---------------------------------------------------------------------------


class TestBuilderInterview:
    def test_interview_start_missing_session(self, client, auth_headers):
        resp = client.post(
            "/api/builder/interview/start",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_interview_start_invalid_session(self, client, auth_headers):
        resp = client.post(
            "/api/builder/interview/start",
            headers=auth_headers,
            json={"session_id": "nonexistent"},
        )
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data

    def test_interview_message_missing_fields(self, client, auth_headers):
        resp = client.post(
            "/api/builder/interview/message",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_interview_status_not_found(self, client, auth_headers):
        resp = client.get("/api/builder/interview/status/nonexistent", headers=auth_headers)
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data


# ---------------------------------------------------------------------------
# Import Experience to Builder (Phase 17.07)
# ---------------------------------------------------------------------------


class TestImportExperience:
    """Tests for POST /api/builder/import-experience/<experience_id>."""

    @pytest.fixture()
    def experience_id(self, client, auth_headers):
        """Create a finalized extracted_experiences row."""
        import sqlite3

        import models

        conn = models.get_db_connection()
        cursor = conn.execute(
            "INSERT INTO extracted_experiences "
            "(session_id, user_id, employer, client, title, responsibilities, "
            "technologies, accomplishments, challenges, bullet_points) "
            "VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "test-sess-001",
                "PwC",
                "OPI",
                "Technical Architect",
                json.dumps(["Led platform modernization"]),
                json.dumps(["Python", "Kafka", "Kubernetes"]),
                json.dumps(["Delivered 40% latency reduction"]),
                json.dumps(["Legacy migration complexity"]),
                json.dumps(
                    [
                        "Led enterprise platform modernization reducing latency by 40%",
                        "Architected event-driven microservices using Kafka and Kubernetes",
                    ]
                ),
            ),
        )
        conn.commit()
        eid = cursor.lastrowid
        conn.close()
        return eid

    def test_import_success(self, client, auth_headers, experience_id):
        resp = client.post(
            f"/api/builder/import-experience/{experience_id}",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["experience_id"] == experience_id
        assert data["employer"] == "PwC"
        assert data["title"] == "Technical Architect"
        assert data["bullet_count"] == 2
        assert data["status"] == "imported"
        assert data["session_id"]

    def test_import_creates_builder_session(self, client, auth_headers, experience_id):
        resp = client.post(
            f"/api/builder/import-experience/{experience_id}",
            headers=auth_headers,
            json={},
        )
        data = resp.get_json()

        # Verify session exists in DB
        sessions = query_db("SELECT * FROM builder_sessions WHERE id = ?", (data["session_id"],))
        assert len(sessions) == 1
        assert sessions[0]["status"] == "imported"
        assert "experiences" in sessions[0]["sources_json"]

    def test_import_compiled_text_has_content(self, client, auth_headers, experience_id):
        resp = client.post(
            f"/api/builder/import-experience/{experience_id}",
            headers=auth_headers,
            json={},
        )
        data = resp.get_json()

        sessions = query_db(
            "SELECT compiled_text FROM builder_sessions WHERE id = ?", (data["session_id"],)
        )
        text = sessions[0]["compiled_text"]
        assert "Technical Architect" in text
        assert "PwC" in text
        assert "Kafka" in text
        assert "latency" in text.lower()

    def test_import_not_found(self, client, auth_headers):
        resp = client.post(
            "/api/builder/import-experience/99999",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 404

    def test_import_with_job_text(self, client, auth_headers, experience_id):
        resp = client.post(
            f"/api/builder/import-experience/{experience_id}",
            headers=auth_headers,
            json={"job_text": "Senior Python developer with Kafka experience"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        sessions = query_db(
            "SELECT job_text FROM builder_sessions WHERE id = ?", (data["session_id"],)
        )
        assert "Kafka" in sessions[0]["job_text"]

    def test_import_requires_auth(self, client):
        resp = client.post("/api/builder/import-experience/1", json={})
        assert resp.status_code == 401
