"""Per-agent acceptance criteria for resume optimizer agents.

Each agent type has a list of AcceptanceCriterion checks. Criteria are
intentionally conservative: they catch total failures (empty output,
placeholder bleed-through, missing required fields) without being fragile
about LLM-specific wording or exact numeric thresholds.
"""

from __future__ import annotations

from typing import Any

from .criteria_types import AcceptanceCriterion

# Placeholder strings the LLM sometimes emits instead of real content
_PLACEHOLDERS = (
    "[Your Name]",
    "[Your Full Name]",
    "[Candidate Name]",
    "[Company]",
    "[Company Name]",
    "[Position]",
    "[Job Title]",
    "[Role]",
    "[Hiring Manager]",
    "[Hiring Manager's Name]",
)


def _has_placeholder(text: str) -> bool:
    return any(p in text for p in _PLACEHOLDERS)


def _is_nonempty_str(val: Any, min_len: int = 1) -> bool:
    return isinstance(val, str) and len(val.strip()) >= min_len


# ──────────────────────────────────────────────────────────────────────────────
# Resume Tailor
# Output keys: optimized_text, ats_score, score_breakdown, matching_keywords,
#              added_keywords, version_id, job_requirements, experience_matches
# ──────────────────────────────────────────────────────────────────────────────

RESUME_TAILOR_CRITERIA: list[AcceptanceCriterion] = [
    AcceptanceCriterion(
        name="optimized_text_present",
        check=lambda r: _is_nonempty_str(r.get("optimized_text"), min_len=100),
        failure_hint=(
            "optimized_text is missing or too short (<100 chars). "
            "The tailoring step likely failed silently."
        ),
    ),
    AcceptanceCriterion(
        name="ats_score_nonzero",
        check=lambda r: isinstance(r.get("ats_score"), (int, float))
        and r["ats_score"] >= 50,
        failure_hint=(
            "ats_score is 0 or below 50. "
            "Either the ATS scoring failed or the tailored resume is unusable."
        ),
    ),
    AcceptanceCriterion(
        name="version_id_written",
        check=lambda r: _is_nonempty_str(r.get("version_id")),
        failure_hint=(
            "version_id is missing — tailored resume was not persisted to the database."
        ),
    ),
    AcceptanceCriterion(
        name="no_placeholders",
        check=lambda r: not _has_placeholder(r.get("optimized_text", "")),
        failure_hint=(
            "Unresolved placeholder text found in optimized_text "
            "(e.g. '[Company]', '[Your Name]'). "
            "The _replace_placeholders() step did not run or had no source data."
        ),
    ),
]

# ──────────────────────────────────────────────────────────────────────────────
# Cover Letter
# Output keys: id, subject, greeting, body, closing, tone, company, role_title
# ──────────────────────────────────────────────────────────────────────────────

COVER_LETTER_CRITERIA: list[AcceptanceCriterion] = [
    AcceptanceCriterion(
        name="body_present",
        check=lambda r: _is_nonempty_str(r.get("body"), min_len=150),
        failure_hint=(
            "body is missing or under 150 chars. "
            "The cover letter generation step failed silently."
        ),
    ),
    AcceptanceCriterion(
        name="greeting_present",
        check=lambda r: _is_nonempty_str(r.get("greeting")),
        failure_hint=(
            "greeting is empty. Cover letter has no salutation."
        ),
    ),
    AcceptanceCriterion(
        name="closing_present",
        check=lambda r: _is_nonempty_str(r.get("closing"), min_len=5),
        failure_hint=(
            "closing is empty or too short (<5 chars). Cover letter has no proper sign-off."
        ),
    ),
    AcceptanceCriterion(
        name="no_placeholders_in_body",
        check=lambda r: not _has_placeholder(r.get("body", "")),
        failure_hint=(
            "Unresolved placeholder text found in cover letter body. "
            "Company name, position, or candidate name were not injected."
        ),
    ),
]

# ──────────────────────────────────────────────────────────────────────────────
# Interview Coach (session start)
# Output keys: session_id, message (opening question), + session context
# ──────────────────────────────────────────────────────────────────────────────

