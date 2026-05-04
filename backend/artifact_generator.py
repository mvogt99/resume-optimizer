"""Artifact generator — produces 7 output artifacts per JD optimization run.

Artifacts:
  tailored_resume   — full resume rewritten to address gaps and score requirements
  cover_letter      — targeted cover letter using evidence anchors and role fit
  gap_report        — structured gap analysis with rewrite recommendations
  keyword_map       — ATS keyword mapping (required vs present vs missing)
  interview_seeds   — STAR talking point seeds per key requirement
  linkedin_summary  — updated LinkedIn About section targeting this role
  one_pager         — executive one-pager (skills, highlights, fit summary)

All generators: never raise, return {content: '', error: str} on failure.
LLM calls use task_type='generation' via llm_helper.call_llm_quality.
"""

import logging

logger = logging.getLogger(__name__)

# Module-level LLM import — allows test patching via patch("artifact_generator.call_llm_quality")
try:
    from llm_helper import call_llm_quality
except ImportError:  # pragma: no cover
    call_llm_quality = None  # type: ignore[assignment]

ARTIFACT_TYPES = [
    "tailored_resume", "cover_letter", "gap_report",
    "keyword_map", "interview_seeds", "linkedin_summary", "one_pager",
]


def _word_count(text: str) -> int:
    return len(text.split()) if text else 0


def _make_artifact(content: str, artifact_type: str, error: str = "") -> dict:
    return {
        "artifact_type": artifact_type,
        "content": content,
        "word_count": _word_count(content),
        "error": error,
    }


def _profile_summary(candidate_profile: dict) -> str:
    """Extract a compact profile summary for prompt injection."""
    name = candidate_profile.get("candidate_id", "Candidate")
    families = ", ".join(candidate_profile.get("target_role_families", []))
    branding = candidate_profile.get("branding_summary", "")[:300]
    skills = [
        item.get("canonical_skill", "")
        for item in candidate_profile.get("skill_inventory", [])[:15]
        if item.get("canonical_skill")
    ]
    companies = [
        u.get("company", "") + " (" + u.get("title", "") + ")"
        for u in candidate_profile.get("experience_units", [])[:4]
        if u.get("company")
    ]
    return (
        f"Role families: {families}\n"
        f"Branding: {branding}\n"
        f"Key skills: {', '.join(skills)}\n"
        f"Experience: {'; '.join(companies)}"
    )


def _top_requirements(requirements: list, scores: list, n: int = 8) -> str:
    """Return top-N requirements by importance as a compact string."""
    score_map = {s["requirement_id"]: s.get("composite_score", 0.0) for s in scores}
    sorted_reqs = sorted(
        requirements,
        key=lambda r: r.get("importance", 0.5),
        reverse=True,
    )[:n]
    lines = []
    for r in sorted_reqs:
        score = score_map.get(r.get("requirement_id", ""), 0.0)
        lines.append(f"- [{r.get('requirement_type','').upper()}] {r.get('text','')[:120]} (match={score:.2f})")
    return "\n".join(lines)


def _high_gaps(gaps: list, n: int = 6) -> str:
    """Return top-N high/medium gaps as a compact string."""
    prioritized = [g for g in gaps if g.get("severity") == "high"]
    prioritized += [g for g in gaps if g.get("severity") == "medium"]
    lines = []
    for g in prioritized[:n]:
        lines.append(f"- [{g.get('severity','').upper()}] {g.get('description','')[:120]}")
    return "\n".join(lines) or "No critical gaps identified."


