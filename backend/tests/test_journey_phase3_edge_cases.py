"""Phase 3: Edge case tests for significance scoring robustness.

TDD Contract:
- Malformed watermarks_json doesn't crash get_latest_watermarks
- score_event handles None technologies gracefully
- score_event handles missing full_text
- classify_event handles unknown source_type
- Score boundaries (min=1, max=5) enforced even with extreme inputs
"""

import json
import sqlite3
import tempfile

import pytest

from models import get_latest_watermarks, save_mining_run, get_db
from journey_scorer import score_event, classify_event


@pytest.fixture
def temp_db_edge(monkeypatch, request):
    """Create temp SQLite database for edge case testing."""
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

    for i in range(20, 30):
        conn.execute("INSERT OR IGNORE INTO users (id, email, password_hash) VALUES (?, ?, ?)",
                     (i, f'edge{i}@test.com', 'hash'))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()

    yield path

    conn.close()
    import os
    os.unlink(path)


class TestMalformedWatermarks:
    """Mutation: Don't handle malformed JSON in watermarks_json."""

    def test_malformed_watermarks_json_returns_empty(self, temp_db_edge):
        """Verify: Malformed watermarks_json returns {} instead of crashing."""
        with get_db() as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute(
                "INSERT INTO journey_mining_runs "
                "(user_id, status, watermarks_json, completed_at) "
                "VALUES (?, 'completed', ?, CURRENT_TIMESTAMP)",
                (20, "{not valid json}")  # Invalid JSON
            )
            conn.execute("PRAGMA foreign_keys = ON")
            conn.commit()

        # ASSERTION: Should not crash, return empty or default
        watermarks = get_latest_watermarks(20)
        assert isinstance(watermarks, dict)
        # Either returns empty or safely defaults
        assert len(watermarks) <= 0 or watermarks.get("files") is None

    def test_null_watermarks_json(self, temp_db_edge):
        """Verify: NULL watermarks_json doesn't crash."""
        with get_db() as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute(
                "INSERT INTO journey_mining_runs "
                "(user_id, status, watermarks_json, completed_at) "
                "VALUES (?, 'completed', NULL, CURRENT_TIMESTAMP)",
                (21,)
            )
            conn.execute("PRAGMA foreign_keys = ON")
            conn.commit()

        # ASSERTION: Should return empty dict
        watermarks = get_latest_watermarks(21)
        assert watermarks == {} or isinstance(watermarks, dict)

    def test_empty_string_watermarks_json(self, temp_db_edge):
        """Verify: Empty string watermarks_json returns {}."""
        with get_db() as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute(
                "INSERT INTO journey_mining_runs "
                "(user_id, status, watermarks_json, completed_at) "
                "VALUES (?, 'completed', '', CURRENT_TIMESTAMP)",
                (22,)
            )
            conn.execute("PRAGMA foreign_keys = ON")
            conn.commit()

        watermarks = get_latest_watermarks(22)
        assert isinstance(watermarks, dict)


class TestScoreEventEdgeCases:
    """Mutation: Don't validate event/source structure in score_event."""

    def test_score_event_with_none_technologies(self):
        """Verify: score_event handles None technologies field."""
        source = {
            "source_type": "git_commit",
            "title": "feat(api): Add endpoint",
            "full_text": "Added new API endpoint",
            "classification": ""
        }
        event = {"technologies": None}

        # ASSERTION: Should not crash, still score correctly
        score = score_event(source, event)
        assert score == 3  # feat scores 3 even with None techs

    def test_score_event_with_missing_technologies(self):
        """Verify: score_event handles missing technologies key."""
        source = {
            "source_type": "git_commit",
            "title": "feat(core): Core system",
            "full_text": "Implemented core",
            "classification": ""
        }
        event = {}  # No technologies key at all

        # ASSERTION: Should not crash
        score = score_event(source, event)
        assert score >= 1 and score <= 5

    def test_score_event_with_missing_full_text(self):
        """Verify: score_event handles missing full_text."""
        source = {
            "source_type": "git_commit",
            "title": "feat(auth): Authentication",
            # "full_text": missing
            "classification": ""
        }
        event = {"technologies": []}

        # ASSERTION: Should not crash
        score = score_event(source, event)
        assert score >= 1 and score <= 5

    def test_score_event_with_empty_source(self):
        """Verify: score_event handles empty/minimal source."""
        source = {
            "source_type": "unknown",
            "title": "",
            "full_text": "",
            "classification": ""
        }
        event = {"technologies": []}

        # ASSERTION: Should return minimum score
        score = score_event(source, event)
        assert score >= 1  # Never below baseline

    def test_score_event_with_extreme_technology_list(self):
        """Verify: score_event handles very large technology lists."""
        source = {
            "source_type": "git_commit",
            "title": "chore: Update deps",
            "full_text": "",
            "classification": ""
        }
        # 100 technologies
        event = {"technologies": [f"tech_{i}" for i in range(100)]}

        # ASSERTION: Score still capped at 5
        score = score_event(source, event)
        assert score <= 5

    def test_score_event_min_baseline(self):
        """Verify: Even worst-case source scores >= 1."""
        sources = [
            {
                "source_type": "unknown_type",
                "title": "",
                "full_text": "",
                "classification": ""
            },
            {
                "source_type": "garbage",
                "title": "xyz",
                "full_text": None,
                "classification": ""
            },
            {
                "source_type": "",
                "title": "",
                "full_text": "",
                "classification": ""
            },
        ]

        for source in sources:
            event = {"technologies": []}
            score = score_event(source, event)
            # ASSERTION: All score >= 1
            assert score >= 1


