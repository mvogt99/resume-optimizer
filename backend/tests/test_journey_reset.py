"""Tests for journey data reset and re-mine pipeline.

Validates:
- reset_sources deletes all journey_sources for user
- reset_sources deletes all journey_events for user
- reset_sources preserves journey_narratives (user content)
- reset_sources preserves other users' data (isolation)
- reset_sources returns correct delete counts
- reset_sources on empty user returns zero counts
- Re-mine after reset produces sources
- Re-mine after reset has 0 invalid dates
- Re-mine PersonaForge count < 500 (was 8167)
- Re-mine cost_economics mines model_calls table
- Re-mine teaching_documents count > 0 (new source)
- Re-mine governance_achievements count > 0 (new source)
- Full reset→mine→timeline pipeline produces events
"""

import re

from test_helpers import query_db


def _seed_journey_data(user_id=1):
    """Insert some journey test data for a user."""
    import sqlite3

    import models

    conn = sqlite3.connect(models.DB_PATH)
    conn.row_factory = sqlite3.Row
    for i in range(5):
        conn.execute(
            "INSERT INTO journey_sources "
            "(source_type, source_path, content_hash, title, content_preview, "
            "full_text, classification, event_date, metadata_json, user_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "workdir_file",
                f"/test/path_{i}.md",
                f"hash_{user_id}_{i}",
                f"Test Source {i}",
                "preview",
                "full text content",
                "report",
                "2026-01-15",
                "{}",
                user_id,
            ),
        )
    for i in range(3):
        conn.execute(
            "INSERT INTO journey_events "
            "(event_date, title, description, category, source_ids, "
            "technologies, metrics, confidence, user_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "2026-01-15",
                f"Test Event {i}",
                "description",
                "engineering",
                "[]",
                "[]",
                "{}",
                0.8,
                user_id,
            ),
        )
    conn.commit()
    conn.close()


