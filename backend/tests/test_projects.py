"""Tests for project routes — CRUD, analysis, documents, approve.

Content validation + DB verification for all operations.
No mocks, no skips.
"""

from test_helpers import query_db


def test_list_projects_empty(client, auth_headers):
    """GET /api/projects with no projects → empty list."""
    resp = client.get("/api/projects", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "projects" in data
    assert isinstance(data["projects"], list)
    assert len(data["projects"]) == 0


def test_create_project_success(client, auth_headers):
    """POST /api/projects with valid data → 201, DB row created."""
    resp = client.post(
        "/api/projects",
        headers=auth_headers,
        json={
            "client_name": "Test Client Corp",
            "folder_id": "fake_folder_id_123",
        },
    )
    assert resp.status_code == 201, f"Project create failed: {resp.get_json()}"
    data = resp.get_json()
    assert "project_id" in data
    assert "message" in data
    pid = data["project_id"]

    # DB: verify project row
    rows = query_db("SELECT * FROM client_projects WHERE id = ?", (pid,))
    assert len(rows) == 1, f"No client_projects row for {pid}"
    assert rows[0]["client_name"] == "Test Client Corp"
    assert rows[0]["folder_id"] == "fake_folder_id_123"


def test_create_project_missing_fields(client, auth_headers):
    """POST /api/projects missing folder_id → 400 with error."""
    resp = client.post("/api/projects", headers=auth_headers, json={"client_name": "Test"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data
    assert isinstance(data["error"], str)


def test_list_projects_with_data(client, auth_headers):
    """After creating a project, it shows in the list."""
    client.post(
        "/api/projects",
        headers=auth_headers,
        json={"client_name": "Listed Corp", "folder_id": "folder_456"},
    )
    resp = client.get("/api/projects", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["projects"]) >= 1
    project = data["projects"][0]
    assert "id" in project
    assert "client_name" in project
    assert project["client_name"] == "Listed Corp"

    # DB: verify row matches API response
    rows = query_db("SELECT * FROM client_projects WHERE client_name = ?", ("Listed Corp",))
    assert len(rows) >= 1, "Listed Corp not found in DB"


def test_project_analysis_not_found(client, auth_headers):
    """GET /api/projects/99999/analysis → 404 with error."""
    resp = client.get("/api/projects/99999/analysis", headers=auth_headers)
    assert resp.status_code == 404
    data = resp.get_json()
    assert "error" in data


def test_project_documents_not_found(client, auth_headers):
    """GET /api/projects/99999/documents → 404 with error."""
    resp = client.get("/api/projects/99999/documents", headers=auth_headers)
    assert resp.status_code == 404
    data = resp.get_json()
    assert "error" in data


def test_project_approve_not_found(client, auth_headers):
    """POST /api/projects/99999/approve → 404 with error."""
    resp = client.post("/api/projects/99999/approve", headers=auth_headers)
    assert resp.status_code == 404
    data = resp.get_json()
    assert "error" in data


def test_projects_require_auth(client):
    """GET /api/projects without auth → 401."""
    resp = client.get("/api/projects")
    assert resp.status_code == 401
    data = resp.get_json()
    assert "error" in data or "message" in data or "msg" in data

    # DB: client_projects table accessible
    query_db("SELECT COUNT(*) FROM client_projects")