def generate_tailored_resume(
    candidate_profile: dict,
    requirements: list,
    scores: list,
    gaps: list,
    rewrite_targets: list,
    resume_text: str,
) -> dict:
    """Generate a full resume rewritten to address gaps and score key requirements."""
    artifact_type = "tailored_resume"
    if not call_llm_quality:
        return _make_artifact("", artifact_type, "LLM unavailable")
    try:
        gap_actions = "\n".join(
            f"- {t.get('suggested_action', '')}" for t in rewrite_targets[:5]
        )
        prompt = (
            f"You are an expert resume writer. Rewrite the resume below to better match "
            f"the job requirements. Address the gaps listed. Keep factual accuracy — do not "
            f"fabricate experience.\n\n"
            f"CANDIDATE PROFILE:\n{_profile_summary(candidate_profile)}\n\n"
            f"TOP REQUIREMENTS:\n{_top_requirements(requirements, scores)}\n\n"
            f"GAPS TO ADDRESS:\n{gap_actions}\n\n"
            f"ORIGINAL RESUME:\n{resume_text[:2500]}\n\n"
            f"Write the complete tailored resume. Use strong action verbs. "
            f"Quantify achievements where evidence supports it."
        )
        content = call_llm_quality(prompt, task_type="generation", max_tokens=2048) or ""
        return _make_artifact(str(content), artifact_type)
    except Exception as e:
        logger.error("artifact_generator: tailored_resume failed: %s", e)
        return _make_artifact("", artifact_type, str(e))


def generate_cover_letter(
    candidate_profile: dict,
    requirements: list,
    scores: list,
    gaps: list,
    rewrite_targets: list,
    resume_text: str,
) -> dict:
    """Generate a targeted cover letter using evidence anchors and role fit."""
    artifact_type = "cover_letter"
    if not call_llm_quality:
        return _make_artifact("", artifact_type, "LLM unavailable")
    try:
        top_skills = [
            item.get("canonical_skill", "")
            for item in candidate_profile.get("skill_inventory", [])[:8]
            if item.get("canonical_skill")
        ]
        prompt = (
            f"Write a compelling cover letter for this candidate applying to the role described "
            f"by the requirements below. 3-4 paragraphs, professional tone.\n\n"
            f"CANDIDATE PROFILE:\n{_profile_summary(candidate_profile)}\n\n"
            f"TOP JOB REQUIREMENTS:\n{_top_requirements(requirements, scores, n=5)}\n\n"
            f"STRONGEST SKILLS TO HIGHLIGHT: {', '.join(top_skills)}\n\n"
            f"Write the cover letter. Open with a strong hook. Connect experience to requirements. "
            f"Close with a clear call to action."
        )
        content = call_llm_quality(prompt, task_type="generation", max_tokens=600) or ""
        return _make_artifact(str(content), artifact_type)
    except Exception as e:
        logger.error("artifact_generator: cover_letter failed: %s", e)
        return _make_artifact("", artifact_type, str(e))


def generate_gap_report(
    candidate_profile: dict,
    requirements: list,
    scores: list,
    gaps: list,
    rewrite_targets: list,
    resume_text: str,
) -> dict:
    """Generate a structured gap analysis report with actionable recommendations."""
    artifact_type = "gap_report"
    if not gaps:
        return _make_artifact("No gaps identified.", artifact_type)
    try:
        lines = ["# Gap Analysis Report\n"]
        by_severity: dict = {"high": [], "medium": [], "low": []}
        for g in gaps:
            by_severity.get(g.get("severity", "low"), []).append(g)

        for sev in ("high", "medium", "low"):
            group = by_severity[sev]
            if not group:
                continue
            lines.append(f"## {sev.upper()} Priority ({len(group)} gaps)\n")
            for g in group:
                lines.append(f"**{g.get('gap_type','').replace('_',' ').title()}**")
                lines.append(f"- Issue: {g.get('description','')}")
                lines.append(f"- Action: {g.get('recommended_action','')}\n")

        if rewrite_targets:
            lines.append("## Rewrite Targets\n")
            for t in rewrite_targets[:5]:
                lines.append(f"- Priority {t.get('priority','')}: {t.get('suggested_action','')}")
                lines.append(f"  Template: _{t.get('rewrite_template','')}_\n")

        content = "\n".join(lines)
        return _make_artifact(content, artifact_type)
    except Exception as e:
        logger.error("artifact_generator: gap_report failed: %s", e)
        return _make_artifact("", artifact_type, str(e))


