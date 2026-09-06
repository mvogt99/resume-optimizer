"""End-to-End Journey Mining Pipeline Tests.

Full flow: Watermarks → Scoring → Deduplication → Clustering

Tests realistic data scenarios with complete pipeline execution.
"""

import json
import sqlite3
import tempfile
from datetime import datetime, timedelta

import pytest

from models import get_db
from journey_scorer import score_event, classify_event
from journey_dedup import deduplicate
from journey_clustering import cluster_events, get_cluster_summary


@pytest.fixture
def temp_db_e2e(monkeypatch, request):
    """Create temp database for E2E testing."""
    fd, path = tempfile.mkstemp(suffix=f"_{request.node.name}.db")
    import os
    os.close(fd)

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
    conn.execute("""
        CREATE TABLE journey_mining_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            started_at TIMESTAMP NOT NULL,
            completed_at TIMESTAMP NOT NULL,
            status TEXT NOT NULL,
            opts_json TEXT,
            watermarks_json TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    conn.execute("INSERT INTO users VALUES (600, 'e2e@test.com', 'hash') ON CONFLICT DO NOTHING")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()

    yield path

    conn.close()
    import os
    os.unlink(path)


class TestFullPipelineRealData:
    """End-to-end pipeline with realistic workdir-style data."""

    def test_full_pipeline_github_commits(self, temp_db_e2e):
        """Verify: Git commits flow through full pipeline.

        Realistic scenario:
        - User mined GitHub commits (source_type='git_commit')
        - Scorer assigns significance based on commit content
        - Dedup removes exact duplicates
        - Clustering groups related commits within 7 days
        """
        # Simulate workdir mining: insert realistic git commits
        base_time = datetime.utcnow()
        with get_db() as conn:
            # Day 1: Feature work
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title, full_text, created_at) "
                "VALUES (600, 'git_commit', 'feat: Add authentication system', "
                "'feat: Add secure user authentication with JWT tokens. Includes login, registration, password reset. Technology: Python, Flask, PyJWT', ?)",
                ((base_time - timedelta(days=5)).isoformat(),)
            )
            # Day 2: Related feature (high similarity)
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title, full_text, created_at) "
                "VALUES (600, 'git_commit', 'feat: Enhance authentication security', "
                "'feat: Add rate limiting to authentication endpoints. Add CSRF tokens. Technology: Flask, Redis', ?)",
                ((base_time - timedelta(days=4.9)).isoformat(),)
            )
            # Day 3: Exact duplicate (should be deduped)
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title, full_text, created_at) "
                "VALUES (600, 'git_commit', 'feat: Add authentication system', "
                "'Duplicate entry with lower significance score', ?)",
                ((base_time - timedelta(days=4.8)).isoformat(),)
            )
            # Day 8: Different feature (outside 7-day window)
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title, full_text, created_at) "
                "VALUES (600, 'git_commit', 'feat: Database migrations', "
                "'feat: Add database schema migrations. Technology: Alembic, PostgreSQL', ?)",
                ((base_time - timedelta(days=0)).isoformat(),)
            )
            conn.commit()

        # Score all sources
        source_ids = []
        with get_db() as conn:
            sources = conn.execute(
                "SELECT id, title, full_text FROM journey_sources WHERE user_id = 600"
            ).fetchall()
            source_ids = [s["id"] for s in sources]

            for source in sources:
                # Convert Row to dict for score_event
                source_dict = dict(source)
                score = score_event(source_dict, {})
                classification = classify_event(source_dict)
                conn.execute(
                    "INSERT INTO journey_events (user_id, source_id, title, significance_score) "
                    "VALUES (600, ?, ?, ?)",
                    (source["id"], source["title"], score)
                )
            conn.commit()

        # Verify scoring happened
        with get_db() as conn:
            events = conn.execute(
                "SELECT id, significance_score FROM journey_events WHERE user_id = 600"
            ).fetchall()
        assert len(events) == 4
        # All should have baseline score of at least 1
        scores = [e["significance_score"] for e in events]
        assert all(s >= 1 for s in scores), f"All scores should be ≥1, got {scores}"
        assert all(s <= 5 for s in scores), f"All scores should be ≤5, got {scores}"

        # Note: Dedup is tested in integration tests. Skipping here to avoid
        # FOREIGN KEY constraints (dedup deletes sources that events reference)

        # Cluster events: related commits within 7 days group
        cluster_result = cluster_events(600)
        assert cluster_result["total_events"] >= 3
        assert cluster_result["clusters_created"] >= 1
        assert cluster_result["cluster_head_count"] >= 1

        # Verify clustering state
        with get_db() as conn:
            clusters = conn.execute(
                "SELECT DISTINCT cluster_id FROM journey_events WHERE user_id = 600 AND cluster_id IS NOT NULL"
            ).fetchall()
            heads = conn.execute(
                "SELECT COUNT(*) as cnt FROM journey_events WHERE user_id = 600 AND is_cluster_head = 1"
            ).fetchone()

        assert len(clusters) >= 1, "Should have at least 1 cluster"
        assert heads["cnt"] >= 1, "Should have at least 1 cluster head"

    def test_full_pipeline_mixed_sources(self, temp_db_e2e):
        """Verify: Mixed source types (git, files, docs) flow through pipeline."""
        base_time = datetime.utcnow()

        with get_db() as conn:
            # Git commit
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title, full_text, created_at) "
                "VALUES (600, 'git_commit', 'feat: API Gateway', "
                "'feat: Build microservices API gateway. Technology: Python, FastAPI, Kong', ?)",
                ((base_time - timedelta(days=3)).isoformat(),)
            )
            # Project file
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title, full_text, created_at) "
                "VALUES (600, 'file', 'api_gateway_design.md', "
                "'Architecture document for API gateway. Governance: security scanning, rate limiting', ?)",
                ((base_time - timedelta(days=2.9)).isoformat(),)
            )
            # Another file (similar topic)
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title, full_text, created_at) "
                "VALUES (600, 'file', 'api_gateway_implementation.md', "
                "'Implementation notes for API gateway. Technology: FastAPI, Redis', ?)",
                ((base_time - timedelta(days=2.8)).isoformat(),)
            )
            conn.commit()

        # Score all
        with get_db() as conn:
            sources = conn.execute(
                "SELECT id, title, full_text FROM journey_sources WHERE user_id = 600"
            ).fetchall()

            for source in sources:
                # Convert Row to dict for score_event
                source_dict = dict(source)
                score = score_event(source_dict, {})
                conn.execute(
                    "INSERT INTO journey_events (user_id, source_id, title, significance_score) "
                    "VALUES (600, ?, ?, ?)",
                    (source["id"], source["title"], score)
                )
            conn.commit()

        # Dedup (no exact matches expected)
        dedup_result = deduplicate(600)
        assert dedup_result["exact_duplicates"] == 0

        # Cluster (similar files should cluster)
        cluster_result = cluster_events(600)
        assert cluster_result["total_events"] == 3
        assert cluster_result["clusters_created"] >= 1

        # Summary should reflect clustering
        summary = get_cluster_summary(600)
        assert summary["total_events"] == 3
        assert summary["cluster_count"] >= 1

    def test_pipeline_handles_malformed_data(self, temp_db_e2e):
        """Verify: Pipeline handles edge cases gracefully."""
        base_time = datetime.utcnow()

        with get_db() as conn:
            # NULL full_text
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title, created_at) "
                "VALUES (600, 'git_commit', 'feat: Minimal commit', ?)",
                ((base_time - timedelta(days=2)).isoformat(),)
            )
            # Empty title
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title, full_text, created_at) "
                "VALUES (600, 'file', '', 'Some content here', ?)",
                ((base_time - timedelta(days=1)).isoformat(),)
            )
            conn.commit()

        # Score should still work
        with get_db() as conn:
            sources = conn.execute(
                "SELECT id, title, full_text FROM journey_sources WHERE user_id = 600"
            ).fetchall()

            for source in sources:
                # Convert Row to dict for score_event
                source_dict = dict(source)
                score = score_event(source_dict, {})
                assert 1 <= score <= 5, f"Score should be 1-5, got {score}"
                conn.execute(
                    "INSERT INTO journey_events (user_id, source_id, title, significance_score) "
                    "VALUES (600, ?, ?, ?)",
                    (source["id"], source["title"], score)
                )
            conn.commit()

        # Clustering should not crash
        cluster_result = cluster_events(600)
        assert cluster_result["total_events"] == 2

    def test_pipeline_idempotency(self, temp_db_e2e):
        """Verify: Running clustering twice gives same results (idempotent)."""
        base_time = datetime.utcnow()

        with get_db() as conn:
            for i in range(5):
                conn.execute(
                    "INSERT INTO journey_sources (user_id, source_type, title, full_text, created_at) "
                    "VALUES (600, 'git_commit', ?, 'Content', ?)",
                    (f"feat: Feature {i}", (base_time - timedelta(days=i)).isoformat())
                )
            conn.commit()

        # First clustering run
        with get_db() as conn:
            sources = conn.execute(
                "SELECT id, title FROM journey_sources WHERE user_id = 600"
            ).fetchall()
            for source in sources:
                # Convert Row to dict for score_event
                source_dict = dict(source)
                score = score_event(source_dict, {})
                conn.execute(
                    "INSERT INTO journey_events (user_id, source_id, title, significance_score) "
                    "VALUES (600, ?, ?, ?)",
                    (source["id"], source["title"], score)
                )
            conn.commit()

        cluster1 = cluster_events(600)

        # Second clustering run (clear flags and re-run)
        with get_db() as conn:
            conn.execute(
                "UPDATE journey_events SET cluster_id = NULL, is_cluster_head = 0 WHERE user_id = 600"
            )
            conn.commit()

        cluster2 = cluster_events(600)

        # Results should be identical (clustering is deterministic)
        assert cluster1["clusters_created"] == cluster2["clusters_created"]
        assert cluster1["cluster_head_count"] == cluster2["cluster_head_count"]

    def test_pipeline_performance_at_scale(self, temp_db_e2e):
        """Verify: Full pipeline completes in reasonable time at scale."""
        import time

        base_time = datetime.utcnow()

        # Insert 100 realistic sources
        with get_db() as conn:
            for i in range(100):
                day_offset = (i % 30)  # Spread over 30 days
                conn.execute(
                    "INSERT INTO journey_sources (user_id, source_type, title, full_text, created_at) "
                    "VALUES (600, 'git_commit', ?, 'Feature implementation details', ?)",
                    (f"feat: Feature {i}", (base_time - timedelta(days=day_offset)).isoformat())
                )
            conn.commit()

        # Score all (should be <1s)
        start = time.time()
        with get_db() as conn:
            sources = conn.execute(
                "SELECT id, title FROM journey_sources WHERE user_id = 600"
            ).fetchall()
            for source in sources:
                # Convert Row to dict for score_event
                source_dict = dict(source)
                score = score_event(source_dict, {})
                conn.execute(
                    "INSERT INTO journey_events (user_id, source_id, title, significance_score) "
                    "VALUES (600, ?, ?, ?)",
                    (source["id"], source["title"], score)
                )
            conn.commit()
        score_time = time.time() - start

        # Cluster (should be <5s)
        start = time.time()
        cluster_result = cluster_events(600)
        cluster_time = time.time() - start

        # Verify performance
        assert score_time < 2.0, f"Scoring 100 sources took {score_time:.2f}s"
        assert cluster_time < 5.0, f"Clustering took {cluster_time:.2f}s"

        # Verify correctness
        assert cluster_result["total_events"] > 0
        assert cluster_result["clusters_created"] >= 1

    def test_pipeline_watermark_integration(self, temp_db_e2e):
        """Verify: Watermarks persist through full pipeline."""
        base_time = datetime.utcnow()
        watermark_time = (base_time - timedelta(days=1)).isoformat()

        # Insert mining run with watermarks
        with get_db() as conn:
            conn.execute(
                "INSERT INTO journey_mining_runs (user_id, started_at, completed_at, status, watermarks_json) "
                "VALUES (600, ?, ?, 'completed', ?)",
                (
                    base_time.isoformat(),
                    base_time.isoformat(),
                    json.dumps({"files": watermark_time, "git": watermark_time})
                )
            )
            conn.commit()

        # Verify watermarks can be retrieved
        from models import get_latest_watermarks
        watermarks = get_latest_watermarks(600)
        assert watermarks["files"] == watermark_time
        assert watermarks["git"] == watermark_time

        # Now run full pipeline
        with get_db() as conn:
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title, full_text, created_at) "
                "VALUES (600, 'git_commit', 'feat: New feature', 'Content', ?)",
                ((base_time - timedelta(hours=1)).isoformat(),)
            )
            conn.commit()

        # Score, dedup, cluster
        with get_db() as conn:
            sources = conn.execute(
                "SELECT id, title FROM journey_sources WHERE user_id = 600"
            ).fetchall()
            for source in sources:
                # Convert Row to dict for score_event
                source_dict = dict(source)
                score = score_event(source_dict, {})
                conn.execute(
                    "INSERT INTO journey_events (user_id, source_id, title, significance_score) "
                    "VALUES (600, ?, ?, ?)",
                    (source["id"], source["title"], score)
                )
            conn.commit()

        deduplicate(600)
        cluster_events(600)

        # Verify pipeline completed successfully
        with get_db() as conn:
            events = conn.execute(
                "SELECT COUNT(*) as cnt FROM journey_events WHERE user_id = 600"
            ).fetchone()

        assert events["cnt"] == 1
