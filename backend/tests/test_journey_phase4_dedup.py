"""Phase 4a: Semantic Deduplication - Mutation verified tests.

TDD Contract:
- test_exact_match_found: Identifies sources with same title + source_type
- test_fuzzy_match_found: Identifies >80% similar titles within 1-day window
- test_keep_higher_significance: Merge keeps higher-score source
- test_window_boundary: Respects 1-day window for fuzzy match
- test_similarity_threshold: Respects 80% threshold
- test_full_dedup_pipeline: exact + fuzzy + merge all work together
- test_no_cross_user_dedup: Never merges across different users
- test_merge_count_accurate: Correct number of merges reported
"""

import sqlite3
import tempfile
from datetime import datetime, timedelta

import pytest

from models import get_db
from journey_dedup import (
    find_exact_duplicates,
    find_fuzzy_duplicates,
    string_similarity,
    merge_duplicates,
    deduplicate,
)


@pytest.fixture
def temp_db_dedup(monkeypatch, request):
    """Create temp database for dedup testing."""
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

    conn.execute("INSERT INTO users VALUES (300, 'dedup@test.com', 'hash') ON CONFLICT DO NOTHING")
    conn.execute("INSERT INTO users VALUES (301, 'other@test.com', 'hash') ON CONFLICT DO NOTHING")

    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()

    yield path

    conn.close()
    import os
    os.unlink(path)


class TestExactDuplicates:
    """Mutation: Don't check for same title/source_type/user_id OR remove the check."""

    def test_exact_match_found(self, temp_db_dedup):
        """Verify: Exact duplicates (same title + source_type) are found.

        Mutation: Remove HAVING COUNT(*) > 1 → no duplicates found
        Result: Empty list returned → Test fails ✓
        """
        # Insert exact duplicates
        with get_db() as conn:
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title) VALUES (300, 'git_commit', 'feat: Auth')"
            )
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title) VALUES (300, 'git_commit', 'feat: Auth')"
            )
            conn.commit()

        # Find duplicates
        dups = find_exact_duplicates(300)

        # ASSERTION: Must find one pair
        assert len(dups) == 1
        assert dups[0][0] != dups[0][1]  # Different IDs

    def test_exact_match_different_type_not_duplicate(self, temp_db_dedup):
        """Verify: Same title but different source_type = NOT duplicate.

        Mutation: Remove source_type from GROUP BY → wrongly treats as duplicate
        Result: Incorrectly merges different types → Test fails ✓
        """
        # Insert with same title, different types
        with get_db() as conn:
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title) VALUES (300, 'git_commit', 'feat: Auth')"
            )
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title) VALUES (300, 'file', 'feat: Auth')"
            )
            conn.commit()

        # Find duplicates
        dups = find_exact_duplicates(300)

        # ASSERTION: Should NOT find duplicates
        assert len(dups) == 0

    def test_no_cross_user_exact_match(self, temp_db_dedup):
        """Verify: Different users' sources never merge.

        Mutation: Remove user_id from GROUP BY → cross-user merges
        Result: User 300 and 301 incorrectly merged → Test fails ✓
        """
        # Insert same title for different users
        with get_db() as conn:
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title) VALUES (300, 'git_commit', 'feat: Auth')"
            )
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title) VALUES (301, 'git_commit', 'feat: Auth')"
            )
            conn.commit()

        # Find duplicates for user 300
        dups = find_exact_duplicates(300)

        # ASSERTION: No duplicates found (different users)
        assert len(dups) == 0


class TestFuzzyDuplicates:
    """Mutation: Don't check similarity OR don't respect time window."""

    def test_fuzzy_match_found(self, temp_db_dedup):
        """Verify: >80% similar titles within 1-day are found.

        Mutation: Remove similarity check → all titles considered duplicates
        Result: Every pair matches → Test fails ✓
        """
        # Insert fuzzy duplicates
        with get_db() as conn:
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title) VALUES (300, 'git_commit', 'feat: Authentication system')"
            )
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title) VALUES (300, 'git_commit', 'feat: Authentication')"
            )
            conn.commit()

        # Find fuzzy duplicates
        dups = find_fuzzy_duplicates(300, threshold=0.8)

        # ASSERTION: Should find fuzzy match
        assert len(dups) > 0

    def test_similarity_threshold_respected(self, temp_db_dedup):
        """Verify: Titles below 80% similarity not matched.

        Mutation: Change threshold to 0.0 → all match
        Result: Too many duplicates found → Test fails ✓
        """
        # Insert low-similarity titles
        with get_db() as conn:
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title) VALUES (300, 'git_commit', 'feat: Auth')"
            )
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title) VALUES (300, 'git_commit', 'fix: Database')"
            )
            conn.commit()

        # Find fuzzy duplicates with 80% threshold
        dups = find_fuzzy_duplicates(300, threshold=0.8)

        # ASSERTION: Should NOT match (low similarity)
        assert len(dups) == 0

    def test_window_boundary_respected(self, temp_db_dedup):
        """Verify: Titles >1-day apart don't match as fuzzy duplicates.

        Mutation: Remove window check OR increase window → older sources match
        Result: Old sources incorrectly merged → Test fails ✓
        """
        # Insert similar titles but outside 1-day window
        old_time = (datetime.utcnow() - timedelta(days=3)).isoformat()
        recent_time = datetime.utcnow().isoformat()

        with get_db() as conn:
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title, created_at) "
                "VALUES (300, 'git_commit', 'feat: Authentication', ?)",
                (old_time,)
            )
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title, created_at) "
                "VALUES (300, 'git_commit', 'feat: Authentication', ?)",
                (recent_time,)
            )
            conn.commit()

        # Find fuzzy duplicates
        dups = find_fuzzy_duplicates(300, threshold=0.8, day_window=1)

        # ASSERTION: Should NOT match (>1 day apart)
        assert len(dups) == 0

    def test_string_similarity_calculation(self):
        """Verify: Similarity score calculation is correct.

        Mutation: Remove string comparison logic → always return 1.0
        Result: All strings match → Test fails ✓
        """
        # Test exact match
        sim = string_similarity("feat: Auth", "feat: Auth")
        assert sim == 1.0

        # Test high similarity
        sim = string_similarity("feat: Authentication system", "feat: Authentication")
        assert sim > 0.8

        # Test low similarity
        sim = string_similarity("feat: Auth", "fix: Database")
        assert sim < 0.5


