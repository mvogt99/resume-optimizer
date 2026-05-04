"""
Google Drive integration for resume ingestion.
Supports importing Google Docs (via MCP readDocument), PDF, DOCX, DOC, TXT
(via google-api-python-client download + local parsing).
"""

import io
import os
import tempfile

_gdrive_service = None


def get_gdrive_service():
    """Singleton accessor for GDriveService."""
    global _gdrive_service
    if _gdrive_service is None:
        _gdrive_service = GDriveService()
    return _gdrive_service


class GDriveService:
    """Wraps MCP calls + Google Drive API for resume file operations."""

    # MIME types we can handle
    SUPPORTED_MIMES = {
        "application/vnd.google-apps.document": "gdoc",
        "application/pdf": "pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "application/msword": "doc",
        "text/plain": "txt",
    }

    RESUME_FOLDER_NAME = "Resumes"

    def __init__(self):
        self._token_path = None

    def _get_drive_service(self):
        """Build a Google Drive API service per call (httplib2 is not thread-safe)."""
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            # Resolve token path once, reuse on subsequent calls
            if self._token_path is None:
                token_paths = [
                    os.environ.get("GOOGLE_TOKEN_PATH", ""),
                    os.path.expanduser("~/.config/resume-optimizer/token.json"),
                    os.path.expanduser("~/.config/google-docs-mcp/token.json"),
                ]
                for tp in token_paths:
                    if tp and os.path.exists(tp):
                        self._token_path = tp
                        break

            if not self._token_path:
                raise FileNotFoundError(
                    "Google credentials not found. Expected token at one of: "
                    "~/.config/resume-optimizer/token.json, "
                    "~/.config/google-docs-mcp/token.json. "
                    "Run the OAuth setup flow first."
                )

            credentials = Credentials.from_authorized_user_file(self._token_path)
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            return build("drive", "v3", credentials=credentials)

        except ImportError:
            raise ImportError(
                "google-api-python-client and google-auth required. "
                "Install with: pip install google-api-python-client google-auth"
            )

    FOLDER_MIME = "application/vnd.google-apps.folder"

    def _format_item(self, f):
        """Format a Drive file/folder into a consistent response dict."""
        mime = f.get("mimeType", "")
        is_folder = mime == self.FOLDER_MIME
        file_type = "folder" if is_folder else (self.SUPPORTED_MIMES.get(mime) or "unsupported")
        return {
            "id": f["id"],
            "name": f["name"],
            "mimeType": mime,
            "fileType": file_type,
            "isFolder": is_folder,
            "supported": is_folder or file_type != "unsupported",
            "modifiedTime": f.get("modifiedTime", ""),
            "size": int(f["size"]) if f.get("size") else None,
        }

    def list_folder_by_id(self, folder_id):
        """
        List files and subfolders in a Drive folder by ID.
        Returns folders first, then files, both sorted by modifiedTime desc.
        """
        service = self._get_drive_service()

        file_query = f"'{folder_id}' in parents and trashed = false"
        results = (
            service.files()
            .list(
                q=file_query,
                fields="files(id, name, mimeType, modifiedTime, size)",
                orderBy="folder,modifiedTime desc",
            )
            .execute()
        )

        items = [self._format_item(f) for f in results.get("files", [])]
        # Sort: folders first, then by modifiedTime desc
        folders = [i for i in items if i["isFolder"]]
        files = [i for i in items if not i["isFolder"]]
        return {"files": folders + files, "folder_id": folder_id}

    def list_resume_folder(self, folder_name=None):
        """
        List files in a named folder on Google Drive.
        Returns list of file metadata dicts.
        """
        service = self._get_drive_service()
        folder = folder_name or self.RESUME_FOLDER_NAME

        # Find the folder by name
        folder_query = (
            f"name = '{folder}' and mimeType = '{self.FOLDER_MIME}' " "and trashed = false"
        )
        folder_results = service.files().list(q=folder_query, fields="files(id, name)").execute()
        found = folder_results.get("files", [])

        if not found:
            return {"files": [], "folder_found": False, "folder_name": folder}

        result = self.list_folder_by_id(found[0]["id"])
        result["folder_found"] = True
        result["folder_name"] = folder
        return result

    def get_root_folders(self):
        """List top-level folders in the user's Drive."""
        service = self._get_drive_service()
        query = f"mimeType = '{self.FOLDER_MIME}' and 'root' in parents " "and trashed = false"
        results = (
            service.files()
            .list(
                q=query,
                fields="files(id, name, mimeType, modifiedTime)",
                orderBy="name",
            )
            .execute()
        )
        return {"files": [self._format_item(f) for f in results.get("files", [])]}

    def import_file(self, file_id):
        """
        Import a file from Google Drive by ID.
        Returns parsed text content and metadata.
        """
        service = self._get_drive_service()

        # Get file metadata
        file_meta = (
            service.files()
            .get(fileId=file_id, fields="id, name, mimeType, modifiedTime, size")
            .execute()
        )

        mime = file_meta.get("mimeType", "")
        file_type = self.SUPPORTED_MIMES.get(mime)

        if not file_type:
            raise ValueError(
                f"Unsupported file type: {mime}. "
                f"Supported: {', '.join(self.SUPPORTED_MIMES.values())}"
            )

        if file_type == "gdoc":
            text = self._import_google_doc(service, file_id)
        else:
            text = self._import_binary_file(service, file_id, file_meta["name"], file_type)

        return {
            "text": text,
            "file_id": file_id,
            "file_name": file_meta["name"],
            "file_type": file_type,
            "mime_type": mime,
            "modified_time": file_meta.get("modifiedTime", ""),
        }

    def get_file_metadata(self, file_id):
        """Get metadata for a specific file."""
        service = self._get_drive_service()
        return (
            service.files()
            .get(fileId=file_id, fields="id, name, mimeType, modifiedTime, size, webViewLink")
            .execute()
        )

    def _import_google_doc(self, service, file_id):
        """Export Google Doc as plain text."""
        content = service.files().export(fileId=file_id, mimeType="text/plain").execute()
        if isinstance(content, bytes):
            return content.decode("utf-8")
        return str(content)

    def _import_binary_file(self, service, file_id, filename, file_type):
        """Download binary file and parse with local parsers."""
        from googleapiclient.http import MediaIoBaseDownload

        request = service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)

        done = False
        while not done:
            _, done = downloader.next_chunk()

        # Write to temp file and parse
        ext_map = {"pdf": ".pdf", "docx": ".docx", "doc": ".doc", "txt": ".txt"}
        ext = ext_map.get(file_type, ".txt")

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(buffer.getvalue())
            tmp_path = tmp.name

        try:
            # Import at function level to avoid circular imports
            from utils import process_resume

            result = process_resume(tmp_path)
            return result.get("text", "")
        finally:
            os.unlink(tmp_path)
