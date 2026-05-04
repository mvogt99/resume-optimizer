"""
Phase 10: AI Journey Knowledge Mining.
Mines workdir/, Qdrant, ArangoDB, and git history to reconstruct
the user's AI/agentic journey. Builds timeline, skills, achievements.

Split into mixin modules to comply with 500-line file limit:
  journey_miner_mining_mixin.py   — local file, Qdrant, ArangoDB, git
  journey_miner_enrichment_mixin.py — teaching, FTAL, cost, PersonaForge
  journey_miner_career_mixin.py   — governance, autonomy, AI platform, storage
  journey_miner_timeline_mixin.py — timeline, narratives, getters
  journey_miner_arango_mixin.py   — ArangoDB write
  journey_miner_review_mixin.py   — review sessions, narrative interview
  journey_miner_utils.py          — standalone helper functions
"""

import json
import logging
import os

from batch_jobs import get_batch_manager  # noqa: E402
from journey_miner_arango_mixin import ArangoMixin
from journey_miner_career_mixin import CareerMixin
from journey_miner_enrichment_mixin import EnrichmentMixin
from journey_miner_mining_mixin import FileMiningMixin
from journey_miner_review_mixin import ReviewMixin
from journey_miner_timeline_mixin import TimelineMixin
from journey_miner_utils import (  # noqa: F401 — re-exported for callers
    _extract_date,
    _extract_technologies,
)
from models import get_latest_watermarks, save_mining_run

logger = logging.getLogger(__name__)

HARNESS_URL = os.environ.get("HARNESS_URL", "http://localhost:8000/api/harness/run")

# Paths to mine
WORKDIR_ROOT = os.environ.get(
    "JOURNEY_WORKDIR", "/home/mike/models/source/hybrid-ai-windows/workdir"
)
GIT_ROOT = os.environ.get("JOURNEY_GIT_ROOT", "/home/mike/models/source/hybrid-ai-windows")
QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
# Qdrant Cloud (CLOUDLIFT_ENV=aws) — mv-test-cluster, us-east-2
QDRANT_CLOUD_URL = os.environ.get(
    "QDRANT_CLOUD_URL",
    "https://fb46d143-3577-43a4-a9d5-c09ea6f2f59a.us-east-2-0.aws.cloud.qdrant.io",
)
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "")

# Classification rules by directory
DIR_CLASSIFICATIONS = {
    "reports": "report",
    "teaching": "teaching",
    "docs": "documentation",
    "tasks": "task_spec",
    "specs": "specification",
    "scripts": "script",
    "sessions": "session",
    "coordinators": "coordinator",
    "patches": "patch",
    "learnings": "learning",
}

_miner = None


def get_journey_miner():
    global _miner
    if _miner is None:
        _miner = JourneyMiner()
    return _miner


