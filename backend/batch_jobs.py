"""
Background job manager using daemon threads + SQLite job tracking.
No external deps (Celery/Redis). Each method opens its own DB connection for thread safety.
"""

import contextlib
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

import models

_lock = threading.Lock()


def _init_batch_jobs_table():
    with models.get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS batch_jobs (
                id TEXT PRIMARY KEY,
                job_type TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                user_id INTEGER NOT NULL,
                params_json TEXT DEFAULT '{}',
                progress_json TEXT DEFAULT '{}',
                result_json TEXT DEFAULT '{}',
                error_message TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP
            )
        """
        )
        conn.commit()


class BatchJobManager:
    """Singleton background job manager."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._threads = {}
            cls._instance._shutdown = False
        return cls._instance

    def create_job(self, job_type, user_id, params=None):
        job_id = str(uuid.uuid4())
        with models.get_db() as conn:
            conn.execute(
                "INSERT INTO batch_jobs (id, job_type, user_id, params_json) VALUES (?, ?, ?, ?)",
                (job_id, job_type, user_id, json.dumps(params or {})),
            )
            conn.commit()
        return job_id

    def start_job(self, job_id, worker_fn):
        # Capture DB path NOW so the worker thread uses the correct DB
        # even if models.DB_PATH is changed/deleted later (e.g., in tests)
        db_path = models.DB_PATH
        conn = models.get_db_connection(db_path=db_path)
        try:
            conn.execute(
                "UPDATE batch_jobs SET status = 'running', started_at = ? WHERE id = ?",
                (datetime.now(timezone.utc).isoformat(), job_id),
            )
            conn.commit()
        finally:
            conn.close()

        t = threading.Thread(
            target=self._run_worker, args=(job_id, worker_fn, db_path), daemon=False
        )
        with _lock:
            self._threads[job_id] = t
        t.start()

    def _run_worker(self, job_id, worker_fn, db_path):
        try:
            result = worker_fn(job_id)
            if not self._shutdown:
                self.complete_job(job_id, result, db_path=db_path)
        except Exception as e:
            if not self._shutdown:
                self.fail_job(job_id, str(e), db_path=db_path)
        finally:
            with _lock:
                self._threads.pop(job_id, None)

    def update_progress(self, job_id, progress, db_path=None):
        path = db_path or models.DB_PATH
        conn = models.get_db_connection(db_path=path)
        try:
            conn.execute(
                "UPDATE batch_jobs SET progress_json = ? WHERE id = ?",
                (json.dumps(progress), job_id),
            )
            conn.commit()
        finally:
            conn.close()

    def complete_job(self, job_id, result=None, db_path=None):
        path = db_path or models.DB_PATH
        try:
            conn = models.get_db_connection(db_path=path)
            try:
                conn.execute(
                    "UPDATE batch_jobs SET status = 'completed', "
                    "result_json = ?, completed_at = ? WHERE id = ?",
                    (
                        json.dumps(result or {}),
                        datetime.now(timezone.utc).isoformat(),
                        job_id,
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        except sqlite3.OperationalError:
            pass  # DB deleted during test teardown — safe to ignore

    def fail_job(self, job_id, error_message, db_path=None):
        path = db_path or models.DB_PATH
        try:
            conn = models.get_db_connection(db_path=path)
            try:
                conn.execute(
                    "UPDATE batch_jobs SET status = 'failed', "
                    "error_message = ?, completed_at = ? WHERE id = ?",
                    (error_message, datetime.now(timezone.utc).isoformat(), job_id),
                )
                conn.commit()
            finally:
                conn.close()
        except sqlite3.OperationalError:
            pass  # DB deleted during test teardown — safe to ignore

    def cancel_job(self, job_id, user_id=None):
        from models import get_db

        with get_db() as conn:
            if user_id is not None:
                row = conn.execute(
                    "SELECT id FROM batch_jobs WHERE id = ? AND user_id = ?",
                    (job_id, user_id),
                ).fetchone()
                if not row:
                    return {"error": "Job not found"}
            conn.execute(
                "UPDATE batch_jobs SET status = 'cancelled', completed_at = ? WHERE id = ?",
                (datetime.now(timezone.utc).isoformat(), job_id),
            )
            conn.commit()
        return {"message": "Job cancelled"}

    def get_job(self, job_id):
        with models.get_db() as conn:
            row = conn.execute("SELECT * FROM batch_jobs WHERE id = ?", (job_id,)).fetchone()
        if not row:
            return None
        return _row_to_dict(row)

    def get_jobs_for_user(self, user_id, job_type=None, limit=50):
        with models.get_db() as conn:
            if job_type:
                rows = conn.execute(
                    "SELECT * FROM batch_jobs WHERE user_id = ? "
                    "AND job_type = ? ORDER BY created_at DESC LIMIT ?",
                    (user_id, job_type, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM batch_jobs WHERE user_id = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (user_id, limit),
                ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def is_cancelled(self, job_id):
        with models.get_db() as conn:
            row = conn.execute("SELECT status FROM batch_jobs WHERE id = ?", (job_id,)).fetchone()
        return row and row[0] == "cancelled"

    def shutdown(self, timeout=5):
        """Join all worker threads. Call before deleting test DBs."""
        self._shutdown = True
        with _lock:
            threads = list(self._threads.values())
        for t in threads:
            t.join(timeout)


def _row_to_dict(row):
    d = dict(row)
    for key in ("params_json", "progress_json", "result_json"):
        if key in d and isinstance(d[key], str):
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                d[key] = json.loads(d[key])
    return d


def get_batch_manager():
    _init_batch_jobs_table()
    return BatchJobManager()
