"""
Stage-specific message handling, extraction, LLM calls, bullet generation,
and context enrichment for ExperienceExtractor.
"""

import json
import re

# ---------------------------------------------------------------------------
# Context enrichment helpers
# ---------------------------------------------------------------------------


def enrich_session_context(context, user_id, employer, client):
    """Enrich session context with data from journey, projects, and graph."""
    try:
        from context_enrichment import format_context_for_prompt, gather_context_for_employer

        gathered = gather_context_for_employer(user_id, employer, client)

        known_techs = gathered.get("technologies_known", [])
        if known_techs:
            existing = {t.lower() for t in context.get("technologies", [])}
            for tech in known_techs[:20]:
                if tech.lower() not in existing:
                    context.setdefault("technologies", []).append(tech)
                    existing.add(tech.lower())

        context["_enrichment"] = format_context_for_prompt(gathered, max_chars=4000)

        parts = []
        proj = gathered.get("project_analysis")
        if proj:
            parts.append(
                f"I found project documentation for "
                f"**{proj.get('client_name', client or employer)}** "
                "in the knowledge base"
            )
        n_events = len(gathered.get("journey_events", []))
        if n_events:
            parts.append(f"{n_events} related journey event(s)")
        n_achievements = len(gathered.get("achievements", []))
        if n_achievements:
            parts.append(f"{n_achievements} achievement(s)")
        if known_techs:
            parts.append(f"{len(known_techs)} technologies already documented")

        if parts:
            return (
                "I already have some context from your career data: "
                + ", ".join(parts)
                + ". I'll use this to ask more targeted questions."
            )

    except Exception:
        pass
    return ""


def enrich_from_themes(context, user_id, stage, user_message, split_items_fn):
    """Dynamically mine journey data based on themes emerging from the conversation."""
    try:
        from context_enrichment import _get_matching_journey_events

        themes = set()
        for tech in context.get("technologies", []):
            themes.add(tech)
        items = split_items_fn(user_message)
        for item in items:
            words = item.split()
            if 1 <= len(words) <= 4:
                themes.add(item.strip())

        if not themes:
            return

        mined_themes = set(context.get("_mined_themes", []))
        new_themes = themes - mined_themes
        if not new_themes:
            return

        all_new_events = []
        for theme in list(new_themes)[:5]:
            events = _get_matching_journey_events(
                user_id,
                employer=context.get("employer", ""),
                client=context.get("client", ""),
                technologies=[theme],
            )
            all_new_events.extend(events)

        if not all_new_events:
            context["_mined_themes"] = list(mined_themes | new_themes)
            return

        existing_enrichment = context.get("_enrichment", "")
        new_event_texts = []
        seen_titles = set()
        for evt in all_new_events:
            title = evt.get("title", "")
            if title and title not in seen_titles and title not in existing_enrichment:
                seen_titles.add(title)
                date = evt.get("event_date", "")
                techs = evt.get("technologies", [])
                if isinstance(techs, str):
                    try:
                        techs = json.loads(techs)
                    except (json.JSONDecodeError, TypeError):
                        techs = []
                tech_str = f" [{', '.join(techs[:5])}]" if techs else ""
                new_event_texts.append(f"  - {date}: {title}{tech_str}")

        if new_event_texts:
            addition = (
                "\n\nNEWLY DISCOVERED JOURNEY EVENTS "
                f"(matching themes: {', '.join(list(new_themes)[:5])}):\n"
                + "\n".join(new_event_texts[:10])
            )
            context["_enrichment"] = (existing_enrichment + addition)[:6000]

        context["_mined_themes"] = list(mined_themes | new_themes)

    except Exception:
        pass


# ---------------------------------------------------------------------------
# Message extraction helpers
# ---------------------------------------------------------------------------


def extract_from_message(context, stage, message, split_items_fn):
    """Extract structured info from user message based on current stage."""
    msg = message.strip()

    if stage == "intro":
        if not context.get("employer") and msg:
            context["employer"] = msg.split(",")[0].strip().split(" at ")[-1].strip()
    elif stage == "role":
        if not context.get("title"):
            context["title"] = msg
    elif stage == "responsibilities":
        context.setdefault("responsibilities", []).extend(split_items_fn(msg))
    elif stage == "technologies":
        context.setdefault("technologies", []).extend(split_items_fn(msg))
    elif stage == "outcomes":
        context.setdefault("outcomes", []).extend(split_items_fn(msg))
    elif stage == "challenges":
        context.setdefault("challenges", []).extend(split_items_fn(msg))

    return context


