"""Career Advisor Analysis — career context building, phase extraction, skills portfolio."""

# Module contents:
# _build_career_context()      — builds career context dict from all data sources
# _extract_career_phases()     — groups career history into chronological phases
# _compute_skills_portfolio()  — categorizes skills into current/growing/developing buckets
# _market_recommendations()    — generates role-specific market recommendations
# _save_analysis()             — persists analysis result to SQLite

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List

from models import get_db

logger = logging.getLogger(__name__)


class _CareerAdvisorAnalysisMixin:

    def _build_career_context(self, user_id: int) -> Dict[str, Any]:
        """Aggregate all career data sources into a single context dict.

        Gathers:
        - User profile (LinkedIn + resume + deep profile via base class)
        - Journey events from SQLite
        - Client project data
        - Skills portfolio (categorised)
        - Pre-rendered text snippets for LLM prompts

        Returns dict with keys: profile, profile_text, journey_events,
        journey_text, projects, phases_text, skills_portfolio.
        """
        profile = self._get_user_profile(user_id)
        profile_text = self._profile_summary(profile)

        # Journey events
        journey_events: List[Dict[str, Any]] = []
        journey_text = ""
        try:
            with get_db() as conn:
                events = conn.execute(
                    "SELECT title, category, technologies, event_date "
                    "FROM journey_events WHERE user_id = ? "
                    "ORDER BY event_date DESC LIMIT 30",
                    (user_id,),
                ).fetchall()
            journey_events = [dict(e) for e in events]
            if journey_events:
                lines = [
                    f"- {e['title']} ({e['category']})"
                    + (f" [{e['event_date']}]" if e.get("event_date") else "")
                    for e in journey_events
                ]
                journey_text = "\n\nRecent career events:\n" + "\n".join(lines)
        except Exception:
            pass

        # Client projects
        projects: List[Dict[str, Any]] = []
        try:
            with get_db() as conn:
                rows = conn.execute(
                    "SELECT client_name, analysis_json FROM client_projects "
                    "WHERE user_id = ? AND status = 'approved' LIMIT 10",
                    (user_id,),
                ).fetchall()
            for r in rows:
                proj: Dict[str, Any] = {"client_name": r["client_name"]}
                try:
                    proj["analysis"] = json.loads(r["analysis_json"] or "{}")
                except (json.JSONDecodeError, TypeError):
                    proj["analysis"] = {}
                projects.append(proj)
        except Exception:
            pass

        # Career phases (local extraction)
        phases = self._extract_career_phases(profile, projects, journey_events)
        phases_text = ""
        if phases:
            phase_lines = [
                f"- {p.get('phase_name', 'Phase')}: {p.get('description', '')}" for p in phases
            ]
            phases_text = "\n\nDetected career phases:\n" + "\n".join(phase_lines)

        # Skills portfolio
        portfolio = self._compute_skills_portfolio(profile)

        return {
            "profile": profile,
            "profile_text": profile_text,
            "journey_events": journey_events,
            "journey_text": journey_text,
            "projects": projects,
            "phases_text": phases_text,
            "skills_portfolio": portfolio,
        }

    def _extract_career_phases(
        self,
        profile: Dict[str, Any],
        projects: List[Dict[str, Any]],
        journey_events: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Detect career phases from profile, projects, and journey events.

        Uses heuristics (experience entries, project timelines, event categories)
        to segment the career into logical phases.  Does NOT call the LLM.

        Returns list of dicts with phase_name, description, skills, and
        approximate ordering.
        """
        phases: List[Dict[str, Any]] = []

        # Phase detection from LinkedIn experience
        experience = profile.get("linkedin", {}).get("experience", [])
        for i, exp in enumerate(experience if isinstance(experience, list) else []):
            if not isinstance(exp, dict):
                continue
            title = exp.get("title", "")
            company = exp.get("company", "")
            if title or company:
                phases.append(
                    {
                        "phase_name": f"{title} at {company}".strip(" at "),  # noqa: B005
                        "description": f"Role: {title}, Company: {company}",
                        "skills": [],
                        "order": i,
                    }
                )

        # Enrich with project data
        for proj in projects:
            client = proj.get("client_name", "")
            analysis = proj.get("analysis", {})
            techs: List[str] = []
            if isinstance(analysis, dict):
                tech_data = analysis.get("technologies", [])
                if isinstance(tech_data, list):
                    techs = [
                        t.get("name", str(t)) if isinstance(t, dict) else str(t)
                        for t in tech_data[:10]
                    ]
            # Try to match to an existing phase
            matched = False
            for phase in phases:
                if client and client.lower() in phase.get("description", "").lower():
                    phase["skills"] = list(set(phase.get("skills", []) + techs))
                    matched = True
                    break
            if not matched and client:
                phases.append(
                    {
                        "phase_name": f"Project: {client}",
                        "description": f"Client project for {client}",
                        "skills": techs,
                        "order": len(phases),
                    }
                )

        # Enrich with journey event categories
        categories: Dict[str, int] = {}
        for evt in journey_events:
            cat = evt.get("category", "")
            if cat:
                categories[cat] = categories.get(cat, 0) + 1

        if categories and not phases:
            # No experience data — create phases from event categories
            for cat, count in sorted(categories.items(), key=lambda x: -x[1])[:5]:
                phases.append(
                    {
                        "phase_name": cat.replace("_", " ").title(),
                        "description": f"{count} events in {cat}",
                        "skills": [],
                        "order": len(phases),
                    }
                )

        return phases

    def _compute_skills_portfolio(self, profile: Dict[str, Any]) -> Dict[str, List[str]]:
        """Categorise all known skills into a structured portfolio.

        Aggregates skills from LinkedIn, deep profile (technologies,
        higher-order skills), and resume text into categories:
        technical, leadership, domain, tools, and methodologies.

        Returns dict mapping category name to list of skill strings.
        """
        all_skills: List[str] = []

        # LinkedIn skills
        li_skills = profile.get("linkedin", {}).get("skills", [])
        for s in li_skills if isinstance(li_skills, list) else []:
            name = s.get("skill", s.get("name", str(s))) if isinstance(s, dict) else str(s)
            if name:
                all_skills.append(name)

        # Deep profile technologies
        techs = profile.get("top_technologies", [])
        if isinstance(techs, list):
            all_skills.extend(str(t) for t in techs)

        # Higher-order skills
        hos = profile.get("higher_order_skills", [])
        if isinstance(hos, list):
            all_skills.extend(str(s) for s in hos)

        # Differentiators
        diffs = profile.get("differentiators", [])
        if isinstance(diffs, list):
            all_skills.extend(str(d) for d in diffs)

        # Deduplicate preserving order
        seen: set[str] = set()
        unique: List[str] = []
        for s in all_skills:
            key = s.strip().lower()
            if key and key not in seen:
                seen.add(key)
                unique.append(s.strip())

        # Categorise via keyword heuristics
        technical_kw = {
            "python",
            "java",
            "javascript",
            "typescript",
            "go",
            "rust",
            "c++",
            "c#",
            "sql",
            "nosql",
            "react",
            "angular",
            "vue",
            "node",
            "fastapi",
            "flask",
            "django",
            "spring",
            "kubernetes",
            "docker",
            "aws",
            "azure",
            "gcp",
            "terraform",
            "kafka",
            "redis",
            "postgresql",
            "mongodb",
            "graphql",
            "rest",
            "api",
            "microservices",
            "machine learning",
            "deep learning",
            "llm",
            "ai",
            "ml",
            "nlp",
            "data engineering",
            "data science",
        }
        leadership_kw = {
            "leadership",
            "management",
            "strategy",
            "mentoring",
            "coaching",
            "stakeholder",
            "executive",
            "team building",
            "cross-functional",
            "roadmap",
            "vision",
            "transformation",
            "change management",
        }
        methodology_kw = {
            "agile",
            "scrum",
            "kanban",
            "devops",
            "ci/cd",
            "tdd",
            "bdd",
            "design thinking",
            "lean",
            "six sigma",
            "sre",
            "itil",
        }

        portfolio: Dict[str, List[str]] = {
            "technical": [],
            "leadership": [],
            "domain": [],
            "tools": [],
            "methodologies": [],
        }

        for skill in unique:
            skill_lower = skill.lower()
            if any(kw in skill_lower for kw in technical_kw):
                portfolio["technical"].append(skill)
            elif any(kw in skill_lower for kw in leadership_kw):
                portfolio["leadership"].append(skill)
            elif any(kw in skill_lower for kw in methodology_kw):
                portfolio["methodologies"].append(skill)
            else:
                portfolio["domain"].append(skill)

        return portfolio

    def _market_recommendations(
        self,
        top_demand: List[tuple[str, int]],
        skills_have: Dict[str, int],
        total: int,
    ) -> List[str]:
        """Generate actionable recommendations from demand vs supply data."""
        recs: List[str] = []
        if total == 0:
            return ["Start searching for jobs to build market data."]
        for skill, count in top_demand[:5]:
            if skill not in skills_have:
                recs.append(f"'{skill}' appears in {count} postings — consider learning it.")
        if not recs:
            recs.append("Your skills align well with market demand.")
        return recs

    def _save_analysis(
        self,
        user_id: int,
        analysis_type: str,
        result: Dict[str, Any],
        target_role: str = "",
    ) -> str:
        """Persist a career analysis result to the career_analyses table.

        Returns the generated analysis ID.
        """
        analysis_id = str(uuid.uuid4())
        with get_db() as conn:
            conn.execute(
                "INSERT INTO career_analyses "
                "(id, user_id, analysis_type, target_role, result_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (analysis_id, user_id, analysis_type, target_role, json.dumps(result)),
            )
            conn.commit()
        return analysis_id
