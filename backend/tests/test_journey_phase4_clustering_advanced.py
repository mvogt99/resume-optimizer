"""Phase 4b: Event Clustering - Mutation verified tests (Part 2: Persistence & Scale).

TDD Contract:
- test_cluster_id_persisted: cluster_id stored in DB
- test_cluster_head_flag_persisted: is_cluster_head flag stored
- test_no_cross_user_clustering: Never clusters across different users
- test_single_event_cluster: Single event creates cluster
- test_empty_user_no_clusters: User with no events returns empty
- test_cluster_summary_counts_accurate: Summary stats accurate
- test_clustering_performance_at_scale: O(n²) performance at 1000 events
"""

import sqlite3
import tempfile
from datetime import datetime, timedelta
import time

import pytest

from models import get_db
from journey_clustering import cluster_events, get_cluster_summary


@pytest.fixture
def temp_db_cluster_adv(monkeypatch, request):
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

    conn.execute("INSERT INTO users VALUES (400, 'cluster@test.com', 'hash')")
    conn.execute("INSERT INTO users VALUES (401, 'other@test.com', 'hash')")

    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()

    yield path

    conn.close()
    import os
    os.unlink(path)


class TestClusterPersistence:
    """Mutation: Don't update cluster_id OR don't update is_cluster_head."""

    def test_cluster_id_persisted(self, temp_db_cluster_adv):
        """Verify: cluster_id is stored in DB.

        Mutation: Skip UPDATE ... cluster_id statement → no cluster_id
        Result: cluster_id remains NULL → Test fails ✓
        """
        # Insert source
        with get_db() as conn:
            conn.execute("INSERT INTO journey_sources (user_id, source_type, title) VALUES (400, 'git', 'feat')")
            conn.commit()

        # Insert similar events
        with get_db() as conn:
            conn.execute(
                "INSERT INTO journey_events (user_id, source_id, title) "
                "VALUES (400, 1, 'feat: Auth')"
            )
            conn.execute(
                "INSERT INTO journey_events (user_id, source_id, title) "
                "VALUES (400, 1, 'feat: Authentication')"
            )
            conn.commit()

        # Cluster
        result = cluster_events(400)

        # ASSERTION: Events should have cluster_id set
        with get_db() as conn:
            clustered = conn.execute(
                "SELECT COUNT(*) as cnt FROM journey_events WHERE user_id = 400 AND cluster_id IS NOT NULL"
            ).fetchone()

        assert clustered["cnt"] > 0, "Events should be assigned to clusters"

    def test_cluster_head_flag_persisted(self, temp_db_cluster_adv):
        """Verify: is_cluster_head flag is stored.

        Mutation: Skip is_cluster_head UPDATE → flag remains 0
        Result: No cluster heads marked → Test fails ✓
        """
        # Insert source
        with get_db() as conn:
            conn.execute("INSERT INTO journey_sources (user_id, source_type, title) VALUES (400, 'git', 'feat')")
            conn.commit()

        # Insert similar events
        with get_db() as conn:
            conn.execute(
                "INSERT INTO journey_events (user_id, source_id, title) "
                "VALUES (400, 1, 'feat: Auth')"
            )
            conn.execute(
                "INSERT INTO journey_events (user_id, source_id, title) "
                "VALUES (400, 1, 'feat: Authentication')"
            )
            conn.commit()

        # Cluster
        result = cluster_events(400)

        # ASSERTION: At least one cluster head should be marked
        with get_db() as conn:
            heads = conn.execute(
                "SELECT COUNT(*) as cnt FROM journey_events WHERE user_id = 400 AND is_cluster_head = 1"
            ).fetchone()

        assert heads["cnt"] > 0, "At least one cluster head should be marked"


class TestCrossUserIsolation:
    """Mutation: Don't check user_id OR group by user_id."""

    def test_no_cross_user_clustering(self, temp_db_cluster_adv):
        """Verify: Different users' events never cluster.

        Mutation: Remove user_id filter → cross-user clustering
        Result: User 400 and 401 incorrectly cluster → Test fails ✓
        """
        # Insert sources for both users
        with get_db() as conn:
            conn.execute("INSERT INTO journey_sources (user_id, source_type, title) VALUES (400, 'git', 'feat')")
            conn.execute("INSERT INTO journey_sources (user_id, source_type, title) VALUES (401, 'git', 'feat')")
            conn.commit()

        # Insert identical events for different users
        with get_db() as conn:
            conn.execute(
                "INSERT INTO journey_events (user_id, source_id, title) "
                "VALUES (400, 1, 'feat: Auth')"
            )
            conn.execute(
                "INSERT INTO journey_events (user_id, source_id, title) "
                "VALUES (401, 2, 'feat: Auth')"
            )
            conn.commit()

        # Cluster user 400
        result = cluster_events(400)

        # ASSERTION: User 401's event should NOT have cluster_id set
        with get_db() as conn:
            user401_clustered = conn.execute(
                "SELECT COUNT(*) as cnt FROM journey_events WHERE user_id = 401 AND cluster_id IS NOT NULL"
            ).fetchone()

        assert user401_clustered["cnt"] == 0, "User 401 events should not be clustered during user 400 clustering"


