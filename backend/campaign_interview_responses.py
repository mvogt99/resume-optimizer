"""
CampaignInterviewerResponseMixin — LLM response generation and graph suggestions.

Split from campaign_interview.py to comply with 500-line file limit.
Inherited by CampaignInterviewer.
"""

import json

from llm_helper import call_llm, call_llm_quality
from models import get_db

STAGES = [
    "theme",
    "audience",
    "tone",
    "storyline",
    "post_count",
    "content_seeds",
    "review",
]

STAGE_DESCRIPTIONS = {
    "theme": "selecting the campaign theme",
    "audience": "defining the target audience",
    "tone": "setting the voice and tone",
    "storyline": "crafting the narrative arc",
    "post_count": "deciding post count and cadence",
    "content_seeds": "generating specific post ideas",
    "review": "reviewing the full campaign outline",
}


class CampaignInterviewerResponseMixin:
    """Mixin providing response generation and suggestion methods for CampaignInterviewer."""

    # --- Private: extraction ---

    def _extract_from_message(self, context, stage, message):
        msg = message.strip()
        if stage == "theme":
            if msg:
                context["theme"] = msg
        elif stage == "audience":
            if msg:
                context["audience"] = msg
        elif stage == "tone":
            if msg:
                context["tone"] = msg
        elif stage == "storyline":
            if msg:
                context["storyline"] = msg
        elif stage == "post_count":
            # Try to extract a number
            import re

            nums = re.findall(r"\d+", msg)
            if nums:
                context["post_count"] = min(int(nums[0]), 20)
            else:
                context["post_count"] = 5  # default
            context["cadence"] = msg
        elif stage == "content_seeds" and not context.get("seeds"):
            # LLM will generate seeds; user message is confirmation/adjustment
            context["seeds"] = self._generate_seeds(context)
        return context

    def _advance_stage(self, current_stage, context):
        try:
            idx = STAGES.index(current_stage)
        except ValueError:
            return "theme"

        if current_stage == "review":
            return "review"

        return STAGES[min(idx + 1, len(STAGES) - 1)]

    # --- Private: response generation ---

    def _generate_response(self, context, new_stage, user_message, suggestions):
        """Try LLM, fall back to templates."""
        llm_response = self._call_llm_for_stage(context, new_stage, user_message, suggestions)
        if llm_response:
            return llm_response
        return self._template_response(context, new_stage, suggestions)

    def _call_llm_for_stage(self, context, stage, user_message, suggestions):
        suggestion_text = ""
        if suggestions:
            items = [s.get("name", s.get("theme", str(s))) for s in suggestions[:5]]
            suggestion_text = f"\nSuggestions from knowledge graph: {', '.join(items)}"

        prompt = (
            "You are a LinkedIn marketing strategist helping plan a content campaign.\n\n"
            f"Current stage: {stage} — {STAGE_DESCRIPTIONS.get(stage, '')}\n"
            f"Campaign context so far:\n"
            f"- Theme: {context.get('theme', 'not set')}\n"
            f"- Audience: {context.get('audience', 'not set')}\n"
            f"- Tone: {context.get('tone', 'not set')}\n"
            f"- Storyline: {context.get('storyline', 'not set')}\n"
            f"- Post count: {context.get('post_count', 'not set')}\n"
            f"{suggestion_text}\n\n"
            f"User just said: {user_message}\n\n"
            "Respond with a natural, focused question to gather info for this stage. "
            "If transitioning to the next stage, acknowledge what was decided and ask "
            "the next question. Keep it conversational (2-4 sentences). "
            "If this is the review stage, present a clear summary of the full campaign plan."
        )

        return call_llm_quality(prompt, task_type="reasoning", max_tokens=512)

    def _template_response(self, context, stage, suggestions):
        """Fallback template questions."""
        suggestion_suffix = ""
        if suggestions:
            items = [s.get("name", s.get("theme", str(s))) for s in suggestions[:3]]
            suggestion_suffix = "\n\nSuggestions: " + ", ".join(items)

        templates = {
            "theme": (
                "What theme would you like to build your campaign around? "
                "This could be a technology area, leadership insight, or industry trend."
                + suggestion_suffix
            ),
            "audience": (
                f'Great theme: **{context.get("theme", "")}**!\n\n'
                "Who is your target audience? Think about job titles, industries, "
                "or professional communities that would benefit from this content."
                + suggestion_suffix
            ),
            "tone": (
                "What tone and voice should the campaign use?\n\n"
                "Options: thought-leader, conversational, technical deep-dive, "
                "storytelling, or a mix. What feels right for you?"
            ),
            "storyline": (
                "What narrative arc should tie the posts together?\n\n"
                "For example: problem → exploration → solution → results, "
                "or chronological journey, or contrarian takes." + suggestion_suffix
            ),
            "post_count": (
                "How many posts should the campaign include, and what cadence?\n\n"
                "Typical LinkedIn campaigns: 3-5 posts over 1-2 weeks, "
                "or 8-12 posts over a month."
            ),
            "content_seeds": (
                "Based on your campaign plan, here are suggested post topics. "
                "Do these look good, or would you like to adjust?\n\n"
                + self._format_seeds(context.get("seeds", []))
            ),
            "review": self._format_review(context),
        }
        return templates.get(stage, templates["theme"])

    def _format_seeds(self, seeds):
        if not seeds:
            return "(No seeds generated yet)"
        lines = []
        for i, seed in enumerate(seeds):
            title = seed.get("title", f"Post {i + 1}")
            points = seed.get("key_points", [])
            lines.append(f"**{i + 1}. {title}**")
            for p in points[:3]:
                lines.append(f"   - {p}")
        return "\n".join(lines)

    def _format_review(self, context):
        seeds_text = self._format_seeds(context.get("seeds", []))
        return (
            "Here's your complete campaign plan:\n\n"
            f"**Theme:** {context.get('theme', 'N/A')}\n"
            f"**Audience:** {context.get('audience', 'N/A')}\n"
            f"**Tone:** {context.get('tone', 'N/A')}\n"
            f"**Storyline:** {context.get('storyline', 'N/A')}\n"
            f"**Posts:** {context.get('post_count', 0)} ({context.get('cadence', 'N/A')})\n\n"
            f"**Post Ideas:**\n{seeds_text}\n\n"
            "If this looks good, click **Create Campaign** to proceed to post generation. "
            "Otherwise, tell me what you'd like to change."
        )

    # --- Private: graph-grounded suggestions ---

    def _get_theme_suggestions(self):
        """Suggest themes from journey narratives and skills."""
        try:
            from arango_client import get_graph_client

            arango = get_graph_client()
            if not arango.is_connected:
                return self._get_theme_suggestions_from_db()

            skills = arango.query("FOR s IN ro_ai_skills SORT s.event_count DESC LIMIT 8 RETURN s")
            milestones = arango.query(
                "FOR m IN ro_journey_milestones SORT m.event_date DESC LIMIT 5 "
                "RETURN {title: m.title, date: m.event_date}"
            )
            return skills + milestones
        except Exception:
            return self._get_theme_suggestions_from_db()

    def _get_theme_suggestions_from_db(self):
        """Fallback: get campaign seed narratives from SQLite."""
        with get_db() as conn:
            rows = conn.execute(
                "SELECT title, content FROM journey_narratives "
                "WHERE narrative_type IN ('campaign_seed', 'theme_index') "
                "ORDER BY created_at DESC LIMIT 10"
            ).fetchall()

        results = []
        for row in rows:
            try:
                items = json.loads(row["content"])
                if isinstance(items, list):
                    results.extend(items)
                else:
                    results.append({"theme": row["title"]})
            except (json.JSONDecodeError, TypeError):
                results.append({"theme": row["title"]})
        return results[:8]

    def _get_stage_suggestions(self, stage, context):
        """Get graph-grounded suggestions for a given stage."""
        try:
            from arango_client import get_graph_client

            arango = get_graph_client()
            if not arango.is_connected:
                return []

            if stage == "audience":
                # Suggest from LinkedIn profile skills
                return arango.query(
                    "FOR s IN ro_ai_skills SORT s.event_count DESC LIMIT 5 "
                    "RETURN {name: s.name, type: 'skill'}"
                )
            elif stage == "storyline":
                # Suggest from journey timeline
                return arango.query(
                    "FOR m IN ro_journey_milestones SORT m.event_date LIMIT 5 "
                    "RETURN {name: m.title, date: m.event_date, type: 'milestone'}"
                )
            elif stage == "content_seeds":
                # Knowledge context for the theme
                theme = context.get("theme", "")
                if theme:
                    kc = arango.get_knowledge_context(theme, limit=5)
                    all_items = []
                    for c in kc.get("clients", []):
                        all_items.append(
                            {"name": c.get("name", ""), "type": "client", "_id": c.get("_id", "")}
                        )
                    for s in kc.get("skills", []):
                        all_items.append(
                            {"name": s.get("name", ""), "type": "skill", "_id": s.get("_id", "")}
                        )
                    for m in kc.get("milestones", []):
                        all_items.append(
                            {
                                "name": m.get("title", ""),
                                "type": "milestone",
                                "_id": m.get("_id", ""),
                            }
                        )
                    return all_items
        except Exception:
            pass
        return []

    def _generate_seeds(self, context):
        """Generate post seed ideas using LLM + graph context."""
        count = context.get("post_count", 5) or 5
        theme = context.get("theme", "AI")

        # Try graph context
        source_refs = []
        try:
            from arango_client import get_graph_client

            arango = get_graph_client()
            if arango.is_connected:
                kc = arango.get_knowledge_context(theme, limit=10)
                for c in kc.get("clients", []):
                    source_refs.append(
                        {"type": "client", "_id": c.get("_id", ""), "name": c.get("name", "")}
                    )
                for s in kc.get("skills", []):
                    source_refs.append(
                        {"type": "skill", "_id": s.get("_id", ""), "name": s.get("name", "")}
                    )
                for m in kc.get("milestones", []):
                    source_refs.append(
                        {"type": "milestone", "_id": m.get("_id", ""), "name": m.get("title", "")}
                    )
        except Exception:
            pass

        ref_text = ""
        if source_refs:
            ref_text = "\n\nAvailable source references from knowledge graph:\n"
            ref_text += "\n".join(f"- [{r['type']}] {r.get('name', '')}" for r in source_refs[:10])

        prompt = (
            f"Generate {count} LinkedIn post ideas for a campaign.\n\n"
            f"Theme: {theme}\n"
            f"Audience: {context.get('audience', 'professionals')}\n"
            f"Tone: {context.get('tone', 'thought-leader')}\n"
            f"Storyline: {context.get('storyline', 'educational series')}\n"
            f"{ref_text}\n\n"
            "Return a JSON array of objects with:\n"
            '- "title": post title (5-10 words)\n'
            '- "key_points": array of 2-3 main points to cover\n'
            '- "source_refs": array of relevant reference names from the list above'
        )

        raw = call_llm(prompt, task_type="coding", max_tokens=2048)
        if raw:
            from llm_helper import extract_json

            parsed = extract_json(raw)
            if isinstance(parsed, list):
                # Enrich source_refs with _id from our graph data
                for seed in parsed:
                    enriched = []
                    for ref_name in seed.get("source_refs", []):
                        if isinstance(ref_name, str):
                            # Find matching graph ref
                            match = next(
                                (
                                    r
                                    for r in source_refs
                                    if r.get("name", "").lower() == ref_name.lower()
                                ),
                                None,
                            )
                            if match:
                                enriched.append(match)
                            else:
                                enriched.append({"type": "unknown", "name": ref_name})
                        elif isinstance(ref_name, dict):
                            enriched.append(ref_name)
                    seed["source_refs"] = enriched
                return parsed[:count]

        # Fallback: generate simple stubs
        return [
            {
                "title": f"{theme} — Part {i + 1}",
                "key_points": ["Key insight", "Real example"],
                "source_refs": [],
            }
            for i in range(count)
        ]
