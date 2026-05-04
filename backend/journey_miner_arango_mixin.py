"""ArangoMixin: writing approved journey data to ArangoDB knowledge graph."""

import hashlib
import json
import logging

logger = logging.getLogger(__name__)


class ArangoMixin:
    """Mixin providing ArangoDB write methods for JourneyMiner."""

    def _write_journey_to_arango(self, user_id):
        """Write approved journey data to ArangoDB knowledge graph."""
        try:
            from arango_client import get_arango_client

            arango = get_arango_client()
            if not arango.is_connected:
                logger.info("ArangoDB not connected, skipping graph write")
                return
        except Exception as e:
            logger.error("ArangoDB unavailable: %s", e)
            return

        # Write skills
        skills = self.get_skills(user_id=user_id)
        for skill in skills:
            arango.upsert_vertex(
                "ro_ai_skills",
                {
                    "name": skill["name"],
                    "first_seen": skill["first_seen"],
                    "last_seen": skill["last_seen"],
                    "event_count": skill["event_count"],
                    "categories": skill["categories"],
                },
                key_source=f"skill:{skill['name']}",
            )

        # Write milestone events
        from models import get_db

        with get_db() as conn:
            events = conn.execute(
                "SELECT * FROM journey_events "
                "WHERE category IN ('milestone', 'achievement') AND user_id = ? "
                "ORDER BY event_date",
                (user_id,),
            ).fetchall()

        for event in events:
            milestone_id = arango.upsert_vertex(
                "ro_journey_milestones",
                {
                    "title": event["title"],
                    "date": event["event_date"],
                    "description": event["description"],
                    "category": event["category"],
                },
                key_source=f"milestone:{event['title']}",
            )

            # Link to skills
            try:
                techs = json.loads(event["technologies"]) if event["technologies"] else []
            except (json.JSONDecodeError, TypeError):
                techs = []
            for tech in techs:
                skill_id = f"ro_ai_skills/{hashlib.sha1(f'skill:{tech}'.encode()).hexdigest()}"
                arango.upsert_edge("ro_milestone_demonstrated_skill", milestone_id, skill_id)
