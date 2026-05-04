"""
LLM synthesis methods for DeepProfileEngine — profile synthesis, role synthesis,
source summary, and data condensing.
"""

import json


def build_source_summary(raw):
    """Build a human-readable summary of data sources."""
    parts = []
    li = raw.get("linkedin", {})
    if li.get("skills"):
        parts.append(
            f"LinkedIn: {len(li['skills'])} skills, "
            f"{len(li.get('experience', []))} positions, "
            f"{len(li.get('recommendations', []))} recommendations"
        )
    projs = raw.get("projects", [])
    if projs:
        parts.append(f"Projects: {len(projs)} analyzed clients")
    journey = raw.get("journey", {})
    if journey.get("events"):
        parts.append(
            f"Journey: {len(journey['events'])} events, "
            f"{len(journey.get('narratives', []))} narratives"
        )
    exps = raw.get("experiences", [])
    if exps:
        parts.append(f"Experiences: {len(exps)} extracted")
    resumes = raw.get("resumes", [])
    if resumes:
        parts.append(f"Resumes: {len(resumes)} versions")
    interviews = raw.get("skills_interviews", [])
    if interviews:
        parts.append(f"Skills interviews: {len(interviews)} sessions")
    wip = raw.get("wip_projects", [])
    if wip:
        names = [p.get("name", "?") for p in wip]
        parts.append(f"WIP projects: {len(wip)} ({', '.join(names)})")
    return "; ".join(parts) if parts else "No data sources found"