def extract_fields_from_text(text):
    """Extract experience fields from uploaded context text using heuristics."""
    result = {
        "title": "",
        "responsibilities": [],
        "technologies": [],
        "outcomes": [],
        "challenges": [],
    }

    lines = [line_text.strip() for line_text in text.split("\n") if line_text.strip()]
    tech_keywords = set()
    tech_pattern = re.compile(
        r"\b(Python|Java|JavaScript|TypeScript|React|Angular|Vue|Node\.?js|"
        r"AWS|Azure|GCP|Docker|Kubernetes|SQL|PostgreSQL|MongoDB|Redis|"
        r"FastAPI|Flask|Django|Spring|\.NET|C\+\+|C#|Go|Rust|Ruby|PHP|"
        r"TensorFlow|PyTorch|Kafka|RabbitMQ|GraphQL|REST|gRPC|CI/CD|"
        r"Git|Jenkins|Terraform|Ansible|Linux|Agile|Scrum|SAFe|"
        r"Microservices|API|ETL|ML|AI|NLP|DataOps|DevOps|SRE)\b",
        re.IGNORECASE,
    )

    for line in lines:
        techs = tech_pattern.findall(line)
        tech_keywords.update(techs)

        if re.search(
            r"\d+%|\$\d|reduced|increased|improved|saved|delivered|achieved",
            line,
            re.IGNORECASE,
        ):
            result["outcomes"].append(line)
        elif re.search(
            r"^(?:Led|Managed|Designed|Developed|Implemented|Architected|"
            r"Created|Built|Maintained|Coordinated|Established|Oversaw|"
            r"Directed|Supervised|Executed|Delivered|Collaborated)",
            line,
            re.IGNORECASE,
        ):
            result["responsibilities"].append(line)
        elif re.search(
            r"challenge|problem|issue|obstacle|difficult|resolved|fixed|troubleshot",
            line,
            re.IGNORECASE,
        ):
            result["challenges"].append(line)

    result["technologies"] = sorted(tech_keywords)
    return result


# ---------------------------------------------------------------------------
# LLM calls and template fallbacks
# ---------------------------------------------------------------------------


def call_llm_for_response(session_id, context, stage, user_message):
    """Call FTAL harness for LLM-generated follow-up questions."""
    from llm_helper import call_llm_quality

    prompt = build_extraction_prompt(context, stage, user_message)
    result = call_llm_quality(prompt, task_type="reasoning", max_tokens=512)
    if result and len(result) > 10:
        return result.strip()
    return None


def build_extraction_prompt(context, stage, user_message):
    """Build a prompt for the LLM to generate the next interview question."""
    stage_descriptions = {
        "intro": "gathering basic info (employer, client, role)",
        "role": "understanding their job title and team structure",
        "responsibilities": "learning about their day-to-day responsibilities",
        "technologies": "identifying technologies, tools, and methodologies used",
        "outcomes": "extracting key accomplishments and measurable outcomes",
        "challenges": "understanding difficult problems they solved",
        "complete": "wrapping up and summarizing",
    }

    enrichment_section = ""
    enrichment_data = context.get("_enrichment", "")
    if enrichment_data:
        enrichment_section = (
            "\n\nKNOWN CAREER DATA (from journey mining, project analysis, knowledge graph):\n"
            + enrichment_data[:3000]
            + "\n\nUse this data to ask informed follow-up questions.\n"
        )

    uploaded_section = ""
    uploaded_contexts = context.get("uploaded_contexts", [])
    if uploaded_contexts:
        uploads_summary = []
        for uc in uploaded_contexts[-3:]:
            source = uc.get("source", "uploaded document")
            text_preview = uc.get("text", "")[:2000]
            uploads_summary.append(f"[From {source}]:\n{text_preview}")
        uploaded_section = (
            "\n\nADDITIONAL CONTEXT FROM UPLOADED DOCUMENTS:\n"
            + "\n---\n".join(uploads_summary)
            + "\n\nUse this context to ask more targeted questions.\n"
        )

    return (
        "You are an expert career coach conducting an interview to extract work experience "
        "for a resume. Ask focused, specific follow-up questions.\n\n"
        f"Current stage: {stage} — {stage_descriptions.get(stage, '')}\n\n"
        f"Context gathered so far:\n"
        f"- Employer: {context.get('employer', 'unknown')}\n"
        f"- Client: {context.get('client', 'unknown')}\n"
        f"- Title: {context.get('title', 'unknown')}\n"
        f"- Responsibilities: {', '.join(context.get('responsibilities', []))}\n"
        f"- Technologies: {', '.join(context.get('technologies', []))}\n"
        f"- Outcomes: {', '.join(context.get('outcomes', []))}\n"
        f"- Challenges: {', '.join(context.get('challenges', []))}\n"
        f"{enrichment_section}"
        f"{uploaded_section}\n"
        f"User just said: {user_message}\n\n"
        "Respond with a natural, encouraging follow-up question. "
        "Keep it conversational (2-3 sentences max)."
    )


