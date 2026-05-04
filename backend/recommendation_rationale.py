"""LLM-generated recommendation rationale for multi-resume comparison.

Provides generate_rationale() — a 3-5 sentence explanation of why the top-ranked
resume is recommended, with per-resume strengths and gaps. Falls back to
template_rationale() on LLM timeout or failure.

No side effects: pure inputs -> string output.
"""

import logging
import signal

from llm_helper import call_llm_quality

logger = logging.getLogger(__name__)

# Quality threshold: rationale must be at least this many chars to be kept
_MIN_RATIONALE_LENGTH = 80


def generate_rationale(rankings, job_text, timeout=30):
    """Generate LLM explanation for the recommendation result.

    Args:
        rankings: list[dict] — sorted rankings from compare_resumes()
        job_text: str — job description text used for comparison
        timeout: int — seconds to wait for LLM (default 30)

    Returns:
        str — rationale text (LLM-generated or template fallback)
    """
    if not rankings:
        return "No resumes were compared."

    try:
        prompt = _build_rationale_prompt(rankings, job_text)

        # Use signal-based timeout for synchronous LLM call
        result = _call_with_timeout(
            lambda: call_llm_quality(prompt, task_type="reasoning", max_tokens=512),
            timeout=timeout
        )

        if result and isinstance(result, str) and len(result.strip()) >= _MIN_RATIONALE_LENGTH:
            return result.strip()

        logger.warning("[rationale] LLM returned short/empty result, using template fallback")
        return template_rationale(rankings)

    except Exception as e:
        logger.warning("[rationale] LLM failed (%s), using template fallback", str(e))
        return template_rationale(rankings)


def template_rationale(rankings):
    """Generate a deterministic template-based rationale from rankings.

    Used as fallback when LLM is unavailable or returns low-quality output.
    References the top resume's filename, score, and key matching keywords.

    Args:
        rankings: list[dict] — sorted rankings (rank 1 = best match)

    Returns:
        str — template-generated rationale
    """
    if not rankings:
        return "No resumes were compared."

    top = rankings[0]
    filename = top.get("filename", "the top resume")
    score = top.get("score", 0)
    matching = top.get("matching_keywords", [])[:5]
    missing = top.get("missing_keywords", [])[:3]
    breakdown = top.get("score_breakdown", {})

    skills_score = breakdown.get("skills_match", 0)
    keyword_score = breakdown.get("keyword_coverage", 0)

    lines = []

    # Opening: recommendation + score
    lines.append(
        f"Based on the analysis, {filename} is the best match for this role "
        f"with an ATS compatibility score of {score}/100."
    )

    # Strengths
    if matching:
        kw_list = ", ".join(matching[:4])
        lines.append(
            f"This resume demonstrates strong alignment with key requirements including "
            f"{kw_list} (keyword coverage: {keyword_score:.0f}%, "
            f"skills match: {skills_score:.0f}%)."
        )
    else:
        lines.append(
            f"The resume shows reasonable structure with keyword coverage of "
            f"{keyword_score:.0f}% and skills match of {skills_score:.0f}%."
        )

    # Gaps
    if missing:
        gap_list = ", ".join(missing)
        lines.append(
            f"Areas for improvement include: {gap_list}. "
            f"Adding these to the resume could improve the ATS score further."
        )

    # Comparison if multiple resumes
    if len(rankings) > 1:
        second = rankings[1]
        score_diff = score - second.get("score", 0)
        lines.append(
            f"This resume scores {score_diff} points higher than the next candidate "
            f"({second.get('filename', 'resume 2')}, score: {second.get('score', 0)}/100)."
        )

    return " ".join(lines)


def _build_rationale_prompt(rankings, job_text):
    """Build the LLM prompt for rationale generation."""
    top = rankings[0]
    filename = top.get("filename", "Resume 1")
    score = top.get("score", 0)
    matching = top.get("matching_keywords", [])[:8]
    missing = top.get("missing_keywords", [])[:5]

    # Build comparison summary
    comparison_lines = []
    for r in rankings[:4]:  # Max 4 in prompt to avoid token bloat
        rname = r.get("filename") or f"Resume {r.get('rank', '?')}"
        comparison_lines.append(
            f"- {rname}: "
            f"score={r.get('score', 0)}/100, rank={r.get('rank', '?')}, "
            f"keywords matched={len(r.get('matching_keywords', []))}"
        )
    comparison_block = "\n".join(comparison_lines)

    prompt = (
        "You are an expert career advisor. Write a concise 3-5 sentence recommendation "
        "explaining which resume best matches the job description and why.\n\n"
        f"JOB DESCRIPTION SUMMARY:\n{job_text[:1500]}\n\n"
        f"RESUME COMPARISON:\n{comparison_block}\n\n"
        f"TOP RECOMMENDATION: {filename} (score: {score}/100)\n"
        f"  Matching keywords: {', '.join(matching) if matching else 'none identified'}\n"
        f"  Missing keywords: {', '.join(missing) if missing else 'none'}\n\n"
        "RULES:\n"
        "- Write 3-5 sentences only\n"
        "- Mention the recommended resume filename by name\n"
        "- Reference at least one specific matching skill or keyword\n"
        "- Note at least one gap or area for improvement\n"
        "- Be specific, factual, and actionable — no generic filler\n"
        "- Output the rationale text only, no headers or bullets\n"
    )
    return prompt


def _call_with_timeout(fn, timeout=30):
    """Call fn() with a Unix signal-based timeout. Returns None on timeout."""
    def _handler(signum, frame):
        raise TimeoutError(f"LLM call timed out after {timeout}s")

    old_handler = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(timeout)
    try:
        return fn()
    except TimeoutError:
        logger.warning("[rationale] LLM timed out after %ds", timeout)
        return None
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
