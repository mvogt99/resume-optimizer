"""
Stage handlers, LLM follow-up methods, cross-source context loading,
gap re-prioritization, and bullet extraction for BuilderInterviewer.
"""

import json
import re

import httpx

HARNESS_TIMEOUT = 60

try:
    from llm_helper import call_llm_direct, extract_json
except ImportError:
    call_llm_direct = None
    extract_json = None


# ---------------------------------------------------------------------------
# Cross-source context loading
# ---------------------------------------------------------------------------


def build_cross_source_context(builder_session_id):
    """Load project insights, journey data, and experiences for question context."""
    from models import get_db

    context = {"projects": [], "journey_events": [], "experiences": [], "outcomes": []}

    with get_db() as conn:
        try:
            projects = conn.execute(
                "SELECT client_name, technical_analysis_json, role_analysis_json, "
                "skills_json, business_outcomes_json FROM client_projects WHERE approved = 1"
            ).fetchall()
            for p in projects:
                tech = []
                try:
                    tech_list = json.loads(p["technical_analysis_json"] or "[]")
                    tech = [t.get("name", "") for t in tech_list[:10]]
                except (json.JSONDecodeError, TypeError):
                    pass
                roles = []
                try:
                    role_list = json.loads(p["role_analysis_json"] or "[]")
                    roles = [r.get("title", "") for r in role_list[:5]]
                except (json.JSONDecodeError, TypeError):
                    pass
                skills = []
                try:
                    skill_list = json.loads(p["skills_json"] or "[]")
                    skills = [s.get("name", "") for s in skill_list[:10]]
                except (json.JSONDecodeError, TypeError):
                    pass
                context["projects"].append(
                    {
                        "client": p["client_name"],
                        "technologies": tech,
                        "roles": roles,
                        "skills": skills,
                    }
                )

                try:
                    outcomes_list = json.loads(p["business_outcomes_json"] or "[]")
                    if isinstance(outcomes_list, list):
                        sorted_outcomes = sorted(
                            outcomes_list,
                            key=lambda o: (o.get("confidence", 0) if isinstance(o, dict) else 0),
                            reverse=True,
                        )
                        for o in sorted_outcomes[:5]:
                            if isinstance(o, dict) and o.get("outcome_title"):
                                context["outcomes"].append(
                                    {
                                        "title": o["outcome_title"],
                                        "type": o.get("outcome_type", ""),
                                        "metric": o.get("metric_value", ""),
                                        "client": p["client_name"],
                                    }
                                )
                except (json.JSONDecodeError, TypeError):
                    pass
        except Exception:
            pass

        try:
            events = conn.execute(
                "SELECT title, category, technologies FROM journey_events "
                "ORDER BY event_date DESC LIMIT 20"
            ).fetchall()
            for e in events:
                techs = []
                try:  # noqa: SIM105
                    techs = json.loads(e["technologies"] or "[]")
                except (json.JSONDecodeError, TypeError):
                    pass
                context["journey_events"].append(
                    {"title": e["title"], "category": e["category"], "technologies": techs[:5]}
                )
        except Exception:
            pass

        try:
            exps = conn.execute(
                "SELECT content FROM extracted_experiences ORDER BY created_at DESC LIMIT 10"
            ).fetchall()
            for exp in exps:
                context["experiences"].append(exp["content"][:200])
        except Exception:
            pass

    return context


# ---------------------------------------------------------------------------
# Gap re-prioritization
# ---------------------------------------------------------------------------


def reprioritize_gaps(remaining_gaps, extracted, user_message, job_text):
    """After each response, LLM re-ranks remaining gaps by importance."""
    gap_list = json.dumps(
        [
            {"skill": g.get("skill", ""), "category": g.get("category", "")}
            for g in remaining_gaps[:15]
        ]
    )
    extracted_skills = list({s for b in extracted for s in b.get("related_skills", [])})

    prompt = (
        "Re-prioritize these resume gap topics for the next interview question.\n\n"
        f"Job description excerpt (first 500 chars): {job_text[:500]}\n"
        f"User just discussed: {user_message[:300]}\n"
        f"Skills already covered: {', '.join(extracted_skills)}\n"
        f"Remaining gaps: {gap_list}\n\n"
        "Re-order the gaps by:\n"
        "1. Job emphasis (most emphasized in job description first)\n"
        "2. Natural follow-on from user's last response\n"
        "3. ATS impact (keywords that ATS systems look for)\n\n"
        "Return a JSON array of the same gap objects, re-ordered. "
        "Keep all gaps, just change the order."
    )

    if call_llm_direct:
        try:
            raw = call_llm_direct(prompt + "\nReturn ONLY the JSON array.", max_tokens=1024)
            if raw:
                parsed = extract_json(raw)
                if isinstance(parsed, list) and len(parsed) > 0:
                    return parsed
        except Exception as e:
            print(f"[interview] LLM reprioritize failed: {e}")
    return None


