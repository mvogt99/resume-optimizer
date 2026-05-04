"""Phase 9: Client Project Documentation Analysis."""

import contextlib
import json
import os
import tempfile

from batch_jobs import get_batch_manager
from document_parser import parse_any
from models import get_db

_analyzer = None


def get_project_analyzer():
    global _analyzer
    if _analyzer is None:
        _analyzer = ProjectAnalyzer()
    return _analyzer


class ProjectAnalyzer:
    """Singleton for client project analysis pipeline."""

    SUPPORTED_MIMES = {
        "application/vnd.google-apps.document": "gdoc",
        "application/vnd.google-apps.presentation": "gslides",
        "application/vnd.google-apps.spreadsheet": "gsheet",
        "application/pdf": "pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
        "text/plain": "txt",
        "text/markdown": "md",
        "application/json": "json",
        "application/xml": "xml",
        "text/xml": "xml",
        "text/csv": "csv",
    }

    EXPORT_MIMES = {
        "application/vnd.google-apps.document": "text/plain",
        "application/vnd.google-apps.presentation": "text/plain",
        "application/vnd.google-apps.spreadsheet": "text/csv",
    }

    def create_client(self, user_id, client_name, folder_id, folder_name=""):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO client_projects "
                "(user_id, client_name, folder_id, folder_name) VALUES (?, ?, ?, ?)",
                (user_id, client_name, folder_id, folder_name),
            )
            conn.commit()
            return cursor.lastrowid

    def get_client(self, client_id, user_id=None):
        with get_db() as conn:
            if user_id is not None:
                row = conn.execute(
                    "SELECT * FROM client_projects WHERE id = ? AND user_id = ?",
                    (client_id, user_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM client_projects WHERE id = ?", (client_id,)
                ).fetchone()
        return dict(row) if row else None

    def get_clients_for_user(self, user_id):
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM client_projects WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            for key in (
                "technical_analysis_json",
                "governance_analysis_json",
                "role_analysis_json",
                "skills_json",
                "correlation_json",
                "business_outcomes_json",
            ):
                if isinstance(d.get(key), str):
                    with contextlib.suppress(json.JSONDecodeError, TypeError):
                        d[key] = json.loads(d[key])
            result.append(d)
        return result

    def start_analysis(self, client_id, user_id):
        manager = get_batch_manager()
        job_id = manager.create_job("project_analysis", user_id, {"client_id": client_id})
        manager.start_job(job_id, lambda jid: self._analysis_worker(jid, client_id))
        return job_id

    def start_reanalysis(self, client_id, user_id, force=False, reextract_only=False):
        """Re-run LLM extraction on already-ingested documents (skip crawl+ingest)."""
        manager = get_batch_manager()
        job_id = manager.create_job(
            "project_reanalysis",
            user_id,
            {"client_id": client_id, "force": force, "reextract_only": reextract_only},
        )
        manager.start_job(
            job_id,
            lambda jid: self._reanalysis_worker(
                jid, client_id, force=force, reextract_only=reextract_only
            ),
        )
        return job_id

    def _reanalysis_worker(self, job_id, client_id, force=False, reextract_only=False):
        from project_analyzer_extraction import (
            classify_documents,
            extract_skills_and_outcomes_combined,
            load_classifications,
        )
        from project_analyzer_synthesis import (
            analyze_documents,
            correlate_cross_document,
            synthesize_client,
        )

        manager = get_batch_manager()
        if not self.get_client(client_id):
            raise ValueError(f"Client {client_id} not found")

        try:
            with get_db() as conn:
                if reextract_only:
                    conn.execute(
                        "UPDATE project_documents SET outcomes_json = NULL "
                        "WHERE client_id = ? AND status = 'analyzed'",
                        (client_id,),
                    )
                    conn.commit()
                    count = conn.execute(
                        "SELECT COUNT(*) FROM project_documents "
                        "WHERE client_id = ? AND status = 'analyzed'",
                        (client_id,),
                    ).fetchone()[0]
                    if count == 0:
                        self._update_client_status(client_id, "completed")
                        return {"status": "completed", "document_count": 0}
                    classifications = load_classifications(client_id)
                else:
                    if force:
                        conn.execute(
                            "UPDATE project_documents SET status = 'parsed', "
                            "analysis_json = '{}', "
                            "classification_json = NULL, outcomes_json = NULL "
                            "WHERE client_id = ? AND status = 'analyzed'",
                            (client_id,),
                        )
                    else:
                        conn.execute(
                            "UPDATE project_documents SET status = 'parsed', analysis_json = '{}' "
                            "WHERE client_id = ? AND status = 'analyzed' "
                            "AND analysis_json IN ("
                            '\'{"technical": [], "governance": [], "role": []}\', '
                            '\'{"technical": [], "governance": [], "role": [], '
                            '"skipped": "text_too_short"}\', \'{}\','
                            " '[]')",
                            (client_id,),
                        )
                    conn.commit()
                    count = conn.execute(
                        "SELECT COUNT(*) FROM project_documents "
                        "WHERE client_id = ? AND status = 'parsed'",
                        (client_id,),
                    ).fetchone()[0]
                    if count == 0:
                        self._update_client_status(client_id, "completed")
                        return {"status": "completed", "document_count": 0}

                if manager.is_cancelled(job_id):
                    return {"status": "cancelled"}

                self._update_client_status(client_id, "classifying")
                manager.update_progress(
                    job_id, {"phase": "classifying", "total": count, "processed": 0}
                )
                classifications = classify_documents(client_id, job_id, manager)

            if manager.is_cancelled(job_id):
                return {"status": "cancelled"}
            self._update_client_status(client_id, "analyzing")
            analyze_documents(client_id, job_id, manager, classifications)

            if manager.is_cancelled(job_id):
                return {"status": "cancelled"}
            self._update_client_status(client_id, "extracting_skills_outcomes")
            extract_skills_and_outcomes_combined(client_id, job_id, manager, classifications)

            if manager.is_cancelled(job_id):
                return {"status": "cancelled"}
            self._update_client_status(client_id, "correlating")
            correlate_cross_document(client_id, self.get_client)

            if manager.is_cancelled(job_id):
                return {"status": "cancelled"}
            self._update_client_status(client_id, "synthesizing")
            synthesize_client(client_id)

            self._update_client_status(client_id, "completed")
            return {"status": "completed", "document_count": count}
        except Exception:
            self._update_client_status(client_id, "failed")
            raise

    def _analysis_worker(self, job_id, client_id):
        from project_analyzer_extraction import (
            classify_documents,
            extract_skills_and_outcomes_combined,
        )
        from project_analyzer_synthesis import (
            analyze_documents,
            correlate_cross_document,
            synthesize_client,
        )

        manager = get_batch_manager()
        client = self.get_client(client_id)
        if not client:
            raise ValueError(f"Client {client_id} not found")

        try:
            with get_db() as conn:
                conn.execute(
                    "UPDATE project_documents SET status = 'parsed', analysis_json = '{}' "
                    "WHERE client_id = ? AND status = 'analyzed' "
                    "AND analysis_json IN ("
                    '\'{"technical": [], "governance": [], "role": []}\', \'{}\','
                    " '[]')",
                    (client_id,),
                )
                conn.commit()

            self._update_client_status(client_id, "crawling")
            manager.update_progress(job_id, {"phase": "crawling", "total": 0, "processed": 0})
            files = self._crawl_folder(client["folder_id"])

            if manager.is_cancelled(job_id):
                return {"status": "cancelled"}

            self._update_client_status(client_id, "ingesting")
            total_files = len(files)
            manager.update_progress(
                job_id, {"phase": "ingesting", "total": total_files, "processed": 0}
            )
            for i, file_info in enumerate(files):
                if manager.is_cancelled(job_id):
                    return {"status": "cancelled"}
                self._ingest_document(client_id, file_info)
                manager.update_progress(
                    job_id,
                    {
                        "phase": "ingesting",
                        "total": total_files,
                        "processed": i + 1,
                        "current_file": file_info.get("name", ""),
                    },
                )

            with get_db() as conn:
                count = conn.execute(
                    "SELECT COUNT(*) FROM project_documents "
                    "WHERE client_id = ? AND status = 'parsed'",
                    (client_id,),
                ).fetchone()[0]
                conn.execute(
                    "UPDATE client_projects SET document_count = ? WHERE id = ?", (count, client_id)
                )
                conn.commit()

            if manager.is_cancelled(job_id):
                return {"status": "cancelled"}
            self._update_client_status(client_id, "classifying")
            manager.update_progress(
                job_id, {"phase": "classifying", "total": count, "processed": 0}
            )
            classifications = classify_documents(client_id, job_id, manager)

            if manager.is_cancelled(job_id):
                return {"status": "cancelled"}
            self._update_client_status(client_id, "analyzing")
            analyze_documents(client_id, job_id, manager, classifications)

            if manager.is_cancelled(job_id):
                return {"status": "cancelled"}
            self._update_client_status(client_id, "extracting_skills_outcomes")
            extract_skills_and_outcomes_combined(client_id, job_id, manager, classifications)

            if manager.is_cancelled(job_id):
                return {"status": "cancelled"}
            self._update_client_status(client_id, "correlating")
            correlate_cross_document(client_id, self.get_client)

            if manager.is_cancelled(job_id):
                return {"status": "cancelled"}
            self._update_client_status(client_id, "synthesizing")
            synthesize_client(client_id)

            self._update_client_status(client_id, "completed")
            return {"status": "completed", "document_count": count}
        except Exception:
            self._update_client_status(client_id, "failed")
            raise

    def _crawl_folder(self, folder_id, path=""):
        """Recursively crawl a Google Drive folder."""
        try:
            from gdrive_service import get_gdrive_service

            gdrive = get_gdrive_service()
            service = gdrive._get_drive_service()
        except Exception as e:
            print(f"[project_analyzer] Cannot access Google Drive: {e}")
            return []

        files = []
        try:
            results = (
                service.files()
                .list(
                    q=f"'{folder_id}' in parents and trashed = false",
                    fields="files(id, name, mimeType, modifiedTime)",
                    pageSize=200,
                )
                .execute()
            )
            for item in results.get("files", []):
                mime = item["mimeType"]
                if mime == "application/vnd.google-apps.folder":
                    sub_path = f"{path}/{item['name']}" if path else item["name"]
                    files.extend(self._crawl_folder(item["id"], sub_path))
                elif mime in self.SUPPORTED_MIMES:
                    item["folder_path"] = path
                    item["file_type"] = self.SUPPORTED_MIMES[mime]
                    files.append(item)
        except Exception as e:
            print(f"[project_analyzer] Crawl error in {folder_id}: {e}")
        return files

    def _ingest_document(self, client_id, file_info):
        """Download and parse a single document."""
        file_id, file_name = file_info["id"], file_info["name"]
        mime_type = file_info["mimeType"]
        file_type = file_info.get("file_type", "")
        folder_path = file_info.get("folder_path", "")

        with get_db() as conn:
            if conn.execute(
                "SELECT id FROM project_documents WHERE client_id = ? AND file_id = ?",
                (client_id, file_id),
            ).fetchone():
                return

        try:
            from gdrive_service import get_gdrive_service

            service = get_gdrive_service()._get_drive_service()
            if mime_type in self.EXPORT_MIMES:
                content = (
                    service.files()
                    .export(fileId=file_id, mimeType=self.EXPORT_MIMES[mime_type])
                    .execute()
                )
                text = (
                    content.decode("utf-8", errors="replace")
                    if isinstance(content, bytes)
                    else str(content)
                )
            else:
                content = service.files().get_media(fileId=file_id).execute()
                suffix = os.path.splitext(file_name)[1] or f".{file_type}"
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                    tmp.write(content if isinstance(content, bytes) else content.encode("utf-8"))
                    tmp_path = tmp.name
                text = parse_any(tmp_path)
                os.unlink(tmp_path)

            with get_db() as conn:
                conn.execute(
                    "INSERT INTO project_documents "
                    "(client_id, file_id, file_name, mime_type, file_type, "
                    "folder_path, parsed_text, text_length, status) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'parsed')",
                    (
                        client_id,
                        file_id,
                        file_name,
                        mime_type,
                        file_type,
                        folder_path,
                        text,
                        len(text),
                    ),
                )
                conn.commit()
        except Exception as e:
            with get_db() as conn:
                conn.execute(
                    "INSERT INTO project_documents "
                    "(client_id, file_id, file_name, mime_type, file_type, "
                    "folder_path, status, error_message) VALUES (?, ?, ?, ?, ?, ?, 'error', ?)",
                    (client_id, file_id, file_name, mime_type, file_type, folder_path, str(e)),
                )
                conn.commit()

    def get_analysis(self, client_id, user_id=None):
        client = self.get_client(client_id, user_id=user_id)
        if not client:
            return None
        for key in ("technical_analysis_json", "governance_analysis_json", "role_analysis_json"):
            if isinstance(client.get(key), str):
                try:
                    client[key] = json.loads(client[key])
                except (json.JSONDecodeError, TypeError):
                    client[key] = []
        for key in ("skills_json", "business_outcomes_json"):
            if isinstance(client.get(key), str):
                try:
                    client[key] = json.loads(client[key])
                except (json.JSONDecodeError, TypeError):
                    client[key] = []
        for key in ("correlation_json",):
            if isinstance(client.get(key), str):
                try:
                    client[key] = json.loads(client[key])
                except (json.JSONDecodeError, TypeError):
                    client[key] = {}
        return client

    def import_structured_analysis(self, user_id, analysis_json, client_name=None):
        from project_analyzer_arango import import_structured_analysis

        return import_structured_analysis(user_id, analysis_json, client_name)

    def update_analysis(self, client_id, updates):
        sets, vals = [], []
        for key in ("technical_analysis_json", "governance_analysis_json", "role_analysis_json"):
            if key in updates:
                sets.append(f"{key} = ?")
                vals.append(
                    json.dumps(updates[key]) if not isinstance(updates[key], str) else updates[key]
                )
        if sets:
            sets.append("updated_at = CURRENT_TIMESTAMP")
            vals.append(client_id)
            with get_db() as conn:
                conn.execute(f"UPDATE client_projects SET {', '.join(sets)} WHERE id = ?", vals)
                conn.commit()

    def approve_analysis(self, client_id):
        client = self.get_analysis(client_id)
        if not client:
            return False
        with get_db() as conn:
            conn.execute(
                "UPDATE client_projects SET approved = 1, "
                "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (client_id,),
            )
            conn.commit()
        from project_analyzer_arango import write_to_arango

        write_to_arango(client)
        return True

    def get_documents(self, client_id):
        with get_db() as conn:
            rows = conn.execute(
                "SELECT id, file_id, file_name, mime_type, file_type, "
                "folder_path, text_length, status, error_message "
                "FROM project_documents WHERE client_id = ? ORDER BY folder_path, file_name",
                (client_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def _update_client_status(self, client_id, status):
        with get_db() as conn:
            conn.execute(
                "UPDATE client_projects SET analysis_status = ?, "
                "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, client_id),
            )
            conn.commit()

    def list_drive_folders(self, parent_id=None):
        from project_analyzer_arango import list_drive_folders

        return list_drive_folders(parent_id)