def generate_keyword_map(
    candidate_profile: dict,
    requirements: list,
    scores: list,
    gaps: list,
    rewrite_targets: list,
    resume_text: str,
) -> dict:
    """Generate ATS keyword map: required vs present vs missing."""
    artifact_type = "keyword_map"
    try:
        resume_lower = resume_text.lower()
        score_map = {s["requirement_id"]: s for s in scores}
        lines = ["# ATS Keyword Map\n", "| Keyword | Status | Match Score |", "|---------|--------|-------------|"]

        for req in requirements:
            req_id = req.get("requirement_id", "")
            score_info = score_map.get(req_id, {})
            composite = score_info.get("composite_score", 0.0)
            skills = req.get("canonical_skills", [])
            if not skills:
                continue
            for skill in skills[:3]:
                present = skill.lower() in resume_lower
                status = "✓ Present" if present else "✗ Missing"
                lines.append(f"| {skill} | {status} | {composite:.2f} |")

        content = "\n".join(lines)
        return _make_artifact(content, artifact_type)
    except Exception as e:
        logger.error("artifact_generator: keyword_map failed: %s", e)
        return _make_artifact("", artifact_type, str(e))


def generate_interview_seeds(
    candidate_profile: dict,
    requirements: list,
    scores: list,
    gaps: list,
    rewrite_targets: list,
    resume_text: str,
) -> dict:
    """Generate STAR talking point seeds for top requirements."""
    artifact_type = "interview_seeds"
    if not call_llm_quality:
        return _make_artifact("", artifact_type, "LLM unavailable")
    try:
        prompt = (
            f"Generate 5-6 STAR-format interview talking point seeds for this candidate.\n\n"
            f"CANDIDATE PROFILE:\n{_profile_summary(candidate_profile)}\n\n"
            f"KEY REQUIREMENTS TO PREPARE FOR:\n{_top_requirements(requirements, scores, n=6)}\n\n"
            f"RESUME CONTEXT:\n{resume_text[:1000]}\n\n"
            f"For each talking point: one sentence on Situation/Task, one on Action, one on Result. "
            f"Use [METRIC] placeholders where quantification would strengthen the story."
        )
        content = call_llm_quality(prompt, task_type="generation", max_tokens=800) or ""
        return _make_artifact(str(content), artifact_type)
    except Exception as e:
        logger.error("artifact_generator: interview_seeds failed: %s", e)
        return _make_artifact("", artifact_type, str(e))


def generate_linkedin_summary(
    candidate_profile: dict,
    requirements: list,
    scores: list,
    gaps: list,
    rewrite_targets: list,
    resume_text: str,
) -> dict:
    """Generate an updated LinkedIn About section optimized for this role."""
    artifact_type = "linkedin_summary"
    if not call_llm_quality:
        return _make_artifact("", artifact_type, "LLM unavailable")
    try:
        existing = candidate_profile.get("branding_summary", "")[:400]
        prompt = (
            f"Rewrite this candidate's LinkedIn About section to be optimized for the role "
            f"described below. 150-200 words. First-person voice. Hook in first sentence.\n\n"
            f"CANDIDATE PROFILE:\n{_profile_summary(candidate_profile)}\n\n"
            f"TARGET ROLE REQUIREMENTS:\n{_top_requirements(requirements, scores, n=5)}\n\n"
            f"EXISTING SUMMARY:\n{existing}\n\n"
            f"Write the updated LinkedIn About section."
        )
        content = call_llm_quality(prompt, task_type="generation", max_tokens=400) or ""
        return _make_artifact(str(content), artifact_type)
    except Exception as e:
        logger.error("artifact_generator: linkedin_summary failed: %s", e)
        return _make_artifact("", artifact_type, str(e))