def condense_raw_for_llm(raw):
    """Pre-summarize raw data to fit LLM context while preserving signal."""
    condensed = {"linkedin": raw.get("linkedin", {})}

    projects = raw.get("projects", [])
    n_proj = max(len(projects), 1)
    max_skills = max(10, 30 // n_proj)
    max_outcomes = max(8, 20 // n_proj)
    max_tech = max(8, 20 // n_proj)
    condensed_projects = []
    for proj in projects:
        cp = {"client_name": proj.get("client_name", "")}
        skills = proj.get("skills", [])
        if isinstance(skills, list):
            top_skills = sorted(skills, key=lambda s: -s.get("confidence", 0))[:max_skills]
            cp["top_skills"] = [
                {
                    "name": s.get("name"),
                    "category": s.get("category"),
                    "proficiency_signal": s.get("proficiency_signal"),
                }
                for s in top_skills
            ]
            cp["total_skills"] = len(skills)
        outcomes = proj.get("business_outcomes", [])
        if isinstance(outcomes, list):
            top_outcomes = sorted(outcomes, key=lambda o: -o.get("confidence", 0))[:max_outcomes]
            cp["top_outcomes"] = [
                {
                    "title": o.get("outcome_title"),
                    "type": o.get("outcome_type"),
                    "metric": o.get("metric_value"),
                    "description": o.get("description", "")[:80],
                }
                for o in top_outcomes
            ]
            cp["total_outcomes"] = len(outcomes)
        tech = proj.get("technical_analysis", {})
        if isinstance(tech, list):
            cp["tech_count"] = len(tech)
            cp["tech_sample"] = [t.get("technology") or t.get("name", "") for t in tech[:max_tech]]
        role = proj.get("role_analysis", {})
        if isinstance(role, list):
            cp["role_count"] = len(role)
            cp["role_sample"] = [r.get("contribution") or r.get("title", "") for r in role[:5]]
        condensed_projects.append(cp)
    condensed["projects"] = condensed_projects

    li = condensed.get("linkedin", {})
    if li.get("recommendations"):
        condensed["linkedin"]["recommendations"] = [
            {"author": r.get("author", ""), "text": r.get("text", "")[:100]}
            for r in li["recommendations"][:5]
        ]
    if li.get("skills"):
        skills = sorted(
            li["skills"],
            key=lambda s: -(s.get("endorsements", 0) or s.get("endorsements_count", 0)),
        )[:20]
        condensed["linkedin"]["skills"] = [
            {
                "name": s.get("name") or s.get("skill", ""),
                "endorsements": s.get("endorsements", 0) or s.get("endorsements_count", 0),
            }
            for s in skills
        ]
    if li.get("experience"):
        condensed["linkedin"]["experience"] = [
            {
                "title": e.get("title", ""),
                "company": e.get("company", ""),
                "description": (e.get("description") or "")[:200],
                "start_date": e.get("start_date", ""),
                "end_date": e.get("end_date", ""),
            }
            for e in li["experience"][:5]
        ]

    journey = raw.get("journey", {})
    if journey.get("events"):
        priority = {"achievement": 0, "milestone": 1, "development": 2, "learning": 3, "fix": 4}
        sorted_events = sorted(
            journey["events"], key=lambda e: priority.get(e.get("category", ""), 5)
        )
        condensed["journey"] = {
            "event_count": len(journey["events"]),
            "events": [
                {
                    "date": e.get("event_date", ""),
                    "title": e.get("title", "")[:60],
                    "category": e.get("category", ""),
                    "technologies": (e.get("technologies") or [])[:5],
                }
                for e in sorted_events[:20]
            ],
        }
    else:
        condensed["journey"] = {"event_count": 0, "events": []}
    if journey.get("narratives"):
        condensed["journey"]["narratives"] = [
            {
                "type": n.get("narrative_type", ""),
                "title": n.get("title", ""),
                "content": n.get("content", "")[:150],
            }
            for n in journey["narratives"][:15]
        ]

    condensed["experiences"] = raw.get("experiences", [])
    resumes = raw.get("resumes", [])
    condensed["resumes"] = [
        {
            "source": r.get("source", ""),
            "file_name": r.get("file_name", ""),
            "text_preview": (r.get("parsed_text") or "")[:500],
        }
        for r in resumes[:3]
    ]
    condensed["skills_interviews"] = raw.get("skills_interviews", [])
    wip_projects = raw.get("wip_projects", [])
    condensed["wip_projects"] = [
        {
            "name": p.get("name", ""),
            "description": p.get("description", ""),
            "technologies": p.get("technologies", [])[:30],
            "architecture_patterns": p.get("architecture_patterns", []),
            "skills_demonstrated": p.get("skills_demonstrated", []),
            "file_count": p.get("file_count", 0),
        }
        for p in wip_projects
    ]
    return condensed


def synthesize_profile(raw):
    """Use LLM to synthesize a unified professional profile from all data sources."""
    from llm_helper import call_llm_quality, extract_json

    condensed = condense_raw_for_llm(raw)
    context = json.dumps(condensed, default=str)
    # Keep under 14000 chars to stay within 16384 token model context window
    # (thinking models consume output token budget for <think> blocks)
    if len(context) > 14000:
        context = context[:14000] + "\n... [truncated]"

    prompt = (
        "You are a senior career strategist analyzing a professional's complete data.\n\n"
        "Analyze ALL the following data sources and synthesize a comprehensive profile.\n"
        "Data includes: LinkedIn profile, client project analyses "
        "(skills, outcomes, technologies),\n"
        "AI journey events/narratives, work-in-progress side projects, and resumes.\n\n"
        "IMPORTANT INSTRUCTIONS:\n"
        "- From journey events and WIP projects, INFER higher-order skills such as:\n"
        "  design thinking, solution architecture, agentic AI design, autonomous systems,\n"
        "  graph-based knowledge engineering, DevOps pipeline design, API design patterns,\n"
        "  enterprise integration strategy, data governance, team leadership.\n"
        "- WIP projects demonstrate ACTIVE skill investment — treat them as strong signals.\n"
        "- Journey achievements/milestones show progression — identify growth patterns.\n"
        "- Cross-reference LinkedIn endorsements with project evidence for confidence.\n\n"
        "DATA SOURCES:\n" + context + "\n\n"
        "Return a JSON object with these fields:\n"
        "{\n"
        '  "professional_summary": "3-4 sentence comprehensive summary",\n'
        '  "career_arc": {"phases": [{"title": "...", "period": "...", "focus": "...",\n'
        '    "key_achievements": [...]}], "trajectory": "...", "years_total": 20},\n'
        '  "technology_mastery": [{"name": "...", "proficiency": "expert|advanced|intermediate|beginner",\n'  # noqa: E501
        '    "years_approx": 5, "contexts": [...],\n'
        '    "evidence": [{"source": "...", "detail": "..."}], "endorsement_count": 50}],\n'
        '  "higher_order_skills": [{"skill": "...", "proficiency": "...",\n'
        '    "evidence": [...], "demonstrated_in": [...]}],\n'
        '  "business_impacts": [{"title": "...", "context": "...", "scope": "...",\n'
        '    "metrics": {"before": "...", "after": "...", "improvement": "..."},\n'
        '    "star_bullet": "...", "evidence_sources": [...]}],\n'
        '  "leadership_profile": {"team_scope": "...", "mentoring_evidence": [...],\n'
        '    "cross_functional": [...], "decision_examples": [...]},\n'
        '  "differentiators": [{"theme": "...", "evidence": [...], "narrative": "..."}],\n'
        '  "knowledge_gaps": [{"area": "...", "current_level": "...", "evidence": "..."}],\n'
        '  "cross_source_insights": [{"insight": "...", "sources": [...], "significance": "..."}]\n'
        "}\n\nBe thorough and evidence-based. Return ONLY valid JSON."
    )

    # 12000 tokens: thinking models (Qwen3) use ~6000 for <think> block + ~6000 for JSON output
    raw_response = call_llm_quality(prompt, task_type="reasoning", max_tokens=12000)
    return extract_json(raw_response) if raw_response else None


def build_fallback_profile(raw):
    """Build a basic profile from raw data without LLM."""
    li = raw.get("linkedin", {})
    profile = {
        "professional_summary": li.get("summary", "Profile built from available data sources."),
        "career_arc": {"phases": [], "trajectory": "", "years_total": 0},
        "technology_mastery": [],
        "business_impacts": [],
        "leadership_profile": {
            "team_scope": "",
            "mentoring_evidence": [],
            "cross_functional": [],
            "decision_examples": [],
        },
        "differentiators": [],
        "knowledge_gaps": [],
        "cross_source_insights": [],
    }

    for skill in li.get("skills", [])[:20]:
        name = skill.get("name") or skill.get("skill", "")
        endorsements = skill.get("endorsements", 0) or skill.get("endorsements_count", 0)
        if name:
            proficiency = (
                "expert"
                if endorsements > 50
                else (
                    "advanced"
                    if endorsements > 20
                    else ("intermediate" if endorsements > 5 else "beginner")
                )
            )
            profile["technology_mastery"].append(
                {
                    "name": name,
                    "proficiency": proficiency,
                    "years_approx": 0,
                    "contexts": [],
                    "evidence": [{"source": "LinkedIn", "detail": f"{endorsements} endorsements"}],
                    "endorsement_count": endorsements,
                }
            )

    for exp in li.get("experience", []):
        profile["career_arc"]["phases"].append(
            {
                "title": exp.get("title", ""),
                "period": f"{exp.get('start_date', '')} - {exp.get('end_date', 'Present')}",
                "focus": exp.get("company", ""),
                "key_achievements": [],
            }
        )

    return profile


def synthesize_for_role(profile, job_text):
    """Generate role-specific synthesis from a deep profile and job description."""
    from llm_helper import call_llm_quality, extract_json

    profile_str = json.dumps(profile, default=str)
    if len(profile_str) > 8000:
        profile_str = profile_str[:8000] + "\n... [truncated]"

    prompt = (
        "You are a career strategist creating a role-specific presentation.\n\n"
        "DEEP PROFILE:\n" + profile_str + "\n\n"
        "TARGET JOB DESCRIPTION:\n" + job_text[:4000] + "\n\n"
        "Analyze the fit and return a JSON object:\n"
        "{\n"
        '  "fit_score": 85,\n'
        '  "top_angles": [{"angle": "...", "evidence": "...", "strength": "strong|moderate|emerging"}],\n'  # noqa: E501
        '  "tailored_bullets": [{"bullet": "STAR-format bullet", "relevance": "high|medium"}],\n'
        '  "gap_mitigation": [{"gap": "...", "mitigation": "...", "transferable_skill": "..."}],\n'
        '  "interview_talking_points": [{"topic": "...", "story": "...", "connection_to_role": "..."}]\n'  # noqa: E501
        "}\n\nReturn ONLY valid JSON."
    )

    raw_response = call_llm_quality(prompt, task_type="reasoning", max_tokens=4096)
    return extract_json(raw_response) if raw_response else None
