"""Tests for resume template CRUD and customization (Phase 13.1)."""

import io

import pytest
from test_helpers import JD_TEXT, RESUME_TEXT, query_db


class TestTemplateCreate:
    def test_create_template(self, client, auth_headers):
        resp = client.post(
            "/api/templates",
            headers=auth_headers,
            json={
                "name": "Architect Resume",
                "role_type": "architect",
                "base_content": RESUME_TEXT,
            },
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == "Architect Resume"
        assert data["role_type"] == "architect"
        assert data["base_content"] == RESUME_TEXT
        assert "id" in data
        # DB: verify template persisted
        rows = query_db("SELECT name, role_type FROM resume_templates WHERE id = ?", (data["id"],))
        assert len(rows) == 1
        assert rows[0]["name"] == "Architect Resume"

    def test_create_template_missing_name(self, client, auth_headers):
        resp = client.post(
            "/api/templates",
            headers=auth_headers,
            json={"role_type": "ic", "base_content": "content"},
        )
        assert resp.status_code == 400
        assert "name" in resp.get_json()["error"].lower()

    def test_create_template_invalid_role_type(self, client, auth_headers):
        resp = client.post(
            "/api/templates",
            headers=auth_headers,
            json={"name": "Bad", "role_type": "ninja", "base_content": "content"},
        )
        assert resp.status_code == 400
        assert "role_type" in resp.get_json()["error"].lower()

    def test_create_template_missing_content(self, client, auth_headers):
        resp = client.post(
            "/api/templates",
            headers=auth_headers,
            json={"name": "Empty", "role_type": "general"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert data["error"] != ""

    def test_create_from_resume_id(self, client, auth_headers):
        # Upload a resume first
        upload = client.post(
            "/api/resume/upload",
            headers={"Authorization": auth_headers["Authorization"]},
            data={"file": (io.BytesIO(RESUME_TEXT.encode()), "resume.txt")},
            content_type="multipart/form-data",
        )
        assert upload.status_code == 201
        resume_id = upload.get_json()["resume_id"]

        resp = client.post(
            "/api/templates",
            headers=auth_headers,
            json={"name": "From Upload", "role_type": "general", "from_resume_id": resume_id},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert len(data["base_content"]) > 100

    def test_create_from_invalid_resume_id(self, client, auth_headers):
        resp = client.post(
            "/api/templates",
            headers=auth_headers,
            json={"name": "Bad", "role_type": "general", "from_resume_id": 99999},
        )
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data
        assert data["error"] != ""

    def test_create_all_valid_role_types(self, client, auth_headers):
        for rt in ("architect", "manager", "ic", "consultant", "executive", "general"):
            resp = client.post(
                "/api/templates",
                headers=auth_headers,
                json={"name": f"Template {rt}", "role_type": rt, "base_content": "content"},
            )
            assert resp.status_code == 201, f"Failed for role_type={rt}"
            data = resp.get_json()
            assert data["role_type"] == rt
        # DB: verify all 6 templates created
        rows = query_db("SELECT role_type FROM resume_templates WHERE user_id = 1")
        assert len(rows) == 6


class TestTemplateList:
    def test_list_empty(self, client, auth_headers):
        resp = client.get("/api/templates", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 0
        assert data["templates"] == []

    def test_list_multiple(self, client, auth_headers):
        for i in range(3):
            client.post(
                "/api/templates",
                headers=auth_headers,
                json={
                    "name": f"Template {i}",
                    "role_type": "general",
                    "base_content": f"content {i}",
                },
            )
        # DB: verify 3 templates stored
        rows = query_db("SELECT name FROM resume_templates WHERE user_id = 1 ORDER BY name")
        assert len(rows) == 3
        assert rows[0]["name"] == "Template 0"
        assert rows[2]["name"] == "Template 2"

        resp = client.get("/api/templates", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 3
        assert isinstance(data["templates"], list)
        assert len(data["templates"]) == 3

    def test_list_order_by_updated(self, client, auth_headers):
        for name in ("First", "Second", "Third"):
            client.post(
                "/api/templates",
                headers=auth_headers,
                json={"name": name, "role_type": "general", "base_content": "content"},
            )
        # Update the first one so it moves to top
        templates = client.get("/api/templates", headers=auth_headers).get_json()["templates"]
        first_id = [t for t in templates if t["name"] == "First"][0]["id"]
        client.put(
            f"/api/templates/{first_id}",
            headers=auth_headers,
            json={"base_content": "updated content"},
        )
        resp = client.get("/api/templates", headers=auth_headers)
        names = [t["name"] for t in resp.get_json()["templates"]]
        assert names[0] == "First"  # Most recently updated


class TestTemplateGet:
    def test_get_by_id(self, client, auth_headers):
        create = client.post(
            "/api/templates",
            headers=auth_headers,
            json={"name": "My Template", "role_type": "architect", "base_content": RESUME_TEXT},
        )
        tid = create.get_json()["id"]
        resp = client.get(f"/api/templates/{tid}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["name"] == "My Template"
        # DB: verify template exists
        rows = query_db("SELECT id FROM resume_templates WHERE id = ?", (tid,))
        assert len(rows) == 1

    def test_get_not_found(self, client, auth_headers):
        resp = client.get("/api/templates/99999", headers=auth_headers)
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data
        assert data["error"] != ""


class TestTemplateUpdate:
    def test_update_name(self, client, auth_headers):
        create = client.post(
            "/api/templates",
            headers=auth_headers,
            json={"name": "Old Name", "role_type": "general", "base_content": "content"},
        )
        tid = create.get_json()["id"]
        resp = client.put(f"/api/templates/{tid}", headers=auth_headers, json={"name": "New Name"})
        assert resp.status_code == 200
        assert resp.get_json()["name"] == "New Name"
        # DB: verify update persisted
        rows = query_db("SELECT name FROM resume_templates WHERE id = ?", (tid,))
        assert rows[0]["name"] == "New Name"

    def test_update_role_type(self, client, auth_headers):
        create = client.post(
            "/api/templates",
            headers=auth_headers,
            json={"name": "Test", "role_type": "general", "base_content": "content"},
        )
        tid = create.get_json()["id"]
        resp = client.put(
            f"/api/templates/{tid}", headers=auth_headers, json={"role_type": "manager"}
        )
        assert resp.status_code == 200
        assert resp.get_json()["role_type"] == "manager"
        # DB: verify update persisted
        rows = query_db("SELECT role_type FROM resume_templates WHERE id = ?", (tid,))
        assert rows[0]["role_type"] == "manager"

    def test_update_base_content(self, client, auth_headers):
        create = client.post(
            "/api/templates",
            headers=auth_headers,
            json={"name": "Test", "role_type": "general", "base_content": "old"},
        )
        tid = create.get_json()["id"]
        resp = client.put(
            f"/api/templates/{tid}", headers=auth_headers, json={"base_content": "new content"}
        )
        assert resp.status_code == 200
        assert resp.get_json()["base_content"] == "new content"
        # DB: verify content update persisted
        rows = query_db("SELECT base_content FROM resume_templates WHERE id = ?", (tid,))
        assert rows[0]["base_content"] == "new content"

    def test_update_invalid_role_type(self, client, auth_headers):
        create = client.post(
            "/api/templates",
            headers=auth_headers,
            json={"name": "Test", "role_type": "general", "base_content": "content"},
        )
        tid = create.get_json()["id"]
        resp = client.put(
            f"/api/templates/{tid}", headers=auth_headers, json={"role_type": "wizard"}
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert data["error"] != ""

    def test_update_not_found(self, client, auth_headers):
        resp = client.put("/api/templates/99999", headers=auth_headers, json={"name": "x"})
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data
        assert data["error"] != ""

    def test_update_no_fields(self, client, auth_headers):
        create = client.post(
            "/api/templates",
            headers=auth_headers,
            json={"name": "Test", "role_type": "general", "base_content": "content"},
        )
        tid = create.get_json()["id"]
        resp = client.put(f"/api/templates/{tid}", headers=auth_headers, json={})
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert data["error"] != ""


class TestTemplateDelete:
    def test_delete(self, client, auth_headers):
        create = client.post(
            "/api/templates",
            headers=auth_headers,
            json={"name": "To Delete", "role_type": "general", "base_content": "content"},
        )
        tid = create.get_json()["id"]
        # DB: verify exists before delete
        rows = query_db("SELECT id FROM resume_templates WHERE id = ?", (tid,))
        assert len(rows) == 1

        resp = client.delete(f"/api/templates/{tid}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "message" in data
        # Verify gone via API
        resp2 = client.get(f"/api/templates/{tid}", headers=auth_headers)
        assert resp2.status_code == 404
        # DB: verify gone from database
        rows = query_db("SELECT id FROM resume_templates WHERE id = ?", (tid,))
        assert len(rows) == 0

    def test_delete_not_found(self, client, auth_headers):
        resp = client.delete("/api/templates/99999", headers=auth_headers)
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data


class TestTemplateIsolation:
    def test_user2_cannot_see_user1_template(self, client, auth_headers, second_user_headers):
        create = client.post(
            "/api/templates",
            headers=auth_headers,
            json={"name": "Private", "role_type": "general", "base_content": "secret"},
        )
        tid = create.get_json()["id"]
        resp = client.get(f"/api/templates/{tid}", headers=second_user_headers)
        assert resp.status_code == 404

    def test_user2_cannot_delete_user1_template(self, client, auth_headers, second_user_headers):
        create = client.post(
            "/api/templates",
            headers=auth_headers,
            json={"name": "Private", "role_type": "general", "base_content": "secret"},
        )
        tid = create.get_json()["id"]
        resp = client.delete(f"/api/templates/{tid}", headers=second_user_headers)
        assert resp.status_code == 404
        # Verify still exists for user1
        resp2 = client.get(f"/api/templates/{tid}", headers=auth_headers)
        assert resp2.status_code == 200
        # DB: verify template still in database
        rows = query_db("SELECT id FROM resume_templates WHERE id = ?", (tid,))
        assert len(rows) == 1

    def test_user2_cannot_update_user1_template(self, client, auth_headers, second_user_headers):
        create = client.post(
            "/api/templates",
            headers=auth_headers,
            json={"name": "Private", "role_type": "general", "base_content": "secret"},
        )
        tid = create.get_json()["id"]
        resp = client.put(
            f"/api/templates/{tid}", headers=second_user_headers, json={"name": "Hacked"}
        )
        assert resp.status_code == 404


class TestTemplateCustomize:
    def test_customize_for_job(self, client, auth_headers):
        create = client.post(
            "/api/templates",
            headers=auth_headers,
            json={"name": "Arch", "role_type": "architect", "base_content": RESUME_TEXT},
        )
        tid = create.get_json()["id"]
        resp = client.post(
            f"/api/templates/{tid}/customize",
            headers=auth_headers,
            json={"job_description": JD_TEXT},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "optimized_text" in data
        assert "score" in data
        assert data["score"] > 0
        assert data["score"] <= 100
        assert data["template_id"] == tid
        assert isinstance(data["optimized_text"], str)
        assert len(data["optimized_text"]) > 50
        assert "matching_keywords" in data or "added_keywords" in data

    def test_customize_short_jd(self, client, auth_headers):
        create = client.post(
            "/api/templates",
            headers=auth_headers,
            json={"name": "Test", "role_type": "general", "base_content": RESUME_TEXT},
        )
        tid = create.get_json()["id"]
        resp = client.post(
            f"/api/templates/{tid}/customize",
            headers=auth_headers,
            json={"job_description": "too short"},
        )
        assert resp.status_code == 400

    def test_customize_not_found(self, client, auth_headers):
        resp = client.post(
            "/api/templates/99999/customize",
            headers=auth_headers,
            json={"job_description": JD_TEXT},
        )
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data


class TestTemplateDownload:
    def test_download_pdf(self, client, auth_headers):
        resp = client.post(
            "/api/templates/1/download/pdf",
            headers=auth_headers,
            json={"text": RESUME_TEXT},
        )
        assert resp.status_code == 200
        assert resp.content_type == "application/pdf"
        assert len(resp.data) > 100

    def test_download_docx(self, client, auth_headers):
        resp = client.post(
            "/api/templates/1/download/docx",
            headers=auth_headers,
            json={"text": RESUME_TEXT},
        )
        assert resp.status_code == 200
        assert "wordprocessingml" in resp.content_type
        assert len(resp.data) > 100

    def test_download_invalid_format(self, client, auth_headers):
        resp = client.post(
            "/api/templates/1/download/csv",
            headers=auth_headers,
            json={"text": RESUME_TEXT},
        )
        assert resp.status_code == 400  # Route matches but format invalid


class TestTemplateDB:
    def test_template_persists_in_db(self, client, auth_headers):
        client.post(
            "/api/templates",
            headers=auth_headers,
            json={"name": "DB Test", "role_type": "ic", "base_content": "test content"},
        )
        rows = query_db("SELECT * FROM resume_templates WHERE name = 'DB Test'")
        assert len(rows) == 1
        assert rows[0]["role_type"] == "ic"

    def test_to_dict_has_all_fields(self, client, auth_headers):
        resp = client.post(
            "/api/templates",
            headers=auth_headers,
            json={"name": "Dict Test", "role_type": "executive", "base_content": "content"},
        )
        data = resp.get_json()
        for field in ("id", "user_id", "name", "role_type", "base_content"):
            assert field in data, f"Missing field: {field}"
