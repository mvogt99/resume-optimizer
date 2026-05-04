"""LLM prompt builders for ATS improvement chat — extracted from ats_improvement_chat.py."""

import re

from llm_helper import call_llm_quality


# ---------------------------------------------------------------------------
# Diagnostic builder (Fix E: incorporates remembered corrections count)
# ---------------------------------------------------------------------------

def build_diagnostic(score_data: dict, remembered_count: int = 0) -> str:
    bd = score_data.get("score_breakdown", {})
    score = score_data.get("score", 0)
    added = score_data.get("added_keywords", [])
    sections = score_data.get("sections_found", {})
    missing_secs = [s for s in ["summary", "experience", "education", "skills"]
                    if not sections.get(s)]
    # Actual scoring weights from resume_scorer.py
    signals = [
        ("keywords", bd.get("keyword_coverage", 0), 0.20),
        ("semantic", bd.get("semantic_similarity", 0), 0.20),
        ("skills", bd.get("skills_match", 0), 0.50),
        ("sections", bd.get("section_completeness", 0), 0.10),
    ]
    signals.sort(key=lambda x: x[1])

    # Determine if semantic is the *only* remaining gap (all others ≥90)
    gaps_below_90 = [(name, val) for name, val, _ in signals if val < 90]
    only_semantic_remains = (
        len(gaps_below_90) == 1 and gaps_below_90[0][0] == "semantic"
    )

    def _semantic_label(v, i):
        if only_semantic_remains:
            # Precise math: SCORE_FLOOR=15, calibrated = (raw-15)/85*100
            # raw = sum of other components (all ~100) + semantic*0.20
            other_raw = (
                bd.get("keyword_coverage", 100) * 0.20
                + bd.get("skills_match", 100) * 0.50
                + bd.get("section_completeness", 100) * 0.10
            )
            raw_current = other_raw + v * 0.20
            raw_max = other_raw + 100 * 0.20
            score_floor = 15
            cal_current = max(0, (raw_current - score_floor) / (100 - score_floor) * 100)
            cal_max = max(0, (raw_max - score_floor) / (100 - score_floor) * 100)
            gap_to_100 = round(cal_max - cal_current, 1)
            return (
                f"Semantic Relevance** ({v:.1f}%) — **This is your only remaining gap to 100%.**\n"
                f"   The scoring math: semantic contributes 20% weight. Getting semantic from "
                f"{v:.0f}→100 adds **+{gap_to_100} pts** to your overall score ({score}%→{round(cal_max)}%).\n"
                f"   At {v:.0f}%, you're near the practical ceiling for resume-to-JD cosine similarity. "
                f"Large gains (>5 pts) require adding new content that directly mirrors JD language — "
                f"not just rephrasing existing bullets. Modest improvements (1-3 pts) are possible by "
                f"tightening your summary and experience bullets to echo the exact phrasing in the job description."
            )
        if v >= 70:
            return (
                f"Semantic Relevance** ({v:.1f}%) — Near practical ceiling for resume-to-JD "
                f"similarity. Major gains require adding new content, not rephrasing. "
                f"Est. impact: **+{i} pts**"
            )
        return (
            f"Semantic Relevance** ({v:.1f}%) — Rephrase experience bullets to mirror JD "
            f"language. Est. impact: **+{i} pts**"
        )

    labels = {
        "keywords": lambda v, i: (
            f"Keyword Coverage** ({v:.1f}%) — Integrate missing keywords: "
            f"{', '.join(added[:7])}. Est. impact: **+{i} pts**"
        ),
        "semantic": _semantic_label,
        "skills": lambda v, i: (
            f"Skills Match** ({v:.1f}%) — Add endorsed skills matching requirements. "
            f"Est. impact: **+{i} pts**"
        ),
        "sections": lambda v, i: (
            f"Section Completeness** ({v:.1f}%) — Add: "
            f"{', '.join(missing_secs) or 'formatting'}. Est. impact: **+{i} pts**"
        ),
    }

    lines = [f"Your ATS score is **{score}%**. Here's where you can improve:\n"]
    if remembered_count:
        lines.append(
            f"ℹ️  **{remembered_count} remembered correction(s)** will be applied automatically "
            f"to any generated resume. Type **show corrections** to review or remove them.\n"
        )
    n = 1
    for name, val, weight in signals:
        if val >= 90:
            continue
        impact = int((100 - val) * weight * 0.7)
        if name == "keywords" and not added:
            continue
        lines.append(f"**{n}. {labels[name](val, impact)}")
        n += 1
    lines.append(f"\n**{n}. Comprehensive** — Address all areas above in one pass.")
    lines.append("\nWhich area would you like to focus on? Type the number or describe what to improve.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Improvement suggestions (Fix D: end with explicit confirmation ask)
# ---------------------------------------------------------------------------

def generate_improvement_suggestions(score_data: dict, focus: str, messages: list) -> str:
    bd = score_data.get("score_breakdown", {})
    added = score_data.get("added_keywords", [])
    sem_val = bd.get("semantic_similarity", 0)
    # Fix C: warn if semantic is near ceiling
    ceiling_note = ""
    if focus == "semantic" and sem_val >= 70:
        ceiling_note = (
            "\n\n⚠️ **Note:** Semantic relevance is already near its practical ceiling "
            f"({sem_val:.1f}%). Large improvements (>5 pts) require adding new content sections, "
            "not just rephrasing existing bullets. If you proceed, I'll focus on the highest-impact "
            "phrases — but be realistic that gains will be modest."
        )
    prompt = (
        f"You are an ATS resume optimization expert. Improve the user's {focus} score.\n\n"
        f"Scores: keywords={bd.get('keyword_coverage',0)}%, semantic={sem_val}%, "
        f"skills={bd.get('skills_match',0)}%, sections={bd.get('section_completeness',0)}%\n"
        f"Missing keywords: {', '.join(added[:15])}\n\n"
        f"Job description:\n{score_data.get('job_desc_text','')[:1500]}\n\n"
        f"Current resume:\n{score_data.get('optimized_text', score_data.get('original_text',''))[:3000]}\n\n"
        "Provide 3-5 actionable suggestions with numbered before/after examples from the actual resume. "
        "For each suggestion, use the exact text from the resume in 'Before'. "
        "End your response with: 'Tell me which suggestions to apply (or modify), "
        "and I will confirm the final changes before generating.'"
    )
    response = call_llm(prompt)
    if not response:
        response = _template_suggestions(focus, score_data)
    return response + ceiling_note


# ---------------------------------------------------------------------------
# Confirm-before-generate (Fix D)
# ---------------------------------------------------------------------------

def build_confirmation(suggestions_summary: str) -> str:
    return (
        "Here's what I'll apply to your resume:\n\n"
        f"{suggestions_summary}\n\n"
        "Does this look right? Say **yes** / **go ahead** to generate, or describe any final changes."
    )


# ---------------------------------------------------------------------------
# Resume generation
# ---------------------------------------------------------------------------

def generate_improved_resume(
    score_data: dict,
    session: dict,
    messages: list,
    persisted_corrections: list | None = None,
) -> str:
    """Generate an improved resume via LLM.

    persisted_corrections (Fix A): DB-backed corrections injected into the
    MANDATORY block so the LLM applies them directly, not just via post-hoc
    fuzzy matching.
    """
    original = session.get("original_resume_text") or score_data.get("original_text", "")
    current = session.get("optimized_resume_text") or original
    job_text = session.get("job_desc_text") or score_data.get("job_desc_text", "")
    added = score_data.get("added_keywords", [])
    focus = session.get("improvement_focus", "comprehensive")

    user_corrections = extract_user_corrections(messages)
    conv = "\n".join(
        f"{'User' if m['role']=='user' else 'AI'}: "
        f"{m['content'] if m['role']=='user' else m['content'][:400]}"
        for m in messages[-8:]
    )

    # Combine inline conversation corrections + persisted DB corrections
    all_corrections = list(user_corrections)
    if persisted_corrections:
        for c in persisted_corrections:
            pair = (c["old_text"], c["new_text"])
            if pair not in all_corrections:
                all_corrections.append(pair)

    corrections_block = ""
    if all_corrections:
        corrections_block = (
            "\n\nMANDATORY USER CORRECTIONS (apply EXACTLY as written):\n"
            + "\n".join(f'- Replace "{old}" with "{new}"' for old, new in all_corrections)
            + "\nThese corrections are non-negotiable — apply them verbatim.\n"
        )
    prompt = (
        "You are an expert ATS resume optimizer. Rewrite the resume to maximize ATS compatibility.\n\n"
        f"FOCUS AREA: {focus}\nMISSING KEYWORDS: {', '.join(added[:20])}\n\n"
        f"JOB DESCRIPTION:\n{job_text[:3000]}\n\n"
        f"CURRENT RESUME:\n{current}\n\n"
        f"CONVERSATION CONTEXT:\n{conv}\n"
        f"{corrections_block}\n"
        "INSTRUCTIONS:\n"
        "- CRITICAL: Apply ALL mandatory corrections listed above EXACTLY\n"
        "- Preserve all real facts, dates, companies, titles\n"
        "- Naturally integrate missing keywords into existing bullets\n"
        "- Include ALL sections (Summary, Experience, Education, Skills, Certifications)\n"
        "- Output ONLY the improved resume text, no commentary"
    )
    response = call_llm(prompt, max_tokens=4096)
    if not response:
        return current + "\n\nAdditional Skills: " + ", ".join(added[:15])
    from utils import _restore_missing_sections
    response = _restore_missing_sections(response, current)
    # Enforce all corrections post-hoc as a safety net
    if all_corrections:
        response = enforce_corrections(response, all_corrections)
    return response


def chat_with_context(score_data: dict, session: dict, messages: list, user_message: str) -> str:
    bd = score_data.get("score_breakdown", {})
    added = score_data.get("added_keywords", [])[:10]
    focus = session.get("improvement_focus", "")
    conv = "\n".join(
        f"{'User' if m['role']=='user' else 'AI'}: "
        f"{m['content'] if m['role']=='user' else m['content'][:400]}"
        for m in messages[-8:]
    )
    prompt = (
        "You are an ATS resume optimization assistant.\n\n"
        f"Focus: {focus}\nScores: keywords={bd.get('keyword_coverage',0)}%, "
        f"semantic={bd.get('semantic_similarity',0)}%, skills={bd.get('skills_match',0)}%, "
        f"sections={bd.get('section_completeness',0)}%\n"
        f"Missing keywords: {', '.join(added)}\n\nConversation:\n{conv}\n\nUser: {user_message}\n\n"
        "Respond helpfully. If the user modified suggestions, echo back the final state and ask "
        "them to confirm before generating."
    )
    response = call_llm(prompt, max_tokens=1024)
    return response or (
        "When you're ready to apply improvements, say **go ahead** and I'll generate the resume."
    )


# ---------------------------------------------------------------------------
# Correction helpers
# ---------------------------------------------------------------------------

def extract_user_corrections(messages: list) -> list[tuple[str, str]]:
    corrections = []
    for m in messages:
        if m["role"] != "user":
            continue
        text = m["content"]
        for match in re.finditer(
            r'replace\s+["\u201c]([^"\u201d]+)["\u201d]\s+with\s+["\u201c]([^"\u201d]+)["\u201d]',
            text, re.IGNORECASE,
        ):
            corrections.append((match.group(1).strip(), match.group(2).strip()))
        for match in re.finditer(
            r'replace\s+(.+?)\s+with\s+(.+?)(?:[;.]|\s*$)', text, re.IGNORECASE,
        ):
            old = match.group(1).strip().strip('"\'')
            new = match.group(2).strip().strip('"\'')
            if len(old) > 10 and (old, new) not in corrections:
                corrections.append((old, new))
    return corrections


def enforce_corrections(text: str, corrections: list[tuple[str, str]]) -> str:
    result = text
    for old_text, new_text in corrections:
        if old_text in result:
            result = result.replace(old_text, new_text, 1)
    return result


# ---------------------------------------------------------------------------
# Fallback templates + shared LLM call
# ---------------------------------------------------------------------------

def _template_suggestions(focus: str, score_data: dict) -> str:
    cta = "\nTell me which to apply, and I'll confirm the changes before generating."
    added = score_data.get("added_keywords", [])
    t = {
        "keywords": f"Improve keywords:\n1. Add: {', '.join(added[:5])}\n2. Use exact JD phrasing\n3. Add Technical Skills section{cta}",
        "semantic": f"Improve semantic relevance:\n1. Mirror JD tone\n2. Rewrite Summary\n3. Match industry acronyms{cta}",
        "skills": f"Improve skills:\n1. List matching JD skills\n2. Add LinkedIn endorsed skills{cta}",
        "sections": f"Improve sections:\n1. Add Professional Summary\n2. Distinct section headers{cta}",
    }
    return t.get(focus, t["keywords"])


def call_llm(prompt: str, max_tokens: int = 2048) -> str | None:
    return call_llm_quality(prompt, task_type="reasoning", max_tokens=max_tokens)
