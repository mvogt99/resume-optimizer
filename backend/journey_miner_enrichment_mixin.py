"""EnrichmentMixin: teaching, FTAL history, cost economics, PersonaForge mining."""

import hashlib
import json
import logging
import os
import sqlite3

import requests

from journey_miner_utils import _extract_date
from models import get_db

try:
    from arango import ArangoClient as _ArangoClient
except ImportError:
    _ArangoClient = None

logger = logging.getLogger(__name__)


class EnrichmentMixin:
    """Mixin providing enrichment mining methods for JourneyMiner."""

    def _mine_teaching_documents(self, user_id=0):
        """Mine teaching documents from workdir/teaching/*.md."""
        from journey_miner import WORKDIR_ROOT

        teaching_dir = os.path.join(WORKDIR_ROOT, "teaching")
        if not os.path.isdir(teaching_dir):
            return 0

        count = 0
        for fname in os.listdir(teaching_dir):
            if not fname.endswith(".md"):
                continue

            fpath = os.path.join(teaching_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except Exception:
                continue

            if len(content) < 20:
                continue

            content_hash = hashlib.sha256(content.encode()).hexdigest()
            event_date = _extract_date(fname) or ""

            # Extract topic from filename (TEACHING-topic-hash.md)
            parts = fname.replace(".md", "").split("-", 1)
            title = parts[1] if len(parts) > 1 else fname

            self._store_source(
                source_type="teaching_doc",
                source_path=fpath,
                content_hash=content_hash,
                title=f"Teaching: {title}",
                content_preview=content[:500],
                full_text=content,
                classification="teaching",
                event_date=event_date,
                metadata={"source_system": "ftal_harness"},
                user_id=user_id,
            )
            count += 1

        return count

    def _mine_ftal_history(self, user_id=0):
        """Mine FTAL score history from ArangoDB learnings collection."""
        with get_db() as conn:
            row = conn.execute(
                "SELECT MAX(event_date) FROM journey_sources "
                "WHERE source_type=? AND user_id=?",
                ("ftal_history", user_id),
            ).fetchone()
            since_date = (row[0] or "1900-01-01") if row else "1900-01-01"

        if _ArangoClient is None:
            logger.warning("python-arango not installed; skipping FTAL ArangoDB mining")
            return 0

        count = 0
        try:
            client = _ArangoClient(
                hosts=os.environ.get("ARANGO_HOST", "http://localhost:8529")
            )
            db = client.db(
                "hybrid_ai",
                username="root",
                password=os.environ.get("ARANGO_PASSWORD", "hybrid_ai_root"),
            )

            # ISO datetime strings sort lexicographically — safe to compare against bare date
            cursor = db.aql.execute(
                "FOR doc IN learnings "
                "FILTER doc.created_at >= @since "
                "SORT doc.created_at ASC "
                "LIMIT 2000 RETURN doc",
                bind_vars={"since": since_date},
            )

            for doc in cursor:
                content = doc.get("content") or ""
                if len(content) < 20:
                    continue

                key = doc["_key"]
                created_at = doc.get("created_at", "")
                f_score = int(doc.get("f_score", 0))
                t_score = int(doc.get("t_score", 0))
                a_score = int(doc.get("a_score", 0))
                l_score = int(doc.get("l_score", 0))
                learning_type = doc.get("learning_type", "")
                domain = doc.get("domain", "")

                content_hash = hashlib.sha256(
                    f"ftal-arango:{key}:{content[:100]}".encode()
                ).hexdigest()

                self._store_source(
                    source_type="ftal_history",
                    source_path=f"arangodb/learnings/{key}",
                    content_hash=content_hash,
                    title=f"FTAL: {learning_type} - {domain}",
                    content_preview=content[:500],
                    full_text=content,
                    classification="ftal_task",
                    event_date=created_at[:10] if created_at else "",
                    metadata={
                        "learning_type": learning_type,
                        "domain": domain,
                        "source_system": "ftal_harness",
                        "f_score": f_score,
                        "t_score": t_score,
                        "a_score": a_score,
                        "l_score": l_score,
                        "gap": 100 - f_score - t_score - a_score - l_score,
                    },
                    user_id=user_id,
                )
                count += 1

        except Exception as e:
            logger.warning("FTAL ArangoDB mining failed: %s", e)
            return 0

        return count

    def _mine_cost_economics(self, user_id=0):
        """Mine cost tracking data from gateway cost_tracking.db."""
        from journey_miner import WORKDIR_ROOT

        cost_db = os.path.join(os.path.dirname(WORKDIR_ROOT), "gateway", "cost_tracking.db")
        count = 0

        if not os.path.exists(cost_db):
            return 0

        try:
            conn = sqlite3.connect(cost_db)
            conn.row_factory = sqlite3.Row

            # Discover actual table name (cost_tracking.db uses model_calls).
            # SAFE: cost_table is chosen from a hardcoded candidate list and
            # matched against DB-introspected names — no user input reaches it.
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            table_names = [t["name"] for t in tables]

            _COST_TABLE_CANDIDATES = ("model_calls", "cost_records", "costs")
            cost_table = None
            for candidate in _COST_TABLE_CANDIDATES:
                if candidate in table_names:
                    cost_table = candidate
                    break

            if cost_table:
                assert cost_table in _COST_TABLE_CANDIDATES  # static list, not user input
                rows = conn.execute(
                    f"SELECT * FROM {cost_table} ORDER BY rowid DESC LIMIT 500"  # noqa: S608
                ).fetchall()

                for row in rows:
                    d = dict(row)
                    content = json.dumps(d)
                    content_hash = hashlib.sha256(content.encode()).hexdigest()

                    model = d.get("model", d.get("model_id", "unknown"))
                    cost = d.get("cost", d.get("estimated_cost", 0))
                    ts = d.get("timestamp", d.get("created_at", ""))

                    # Convert Unix epoch timestamps to ISO date
                    event_date = ""
                    if ts:
                        try:
                            ts_float = float(ts)
                            if ts_float > 1_000_000_000:  # Unix epoch
                                from datetime import datetime, timezone

                                event_date = datetime.fromtimestamp(
                                    ts_float, tz=timezone.utc
                                ).strftime("%Y-%m-%d")
                            else:
                                event_date = str(ts)[:10]
                        except (ValueError, TypeError, OSError):
                            event_date = _extract_date(str(ts)) or ""

                    self._store_source(
                        source_type="cost_data",
                        source_path=f"cost_tracking/{d.get('id', d.get('rowid', ''))}",
                        content_hash=content_hash,
                        title=f"Cost: {model} (${cost})",
                        content_preview=content[:500],
                        full_text=content,
                        classification="cost_event",
                        event_date=event_date,
                        metadata={"model": model, "cost": cost},
                        user_id=user_id,
                    )
                    count += 1

            conn.close()

        except Exception as e:
            logger.warning("Cost economics mining failed: %s", e)

        # Also mine cost snapshot reports
        reports_dir = os.path.join(WORKDIR_ROOT, "reports")
        if os.path.isdir(reports_dir):
            for fname in os.listdir(reports_dir):
                if "cost_snapshot" in fname and fname.endswith(".json"):
                    fpath = os.path.join(reports_dir, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            content = f.read()
                        content_hash = hashlib.sha256(content.encode()).hexdigest()
                        event_date = _extract_date(fname) or ""

                        self._store_source(
                            source_type="cost_data",
                            source_path=fpath,
                            content_hash=content_hash,
                            title=f"Cost Snapshot: {fname}",
                            content_preview=content[:500],
                            full_text=content,
                            classification="cost_event",
                            event_date=event_date,
                            user_id=user_id,
                        )
                        count += 1
                    except Exception:
                        continue

        return count

    def _mine_personaforge(self, user_id=0):
        """Mine PersonaForge memories: ArangoDB career_profile + HTTP project_knowledge."""
        count = 0
        seen_hashes = set()

        # Path 1 — ArangoDB direct for career_profile/resume-optimizer (50 items, has dates)
        if _ArangoClient is not None:
            try:
                client = _ArangoClient(hosts=os.environ.get("ARANGO_HOST", "http://localhost:8529"))
                db = client.db("personaforge", username="root", password="hybrid_ai_root")
                cursor = db.aql.execute(
                    "FOR m IN memories FILTER m.user_id == 'resume-optimizer' "
                    "AND m.namespace == 'career_profile' RETURN m"
                )
                for doc in cursor:
                    content = doc.get("content", "")
                    if len(content) < 20:
                        continue
                    content_hash = hashlib.sha256(content.encode()).hexdigest()
                    if content_hash in seen_hashes:
                        continue
                    seen_hashes.add(content_hash)

                    category = (doc.get("metadata") or {}).get("category", "")
                    classification = (
                        "learning" if "teaching" in category
                        else "achievement" if "pattern" in category
                        else "development"
                    )
                    event_date = (doc.get("created_at") or "")[:10]
                    memory_id = doc.get("_key", "")

                    self._store_source(
                        source_type="personaforge",
                        source_path=f"personaforge/career_profile/{memory_id}",
                        content_hash=content_hash,
                        title=f"PersonaForge: {category} ({memory_id[:8]})",
                        content_preview=content[:500],
                        full_text=content,
                        classification=classification,
                        event_date=event_date,
                        metadata={
                            "namespace": "career_profile",
                            "category": category,
                            "memory_id": memory_id,
                        },
                        user_id=user_id,
                    )
                    count += 1
            except Exception as e:
                logger.warning("PersonaForge ArangoDB path failed: %s", e)

        # Path 2 — Retrieval API for project_knowledge/mike (targeted queries)
        _PF_URL = os.environ.get("PF_URL", "http://localhost:8090") + "/api/v1/retrieval/query"
        _QUERIES = [
            "enterprise architecture integration technology stack",
            "career achievement milestone delivery",
            "skills expertise leadership patterns",
        ]
        for query_text in _QUERIES:
            try:
                resp = requests.post(
                    _PF_URL,
                    json={
                        "user_id": "mike",
                        "namespace": "project_knowledge",
                        "query_text": query_text,
                        "limit": 20,
                        "include_states": ["candidate", "validated", "active"],
                        "min_confidence": 0.5,
                    },
                    timeout=15,
                )
                if resp.status_code != 200:
                    continue
                for item in resp.json().get("items", []):
                    content = item.get("content", "")
                    if len(content) < 20:
                        continue
                    content_hash = hashlib.sha256(content.encode()).hexdigest()
                    if content_hash in seen_hashes:
                        continue
                    seen_hashes.add(content_hash)

                    memory_id = item.get("memory_id", "")
                    self._store_source(
                        source_type="personaforge",
                        source_path=f"personaforge/project_knowledge/{memory_id}",
                        content_hash=content_hash,
                        title=f"PersonaForge: project knowledge ({memory_id[:8]})",
                        content_preview=content[:500],
                        full_text=content,
                        classification="development",
                        event_date="",
                        metadata={
                            "namespace": "project_knowledge",
                            "memory_id": memory_id,
                            "score": item.get("score", 0),
                        },
                        user_id=user_id,
                    )
                    count += 1
            except Exception as e:
                logger.warning("PersonaForge API query '%s' failed: %s", query_text, e)

        return count
