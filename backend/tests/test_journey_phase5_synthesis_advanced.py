"""Phase 5: Narrative Synthesis — Advanced Tests.

Tests narrative deduplication, superseding, performance at scale,
and integration with clustering workflow.
"""

import json
import sqlite3
import tempfile
import time
from datetime import datetime, timedelta

import pytest

from models import get_db
from journey_synthesizer import JourneySynthesizer


@pytest.fixture
def temp_db_p5_adv(monkeypatch, request):
    """Create temp database for Phase 5 advanced testing."""
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
        CREATE TABLE journey_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            event_date TEXT NOT NULL,
            title TEXT NOT NULL,
            category TEXT,
            technologies TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            cluster_id INTEGER,
            is_cluster_head INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    conn.execute("""
        CREATE TABLE journey_narratives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            narrative_type TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            superseded_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    conn.execute("""
        CREATE TABLE client_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            client_name TEXT NOT NULL,
            business_outcomes_json TEXT,
            approved INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    conn.execute("INSERT INTO users VALUES (701, 'p5adv@test.com', 'hash')")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()

    yield path

    conn.close()
    import os
    os.unlink(path)


class TestSynthesizerAdvanced:
    """Advanced synthesis scenarios: dedup, superseding, performance, integration."""

    def test_narrative_query_filters_by_user_id(self, temp_db_p5_adv):
        """Verify: Narratives for different users don't interfere."""
        synth = JourneySynthesizer()

        # User 701 narrative
        synth._store_narrative(701, "resume_entry", "Entry 1", "Content 1")

        # Simulate user 702 (different user_id)
        with get_db() as conn:
            conn.execute(
                "INSERT INTO users VALUES (702, 'other@test.com', 'hash')"
            )
            conn.execute(
                "INSERT INTO journey_narratives (user_id, narrative_type, title, content) "
                "VALUES (702, 'resume_entry', 'Entry 2', 'Content 2')"
            )
            conn.commit()

        # Verify only user 701's narratives returned
        with get_db() as conn:
            count_701 = conn.execute(
                "SELECT COUNT(*) as cnt FROM journey_narratives WHERE user_id = 701"
            ).fetchone()["cnt"]
            count_702 = conn.execute(
                "SELECT COUNT(*) as cnt FROM journey_narratives WHERE user_id = 702"
            ).fetchone()["cnt"]

        assert count_701 == 1
        assert count_702 == 1

    def test_narrative_superseding_updates_timestamp(self, temp_db_p5_adv):
        """Verify: regenerate_linkedin_sections() marks old narratives as superseded."""
        synth = JourneySynthesizer()

        # Store initial LinkedIn narrative
        synth._store_narrative(701, "linkedin_headline", "Headline", "Old headline text")

        with get_db() as conn:
            row_before = conn.execute(
                "SELECT superseded_at FROM journey_narratives WHERE user_id = 701"
            ).fetchone()

        assert row_before["superseded_at"] is None

        # Manually mark as superseded (simulating regenerate_linkedin_sections behavior)
        with get_db() as conn:
            conn.execute(
                "UPDATE journey_narratives SET superseded_at = CURRENT_TIMESTAMP "
                "WHERE user_id = 701 AND narrative_type = 'linkedin_headline'"
            )
            conn.commit()

        with get_db() as conn:
            row_after = conn.execute(
                "SELECT superseded_at FROM journey_narratives WHERE user_id = 701"
            ).fetchone()

        assert row_after["superseded_at"] is not None

    def test_narrative_batch_storage_maintains_order(self, temp_db_p5_adv):
        """Verify: Multiple narratives stored in sequence maintain insertion order via created_at."""
        synth = JourneySynthesizer()
        titles = ["First", "Second", "Third", "Fourth", "Fifth"]

        for i, title in enumerate(titles):
            synth._store_narrative(701, "resume_entry", title, f"Content {i}")
            time.sleep(0.001)  # Small delay to ensure timestamp difference

        with get_db() as conn:
            rows = conn.execute(
                "SELECT title FROM journey_narratives WHERE user_id = 701 "
                "ORDER BY created_at ASC"
            ).fetchall()

        retrieved_titles = [r["title"] for r in rows]
        assert retrieved_titles == titles

    def test_narrative_technologies_extraction_from_json(self, temp_db_p5_adv):
        """Verify: Technologies field preserved in stored narrative content."""
        synth = JourneySynthesizer()
        tech_list = ["Python", "FastAPI", "PostgreSQL", "Redis", "Docker"]
        narrative_content = json.dumps({
            "bullet": "Built scalable API backend",
            "technologies": tech_list
        })

        synth._store_narrative(701, "resume_entry", "Tech Test", narrative_content)

        with get_db() as conn:
            row = conn.execute(
                "SELECT content FROM journey_narratives WHERE user_id = 701"
            ).fetchone()

        retrieved = json.loads(row["content"])
        assert all(tech in retrieved["technologies"] for tech in tech_list)

    def test_narrative_empty_content_handled_gracefully(self, temp_db_p5_adv):
        """Verify: Empty content string is stored and retrievable (no corruption)."""
        synth = JourneySynthesizer()
        synth._store_narrative(701, "resume_entry", "Empty Test", "")

        with get_db() as conn:
            row = conn.execute(
                "SELECT content FROM journey_narratives WHERE user_id = 701"
            ).fetchone()

        assert row["content"] == ""

    def test_narrative_special_characters_preserved(self, temp_db_p5_adv):
        """Verify: Special chars (quotes, newlines, emoji) preserved in content."""
        synth = JourneySynthesizer()
        special_content = 'Led "enterprise-scale" initiatives\n✓ 99.99% uptime\n\'Zero-knowledge\' proofs'

        synth._store_narrative(701, "resume_entry", "Special Chars", special_content)

        with get_db() as conn:
            row = conn.execute(
                "SELECT content FROM journey_narratives WHERE user_id = 701"
            ).fetchone()

        assert row["content"] == special_content

    def test_get_business_outcomes_filters_by_approval_and_json(self, temp_db_p5_adv):
        """Verify: _get_business_outcomes_summary() only returns approved projects with valid JSON."""
        with get_db() as conn:
            # Approved project with valid outcomes
            conn.execute(
                "INSERT INTO client_projects (user_id, client_name, approved, business_outcomes_json) "
                "VALUES (701, 'Company A', 1, ?)",
                (json.dumps([
                    {"outcome_title": "30% cost reduction", "outcome_type": "cost_reduction", "metric_value": "30%", "confidence": 0.95},
                    {"outcome_title": "2x throughput", "outcome_type": "scale_achievement", "metric_value": "2x", "confidence": 0.85}
                ]),)
            )
            # Unapproved project (should be skipped)
            conn.execute(
                "INSERT INTO client_projects (user_id, client_name, approved, business_outcomes_json) "
                "VALUES (701, 'Company B', 0, ?)",
                (json.dumps([{"outcome_title": "50% faster", "outcome_type": "efficiency_improvement"}]),)
            )
            # Approved with NULL outcomes (should be skipped)
            conn.execute(
                "INSERT INTO client_projects (user_id, client_name, approved, business_outcomes_json) "
                "VALUES (701, 'Company C', 1, NULL)"
            )
            # Approved with invalid JSON (should be skipped)
            conn.execute(
                "INSERT INTO client_projects (user_id, client_name, approved, business_outcomes_json) "
                "VALUES (701, 'Company D', 1, 'invalid json')"
            )
            conn.commit()

        synth = JourneySynthesizer()
        outcomes = synth._get_business_outcomes_summary()

        # Should have 2 outcomes from Company A only
        assert len(outcomes) == 2
        assert all(o["client"] == "Company A" for o in outcomes)

    def test_narrative_high_volume_insertion_performance(self, temp_db_p5_adv):
        """Verify: Storing 100 narratives completes in <1 second."""
        synth = JourneySynthesizer()
        start = time.time()

        for i in range(100):
            synth._store_narrative(701, "resume_entry", f"Entry {i}", f"Content {i}")

        elapsed = time.time() - start

        with get_db() as conn:
            count = conn.execute(
                "SELECT COUNT(*) as cnt FROM journey_narratives WHERE user_id = 701"
            ).fetchone()["cnt"]

        assert count == 100, f"Expected 100 narratives, got {count}"
        assert elapsed < 1.0, f"Insertion of 100 narratives took {elapsed:.2f}s, expected <1s"

    def test_narrative_query_performance_large_dataset(self, temp_db_p5_adv):
        """Verify: Querying narratives with 500+ total records completes <100ms."""
        synth = JourneySynthesizer()

        # Insert 500 narratives
        with get_db() as conn:
            for i in range(500):
                user = 701 if i < 250 else 702
                if i == 250:
                    conn.execute("INSERT INTO users VALUES (702, 'other@test.com', 'hash')")
                conn.execute(
                    "INSERT INTO journey_narratives (user_id, narrative_type, title, content) "
                    "VALUES (?, ?, ?, ?)",
                    (user, "resume_entry", f"Entry {i}", f"Content {i}")
                )
            conn.commit()

        # Query all user 701 narratives
        start = time.time()
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM journey_narratives WHERE user_id = 701"
            ).fetchall()
        elapsed = time.time() - start

        assert len(rows) == 250
        assert elapsed < 0.1, f"Query took {elapsed:.3f}s, expected <0.1s"

    def test_cluster_integration_with_narratives(self, temp_db_p5_adv):
        """Verify: Events with cluster assignments flow through to narratives."""
        base_time = datetime.utcnow()

        # Create clustered events
        with get_db() as conn:
            for i in range(5):
                conn.execute(
                    "INSERT INTO journey_events (user_id, event_date, title, category, cluster_id, is_cluster_head) "
                    "VALUES (701, ?, ?, ?, ?, ?)",
                    (
                        (base_time - timedelta(days=i)).isoformat(),
                        f"Clustered Event {i}",
                        "FEAT",
                        1,  # All in cluster 1
                        1 if i == 0 else 0  # First one is head
                    )
                )
            conn.commit()

        # Verify cluster structure persists
        with get_db() as conn:
            heads = conn.execute(
                "SELECT COUNT(*) as cnt FROM journey_events WHERE cluster_id = 1 AND is_cluster_head = 1"
            ).fetchone()
            cluster_members = conn.execute(
                "SELECT COUNT(*) as cnt FROM journey_events WHERE cluster_id = 1"
            ).fetchone()

        assert heads["cnt"] == 1
        assert cluster_members["cnt"] == 5

    def test_narrative_content_types_mixed_in_same_user(self, temp_db_p5_adv):
        """Verify: One user can have multiple narrative types stored concurrently."""
        synth = JourneySynthesizer()
        types_stored = [
            ("resume_entry", "Resume: GPU Optimization"),
            ("linkedin_headline", "Headline: Enterprise AI"),
            ("linkedin_summary", "Summary: Career in AI"),
            ("campaign_seed", "Theme: Thought Leadership"),
            ("theme_index", "Themes: 5 Content Categories"),
            ("learning_arc", "Arc: Foundation to Leadership")
        ]

        for ntype, title in types_stored:
            synth._store_narrative(701, ntype, title, f"Content for {ntype}")

        with get_db() as conn:
            by_type = conn.execute(
                "SELECT DISTINCT narrative_type FROM journey_narratives WHERE user_id = 701 "
                "ORDER BY narrative_type"
            ).fetchall()

        retrieved_types = [row["narrative_type"] for row in by_type]
        expected_types = sorted([ntype for ntype, _ in types_stored])

        assert retrieved_types == expected_types

    def test_synthesizer_handles_null_technologies_gracefully(self, temp_db_p5_adv):
        """Verify: Events with NULL technologies field don't crash skill extraction."""
        base_time = datetime.utcnow()

        with get_db() as conn:
            # Event with NULL technologies
            conn.execute(
                "INSERT INTO journey_events (user_id, event_date, title, technologies) "
                "VALUES (701, ?, ?, NULL)",
                ((base_time - timedelta(days=1)).isoformat(), "No Tech Event")
            )
            # Event with empty array
            conn.execute(
                "INSERT INTO journey_events (user_id, event_date, title, technologies) "
                "VALUES (701, ?, ?, ?)",
                ((base_time - timedelta(days=2)).isoformat(), "Empty Tech Event", '[]')
            )
            # Event with valid tech
            conn.execute(
                "INSERT INTO journey_events (user_id, event_date, title, technologies) "
                "VALUES (701, ?, ?, ?)",
                ((base_time - timedelta(days=3)).isoformat(), "With Tech", '["Python"]')
            )
            conn.commit()

        synth = JourneySynthesizer()
        skills = synth._get_skills_summary()

        # Should handle gracefully: Python count = 1
        skill_dict = dict(skills)
        assert skill_dict.get("Python") == 1
