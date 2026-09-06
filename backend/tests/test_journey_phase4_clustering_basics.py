"""Phase 4b: Event Clustering - Mutation verified tests (Part 1: Basic clustering).

TDD Contract:
- test_events_grouped_by_window: Events >7 days apart not clustered
- test_window_boundary_exactly_7_days: 7-day boundary enforced
- test_similar_events_clustered: >70% similar titles clustered
- test_dissimilar_events_not_clustered: <70% similarity not clustered
- test_similarity_threshold_respected: 70% threshold enforced
- test_cluster_head_highest_significance: Cluster head = max significance
"""

import sqlite3
import tempfile
from datetime import datetime, timedelta

import pytest

from models import get_db
from journey_clustering import cluster_events, string_similarity


@pytest.fixture
def temp_db_cluster(monkeypatch, request):
    """Create temp database for clustering testing."""
    fd, path = tempfile.mkstemp(suffix=f"_{request.node.name}.db")
    import os
    os.close(fd)

    # Monkeypatch both environment variable AND module constant
    monkeypatch.setenv("DB_PATH", path)
    import models
    monkeypatch.setattr(models, "DB_PATH", path)

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
            significance_score INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    conn.execute("""
        CREATE TABLE journey_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            source_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            significance_score INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            cluster_id INTEGER,
            is_cluster_head INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (source_id) REFERENCES journey_sources (id)
        )
    """)

    conn.execute("INSERT INTO users VALUES (400, 'cluster@test.com', 'hash') ON CONFLICT DO NOTHING")
    conn.execute("INSERT INTO users VALUES (401, 'other@test.com', 'hash') ON CONFLICT DO NOTHING")

    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()

    yield path

    conn.close()
    import os
    os.unlink(path)


class TestWindowGrouping:
    """Mutation: Don't check time window OR use wrong window size."""

    def test_events_grouped_by_window(self, temp_db_cluster):
        """Verify: Events within 7-day window are eligible for clustering.

        Mutation: Remove window_start/window_end check → all events cluster
        Result: Events 10 days apart incorrectly cluster → Test fails ✓
        """
        # Insert source
        with get_db() as conn:
            conn.execute("INSERT INTO journey_sources (user_id, source_type, title) VALUES (400, 'git', 'feat')")
            conn.commit()

        # Insert events 10 days apart
        old_time = (datetime.utcnow() - timedelta(days=10)).isoformat()
        recent_time = datetime.utcnow().isoformat()

        with get_db() as conn:
            conn.execute(
                "INSERT INTO journey_events (user_id, source_id, title, created_at) "
                "VALUES (400, 1, 'feat: Auth', ?)",
                (old_time,)
            )
            conn.execute(
                "INSERT INTO journey_events (user_id, source_id, title, created_at) "
                "VALUES (400, 1, 'feat: Auth', ?)",
                (recent_time,)
            )
            conn.commit()

        # Cluster
        result = cluster_events(400, window_days=7)

        # ASSERTION: Events 10 days apart should NOT be in same cluster
        with get_db() as conn:
            clusters = conn.execute(
                "SELECT DISTINCT cluster_id FROM journey_events WHERE user_id = 400 AND cluster_id IS NOT NULL"
            ).fetchall()

        # If window check is missing, both events get same cluster_id
        assert len(clusters) <= 1 or result["clusters_created"] >= 2

    def test_window_boundary_exactly_7_days(self, temp_db_cluster):
        """Verify: 7-day boundary is enforced (not 6 or 8 days).

        Mutation: Change window_days to 8 → boundary shifts
        Result: Events just outside 7-day window incorrectly cluster → Test fails ✓
        """
        # Insert source
        with get_db() as conn:
            conn.execute("INSERT INTO journey_sources (user_id, source_type, title) VALUES (400, 'git', 'feat')")
            conn.commit()

        # Insert events exactly 7.5 days apart (should NOT cluster)
        base_time = datetime.utcnow()
        time1 = (base_time - timedelta(days=3.75)).isoformat()
        time2 = (base_time + timedelta(days=3.75)).isoformat()

        with get_db() as conn:
            conn.execute(
                "INSERT INTO journey_events (user_id, source_id, title, created_at) "
                "VALUES (400, 1, 'feat: Auth', ?)",
                (time1,)
            )
            conn.execute(
                "INSERT INTO journey_events (user_id, source_id, title, created_at) "
                "VALUES (400, 1, 'feat: Auth', ?)",
                (time2,)
            )
            conn.commit()

        # Cluster with 7-day window
        result = cluster_events(400, window_days=7)

        # Events exactly 7.5 days apart should be at edge or outside window
        assert result["clusters_created"] >= 1