def generate_template_question(context, stage):
    """Fallback template questions when LLM is unavailable."""
    templates = {
        "intro": (
            "Let's start with the basics. What company were you working for, "
            "and were you assigned to a specific client or project?"
        ),
        "role": (
            "What was your official job title? " "Who did you report to, and how big was your team?"
        ),
        "responsibilities": (
            "What were your main day-to-day responsibilities? " "List as many as you can think of."
        ),
        "technologies": (
            "What technologies, tools, programming languages, or methodologies "
            "did you use in this role?"
        ),
        "outcomes": (
            "What were your key accomplishments? Try to include numbers where possible "
            "(e.g., increased revenue by X%, reduced processing time by Y hours, "
            "managed $Z budget)."
        ),
        "challenges": (
            "What was the most difficult problem you solved in this role? "
            "What was the impact of your solution?"
        ),
        "complete": (
            "I've gathered all the information I need. "
            "Let me compile your experience into resume-ready bullet points. "
            "You can review and edit them before saving."
        ),
    }
    return templates.get(stage, templates["intro"])


# ---------------------------------------------------------------------------
# Bullet generation
# ---------------------------------------------------------------------------


def generate_bullet_points(context):
    """Generate STAR-format resume bullet points from extracted context."""
    raw_bullets = []
    for outcome in context.get("outcomes", []):
        if outcome.strip():
            raw_bullets.append(outcome.strip())
    for resp in context.get("responsibilities", []):
        if resp.strip() and len(raw_bullets) < 8:
            raw_bullets.append(resp.strip())
    for challenge in context.get("challenges", []):
        if challenge.strip() and len(raw_bullets) < 10:
            raw_bullets.append(challenge.strip())

    if not raw_bullets:
        return []

    formatted = format_bullets_with_llm(raw_bullets, context)
    if formatted:
        return formatted

    bullets = []
    for b in raw_bullets:
        if b[0].islower():
            b = b[0].upper() + b[1:]
        bullets.append(b)
    return bullets


def format_bullets_with_llm(raw_bullets, context):
    """Use LLM to rewrite raw bullets into STAR-format resume bullets."""
    employer = context.get("employer", "")
    title = context.get("title", "")
    techs = ", ".join(context.get("technologies", [])[:10])

    enrichment_hint = ""
    enrichment = context.get("_enrichment", "")
    if enrichment:
        enrichment_hint = (
            f"\n\nAdditional context from career data analysis:\n{enrichment[:1500]}\n"
            "Use this context to add specificity. Do NOT fabricate metrics.\n"
        )

    prompt = (
        "Rewrite these raw experience notes into professional STAR-format resume bullet points "
        f"for a {title} role at {employer}.\n\n"
        f"Technologies used: {techs}\n"
        f"{enrichment_hint}\n"
        f"Raw notes:\n" + "\n".join(f"- {b}" for b in raw_bullets) + "\n\n"
        "Rules:\n"
        "- Each bullet starts with a strong action verb\n"
        "- Include STAR format: Situation/Task → Action → Result\n"
        "- Preserve ALL numbers and metrics exactly as given\n"
        "- Do NOT invent metrics\n"
        "- Keep each bullet to 1-2 lines (under 200 characters)\n"
        '- Return a JSON array of strings: ["bullet1", "bullet2", ...]\n'
    )

    try:
        from llm_helper import call_llm_quality, extract_json

        raw = call_llm_quality(prompt, task_type="reasoning", max_tokens=1024)
        if raw:
            parsed = extract_json(raw)
            if isinstance(parsed, list) and all(isinstance(b, str) for b in parsed):
                return parsed
    except Exception:
        pass
    return None
