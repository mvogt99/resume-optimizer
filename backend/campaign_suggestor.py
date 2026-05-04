"""Auto-suggest campaign topics based on new knowledge in the system."""

import logging
from datetime import datetime, timedelta, timezone

from llm_helper import call_llm_quality, extract_json
from models import get_db

logger = logging.getLogger(__name__)


def _get_recent_events(user_id, days=30):
    """Get journey events from the last N days."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT category, title, description, event_date "
            "FROM journey_events WHERE event_date >= ? ORDER BY event_date DESC",
            (cutoff,),
        ).fetchall()
    return [dict(r) for r in rows]


def _get_existing_themes(user_id):
    """Get all campaign themes to avoid duplicates."""
    with get_db() as conn:
        rows = conn.execute("SELECT theme FROM campaigns WHERE user_id = ?", (user_id,)).fetchall()
    return {r[0].lower() for r in rows if r[0]}


def _get_uncovered_projects(user_id, existing_themes):
    """Find approved projects not referenced in any campaign."""
    with get_db() as conn:
        projects = conn.execute(
            "SELECT client_name, technical_analysis_json FROM client_projects "
            "WHERE user_id = ? AND approved = 1",
            (user_id,),
        ).fetchall()

        # Check which campaign posts reference each project
        posts = conn.execute(
            "SELECT cp.content FROM campaign_posts cp "
            "JOIN campaigns c ON cp.campaign_id = c.id WHERE c.user_id = ?",
            (user_id,),
        ).fetchall()

    all_post_text = " ".join((p["content"] or "").lower() for p in posts)

    uncovered = []
    for proj in projects:
        name = proj["client_name"]
        if name.lower() not in all_post_text and name.lower() not in existing_themes:
            uncovered.append(dict(proj))
    return uncovered


def suggest_campaigns(user_id, max_suggestions=5):
    """Suggest new campaign topics based on uncovered knowledge."""
    existing_themes = _get_existing_themes(user_id)
    recent_events = _get_recent_events(user_id)
    uncovered = _get_uncovered_projects(user_id, existing_themes)

    # Build context for LLM
    context_parts = []
    if recent_events:
        event_summaries = [
            f"- {e['title']}: {e.get('description', '')[:100]}" for e in recent_events[:10]
        ]
        context_parts.append("Recent events:\n" + "\n".join(event_summaries))
    if uncovered:
        proj_names = [p["client_name"] for p in uncovered]
        context_parts.append(f"Uncovered projects: {', '.join(proj_names)}")
    if existing_themes:
        context_parts.append(
            f"Existing campaign themes (avoid duplicates): {', '.join(existing_themes)}"
        )

    if not context_parts:
        return {
            "suggestions": [],
            "based_on": {
                "new_events": 0,
                "uncovered_projects": 0,
                "trending_skills": 0,
            },
        }

    prompt = (
        f"Suggest {max_suggestions} LinkedIn campaign topics based on this career data.\n\n"
        + "\n\n".join(context_parts)
        + "\n\nReturn a JSON array of objects with fields: "
        "theme, audience, rationale, source_type (event/project/skill), source_reference.\n"
        "Avoid themes similar to existing campaigns listed above."
    )

    raw = call_llm_quality(prompt, task_type="reasoning", max_tokens=2048)
    suggestions = []

    if raw:
        parsed = extract_json(raw)
        if isinstance(parsed, list):
            suggestions = parsed[:max_suggestions]
        elif isinstance(parsed, dict) and "suggestions" in parsed:
            suggestions = parsed["suggestions"][:max_suggestions]

    # Fallback: template suggestions from raw data
    if not suggestions:
        for proj in uncovered[:max_suggestions]:
            suggestions.append(
                {
                    "theme": f"Insights from {proj['client_name']}",
                    "audience": "Technology leaders and practitioners",
                    "rationale": (
                        f"Project {proj['client_name']} has not been featured in any campaign yet."
                    ),
                    "source_type": "project",
                    "source_reference": proj["client_name"],
                }
            )
        for evt in recent_events[: max(0, max_suggestions - len(suggestions))]:
            suggestions.append(
                {
                    "theme": evt.get("title", "Recent Achievement"),
                    "audience": "Professional network",
                    "rationale": f"Recent event: {evt.get('description', '')[:200]}",
                    "source_type": "event",
                    "source_reference": evt.get("title", ""),
                }
            )

    return {
        "suggestions": suggestions[:max_suggestions],
        "based_on": {
            "new_events": len(recent_events),
            "uncovered_projects": len(uncovered),
            "trending_skills": 0,
        },
    }


def get_uncovered_topics(user_id):
    """Return topics/projects/events NOT yet used in any campaign."""
    existing_themes = _get_existing_themes(user_id)
    uncovered_projects = _get_uncovered_projects(user_id, existing_themes)

    # Find events not referenced in campaigns
    with get_db() as conn:
        all_events = conn.execute(
            "SELECT category, title, description, event_date FROM journey_events "
            "ORDER BY event_date DESC"
        ).fetchall()

        posts = conn.execute(
            "SELECT cp.content FROM campaign_posts cp "
            "JOIN campaigns c ON cp.campaign_id = c.id WHERE c.user_id = ?",
            (user_id,),
        ).fetchall()

    all_post_text = " ".join((p["content"] or "").lower() for p in posts)

    uncovered_events = []
    for evt in all_events:
        title = evt["title"] or ""
        if title.lower() not in all_post_text:
            uncovered_events.append(dict(evt))

    return {
        "uncovered_projects": [{"client_name": p["client_name"]} for p in uncovered_projects],
        "uncovered_events": uncovered_events[:20],
    }
