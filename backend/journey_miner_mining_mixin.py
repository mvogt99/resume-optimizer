"""FileMiningMixin: local file, Qdrant, ArangoDB, and git mining methods."""

import hashlib
import json
import logging
import os
import subprocess

from journey_miner_utils import _extract_date

logger = logging.getLogger(__name__)


class FileMiningMixin:
    """Mixin providing source-harvesting methods for JourneyMiner."""

    def _harvest_local_files(self, job_id, manager, user_id=0, opts=None):
        """Walk workdir/ and ingest files as journey sources.

        opts filtering:
          since_date / until_date  — ISO date strings; skip files whose extracted date is outside range
          project_scope            — list containing "workdir-only" skips git roots;
                                     "hybrid-ai-windows" / "resume-optimizer" also walk those git trees
        """
        from journey_miner import WORKDIR_ROOT, DIR_CLASSIFICATIONS

        opts = opts or {}
        since_date = opts.get("since_date", "")
        until_date = opts.get("until_date", "")
        scope = set(opts.get("project_scope") or ["all"])

        # Build list of root directories to walk
        walk_roots = [WORKDIR_ROOT]
        if "all" in scope or "hybrid-ai-windows" in scope:
            hai_root = "/home/mike/models/source/hybrid-ai-windows"
            if os.path.isdir(hai_root):
                walk_roots.append(hai_root)
        if "all" in scope or "resume-optimizer" in scope:
            ro_root = "/home/mike/models/source/hybrid-ai-windows/applications/resume-optimizer"
            if os.path.isdir(ro_root) and ro_root not in walk_roots:
                walk_roots.append(ro_root)

        count = 0
        seen_paths: set = set()

        for walk_root in walk_roots:
            if not os.path.isdir(walk_root):
                continue
            for root, dirs, files in os.walk(walk_root):
                # Skip hidden dirs, __pycache__, node_modules, .venv
                dirs[:] = [
                    d for d in dirs
                    if not d.startswith(".") and d not in ("__pycache__", "node_modules", ".venv", "venv")
                ]

                for fname in files:
                    if manager.is_cancelled(job_id):
                        return count

                    fpath = os.path.join(root, fname)
                    if fpath in seen_paths:
                        continue
                    seen_paths.add(fpath)

                    ext = os.path.splitext(fname)[1].lower()
                    if ext not in (".md", ".txt", ".json", ".py", ".sh", ".yaml", ".yml"):
                        continue

                    try:
                        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                            content = f.read()
                    except Exception:
                        continue

                    if len(content) < 20:
                        continue

                    content_hash = hashlib.sha256(content.encode()).hexdigest()

                    # Classify by parent directory
                    rel_path = os.path.relpath(root, WORKDIR_ROOT)
                    first_dir = rel_path.split(os.sep)[0] if rel_path != "." else ""
                    classification = DIR_CLASSIFICATIONS.get(first_dir, "other")

                    # Extract date from filename (patterns: 20260101, 2026-01-01, 2026_01_01)
                    event_date = _extract_date(fname) or _extract_date(rel_path)

                    # Apply date range filter when event_date is extractable
                    if event_date:
                        if since_date and event_date < since_date[:10]:
                            continue
                        if until_date and event_date > until_date[:10]:
                            continue

                    # Title from filename
                    title = os.path.splitext(fname)[0].replace("_", " ").replace("-", " ")

                self._store_source(
                    source_type="local_file",
                    source_path=fpath,
                    content_hash=content_hash,
                    title=title,
                    content_preview=content[:500],
                    full_text=content,
                    classification=classification,
                    event_date=event_date or "",
                    user_id=user_id,
                )
                count += 1

                if count % 50 == 0:
                    manager.update_progress(
                        job_id,
                        {
                            "phase": "harvesting_files",
                            "total": 0,
                            "processed": count,
                        },
                    )

        return count

    def _scan_qdrant(self, user_id=0):
        """Read records from Qdrant collections.

        Local mode: reads hybrid-ai knowledge collections (localhost:6333)
        AWS mode: skips — hybrid-ai collections live in the local gateway,
                  not in the resume-optimizer Qdrant Cloud cluster.
                  Use cloudlift_vector_adapter for ro_* collections instead.
        """
        import os as _os  # noqa: PLC0415
        if _os.environ.get("CLOUDLIFT_ENV") == "aws":
            logger.info("[journey_miner] Skipping Qdrant scan in AWS mode (hybrid-ai collections are local-only)")
            return 0

        from journey_miner import QDRANT_HOST, QDRANT_PORT  # noqa: PLC0415

        count = 0
        try:
            from qdrant_client import QdrantClient  # noqa: PLC0415

            # Add timeout to fail fast if Qdrant is unavailable
            client = QdrantClient(
                host=QDRANT_HOST, port=QDRANT_PORT, timeout=5.0
            )
            collections = [
                "hybrid_ai_knowledge",
                "hybrid_ai_learnings",
                "hybrid_ai_rules",
            ]

            for coll_name in collections:
                try:
                    # Scroll through records
                    records, next_offset = client.scroll(
                        collection_name=coll_name,
                        limit=500,
                        with_payload=True,
                        with_vectors=False,
                    )

                    for record in records:
                        payload = record.payload or {}
                        content = payload.get("content", "") or payload.get("text", "")
                        if not content or len(content) < 20:
                            continue

                        content_hash = hashlib.sha256(content.encode()).hexdigest()
                        title = payload.get("title", "") or payload.get("category", coll_name)

                        self._store_source(
                            source_type="qdrant",
                            source_path=f"{coll_name}/{record.id}",
                            content_hash=content_hash,
                            title=str(title),
                            content_preview=content[:500],
                            full_text=content,
                            classification="knowledge_base",
                            event_date=payload.get("timestamp", ""),
                            user_id=user_id,
                        )
                        count += 1
                except Exception as e:
                    logger.warning("Qdrant collection %s error: %s", coll_name, e)

        except Exception as e:
            logger.error("Qdrant scan failed: %s", e)

        return count

    def _scan_arango(self, user_id=0, opts=None):
        """Read records from gateway ArangoDB vertex collections."""
        opts = opts or {}
        since_date = opts.get("since_date") or ""
        until_date = opts.get("until_date") or ""
        count = 0
        try:
            from arango import ArangoClient

            client = ArangoClient(hosts=os.environ.get("ARANGO_HOST", "http://localhost:8529"))
            db = client.db(
                os.environ.get("ARANGO_DB", "hybrid_ai"),
                username=os.environ.get("ARANGO_USER", "root"),
                password=os.environ.get("ARANGO_PASSWORD", "hybrid_ai_root"),
            )

            gateway_collections = [
                "learnings",
                "rules",
                "teachings",
                "incidents",
                "task_results",
            ]

            for coll_name in gateway_collections:
                try:
                    if not db.has_collection(coll_name):
                        continue
                    coll = db.collection(coll_name)
                    cursor = coll.all(limit=500)
                    for doc in cursor:
                        content = doc.get("content", "") or doc.get("text", "") or json.dumps(doc)
                        if len(content) < 20:
                            continue

                        content_hash = hashlib.sha256(content.encode()).hexdigest()
                        title = doc.get("title", "") or doc.get("type", coll_name)

                        self._store_source(
                            source_type="arango",
                            source_path=f"{coll_name}/{doc.get('_key', '')}",
                            content_hash=content_hash,
                            title=str(title),
                            content_preview=content[:500],
                            full_text=content,
                            classification="knowledge_base",
                            event_date=doc.get("timestamp", "") or doc.get("created_at", ""),
                            user_id=user_id,
                        )
                        # Apply date range filter on raw doc timestamps
                        raw_ts = (doc.get("timestamp", "") or doc.get("created_at", ""))[:10]
                        if raw_ts:
                            if since_date and raw_ts < since_date[:10]:
                                continue
                            if until_date and raw_ts > until_date[:10]:
                                continue
                        count += 1
                except Exception as e:
                    logger.warning("ArangoDB collection %s error: %s", coll_name, e)

        except Exception as e:
            logger.error("ArangoDB scan failed: %s", e)

        return count

    def _parse_git_history(self, user_id=0, opts=None):
        """Parse git log for commit history.

        opts filtering:
          since_date    — override default 2025-12-01 lower bound
          until_date    — upper date bound
          project_scope — list; "resume-optimizer" restricts paths to applications/resume-optimizer/
        """
        from journey_miner import GIT_ROOT

        opts = opts or {}
        since_date = opts.get("since_date") or "2025-12-01"
        until_date = opts.get("until_date") or ""
        scope = set(opts.get("project_scope") or ["all"])

        # Build git log command
        cmd = ["git", "log", f"--since={since_date}", "--format=%H|%aI|%s", "--stat"]
        if until_date:
            cmd.append(f"--until={until_date}")

        # Path filters
        path_filters = []
        if "resume-optimizer" in scope and "all" not in scope and "hybrid-ai-windows" not in scope:
            path_filters.append("applications/resume-optimizer/")
        if path_filters:
            cmd.append("--")
            cmd.extend(path_filters)

        count = 0
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=GIT_ROOT,
                timeout=30,
            )
            if result.returncode != 0:
                return 0

            current_commit = None
            stat_lines = []

            for line in result.stdout.split("\n"):
                if "|" in line and line.count("|") >= 2:
                    parts = line.split("|", 2)
                    if len(parts[0]) == 40:  # SHA hash
                        # Save previous commit
                        if current_commit:
                            self._save_git_commit(current_commit, stat_lines, user_id=user_id)
                            count += 1
                        current_commit = {
                            "hash": parts[0],
                            "date": parts[1],
                            "message": parts[2],
                        }
                        stat_lines = []
                        continue

                if current_commit and line.strip():
                    stat_lines.append(line.strip())

            # Save last commit
            if current_commit:
                self._save_git_commit(current_commit, stat_lines, user_id=user_id)
                count += 1

        except Exception as e:
            logger.warning("Git parse failed: %s", e)

        return count

    def _save_git_commit(self, commit, stat_lines, user_id=0):
        content = f"Commit: {commit['message']}\n\nFiles changed:\n" + "\n".join(stat_lines[:20])
        content_hash = hashlib.sha256(commit["hash"].encode()).hexdigest()

        # Extract date (ISO format)
        event_date = commit["date"][:10] if commit["date"] else ""

        self._store_source(
            source_type="git_commit",
            source_path=commit["hash"],
            content_hash=content_hash,
            title=commit["message"],
            content_preview=content[:500],
            full_text=content,
            classification="commit",
            event_date=event_date,
            user_id=user_id,
        )
