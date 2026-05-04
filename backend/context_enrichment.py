"""
Context enrichment bridge — connects journey mining, project analysis,
ArangoDB graph, and deep profile data into experience chat and profile
synthesis pipelines.

This module provides functions to gather contextual evidence from all
data sources and format it for injection into LLM prompts (experience
interviewer, deep profile, LinkedIn generator).
"""

import contextlib
import json
import logging

from models import get_db

logger = logging.getLogger(__name__)

# Private helpers delegated to context_enrichment_helpers.py (500-line split).
from context_enrichment_helpers import (  # noqa: E402
    _aggregate_technologies,
    _format_graph_context,
    _format_project_analysis,
    _get_approved_narratives,
    _get_graph_context,
    _get_matching_achievements,
    _get_matching_journey_events,
    _get_matching_project_analysis,
    _get_prior_experiences,
)


def gather_context_for_employer(user_id, employer="", client="", technologies=None):
    """Gather all known context about a user's work at a specific employer/client.

    Queries journey events, project analysis, ArangoDB graph, and
    extracted experiences to build a comprehensive context bundle.

    Returns:
        dict with keys: journey_events, project_analysis, graph_context,
        prior_experiences, technologies_known, achievements, narratives
    """
    context = {  # noqa: SIM904
        "journey_events": [],
        "project_analysis": None,
        "graph_context": {"clients": [], "skills": [], "milestones": []},
        "prior_experiences": [],
        "technologies_known": [],
        "achievements": [],
        "narratives": [],
    }

    # 1. Journey events matching employer/client/technologies
    context["journey_events"] = _get_matching_journey_events(
        user_id, employer, client, technologies
    )

    # 2. Project analysis for matching client
    context["project_analysis"] = _get_matching_project_analysis(user_id, employer, client)

    # 3. ArangoDB graph context
    context["graph_context"] = _get_graph_context(employer, client)

    # 4. Prior extracted experiences for same employer/client
    context["prior_experiences"] = _get_prior_experiences(user_id, employer, client)

    # 5. Known technologies from all sources
    context["technologies_known"] = _aggregate_technologies(context)

    # 6. Achievements from journey
    context["achievements"] = _get_matching_achievements(user_id, employer, client)

    # 7. Approved narratives
    context["narratives"] = _get_approved_narratives(user_id)

    return context


def format_context_for_prompt(context, max_chars=4000):
    """Format gathered context into a text block suitable for LLM prompt injection.

    Prioritizes: project analysis > graph data > journey events > narratives.
    Truncates to max_chars to avoid overwhelming the prompt.
    """
    sections = []

    # Project analysis (richest source)
    proj = context.get("project_analysis")
    if proj:
        section = _format_project_analysis(proj)
        if section:
            sections.append(section)

    # Graph context (cross-referenced evidence)
    graph = context.get("graph_context", {})
    graph_section = _format_graph_context(graph)
    if graph_section:
        sections.append(graph_section)

    # Journey events
    events = context.get("journey_events", [])
    if events:
        event_lines = ["JOURNEY EVENTS (AI/engineering history):"]
        for evt in events[:10]:
            date = evt.get("event_date", "")
            title = evt.get("title", "")
            techs = evt.get("technologies", [])
            if isinstance(techs, str):
                with contextlib.suppress(json.JSONDecodeError):
                    techs = json.loads(techs)
            tech_str = f" [{', '.join(techs[:5])}]" if techs else ""
            event_lines.append(f"  - {date}: {title}{tech_str}")
        sections.append("\n".join(event_lines))

    # Achievements
    achievements = context.get("achievements", [])
    if achievements:
        ach_lines = ["KEY ACHIEVEMENTS:"]
        for ach in achievements[:5]:
            title = ach.get("title", "")
            metrics = ach.get("metrics", [])
            if isinstance(metrics, str):
                with contextlib.suppress(json.JSONDecodeError):
                    metrics = json.loads(metrics)
            metrics_str = f" ({', '.join(str(m) for m in metrics[:3])})" if metrics else ""
            ach_lines.append(f"  - {title}{metrics_str}")
        sections.append("\n".join(ach_lines))

    # Approved narratives
    narratives = context.get("narratives", [])
    if narratives:
        narr_lines = ["APPROVED NARRATIVES:"]
        for narr in narratives[:3]:
            ntype = narr.get("narrative_type", "")
            title = narr.get("title", "")
            content = narr.get("content", "")[:300]
            narr_lines.append(f"  [{ntype}] {title}: {content}")
        sections.append("\n".join(narr_lines))

    # Technologies known
    techs = context.get("technologies_known", [])
    if techs:
        sections.append(f"TECHNOLOGIES DEMONSTRATED: {', '.join(techs[:30])}")

    # Prior experience extractions
    priors = context.get("prior_experiences", [])
    if priors:
        prior_lines = ["PRIOR EXPERIENCE EXTRACTIONS:"]
        for exp in priors[:3]:
            title = exp.get("title", "unknown role")
            bullets = exp.get("bullet_points", [])
            if isinstance(bullets, str):
                with contextlib.suppress(json.JSONDecodeError):
                    bullets = json.loads(bullets)
            prior_lines.append(f"  {title}:")
            for bp in (bullets or [])[:3]:
                prior_lines.append(f"    - {bp}")
        sections.append("\n".join(prior_lines))

    combined = "\n\n".join(sections)
    if len(combined) > max_chars:
        combined = combined[:max_chars] + "\n[... truncated]"

    return combined


def get_deep_profile_summary(user_id, max_chars=2000):
    """Get a concise deep profile summary for prompt enrichment."""
    try:
        from deep_profile import get_deep_profile_engine

        engine = get_deep_profile_engine()
        profile = engine.get_profile(user_id)
        if not profile:
            return ""

        parts = []

        # Executive summary
        if profile.get("executive_summary"):
            parts.append(f"CAREER SUMMARY: {profile['executive_summary'][:500]}")

        # Higher-order skills
        if profile.get("higher_order_skills"):
            skills = profile["higher_order_skills"]
            if isinstance(skills, list):
                skill_names = [
                    s.get("name", s) if isinstance(s, dict) else str(s) for s in skills[:10]
                ]
                parts.append(f"HIGHER-ORDER SKILLS: {', '.join(skill_names)}")

        # Career phases
        if profile.get("career_phases"):
            phase_lines = ["CAREER PHASES:"]
            for phase in profile["career_phases"][:5]:
                if isinstance(phase, dict):
                    phase_lines.append(
                        f"  - {phase.get('title', phase.get('period', ''))}: "
                        f"{phase.get('summary', '')[:150]}"
                    )
            parts.append("\n".join(phase_lines))

        # Differentiators
        if profile.get("differentiators"):
            diffs = profile["differentiators"][:5]
            diff_strs = [d.get("label", d) if isinstance(d, dict) else str(d) for d in diffs]
            parts.append(f"DIFFERENTIATORS: {', '.join(diff_strs)}")

        # Business impacts
        if profile.get("business_impacts"):
            impacts = profile["business_impacts"][:5]
            impact_lines = ["BUSINESS IMPACTS:"]
            for imp in impacts:
                if isinstance(imp, dict):
                    impact_lines.append(
                        f"  - {imp.get('description', imp.get('impact', str(imp)))[:150]}"
                    )
                else:
                    impact_lines.append(f"  - {str(imp)[:150]}")
            parts.append("\n".join(impact_lines))

        result = "\n\n".join(parts)
        return result[:max_chars] if len(result) > max_chars else result

    except Exception as e:
        logger.debug("Failed to get deep profile summary: %s", e)
        return ""
