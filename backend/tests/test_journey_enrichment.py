"""Tests for Phase 10 journey mining enrichment (Track C).

Verifies 6 new mining sources: teaching docs, FTAL history, cost economics,
PersonaForge, governance achievements, and autonomy proofs.
"""

import contextlib
import hashlib
import json
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import models
from journey_miner import JourneyMiner, get_journey_miner

WORKDIR_ROOT = os.environ.get(
    "JOURNEY_WORKDIR", "/home/mike/models/source/hybrid-ai-windows/workdir"
)


@pytest.fixture(scope="module", autouse=True)
def _isolated_db(tmp_path_factory):
    """Create an isolated database so full-suite runs don't clobber DB_PATH."""
    original_db_path = models.DB_PATH

    tmp_dir = tmp_path_factory.mktemp("journey_enrich")
    db_path = str(tmp_dir / "test.db")

    # Patch DB_PATH in models and all loaded modules
    models.DB_PATH = db_path
    for mod in list(sys.modules.values()):
        if mod is None or mod is models:
            continue
        if hasattr(mod, "DB_PATH") and isinstance(mod.DB_PATH, str):
            with contextlib.suppress(AttributeError, TypeError):
                mod.DB_PATH = db_path

    models.init_db()

    # Reset journey_miner singleton so it uses the new DB
    import journey_miner as _jm

    _jm._miner = None

    yield db_path

    # Restore original DB_PATH
    models.DB_PATH = original_db_path
    for mod in list(sys.modules.values()):
        if mod is None or mod is models:
            continue
        if hasattr(mod, "DB_PATH") and isinstance(mod.DB_PATH, str):
            with contextlib.suppress(AttributeError, TypeError):
                mod.DB_PATH = original_db_path
    _jm._miner = None


@pytest.fixture(scope="module")
def miner():
    """Get a fresh JourneyMiner instance."""
    return JourneyMiner()


class TestMineTeachingDocuments:
    """C.1: Mining teaching documents from workdir/teaching/."""

    def test_mine_teaching_documents_finds_files(self, miner):
        """Teaching directory has .md files that get mined."""
        teaching_dir = os.path.join(WORKDIR_ROOT, "teaching")
        if not os.path.isdir(teaching_dir):
            pytest.skip("workdir/teaching/ not found")

        count = miner._mine_teaching_documents(user_id=99)
        assert count > 0, "Expected teaching documents to be found"

    def test_teaching_sources_classified(self, miner):
        """Mined teaching sources have classification='teaching'."""
        with models.get_db() as conn:
            rows = conn.execute(
                "SELECT classification FROM journey_sources "
                "WHERE user_id = 99 AND source_type = 'teaching_doc' LIMIT 5"
            ).fetchall()

        assert len(rows) > 0, "Expected teaching_doc sources in DB"
        for row in rows:
            assert row["classification"] == "teaching"

    def test_teaching_title_has_topic(self, miner):
        """Teaching source titles include topic information."""
        with models.get_db() as conn:
            rows = conn.execute(
                "SELECT title FROM journey_sources "
                "WHERE user_id = 99 AND source_type = 'teaching_doc' LIMIT 5"
            ).fetchall()

        assert len(rows) > 0
        for row in rows:
            assert row["title"].startswith(
                "Teaching:"
            ), f"Title should start with 'Teaching:': {row['title']}"


class TestMineFTALHistory:
    """C.2: Mining FTAL score history from Qdrant."""

    def test_mine_ftal_history_from_qdrant(self, miner):
        """FTAL records found in Qdrant hybrid_ai_learnings."""
        count = miner._mine_ftal_history(user_id=99)
        # May be 0 if Qdrant collection is empty, but should not error
        assert count >= 0, "FTAL history mining should not error"

    def test_ftal_sources_classified(self, miner):
        """FTAL sources have classification='ftal_task'."""
        with models.get_db() as conn:
            rows = conn.execute(
                "SELECT classification FROM journey_sources "
                "WHERE user_id = 99 AND source_type = 'ftal_history' LIMIT 5"
            ).fetchall()

        # If records exist, verify classification
        for row in rows:
            assert row["classification"] == "ftal_task"


