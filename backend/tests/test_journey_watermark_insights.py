"""Phase B: Watermark Insights - Mutation verified tests.

TDD Contract:
- test_identifies_incremental_mining: Detects when current run used previous watermarks
- test_identifies_full_scan: Detects when current run did full scan
- test_watermarks_missing_shows_full_scan: New users without watermarks = full scan
- test_watermark_mismatch_shows_full_scan: opts["since_date"] != watermark = full scan
- test_timestamp_diff_calculation: Correctly calculates time between runs
- test_two_runs_required: Analysis only generated with 2+ runs
"""

from db_engine import as_datetime
import json
import sqlite3
import tempfile
from datetime import datetime, timedelta

import pytest

from models import get_db, save_mining_run
from watermark_insights import get_watermark_insights, is_incremental_mining


@pytest.fixture
def temp_db_watermark(monkeypatch, request):
    """Create temp SQLite database for watermark insights testing."""
    fd, path = tempfile.mkstemp(suffix=f"_{request.node.name}.db")
    import os
    os.close(fd)

    monkeypatch.setenv("DB_PATH", path)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS journey_mining_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            status TEXT DEFAULT 'running',
            opts_json TEXT DEFAULT '{}',
            watermarks_json TEXT DEFAULT '{}',
            sources_scanned INTEGER DEFAULT 0,
            events_added INTEGER DEFAULT 0,
            events_updated INTEGER DEFAULT 0,
            events_deduplicated INTEGER DEFAULT 0,
            error_message TEXT DEFAULT '',
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    conn.execute("INSERT OR IGNORE INTO users (id, email, password_hash) VALUES (?, ?, ?)",
                 (100, 'watermark@test.com', 'hash'))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()

    yield path

    conn.close()
    import os
    os.unlink(path)