# ---------------------------------------------------------------------------
# LLM follow-up methods
# ---------------------------------------------------------------------------


def call_llm_followup_v2(session_id, remaining_gaps, extracted, user_message, cross_source):
    """LLM follow-up that references specific project details."""
    if not cross_source or not cross_source.get("projects"):
        return None

    gap_list = ", ".join(g.get("skill", "") for g in remaining_gaps[:5])
    next_gap = remaining_gaps[0] if remaining_gaps else {}
    next_skill = next_gap.get("skill", "")

    relevant_projects = []
    for proj in cross_source.get("projects", []):
        all_items = proj.get("technologies", []) + proj.get("skills", []) + proj.get("roles", [])
        if any(next_skill.lower() in item.lower() for item in all_items if item):
            relevant_projects.append(proj)

    project_context = ""
    if relevant_projects:
        for p in relevant_projects[:2]:
            project_context += (
                f"\nAt {p['client']}: technologies used include "
                f"{', '.join(p['technologies'][:5])}. "
            )
            if p.get("roles"):
                project_context += f"Key contributions: {', '.join(p['roles'][:3])}. "

    journey_context = ""
    for event in cross_source.get("journey_events", [])[:5]:
        if next_skill.lower() in event.get("title", "").lower():
            journey_context += f"\nPrevious work: {event['title']}. "

    outcome_context = ""
    for outcome in cross_source.get("outcomes", []):
        outcome_context += (
            f"\nKnown outcome at {outcome.get('client', '')}: {outcome.get('title', '')}"
        )
        if outcome.get("metric"):
            outcome_context += f" ({outcome['metric']})"
        outcome_context += ". "

    prompt = (
        "You are an expert career coach conducting a resume gap interview. "
        "You have access to the user's project history and should reference "
        "specific details to help them recall and articulate their experience.\n\n"
        f"Next gap to address: {next_skill} ({next_gap.get('category', 'general')})\n"
        f"Other remaining gaps: {gap_list}\n"
        f"User just said: {user_message[:500]}\n"
    )
    if project_context:
        prompt += f"\nKnown project context: {project_context}\n"
    if journey_context:
        prompt += f"\nCareer journey context: {journey_context}\n"
    if outcome_context:
        prompt += f"\nKnown business outcomes: {outcome_context}\n"

    prompt += (
        "\nAsk a specific follow-up question that:\n"
        "1. References specific project details you know about\n"
        "2. Probes for STAR specifics: Situation, Task, Action, Result\n"
        "3. Asks for metrics (team size, cost savings, time reduction, etc.)\n"
        "4. Is conversational — 2-3 sentences max\n"
        "Do NOT start with 'Great' or 'That's great'."
    )

    if call_llm_direct:
        try:
            output = call_llm_direct(prompt, max_tokens=512)
            if output and len(output) > 10:
                output = re.sub(r"<think>.*?</think>", "", output, flags=re.DOTALL).strip()
                return output
        except Exception as e:
            print(f"[interview] LLM followup v2 failed: {e}")
    return None


def call_llm_followup(session_id, remaining_gaps, extracted, user_message):
    """Original LLM follow-up method (no cross-source context)."""
    gap_list = ", ".join(g.get("skill", "") for g in remaining_gaps[:5])
    extracted_count = len(extracted)

    prompt = (
        "You are an expert career coach conducting a resume gap interview. "
        "The user is building a resume for a specific job. "
        f"Remaining skill/experience gaps: {gap_list}\n"
        f"Bullets extracted so far: {extracted_count}\n"
        f"User just said: {user_message}\n\n"
        "Ask a specific follow-up question targeting the next most important gap. "
        "If the user mentioned relevant experience, acknowledge it and dig deeper "
        "(ask for metrics, specific technologies, team size, impact). "
        "Keep it conversational — 2-3 sentences max."
    )

    if call_llm_direct:
        try:
            output = call_llm_direct(prompt, max_tokens=512)
            if output and len(output) > 10:
                output = re.sub(r"<think>.*?</think>", "", output, flags=re.DOTALL).strip()
                return output
        except Exception as e:
            print(f"[interview] LLM followup failed: {e}")
    return None


# ---------------------------------------------------------------------------
# LLM-powered bullet extraction
# ---------------------------------------------------------------------------