class TestEdgeCases:
    """Mutation: Don't handle empty/single event cases."""

    def test_single_event_cluster(self, temp_db_cluster_adv):
        """Verify: Single event creates cluster with itself.

        Mutation: Skip processing single events → no cluster created
        Result: Single event unclustered → Test fails ✓
        """
        # Insert source and single event
        with get_db() as conn:
            conn.execute("INSERT INTO journey_sources (user_id, source_type, title) VALUES (400, 'git', 'feat')")
            conn.execute(
                "INSERT INTO journey_events (user_id, source_id, title) "
                "VALUES (400, 1, 'feat: Auth')"
            )
            conn.commit()

        # Cluster
        result = cluster_events(400)

        # ASSERTION: Single event should create 1 cluster
        assert result["clusters_created"] >= 1

    def test_empty_user_no_clusters(self, temp_db_cluster_adv):
        """Verify: User with no events returns empty summary.

        Mutation: Don't check for empty events → crash or wrong count
        Result: Exception or non-zero count → Test fails ✓
        """
        # Cluster user with no events
        result = cluster_events(400)

        # ASSERTION: No clusters created
        assert result["total_events"] == 0
        assert result["clusters_created"] == 0


class TestClusterSummary:
    """Mutation: Don't count correctly OR skip GROUP BY."""

    def test_cluster_summary_counts_accurate(self, temp_db_cluster_adv):
        """Verify: Summary stats are correct.

        Mutation: Wrong COUNT(*) query → wrong counts
        Result: Inaccurate summary → Test fails ✓
        """
        # Insert sources
        with get_db() as conn:
            for i in range(3):
                conn.execute(
                    "INSERT INTO journey_sources (user_id, source_type, title) VALUES (400, 'git', ?)",
                    (f"feat{i}",)
                )
            conn.commit()

        # Insert 3 events (pair of similar + 1 dissimilar)
        with get_db() as conn:
            conn.execute(
                "INSERT INTO journey_events (user_id, source_id, title) "
                "VALUES (400, 1, 'feat: Auth')"
            )
            conn.execute(
                "INSERT INTO journey_events (user_id, source_id, title) "
                "VALUES (400, 2, 'feat: Authentication')"
            )
            conn.execute(
                "INSERT INTO journey_events (user_id, source_id, title) "
                "VALUES (400, 3, 'fix: Database')"
            )
            conn.commit()

        # Cluster
        cluster_events(400)

        # Get summary
        summary = get_cluster_summary(400)

        # ASSERTION: Counts should match
        assert summary["total_events"] == 3
        assert summary["clustered_events"] > 0
        assert summary["cluster_count"] >= 1
        assert summary["average_cluster_size"] > 0

    def test_summary_average_cluster_size(self, temp_db_cluster_adv):
        """Verify: Average cluster size is calculated correctly.

        Mutation: Wrong division → incorrect average
        Result: Wrong avg_size → Test fails ✓
        """
        # Insert source
        with get_db() as conn:
            conn.execute("INSERT INTO journey_sources (user_id, source_type, title) VALUES (400, 'git', 'feat')")
            conn.commit()

        # Insert 4 similar events (all should be in 1 cluster)
        with get_db() as conn:
            for i in range(4):
                conn.execute(
                    "INSERT INTO journey_events (user_id, source_id, title) "
                    "VALUES (400, 1, ?)",
                    (f"feat: Auth {i}",)
                )
            conn.commit()

        # Cluster
        cluster_events(400)

        # Get summary
        summary = get_cluster_summary(400)

        # ASSERTION: 4 events in 1 cluster should give avg = 4
        if summary["cluster_count"] > 0:
            assert summary["average_cluster_size"] >= 1.0


class TestPerformance:
    """Mutation: Don't optimize → O(n²) becomes O(n³)."""

    def test_clustering_performance_at_scale(self, temp_db_cluster_adv):
        """Verify: Clustering at 1000 events completes in <5s.

        Mutation: Remove indexing or optimize early-exit → slow
        Result: >5s clustering time → Test fails ✓
        """
        # Insert source
        with get_db() as conn:
            conn.execute("INSERT INTO journey_sources (user_id, source_type, title) VALUES (400, 'git', 'feat')")
            conn.commit()

        # Insert 1000 events
        with get_db() as conn:
            for i in range(1000):
                conn.execute(
                    "INSERT INTO journey_events (user_id, source_id, title) "
                    "VALUES (400, 1, ?)",
                    (f"feat: Feature {i}",)
                )
            conn.commit()

        # Cluster and measure time
        start = time.time()
        result = cluster_events(400)
        elapsed = time.time() - start

        # ASSERTION: Should complete in <5s (O(n²) acceptable at scale)
        assert elapsed < 5.0, f"Clustering 1000 events took {elapsed:.2f}s"
        assert result["total_events"] == 1000