class JourneyMiner(
    FileMiningMixin,
    EnrichmentMixin,
    CareerMixin,
    TimelineMixin,
    ArangoMixin,
    ReviewMixin,
):
    """Singleton for AI journey knowledge mining pipeline."""

    def reset_sources(self, user_id):
        from models import get_db

        with get_db() as conn:
            sources_deleted = conn.execute(
                "SELECT COUNT(*) FROM journey_sources WHERE user_id = ?", (user_id,)
            ).fetchone()[0]
            events_deleted = conn.execute(
                "SELECT COUNT(*) FROM journey_events WHERE user_id = ?", (user_id,)
            ).fetchone()[0]
            conn.execute("DELETE FROM journey_sources WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM journey_events WHERE user_id = ?", (user_id,))
            # Narratives are user-authored content — preserved on reset
            conn.commit()
        return {"sources_deleted": sources_deleted, "events_deleted": events_deleted}

    def start_mining(self, user_id, opts=None):
        """Start background mining job.

        opts keys (all optional):
          since_date  — ISO date string, e.g. "2026-01-01"
          until_date  — ISO date string
          project_scope — list of scope tokens: "all" | "hybrid-ai-windows" | "resume-optimizer" | "workdir-only"
          sources     — list: "files" | "git" | "arango" | "enrichment" (default: all)
        """
        opts = opts or {}

        # Phase 1.2: Apply previous watermarks as defaults if not specified
        if not opts.get("since_date") and not opts.get("_force_full"):
            watermarks = get_latest_watermarks(user_id)
            if watermarks.get("files"):
                opts["since_date"] = watermarks["files"]

        manager = get_batch_manager()
        job_id = manager.create_job("journey_mining", user_id)
        manager.start_job(job_id, lambda jid: self._mining_worker(jid, user_id, opts))
        return job_id

    def _mining_worker(self, job_id, user_id, opts=None):
        opts = opts or {}
        sources = set(opts.get("sources") or ["files", "git", "arango", "enrichment"])
        manager = get_batch_manager()

        # Phase 1: Harvest local files
        file_count = 0
        if "files" in sources:
            manager.update_progress(job_id, {"phase": "harvesting_files", "total": 0, "processed": 0})
            file_count = self._harvest_local_files(job_id, manager, user_id=user_id, opts=opts)

        if manager.is_cancelled(job_id):
            return {"status": "cancelled"}

        # Phase 2: Scan ArangoDB (primary source of truth — Qdrant deprecated)
        arango_count = 0
        qdrant_count = 0
        if "arango" in sources:
            manager.update_progress(job_id, {"phase": "scanning_arango", "total": 0, "processed": 0})
            arango_count = self._scan_arango(user_id=user_id, opts=opts)

        if manager.is_cancelled(job_id):
            return {"status": "cancelled"}

        # Phase 4: Parse git history
        git_count = 0
        if "git" in sources:
            manager.update_progress(job_id, {"phase": "parsing_git", "total": 0, "processed": 0})
            git_count = self._parse_git_history(user_id=user_id, opts=opts)

        if manager.is_cancelled(job_id):
            return {"status": "cancelled"}

        # Phase 5: Enrichment mining (Phase 10 — 7 sources including AI platform metrics)
        enrichment_count = 0
        if "enrichment" in sources:
            manager.update_progress(job_id, {"phase": "enrichment_mining", "total": 7, "processed": 0})
            enrichment_count += self._mine_teaching_documents(user_id=user_id)
            manager.update_progress(job_id, {"phase": "enrichment_mining", "total": 7, "processed": 1})
            enrichment_count += self._mine_ftal_history(user_id=user_id)
            manager.update_progress(job_id, {"phase": "enrichment_mining", "total": 7, "processed": 2})
            enrichment_count += self._mine_cost_economics(user_id=user_id)
            manager.update_progress(job_id, {"phase": "enrichment_mining", "total": 7, "processed": 3})
            enrichment_count += self._mine_personaforge(user_id=user_id)
            manager.update_progress(job_id, {"phase": "enrichment_mining", "total": 7, "processed": 4})
            enrichment_count += self._mine_governance_achievements(user_id=user_id)
            manager.update_progress(job_id, {"phase": "enrichment_mining", "total": 7, "processed": 5})
            enrichment_count += self._mine_autonomy_phases(user_id=user_id)
            manager.update_progress(job_id, {"phase": "enrichment_mining", "total": 7, "processed": 6})
            enrichment_count += self._mine_ai_platform_metrics(user_id=user_id)
            manager.update_progress(job_id, {"phase": "enrichment_mining", "total": 7, "processed": 7})

        if manager.is_cancelled(job_id):
            return {"status": "cancelled"}

        # Phase 6: Deduplicate
        manager.update_progress(job_id, {"phase": "deduplicating", "total": 0, "processed": 0})
        self._deduplicate(user_id=user_id)

        # Phase 6: Build timeline
        manager.update_progress(job_id, {"phase": "building_timeline", "total": 0, "processed": 0})
        event_count = self._build_timeline(user_id=user_id)

        # Phase 7: Generate narratives
        manager.update_progress(
            job_id, {"phase": "generating_narratives", "total": 0, "processed": 0}
        )
        self._generate_narratives(user_id)

        # Phase 1.3-1.4: Save watermarks on completion
        from datetime import datetime
        watermarks = {
            "files": datetime.utcnow().isoformat(),
            "git": datetime.utcnow().isoformat(),
            "arango": datetime.utcnow().isoformat(),
        }
        save_mining_run(
            user_id=user_id,
            status="completed",
            opts_json=opts,
            watermarks_json=watermarks,
            sources_scanned=(file_count + arango_count + git_count),
            events_added=event_count,
            events_updated=0,
            events_deduplicated=0
        )

        return {
            "status": "completed",
            "files_harvested": file_count,
            "qdrant_records": qdrant_count,
            "arango_records": arango_count,
            "git_commits": git_count,
            "enrichment_records": enrichment_count,
            "timeline_events": event_count,
        }
