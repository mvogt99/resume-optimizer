"""LinkedIn profile update generator — surfaces journey synthesis as editable updates."""

import contextlib
import json
import logging

from models import get_db

logger = logging.getLogger(__name__)


def generate_profile_update(user_id):
    """Generate suggested LinkedIn profile updates from journey narratives + deep profile.

    Aggregates: journey narratives, deep profile, project analysis (skills/outcomes),
    ArangoDB graph context, and journey achievements into cohesive LinkedIn sections.

    Returns dict with sections: headline, summary, experience, skills, featured,
    plus project_highlights and achievements when available.
    """
    sections = {}

    # Get current LinkedIn profile
    current = _get_current_profile(user_id)

    # Get journey narratives for LinkedIn sections
    narratives = _get_journey_narratives(user_id, "linkedin_section")

    # Get deep profile if available
    deep = _get_deep_profile(user_id)

    # Get enrichment context from projects, journey, graph
    enrichment = _get_enrichment_context(user_id)

    # Headline — deep profile differentiators > current
    if deep and deep.get("differentiators"):
        diffs = deep["differentiators"][:3]
        diff_text = " | ".join(d.get("label", d) if isinstance(d, dict) else str(d) for d in diffs)
        sections["headline"] = diff_text
    elif current.get("headline"):
        sections["headline"] = current["headline"]

    # Summary — journey narrative > deep profile executive summary > current
    for n in narratives:
        if "summary" in n.get("title", "").lower() or n.get("narrative_type") == "linkedin_summary":
            sections["summary"] = n.get("content", "")
            break
    if not sections.get("summary") and deep:
        sections["summary"] = deep.get("executive_summary", current.get("summary", ""))

    # Experience bullets — merge narrative + project outcomes + achievements
    exp_narratives = [
        n
        for n in narratives
        if "experience" in n.get("title", "").lower()
        or n.get("narrative_type") == "linkedin_experience"
    ]
    experience_parts = []
    if exp_narratives:
        experience_parts.append(exp_narratives[0].get("content", ""))
    elif deep and deep.get("career_phases"):
        for phase in deep["career_phases"][:3]:
            if isinstance(phase, dict):
                experience_parts.append(f"- {phase.get('summary', phase.get('title', ''))}")

    # Enrich experience with project-level business outcomes
    project_outcomes = enrichment.get("project_outcomes", [])
    if project_outcomes:
        experience_parts.append("\nKey Project Outcomes:")
        for po in project_outcomes[:5]:
            experience_parts.append(f"- {po}")

    if experience_parts:
        sections["experience"] = "\n".join(experience_parts)

    # Skills reorder — merge deep profile + project technologies + graph skills
    all_skills = []
    if deep and deep.get("top_skills"):
        for s in deep["top_skills"][:15]:
            name = s.get("name", s) if isinstance(s, dict) else str(s)
            if name and name not in all_skills:
                all_skills.append(name)

    # Add high-value project technologies not already in the list
    for tech in enrichment.get("project_technologies", [])[:10]:
        if tech not in all_skills:
            all_skills.append(tech)

    # Add graph skills
    for skill in enrichment.get("graph_skills", [])[:5]:
        if skill not in all_skills:
            all_skills.append(skill)

    if all_skills:
        sections["skills"] = ", ".join(all_skills[:20])
    elif current.get("skills_and_endorsements"):
        sections["skills"] = ", ".join(
            s.get("skill", str(s)) for s in current["skills_and_endorsements"][:15]
        )

    # Featured section — campaign seeds
    campaign_seeds = [n for n in narratives if "campaign" in n.get("title", "").lower()]
    if campaign_seeds:
        sections["featured"] = campaign_seeds[0].get("content", "")

    # Project highlights — new section from client project analysis
    project_highlights = enrichment.get("project_highlights", [])
    if project_highlights:
        sections["project_highlights"] = "\n".join(
            f"- **{ph['client']}**: {ph['summary']}" for ph in project_highlights[:5]
        )

    # Journey achievements — new section from journey mining
    achievements = enrichment.get("achievements", [])
    if achievements:
        sections["achievements"] = "\n".join(f"- {a}" for a in achievements[:5])

    # Store suggestions in DB
    for section_name, content in sections.items():
        current_content = _get_section_current(current, section_name)
        _upsert_suggestion(user_id, section_name, current_content, content)

    return {"sections": sections, "count": len(sections)}


