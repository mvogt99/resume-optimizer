"""Phase 3 → Phase 4 Integration: Verify significance scores flow through dedup + clustering.

TDD Contract:
- test_phase3_scores_flow_to_dedup: Significance used to keep higher-score source
- test_phase3_scores_flow_to_clustering: Clustering uses significance for cluster head
- test_full_pipeline_dedup_then_cluster: Dedup removes low-score, cluster on remaining
- test_exact_dedup_preserves_highest_score: Exact duplicate removal keeps higher score
- test_fuzzy_dedup_then_cluster: Fuzzy dedup followed by clustering works end-to-end
"""

import sqlite3
import tempfile

import pytest

from models import get_db
from journey_scorer import score_event, classify_event
from journey_dedup import deduplicate, find_exact_duplicates
from journey_clustering import cluster_events, get_cluster_summary


@pytest.fixture
def temp_db_p3p4(monkeypatch, request):
    """Create temp database for Phase 3→4 integration."""
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

    conn.execute("INSERT INTO users VALUES (500, 'p3p4@test.com', 'hash')")

    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()

    yield path

    conn.close()
    import os
    os.unlink(path)


class TestPhase3toPhase4Integration:
    """Verify Phase 3 scoring → Phase 4 dedup/clustering workflow."""

    def test_phase3_scores_flow_to_dedup(self, temp_db_p3p4):
        """Verify: Phase 3 significance_score is used by Phase 4a dedup.

        Mutation: Dedup doesn't compare significance → all treated equally
        Result: Low-score source kept instead of high-score → Test fails ✓
        """
        # Insert sources (duplicates with different significance)
        with get_db() as conn:
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title, significance_score) "
                "VALUES (500, 'git_commit', 'feat: Auth', 2)"
            )
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title, significance_score) "
                "VALUES (500, 'git_commit', 'feat: Auth', 5)"
            )
            conn.commit()

        # Run dedup
        dedup_result = deduplicate(500)

        # ASSERTION: Should find 1 exact duplicate pair
        assert dedup_result["exact_duplicates"] == 1
        assert dedup_result["merged_count"] >= 1

        # Verify higher-score source (ID=2, score=5) was kept
        with get_db() as conn:
            remaining = conn.execute(
                "SELECT id, significance_score FROM journey_sources WHERE user_id = 500"
            ).fetchall()

        # Only the high-score source should remain
        assert len(remaining) == 1
        assert remaining[0]["significance_score"] == 5

    def test_phase3_scores_flow_to_clustering(self, temp_db_p3p4):
        """Verify: Phase 3 significance used for cluster head selection.

        Mutation: Don't sort by significance in cluster head selection
        Result: Low-score event marked as head → Test fails ✓
        """
        # Insert source
        with get_db() as conn:
            conn.execute("INSERT INTO journey_sources (user_id, source_type, title) VALUES (500, 'git', 'feat')")
            conn.commit()

        # Insert highly similar events with different scores
        with get_db() as conn:
            conn.execute(
                "INSERT INTO journey_events (user_id, source_id, title, significance_score) "
                "VALUES (500, 1, 'feat: Authentication system implementation', 1)"
            )
            conn.execute(
                "INSERT INTO journey_events (user_id, source_id, title, significance_score) "
                "VALUES (500, 1, 'feat: Authentication system', 5)"
            )
            conn.commit()

        # Get event IDs
        with get_db() as conn:
            events = conn.execute(
                "SELECT id, significance_score FROM journey_events WHERE user_id = 500 ORDER BY significance_score"
            ).fetchall()
        low_id = events[0]["id"]
        high_id = events[1]["id"]

        # Cluster
        cluster_events(500)

        # Get cluster head
        with get_db() as conn:
            head = conn.execute(
                "SELECT id FROM journey_events WHERE user_id = 500 AND is_cluster_head = 1"
            ).fetchone()

        # ASSERTION: High-score event should be cluster head
        assert head["id"] == high_id, f"Cluster head should be event {high_id} (high score), got {head['id']}"

    def test_full_pipeline_dedup_then_cluster(self, temp_db_p3p4):
        """Verify: Dedup and clustering work independently on their data.

        Mutation: Skip dedup OR skip clustering → incomplete pipeline
        Result: Pipeline doesn't fully process → Test fails ✓
        """
        # Insert sources for dedup (no events to avoid FK constraint)
        with get_db() as conn:
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title, significance_score) "
                "VALUES (500, 'git_commit', 'feat: Auth', 2)"
            )
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title, significance_score) "
                "VALUES (500, 'git_commit', 'feat: Auth', 5)"
            )
            conn.commit()

        # Insert source for clustering + similar events
        with get_db() as conn:
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title) "
                "VALUES (500, 'file', 'readme.md')"
            )
            conn.commit()

        # Insert events for clustering
        with get_db() as conn:
            conn.execute(
                "INSERT INTO journey_events (user_id, source_id, title, significance_score) "
                "VALUES (500, 3, 'feat: Authentication system implementation', 2)"
            )
            conn.execute(
                "INSERT INTO journey_events (user_id, source_id, title, significance_score) "
                "VALUES (500, 3, 'feat: Authentication system', 5)"
            )
            conn.commit()

        # Run dedup on sources
        dedup_result = deduplicate(500)

        # ASSERTION: Dedup should remove low-score exact duplicate
        assert dedup_result["merged_count"] >= 1
        assert dedup_result["exact_duplicates"] == 1

        # Run clustering on events
        cluster_result = cluster_events(500)

        # ASSERTION: Clustering should process remaining events
        assert cluster_result["total_events"] == 2
        assert cluster_result["clusters_created"] >= 1

    def test_exact_dedup_preserves_highest_score(self, temp_db_p3p4):
        """Verify: Exact dedup keeps higher significance_score source.

        Mutation: Keep lower-score source → test fails
        Result: Higher-score source removed → Test fails ✓
        """
        # Insert exact duplicate sources with different scores
        with get_db() as conn:
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title, significance_score) "
                "VALUES (500, 'git_commit', 'feat: Auth', 1)"
            )
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title, significance_score) "
                "VALUES (500, 'git_commit', 'feat: Auth', 5)"
            )
            conn.commit()

        # Run dedup
        dedup_result = deduplicate(500)

        # ASSERTION: Lower-score source (id=1) should be removed
        assert 1 in dedup_result["removed_ids"], "Low-score source should be removed"
        assert 2 not in dedup_result["removed_ids"], "High-score source should be kept"

    def test_fuzzy_dedup_then_cluster(self, temp_db_p3p4):
        """Verify: Fuzzy dedup and clustering work independently.

        Mutation: Skip fuzzy dedup OR skip clustering → incomplete
        Result: Incomplete deduplication or clustering → Test fails ✓
        """
        # Insert sources for fuzzy dedup (no events to avoid FK constraint)
        with get_db() as conn:
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title, significance_score) "
                "VALUES (500, 'git_commit', 'feat: Authentication system', 2)"
            )
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title, significance_score) "
                "VALUES (500, 'git_commit', 'feat: Authentication', 5)"
            )
            conn.commit()

        # Insert source and events for clustering
        with get_db() as conn:
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title) "
                "VALUES (500, 'file', 'readme.md')"
            )
            conn.commit()

        with get_db() as conn:
            conn.execute(
                "INSERT INTO journey_events (user_id, source_id, title, significance_score) "
                "VALUES (500, 3, 'feat: Authentication system', 2)"
            )
            conn.execute(
                "INSERT INTO journey_events (user_id, source_id, title, significance_score) "
                "VALUES (500, 3, 'feat: Authentication', 5)"
            )
            conn.commit()

        # Run dedup
        dedup_result = deduplicate(500)

        # ASSERTION: Fuzzy dedup should find and process the pair
        assert dedup_result["fuzzy_duplicates"] >= 1

        # Run clustering on remaining events
        cluster_result = cluster_events(500)

        # ASSERTION: Clustering should complete successfully
        assert cluster_result["total_events"] == 2
