"""
Private helper functions for context_enrichment.py.

These functions are called by the public API in context_enrichment.py.
Split from context_enrichment.py to comply with 500-line file limit.
"""

import contextlib
import json
import logging

from models import get_db

logger = logging.getLogger(__name__)


def _get_matching_journey_events(user_id, employer, client, technologies=None):
    """Query journey_events that match employer, client, or technologies."""
    with get_db() as conn:
        # Build search terms
        search_terms = []
        if employer:
            search_terms.append(employer.lower())
        if client:
            search_terms.append(client.lower())

        if not search_terms and not technologies:
            # Return recent events as general context
            rows = conn.execute(
                "SELECT * FROM journey_events ORDER BY event_date DESC LIMIT 20"
            ).fetchall()
            return [dict(r) for r in rows]

        # Search by title/description matching employer/client
        results = []
        if search_terms:
            for term in search_terms:
                rows = conn.execute(
                    "SELECT * FROM journey_events "
                    "WHERE LOWER(title) LIKE ? OR LOWER(description) LIKE ? "
                    "ORDER BY event_date DESC LIMIT 20",
                    (f"%{term}%", f"%{term}%"),
                ).fetchall()
                results.extend(dict(r) for r in rows)

        # Also search by technologies
        if technologies:
            for tech in technologies[:10]:
                rows = conn.execute(
                    "SELECT * FROM journey_events "
                    "WHERE LOWER(technologies) LIKE ? "
                    "ORDER BY event_date DESC LIMIT 10",
                    (f"%{tech.lower()}%",),
                ).fetchall()
                results.extend(dict(r) for r in rows)

    # Deduplicate by event id
    seen = set()
    deduped = []
    for evt in results:
        eid = evt.get("id")
        if eid not in seen:
            seen.add(eid)
            deduped.append(evt)

    return deduped[:20]


def _get_matching_project_analysis(user_id, employer, client):
    """Find project analysis matching employer or client name."""
    search_term = client or employer
    if not search_term:
        return None

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM client_projects "
            "WHERE LOWER(client_name) LIKE ? AND analysis_status IN ('completed', 'complete') "
            "ORDER BY created_at DESC LIMIT 1",
            (f"%{search_term.lower()}%",),
        ).fetchone()

    if not row:
        return None

    result = dict(row)
    for key in (
        "technical_analysis_json",
        "governance_analysis_json",
        "role_analysis_json",
        "skills_json",
        "correlation_json",
        "business_outcomes_json",
    ):
        if isinstance(result.get(key), str):
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                result[key] = json.loads(result[key])

    return result


def _get_graph_context(employer, client):
    """Query ArangoDB graph for matching context."""
    try:
        from arango_client import get_arango_client

        arango = get_arango_client()
        if not arango:
            return {"clients": [], "skills": [], "milestones": []}

        # Search by employer or client name
        search_term = client or employer
        if search_term:
            return arango.get_knowledge_context(search_term, limit=10)
    except Exception as e:
        logger.debug("ArangoDB graph query failed: %s", e)

    return {"clients": [], "skills": [], "milestones": []}


def _get_prior_experiences(user_id, employer, client):
    """Get previously extracted experiences for the same employer/client."""
    # SAFE: `conditions` is built from hardcoded column-name strings like
    # "LOWER(employer) LIKE ?". User-supplied values (employer, client) are
    # bound via ? parameterized placeholders, never interpolated directly.
    conditions = ["user_id = ?"]
    params = [user_id]

    if employer:
        conditions.append("LOWER(employer) LIKE ?")
        params.append(f"%{employer.lower()}%")
    if client:
        conditions.append("LOWER(client) LIKE ?")
        params.append(f"%{client.lower()}%")

    # Only filter by employer/client if we have them
    if len(conditions) == 1:
        return []

    with get_db() as conn:
        where_clause = " AND ".join(conditions)
        rows = conn.execute(
            f"SELECT * FROM extracted_experiences WHERE {where_clause} "
            "ORDER BY created_at DESC LIMIT 5",
            params,
        ).fetchall()

    results = []
    for r in rows:
        d = dict(r)
        for jfield in (
            "responsibilities",
            "technologies",
            "accomplishments",
            "challenges",
            "bullet_points",
        ):
            if isinstance(d.get(jfield), str):
                with contextlib.suppress(json.JSONDecodeError, TypeError):
                    d[jfield] = json.loads(d[jfield])
        results.append(d)

    return results


def _get_matching_achievements(user_id, employer, client):
    """Get journey achievements that match the employer/client context."""
    search_term = client or employer
    with get_db() as conn:
        if search_term:
            rows = conn.execute(
                "SELECT * FROM journey_events "
                "WHERE category IN ('milestone', 'achievement') "
                "AND (LOWER(title) LIKE ? OR LOWER(description) LIKE ?) "
                "ORDER BY event_date DESC LIMIT 10",
                (f"%{search_term.lower()}%", f"%{search_term.lower()}%"),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM journey_events "
                "WHERE category IN ('milestone', 'achievement') "
                "ORDER BY event_date DESC LIMIT 10"
            ).fetchall()

    results = []
    for r in rows:
        d = dict(r)
        for jfield in ("technologies", "metrics"):
            if isinstance(d.get(jfield), str):
                with contextlib.suppress(json.JSONDecodeError, TypeError):
                    d[jfield] = json.loads(d[jfield])
        results.append(d)
    return results


