"""Phase 3: Performance assertion for significance scoring at scale.

TDD Contract:
- test_rescore_1000_events_under_10_seconds: Rescoring 1K events completes in <10 seconds
- Mutation: Add O(n²) sort or O(n*m) loop in score_event
  Result: Timeout or exceeds budget → Test fails ✓
"""

import json
import sqlite3
import tempfile
import time
from datetime import datetime

import pytest

from models import get_db
from journey_scorer import score_event


@pytest.fixture
def temp_db_perf(monkeypatch, request):
    """Create temp SQLite database with schema for performance testing."""
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
        CREATE TABLE IF NOT EXISTS journey_sources (
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
        CREATE TABLE IF NOT EXISTS journey_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            source_id INTEGER NOT NULL,
            event_date TIMESTAMP,
            significance_score INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (source_id) REFERENCES journey_sources (id)
        )
    """)

    conn.execute("INSERT OR IGNORE INTO users (id, email, password_hash) VALUES (?, ?, ?)",
                 (50, 'perf@test.com', 'hash'))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()

    yield path

    conn.close()
    import os
    os.unlink(path)


class TestPerformanceScoring:
    """Mutation: Add O(n²) algorithm or nested loop in score_event."""

    def test_rescore_1000_events_under_10_seconds(self, temp_db_perf):
        """Verify: Rescoring 1K events completes in <10 seconds.

        Mutation breaks: Add O(n²) sort in score_event or nested loop.
        Result: Timeout or exceeds time budget → Test fails ✓
        """
        user_id = 50

        # Stage 1: Populate 1000 sources with varied types
        print("\n[PERF] Inserting 1000 sources...")
        source_types = ["git_commit", "file", "governance", "documentation"]
        titles = [
            "feat(core): Feature",
            "fix(bug): Bug fix",
            "docs: Documentation",
            "chore: Update",
            "test(unit): Unit tests",
            "governance: Security audit",
            "report: Monthly report"
        ]

        sources = []
        with get_db() as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            for i in range(1000):
                source_type = source_types[i % len(source_types)]
                title = titles[i % len(titles)]
                source_id = conn.execute(
                    "INSERT INTO journey_sources (user_id, source_type, title, full_text) "
                    "VALUES (?, ?, ?, ?)",
                    (user_id, source_type, f"{title} #{i}", f"Content for event {i}")
                ).lastrowid
                sources.append({
                    "id": source_id,
                    "source_type": source_type,
                    "title": f"{title} #{i}",
                    "full_text": f"Content for event {i}",
                    "classification": ""
                })
            conn.execute("PRAGMA foreign_keys = ON")
            conn.commit()

        assert len(sources) == 1000, "Failed to insert 1000 sources"

        # Stage 2: Time the scoring of all events
        print("[PERF] Scoring 1000 events...")
        start_time = time.time()

        scores = []
        for source in sources:
            event = {
                "technologies": ["Python", "Go", "Rust"] if source["id"] % 5 == 0 else []
            }
            score = score_event(source, event)
            scores.append(score)

        end_time = time.time()
        elapsed = end_time - start_time

        print(f"[PERF] Scored 1000 events in {elapsed:.3f} seconds")

        # ASSERTION 1: All scores calculated
        assert len(scores) == 1000
        assert all(1 <= s <= 5 for s in scores), "Some scores out of range"

        # ASSERTION 2: Performance threshold
        assert elapsed < 10.0, f"Scoring 1000 events took {elapsed:.3f}s, must be <10s"

        # Stage 3: Store scores in database
        print("[PERF] Storing 1000 scores...")
        with get_db() as conn:
            for source, score in zip(sources, scores):
                conn.execute(
                    "INSERT INTO journey_events (title, significance_score) "
                    "VALUES (?, ?)",
                    (f"event_{source['id']}", score)
                )
            conn.commit()

        # ASSERTION 3: All scores persisted (count in this test session)
        with get_db() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM journey_events WHERE title LIKE 'event_%'"
            ).fetchone()[0]
        assert count >= 1000  # At least the 1000 we just inserted

        print(f"[PERF] ✓ Performance test passed: {elapsed:.3f}s < 10.0s")

    def test_rescore_query_performance(self, temp_db_perf):
        """Verify: Querying and rescoring is efficient."""
        user_id = 50

        # Stage 1: Insert test data
        print("\n[PERF] Inserting 500 test sources...")
        with get_db() as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            for i in range(500):
                conn.execute(
                    "INSERT INTO journey_sources (user_id, source_type, title, full_text) "
                    "VALUES (?, ?, ?, ?)",
                    (user_id, "git_commit", f"feat: Feature {i}", f"Description {i}")
                )
            conn.execute("PRAGMA foreign_keys = ON")
            conn.commit()

        # Stage 2: Time the query + rescore operation
        print("[PERF] Querying and scoring 500 events...")
        start_time = time.time()

        with get_db() as conn:
            sources = conn.execute(
                "SELECT id, source_type, title, full_text FROM journey_sources WHERE user_id = ?",
                (user_id,)
            ).fetchall()

        # Score all (convert Row to dict first)
        scores = {}
        for source_row in sources:
            source = dict(source_row)
            source["classification"] = ""  # Add required field
            event = {"technologies": []}
            score = score_event(source, event)
            scores[source["id"]] = score

        # Update all
        with get_db() as conn:
            for i, (source_id, score) in enumerate(scores.items()):
                conn.execute(
                    "INSERT INTO journey_events (title, significance_score) "
                    "VALUES (?, ?)",
                    (f"perf_event_{i}", score)
                )
            conn.commit()

        end_time = time.time()
        elapsed = end_time - start_time

        print(f"[PERF] Query + score + update 500 events: {elapsed:.3f}s")

        # ASSERTION: Should complete quickly
        assert elapsed < 5.0, f"Query+rescore took {elapsed:.3f}s, must be <5s"

        print(f"[PERF] ✓ Query performance test passed: {elapsed:.3f}s < 5.0s")

    def test_bulk_classification_performance(self, temp_db_perf):
        """Verify: Classifying 500 events is efficient."""
        from journey_scorer import classify_event

        user_id = 50

        # Create varied sources
        sources = [
            {
                "source_type": "git_commit",
                "title": f"feat(core): Feature {i}",
                "classification": ""
            }
            for i in range(250)
        ] + [
            {
                "source_type": "governance",
                "title": f"Governance {i}",
                "classification": ""
            }
            for i in range(250)
        ]

        # Time classification
        print("\n[PERF] Classifying 500 events...")
        start_time = time.time()

        classifications = [classify_event(s) for s in sources]

        end_time = time.time()
        elapsed = end_time - start_time

        print(f"[PERF] Classified 500 events in {elapsed:.3f}s")

        # ASSERTION: All classified and fast
        assert len(classifications) == 500
        assert all(c in ["achievement", "fix", "development", "governance", "learning", "milestone"] for c in classifications)
        assert elapsed < 2.0, f"Classification took {elapsed:.3f}s, must be <2s"

        print(f"[PERF] ✓ Classification performance test passed: {elapsed:.3f}s < 2.0s")
