"""Option C1: audit_events table + log_audit_event() fire-and-forget helper.

Tests verify: table created by init_db, row inserted by log_audit_event,
NULL user_id accepted, caller does not block, never raises on DB error.
"""

import sqlite3
import time
from unittest.mock import patch

import pytest
import models
from models import get_db, init_db, log_audit_event
from models_schema1 import _init_schema_part1
from models_schema2 import (
    _init_schema_final,
    _init_schema_part2,
    _init_schema_part3,
    _run_migrations,
)


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
    """Verify: init_db schema creates the audit_events table."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    _init_schema_part1(cursor)
    _init_schema_part2(cursor)
    _run_migrations(cursor)
    _init_schema_part3(cursor)
    _init_schema_final(cursor)
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    assert "audit_events" in tables


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


def test_log_audit_event_never_raises():
    """Verify: log_audit_event() does not raise even when the DB call fails."""
    with patch("models.get_db", side_effect=Exception("simulated DB failure")):
        # Must not raise — exception is swallowed inside the daemon thread
        log_audit_event(1, "should_not_raise")
    # Allow thread to complete its error path
    time.sleep(0.05)