def get_updates(user_id):
    """Get all pending/applied LinkedIn update suggestions."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM linkedin_profile_updates WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def update_suggestion(update_id, user_id, status=None, suggested_content=None):
    """Accept/reject/edit a suggestion."""
    with get_db() as conn:
        parts = ["updated_at = CURRENT_TIMESTAMP"]
        values = []
        if status:
            parts.append("status = ?")
            values.append(status)
        if suggested_content is not None:
            parts.append("suggested_content = ?")
            values.append(suggested_content)
        if not values:
            return False
        values.extend([update_id, user_id])
        cursor = conn.execute(
            f"UPDATE linkedin_profile_updates SET {', '.join(parts)} "
            "WHERE id = ? AND user_id = ?",
            values,
        )
        conn.commit()
        return cursor.rowcount > 0


def compare_current_vs_suggested(user_id):
    """Side-by-side comparison of current profile vs suggested updates."""
    updates = get_updates(user_id)
    comparison = []
    for u in updates:
        comparison.append(
            {
                "section": u["section_name"],
                "current": u["current_content"],
                "suggested": u["suggested_content"],
                "status": u["status"],
                "id": u["id"],
            }
        )
    return {"comparison": comparison, "count": len(comparison)}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_enrichment_context(user_id):
    """Gather project analysis, journey achievements, and graph skills for LinkedIn enrichment."""
    result = {
        "project_outcomes": [],
        "project_technologies": [],
        "project_highlights": [],
        "graph_skills": [],
        "achievements": [],
    }

    # Project analysis — extract business outcomes and technologies per client
    try:
        import contextlib

        with get_db() as conn:
            rows = conn.execute(
                "SELECT client_name, skills_json, business_outcomes_json, role_analysis_json "
                "FROM client_projects WHERE analysis_status IN ('completed', 'complete') "
                "AND (skills_json IS NOT NULL AND skills_json != '[]')"
            ).fetchall()

        for row in rows:
            client_name = row["client_name"]

            # Extract business outcomes
            outcomes = row["business_outcomes_json"]
            if isinstance(outcomes, str):
                with contextlib.suppress(json.JSONDecodeError, TypeError):
                    outcomes = json.loads(outcomes)
            if isinstance(outcomes, dict):
                for _, items in outcomes.items():
                    if isinstance(items, list):
                        for item in items[:3]:
                            desc = (
                                item.get("description", item.get("outcome", str(item)))
                                if isinstance(item, dict)
                                else str(item)
                            )
                            result["project_outcomes"].append(f"[{client_name}] {desc}")
            elif isinstance(outcomes, list):
                for item in outcomes[:3]:
                    desc = (
                        item.get("description", str(item)) if isinstance(item, dict) else str(item)
                    )
                    result["project_outcomes"].append(f"[{client_name}] {desc}")

            # Extract technologies
            skills = row["skills_json"]
            if isinstance(skills, str):
                with contextlib.suppress(json.JSONDecodeError, TypeError):
                    skills = json.loads(skills)
            if isinstance(skills, dict):
                for cat_skills in skills.values():
                    if isinstance(cat_skills, list):
                        for s in cat_skills[:10]:
                            name = s.get("name", s) if isinstance(s, dict) else str(s)
                            if name and name not in result["project_technologies"]:
                                result["project_technologies"].append(name)

            # Build highlight
            role_analysis = row["role_analysis_json"]
            if isinstance(role_analysis, str):
                with contextlib.suppress(json.JSONDecodeError, TypeError):
                    role_analysis = json.loads(role_analysis)
            summary = ""
            if isinstance(role_analysis, dict):
                summary = str(role_analysis.get("impact", role_analysis.get("contributions", "")))[
                    :200
                ]
            if summary:
                result["project_highlights"].append({"client": client_name, "summary": summary})

    except Exception as e:
        logger.debug("Failed to get project enrichment: %s", e)

    # Journey achievements
    try:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT title, metrics FROM journey_events "
                "WHERE category IN ('milestone', 'achievement') "
                "ORDER BY event_date DESC LIMIT 10"
            ).fetchall()

        for row in rows:
            title = row["title"]
            metrics = row["metrics"]
            if isinstance(metrics, str):
                try:
                    metrics = json.loads(metrics)
                except (json.JSONDecodeError, TypeError):
                    metrics = []
            metrics_str = f" ({', '.join(str(m) for m in metrics[:2])})" if metrics else ""
            result["achievements"].append(f"{title}{metrics_str}")

    except Exception as e:
        logger.debug("Failed to get journey achievements: %s", e)

    # ArangoDB graph skills
    try:
        from arango_client import get_graph_client

        arango = get_graph_client()
        if arango:
            tech_summary = arango.get_technology_summary()
            # Sort by client_count descending — most cross-cutting skills first
            tech_summary.sort(key=lambda t: t.get("client_count", 0), reverse=True)
            for tech in tech_summary[:15]:
                name = tech.get("name", "")
                if name and name not in result["graph_skills"]:
                    result["graph_skills"].append(name)
    except Exception as e:
        logger.debug("Failed to get graph skills: %s", e)

    return result


def _get_current_profile(user_id):
    """Load cached LinkedIn profile from DB."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT profile_json FROM linkedin_profiles WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row:
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                return json.loads(row["profile_json"])
    return {}


