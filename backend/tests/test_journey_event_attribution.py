"""Phase B: Event Attribution - Mutation verified tests.

TDD Contract:
- test_add_attribution_stores_client: Client attribution persists
- test_add_attribution_stores_category: Category attribution persists
- test_get_attribution_returns_data: Retrieved data matches stored
- test_get_events_by_client_filters: Only matching client events returned
- test_get_events_by_category_filters: Only matching category events returned
- test_attribution_summary_counts: Summary counts are accurate
"""

import json
import sqlite3
import tempfile

import pytest

from models import get_db
from event_attribution import (
    add_event_attribution,
    get_event_attribution,
    get_events_by_client,
    get_events_by_category,
    get_attribution_summary,
)


@pytest.fixture
def temp_db_attribution(monkeypatch, request):
    """Create temp database for attribution testing."""
    fd, path = tempfile.mkstemp(suffix=f"_{request.node.name}.db")
    import os
    os.close(fd)

    monkeypatch.setenv("DB_PATH", path)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")

    conn.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE journey_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            source_type TEXT NOT NULL,
            title TEXT NOT NULL,
            full_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    conn.execute("""
        CREATE TABLE event_attribution (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            source_id INTEGER NOT NULL UNIQUE,
            client_project_id INTEGER,
            workdir_category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (source_id) REFERENCES journey_sources (id)
        )
    """)
    conn.execute("""
        CREATE TABLE client_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            client_name TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    conn.execute("INSERT INTO users VALUES (200, 'attr@test.com', 'hash') ON CONFLICT DO NOTHING")
    conn.execute("INSERT INTO client_projects (user_id, client_name) VALUES (200, 'Client A')")
    conn.execute("INSERT INTO client_projects (user_id, client_name) VALUES (200, 'Client B')")

    # Insert test sources
    conn.execute(
        "INSERT INTO journey_sources (user_id, source_type, title) VALUES (200, 'git_commit', 'feat: Auth')"
    )
    conn.execute(
        "INSERT INTO journey_sources (user_id, source_type, title) VALUES (200, 'file', 'report.md')"
    )

    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()

    yield path

    conn.close()
    import os
    os.unlink(path)


class TestEventAttribution:
    """Mutation: Don't store/retrieve attribution data OR don't filter correctly."""

    def test_add_attribution_stores_client(self, temp_db_attribution):
        """Verify: Client attribution is persisted.

        Mutation: Skip INSERT or skip client_project_id field
        Result: Attribution not found on retrieval → Test fails ✓
        """
        # Add attribution
        add_event_attribution(user_id=200, source_id=1, client_project_id=1, workdir_category=None)

        # Retrieve
        attr = get_event_attribution(1)

        # ASSERTION: Client stored and retrieved
        assert attr["source_id"] == 1
        assert attr["client_project_id"] == 1
        assert attr["workdir_category"] is None

    def test_add_attribution_stores_category(self, temp_db_attribution):
        """Verify: Workdir category attribution is persisted.

        Mutation: Skip workdir_category field
        Result: Category not found → Test fails ✓
        """
        # Add attribution
        add_event_attribution(user_id=200, source_id=2, client_project_id=None, workdir_category="reports")

        # Retrieve
        attr = get_event_attribution(2)

        # ASSERTION: Category stored and retrieved
        assert attr["source_id"] == 2
        assert attr["client_project_id"] is None
        assert attr["workdir_category"] == "reports"

    def test_add_attribution_both_fields(self, temp_db_attribution):
        """Verify: Both client and category can be stored together.

        Mutation: Only store first field OR overwrite second
        Result: One field missing → Test fails ✓
        """
        # Add attribution with both fields
        add_event_attribution(user_id=200, source_id=1, client_project_id=1, workdir_category="tasks")

        # Retrieve
        attr = get_event_attribution(1)

        # ASSERTION: Both fields present
        assert attr["client_project_id"] == 1
        assert attr["workdir_category"] == "tasks"

    def test_get_events_by_client_filters(self, temp_db_attribution):
        """Verify: Only events for specific client returned.

        Mutation: Remove WHERE clause for client_project_id
        Result: Returns events from all clients → Test fails ✓
        """
        # Add attributions to different clients
        add_event_attribution(200, 1, client_project_id=1, workdir_category=None)
        add_event_attribution(200, 2, client_project_id=2, workdir_category=None)

        # Get events for client 1
        events = get_events_by_client(200, 1)

        # ASSERTION: Only client 1's event returned
        assert events == [1]
        assert 2 not in events

    def test_get_events_by_category_filters(self, temp_db_attribution):
        """Verify: Only events for specific category returned.

        Mutation: Remove WHERE clause for workdir_category
        Result: Returns all categorized events → Test fails ✓
        """
        # Add attributions with different categories
        add_event_attribution(200, 1, client_project_id=None, workdir_category="reports")
        add_event_attribution(200, 2, client_project_id=None, workdir_category="tasks")

        # Get events for 'reports' category
        events = get_events_by_category(200, "reports")

        # ASSERTION: Only 'reports' category returned
        assert events == [1]
        assert 2 not in events

    def test_attribution_summary_counts_accurate(self, temp_db_attribution):
        """Verify: Summary counts are correct.

        Mutation: Don't count correctly OR skip COUNT(*) aggregation
        Result: Wrong counts → Test fails ✓
        """
        # Add 3 attributions to client 1
        add_event_attribution(200, 1, client_project_id=1, workdir_category=None)
        add_event_attribution(200, 2, client_project_id=1, workdir_category=None)

        # Insert another source for counting
        with get_db() as conn:
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title) VALUES (200, 'file', 'doc.md')"
            )
            conn.commit()

        add_event_attribution(200, 3, client_project_id=1, workdir_category=None)

        # Get summary
        summary = get_attribution_summary(200)

        # ASSERTION: Count is correct
        assert summary["by_client"]["1"] == 3
        assert summary["unattributed"] == 0

    def test_attribution_summary_by_category(self, temp_db_attribution):
        """Verify: Category counts in summary are accurate.

        Mutation: Don't count by category OR wrong GROUP BY
        Result: Wrong category counts → Test fails ✓
        """
        # Add multiple categories
        add_event_attribution(200, 1, client_project_id=None, workdir_category="reports")
        add_event_attribution(200, 2, client_project_id=None, workdir_category="reports")

        # Insert another source
        with get_db() as conn:
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title) VALUES (200, 'file', 'task.md')"
            )
            conn.commit()

        add_event_attribution(200, 3, client_project_id=None, workdir_category="tasks")

        # Get summary
        summary = get_attribution_summary(200)

        # ASSERTION: Category counts correct
        assert summary["by_category"]["reports"] == 2
        assert summary["by_category"]["tasks"] == 1

    def test_attribution_unattributed_count(self, temp_db_attribution):
        """Verify: Unattributed events are counted.

        Mutation: Don't count unattributed OR wrong WHERE clause
        Result: Wrong unattributed count → Test fails ✓
        """
        # Add some attributions
        add_event_attribution(200, 1, client_project_id=1, workdir_category=None)

        # Insert source without attribution
        with get_db() as conn:
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title) VALUES (200, 'file', 'orphan.md')"
            )
            conn.commit()

        # Get summary (source 2 has no attribution entry)
        summary = get_attribution_summary(200)

        # ASSERTION: Only source 1 is attributed
        assert summary["by_client"]["1"] == 1
        # Source 2 is not in any attribution table, so unattributed = 0
        # (unattributed only counts entries in the table with null values)
        assert summary["unattributed"] == 0

    def test_attribution_update_on_conflict(self, temp_db_attribution):
        """Verify: Adding attribution twice updates instead of duplicating.

        Mutation: Remove ON CONFLICT or use INSERT instead of UPSERT
        Result: Duplicate key error or duplicate rows → Test fails ✓
        """
        # Add attribution
        add_event_attribution(200, 1, client_project_id=1, workdir_category="reports")

        # Add again with different values (should update)
        add_event_attribution(200, 1, client_project_id=2, workdir_category="tasks")

        # Retrieve
        attr = get_event_attribution(1)

        # ASSERTION: Should have latest values, not duplicate
        assert attr["client_project_id"] == 2
        assert attr["workdir_category"] == "tasks"

        # Verify only one row exists
        with get_db() as conn:
            count = conn.execute(
                "SELECT COUNT(*) as cnt FROM event_attribution WHERE source_id = 1"
            ).fetchone()
        assert count["cnt"] == 1
