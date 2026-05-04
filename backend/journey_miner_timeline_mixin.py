"""TimelineMixin: timeline building, narrative generation, and public getters."""

import contextlib
import json
import logging

from journey_miner_utils import _extract_technologies
from journey_scorer import score_event, classify_event

logger = logging.getLogger(__name__)


class TimelineMixin:
    """Mixin providing timeline, skills, achievement and narrative methods."""

    def _build_timeline(self, user_id=0):
        """Group sources by date and create journey_events.

        Uses a staging table so existing events survive if rebuilding fails.
        """
        from models import get_db

        with get_db() as conn:
            # Build into staging table first — existing events remain untouched
            conn.execute("DROP TABLE IF EXISTS journey_events_staging")
            conn.execute(
                """
                CREATE TABLE journey_events_staging (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_date TEXT DEFAULT '',
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    category TEXT DEFAULT '',
                    source_ids TEXT DEFAULT '[]',
                    technologies TEXT DEFAULT '[]',
                    metrics TEXT DEFAULT '{}',
                    confidence REAL DEFAULT 0.5,
                    user_id INTEGER DEFAULT 0,
                    significance_score INTEGER DEFAULT 1,
                    cluster_id TEXT DEFAULT '',
                    is_cluster_head INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            sources = conn.execute(
                "SELECT * FROM journey_sources WHERE event_date != '' AND user_id = ? "
                "ORDER BY event_date",
                (user_id,),
            ).fetchall()

            # Group by date
            by_date = {}
            for s in sources:
                date = s["event_date"][:10]
                if date not in by_date:
                    by_date[date] = []
                by_date[date].append(dict(s))

            count = 0
            for date, items in sorted(by_date.items()):
                for item in items:
                    category = classify_event(item)
                    technologies = _extract_technologies(item.get("full_text", ""))

                    # Phase 3: Calculate significance score
                    event_dict = {"technologies": technologies}
                    significance = score_event(item, event_dict)

                    conn.execute(
                        "INSERT INTO journey_events_staging "
                        "(event_date, title, description, category, "
                        "source_ids, technologies, confidence, user_id, significance_score) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            date,
                            item["title"][:200],
                            (item.get("content_preview") or "")[:500],
                            category,
                            json.dumps([item["id"]]),
                            json.dumps(technologies),
                            0.8,
                            user_id,
                            significance,
                        ),
                    )
                    count += 1

            # Swap: only delete old events for this user
            conn.execute("DELETE FROM journey_events WHERE user_id = ?", (user_id,))
            conn.execute(
                "INSERT INTO journey_events "
                "(event_date, title, description, category, source_ids, technologies, "
                "metrics, confidence, user_id, significance_score, cluster_id, is_cluster_head, created_at) "
                "SELECT event_date, title, description, category, source_ids, technologies, "
                "metrics, confidence, user_id, significance_score, cluster_id, is_cluster_head, created_at "
                "FROM journey_events_staging"
            )
            conn.execute("DROP TABLE journey_events_staging")
            conn.commit()

        return count

    def _generate_narratives(self, user_id):
        """Generate narratives from timeline events using LLM."""
        from journey_synthesizer import JourneySynthesizer

        synthesizer = JourneySynthesizer()
        synthesizer.generate_all(user_id)

    # --- Public getters ---

    def get_timeline(self, page=1, per_page=50, category=None, user_id=None, min_significance=1):
        """Get timeline events with optional filtering.

        Args:
            page: pagination (1-indexed)
            per_page: events per page
            category: filter by event category
            user_id: filter by user
            min_significance: filter by significance score (1-5, default 1 = all)

        Returns:
            dict with events, total, page, per_page
        """
        from models import get_db

        with get_db() as conn:
            offset = (page - 1) * per_page
            base_where = "WHERE user_id = ?" if user_id is not None else "WHERE 1=1"
            base_params = [user_id] if user_id is not None else []

            # Phase 3.5: Add min_significance filtering
            if min_significance > 1:
                base_where += " AND significance_score >= ?"
                base_params.append(min_significance)

            if category:
                rows = conn.execute(
                    f"SELECT * FROM journey_events {base_where} AND category = ? "
                    "ORDER BY event_date DESC LIMIT ? OFFSET ?",
                    base_params + [category, per_page, offset],
                ).fetchall()
                total = conn.execute(
                    f"SELECT COUNT(*) FROM journey_events {base_where} AND category = ?",
                    base_params + [category],
                ).fetchone()[0]
            else:
                rows = conn.execute(
                    f"SELECT * FROM journey_events {base_where} "
                    "ORDER BY event_date DESC LIMIT ? OFFSET ?",
                    base_params + [per_page, offset],
                ).fetchall()
                total = conn.execute(
                    f"SELECT COUNT(*) FROM journey_events {base_where}",
                    base_params,
                ).fetchone()[0]

        events = []
        for r in rows:
            d = dict(r)
            for key in ("source_ids", "technologies", "metrics"):
                if isinstance(d.get(key), str):
                    with contextlib.suppress(json.JSONDecodeError, TypeError):
                        d[key] = json.loads(d[key])
            events.append(d)
        return {"events": events, "total": total, "page": page, "per_page": per_page}

    def get_skills(self, user_id=None):
        """Extract unique skills/technologies from timeline events."""
        from models import get_db

        with get_db() as conn:
            if user_id is not None:
                rows = conn.execute(
                    "SELECT technologies, event_date, category FROM journey_events "
                    "WHERE user_id = ? ORDER BY event_date",
                    (user_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT technologies, event_date, category FROM journey_events "
                    "WHERE user_id = 0 ORDER BY event_date"
                ).fetchall()

        skill_map = {}
        for row in rows:
            try:
                techs = json.loads(row[0]) if row[0] else []
            except (json.JSONDecodeError, TypeError):
                techs = []
            for tech in techs:
                if tech not in skill_map:
                    skill_map[tech] = {
                        "name": tech,
                        "first_seen": row[1],
                        "last_seen": row[1],
                        "event_count": 0,
                        "categories": set(),
                    }
                skill_map[tech]["last_seen"] = row[1]
                skill_map[tech]["event_count"] += 1
                if row[2]:
                    skill_map[tech]["categories"].add(row[2])

        result = []
        for skill in skill_map.values():
            skill["categories"] = list(skill["categories"])
            result.append(skill)
        result.sort(key=lambda x: x["event_count"], reverse=True)
        return result

    def get_achievements(self, user_id=None):
        """Get events classified as achievements/milestones."""
        from models import get_db

        with get_db() as conn:
            if user_id is not None:
                rows = conn.execute(
                    "SELECT * FROM journey_events "
                    "WHERE category IN ('milestone', 'achievement') AND user_id = ? "
                    "ORDER BY event_date DESC",
                    (user_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM journey_events "
                    "WHERE category IN ('milestone', 'achievement') AND user_id = 0 "
                    "ORDER BY event_date DESC"
                ).fetchall()
        events = []
        for r in rows:
            d = dict(r)
            for key in ("source_ids", "technologies", "metrics"):
                if isinstance(d.get(key), str):
                    with contextlib.suppress(json.JSONDecodeError, TypeError):
                        d[key] = json.loads(d[key])
            events.append(d)
        return events

    def get_narratives(self, user_id):
        import models

        with models.get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM journey_narratives WHERE user_id = ? "
                "ORDER BY narrative_type, created_at DESC",
                (user_id,),
            ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if isinstance(d.get("source_event_ids"), str):
                with contextlib.suppress(json.JSONDecodeError, TypeError):
                    d["source_event_ids"] = json.loads(d["source_event_ids"])
            result.append(d)
        return result

    def update_narratives(self, user_id, narratives):
        """Update narrative content (user edits before approval)."""
        import models

        with models.get_db() as conn:
            for n in narratives:
                if "id" in n and "content" in n:
                    conn.execute(
                        "UPDATE journey_narratives SET content = ?, "
                        "title = ? WHERE id = ? AND user_id = ?",
                        (n["content"], n.get("title", ""), n["id"], user_id),
                    )
            conn.commit()

    def approve_narratives(self, user_id, narrative_ids=None):
        """Approve narratives and write to ArangoDB."""
        import models

        with models.get_db() as conn:
            if narrative_ids:
                placeholders = ",".join("?" * len(narrative_ids))
                conn.execute(
                    f"UPDATE journey_narratives SET approved = 1, approved_at = CURRENT_TIMESTAMP "
                    f"WHERE id IN ({placeholders}) AND user_id = ?",
                    narrative_ids + [user_id],
                )
            else:
                conn.execute(
                    "UPDATE journey_narratives SET approved = 1, approved_at = CURRENT_TIMESTAMP "
                    "WHERE user_id = ?",
                    (user_id,),
                )
            conn.commit()

        self._write_journey_to_arango(user_id)
        return True
