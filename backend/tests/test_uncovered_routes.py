"""Tests for previously uncovered routes — WI-2.

WI-2a: POST /api/resumes/gdrive/reimport/<version_id>
WI-2b: POST /api/sessions/<id>/optimize (covered in test_integration_sessions.py)

No mocks, no skips. DB verification after every write.
"""

import os

from test_helpers import query_db

GDRIVE_TOKEN_PATH = os.path.expanduser("~/.config/google-docs-mcp/token.json")

# Known GDrive file ID from the Resumes folder (Vogt_Michael-2023c.pdf)
KNOWN_GDRIVE_FILE_ID = "1lIcRt3sybLi9LeIH4ODFur8vKLQzy6ej"
KNOWN_GDRIVE_FILE_NAME = "Vogt_Michael-2023c.pdf"


class TestGDriveReimport:
    """POST /api/resumes/gdrive/reimport/<version_id> — WI-2a."""

    def test_gdrive_reimport_updates_version(self, client, auth_headers):
        """Import a GDrive file → reimport → verify version text updated."""
        assert os.path.exists(
            GDRIVE_TOKEN_PATH
        ), f"Google Drive OAuth token not found at {GDRIVE_TOKEN_PATH}"

        # 1. Import from GDrive
        resp = client.post(
            "/api/resumes/gdrive/import",
            headers=auth_headers,
            json={"file_id": KNOWN_GDRIVE_FILE_ID},
        )
        assert resp.status_code == 201, f"GDrive import failed: {resp.get_json()}"
        version_id = resp.get_json().get("version_id") or resp.get_json().get("id")
        assert version_id, "No version_id returned from GDrive import"

        # DB: verify version exists with source=google_drive
        rows = query_db("SELECT * FROM resume_versions WHERE id = ?", (version_id,))
        assert len(rows) == 1, f"No resume_versions row for {version_id}"
        assert rows[0]["source"] == "google_drive"

        # 2. Reimport same file
        resp = client.post(
            f"/api/resumes/gdrive/reimport/{version_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"Reimport failed: {resp.get_json()}"
        data = resp.get_json()
        assert data.get("text_length", 0) > 0

        # DB: verify text was updated (may be same content if file unchanged)
        rows = query_db("SELECT * FROM resume_versions WHERE id = ?", (version_id,))
        assert len(rows) == 1
        assert rows[0]["parsed_text"] is not None
        assert len(rows[0]["parsed_text"]) > 0

    def test_gdrive_reimport_nonexistent_version(self, client, auth_headers):
        """Reimport of nonexistent version → 404."""
        resp = client.post(
            "/api/resumes/gdrive/reimport/99999",
            headers=auth_headers,
        )
        assert resp.status_code == 404
        err = resp.get_json()
        assert err["error"] == "Version not found or unauthorized"

    def test_gdrive_reimport_non_gdrive_version(self, client, auth_headers):
        """Reimport of non-GDrive version → 400."""
        import models

        # Create a non-GDrive resume_version directly (file upload creates resumes, not versions)
        version = models.ResumeVersion.create(
            user_id=1,
            source="upload",
            file_name="test.txt",
            parsed_text="Non-GDrive resume content for reimport test",
        )
        assert version, "ResumeVersion.create() returned None"

        resp = client.post(
            f"/api/resumes/gdrive/reimport/{version.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 400
        err = resp.get_json()
        assert err["error"] == "Version is not from Google Drive"
