"""Option C1: audit_events table + log_audit_event() fire-and-forget helper.

Tests verify: table created by init_db, row inserted by log_audit_event,
NULL user_id accepted, caller does not block, never raises on DB error.
"""

import time

import pytest
import models
from models import get_db, init_db, log_audit_event


@pytest.fixture(autouse=True)
def _ensure_schema():
    """Re-run init_db() so audit_events table always exists.

    The conftest app fixture patches models.DB_PATH to a temp file and then
    deletes it at teardown without restoring DB_PATH. Any subsequent test that
    accesses models.DB_PATH directly would connect to a fresh empty database
    that has no tables. Calling init_db() here ensures the schema is always
    present regardless of which DB_PATH was left behind by prior fixtures.
    """
    init_db()


def test_audit_events_table_exists():
    """Verify the initialised schema exposes audit_events with the columns
    log_audit_event() writes. The old version built an in-memory SQLite database
    from schema helpers that no longer exist; this app is PostgreSQL-only."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = %s",
            ("audit_events",),
        )
        assert cursor.fetchone(), "schema is missing the audit_events table"

        cursor.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s",
            ("audit_events",),
        )
        columns = {row[0] for row in cursor.fetchall()}
        # A table that exists with the wrong shape would otherwise pass.
        required = {"user_id", "event_type", "created_at"}
        assert required.issubset(columns), (
            f"audit_events is missing columns: {sorted(required - columns)}"
        )


def test_log_audit_event_inserts_row():
    """Verify: log_audit_event() inserts a row into audit_events."""
    # Clean slate so stale rows from previous runs can't cause false positives
    with get_db() as conn:
        conn.execute("DELETE FROM audit_events WHERE event_type = 'c1_test_insert'")
        conn.commit()
    log_audit_event(42, "c1_test_insert", "resume", "res_99", {"action": "created"})
    time.sleep(0.1)  # let daemon thread complete
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_events WHERE event_type = ? AND user_id = ?",
            ("c1_test_insert", 42),
        ).fetchall()
    assert len(rows) == 1
    assert rows[0]["resource_type"] == "resume"


def test_log_audit_event_accepts_null_user_id():
    """Verify: NULL user_id is accepted — no FK violation."""
    with get_db() as conn:
        conn.execute("DELETE FROM audit_events WHERE event_type = 'c1_null_user_event'")
        conn.commit()
    log_audit_event(None, "c1_null_user_event", "system")
    time.sleep(0.1)
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_events WHERE event_type = ? AND user_id IS NULL",
            ("c1_null_user_event",),
        ).fetchall()
    assert len(rows) == 1


def test_log_audit_event_does_not_block():
    """Verify: log_audit_event() returns immediately (fire-and-forget, not blocking)."""
    start = time.time()
    log_audit_event(1, "timing_test")
    elapsed = time.time() - start
    assert elapsed < 0.1, f"log_audit_event blocked for {elapsed:.3f}s"


def test_log_audit_event_never_raises(monkeypatch):
    """Verify: log_audit_event() does not raise even when the DB call fails."""
    def _boom(*args, **kwargs):
        raise Exception("simulated DB failure")

    # Explicit stub rather than patch(): the failure it injects is visible here.
    monkeypatch.setattr("models.get_db", _boom)
    # Must not raise — exception is swallowed inside the daemon thread
    log_audit_event(1, "should_not_raise")
    # Allow thread to complete its error path
    time.sleep(0.05)