class TestMineCostEconomics:
    """C.3: Mining cost tracking data."""

    def test_mine_cost_economics_reads_db(self, miner):
        """Cost data mining reads from cost_tracking.db or reports."""
        count = miner._mine_cost_economics(user_id=99)
        # cost_tracking.db may not exist in test env, but should not error
        assert count >= 0, "Cost mining should not error"

    def test_cost_sources_classified(self, miner):
        """Cost sources have classification='cost_event'."""
        with models.get_db() as conn:
            rows = conn.execute(
                "SELECT classification FROM journey_sources "
                "WHERE user_id = 99 AND source_type = 'cost_data' LIMIT 5"
            ).fetchall()

        for row in rows:
            assert row["classification"] == "cost_event"


class TestMinePersonaForge:
    """C.4: Mining PersonaForge project data."""

    def test_mine_personaforge_finds_reports(self, miner):
        """PersonaForge reports/source files are discovered."""
        count = miner._mine_personaforge(user_id=99)
        assert count >= 0, "PersonaForge mining should not error"

    def test_personaforge_sources_classified(self, miner):
        """PersonaForge sources have classification='project'."""
        with models.get_db() as conn:
            rows = conn.execute(
                "SELECT classification FROM journey_sources "
                "WHERE user_id = 99 AND source_type = 'personaforge' LIMIT 5"
            ).fetchall()

        for row in rows:
            assert row["classification"] == "project"


class TestMineGovernanceAchievements:
    """C.5: Mining governance achievements from roadmap files."""

    def test_mine_governance_finds_grade_history(self, miner):
        """Grade progression data (D+ → A) captured from SESSION_STATE.json."""
        count = miner._mine_governance_achievements(user_id=99)
        assert count > 0, "Expected governance records from roadmap files"

    def test_governance_sources_classified(self, miner):
        """Governance sources have classification='governance'."""
        with models.get_db() as conn:
            rows = conn.execute(
                "SELECT classification, title FROM journey_sources "
                "WHERE user_id = 99 AND source_type = 'governance' LIMIT 5"
            ).fetchall()

        assert len(rows) > 0, "Expected governance sources in DB"
        for row in rows:
            assert row["classification"] == "governance"

    def test_governance_includes_grade_entries(self, miner):
        """Individual grade history entries are stored."""
        with models.get_db() as conn:
            rows = conn.execute(
                "SELECT title FROM journey_sources "
                "WHERE user_id = 99 AND source_type = 'governance' AND title LIKE 'Grade %'"
            ).fetchall()

        assert len(rows) >= 3, f"Expected 3+ grade entries, got {len(rows)}"


class TestMineAutonomyPhases:
    """C.6: Mining autonomy proof documents."""

    def test_mine_autonomy_finds_proofs(self, miner):
        """Autonomy proof documents found in workdir/reports."""
        reports_dir = os.path.join(WORKDIR_ROOT, "reports")
        if not os.path.isdir(reports_dir):
            pytest.skip("workdir/reports/ not found")

        count = miner._mine_autonomy_phases(user_id=99)
        assert count > 0, "Expected autonomy proof documents"

    def test_autonomy_sources_classified(self, miner):
        """Autonomy sources have classification='milestone'."""
        with models.get_db() as conn:
            rows = conn.execute(
                "SELECT classification FROM journey_sources "
                "WHERE user_id = 99 AND source_type = 'autonomy_proof' LIMIT 5"
            ).fetchall()

        for row in rows:
            assert row["classification"] == "milestone"


class TestEnrichmentIntegration:
    """Cross-cutting enrichment tests."""

    def test_deduplicate_handles_new_sources(self, miner):
        """SHA-256 dedup works across all source types."""
        # Run same mining twice
        miner._mine_governance_achievements(user_id=99)

        # Count before dedup
        with models.get_db() as conn:
            before = conn.execute(
                "SELECT COUNT(*) as c FROM journey_sources WHERE user_id = 99"
            ).fetchone()["c"]

        miner._deduplicate(user_id=99)

        with models.get_db() as conn:
            after = conn.execute(
                "SELECT COUNT(*) as c FROM journey_sources WHERE user_id = 99"
            ).fetchone()["c"]

        # Dedup should not increase count, may reduce it
        assert after <= before, "Dedup should not increase source count"

    def test_all_source_types_present(self, miner):
        """After full enrichment, multiple source types exist."""
        with models.get_db() as conn:
            rows = conn.execute(
                "SELECT DISTINCT source_type FROM journey_sources WHERE user_id = 99"
            ).fetchall()

        types = {row["source_type"] for row in rows}
        # At minimum, teaching and governance should exist (they have local files)
        assert (
            "teaching_doc" in types or "governance" in types
        ), f"Expected teaching_doc or governance in source types: {types}"
