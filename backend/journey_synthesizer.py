"""
LLM-powered narrative generation from journey timeline.
Generates resume entries, LinkedIn sections, and campaign seeds.
"""

import contextlib
import json
from datetime import datetime, timezone

from llm_helper import call_llm_quality, extract_json
from models import get_db

# Outcome type rank for sorting (same as agentic_compiler)
_OUTCOME_TYPE_RANK = {
    "revenue_growth": 11,
    "cost_reduction": 10,
    "efficiency_improvement": 9,
    "scale_achievement": 8,
    "quality_improvement": 7,
    "customer_satisfaction": 6,
    "risk_reduction": 5,
    "team_org_impact": 4,
    "process_automation": 3,
    "capability_enablement": 2,
    "time_savings": 1,
}


class JourneySynthesizer:
    """Generate professional narratives from journey events."""

    def generate_all(self, user_id):
        """Generate all narrative types."""
        events = self._get_events_summary()
        skills = self._get_skills_summary()

        if not events:
            return

        context = self._build_context(events, skills)

        self._generate_resume_entries(user_id, context)
        self._generate_linkedin_sections(user_id, context)
        self._generate_campaign_seeds(user_id, context)
        self._generate_learning_arc(user_id, context)
        self._generate_theme_index(user_id, context)

    def _get_events_summary(self):
        with get_db() as conn:
            rows = conn.execute(
                "SELECT event_date, title, category, technologies "
                "FROM journey_events ORDER BY event_date LIMIT 200"
            ).fetchall()
        return [dict(r) for r in rows]

    def _get_skills_summary(self):
        with get_db() as conn:
            rows = conn.execute(
                "SELECT technologies FROM journey_events WHERE technologies != '[]'"
            ).fetchall()

        skill_counts = {}
        for row in rows:
            try:
                techs = json.loads(row[0])
            except (json.JSONDecodeError, TypeError):
                continue
            for tech in techs:
                skill_counts[tech] = skill_counts.get(tech, 0) + 1

        return sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)

    def _build_context(self, events, skills):
        lines = ["=== AI Journey Timeline (key events) ==="]
        for e in events[:50]:
            lines.append(f"  {e['event_date']}: [{e['category']}] {e['title']}")

        lines.append("\n=== Skills (by frequency) ===")
        for skill, count in skills[:30]:
            lines.append(f"  {skill}: {count} events")

        return "\n".join(lines)

    def _generate_resume_entries(self, user_id, context):
        prompt = (
            "Based on this AI/ML journey timeline and skills, "
            "generate 3-5 STAR-format resume bullet points.\n\n"
            "Requirements:\n"
            '- Employer: "Independent / Personal Project"\n'
            "- Each bullet: action verb + what was done + outcome\n"
            "- Focus on: local AI deployment, GPU optimization, "
            "agentic workflows, knowledge graphs\n"
            "- Be specific with technologies named in the timeline\n"
            "- CRITICAL: Do NOT invent percentages, multipliers, or numeric metrics "
            "unless they appear explicitly in the source timeline. "
            "Describe outcomes qualitatively if no hard numbers are available.\n\n"
            "Return a JSON array of objects with fields:\n"
            '- "title": short title (3-5 words)\n'
            '- "bullet": the full STAR-format bullet point\n'
            '- "technologies": array of tech names used'
        )

        raw = call_llm_quality(f"{prompt}\n\n{context}", task_type="coding", max_tokens=2048)
        items = extract_json(raw) if raw else None

        if isinstance(items, list):
            for item in items:
                self._store_narrative(
                    user_id,
                    "resume_entry",
                    item.get("title", ""),
                    item.get("bullet", json.dumps(item)),
                )

    def _generate_linkedin_sections(self, user_id, context):
        prompt = """Based on this AI/ML journey, generate LinkedIn profile additions.

Return a JSON object with:
- "headline_addition": a phrase to add to the existing headline (10-15 words max)
- "summary_paragraph": a paragraph about the AI journey for the LinkedIn summary (100-150 words)
- "featured_projects": array of 2-3 objects with "title" and "description" (30-50 words each)"""

        raw = call_llm_quality(f"{prompt}\n\n{context}", task_type="coding", max_tokens=2048)
        parsed = extract_json(raw) if raw else None

        if isinstance(parsed, dict):
            if parsed.get("headline_addition"):
                self._store_narrative(
                    user_id,
                    "linkedin_headline",
                    "Headline Addition",
                    parsed["headline_addition"],
                )
            if parsed.get("summary_paragraph"):
                self._store_narrative(
                    user_id,
                    "linkedin_summary",
                    "Summary Paragraph",
                    parsed["summary_paragraph"],
                )
            for proj in parsed.get("featured_projects", []):
                self._store_narrative(
                    user_id,
                    "linkedin_project",
                    proj.get("title", ""),
                    proj.get("description", ""),
                )

    def _get_business_outcomes_summary(self):
        """Load top business outcomes from approved client projects."""
        outcomes = []
        with contextlib.suppress(Exception), get_db() as conn:
            rows = conn.execute(
                "SELECT client_name, business_outcomes_json FROM client_projects "
                "WHERE approved = 1 AND business_outcomes_json IS NOT NULL"
            ).fetchall()
            for row in rows:
                try:
                    bo_list = json.loads(row["business_outcomes_json"] or "[]")
                except (json.JSONDecodeError, TypeError):
                    continue
                if not isinstance(bo_list, list):
                    continue
                for bo in bo_list:
                    if not isinstance(bo, dict) or not bo.get("outcome_title"):
                        continue
                    outcomes.append(
                        {
                            "client": row["client_name"],
                            "title": bo["outcome_title"],
                            "type": bo.get("outcome_type", ""),
                            "metric": bo.get("metric_value", ""),
                            "confidence": bo.get("confidence", 0),
                        }
                    )

        # Sort by outcome type rank (descending) then confidence
        outcomes.sort(
            key=lambda x: (
                _OUTCOME_TYPE_RANK.get(x.get("type", ""), 0),
                x.get("confidence", 0),
            ),
            reverse=True,
        )
        return outcomes[:10]

    def _generate_campaign_seeds(self, user_id, context):
        # Load business outcomes for grounding
        outcomes = self._get_business_outcomes_summary()
        outcomes_context = ""
        if outcomes:
            lines = ["\n=== Business Outcomes (from client projects) ==="]
            for o in outcomes:
                line = f"  [{o['type']}] {o['title']}"
                if o.get("metric"):
                    line += f" ({o['metric']})"
                line += f" — {o['client']}"
                lines.append(line)
            outcomes_context = "\n".join(lines)

        prompt = """Based on this AI/ML journey, suggest 3-5 LinkedIn content campaign themes.

For each theme, return a JSON array of objects with:
- "theme": campaign theme name (3-5 words)
- "description": what the campaign would cover (1-2 sentences)
- "post_angles": array of 3 specific post ideas (one-line each)
- "target_audience": who would find this valuable
- "grounding_outcome": the business outcome that best supports this theme (or null if none)"""

        full_context = context
        if outcomes_context:
            full_context += outcomes_context

        raw = call_llm_quality(f"{prompt}\n\n{full_context}", task_type="coding", max_tokens=2048)
        items = extract_json(raw) if raw else None

        if isinstance(items, list):
            for item in items:
                self._store_narrative(
                    user_id,
                    "campaign_seed",
                    item.get("theme", ""),
                    json.dumps(item),
                )

    def _generate_learning_arc(self, user_id, context):
        """Generate a 3-5 phase learning progression narrative from journey events."""
        from llm_helper import synthesize_narrative

        prompt = (
            "Based on this AI/ML journey timeline, generate a professional learning "
            "arc narrative showing 3-5 distinct phases of skill development.\n\n"
            "For each phase, describe:\n"
            "- Phase name (e.g., 'Foundation', 'Specialization', 'Leadership')\n"
            "- Time period (approximate)\n"
            "- Key skills acquired\n"
            "- Defining projects or milestones\n"
            "- Growth narrative (2-3 sentences)\n\n"
            "Write as a cohesive professional story, not bullet points. "
            "Suitable for a LinkedIn 'About' section or cover letter intro."
        )

        narrative = synthesize_narrative(context, prompt, max_tokens=2048)
        if narrative and len(narrative) > 50:
            self._store_narrative(user_id, "learning_arc", "Learning Arc", narrative)

    def _generate_theme_index(self, user_id, context):
        """Cluster journey events into 5-10 marketable content themes."""
        prompt = (
            "Based on this AI/ML journey timeline and skills, identify 5-10 "
            "distinct marketable content themes for LinkedIn thought leadership.\n\n"
            "Return a JSON array of objects with:\n"
            '- "theme": short theme name (3-5 words)\n'
            '- "description": what this theme covers (1-2 sentences)\n'
            '- "evidence_count": approximate number of journey events supporting it\n'
            '- "audience": who would find this valuable\n'
            '- "sample_hook": a compelling opening line for a post on this theme'
        )

        raw = call_llm_quality(f"{prompt}\n\n{context}", task_type="coding", max_tokens=2048)
        items = extract_json(raw) if raw else None

        if isinstance(items, list):
            self._store_narrative(user_id, "theme_index", "Content Theme Index", json.dumps(items))

    def generate_with_interview_context(self, user_id, interview_conversation):
        """Generate narratives incorporating user's conversational input (goals, preferences)."""
        events = self._get_events_summary()
        skills = self._get_skills_summary()
        if not events:
            return

        journey_context = self._build_context(events, skills)

        prompt = (
            "Based on this AI/ML journey timeline AND the user's interview conversation, "
            "generate personalized professional narratives.\n\n"
            "The user has told you their goals, which experiences to highlight, "
            "and their preferred tone. Respect their direction.\n\n"
            "Generate a JSON object with:\n"
            '- "resume_bullets": array of 3-5 STAR-format bullet points (strings)\n'
            '- "linkedin_summary": a paragraph (100-150 words) for LinkedIn About\n'
            '- "key_themes": array of 2-3 theme strings for campaign content\n\n'
            f"Journey data:\n{journey_context}\n\n"
            f"User interview:\n{interview_conversation}\n\n"
            "Return ONLY JSON."
        )

        raw = call_llm_quality(prompt, task_type="reasoning", max_tokens=2048)
        parsed = extract_json(raw) if raw else None

        if isinstance(parsed, dict):
            for bullet in parsed.get("resume_bullets", []):
                self._store_narrative(user_id, "resume_entry", "Interview-generated", bullet)
            if parsed.get("linkedin_summary"):
                self._store_narrative(
                    user_id, "linkedin_summary", "Interview Summary", parsed["linkedin_summary"]
                )
            for theme in parsed.get("key_themes", []):
                self._store_narrative(user_id, "campaign_seed", theme, theme)

    def regenerate_linkedin_sections(self, user_id, deep_profile, pf_context=""):
        """Regenerate LinkedIn headline, summary, and featured projects.

        Supersedes existing linkedin_* narratives for user_id (sets superseded_at)
        and inserts new rows with leadership-framed content.

        Args:
            user_id: int — target user
            deep_profile: dict — differentiators, technology_mastery, etc.
            pf_context: str — PersonaForge persona context string

        Returns:
            dict with headline, summary_paragraph, featured_projects keys (or None on failure)
        """
        differentiators = deep_profile.get("differentiators", [])
        # differentiators can be strings OR dicts {"theme": ..., "narrative": ...}
        diff_names = [
            d.get("theme", str(d)) if isinstance(d, dict) else str(d) for d in differentiators
        ]
        tech_mastery = deep_profile.get("technology_mastery", [])
        tech_names = [
            t.get("name", str(t)) if isinstance(t, dict) else str(t) for t in tech_mastery[:10]
        ]

        diff_block = ", ".join(diff_names) if diff_names else "senior leader"
        tech_block = ", ".join(tech_names) if tech_names else "enterprise technology"
        pf_block = f"\n\nPersonaForge context:\n{pf_context}" if pf_context else ""

        prompt = (
            "You are writing a LinkedIn profile for a SENIOR PRACTICE LEADER, "
            "NOT an individual contributor engineer.\n\n"
            "Key differentiators: " + diff_block + "\n"
            "Technology mastery: " + tech_block + pf_block + "\n\n"
            "Generate a JSON object with:\n"
            '- "headline": LinkedIn headline (max 220 chars). '
            "Use director/practice/leader/executive framing. "
            "NO 'AI/ML Engineer', 'full-stack', or IC-engineer language.\n"
            '- "summary_paragraph": LinkedIn About section (150-250 words). '
            "Lead with strategic impact, P&L ownership, and team leadership. "
            "Reference specific companies and quantified outcomes.\n"
            '- "featured_projects": array of 2-3 objects with "title" and "description" '
            "(30-50 words each) showing practice-building or enterprise-scale work.\n\n"
            "Return ONLY valid JSON."
        )

        raw = call_llm_quality(prompt, task_type="reasoning", max_tokens=2048)
        parsed = extract_json(raw) if raw else None

        if not isinstance(parsed, dict):
            return None

        # Supersede existing linkedin_* narratives for this user
        # Use microsecond precision so new rows sort after superseded ones
        now_us = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")

        with get_db() as conn:
            conn.execute(
                "UPDATE journey_narratives "
                "SET superseded_at = CURRENT_TIMESTAMP "
                "WHERE user_id = ? AND narrative_type IN "
                "('linkedin_headline', 'linkedin_summary', 'linkedin_project') "
                "AND superseded_at IS NULL",
                (user_id,),
            )
            conn.commit()

            # Insert new rows
            if parsed.get("headline"):
                conn.execute(
                    "INSERT INTO journey_narratives "
                    "(user_id, narrative_type, title, content, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (user_id, "linkedin_headline", "Headline", parsed["headline"], now_us),
                )
            if parsed.get("summary_paragraph"):
                conn.execute(
                    "INSERT INTO journey_narratives "
                    "(user_id, narrative_type, title, content, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (user_id, "linkedin_summary", "Summary", parsed["summary_paragraph"], now_us),
                )
            for proj in parsed.get("featured_projects", []):
                conn.execute(
                    "INSERT INTO journey_narratives "
                    "(user_id, narrative_type, title, content, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        user_id,
                        "linkedin_project",
                        proj.get("title", ""),
                        proj.get("description", ""),
                        now_us,
                    ),
                )
            conn.commit()

        return parsed

    def regenerate_campaign_seeds(self, user_id, deep_profile, linkedin_headline=""):
        """Regenerate campaign seeds aligned with deep profile differentiators.

        Args:
            user_id: int — target user
            deep_profile: dict — differentiators, technology_mastery, etc.
            linkedin_headline: str — current headline for positioning context

        Returns:
            dict with campaign_seeds key (or None on failure)
        """
        differentiators = deep_profile.get("differentiators", [])
        diff_names = [
            d.get("theme", str(d)) if isinstance(d, dict) else str(d) for d in differentiators
        ]
        diff_block = ", ".join(diff_names) if diff_names else "senior leader"
        headline_block = f"\nLinkedIn headline: {linkedin_headline}" if linkedin_headline else ""

        prompt = (
            "Generate LinkedIn content campaign seeds for a SENIOR PRACTICE LEADER.\n"
            "Differentiators: " + diff_block + headline_block + "\n\n"
            "Return a JSON object with:\n"
            '- "campaign_seeds": array of 3-5 objects, each with:\n'
            '  - "theme": campaign theme (3-6 words, leadership/practice/enterprise focus)\n'
            '  - "audience": target audience (CTOs, CDOs, enterprise architects, etc.)\n'
            '  - "content_angle": what angle/story to tell (1-2 sentences)\n\n'
            "Each seed must connect to at least one differentiator theme. "
            "Return ONLY valid JSON."
        )

        raw = call_llm_quality(prompt, task_type="reasoning", max_tokens=1024)
        parsed = extract_json(raw) if raw else None

        if not isinstance(parsed, dict):
            return None

        # Store seeds, superseding old ones
        with get_db() as conn:
            conn.execute(
                "UPDATE journey_narratives "
                "SET superseded_at = CURRENT_TIMESTAMP "
                "WHERE user_id = ? AND narrative_type = 'campaign_seed' "
                "AND superseded_at IS NULL",
                (user_id,),
            )
            conn.commit()

            for seed in parsed.get("campaign_seeds", []):
                conn.execute(
                    "INSERT INTO journey_narratives "
                    "(user_id, narrative_type, title, content) VALUES (?, ?, ?, ?)",
                    (user_id, "campaign_seed", seed.get("theme", ""), json.dumps(seed)),
                )
            conn.commit()

        return parsed

    def _store_narrative(self, user_id, narrative_type, title, content):
        with get_db() as conn:
            conn.execute(
                "INSERT INTO journey_narratives "
                "(user_id, narrative_type, title, content) "
                "VALUES (?, ?, ?, ?)",
                (user_id, narrative_type, title, content),
            )
            conn.commit()
