"""
Resume compiler for guided interview output.

Converts the structured context_json from a resume interview session into
formatted resume text. Auto-selects a non-tech template based on career_field.
Optionally enhances bullet points with action verbs via LLM.
"""

import logging
import re

logger = logging.getLogger(__name__)

# Keywords to career field → template type mapping
_FIELD_TEMPLATES = {
    "education": [
        "teach",
        "teacher",
        "school",
        "tutor",
        "instruct",
        "curriculum",
        "principal",
        "counselor",
        "coach",
        "education",
        "classroom",
    ],
    "healthcare": [
        "nurse",
        "nursing",
        "medical",
        "clinical",
        "hospital",
        "patient",
        "cna",
        "lpn",
        "rn",
        "caregiver",
        "health",
        "pharmacy",
        "therapist",
        "dental",
        "doctor",
        "physician",
    ],
    "trades": [
        "plumb",
        "electric",
        "weld",
        "construct",
        "carpent",
        "hvac",
        "mechanic",
        "technician",
        "contractor",
        "install",
        "repair",
        "maintenance",
    ],
    "retail": [
        "retail",
        "cashier",
        "sales",
        "customer service",
        "store",
        "merchandise",
        "inventory",
        "manager",
        "assistant manager",
        "associate",
    ],
}


def _detect_template(career_field: str) -> str:
    """Map career field keywords to template type."""
    low = career_field.lower()
    for template, keywords in _FIELD_TEMPLATES.items():
        if any(kw in low for kw in keywords):
            return template
    return "general_non_tech"


def compile_resume(context: dict, template_type: str = None) -> str:
    """
    Compile context dict into a formatted resume text.

    Args:
        context: The interview context_json dict
        template_type: Override auto-detection. One of:
            education, healthcare, trades, retail, general_non_tech

    Returns:
        Formatted resume text as a string.
    """
    if not template_type:
        career_field = context.get("career_field", "")
        template_type = _detect_template(career_field)

    name = context.get("preferred_name") or context.get("name") or "Your Name"
    email = context.get("email", "")
    phone = context.get("phone", "")
    location = context.get("location", "")
    career_field = context.get("career_field", "")
    years_exp = context.get("years_experience", "")
    objective = context.get("objective", "")
    experiences = context.get("experiences", [])
    education = context.get("education", [])
    hard_skills = context.get("hard_skills", [])
    soft_skills = context.get("soft_skills", [])
    certifications = context.get("certifications", [])
    volunteer = context.get("volunteer", "")
    awards = context.get("awards", "")
    languages = context.get("languages", "")
    publications = context.get("publications", "")

    # Try to enhance bullets with LLM
    experiences = _enhance_bullets(experiences, career_field)

    sections = []

    # ─── Header ──────────────────────────────────────────────────────────────
    header_lines = [name]
    contact_parts = [p for p in [email, phone, location] if p]
    if contact_parts:
        header_lines.append(" | ".join(contact_parts))
    sections.append("\n".join(header_lines))

    # ─── Professional Summary ──────────────────────────────────────────────
    summary = _build_summary(name, career_field, years_exp, objective, template_type)
    if summary:
        sections.append("PROFESSIONAL SUMMARY\n" + "-" * 40 + "\n" + summary)

    # ─── Template-specific ordering ───────────────────────────────────────
    if template_type == "education":
        # Teachers: certifications first, then experience, then education
        if certifications:
            sections.append(
                _format_skills_section([], [], certifications, "CERTIFICATIONS & LICENSES")
            )
        if experiences:
            sections.append(_format_experience_section(experiences))
        if education:
            sections.append(_format_education_section(education))
        skills = hard_skills + soft_skills
        if skills:
            sections.append(_format_skills_section(hard_skills, soft_skills, [], "SKILLS"))

    elif template_type == "healthcare":
        # Healthcare: licenses first, then clinical experience, then education
        if certifications:
            sections.append(
                _format_skills_section([], [], certifications, "LICENSES & CERTIFICATIONS")
            )
        if experiences:
            sections.append(_format_experience_section(experiences, "CLINICAL & WORK EXPERIENCE"))
        if education:
            sections.append(_format_education_section(education))
        skills = hard_skills + soft_skills
        if skills:
            sections.append(_format_skills_section(hard_skills, soft_skills, [], "SKILLS"))

    elif template_type == "trades":
        # Trades: certs + skills first, then work history, then education
        all_certs = certifications[:]
        if hard_skills:
            sections.append(
                _format_skills_section(
                    hard_skills, soft_skills, all_certs, "SKILLS & CERTIFICATIONS"
                )
            )
        elif all_certs:
            sections.append(_format_skills_section([], [], all_certs, "CERTIFICATIONS & LICENSES"))
        if experiences:
            sections.append(_format_experience_section(experiences, "WORK HISTORY"))
        if education:
            sections.append(_format_education_section(education))

    else:
        # General / retail: experience first, then education, then skills
        if experiences:
            sections.append(_format_experience_section(experiences))
        if education:
            sections.append(_format_education_section(education))
        all_skills = hard_skills + soft_skills + certifications
        if all_skills:
            sections.append(_format_skills_section(hard_skills, soft_skills, certifications))

    # ─── Optional sections ────────────────────────────────────────────────
    optional_parts = []
    if volunteer:
        optional_parts.append(f"Volunteer: {volunteer}")
    if awards:
        optional_parts.append(f"Awards: {awards}")
    if languages:
        optional_parts.append(f"Languages: {languages}")
    if publications:
        optional_parts.append(f"Publications: {publications}")
    if optional_parts:
        sections.append("ADDITIONAL INFORMATION\n" + "-" * 40 + "\n" + "\n".join(optional_parts))

    return "\n\n".join(sections)


