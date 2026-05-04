"""Phase P1-A tests: SQLite hardening — WAL mode, busy_timeout, get_db() adoption."""

import sqlite3
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# Backend dir on path (set by pytest.ini)
BACKEND_DIR = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# P1-A.1: WAL mode and busy_timeout
# ---------------------------------------------------------------------------


class TestWalMode:
    def test_init_db_enables_wal_mode(self):
        """WAL mode is active on the database after init_db()."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        with patch("models.DB_PATH", db_path):
            from models import init_db

            init_db()

        conn = sqlite3.connect(db_path)
        row = conn.execute("PRAGMA journal_mode").fetchone()
        conn.close()
        assert row[0] == "wal", f"Expected wal, got {row[0]}"

    def test_get_db_sets_busy_timeout(self):
        """Every get_db() connection has busy_timeout=5000ms."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        with patch("models.DB_PATH", db_path), patch("models.is_postgres", return_value=False):
            from models import get_db

            with get_db() as conn:
                row = conn.execute("PRAGMA busy_timeout").fetchone()
                timeout_ms = row[0]

        assert timeout_ms == 5000, f"Expected 5000ms busy_timeout, got {timeout_ms}"

    def test_get_db_sets_wal_mode(self):
        """get_db() enables WAL mode on each connection."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        with patch("models.DB_PATH", db_path), patch("models.is_postgres", return_value=False):
            from models import get_db

            with get_db() as conn:
                row = conn.execute("PRAGMA journal_mode").fetchone()
                mode = row[0]

        assert mode == "wal"

    def test_get_db_enables_foreign_keys(self):
        """get_db() enables foreign key enforcement."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        with patch("models.DB_PATH", db_path), patch("models.is_postgres", return_value=False):
            from models import get_db

            with get_db() as conn:
                row = conn.execute("PRAGMA foreign_keys").fetchone()
                fk_enabled = row[0]

        assert fk_enabled == 1


# ---------------------------------------------------------------------------
# P1-A.2: grep-based audit — zero raw sqlite3.connect(DB_PATH) in target files
# ---------------------------------------------------------------------------

TARGET_FILES = [
    "context_enrichment.py",
    "journey_synthesizer.py",
    "deep_profile.py",
    "campaign_interview.py",
    "post_generator.py",
    "experience_chat.py",
    "agents/cover_letter.py",
    "agents/career_advisor.py",
    "agents/interview_coach.py",
]


class TestNoRawConnections:
    @pytest.mark.parametrize("rel_path", TARGET_FILES)
    def test_no_raw_connect_in_file(self, rel_path):
        """Target file must not contain raw sqlite3.connect(DB_PATH) calls."""
        file_path = BACKEND_DIR / rel_path
        if not file_path.exists():
            pytest.skip(f"{rel_path} does not exist")

        content = file_path.read_text()
        raw_calls = [
            line.strip()
            for i, line in enumerate(content.splitlines(), 1)
            if "sqlite3.connect(DB_PATH)" in line and "# legacy" not in line.lower()
        ]
        assert not raw_calls, (
            f"{rel_path} still has {len(raw_calls)} raw sqlite3.connect(DB_PATH) call(s):\n"
            + "\n".join(raw_calls[:5])
        )


# ---------------------------------------------------------------------------
# P1-A.3: Concurrent write stress test
# ---------------------------------------------------------------------------


class TestConcurrentWrites:
    def test_concurrent_inserts_no_data_loss(self):
        """4 threads × 50 inserts = 200 rows, no errors, WAL handles contention."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        # Set up table in WAL mode
        setup_conn = sqlite3.connect(db_path)
        setup_conn.execute("PRAGMA journal_mode=WAL")
        setup_conn.execute("PRAGMA busy_timeout=5000")
        setup_conn.execute(
            "CREATE TABLE stress_test (id INTEGER PRIMARY KEY AUTOINCREMENT, val TEXT)"
        )
        setup_conn.commit()
        setup_conn.close()

        errors = []
        THREADS = 4
        ROWS_PER_THREAD = 50

        def insert_rows(thread_id):
            try:
                conn = sqlite3.connect(db_path, timeout=5.0)
                conn.execute("PRAGMA busy_timeout=5000")
                for i in range(ROWS_PER_THREAD):
                    conn.execute(
                        "INSERT INTO stress_test (val) VALUES (?)",
                        (f"thread-{thread_id}-row-{i}",),
                    )
                    conn.commit()
                conn.close()
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=insert_rows, args=(t,)) for t in range(THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors, f"Concurrent insert errors: {errors}"

        verify_conn = sqlite3.connect(db_path)
        count = verify_conn.execute("SELECT COUNT(*) FROM stress_test").fetchone()[0]
        verify_conn.close()

        assert (
            count == THREADS * ROWS_PER_THREAD
        ), f"Expected {THREADS * ROWS_PER_THREAD} rows, got {count}"

    def test_concurrent_reads_during_write_no_error(self):
        """Readers can proceed concurrently with a writer under WAL mode."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        setup_conn = sqlite3.connect(db_path)
        setup_conn.execute("PRAGMA journal_mode=WAL")
        setup_conn.execute(
            "CREATE TABLE read_test (id INTEGER PRIMARY KEY AUTOINCREMENT, val INTEGER)"
        )
        for i in range(20):
            setup_conn.execute("INSERT INTO read_test (val) VALUES (?)", (i,))
        setup_conn.commit()
        setup_conn.close()

        read_errors = []

        def reader():
            try:
                conn = sqlite3.connect(db_path, timeout=5.0)
                conn.execute("PRAGMA busy_timeout=5000")
                for _ in range(10):
                    conn.execute("SELECT COUNT(*) FROM read_test").fetchone()
                    time.sleep(0.01)
                conn.close()
            except Exception as e:
                read_errors.append(str(e))

        def writer():
            conn = sqlite3.connect(db_path, timeout=5.0)
            conn.execute("PRAGMA busy_timeout=5000")
            for i in range(20, 40):
                conn.execute("INSERT INTO read_test (val) VALUES (?)", (i,))
                conn.commit()
                time.sleep(0.005)
            conn.close()

        threads = [threading.Thread(target=reader) for _ in range(3)]
        threads.append(threading.Thread(target=writer))
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not read_errors, f"Reader errors during concurrent write: {read_errors}"
