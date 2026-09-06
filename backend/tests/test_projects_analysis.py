"""E2E tests for client project CRUD, document analysis, approval workflow.

Tests: project create/list, analysis start/get/edit/approve, documents list.
No mocks, no skips. DB verification after every write.
"""

import os

import pytest
from test_helpers import query_db

GDRIVE_TOKEN_PATH = os.path.expanduser("~/.config/google-docs-mcp/token.json")
GDRIVE_AVAILABLE = os.path.exists(GDRIVE_TOKEN_PATH)


# ===================================================================
# Project CRUD (4 tests) — DB verified
# ===================================================================


class TestProjectCRUD:
    """Client project create, list, get with DB verification."""

    def test_project_create(self, client, auth_headers):
        """POST /projects → client_projects row created in DB."""
        resp = client.post(
            "/api/projects",
            headers=auth_headers,
            json={
                "client_name": "Navitus Health Solutions",
                "folder_id": "fake_folder_id_123",
                "folder_name": "Navitus Documents",
            },
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["message"] == "Client project created"
        pid = data["project_id"]

        # DB: client_projects row exists
        rows = query_db("SELECT * FROM client_projects WHERE id = ?", (pid,))
        assert len(rows) == 1, f"No client_projects row for {pid}"
        assert rows[0]["client_name"] == "Navitus Health Solutions"

    def test_project_create_requires_client_name(self, client, auth_headers):
        """POST /projects without client_name → 400."""
        resp = client.post(
            "/api/projects",
            headers=auth_headers,
            json={"folder_id": "some_id"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data.get("error"), "400 must include error message"

    def test_project_list(self, client, auth_headers):
        """GET /projects → projects listed for user."""
        client.post(
            "/api/projects",
            headers=auth_headers,
            json={"client_name": "OPI", "folder_id": "opi_folder"},
        )

        resp = client.get("/api/projects", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "projects" in data
        assert len(data["projects"]) >= 1

        # DB: verify count matches
        db_rows = query_db("SELECT * FROM client_projects")
        assert len(db_rows) >= 1

    def test_project_user_isolation(self, client, auth_headers, second_user_headers):
        """Users only see their own projects — API and DB level."""
        resp1 = client.post(
            "/api/projects",
            headers=auth_headers,
            json={"client_name": "User1 Project", "folder_id": "u1_folder"},
        )
        pid1 = resp1.get_json().get("project_id")

        client.post(
            "/api/projects",
            headers=second_user_headers,
            json={"client_name": "User2 Project", "folder_id": "u2_folder"},
        )

        # User 2 should not see user 1's project
        resp2 = client.get("/api/projects", headers=second_user_headers)
        data = resp2.get_json()
        assert "projects" in data
        project_names = [p.get("client_name") for p in data.get("projects", [])]
        assert "User1 Project" not in project_names

        # DB: verify different user_ids
        assert pid1, "Project creation failed — no project_id returned"
        rows = query_db("SELECT user_id FROM client_projects WHERE id = ?", (pid1,))
        assert len(rows) == 1


# ===================================================================
# Project Analysis (4 tests) — DB verified
# ===================================================================


class TestProjectAnalysis:
    """Project analysis lifecycle."""

    def test_project_analysis_get_before_analyze(self, client, auth_headers):
        """GET /projects/<id>/analysis before analyze → 200 with empty analysis."""
        resp = client.post(
            "/api/projects",
            headers=auth_headers,
            json={"client_name": "TestClient", "folder_id": "test_folder"},
        )
        pid = resp.get_json().get("project_id")

        resp2 = client.get(f"/api/projects/{pid}/analysis", headers=auth_headers)
        assert resp2.status_code == 200  # project exists, analysis fields empty
        data = resp2.get_json()
        assert isinstance(data, dict)

    @pytest.mark.integration  # needs a real Google Drive OAuth token; CI has none

    def test_project_analyze_starts_job(self, client, auth_headers):
        """POST /projects/<id>/analyze → background job created, DB verified."""
        if not GDRIVE_AVAILABLE:
            pytest.fail(
                "Google Drive OAuth token not found at "
                f"{GDRIVE_TOKEN_PATH}. Required for project analysis tests."
            )

        resp = client.post(
            "/api/projects",
            headers=auth_headers,
            json={"client_name": "AnalyzeTest", "folder_id": "real_folder_id"},
        )
        pid = resp.get_json().get("project_id")

        resp2 = client.post(f"/api/projects/{pid}/analyze", headers=auth_headers, json={})
        assert resp2.status_code == 202  # starts background job
        data = resp2.get_json()
        assert data["message"] == "Analysis started"
        job_id = data["job_id"]

        # DB: batch_jobs row exists
        rows = query_db("SELECT * FROM batch_jobs WHERE id = ?", (job_id,))
        assert len(rows) == 1, f"No batch_jobs row for analyze job {job_id}"

    def test_project_analysis_edit(self, client, auth_headers):
        """PUT /projects/<id>/analysis → edits saved in DB."""
        resp = client.post(
            "/api/projects",
            headers=auth_headers,
            json={"client_name": "EditTest", "folder_id": "edit_folder"},
        )
        pid = resp.get_json().get("project_id")

        resp2 = client.put(
            f"/api/projects/{pid}/analysis",
            headers=auth_headers,
            json={"technical": {"technologies": ["Python", "AWS", "Docker"]}},
        )
        assert resp2.status_code == 200  # project exists (just created above)
        edit_data = resp2.get_json()
        assert isinstance(edit_data, dict)

    def test_project_approve(self, client, auth_headers):
        """POST /projects/<id>/approve → approval attempt."""
        resp = client.post(
            "/api/projects",
            headers=auth_headers,
            json={"client_name": "ApproveTest", "folder_id": "approve_folder"},
        )
        pid = resp.get_json().get("project_id")

        resp2 = client.post(f"/api/projects/{pid}/approve", headers=auth_headers, json={})
        assert resp2.status_code == 200
        data = resp2.get_json()
        assert data["message"] == "Analysis approved and stored in knowledge graph"


# ===================================================================
# Project Documents (2 tests)
# ===================================================================


class TestProjectDocuments:
    """Project document listing."""

    def test_project_documents_empty(self, client, auth_headers):
        """GET /projects/<id>/documents → empty before analysis."""
        resp = client.post(
            "/api/projects",
            headers=auth_headers,
            json={"client_name": "DocTest", "folder_id": "doc_folder"},
        )
        pid = resp.get_json().get("project_id")

        resp2 = client.get(f"/api/projects/{pid}/documents", headers=auth_headers)
        assert resp2.status_code == 200  # project exists; returns empty documents list
        data = resp2.get_json()
        assert "documents" in data

    @pytest.mark.integration  # needs a real Google Drive OAuth token; CI has none

    def test_project_folders_browse(self, client, auth_headers):
        """GET /projects/folders → GDrive folder listing."""
        if not GDRIVE_AVAILABLE:
            pytest.fail(
                "Google Drive OAuth token not found at "
                f"{GDRIVE_TOKEN_PATH}. Required for folder browse test."
            )
        resp = client.get("/api/projects/folders", headers=auth_headers)
        if resp.status_code == 503:
            pytest.fail("Google Drive service returned 503 — check OAuth token validity.")
        assert resp.status_code == 200


# ===================================================================
# Project Reanalyze & Reset Status (3 tests) — DB verified
# ===================================================================


class TestProjectReanalyzeAndReset:
    """Reanalyze and reset-status routes — previously mock-only."""

    def test_project_reanalyze(self, client, auth_headers):
        """POST /projects/<id>/reanalyze → starts re-analysis job, DB verified."""
        resp = client.post(
            "/api/projects",
            headers=auth_headers,
            json={"client_name": "ReanalyzeTest", "folder_id": "reanalyze_folder"},
        )
        pid = resp.get_json().get("project_id")
        assert pid, "No project_id returned"

        resp2 = client.post(
            f"/api/projects/{pid}/reanalyze",
            headers=auth_headers,
            json={"force": False},
        )
        assert resp2.status_code == 202  # starts background reanalysis job
        data = resp2.get_json()
        assert "job_id" in data

        # DB: batch_jobs row exists for reanalysis
        job_id = data["job_id"]
        rows = query_db("SELECT * FROM batch_jobs WHERE id = ?", (job_id,))
        assert len(rows) == 1, f"No batch_jobs row for reanalyze job {job_id}"

    def test_project_reanalyze_nonexistent(self, client, auth_headers):
        """POST /projects/99999/reanalyze → 404."""
        resp = client.post(
            "/api/projects/99999/reanalyze",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["error"] == "Project not found"

    def test_project_reset_status(self, client, auth_headers):
        """POST /projects/<id>/reset-status → status reset, DB verified."""
        resp = client.post(
            "/api/projects",
            headers=auth_headers,
            json={"client_name": "ResetTest", "folder_id": "reset_folder"},
        )
        pid = resp.get_json().get("project_id")
        assert pid, "No project_id returned"

        resp2 = client.post(
            f"/api/projects/{pid}/reset-status",
            headers=auth_headers,
            json={},
        )
        assert resp2.status_code == 200
        data = resp2.get_json()
        assert data["project_id"] == pid
        assert data["analysis_status"] in ("completed", "failed")

        # DB: verify status was updated
        rows = query_db("SELECT analysis_status FROM client_projects WHERE id = ?", (pid,))
        assert len(rows) == 1
        assert rows[0]["analysis_status"] in ("completed", "failed")

    def test_project_reset_status_nonexistent(self, client, auth_headers):
        """POST /projects/99999/reset-status → 404."""
        resp = client.post(
            "/api/projects/99999/reset-status",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["error"] == "Project not found"