INTERVIEW_COACH_CRITERIA: list[AcceptanceCriterion] = [
    AcceptanceCriterion(
        name="session_id_present",
        check=lambda r: _is_nonempty_str(r.get("session_id")),
        failure_hint=(
            "session_id is missing. The coaching session was not created in the database."
        ),
    ),
    AcceptanceCriterion(
        name="opening_message_present",
        check=lambda r: _is_nonempty_str(r.get("message"), min_len=20),
        failure_hint=(
            "Opening message (first question) is missing or too short. "
            "The session initialisation failed to generate a question."
        ),
    ),
    AcceptanceCriterion(
        name="no_error_key",
        check=lambda r: "error" not in r,
        failure_hint=(
            "Result contains an 'error' key. "
            "The agent reported failure but the route handler did not catch it."
        ),
    ),
]

# ──────────────────────────────────────────────────────────────────────────────
# Career Advisor (analyze_career)
# Output: LLM-extracted JSON dict. Fields vary but must have substance.
# ──────────────────────────────────────────────────────────────────────────────

_ADVISOR_SUBSTANCE_KEYS = {
    "trajectory", "career_phases", "phases",
    "skill_gaps", "gaps", "skills_gap",
    "recommendations", "recommendation",
    "strengths", "differentiators",
    "market_trends", "trends",
    "next_roles", "role_suggestions",
}


def _advisor_has_substance(r: Any) -> bool:
    if not isinstance(r, dict):
        return False
    keys_lower = {k.lower() for k in r}
    return bool(keys_lower & _ADVISOR_SUBSTANCE_KEYS)


CAREER_ADVISOR_CRITERIA: list[AcceptanceCriterion] = [
    AcceptanceCriterion(
        name="result_is_dict",
        check=lambda r: isinstance(r, dict) and len(r) >= 2,
        failure_hint=(
            "Career advisor returned an empty or non-dict result. "
            "LLM JSON extraction likely failed."
        ),
    ),
    AcceptanceCriterion(
        name="substance_fields_present",
        check=_advisor_has_substance,
        failure_hint=(
            "Career analysis is missing substance fields "
            "(trajectory, skill_gaps, recommendations, etc.). "
            "The LLM may have returned a generic or off-topic response."
        ),
    ),
    AcceptanceCriterion(
        name="no_error_key",
        check=lambda r: isinstance(r, dict) and "error" not in r,
        failure_hint=(
            "Result contains an 'error' key — LLM was unavailable or returned garbage."
        ),
    ),
]

# ──────────────────────────────────────────────────────────────────────────────
# Cover Letter Regenerate
# Same structural requirements as initial generation.
# ──────────────────────────────────────────────────────────────────────────────

COVER_REGEN_CRITERIA: list[AcceptanceCriterion] = [
    AcceptanceCriterion(
        name="body_present",
        check=lambda r: _is_nonempty_str(r.get("body"), min_len=150),
        failure_hint=(
            "Regenerated cover letter body is missing or under 150 chars. "
            "The LLM failed to produce a revised letter."
        ),
    ),
    AcceptanceCriterion(
        name="greeting_present",
        check=lambda r: _is_nonempty_str(r.get("greeting")),
        failure_hint="Regenerated letter has no salutation.",
    ),
    AcceptanceCriterion(
        name="closing_present",
        check=lambda r: _is_nonempty_str(r.get("closing"), min_len=5),
        failure_hint="Regenerated letter has no sign-off / closing or closing is too short (<5 chars).",
    ),
    AcceptanceCriterion(
        name="no_placeholders_in_body",
        check=lambda r: not _has_placeholder(r.get("body", "")),
        failure_hint=(
            "Regenerated letter contains unresolved placeholder text. "
            "Placeholder substitution must run after LLM call."
        ),
    ),
]

# ──────────────────────────────────────────────────────────────────────────────
# Interview Coach — Answer scoring (process_answer)
# Output: score dict, is_complete bool, next_question OR assessment
# ──────────────────────────────────────────────────────────────────────────────

