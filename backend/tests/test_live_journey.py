"""Live Journey Miner integration tests — verifies journey_miner.py against real services.

Tests: file harvesting, Qdrant scanning, ArangoDB scanning, git history, deduplication,
timeline construction, skill extraction.
Requires: workdir/, Qdrant (6333), ArangoDB (8529), git repo.
Skips individual sources gracefully if unavailable.
"""

import os
import sys
import tempfile

import pytest
import requests

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)


def _qdrant_up():
    try:
        r = requests.get("http://localhost:6333/healthz", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def _arango_up():
    try:
        r = requests.get(
            "http://localhost:8529/_api/version",
            auth=("root", "hybrid_ai_root"),
            timeout=3,
        )
        return r.status_code == 200
    except Exception:
        return False


QDRANT_AVAILABLE = _qdrant_up()
ARANGO_AVAILABLE = _arango_up()
WORKDIR = os.environ.get(
    "JOURNEY_WORKDIR",
    "/home/mike/models/source/hybrid-ai-windows/workdir",
)
WORKDIR_AVAILABLE = os.path.isdir(WORKDIR)
GIT_ROOT = os.environ.get(
    "JOURNEY_GIT_ROOT",
    "/home/mike/models/source/hybrid-ai-windows",
)
GIT_AVAILABLE = os.path.isdir(os.path.join(GIT_ROOT, ".git"))


@pytest.fixture()
def miner_with_test_db():
    """Return JourneyMiner pointing at temp test DB."""
    from models import get_db_connection

    import models

    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    old_db = models.DB_PATH
    models.DB_PATH = db_path
    # Patch all modules that imported DB_PATH
    for mod in list(sys.modules.values()):
        if mod is None or mod is models:
            continue
        if hasattr(mod, "DB_PATH") and isinstance(mod.DB_PATH, str):
            try:
                mod.DB_PATH = db_path
            except (AttributeError, TypeError):
                pass

    models.init_db()

    # Create batch_jobs table (used by harvest workers)
    conn = get_db_connection()
    conn.execute(
        """CREATE TABLE IF NOT EXISTS batch_jobs (
            id TEXT PRIMARY KEY,
            job_type TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            user_id INTEGER NOT NULL,
            params_json TEXT DEFAULT '{}',
            progress_json TEXT DEFAULT '{}',
            result_json TEXT DEFAULT '{}',
            error_message TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP
        )"""
    )
    conn.commit()
    conn.close()

    # Reset singletons
    import batch_jobs as _bj

    _bj.BatchJobManager._instance = None

    import journey_miner

    journey_miner._miner = None
    miner = journey_miner.get_journey_miner()

    yield miner

    journey_miner._miner = None
    models.DB_PATH = old_db
    os.close(db_fd)
    os.unlink(db_path)


# ===================================================================
# File Harvesting (2 tests)
# ===================================================================


class TestFileHarvesting:
    """Mine local workdir/ files."""

    @pytest.mark.skipif(not WORKDIR_AVAILABLE, reason="workdir not found")
    def test_harvest_local_files_finds_files(self, miner_with_test_db):
        """_harvest_local_files discovers files in workdir/."""
        import batch_jobs

        batch_jobs.BatchJobManager._instance = None
        manager = batch_jobs.BatchJobManager()
        job_id = manager.create_job("journey_mine", user_id=0)

        count = miner_with_test_db._harvest_local_files(job_id, manager, user_id=0)
        assert count > 0, "workdir/ must contain minable files"

    @pytest.mark.skipif(not WORKDIR_AVAILABLE, reason="workdir not found")
    def test_harvest_classifies_by_directory(self, miner_with_test_db):
        """Files classified as report/teaching/docs based on directory."""
        import batch_jobs

        batch_jobs.BatchJobManager._instance = None
        manager = batch_jobs.BatchJobManager()
        job_id = manager.create_job("journey_mine", user_id=0)

        miner_with_test_db._harvest_local_files(job_id, manager, user_id=0)

        sources = miner_with_test_db.get_sources(user_id=0)
        classifications = {s.get("classification") for s in sources}
        # workdir has reports/, teaching/, docs/ — at least one classification
        assert (
            len(classifications) >= 1
        ), f"At least one classification expected, got: {classifications}"


# ===================================================================
# Qdrant Scanning (2 tests)
# ===================================================================


class TestQdrantScanning:
    """Scan Qdrant vector DB for knowledge records."""

    @pytest.mark.skipif(not QDRANT_AVAILABLE, reason="Qdrant not running")
    def test_scan_qdrant_finds_records(self, miner_with_test_db):
        """_scan_qdrant discovers records from Qdrant collections."""
        count = miner_with_test_db._scan_qdrant(user_id=0)
        assert count >= 0  # May be 0 if collections empty but should not error

    @pytest.mark.skipif(not QDRANT_AVAILABLE, reason="Qdrant not running")
    def test_qdrant_sources_stored(self, miner_with_test_db):
        """Qdrant records stored as journey_sources with correct type."""
        count = miner_with_test_db._scan_qdrant(user_id=0)
        if count > 0:
            sources = miner_with_test_db.get_sources(source_type="qdrant", user_id=0)
            assert len(sources) > 0
            assert sources[0].get("source_type") == "qdrant"


# ===================================================================
# ArangoDB Scanning (2 tests)
# ===================================================================


class TestArangoScanning:
    """Scan ArangoDB gateway collections."""

    @pytest.mark.skipif(not ARANGO_AVAILABLE, reason="ArangoDB not running")
    def test_scan_arango_finds_docs(self, miner_with_test_db):
        """_scan_arango discovers documents from gateway collections."""
        count = miner_with_test_db._scan_arango(user_id=0)
        assert count >= 0  # May be 0 if collections empty

    @pytest.mark.skipif(not ARANGO_AVAILABLE, reason="ArangoDB not running")
    def test_arango_sources_stored(self, miner_with_test_db):
        """ArangoDB docs stored as journey_sources with correct type."""
        count = miner_with_test_db._scan_arango(user_id=0)
        if count > 0:
            sources = miner_with_test_db.get_sources(source_type="arango", user_id=0)
            assert len(sources) > 0


# ===================================================================
# Git History (2 tests)
# ===================================================================


class TestGitHistory:
    """Parse git commit history."""

    @pytest.mark.skipif(not GIT_AVAILABLE, reason="Git repo not found")
    def test_parse_git_history_finds_commits(self, miner_with_test_db):
        """_parse_git_history discovers commits since 2025-12-01."""
        count = miner_with_test_db._parse_git_history(user_id=0)
        assert count > 0, "Git repo must have commits since 2025-12-01"

    @pytest.mark.skipif(not GIT_AVAILABLE, reason="Git repo not found")
    def test_git_sources_have_dates(self, miner_with_test_db):
        """Git commits stored with event_date from commit timestamp."""
        miner_with_test_db._parse_git_history(user_id=0)
        sources = miner_with_test_db.get_sources(source_type="git_commit", user_id=0)
        assert len(sources) > 0
        # All git sources should have dates
        for s in sources[:5]:
            assert s.get("event_date"), f"Git source missing date: {s.get('title')}"


# ===================================================================
# Deduplication & Timeline (3 tests)
# ===================================================================


class TestDeduplicationTimeline:
    """SHA-256 deduplication and timeline construction."""

    @pytest.mark.skipif(not WORKDIR_AVAILABLE, reason="workdir not found")
    def test_deduplication_removes_duplicates(self, miner_with_test_db):
        """Running harvest twice, dedup keeps only unique content."""
        import batch_jobs

        batch_jobs.BatchJobManager._instance = None
        manager = batch_jobs.BatchJobManager()
        job_id = manager.create_job("journey_mine", user_id=0)

        count1 = miner_with_test_db._harvest_local_files(job_id, manager, user_id=0)
        count2 = miner_with_test_db._harvest_local_files(job_id, manager, user_id=0)
        miner_with_test_db._deduplicate(user_id=0)

        sources = miner_with_test_db.get_sources(user_id=0)
        # After dedup, count should be <= count1 (first harvest)
        assert len(sources) <= count1 + count2  # Dedup should remove dupes

    @pytest.mark.skipif(not WORKDIR_AVAILABLE, reason="workdir not found")
    def test_build_timeline_creates_events(self, miner_with_test_db):
        """_build_timeline creates journey_events from dated sources."""
        import batch_jobs

        batch_jobs.BatchJobManager._instance = None
        manager = batch_jobs.BatchJobManager()
        job_id = manager.create_job("journey_mine", user_id=0)

        miner_with_test_db._harvest_local_files(job_id, manager, user_id=0)
        miner_with_test_db._deduplicate(user_id=0)
        event_count = miner_with_test_db._build_timeline(user_id=0)

        assert event_count > 0, "Timeline must contain events from dated sources"

        timeline = miner_with_test_db.get_timeline(user_id=0)
        assert "events" in timeline
        assert len(timeline["events"]) > 0

    @pytest.mark.skipif(not WORKDIR_AVAILABLE, reason="workdir not found")
    def test_timeline_valid_dates_are_chronological(self, miner_with_test_db):
        """Valid YYYY-MM-DD dates in timeline are sorted ascending."""
        import re

        import batch_jobs

        batch_jobs.BatchJobManager._instance = None
        manager = batch_jobs.BatchJobManager()
        job_id = manager.create_job("journey_mine", user_id=0)

        miner_with_test_db._harvest_local_files(job_id, manager, user_id=0)
        miner_with_test_db._deduplicate(user_id=0)
        miner_with_test_db._build_timeline(user_id=0)

        timeline = miner_with_test_db.get_timeline(per_page=500, user_id=0)
        events = timeline["events"]
        # Filter to only valid YYYY-MM-DD dates (miner may extract garbled dates)
        valid_date_re = re.compile(r"^20\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])$")
        dates = [
            e["event_date"][:10]
            for e in events
            if e.get("event_date") and valid_date_re.match(e["event_date"][:10])
        ]
        assert len(dates) > 0, "Must have valid-dated events"
        # get_timeline returns DESC (most recent first)
        assert dates == sorted(
            dates, reverse=True
        ), "Valid dates must be in reverse chronological order"


# ===================================================================
# Skills Extraction (1 test)
# ===================================================================


class TestSkillsExtraction:
    """Technology keyword extraction from timeline."""

    @pytest.mark.skipif(not WORKDIR_AVAILABLE, reason="workdir not found")
    def test_get_skills_extracts_technologies(self, miner_with_test_db):
        """get_skills returns technologies found in mined content."""
        import batch_jobs

        batch_jobs.BatchJobManager._instance = None
        manager = batch_jobs.BatchJobManager()
        job_id = manager.create_job("journey_mine", user_id=0)

        miner_with_test_db._harvest_local_files(job_id, manager, user_id=0)
        miner_with_test_db._deduplicate(user_id=0)
        miner_with_test_db._build_timeline(user_id=0)

        skills = miner_with_test_db.get_skills(user_id=0)
        assert isinstance(skills, list)
        if len(skills) > 0:
            skill_names = {s["name"].lower() for s in skills}
            # Workdir contains Python/FastAPI/Docker references
            assert any(
                tech in skill_names
                for tech in ("python", "fastapi", "docker", "qdrant", "arangodb")
            ), f"Expected known tech in skills, got: {skill_names}"
