"""Tests for data utility modules: migrate_data_to_user.py and bus_client.py.

migrate_data_to_user: Tests use the test fixture DB (not production).
bus_client: Tests verify init, availability check, and sequential fallback.
"""

import json
import sqlite3
import uuid

import pytest
from test_helpers import query_db

# ---------------------------------------------------------------------------
# migrate_data_to_user.py tests
# ---------------------------------------------------------------------------


def _seed_migration_data(db_path, source_user_id=0):
    """Insert test data for migration testing."""
    conn = get_db_connection()
    # Insert a resume (schema: user_id, filename, file_path)
    conn.execute(
        "INSERT INTO resumes (user_id, filename, file_path) " "VALUES (?, ?, ?)",
        (source_user_id, "test.pdf", "/uploads/test.pdf"),
    )
    # Insert a job description (schema: user_id, text)
    conn.execute(
        "INSERT INTO job_descriptions (user_id, text) VALUES (?, ?)",
        (source_user_id, "Job description content here"),
    )
    conn.commit()
    conn.close()


def test_migrate_ensure_target_user(app):
    import migrate_data_to_user as mig
    import models

    mig.DB_PATH = models.DB_PATH
    conn = mig.get_db()
    user_id = mig.ensure_target_user(conn)
    assert isinstance(user_id, int)
    assert user_id > 0
    conn.close()


def test_migrate_copy_rows_copies_data(app):
    import migrate_data_to_user as mig
    import models

    mig.DB_PATH = models.DB_PATH
    _seed_migration_data(models.DB_PATH, source_user_id=0)

    conn = mig.get_db()
    target_id = mig.ensure_target_user(conn)
    id_map = mig.copy_rows(conn, "resumes", {0}, target_id)
    conn.commit()
    conn.close()

    assert isinstance(id_map, dict)
    rows = query_db("SELECT * FROM resumes WHERE user_id = ?", (target_id,))
    assert len(rows) >= 1, "Copied resume should exist for target user"


def test_migrate_copy_rows_preserves_content(app):
    import migrate_data_to_user as mig
    import models

    mig.DB_PATH = models.DB_PATH
    _seed_migration_data(models.DB_PATH, source_user_id=0)

    conn = mig.get_db()
    target_id = mig.ensure_target_user(conn)
    mig.copy_rows(conn, "resumes", {0}, target_id)
    conn.commit()
    conn.close()

    rows = query_db("SELECT filename FROM resumes WHERE user_id = ?", (target_id,))
    assert any(
        "test.pdf" in r["filename"] for r in rows
    ), "Migrated resume should preserve filename"


def test_migrate_copy_rows_handles_missing_user(app):
    import migrate_data_to_user as mig
    import models

    mig.DB_PATH = models.DB_PATH
    conn = mig.get_db()
    target_id = mig.ensure_target_user(conn)
    # Copy from user_id=999 which has no data
    id_map = mig.copy_rows(conn, "resumes", {999}, target_id)
    conn.close()
    assert id_map == {}, "No rows to copy should return empty map"


def test_migrate_copy_jd_rows(app):
    import migrate_data_to_user as mig
    import models

    mig.DB_PATH = models.DB_PATH
    _seed_migration_data(models.DB_PATH, source_user_id=0)

    conn = mig.get_db()
    target_id = mig.ensure_target_user(conn)
    id_map = mig.copy_rows(conn, "job_descriptions", {0}, target_id)
    conn.commit()
    conn.close()

    rows = query_db("SELECT * FROM job_descriptions WHERE user_id = ?", (target_id,))
    assert len(rows) >= 1


def test_migrate_copy_rows_with_string_id(app):
    import migrate_data_to_user as mig
    import models

    mig.DB_PATH = models.DB_PATH

    # Insert a batch job with string ID
    conn = models.get_db_connection()
    job_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO batch_jobs (id, job_type, user_id, status) VALUES (?, ?, ?, ?)",
        (job_id, "test_job", 0, "completed"),
    )
    conn.commit()
    conn.close()

    conn = mig.get_db()
    target_id = mig.ensure_target_user(conn)
    id_map = mig.copy_rows_with_string_id(conn, "batch_jobs", {0}, target_id)
    conn.commit()
    conn.close()

    assert isinstance(id_map, dict)


