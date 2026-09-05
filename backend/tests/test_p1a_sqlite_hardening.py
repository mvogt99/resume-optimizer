"""P1-A tests: Postgres-only architecture conformance + concurrency safety.

Originally a SQLite-hardening suite (WAL mode, busy_timeout PRAGMAs). Postgres
is now the sole database backend — those PRAGMA-specific assertions have no
Postgres equivalent and were retired. What's kept/replaced:
  - The "no raw DB bypass" architecture audit (broadened: any production file
    importing sqlite3 directly is a bug now, not just a DB_PATH connect call).
  - The concurrent-write safety property, reimplemented against real Postgres.
"""

import os
import threading
import uuid
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# P1-A.2: grep-based audit — zero sqlite3 usage in production code
# ---------------------------------------------------------------------------

# Intentionally-local SQLite stores, outside the shared Postgres app schema —
# not part of this audit (separate queue/cost-tracking DBs, not request-path data).
_ALLOWED_SQLITE_FILES = {
    "agents/claim_recorder.py",
    "journey_miner_enrichment_mixin.py",
    # One-time SQLite -> Postgres data migration tool — legitimately reads
    # the archived SQLite source file, not part of the live request path.
    "migrate_sqlite_to_postgres.py",
}
# Directories not part of the live application (tests, one-off scripts, migrations).
_EXCLUDED_DIRS = {"tests", "migrations", "__pycache__", ".venv"}


def _production_py_files():
    for path in BACKEND_DIR.rglob("*.py"):
        rel = path.relative_to(BACKEND_DIR)
        if any(part in _EXCLUDED_DIRS for part in rel.parts):
            continue
        if str(rel) in _ALLOWED_SQLITE_FILES:
            continue
        yield rel


class TestNoRawSqliteUsage:
    def test_no_sqlite3_import_in_production_code(self):
        """No production file should import sqlite3 — Postgres is the only backend."""
        offenders = []
        for rel in _production_py_files():
            content = (BACKEND_DIR / rel).read_text()
            if "import sqlite3" in content:
                offenders.append(str(rel))
        assert not offenders, (
            f"{len(offenders)} production file(s) still import sqlite3 "
            f"(Postgres is the only supported backend):\n" + "\n".join(offenders[:10])
        )


# ---------------------------------------------------------------------------
# P1-A.3: Concurrent write stress test — Postgres
# ---------------------------------------------------------------------------


class TestConcurrentWrites:
    def test_concurrent_inserts_no_data_loss(self, app):
        """4 threads x 50 inserts = 200 rows, no errors, no lost writes."""
        from models import get_db, get_db_connection

        with get_db() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS stress_test "
                "(id SERIAL PRIMARY KEY, val TEXT)"
            )
            conn.commit()

        errors = []
        THREADS = 4
        ROWS_PER_THREAD = 50

        def insert_rows(thread_id):
            try:
                conn = get_db_connection()
                for i in range(ROWS_PER_THREAD):
                    conn.execute(
                        "INSERT INTO stress_test (val) VALUES (?)",
                        (f"thread-{thread_id}-row-{i}",),
                    )
                    conn.commit()
                conn.close()
            except Exception as e:  # noqa: BLE001
                errors.append(str(e))

        threads = [threading.Thread(target=insert_rows, args=(t,)) for t in range(THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors, f"Concurrent insert errors: {errors}"

        with get_db() as conn:
            count = conn.execute("SELECT COUNT(*) FROM stress_test").fetchone()[0]

        assert (
            count == THREADS * ROWS_PER_THREAD
        ), f"Expected {THREADS * ROWS_PER_THREAD} rows, got {count}"

    def test_concurrent_reads_during_write_no_error(self, app):
        """Readers proceed concurrently with a writer without error."""
        from models import get_db, get_db_connection

        with get_db() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS read_test (id SERIAL PRIMARY KEY, val INTEGER)"
            )
            for i in range(20):
                conn.execute("INSERT INTO read_test (val) VALUES (?)", (i,))
            conn.commit()

        read_errors = []

        def reader():
            try:
                conn = get_db_connection()
                for _ in range(10):
                    conn.execute("SELECT COUNT(*) FROM read_test").fetchone()
                conn.close()
            except Exception as e:  # noqa: BLE001
                read_errors.append(str(e))

        def writer():
            conn = get_db_connection()
            for i in range(20, 40):
                conn.execute("INSERT INTO read_test (val) VALUES (?)", (i,))
                conn.commit()
            conn.close()

        threads = [threading.Thread(target=reader) for _ in range(3)]
        threads.append(threading.Thread(target=writer))
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not read_errors, f"Reader errors during concurrent write: {read_errors}"
