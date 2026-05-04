"""Generate portfolio showcase from career data (projects, skills, achievements)."""

import json
import logging

import linkedin_cache
from llm_helper import call_llm_quality
from models import get_db

logger = logging.getLogger(__name__)


def _load_projects(user_id):
    """Load approved client projects."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, client_name, folder_id, analysis_json, approved "
            "FROM client_projects WHERE user_id = ? AND approved = 1",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def _load_narratives(user_id):
    """Load journey narratives."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT narrative_type, content_json FROM journey_narratives WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    result = {}
    for r in rows:
        result[r["narrative_type"]] = json.loads(r["content_json"] or "{}")
    return result


def generate_portfolio(user_id):
    """Build a structured portfolio from all career data sources."""
    projects = _load_projects(user_id)
    narratives = _load_narratives(user_id)
    li_profile = linkedin_cache.get_raw(user_id) or {}

    name = li_profile.get("full_name", li_profile.get("name", ""))
    headline = li_profile.get("headline", "")
    education = li_profile.get("education_history", li_profile.get("education", []))
    skills = li_profile.get("skills_and_endorsements", li_profile.get("skills", []))

    # Build project items
    project_items = []
    for proj in projects:
        analysis = json.loads(proj.get("analysis_json") or "{}")
        item = {
            "project_name": proj["client_name"],
            "client": proj["client_name"],
            "role": "",
            "description": "",
            "technologies": [],
            "outcomes": [],
        }

        if analysis:
            item["role"] = analysis.get("role", "")
            item["technologies"] = analysis.get("technologies", [])[:15]
            item["outcomes"] = analysis.get("outcomes", analysis.get("business_outcomes", []))[:5]
            raw_desc = analysis.get("summary", analysis.get("description", ""))

            # Try LLM synthesis for richer description
            if raw_desc:
                prompt = (
                    f"Write a concise 2-3 sentence project description for a portfolio showcase.\n"
                    f"Project: {proj['client_name']}\n"
                    f"Raw summary: {raw_desc[:1000]}\n"
                    f"Technologies: {', '.join(item['technologies'][:10])}\n"
                    f"Return ONLY the description text, no JSON."
                )
                synthesized = call_llm_quality(prompt, task_type="reasoning", max_tokens=512)
                item["description"] = synthesized or raw_desc[:500]
            else:
                item["description"] = f"Project for {proj['client_name']}"

        project_items.append(item)

    # Build skills summary from LinkedIn + projects
    skill_names = []
    for s in (skills or [])[:30]:
        if isinstance(s, dict):
            skill_names.append(s.get("name", str(s)))
        else:
            skill_names.append(str(s))

    sections = []
    if project_items:
        sections.append({"title": "Projects", "items": project_items})

    # Add narrative sections if available
    resume_entries = narratives.get("resume_entries", {})
    if isinstance(resume_entries, dict) and resume_entries.get("entries"):
        sections.append({"title": "Key Achievements", "items": resume_entries["entries"][:5]})

    return {
        "name": name,
        "headline": headline,
        "sections": sections,
        "skills_summary": skill_names,
        "education": education if isinstance(education, list) else [],
    }


def export_portfolio_text(user_id):
    """Export portfolio as formatted plain text."""
    portfolio = generate_portfolio(user_id)
    lines = []

    lines.append(portfolio.get("name", "Portfolio"))
    lines.append(portfolio.get("headline", ""))
    lines.append("=" * 60)
    lines.append("")

    project_count = 0
    for section in portfolio.get("sections", []):
        lines.append(section["title"].upper())
        lines.append("-" * 40)
        for item in section.get("items", []):
            if isinstance(item, dict):
                name = item.get("project_name", item.get("title", ""))
                if name:
                    lines.append(f"  {name}")
                desc = item.get("description", "")
                if desc:
                    lines.append(f"    {desc}")
                techs = item.get("technologies", [])
                if techs:
                    lines.append(f"    Technologies: {', '.join(techs[:10])}")
                outcomes = item.get("outcomes", [])
                for o in outcomes[:3]:
                    if isinstance(o, str):
                        lines.append(f"    - {o}")
                    elif isinstance(o, dict):
                        lines.append(f"    - {o.get('description', str(o))}")
                project_count += 1
            else:
                lines.append(f"  - {item}")
            lines.append("")
        lines.append("")

    if portfolio.get("skills_summary"):
        lines.append("SKILLS")
        lines.append("-" * 40)
        lines.append(", ".join(portfolio["skills_summary"]))
        lines.append("")

    if portfolio.get("education"):
        lines.append("EDUCATION")
        lines.append("-" * 40)
        for edu in portfolio["education"]:
            if isinstance(edu, dict):
                lines.append(
                    f"  {edu.get('degree', '')} -- {edu.get('school', edu.get('institution', ''))}"
                )
            else:
                lines.append(f"  {edu}")
        lines.append("")

    text = "\n".join(lines)
    return {
        "text": text,
        "sections": len(portfolio.get("sections", [])),
        "projects": project_count,
    }