COACH_ANSWER_CRITERIA: list[AcceptanceCriterion] = [
    AcceptanceCriterion(
        name="score_present",
        check=lambda r: isinstance(r.get("score"), dict) and len(r["score"]) > 0,
        failure_hint=(
            "Answer score dict is missing or empty. "
            "The LLM did not return a structured STAR evaluation."
        ),
    ),
    AcceptanceCriterion(
        name="is_complete_is_bool",
        check=lambda r: isinstance(r.get("is_complete"), bool),
        failure_hint=(
            "is_complete flag is missing. "
            "Session state cannot be determined without this field."
        ),
    ),
    AcceptanceCriterion(
        name="continuation_or_assessment",
        check=lambda r: (
            _is_nonempty_str(r.get("next_question"), min_len=10)
            or isinstance(r.get("assessment"), dict)
        ),
        failure_hint=(
            "Neither next_question nor assessment is present. "
            "Incomplete sessions need a next_question; completed sessions need an assessment."
        ),
    ),
    AcceptanceCriterion(
        name="no_error_key",
        check=lambda r: "error" not in r,
        failure_hint="Result contains an 'error' key — answer processing failed.",
    ),
]

# ──────────────────────────────────────────────────────────────────────────────
# Career Advisor — Skills Roadmap (get_skills_roadmap)
# Output: target_role, current_readiness, timeline_months, phases, quick_wins, key_gap
# ──────────────────────────────────────────────────────────────────────────────

ADVISOR_ROADMAP_CRITERIA: list[AcceptanceCriterion] = [
    AcceptanceCriterion(
        name="target_role_present",
        check=lambda r: _is_nonempty_str(r.get("target_role")),
        failure_hint="target_role is missing from roadmap output.",
    ),
    AcceptanceCriterion(
        name="phases_present",
        check=lambda r: isinstance(r.get("phases"), list) and len(r["phases"]) >= 1,
        failure_hint=(
            "phases list is missing or empty. "
            "Roadmap must contain at least one development phase."
        ),
    ),
    AcceptanceCriterion(
        name="key_gap_present",
        check=lambda r: _is_nonempty_str(r.get("key_gap")),
        failure_hint="key_gap is missing — the single most important gap was not identified.",
    ),
    AcceptanceCriterion(
        name="no_error_key",
        check=lambda r: isinstance(r, dict) and "error" not in r,
        failure_hint="Roadmap result contains an 'error' key — LLM unavailable or failed.",
    ),
]

# ──────────────────────────────────────────────────────────────────────────────
# Career Advisor — Role Recommendations (get_role_recommendations)
# Output: dict with recommendations list (title, fit_score, reasoning, ...)
# ──────────────────────────────────────────────────────────────────────────────

ADVISOR_ROLES_CRITERIA: list[AcceptanceCriterion] = [
    AcceptanceCriterion(
        name="recommendations_present",
        check=lambda r: isinstance(r.get("recommendations"), list)
        and len(r["recommendations"]) >= 1,
        failure_hint=(
            "recommendations list is missing or empty. "
            "The LLM did not return role suggestions."
        ),
    ),
    AcceptanceCriterion(
        name="each_rec_has_title",
        check=lambda r: all(
            _is_nonempty_str(rec.get("title"))
            for rec in (r.get("recommendations") or [])[:3]
        ),
        failure_hint=(
            "One or more of the first 3 role recommendations are missing a title. "
            "Every recommendation must have a non-empty 'title' field."
        ),
    ),
    AcceptanceCriterion(
        name="no_error_key",
        check=lambda r: isinstance(r, dict) and "error" not in r,
        failure_hint="Role recommendations result contains an 'error' key.",
    ),
]

# ──────────────────────────────────────────────────────────────────────────────
# Registry: agent_type → criteria list
# ──────────────────────────────────────────────────────────────────────────────

CRITERIA_REGISTRY: dict[str, list[AcceptanceCriterion]] = {
    "resume_tailor": RESUME_TAILOR_CRITERIA,
    "cover_letter": COVER_LETTER_CRITERIA,
    "cover_letter_regen": COVER_REGEN_CRITERIA,
    "interview_coach": INTERVIEW_COACH_CRITERIA,
    "coach_answer": COACH_ANSWER_CRITERIA,
    "career_advisor": CAREER_ADVISOR_CRITERIA,
    "advisor_roadmap": ADVISOR_ROADMAP_CRITERIA,
    "advisor_roles": ADVISOR_ROLES_CRITERIA,
}
