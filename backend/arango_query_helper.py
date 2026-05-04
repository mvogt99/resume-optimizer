"""CT-4: Query helper for ro_* context injection at inference time.

Provides agent-specific query methods to fetch knowledge graph data.
Results are formatted as human-readable context strings for prompt injection.
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class ArangoContextHelper:
    """Wraps ArangoClient to provide agent-specific context queries."""

    def __init__(self, client):
        self.client = client

    def get_project_context(self, user_id: str, limit: int = 3) -> str:
        """Resume Tailor context: quantified achievements from ro_client_projects.

        Returns formatted string with project names, outcomes, and metrics.
        """
        try:
            projects = self.client.query_projects_by_user(user_id, limit=limit)
            if not projects:
                return ""
            lines = ["# Relevant Projects and Outcomes"]
            for proj in projects[:limit]:
                lines.append(f"- {proj.get('name', '')}")
                for outcome in proj.get("outcomes", [])[:2]:
                    lines.append(f"  * {outcome}")
            return "\n".join(lines)
        except Exception as e:
            logger.debug(f"Failed to fetch project context: {e}")
            return ""

    def get_milestone_context(self, user_id: str, limit: int = 5) -> str:
        """Cover Letter context: career milestones from ro_journey_milestones.

        Returns formatted string with transitions, promotions, and impacts.
        """
        try:
            milestones = self.client.query_journey_milestones(user_id, limit=limit)
            if not milestones:
                return ""
            lines = ["# Career Milestones and Transitions"]
            for ms in milestones[:limit]:
                event = ms.get("event", "")
                date = ms.get("date", "")
                impact = ms.get("impact", "")
                lines.append(f"- {event} ({date})")
                if impact:
                    lines.append(f"  Impact: {impact}")
            return "\n".join(lines)
        except Exception as e:
            logger.debug(f"Failed to fetch milestone context: {e}")
            return ""

    def get_outcomes_context(self, user_id: str, limit: int = 4) -> str:
        """Interview Coach context: STAR-ready outcomes from ro_business_outcomes.

        Returns formatted string with descriptions and metrics.
        """
        try:
            outcomes = self.client.query_business_outcomes(user_id, limit=limit)
            if not outcomes:
                return ""
            lines = ["# Business Outcomes & STAR Examples"]
            for outcome in outcomes[:limit]:
                desc = outcome.get("description", "")
                lines.append(f"- {desc}")
                for metric in outcome.get("metrics", [])[:2]:
                    lines.append(f"  * {metric}")
            return "\n".join(lines)
        except Exception as e:
            logger.debug(f"Failed to fetch outcomes context: {e}")
            return ""

    def get_skills_context(self, user_id: str, limit: int = 5) -> str:
        """Career Advisor context: skills trajectory from ro_skills + ro_journey_milestones.

        Returns formatted string with skill adoption timeline.
        """
        try:
            skills = self.client.query_skills_inventory(user_id, limit=limit)
            if not skills:
                return ""
            lines = ["# Skills Inventory & Trajectory"]
            for skill in skills[:limit]:
                name = skill.get("skill", "")
                adopted = skill.get("adopted_date", "")
                projects = skill.get("projects", 0)
                lines.append(f"- {name} (adopted {adopted}, used in {projects} projects)")
            return "\n".join(lines)
        except Exception as e:
            logger.debug(f"Failed to fetch skills context: {e}")
            return ""


# Stub implementations for ArangoClient query methods
# (RTX 5090 will generate full AQL queries; stubs for test mocking)


class StubArangoClient:
    """Stub client that returns empty lists (for testing without ArangoDB)."""

    def query_projects_by_user(self, user_id: str, limit: int = 3) -> List[Dict[str, Any]]:
        return []

    def query_journey_milestones(self, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        return []

    def query_business_outcomes(self, user_id: str, limit: int = 4) -> List[Dict[str, Any]]:
        return []

    def query_skills_inventory(self, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        return []


def get_context_helper(client=None):
    """Get or create an ArangoContextHelper instance."""
    if client is None:
        try:
            from arango_client import get_arango_client

            client = get_arango_client()
        except Exception:
            client = StubArangoClient()
    return ArangoContextHelper(client)