def _get_journey_narratives(user_id, narrative_type=None):
    """Load journey narratives from DB."""
    with get_db() as conn:
        if narrative_type:
            rows = conn.execute(
                "SELECT * FROM journey_narratives WHERE user_id = ? AND narrative_type LIKE ?",
                (user_id, f"%{narrative_type}%"),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM journey_narratives WHERE user_id = ?", (user_id,)
            ).fetchall()
        return [dict(r) for r in rows]


def _get_deep_profile(user_id):
    """Load the latest deep profile — checks deep_profiles table first, then career_analyses."""
    # Primary source: deep_profiles table (from deep_profile.py engine)
    try:
        from deep_profile import get_deep_profile_engine

        engine = get_deep_profile_engine()
        profile = engine.get_profile(user_id)
        if profile:
            return profile
    except Exception:
        pass

    # Fallback: career_analyses table
    with get_db() as conn:
        row = conn.execute(
            "SELECT result_json FROM career_analyses "
            "WHERE user_id = ? AND analysis_type = 'deep_profile' "
            "ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        if row:
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                return json.loads(row["result_json"])
    return None


def _get_section_current(profile, section_name):
    """Extract current content for a section from LinkedIn profile."""
    if section_name == "headline":
        return profile.get("headline", "")
    if section_name == "summary":
        return profile.get("summary", "")
    if section_name == "skills":
        skills = profile.get("skills_and_endorsements", [])
        return ", ".join(s.get("skill", str(s)) for s in skills[:15])
    return ""


def _upsert_suggestion(user_id, section_name, current_content, suggested_content):
    """Insert or update a suggestion for a section."""
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM linkedin_profile_updates "
            "WHERE user_id = ? AND section_name = ? AND status = 'pending'",
            (user_id, section_name),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE linkedin_profile_updates SET suggested_content = ?, "
                "current_content = ? WHERE id = ?",
                (suggested_content, current_content, existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO linkedin_profile_updates "
                "(user_id, section_name, current_content, suggested_content) "
                "VALUES (?, ?, ?, ?)",
                (user_id, section_name, current_content, suggested_content),
            )
        conn.commit()
