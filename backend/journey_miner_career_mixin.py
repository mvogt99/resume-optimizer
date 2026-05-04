"""CareerMixin: governance, autonomy phase, AI platform metrics, storage, dedup."""

import hashlib
import json
import logging
import os

from journey_miner_utils import _extract_date

logger = logging.getLogger(__name__)


class CareerMixin:
    """Mixin providing career-data mining + storage methods for JourneyMiner."""

    def _mine_governance_achievements(self, user_id=0):
        """Mine resume-optimizer governance data from roadmap files."""
        count = 0
        ro_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        roadmap_dir = os.path.join(ro_root, "roadmap")

        # Mine SESSION_STATE.json for grade history
        state_file = os.path.join(roadmap_dir, "SESSION_STATE.json")
        if os.path.exists(state_file):
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)

                # Each grade history entry is a governance milestone
                for entry in state.get("grade_history", []):
                    content = (
                        f"Quality Grade: {entry.get('grade', '?')} | "
                        f"Tests: {entry.get('tests', 0)} | "
                        f"Notes: {entry.get('notes', '')}"
                    )
                    content_hash = hashlib.sha256(content.encode()).hexdigest()

                    self._store_source(
                        source_type="governance",
                        source_path=state_file,
                        content_hash=content_hash,
                        title=f"Grade {entry.get('grade', '?')}: {entry.get('notes', '')}",
                        content_preview=content,
                        full_text=content,
                        classification="governance",
                        event_date=entry.get("date", ""),
                        metadata={
                            "grade": entry.get("grade"),
                            "tests": entry.get("tests"),
                        },
                        user_id=user_id,
                    )
                    count += 1

            except Exception as e:
                logger.warning("Governance state mining failed: %s", e)

        # Mine QUALITY_ROADMAP and HONEST_ASSESSMENT
        for fname in ["QUALITY_ROADMAP_A_GRADE.md", "HONEST_ASSESSMENT.md"]:
            fpath = os.path.join(roadmap_dir, fname)
            if not os.path.exists(fpath):
                continue

            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()

                content_hash = hashlib.sha256(content.encode()).hexdigest()

                self._store_source(
                    source_type="governance",
                    source_path=fpath,
                    content_hash=content_hash,
                    title=f"Governance: {fname}",
                    content_preview=content[:500],
                    full_text=content,
                    classification="governance",
                    event_date="",
                    user_id=user_id,
                )
                count += 1
            except Exception:
                continue

        return count

    def _mine_autonomy_phases(self, user_id=0):
        """Mine autonomy proof documents from workdir/reports."""
        from journey_miner import WORKDIR_ROOT

        count = 0
        reports_dir = os.path.join(WORKDIR_ROOT, "reports")
        if not os.path.isdir(reports_dir):
            return 0

        # Target files for autonomy proof
        autonomy_files = [
            "AUTONOMY_PROOF_COMPLETE.md",
            "PHASE7_RESULTS.md",
        ]
        # Also scan for phase checkpoint files
        for fname in os.listdir(reports_dir):
            if fname.startswith("SESSION_CHECKPOINT_") or fname.startswith("PHASE"):
                autonomy_files.append(fname)

        seen = set()
        for fname in autonomy_files:
            if fname in seen:
                continue
            seen.add(fname)

            fpath = os.path.join(reports_dir, fname)
            if not os.path.exists(fpath):
                continue

            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except Exception:
                continue

            if len(content) < 20:
                continue

            content_hash = hashlib.sha256(content.encode()).hexdigest()
            event_date = _extract_date(fname) or ""
            title = os.path.splitext(fname)[0].replace("_", " ")

            self._store_source(
                source_type="autonomy_proof",
                source_path=fpath,
                content_hash=content_hash,
                title=f"Autonomy: {title}",
                content_preview=content[:500],
                full_text=content,
                classification="milestone",
                event_date=event_date,
                metadata={"proof_type": "autonomy_phase"},
                user_id=user_id,
            )
            count += 1

        return count

    def _mine_ai_platform_metrics(self, user_id=0):
        """W6: Mine agent_runs and FTAL harness stats as career journey events.

        Each agent type with sufficient usage gets a journey event capturing
        adoption date, quality scores, and acceptance pass rates. Demonstrates
        the user's hands-on experience operating an AI-assisted career platform.
        """
        try:
            from ai_journey_source import collect_all
        except ImportError:
            logger.warning("[JourneyMiner] ai_journey_source not available, skipping W6 mining")
            return 0

        events = collect_all(user_id)
        count = 0
        for ev in events:
            content = json.dumps(ev, sort_keys=True)
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            self._store_source(
                source_type=ev.get("source_type", "ai_platform"),
                source_path="ai_platform_metrics",
                content_hash=content_hash,
                title=ev.get("title", "AI Platform Event"),
                content_preview=ev.get("description", "")[:500],
                full_text=content,
                classification=ev.get("category", "ai_tooling"),
                event_date=ev.get("event_date", ""),
                metadata=ev.get("metadata", {}),
                user_id=user_id,
            )
            count += 1

        return count

    def _store_source(
        self,
        source_type,
        source_path,
        content_hash,
        title,
        content_preview,
        full_text,
        classification,
        event_date,
        metadata=None,
        user_id=0,
    ):
        from models import get_db

        with get_db() as conn:
            existing = conn.execute(
                "SELECT id FROM journey_sources WHERE content_hash = ? AND user_id = ?",
                (content_hash, user_id),
            ).fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO journey_sources "
                    "(source_type, source_path, content_hash, title, content_preview, "
                    "full_text, classification, event_date, metadata_json, user_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        source_type,
                        source_path,
                        content_hash,
                        title,
                        content_preview,
                        full_text,
                        classification,
                        event_date,
                        json.dumps(metadata or {}),
                        user_id,
                    ),
                )
                conn.commit()

    def _deduplicate(self, user_id=0):
        """Remove duplicate sources by content_hash, keeping the first."""
        from models import get_db

        with get_db() as conn:
            conn.execute(
                """
                DELETE FROM journey_sources WHERE user_id = ? AND id NOT IN (
                    SELECT MIN(id) FROM journey_sources WHERE user_id = ? GROUP BY content_hash
                )
            """,
                (user_id, user_id),
            )
            conn.commit()