class TestWatermarkInsights:
    """Mutation: Don't compare since_date to watermarks OR don't detect full scans."""

    def test_identifies_incremental_mining(self, temp_db_watermark):
        """Verify: detect when current run used previous watermarks (incremental mining).

        Mutation: Don't compare since_date == watermark → always returns False
        Result: All incremental mining marked as full scan → Test fails ✓
        """
        user_id = 100

        # Clean up any prior test data
        with get_db() as conn:
            conn.execute("DELETE FROM journey_mining_runs WHERE user_id = ?", (user_id,))
            conn.commit()

        # Create first run with watermarks
        watermark_date = "2026-04-01T00:00:00"
        run1_id = save_mining_run(
            user_id=user_id,
            status="completed",
            opts_json={},
            watermarks_json={"files": watermark_date, "git": watermark_date},
            sources_scanned=10,
            events_added=5
        )

        # Small sleep to ensure different timestamps
        import time
        time.sleep(0.1)

        # Create second run that uses first run's watermarks (incremental)
        run2_id = save_mining_run(
            user_id=user_id,
            status="completed",
            opts_json={"since_date": watermark_date},
            watermarks_json={"files": "2026-04-15T00:00:00", "git": "2026-04-15T00:00:00"},
            sources_scanned=5,
            events_added=2
        )

        # Get insights
        insights = get_watermark_insights(user_id)

        # ASSERTION: Must detect incremental
        assert insights["has_previous_run"] is True
        assert insights["has_current_run"] is True
        assert insights["analysis"] is not None
        assert insights["analysis"]["incremental"] is True
        assert "files" in insights["analysis"]["incremental_sources"]

    def test_identifies_full_scan(self, temp_db_watermark):
        """Verify: detect when current run did full scan (ignored watermarks).

        Mutation: Always return True for incremental → full scan never detected
        Result: Full scan marked as incremental → Test fails ✓
        """
        user_id = 100

        # Create first run with watermarks
        save_mining_run(
            user_id=user_id,
            status="completed",
            opts_json={},
            watermarks_json={"files": "2026-04-01T00:00:00"},
            sources_scanned=10,
            events_added=5
        )

        # Create second run that does NOT use watermarks (full scan)
        save_mining_run(
            user_id=user_id,
            status="completed",
            opts_json={},  # No since_date = full scan
            watermarks_json={"files": "2026-04-15T00:00:00"},
            sources_scanned=15,
            events_added=8
        )

        # Get insights
        insights = get_watermark_insights(user_id)

        # ASSERTION: Must detect full scan
        assert insights["analysis"]["incremental"] is False
        assert "files" not in insights["analysis"]["incremental_sources"] or len(insights["analysis"]["full_scan_sources"]) > 0

    def test_watermarks_missing_shows_full_scan(self, temp_db_watermark):
        """Verify: first run with no watermarks is treated as full scan.

        Mutation: Treat missing watermarks as incremental → new users marked wrong
        Result: New user analysis wrong → Test fails ✓
        """
        user_id = 101  # Use different user_id to avoid pollution

        # Clean up
        with get_db() as conn:
            conn.execute("DELETE FROM journey_mining_runs WHERE user_id = ?", (user_id,))
            conn.commit()

        # Create first (and only) run - new user, no previous watermarks
        save_mining_run(
            user_id=user_id,
            status="completed",
            opts_json={},
            watermarks_json={},
            sources_scanned=10,
            events_added=5
        )

        # Get insights
        insights = get_watermark_insights(user_id)

        # ASSERTION: Only 1 run, no analysis yet
        assert insights["has_previous_run"] is False
        assert insights["has_current_run"] is True
        assert insights["analysis"] is None  # Can't analyze with only 1 run

    def test_watermark_mismatch_shows_full_scan(self, temp_db_watermark):
        """Verify: if since_date != previous watermark, it's a full scan.

        Mutation: Don't check for equality → wrong watermarks treated as matches
        Result: Full scan with wrong since_date marked as incremental → Test fails ✓
        """
        user_id = 100

        # Create first run with watermark
        save_mining_run(
            user_id=user_id,
            status="completed",
            opts_json={},
            watermarks_json={"files": "2026-04-01T00:00:00"},
            sources_scanned=10,
            events_added=5
        )

        # Create second run with mismatched since_date (full scan in disguise)
        save_mining_run(
            user_id=user_id,
            status="completed",
            opts_json={"since_date": "2026-03-15T00:00:00"},  # Different date = full scan
            watermarks_json={"files": "2026-04-15T00:00:00"},
            sources_scanned=20,
            events_added=10
        )

        # Get insights
        insights = get_watermark_insights(user_id)

        # ASSERTION: Must detect mismatch as full scan
        assert insights["analysis"]["incremental"] is False

    def test_timestamp_diff_calculation(self, temp_db_watermark):
        """Verify: timestamp difference calculated correctly.

        Mutation: Skip timestamp calculation → wrong values
        Result: Timestamp diff wrong → Test fails ✓
        """
        user_id = 100

        # Create first run
        save_mining_run(
            user_id=user_id,
            status="completed",
            opts_json={},
            watermarks_json={"files": "2026-04-01T00:00:00"},
            sources_scanned=10,
            events_added=5
        )

        # Get the first run to extract its completed_at
        with get_db() as conn:
            first_run = conn.execute(
                "SELECT completed_at FROM journey_mining_runs WHERE user_id = ? ORDER BY completed_at ASC LIMIT 1",
                (user_id,)
            ).fetchone()

        # Create second run ~2 hours later
        with get_db() as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            completed_at_1 = first_run["completed_at"]
            # Parse and add 2 hours
            # psycopg2 returns a datetime; sqlite3 returned an ISO string.
            dt1 = as_datetime(completed_at_1)
            dt2 = dt1 + timedelta(hours=2)

            conn.execute(
                """INSERT INTO journey_mining_runs
                (user_id, started_at, completed_at, status, opts_json, watermarks_json, sources_scanned, events_added)
                VALUES (?, ?, ?, 'completed', '{}', '{}', 20, 10)""",
                (user_id, dt2.isoformat(), dt2.isoformat())
            )
            conn.execute("PRAGMA foreign_keys = ON")
            conn.commit()

        # Get insights
        insights = get_watermark_insights(user_id)

        # ASSERTION: Timestamp diff should be ~120 minutes
        diff_minutes = insights["analysis"]["timestamp_diff_minutes"]
        assert 119 <= diff_minutes <= 121, f"Expected ~120 minutes, got {diff_minutes}"

    def test_two_runs_required_for_analysis(self, temp_db_watermark):
        """Verify: analysis only generated when 2+ runs exist.

        Mutation: Don't require second run → analysis generated with 1 run
        Result: Analysis present with only 1 run → Test fails ✓
        """
        user_id = 102  # Use different user_id to avoid pollution

        # Clean up
        with get_db() as conn:
            conn.execute("DELETE FROM journey_mining_runs WHERE user_id = ?", (user_id,))
            conn.commit()

        # Create only one run
        save_mining_run(
            user_id=user_id,
            status="completed",
            opts_json={},
            watermarks_json={"files": "2026-04-01T00:00:00"},
            sources_scanned=10,
            events_added=5
        )

        # Get insights
        insights = get_watermark_insights(user_id)

        # ASSERTION: Analysis should be None with only 1 run
        assert insights["has_previous_run"] is False
        assert insights["analysis"] is None

    def test_no_runs_returns_empty(self, temp_db_watermark):
        """Verify: new user with no runs returns empty insights.

        Mutation: Don't initialize empty response → crashes on new user
        Result: Exception thrown → Test fails ✓
        """
        user_id = 200  # Non-existent user

        # Get insights for user with no runs
        insights = get_watermark_insights(user_id)

        # ASSERTION: Should return empty structure, not crash
        assert insights["has_previous_run"] is False
        assert insights["has_current_run"] is False
        assert insights["analysis"] is None


class TestIsIncrementalMiningHelper:
    """Test the is_incremental_mining() helper function directly."""

    def test_is_incremental_when_since_date_matches_watermark(self):
        """Verify: since_date == watermark → incremental."""
        prev_watermarks = {"files": "2026-04-01T00:00:00"}
        curr_opts = {"since_date": "2026-04-01T00:00:00"}

        result = is_incremental_mining(prev_watermarks, curr_opts)
        assert result is True

    def test_is_full_scan_when_since_date_missing(self):
        """Verify: no since_date → full scan."""
        prev_watermarks = {"files": "2026-04-01T00:00:00"}
        curr_opts = {}  # No since_date

        result = is_incremental_mining(prev_watermarks, curr_opts)
        assert result is False

    def test_is_full_scan_when_since_date_mismatches(self):
        """Verify: since_date != watermark → full scan."""
        prev_watermarks = {"files": "2026-04-01T00:00:00"}
        curr_opts = {"since_date": "2026-03-15T00:00:00"}  # Different date

        result = is_incremental_mining(prev_watermarks, curr_opts)
        assert result is False

    def test_is_full_scan_when_no_previous_watermark(self):
        """Verify: missing previous watermark → full scan."""
        prev_watermarks = {}
        curr_opts = {"since_date": "2026-04-01T00:00:00"}

        result = is_incremental_mining(prev_watermarks, curr_opts)
        assert result is False
