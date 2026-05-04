"""Live Google Drive integration tests — verifies gdrive_service.py against real GDrive.

Tests: initialization, folder browsing, MIME type filtering, file metadata.
Requires OAuth token at ~/.config/google-docs-mcp/token.json or ~/.config/resume-optimizer/token.json.
Skips gracefully if token unavailable.
"""

import os
import sys

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


def _gdrive_token_exists():
    paths = [
        os.path.expanduser("~/.config/resume-optimizer/token.json"),
        os.path.expanduser("~/.config/google-docs-mcp/token.json"),
    ]
    env_path = os.environ.get("GOOGLE_TOKEN_PATH")
    if env_path:
        paths.insert(0, env_path)
    return any(os.path.exists(p) for p in paths)


GDRIVE_AVAILABLE = _gdrive_token_exists()
pytestmark = pytest.mark.skipif(not GDRIVE_AVAILABLE, reason="Google Drive token not found")


@pytest.fixture(scope="module")
def gdrive():
    """Return GDriveService instance."""
    from gdrive_service import get_gdrive_service

    return get_gdrive_service()


# ===================================================================
# Initialization (1 test)
# ===================================================================


class TestGDriveInit:
    """Google Drive service initialization."""

    def test_service_initializes(self, gdrive):
        """GDriveService initializes without error."""
        assert gdrive is not None


# ===================================================================
# Folder Browsing (3 tests)
# ===================================================================


class TestFolderBrowsing:
    """Browse Google Drive folders."""

    def test_get_root_folders(self, gdrive):
        """get_root_folders returns list of top-level folders."""
        result = gdrive.get_root_folders()
        assert "files" in result
        assert isinstance(result["files"], list)
        # User should have at least one folder
        assert len(result["files"]) >= 1
        # All items should be folders
        for item in result["files"]:
            assert (
                item.get("isFolder") is True
                or item.get("mimeType") == "application/vnd.google-apps.folder"
            )

    def test_list_resume_folder(self, gdrive):
        """list_resume_folder finds Resumes folder or reports not found."""
        result = gdrive.list_resume_folder()
        assert isinstance(result, dict)
        assert "files" in result
        # folder_found indicates if "Resumes" folder exists
        if result.get("folder_found"):
            assert isinstance(result["files"], list)
            assert result.get("folder_name") == "Resumes"

    def test_list_folder_by_id_returns_files(self, gdrive):
        """list_folder_by_id with root returns files."""
        # First get a root folder ID
        root = gdrive.get_root_folders()
        if not root["files"]:
            pytest.skip("No root folders found")

        folder_id = root["files"][0]["id"]
        result = gdrive.list_folder_by_id(folder_id)
        assert "files" in result
        assert isinstance(result["files"], list)
        assert result.get("folder_id") == folder_id


# ===================================================================
# MIME Type Filtering (1 test)
# ===================================================================


class TestMIMETypes:
    """Supported MIME type classification."""

    def test_supported_types_only(self, gdrive):
        """File listing marks supported types correctly."""
        root = gdrive.get_root_folders()
        if not root["files"]:
            pytest.skip("No root folders found")

        folder_id = root["files"][0]["id"]
        result = gdrive.list_folder_by_id(folder_id)

        for item in result["files"]:
            file_type = item.get("fileType", "")
            supported = item.get("supported", False)
            if file_type in ("folder", "gdoc", "pdf", "docx", "doc", "txt"):
                assert supported is True, f"{file_type} should be supported"
            elif file_type == "unsupported":
                assert supported is False


# ===================================================================
# File Import (1 test)
# ===================================================================


class TestFileImport:
    """Import files from Google Drive."""

    def test_get_file_metadata(self, gdrive):
        """get_file_metadata returns metadata for a known file."""
        # Find a file in root folders to test metadata
        root = gdrive.get_root_folders()
        if not root["files"]:
            pytest.skip("No root folders found")

        folder_id = root["files"][0]["id"]
        result = gdrive.list_folder_by_id(folder_id)
        files = [f for f in result["files"] if not f.get("isFolder")]
        if not files:
            pytest.skip("No files found in first folder")

        file_id = files[0]["id"]
        metadata = gdrive.get_file_metadata(file_id)
        assert "id" in metadata
        assert "name" in metadata
        assert "mimeType" in metadata
        assert metadata["id"] == file_id