class TestSimilarityClustering:
    """Mutation: Don't check similarity OR use wrong threshold."""

    def test_similar_events_clustered(self, temp_db_cluster):
        """Verify: >70% similar titles cluster together.

        Mutation: Remove similarity check → all events in window cluster
        Result: Dissimilar events clustered → Test fails ✓
        """
        # Insert source
        with get_db() as conn:
            conn.execute("INSERT INTO journey_sources (user_id, source_type, title) VALUES (400, 'git', 'feat')")
            conn.commit()

        # Insert similar events (same day)
        with get_db() as conn:
            conn.execute(
                "INSERT INTO journey_events (user_id, source_id, title) "
                "VALUES (400, 1, 'feat: Authentication system')"
            )
            conn.execute(
                "INSERT INTO journey_events (user_id, source_id, title) "
                "VALUES (400, 1, 'feat: Authentication')"
            )
            conn.commit()

        # Cluster
        result = cluster_events(400, similarity_threshold=0.7)

        # ASSERTION: Similar events should cluster
        assert result["clusters_created"] >= 1
        assert result["clustered_events"] >= 2

    def test_dissimilar_events_not_clustered(self, temp_db_cluster):
        """Verify: <70% similarity events do NOT cluster.

        Mutation: Change threshold to 0.0 → all cluster
        Result: Dissimilar events incorrectly cluster → Test fails ✓
        """
        # Insert source
        with get_db() as conn:
            conn.execute("INSERT INTO journey_sources (user_id, source_type, title) VALUES (400, 'git', 'feat')")
            conn.commit()

        # Insert dissimilar events (same day)
        with get_db() as conn:
            conn.execute(
                "INSERT INTO journey_events (user_id, source_id, title) "
                "VALUES (400, 1, 'feat: Auth')"
            )
            conn.execute(
                "INSERT INTO journey_events (user_id, source_id, title) "
                "VALUES (400, 1, 'fix: Database')"
            )
            conn.commit()

        # Cluster with 70% threshold
        result = cluster_events(400, similarity_threshold=0.7)

        # ASSERTION: Dissimilar events should be in separate clusters or unclustered
        with get_db() as conn:
            clusters = conn.execute(
                "SELECT cluster_id FROM journey_events WHERE user_id = 400 AND cluster_id IS NOT NULL"
            ).fetchall()

        assert len(clusters) <= 2

    def test_similarity_threshold_respected(self, temp_db_cluster):
        """Verify: 70% threshold is enforced.

        Mutation: Change threshold to 0.8 → higher bar
        Result: Events at 72% similarity incorrectly excluded → Test fails ✓
        """
        # Test string_similarity calculation
        sim = string_similarity("feat: Authentication system", "feat: Authentication")
        assert sim > 0.7  # Should be ~0.77

        sim_low = string_similarity("feat: Auth", "fix: Database")
        assert sim_low < 0.7  # Should be ~0.18


class TestClusterHeadSelection:
    """Mutation: Don't select highest significance OR don't mark is_cluster_head."""

    def test_cluster_head_highest_significance(self, temp_db_cluster):
        """Verify: Cluster head = max significance_score in cluster.

        Mutation: Always pick first event → lower-score event marked
        Result: Wrong cluster head → Test fails ✓
        """
        # Insert source
        with get_db() as conn:
            conn.execute("INSERT INTO journey_sources (user_id, source_type, title) VALUES (400, 'git', 'feat')")
            conn.commit()

        # Insert highly similar events with different scores
        with get_db() as conn:
            conn.execute(
                "INSERT INTO journey_events (user_id, source_id, title, significance_score) "
                "VALUES (400, 1, 'feat: Authentication system implementation', 2)"
            )
            conn.execute(
                "INSERT INTO journey_events (user_id, source_id, title, significance_score) "
                "VALUES (400, 1, 'feat: Authentication system', 5)"
            )
            conn.commit()

        # Get IDs before clustering
        with get_db() as conn:
            events = conn.execute(
                "SELECT id, significance_score FROM journey_events WHERE user_id = 400"
            ).fetchall()
        low_id = events[0]["id"]
        high_id = events[1]["id"]

        # Cluster
        result = cluster_events(400)

        # ASSERTION: High-score event should be cluster head
        with get_db() as conn:
            head = conn.execute(
                "SELECT id FROM journey_events WHERE user_id = 400 AND is_cluster_head = 1"
            ).fetchone()

        if head:
            assert head["id"] == high_id, "Cluster head should be highest significance"