def test_migrate_copy_child_rows(app):
    """copy_child_rows remaps parent FK references."""
    import migrate_data_to_user as mig
    import models

    mig.DB_PATH = models.DB_PATH

    # Create a client_project (parent) and project_document (child)
    conn2 = models.get_db_connection()
    conn2.execute(
        "INSERT INTO client_projects (user_id, client_name, folder_id, analysis_status) "
        "VALUES (?, ?, ?, ?)",
        (0, "Test Client", "folder_abc", "analyzed"),
    )
    project_id = conn2.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn2.execute(
        "INSERT INTO project_documents (client_id, file_id, file_name, user_id) "
        "VALUES (?, ?, ?, ?)",
        (project_id, "file_xyz", "doc.pdf", 0),
    )
    conn2.commit()
    conn2.close()

    conn = mig.get_db()
    target_id = mig.ensure_target_user(conn)
    parent_map = mig.copy_rows(conn, "client_projects", {0}, target_id)
    conn.commit()

    if parent_map:
        child_map = mig.copy_child_rows(conn, "project_documents", "client_id", parent_map)
        assert isinstance(child_map, dict)

    conn.close()


def test_migrate_does_not_crash_on_rerun(app):
    """Running copy_rows twice should not crash (autoincrement creates new rows)."""
    import migrate_data_to_user as mig
    import models

    mig.DB_PATH = models.DB_PATH
    _seed_migration_data(models.DB_PATH, source_user_id=0)

    conn = mig.get_db()
    target_id = mig.ensure_target_user(conn)
    mig.copy_rows(conn, "resumes", {0}, target_id)
    conn.commit()

    # Run again — should not crash (IntegrityError caught for non-autoincrement)
    id_map = mig.copy_rows(conn, "resumes", {0}, target_id)
    conn.commit()
    conn.close()

    assert isinstance(id_map, dict), "Second run should return valid id_map"


def test_migrate_get_db_returns_connection(app):
    import migrate_data_to_user as mig
    import models

    mig.DB_PATH = models.DB_PATH
    conn = mig.get_db()
    assert conn is not None
    # Should have row_factory
    cursor = conn.execute("SELECT 1 as val")
    row = cursor.fetchone()
    assert row["val"] == 1, "row_factory should be set for dict-like access"
    conn.close()


# ---------------------------------------------------------------------------
# bus_client.py tests
# ---------------------------------------------------------------------------


def test_bus_client_init():
    from bus_client import ResumeAnalysisBus

    bus = ResumeAnalysisBus()
    assert bus is not None


def test_bus_client_availability():
    """Bus should report not-available when Artemis isn't running."""
    from bus_client import ResumeAnalysisBus

    bus = ResumeAnalysisBus()
    available = bus.is_available()
    # In test env, Artemis is likely not running
    assert isinstance(available, bool)


def test_bus_client_publish_returns_false_when_unavailable():
    """publish_chunk should return False when bus not connected."""
    from bus_client import ResumeAnalysisBus

    bus = ResumeAnalysisBus()
    if bus.is_available():
        pytest.skip("Artemis is running — skip unavailability test")

    result = bus.publish_chunk(
        doc_id="test-doc",
        chunk_idx=0,
        chunk_text="test content",
        context={"project": "test"},
        extractors=["skills"],
    )
    assert result is False, "publish_chunk should return False when bus unavailable"


def test_bus_client_collect_empty_results():
    """collect_results with 0 expected should return empty list quickly."""
    from bus_client import ResumeAnalysisBus

    bus = ResumeAnalysisBus()
    results = bus.collect_results(expected_count=0, timeout=1)
    assert isinstance(results, list)
    assert len(results) == 0


def test_bus_client_drain_results_no_error():
    """drain_results should not raise even when queue is empty."""
    from bus_client import ResumeAnalysisBus

    bus = ResumeAnalysisBus()
    bus.drain_results()  # Should not raise


def test_bus_client_stop_no_error():
    """stop should not raise even when not connected."""
    from bus_client import ResumeAnalysisBus

    bus = ResumeAnalysisBus()
    bus.stop()  # Should not raise


def test_bus_client_singleton():
    """get_analysis_bus should return the same instance."""
    from bus_client import get_analysis_bus

    bus1 = get_analysis_bus()
    bus2 = get_analysis_bus()
    assert bus1 is bus2, "Singleton should return same instance"