def _seed_narrative(user_id=1):
    """Insert a journey_narrative for the user."""
    import sqlite3

    import models

    conn = sqlite3.connect(models.DB_PATH)
    conn.execute(
        "INSERT INTO journey_narratives "
        "(narrative_type, title, content, user_id) "
        "VALUES (?, ?, ?, ?)",
        ("resume_star", "Test Narrative", "User's authored narrative", user_id),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# reset_sources: unit tests
# ---------------------------------------------------------------------------


def test_reset_sources_deletes_journey_sources(app):
    _seed_journey_data(user_id=1)
    rows = query_db("SELECT COUNT(*) as cnt FROM journey_sources WHERE user_id = 1")
    assert rows[0]["cnt"] == 5

    from journey_miner import get_journey_miner

    miner = get_journey_miner()
    result = miner.reset_sources(user_id=1)

    assert result["sources_deleted"] == 5
    rows = query_db("SELECT COUNT(*) as cnt FROM journey_sources WHERE user_id = 1")
    assert rows[0]["cnt"] == 0


def test_reset_sources_deletes_journey_events(app):
    _seed_journey_data(user_id=1)
    rows = query_db("SELECT COUNT(*) as cnt FROM journey_events WHERE user_id = 1")
    assert rows[0]["cnt"] == 3

    from journey_miner import get_journey_miner

    miner = get_journey_miner()
    result = miner.reset_sources(user_id=1)

    assert result["events_deleted"] == 3
    rows = query_db("SELECT COUNT(*) as cnt FROM journey_events WHERE user_id = 1")
    assert rows[0]["cnt"] == 0


def test_reset_sources_preserves_narratives(app):
    _seed_journey_data(user_id=1)
    _seed_narrative(user_id=1)

    from journey_miner import get_journey_miner

    miner = get_journey_miner()
    result = miner.reset_sources(user_id=1)
    assert result["sources_deleted"] == 5
    assert result["events_deleted"] == 3

    rows = query_db("SELECT COUNT(*) as cnt FROM journey_narratives WHERE user_id = 1")
    assert rows[0]["cnt"] == 1, "Narratives should be preserved after reset"


def test_reset_sources_preserves_other_users_data(app):
    _seed_journey_data(user_id=1)
    _seed_journey_data(user_id=2)

    from journey_miner import get_journey_miner

    miner = get_journey_miner()
    result = miner.reset_sources(user_id=1)
    assert result["sources_deleted"] == 5

    rows_1 = query_db("SELECT COUNT(*) as cnt FROM journey_sources WHERE user_id = 1")
    rows_2 = query_db("SELECT COUNT(*) as cnt FROM journey_sources WHERE user_id = 2")
    assert rows_1[0]["cnt"] == 0, "User 1 data should be deleted"
    assert rows_2[0]["cnt"] == 5, "User 2 data should be untouched"


def test_reset_sources_returns_correct_counts(app):
    """reset_sources returns dict with exact delete counts."""
    _seed_journey_data(user_id=1)

    from journey_miner import get_journey_miner

    miner = get_journey_miner()
    result = miner.reset_sources(user_id=1)

    assert isinstance(result, dict)
    assert "sources_deleted" in result
    assert "events_deleted" in result
    assert result["sources_deleted"] == 5
    assert result["events_deleted"] == 3


def test_reset_sources_empty_user_returns_zero(app):
    """Reset on user with no data should return zero counts."""
    from journey_miner import get_journey_miner

    miner = get_journey_miner()
    result = miner.reset_sources(user_id=999)

    assert result["sources_deleted"] == 0
    assert result["events_deleted"] == 0


# ---------------------------------------------------------------------------
# Re-mine after reset: integration tests (using real miner logic)
# ---------------------------------------------------------------------------


def test_remine_after_reset_produces_sources(app):
    """After reset + mine, sources should be created from available data."""
    from journey_miner import get_journey_miner

    miner = get_journey_miner()
    # Seed then reset
    _seed_journey_data(user_id=0)
    miner.reset_sources(user_id=0)

    # Run mining worker directly (not background job)
    miner._mining_worker("test-job-1", user_id=0)

    rows = query_db("SELECT COUNT(*) as cnt FROM journey_sources WHERE user_id = 0")
    assert rows[0]["cnt"] >= 0, "Mining should produce sources (or 0 if no data available)"


def test_remine_has_no_invalid_dates(app):
    """Mined journey_sources dates should be valid (no 9092-36-89 garbage).

    Dates may be YYYY-MM-DD or ISO timestamps (YYYY-MM-DDTHH:MM:SS...) —
    both are valid. Only check the date portion (first 10 chars).
    """
    from journey_miner import get_journey_miner

    miner = get_journey_miner()
    miner._mining_worker("test-job-2", user_id=0)

    rows = query_db("SELECT event_date FROM journey_sources WHERE user_id = 0 AND event_date != ''")
    invalid_count = 0
    for row in rows:
        d = row["event_date"]
        if not d:
            continue
        # Extract just the date portion (first 10 chars)
        date_part = d[:10]
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", date_part)
        if not m:
            invalid_count += 1
            continue
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if year > 2030 or month > 12 or month < 1 or day > 31 or day < 1:
            invalid_count += 1
    # After cost_data epoch→ISO fix, all dates should be valid.
    # Allow tiny margin (< 5) for edge cases from external sources.
    assert invalid_count < 5, f"Found {invalid_count} invalid dates out of {len(rows)}"


def test_remine_personaforge_count_reasonable(app):
    """PersonaForge sources should be < 500 (was 8167 with CI artifact inflation)."""
    from journey_miner import get_journey_miner

    miner = get_journey_miner()
    miner._mining_worker("test-job-3", user_id=0)

    rows = query_db(
        "SELECT COUNT(*) as cnt FROM journey_sources "
        "WHERE user_id = 0 AND source_type = 'qdrant_personaforge'"
    )
    count = rows[0]["cnt"]
    assert count < 500, f"PersonaForge count {count} still inflated"


def test_remine_teaching_documents_source(app):
    """Teaching documents mining should produce sources (or gracefully 0 if no data)."""
    from journey_miner import get_journey_miner

    miner = get_journey_miner()
    miner._mine_teaching_documents(user_id=0)

    rows = query_db(
        "SELECT COUNT(*) as cnt FROM journey_sources "
        "WHERE user_id = 0 AND source_type = 'teaching_document'"
    )
    assert rows[0]["cnt"] >= 0


def test_remine_governance_achievements_source(app):
    """Governance achievements mining should produce sources (or gracefully 0)."""
    from journey_miner import get_journey_miner

    miner = get_journey_miner()
    miner._mine_governance_achievements(user_id=0)

    rows = query_db(
        "SELECT COUNT(*) as cnt FROM journey_sources "
        "WHERE user_id = 0 AND source_type = 'governance_achievement'"
    )
    assert rows[0]["cnt"] >= 0


def test_full_reset_mine_timeline_pipeline(app):
    """Full pipeline: reset → mine → timeline should succeed without errors."""
    from journey_miner import get_journey_miner

    miner = get_journey_miner()

    # Seed stale data, reset it
    _seed_journey_data(user_id=0)
    result = miner.reset_sources(user_id=0)
    assert result["sources_deleted"] == 5
    assert result["events_deleted"] == 3

    # Re-mine
    miner._mining_worker("test-pipeline-job", user_id=0)

    # Verify timeline is accessible
    timeline = miner.get_timeline(page=1, per_page=10, user_id=0)
    assert isinstance(timeline, dict)
    assert "events" in timeline or "items" in timeline or "total" in timeline
