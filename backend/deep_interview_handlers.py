"""
Question/response handlers, gap identification, prompt building,
and synthesis for the DeepInterviewer adaptive interview engine.
"""

import json

# ---------------------------------------------------------------------------
# Gap identification and opening message
# ---------------------------------------------------------------------------


def identify_gaps(profile, mode, job_text):
    """Identify areas that need deeper exploration."""
    if not profile:
        return [
            "career_history",
            "technical_skills",
            "business_impact",
            "leadership",
            "career_goals",
        ]

    gaps = []

    tech = profile.get("technology_mastery", [])
    if len(tech) < 5 or not any(t.get("evidence") for t in tech):
        gaps.append("technical_depth")

    impacts = profile.get("business_impacts", [])
    if len(impacts) < 3 or not any(i.get("metrics") for i in impacts):
        gaps.append("quantified_impact")

    leadership = profile.get("leadership_profile", {})
    if not leadership.get("team_scope") or not leadership.get("decision_examples"):
        gaps.append("leadership_evidence")

    arc = profile.get("career_arc", {})
    if not arc.get("trajectory") or len(arc.get("phases", [])) < 2:
        gaps.append("career_narrative")

    diffs = profile.get("differentiators", [])
    if len(diffs) < 2:
        gaps.append("unique_value_proposition")

    knowledge_gaps = profile.get("knowledge_gaps", [])
    if not knowledge_gaps:
        gaps.append("honest_self_assessment")

    if mode == "role_specific" and job_text:
        gaps.append("role_fit_evidence")

    return gaps if gaps else ["refinement"]


def generate_opening(profile, exploration_areas, mode, job_text):
    """Generate the opening message for the interview."""
    summary = profile.get("professional_summary", "") if profile else ""
    area_names = ", ".join(exploration_areas[:3])

    if mode == "comprehensive":
        opening = (
            f"I've analyzed your professional data across all available sources. "
            f"{'Here is what I know: ' + summary[:200] + ' ' if summary else ''}"
            f"To build the strongest possible profile, I'd like to explore these areas "
            f"in more depth: {area_names}. "
            f"Let's start — can you tell me about a project or accomplishment you're "
            f"most proud of, and what made it significant?"
        )
    elif mode == "role_specific":
        job_snippet = (job_text or "")[:150]
        opening = (
            f"I've reviewed your profile and the target role. "
            f"For this position ({job_snippet}...), I want to understand how your "
            f"experience maps to the key requirements. "
            f"The areas I'd like to explore: {area_names}. "
            f"Let's start with your most relevant experience for this role."
        )
    else:  # update
        opening = (
            "Welcome back! I have your existing profile. "
            "What new experiences, projects, or accomplishments would you like to add? "
            "Or is there an area you'd like to strengthen?"
        )

    return opening


def get_opening_suggestions(exploration_areas):
    """Generate clickable suggestion chips for the opening."""
    suggestion_map = {
        "technical_depth": "I'd like to talk about my technical expertise",
        "quantified_impact": "I have some metrics and business outcomes to share",
        "leadership_evidence": "Let me tell you about my leadership experience",
        "career_narrative": "I want to explain my career trajectory",
        "unique_value_proposition": "I know what makes me unique in my field",
        "honest_self_assessment": "I'd like to discuss areas I'm developing",
        "role_fit_evidence": "Let me explain why I'm a great fit for this role",
        "refinement": "I'd like to refine and strengthen my profile",
        "career_history": "Let me walk you through my career history",
        "technical_skills": "I want to discuss my technical skills in depth",
        "business_impact": "I have business impact examples to share",
        "leadership": "I'd like to talk about my leadership style",
        "career_goals": "I want to discuss where my career is heading",
    }
    suggestions = []
    for area in exploration_areas[:4]:
        if area in suggestion_map:
            suggestions.append(suggestion_map[area])
    return suggestions


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------


def build_interview_prompt(profile, messages, depth_assessment, mode, job_text):
    """Build the full LLM prompt for generating the next interview question."""
    profile_str = json.dumps(profile, default=str)
    if len(profile_str) > 6000:
        profile_str = profile_str[:6000] + "\n...[truncated]"

    conversation = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages[-12:])
    depth_str = json.dumps(depth_assessment)

    role_context = ""
    if mode == "role_specific" and job_text:
        role_context = f"\nTARGET JOB:\n{job_text[:2000]}\n"

    return (
        "You are conducting a deep professional interview. Your goal is to build the most thorough "
        "understanding of this person's career, technical depth, business impact, "  # noqa: E501
        "and leadership.\n\n"
        "You have access to their aggregated professional data (provided below). Your job is to:\n"
        "1. Identify what you DON'T yet know that would strengthen their profile\n"
        "2. Ask the MOST VALUABLE question right now — the one that fills the biggest gap\n"
        "3. Probe for SPECIFICS: numbers, scope, outcomes, decisions, challenges overcome\n"
        "4. When you get a surface-level answer, dig deeper: 'What was the measurable result?'\n"
        "5. Cross-reference their answers with existing data\n"
        "6. Adjust your approach based on their communication style\n\n"
        "After each answer, assess whether the information is:\n"
        "- SUFFICIENT: move to the next most valuable area\n"
        "- NEEDS_DEPTH: ask a targeted follow-up\n"
        "- CONTRADICTS_EVIDENCE: gently probe the discrepancy\n\n"
        f"PROFESSIONAL PROFILE:\n{profile_str}\n\n"
        f"DEPTH ASSESSMENT:\n{depth_str}\n"
        f"{role_context}\n"
        f"CONVERSATION:\n{conversation}\n\n"
        "Return a JSON object:\n"
        "{\n"
        '  "message": "your question or response",\n'
        '  "area": "technical|business_impact|leadership|career_narrative|role_targeting|differentiators",\n'  # noqa: E501
        '  "depth_assessment": {"technical": "covered|partial|gap", ...},\n'
        '  "suggestions": ["Suggested response 1", "Suggested response 2"],\n'
        '  "profile_updates": [{"field": "leadership_profile.team_scope", "value": "8 engineers"}],\n'  # noqa: E501
        '  "exploration_complete": false\n'
        "}\n\nReturn ONLY valid JSON."
    )