def _get_approved_narratives(user_id):
    """Get approved journey narratives (resume entries, LinkedIn sections, learning arcs)."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT narrative_type, title, content FROM journey_narratives "
            "WHERE (user_id = ? OR user_id = 0) AND "
            "(approved = 1 OR narrative_type IN "
            "('resume_entry', 'linkedin_section', 'learning_arc')) "
            "ORDER BY narrative_type, created_at DESC LIMIT 10",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def _aggregate_technologies(context):
    """Aggregate unique technologies from all context sources."""
    techs = set()

    # From journey events
    for evt in context.get("journey_events", []):
        event_techs = evt.get("technologies", [])
        if isinstance(event_techs, str):
            with contextlib.suppress(json.JSONDecodeError):
                event_techs = json.loads(event_techs)
        if isinstance(event_techs, list):
            techs.update(t for t in event_techs if isinstance(t, str))

    # From project analysis
    proj = context.get("project_analysis")
    if proj:
        skills = proj.get("skills_json") or proj.get("skills") or {}
        if isinstance(skills, dict):
            for cat_skills in skills.values():
                if isinstance(cat_skills, list):
                    for s in cat_skills:
                        if isinstance(s, str):
                            techs.add(s)
                        elif isinstance(s, dict):
                            techs.add(s.get("name", ""))

    # From graph
    graph = context.get("graph_context", {})
    for skill in graph.get("skills", []):
        if isinstance(skill, dict):
            techs.add(skill.get("name", ""))
        elif isinstance(skill, str):
            techs.add(skill)

    # From prior experiences
    for exp in context.get("prior_experiences", []):
        exp_techs = exp.get("technologies", [])
        if isinstance(exp_techs, list):
            techs.update(t for t in exp_techs if isinstance(t, str))

    return sorted(t for t in techs if t)


def _format_project_analysis(proj):
    """Format project analysis into readable text for prompt."""
    lines = [f"PROJECT ANALYSIS — {proj.get('client_name', 'Unknown Client')}:"]

    # Technical analysis
    tech = proj.get("technical_analysis_json") or proj.get("technical_analysis") or {}
    if isinstance(tech, dict):
        if tech.get("architecture"):
            lines.append(f"  Architecture: {str(tech['architecture'])[:200]}")
        if tech.get("technologies"):
            tech_list = tech["technologies"]
            if isinstance(tech_list, list):
                lines.append(f"  Technologies: {', '.join(str(t) for t in tech_list[:15])}")
        if tech.get("integrations"):
            lines.append(f"  Integrations: {str(tech['integrations'])[:200]}")

    # Role analysis
    role = proj.get("role_analysis_json") or proj.get("role_analysis") or {}
    if isinstance(role, dict):
        if role.get("contributions"):
            lines.append(f"  Contributions: {str(role['contributions'])[:300]}")
        if role.get("leadership"):
            lines.append(f"  Leadership: {str(role['leadership'])[:200]}")
        if role.get("impact"):
            lines.append(f"  Impact: {str(role['impact'])[:200]}")

    # Business outcomes
    outcomes = proj.get("business_outcomes_json") or proj.get("business_outcomes") or {}
    if isinstance(outcomes, dict) and outcomes:
        lines.append(f"  Business Outcomes: {str(outcomes)[:300]}")
    elif isinstance(outcomes, list) and outcomes:
        for o in outcomes[:5]:
            if isinstance(o, dict):
                lines.append(f"  - {o.get('description', o.get('outcome', str(o)))[:150]}")
            else:
                lines.append(f"  - {str(o)[:150]}")

    # Skills
    skills = proj.get("skills_json") or proj.get("skills") or {}
    if isinstance(skills, dict):
        all_skills = []
        for cat_skills in skills.values():
            if isinstance(cat_skills, list):
                for s in cat_skills[:10]:
                    all_skills.append(s.get("name", s) if isinstance(s, dict) else str(s))
        if all_skills:
            lines.append(f"  Skills Demonstrated: {', '.join(all_skills[:20])}")

    return "\n".join(lines) if len(lines) > 1 else ""


def _format_graph_context(graph):
    """Format ArangoDB graph context into readable text."""
    if not graph:
        return ""

    lines = []

    clients = graph.get("clients", [])
    if clients:
        client_names = [
            c.get("name", str(c)) if isinstance(c, dict) else str(c) for c in clients[:5]
        ]
        lines.append(f"RELATED CLIENTS (from knowledge graph): {', '.join(client_names)}")

    skills = graph.get("skills", [])
    if skills:
        skill_names = [
            s.get("name", str(s)) if isinstance(s, dict) else str(s) for s in skills[:10]
        ]
        lines.append(f"GRAPH SKILLS: {', '.join(skill_names)}")

    milestones = graph.get("milestones", [])
    if milestones:
        milestone_strs = [
            m.get("title", str(m)) if isinstance(m, dict) else str(m) for m in milestones[:5]
        ]
        lines.append(f"GRAPH MILESTONES: {', '.join(milestone_strs)}")

    return "\n".join(lines)