# ─── Section formatters ────────────────────────────────────────────────────────


def _build_summary(name, career_field, years_exp, objective, template_type):
    """Build a professional summary paragraph."""
    parts = []
    if career_field and years_exp:
        parts.append(f"Dedicated {career_field} professional with {years_exp} years of experience.")
    elif career_field:
        parts.append(f"Dedicated {career_field} professional.")
    if objective:
        parts.append(objective)
    return " ".join(parts)


def _format_experience_section(experiences, header="PROFESSIONAL EXPERIENCE"):
    """Format all work experiences into a resume section."""
    lines = [header, "-" * 40]
    for exp in experiences:
        title = exp.get("title", "")
        employer = exp.get("employer", "")
        start = exp.get("start_date", "")
        end = exp.get("end_date", "Present")
        duties = exp.get("duties", [])

        if not title and not employer:
            continue

        date_range = f"{start} – {end}" if start else ""

        if employer and date_range:
            lines.append(f"{title} | {employer}  ({date_range})")
        elif employer:
            lines.append(f"{title} | {employer}")
        else:
            lines.append(title)

        for duty in duties:
            duty = duty.strip()
            if duty:
                lines.append(f"  • {duty}")
        lines.append("")

    return "\n".join(lines).rstrip()


def _format_education_section(education):
    """Format education entries."""
    lines = ["EDUCATION", "-" * 40]
    for edu in education:
        degree = edu.get("degree", "")
        school = edu.get("school", "")
        year = edu.get("year", "")
        honors = edu.get("honors", "")

        if not degree and not school:
            continue

        entry = degree
        if school:
            entry += f" | {school}"
        if year:
            entry += f"  ({year})"
        lines.append(entry)
        if honors:
            lines.append(f"  {honors}")
        lines.append("")

    return "\n".join(lines).rstrip()


def _format_skills_section(hard_skills, soft_skills, certifications, header="SKILLS"):
    """Format skills into a readable section."""
    lines = [header, "-" * 40]

    if certifications:
        lines.append("Certifications & Licenses: " + ", ".join(certifications))
    if hard_skills:
        lines.append("Technical Skills: " + ", ".join(hard_skills))
    if soft_skills:
        lines.append("Core Competencies: " + ", ".join(soft_skills))

    return "\n".join(lines)


# ─── LLM bullet enhancement ────────────────────────────────────────────────────


def _enhance_bullets(experiences, career_field):
    """Try to rewrite raw duties as action-verb bullets using LLM. Falls back silently."""
    if not experiences:
        return experiences

    try:
        from smart_llm import call_smart

        enhanced = []
        for exp in experiences:
            duties = exp.get("duties", [])
            if not duties:
                enhanced.append(exp)
                continue

            prompt = (
                f"Rewrite these resume bullet points for a {career_field or 'professional'}. "
                f"Use strong action verbs. Keep each bullet concise (one sentence). "
                f"Return ONLY the rewritten bullets, one per line, no numbering:\n\n"
                + "\n".join(f"- {d}" for d in duties)
            )
            result = call_smart(
                prompt,
                task_type="resume_rewrite",
                task_hint="rewrite resume bullets with action verbs",
                max_tokens=400,
                temperature=0.5,
            )
            if result:
                new_duties = []
                for line in result.strip().split("\n"):
                    line = re.sub(r"^[-•*\d.)\s]+", "", line).strip()
                    if len(line) > 5:
                        new_duties.append(line)
                if new_duties:
                    exp = dict(exp)
                    exp["duties"] = new_duties
            enhanced.append(exp)
        return enhanced

    except Exception as e:
        logger.debug("Bullet enhancement skipped: %s", e)
        return experiences