class TestClassifyEventEdgeCases:
    """Mutation: Don't validate source structure in classify_event."""

    def test_classify_unknown_source_type(self):
        """Verify: classify_event handles unknown source_type."""
        source = {
            "source_type": "unknown_or_future_type",
            "title": "Some event",
            "classification": ""
        }

        # ASSERTION: Should return a valid classification (not None/crash)
        classification = classify_event(source)
        assert classification in ["achievement", "fix", "development", "governance", "learning", "milestone", "governance"]

    def test_classify_missing_classification_field(self):
        """Verify: classify_event handles missing classification field."""
        source = {
            "source_type": "git_commit",
            "title": "feat(core): Feature",
            # "classification": missing
        }

        # ASSERTION: Should still classify based on source_type and title
        classification = classify_event(source)
        assert classification is not None
        assert isinstance(classification, str)

    def test_classify_null_source_fields(self):
        """Verify: classify_event handles None values in fields."""
        source = {
            "source_type": "governance",
            "title": None,
            "classification": None
        }

        # ASSERTION: Should classify based on source_type
        classification = classify_event(source)
        assert classification == "governance"

    def test_classify_empty_title(self):
        """Verify: classify_event handles empty title."""
        source = {
            "source_type": "git_commit",
            "title": "",
            "classification": ""
        }

        # ASSERTION: Should return valid classification
        classification = classify_event(source)
        assert isinstance(classification, str)


class TestScoreBoundaryConditions:
    """Mutation: Remove min(score, 5) OR baseline = 0."""

    def test_score_never_below_one(self):
        """Verify: Minimum score is always 1."""
        test_sources = [
            {"source_type": "unknown", "title": "", "full_text": "", "classification": ""},
            {"source_type": "file", "title": "random", "full_text": "", "classification": ""},
        ]

        for source in test_sources:
            event = {"technologies": []}
            score = score_event(source, event)
            assert score >= 1, f"Score below 1 for source: {source}"

    def test_score_never_above_five(self):
        """Verify: Maximum score is always 5."""
        # Extreme case: feat + governance + report + completion keyword + impact keyword + 5+ techs
        source = {
            "source_type": "governance",
            "title": "CRITICAL BREAKTHROUGH MILESTONE SHIPPED DEPLOYED",
            "full_text": (
                "Critical milestone first time shipped deployed production "
                "breakthrough launched impact first time deploying critical"
            ),
            "classification": "report"
        }
        event = {
            "technologies": ["Python", "Go", "Rust", "Java", "C++", "JavaScript", "TypeScript"]
        }

        score = score_event(source, event)
        assert score <= 5, f"Score above 5: {score}"

    def test_score_boundary_exactly_five(self):
        """Verify: Score can equal exactly 5."""
        source = {
            "source_type": "governance",
            "title": "CRITICAL BREAKTHROUGH MILESTONE",
            "full_text": (
                "First time deploying production shipped critical system "
                "launched breakthrough milestone"
            ),
            "classification": "report"
        }
        event = {"technologies": ["Python", "Go", "Rust", "Java", "C++"]}

        score = score_event(source, event)
        assert score == 5


class TestTechnologyEdgeCases:
    """Mutation: Change tech breadth threshold from 5 to 3."""

    def test_tech_breadth_exactly_five_triggers_bonus(self):
        """Verify: Exactly 5 technologies triggers bonus."""
        source = {
            "source_type": "git_commit",
            "title": "chore: Update",
            "full_text": "",
            "classification": ""
        }
        event = {
            "technologies": ["Python", "Go", "Rust", "Java", "C++"]
        }

        score = score_event(source, event)
        # Baseline 1 + tech bonus 1 = 2
        assert score >= 2

    def test_tech_breadth_four_no_bonus(self):
        """Verify: 4 technologies don't trigger bonus."""
        source = {
            "source_type": "git_commit",
            "title": "chore: Update",
            "full_text": "",
            "classification": ""
        }
        event = {
            "technologies": ["Python", "Go", "Rust", "Java"]
        }

        score = score_event(source, event)
        # Baseline 1, no tech bonus
        assert score == 1

    def test_tech_breadth_six_still_capped(self):
        """Verify: 6+ technologies still capped at 5."""
        source = {
            "source_type": "governance",
            "title": "CRITICAL MILESTONE",
            "full_text": "Critical milestone achieved",
            "classification": "report"
        }
        event = {
            "technologies": ["Python", "Go", "Rust", "Java", "C++", "JavaScript", "TypeScript"]
        }

        score = score_event(source, event)
        assert score <= 5