class TestMergeDuplicates:
    """Mutation: Don't keep higher significance OR don't delete removed sources."""

    def test_keep_higher_significance(self, temp_db_dedup):
        """Verify: Merge keeps the higher-significance source.

        Mutation: Always keep first source → keeps lower-score source
        Result: Wrong source kept → Test fails ✓
        """
        # Insert duplicates with different significance
        with get_db() as conn:
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title, significance_score) "
                "VALUES (300, 'git_commit', 'feat: Auth', 2)"
            )
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title, significance_score) "
                "VALUES (300, 'git_commit', 'feat: Auth', 4)"
            )
            conn.commit()

        # Get IDs
        with get_db() as conn:
            sources = conn.execute(
                "SELECT id, significance_score FROM journey_sources WHERE user_id = 300"
            ).fetchall()

        low_id = sources[0]["id"]
        high_id = sources[1]["id"]

        # Merge (low_id, high_id) pair - should keep high_id
        result = merge_duplicates(300, [(low_id, high_id)])

        # ASSERTION: High-score source should be kept
        assert high_id not in result["removed_ids"]
        assert low_id in result["removed_ids"]

    def test_merge_count_accurate(self, temp_db_dedup):
        """Verify: Merge count matches actual merges.

        Mutation: Don't count merges OR count wrong duplicates
        Result: Wrong count returned → Test fails ✓
        """
        # Insert 3 pairs of duplicates
        with get_db() as conn:
            for i in range(3):
                conn.execute(
                    "INSERT INTO journey_sources (user_id, source_type, title) VALUES (300, 'git_commit', ?)",
                    (f"feat: Feature {i}",)
                )
                conn.execute(
                    "INSERT INTO journey_sources (user_id, source_type, title) VALUES (300, 'git_commit', ?)",
                    (f"feat: Feature {i}",)
                )
            conn.commit()

        # Get all duplicates
        exact = find_exact_duplicates(300)

        # Merge
        result = merge_duplicates(300, exact)

        # ASSERTION: Count matches actual merges
        assert result["merged_count"] == 3
        assert len(result["removed_ids"]) == 3

    def test_sources_deleted_on_merge(self, temp_db_dedup):
        """Verify: Removed sources are actually deleted from DB.

        Mutation: Skip DELETE statement → sources remain in DB
        Result: Duplicates still exist → Test fails ✓
        """
        # Insert duplicates
        with get_db() as conn:
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title) VALUES (300, 'git_commit', 'feat: Auth')"
            )
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title) VALUES (300, 'git_commit', 'feat: Auth')"
            )
            conn.commit()

        # Get IDs
        with get_db() as conn:
            ids = conn.execute(
                "SELECT id FROM journey_sources WHERE user_id = 300"
            ).fetchall()

        keep_id = ids[0]["id"]
        remove_id = ids[1]["id"]

        # Merge
        merge_duplicates(300, [(keep_id, remove_id)])

        # Verify deleted
        with get_db() as conn:
            remaining = conn.execute(
                "SELECT COUNT(*) as cnt FROM journey_sources WHERE user_id = 300"
            ).fetchone()

        # ASSERTION: Only one source remains
        assert remaining["cnt"] == 1


class TestFullDedup:
    """Integration test: exact + fuzzy + merge all work together."""

    def test_full_dedup_pipeline(self, temp_db_dedup):
        """Verify: Full dedup pipeline (exact + fuzzy + merge) works.

        Mutation: Skip exact OR skip fuzzy OR skip merge
        Result: Incomplete deduplication → Test fails ✓
        """
        # Insert mix of exact and fuzzy duplicates
        with get_db() as conn:
            # Exact duplicates
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title) VALUES (300, 'git_commit', 'feat: Auth')"
            )
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title) VALUES (300, 'git_commit', 'feat: Auth')"
            )

            # Fuzzy duplicates
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title) VALUES (300, 'git_commit', 'feat: Database system')"
            )
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title) VALUES (300, 'git_commit', 'feat: Database')"
            )

            # No duplicate
            conn.execute(
                "INSERT INTO journey_sources (user_id, source_type, title) VALUES (300, 'git_commit', 'fix: Bug')"
            )

            conn.commit()

        # Run full pipeline
        result = deduplicate(300, fuzzy_threshold=0.8)

        # ASSERTION: Should find 2 exact + 1 fuzzy, merge all
        assert result["exact_duplicates"] == 1
        assert result["fuzzy_duplicates"] == 1
        assert result["merged_count"] == 2
        assert len(result["removed_ids"]) == 2

        # Verify DB state
        with get_db() as conn:
            count = conn.execute(
                "SELECT COUNT(*) as cnt FROM journey_sources WHERE user_id = 300"
            ).fetchone()

        # ASSERTION: 3 sources remain (5 inserted - 2 removed)
        assert count["cnt"] == 3
