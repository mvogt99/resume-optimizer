"""Core tests for batch_jobs.py — job lifecycle, threading, singleton, cancel, progress."""

import json
import time

import batch_jobs
import pytest
from test_helpers import query_db

# ---------------------------------------------------------------------------
# create_job
# ---------------------------------------------------------------------------


class TestCreateJob:
    """Tests for BatchJobManager.create_job()."""

    def test_returns_uuid_string(self, app):
        import uuid

        mgr = batch_jobs.get_batch_manager()
        job_id = mgr.create_job("test_type", 1)
        uuid.UUID(job_id)  # raises ValueError if invalid

    def test_persists_to_db(self, app):
        mgr = batch_jobs.get_batch_manager()
        job_id = mgr.create_job("optimize", 1, {"resume_id": 42})
        rows = query_db("SELECT * FROM batch_jobs WHERE id = ?", (job_id,))
        assert len(rows) == 1
        assert rows[0]["job_type"] == "optimize"
        assert rows[0]["user_id"] == 1
        assert rows[0]["status"] == "pending"
        assert json.loads(rows[0]["params_json"]) == {"resume_id": 42}

    def test_default_params_empty_dict(self, app):
        mgr = batch_jobs.get_batch_manager()
        job_id = mgr.create_job("scan", 1)
        rows = query_db("SELECT params_json FROM batch_jobs WHERE id = ?", (job_id,))
        assert json.loads(rows[0]["params_json"]) == {}

    def test_created_at_populated(self, app):
        mgr = batch_jobs.get_batch_manager()
        job_id = mgr.create_job("test", 1)
        rows = query_db("SELECT created_at FROM batch_jobs WHERE id = ?", (job_id,))
        assert rows[0]["created_at"] is not None


# ---------------------------------------------------------------------------
# get_job
# ---------------------------------------------------------------------------


class TestGetJob:
    """Tests for BatchJobManager.get_job()."""

    def test_returns_dict_with_parsed_json(self, app):
        mgr = batch_jobs.get_batch_manager()
        job_id = mgr.create_job("test", 1, {"key": "value"})
        job = mgr.get_job(job_id)
        assert job is not None
        assert job["job_type"] == "test"
        assert isinstance(job["params_json"], dict)
        assert job["params_json"]["key"] == "value"

    def test_returns_none_for_nonexistent(self, app):
        mgr = batch_jobs.get_batch_manager()
        assert mgr.get_job("nonexistent-id") is None

    def test_status_is_pending(self, app):
        mgr = batch_jobs.get_batch_manager()
        job_id = mgr.create_job("test", 1)
        job = mgr.get_job(job_id)
        assert job["status"] == "pending"


# ---------------------------------------------------------------------------
# get_jobs_for_user
# ---------------------------------------------------------------------------


class TestGetJobsForUser:
    """Tests for BatchJobManager.get_jobs_for_user()."""

    def test_filters_by_user_id(self, app):
        mgr = batch_jobs.get_batch_manager()
        mgr.create_job("type1", 1)
        mgr.create_job("type1", 2)
        jobs = mgr.get_jobs_for_user(1)
        assert len(jobs) == 1
        assert jobs[0]["user_id"] == 1

    def test_filters_by_job_type(self, app):
        mgr = batch_jobs.get_batch_manager()
        mgr.create_job("typeA", 1)
        mgr.create_job("typeB", 1)
        jobs = mgr.get_jobs_for_user(1, job_type="typeA")
        assert len(jobs) == 1
        assert jobs[0]["job_type"] == "typeA"

    def test_respects_limit(self, app):
        mgr = batch_jobs.get_batch_manager()
        for _ in range(10):
            mgr.create_job("bulk", 1)
        jobs = mgr.get_jobs_for_user(1, limit=5)
        assert len(jobs) == 5


# ---------------------------------------------------------------------------
# complete_job / fail_job
# ---------------------------------------------------------------------------


class TestCompleteAndFail:
    """Tests for complete_job() and fail_job()."""

    def test_complete_sets_status_and_result(self, app):
        mgr = batch_jobs.get_batch_manager()
        job_id = mgr.create_job("test", 1)
        mgr.complete_job(job_id, {"output": "done"})
        rows = query_db("SELECT status, result_json FROM batch_jobs WHERE id = ?", (job_id,))
        assert rows[0]["status"] == "completed"
        assert json.loads(rows[0]["result_json"])["output"] == "done"

    def test_complete_sets_completed_at(self, app):
        mgr = batch_jobs.get_batch_manager()
        job_id = mgr.create_job("test", 1)
        mgr.complete_job(job_id, {})
        rows = query_db("SELECT completed_at FROM batch_jobs WHERE id = ?", (job_id,))
        assert rows[0]["completed_at"] is not None

    def test_fail_sets_status_and_error(self, app):
        mgr = batch_jobs.get_batch_manager()
        job_id = mgr.create_job("test", 1)
        mgr.fail_job(job_id, "Something went wrong")
        rows = query_db("SELECT status, error_message FROM batch_jobs WHERE id = ?", (job_id,))
        assert rows[0]["status"] == "failed"
        assert rows[0]["error_message"] == "Something went wrong"