def extract_bullets_llm(user_message, current_gaps, job_text, harness_url):
    """LLM-powered extraction that produces polished STAR bullets."""
    if len(user_message.strip()) < 30:
        return []

    gap_skills = [g.get("skill", "") for g in current_gaps[:10]]

    prompt = (
        "Extract polished resume bullet points from this interview response.\n\n"
        f"User's response: {user_message}\n"
        f"Gap skills being addressed: {', '.join(gap_skills)}\n"
        f"Job description excerpt: {job_text[:300]}\n\n"
        "For each distinct accomplishment or experience mentioned, create a bullet with:\n"
        "- Start with a strong action verb (Led, Designed, Implemented, Reduced, etc.)\n"
        "- Include STAR format: Situation/Task → Action → Result\n"
        "- Preserve any real metrics the user mentioned — do NOT invent metrics\n"
        "- Keep each bullet to 1-2 sentences\n\n"
        "Return a JSON array of objects with:\n"
        '- "text": the polished bullet point\n'
        '- "related_skills": list of skills this bullet demonstrates\n'
        '- "has_metrics": boolean — does the bullet contain quantified results?\n'
        '- "star_complete": boolean — does it have all STAR components?\n'
        "\nReturn ONLY the JSON array, no explanation."
    )

    if call_llm_direct:
        try:
            raw = call_llm_direct(prompt, max_tokens=2048)
            if raw:
                parsed = extract_json(raw)
                if isinstance(parsed, list) and len(parsed) > 0:
                    for bullet in parsed:
                        bullet["source"] = "builder_interview_llm"
                        if "text" not in bullet:
                            continue
                        bullet.setdefault("related_skills", ["general"])
                        bullet.setdefault("has_metrics", False)
                        bullet.setdefault("star_complete", False)
                    return [b for b in parsed if b.get("text")]
        except Exception as e:
            print(f"[interview] LLM direct bullet extraction failed: {e}")

    try:
        resp = httpx.post(
            harness_url,
            json={"task": prompt, "task_type": "reasoning", "max_tokens": 2048},
            timeout=HARNESS_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            raw = data.get("output", "") or data.get("result", "") or ""
            if raw:
                from llm_helper import extract_json as _extract_json

                parsed = _extract_json(raw)
                if isinstance(parsed, list) and len(parsed) > 0:
                    for bullet in parsed:
                        bullet["source"] = "builder_interview_llm"
                        if "text" not in bullet:
                            continue
                        bullet.setdefault("related_skills", ["general"])
                        bullet.setdefault("has_metrics", False)
                        bullet.setdefault("star_complete", False)
                    return [b for b in parsed if b.get("text")]
    except Exception:
        pass

    return []


# ---------------------------------------------------------------------------
# Template fallback
# ---------------------------------------------------------------------------


def generate_gap_question(gaps, context, outcome_hint=None):
    """Template-based fallback questions for each gap category."""
    if not gaps:
        return "Is there anything else you'd like to add to your resume?"

    gap = gaps[0]
    skill = gap.get("skill", "this area")
    category = gap.get("category", "general")

    templates = {
        "technical": (
            f"Do you have experience with **{skill}**? "
            f"If so, describe a specific project or task where you used it, "
            f"including any measurable outcomes."
        ),
        "leadership": (
            f"The role requires **{skill}**. "
            f"Can you describe a time you demonstrated this? "
            f"What was the team size and what was the result?"
        ),
        "methodology": (
            f"This position involves **{skill}**. "
            f"Have you used this approach in a previous role? "
            f"What was the context and outcome?"
        ),
        "domain": (
            f"The job requires knowledge of **{skill}**. "
            f"What's your experience in this area? "
            f"Any specific projects or certifications?"
        ),
        "general": (
            f"Tell me about your experience with **{skill}**. "
            f"Try to include specific examples with measurable results."
        ),
    }

    question = templates.get(category, templates["general"])

    if outcome_hint:
        title = outcome_hint.get("title", "")
        metric = outcome_hint.get("metric", "")
        outcome_desc = title
        if metric:
            outcome_desc += f" ({metric})"
        question += (
            f" I noticed your project achieved **{outcome_desc}** — "
            f"how did your work contribute to that result?"
        )

    return question


# ---------------------------------------------------------------------------
# Regex-based bullet extraction (fallback)
# ---------------------------------------------------------------------------


def extract_bullets_from_response(user_message, current_gaps):
    """Regex-based fallback: parse user text into structured bullets."""
    bullets = []
    msg = user_message.strip()

    if len(msg) < 20:
        return bullets

    items = re.split(r"[.\n]|[-*•]\s+", msg)
    gap_skills = [g.get("skill", "").lower() for g in current_gaps]

    for item in items:
        item = item.strip()
        if len(item) < 15:
            continue
        if item[0].islower():
            item = item[0].upper() + item[1:]

        related = []
        item_lower = item.lower()
        for skill in gap_skills:
            if skill and skill in item_lower:
                related.append(skill)

        bullets.append(
            {
                "text": item,
                "related_skills": related if related else ["general"],
                "source": "builder_interview",
                "has_metrics": False,
                "star_complete": False,
            }
        )

    return bullets