def fallback_question(depth_assessment):
    """Generate a template question when LLM is unavailable."""
    for area, status in depth_assessment.items():
        if status == "gap":
            questions = {
                "technical": "Can you tell me about the technologies you work with most and your level of expertise?",  # noqa: E501
                "business_impact": (
                    "What's a project where you delivered measurable business results?"
                ),
                "leadership": (
                    "Have you led teams or mentored others? Tell me about that experience."
                ),
                "career_narrative": "Walk me through your career journey — what led you to where you are now?",  # noqa: E501
                "role_targeting": "What about this target role excites you, and what experience prepares you for it?",  # noqa: E501
                "differentiators": "What do you think sets you apart from other professionals in your field?",  # noqa: E501
            }
            return questions.get(area, "Tell me more about your professional background.")
    return "Is there anything else you'd like to add to strengthen your profile?"


# ---------------------------------------------------------------------------
# Profile update helpers
# ---------------------------------------------------------------------------


def apply_update(profile, field, value):
    """Apply a single update to the working profile."""
    parts = field.split(".")
    target = profile
    for part in parts[:-1]:
        if isinstance(target, dict):
            if part not in target:
                target[part] = {}
            target = target[part]
        else:
            return
    if isinstance(target, dict):
        key = parts[-1]
        existing = target.get(key)
        if isinstance(existing, list) and not isinstance(value, list):
            target[key].append(value)
        else:
            target[key] = value


# ---------------------------------------------------------------------------
# Final synthesis and summary
# ---------------------------------------------------------------------------


def run_final_synthesis(working_profile, messages, job_text):
    """Run a final LLM synthesis incorporating all interview insights."""
    from llm_helper import call_llm_quality, extract_json

    profile_str = json.dumps(working_profile, default=str)
    if len(profile_str) > 6000:
        profile_str = profile_str[:6000] + "\n...[truncated]"

    conversation = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages[-20:])

    prompt = (
        "You have just completed a deep professional interview. "
        "Based on the conversation and the existing profile data, "
        "generate an UPDATED comprehensive professional profile.\n\n"
        f"EXISTING PROFILE:\n{profile_str}\n\n"
        f"INTERVIEW CONVERSATION:\n{conversation}\n\n"
        "Merge all new information from the interview into the profile. "
        "Return the complete updated profile as JSON with the same structure:\n"
        "{\n"
        '  "professional_summary": "...",\n'
        '  "career_arc": {"phases": [...], "trajectory": "...", "years_total": N},\n'
        '  "technology_mastery": [...],\n'
        '  "business_impacts": [...],\n'
        '  "leadership_profile": {...},\n'
        '  "differentiators": [...],\n'
        '  "knowledge_gaps": [...],\n'
        '  "cross_source_insights": [...]\n'
        "}\n\nReturn ONLY valid JSON."
    )

    raw = call_llm_quality(prompt, task_type="reasoning", max_tokens=4096)
    return extract_json(raw) if raw else None


def summarize_improvements(before, after):
    """Summarize what the interview added to the profile."""
    improvements = []

    before_techs = len(before.get("technology_mastery", []))
    after_techs = len(after.get("technology_mastery", []))
    if after_techs > before_techs:
        improvements.append(f"Added {after_techs - before_techs} technology entries")

    before_impacts = len(before.get("business_impacts", []))
    after_impacts = len(after.get("business_impacts", []))
    if after_impacts > before_impacts:
        improvements.append(f"Added {after_impacts - before_impacts} business impact entries")

    before_diffs = len(before.get("differentiators", []))
    after_diffs = len(after.get("differentiators", []))
    if after_diffs > before_diffs:
        improvements.append(f"Added {after_diffs - before_diffs} differentiators")

    after_leader = after.get("leadership_profile", {})
    before_leader = before.get("leadership_profile", {})
    if after_leader.get("team_scope") and not before_leader.get("team_scope"):
        improvements.append("Added leadership scope details")

    if not improvements:
        improvements.append("Profile refined with interview insights")

    return "; ".join(improvements)


def write_to_graph(profile):
    """Write deep profile to ArangoDB knowledge graph."""
    try:
        from arango_client import get_graph_client

        arango = get_graph_client()
        if not arango.is_connected:
            return
        arango.write_deep_profile_to_graph(profile)
    except Exception as e:
        print(f"[deep_interview] ArangoDB write failed: {e}")