# ---------------------------------------------------------------------------
# cancel_job
# ---------------------------------------------------------------------------


class TestCancelJob:
    """Tests for BatchJobManager.cancel_job()."""

    def test_cancel_sets_status(self, app):
        mgr = batch_jobs.get_batch_manager()
        job_id = mgr.create_job("test", 1)
        result = mgr.cancel_job(job_id)
        assert "message" in result
        rows = query_db("SELECT status FROM batch_jobs WHERE id = ?", (job_id,))
        assert rows[0]["status"] == "cancelled"

    def test_cancel_with_correct_user_id(self, app):
        mgr = batch_jobs.get_batch_manager()
        job_id = mgr.create_job("test", 1)
        result = mgr.cancel_job(job_id, user_id=1)
        assert "message" in result

    def test_cancel_with_wrong_user_id_returns_error(self, app):
        mgr = batch_jobs.get_batch_manager()
        job_id = mgr.create_job("test", 1)
        result = mgr.cancel_job(job_id, user_id=999)
        assert "error" in result

    def test_is_cancelled_true(self, app):
        mgr = batch_jobs.get_batch_manager()
        job_id = mgr.create_job("test", 1)
        mgr.cancel_job(job_id)
        assert mgr.is_cancelled(job_id) is True

    def test_is_cancelled_false_for_pending(self, app):
        mgr = batch_jobs.get_batch_manager()
        job_id = mgr.create_job("test", 1)
        assert mgr.is_cancelled(job_id) is False


# ---------------------------------------------------------------------------
# update_progress
# ---------------------------------------------------------------------------


class TestUpdateProgress:
    """Tests for BatchJobManager.update_progress()."""

    def test_stores_progress_dict(self, app):
        mgr = batch_jobs.get_batch_manager()
        job_id = mgr.create_job("test", 1)
        mgr.update_progress(job_id, {"pct": 50, "step": "parsing"})
        rows = query_db("SELECT progress_json FROM batch_jobs WHERE id = ?", (job_id,))
        progress = json.loads(rows[0]["progress_json"])
        assert progress["pct"] == 50
        assert progress["step"] == "parsing"


# ---------------------------------------------------------------------------
# start_job (threading)
# ---------------------------------------------------------------------------


class TestStartJob:
    """Tests for BatchJobManager.start_job() with threaded workers."""

    def test_successful_worker_completes_job(self, app):
        mgr = batch_jobs.get_batch_manager()
        job_id = mgr.create_job("test", 1)

        def worker(jid):
            return {"done": True}

        mgr.start_job(job_id, worker)
        mgr.shutdown(timeout=5)
        rows = query_db("SELECT status FROM batch_jobs WHERE id = ?", (job_id,))
        assert rows[0]["status"] == "completed"

    def test_failing_worker_fails_job(self, app):
        mgr = batch_jobs.get_batch_manager()
        job_id = mgr.create_job("test", 1)

        def worker(jid):
            raise RuntimeError("Worker crashed")

        mgr.start_job(job_id, worker)
        mgr.shutdown(timeout=5)
        rows = query_db("SELECT status, error_message FROM batch_jobs WHERE id = ?", (job_id,))
        assert rows[0]["status"] == "failed"
        assert "Worker crashed" in rows[0]["error_message"]

    def test_start_sets_running_status(self, app):
        mgr = batch_jobs.get_batch_manager()
        job_id = mgr.create_job("test", 1)

        def worker(jid):
            time.sleep(0.5)
            return {}

        mgr.start_job(job_id, worker)
        # Check running status before worker completes
        time.sleep(0.05)
        rows = query_db("SELECT status FROM batch_jobs WHERE id = ?", (job_id,))
        assert rows[0]["status"] == "running"
        mgr.shutdown(timeout=5)


# ---------------------------------------------------------------------------
# singleton pattern
# ---------------------------------------------------------------------------


class TestSingleton:
    """Tests for BatchJobManager singleton pattern."""

    def test_same_instance(self, app):
        batch_jobs.BatchJobManager._instance = None
        a = batch_jobs.BatchJobManager()
        b = batch_jobs.BatchJobManager()
        assert a is b

    def test_get_batch_manager_returns_instance(self, app):
        mgr = batch_jobs.get_batch_manager()
        assert isinstance(mgr, batch_jobs.BatchJobManager)


# ---------------------------------------------------------------------------
# _row_to_dict (module-level function)
# ---------------------------------------------------------------------------


class TestRowToDict:
    """Tests for the module-level _row_to_dict() function."""

    def test_parses_json_fields(self, app):
        mgr = batch_jobs.get_batch_manager()
        job_id = mgr.create_job("test", 1, {"key": "val"})
        mgr.update_progress(job_id, {"pct": 75})
        mgr.complete_job(job_id, {"result": "ok"})
        job = mgr.get_job(job_id)
        # _row_to_dict parses params_json, progress_json, result_json
        assert isinstance(job["params_json"], dict)
        assert job["params_json"]["key"] == "val"
        assert isinstance(job["progress_json"], dict)
        assert job["progress_json"]["pct"] == 75
        assert isinstance(job["result_json"], dict)
        assert job["result_json"]["result"] == "ok"