def generate_one_pager(
    candidate_profile: dict,
    requirements: list,
    scores: list,
    gaps: list,
    rewrite_targets: list,
    resume_text: str,
) -> dict:
    """Generate an executive one-pager: skills, highlights, role fit summary."""
    artifact_type = "one_pager"
    if not call_llm_quality:
        return _make_artifact("", artifact_type, "LLM unavailable")
    try:
        prompt = (
            f"Create a one-page executive summary for this candidate targeting the role below.\n\n"
            f"CANDIDATE PROFILE:\n{_profile_summary(candidate_profile)}\n\n"
            f"TOP REQUIREMENTS:\n{_top_requirements(requirements, scores, n=6)}\n\n"
            f"HIGH GAPS TO ACKNOWLEDGE:\n{_high_gaps(gaps, n=3)}\n\n"
            f"Format: 4 sections — Value Proposition (2 sentences), "
            f"Core Capabilities (6-8 bullet skills), "
            f"Career Highlights (3 bullets with impact), "
            f"Role Fit (2 sentences on alignment + one honest gap acknowledgment)."
        )
        content = call_llm_quality(prompt, task_type="generation", max_tokens=600) or ""
        return _make_artifact(str(content), artifact_type)
    except Exception as e:
        logger.error("artifact_generator: one_pager failed: %s", e)
        return _make_artifact("", artifact_type, str(e))


_GENERATORS = {
    "tailored_resume": generate_tailored_resume,
    "cover_letter": generate_cover_letter,
    "gap_report": generate_gap_report,
    "keyword_map": generate_keyword_map,
    "interview_seeds": generate_interview_seeds,
    "linkedin_summary": generate_linkedin_summary,
    "one_pager": generate_one_pager,
}


def generate_artifacts(
    candidate_profile: dict,
    requirements: list,
    scores: list,
    gaps: list,
    rewrite_targets: list,
    resume_text: str,
    artifacts: list | None = None,
) -> dict:
    """Orchestrate generation of all (or selected) artifacts.

    Args:
        candidate_profile: From normalizer.normalize_candidate().
        requirements:      From jd_parser.parse_requirements().
        scores:            From hybrid_scorer.score_all_requirements().
        gaps:              From gap_classifier.classify_gaps().
        rewrite_targets:   From rewrite_planner.plan_rewrites().
        resume_text:       Current resume text.
        artifacts:         Optional list of artifact names to generate (default: all 7).

    Returns:
        Dict mapping artifact_type → {content, word_count, artifact_type, error}.
        Never raises.
    """
    requested = artifacts if artifacts else ARTIFACT_TYPES
    results = {}
    args = (candidate_profile, requirements, scores, gaps, rewrite_targets, resume_text)

    for name in requested:
        if name not in _GENERATORS:
            logger.warning("artifact_generator: unknown artifact type '%s' — skipped", name)
            continue
        try:
            results[name] = _GENERATORS[name](*args)
        except Exception as e:
            logger.error("artifact_generator: %s crashed: %s", name, e)
            results[name] = _make_artifact("", name, str(e))

    return results


def get_artifact_summary(artifacts: dict) -> dict:
    """Return a summary of generated artifacts.

    Args:
        artifacts: Dict from generate_artifacts().

    Returns:
        {total, generated_count, failed_count, total_word_count, by_type}
    """
    total = len(artifacts)
    generated = sum(1 for a in artifacts.values() if a.get("content"))
    failed = sum(1 for a in artifacts.values() if a.get("error"))
    total_words = sum(a.get("word_count", 0) for a in artifacts.values())
    by_type = {
        name: {"word_count": a.get("word_count", 0), "has_error": bool(a.get("error"))}
        for name, a in artifacts.items()
    }
    return {
        "total": total,
        "generated_count": generated,
        "failed_count": failed,
        "total_word_count": total_words,
        "by_type": by_type,
    }
