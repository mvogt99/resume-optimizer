"""Pure scoring logic extracted from utils.py:optimize_resume()

This module provides score_resume() — a deterministic, side-effect-free function that
scores a resume against a job description using four NLP signals:
  - Skills match (50%) — endorsement-weighted skill overlap
  - Keyword coverage (20%) — lemmatized phrase overlap
  - Semantic similarity (20%) — sentence-transformer cosine similarity
  - Section completeness (10%) — presence of Summary/Experience/Education/Skills sections

Scoring has NO side effects: no text modification, no LLM calls, no content enhancement.
Content enhancement (accomplishment injection, LLM rewrite) remains in utils.py:optimize_resume().
"""

import re
from keyword_grouper import build_equiv_map, match_keyword_to_equivalencies
from nlp_engine import analyze_resume_vs_job, calculate_similarity, extract_skill_phrases
from nlp_similarity import score_semantic_alignment
from skills_optimizer import weighted_skill_match


def _strip_phrases_from_text(text: str, phrases: set) -> str:
    """Remove ignored phrases from text so they don't influence NLP signals."""
    if not phrases:
        return text
    result = text
    for phrase in phrases:
        # Case-insensitive removal of the phrase
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        result = pattern.sub("", result)
    return result


def score_resume(
    resume_data, job_keywords, job_text="", linkedin_profile=None,
    precomputed_semantic=None, equivalencies=None, ignored_keywords=None,
):
    """Score a resume against a job description using multi-signal NLP.

    Args:
        resume_data: dict with keys {text, skills, experience, education}
        job_keywords: list[str] — job keywords/phrases to match
        job_text: str (optional) — full job description text for semantic similarity
        linkedin_profile: dict (optional) — LinkedIn data with skills/endorsements
        precomputed_semantic: float (optional) — pre-computed semantic similarity
        equivalencies: list (optional) — user's persisted equivalency mappings
        ignored_keywords: set (optional) — keywords to exclude from ALL scoring signals

    Returns:
        dict with keys:
          - score: int (0-100) final calibrated score
          - score_breakdown: dict with keyword_coverage, semantic_similarity,
                            skills_match, section_completeness (each 0-100)
          - sections_found: dict with bool values for skills, experience, education, summary
          - matching_keywords: list[str] sorted
          - missing_keywords: list[str] sorted
          - skill_phrases_matched: list[str] from curated vocab
    """
    resume_text = resume_data.get("text", "")
    resume_skills = [s.lower() for s in resume_data.get("skills", [])]
    ignored = ignored_keywords or set()

    # If no full job text, reconstruct from keywords
    if not job_text:
        job_text = " ".join(job_keywords)

    # Strip ignored phrases from JD text so they don't influence NLP signals
    effective_job_text = _strip_phrases_from_text(job_text, ignored) if ignored else job_text

    # --- Signal 1: Keyword coverage (20%) ---
    analysis = analyze_resume_vs_job(resume_text, effective_job_text)
    keyword_score = analysis["match_score"]  # 0-100

    # Also check skill phrases for multi-word matches
    resume_phrases = set(extract_skill_phrases(resume_text))
    job_phrases = set(extract_skill_phrases(effective_job_text))
    # Filter ignored from job phrases
    if ignored:
        job_phrases = {p for p in job_phrases if p.lower() not in ignored}
    phrase_overlap = resume_phrases & job_phrases
    if job_phrases:
        phrase_score = (len(phrase_overlap) / len(job_phrases)) * 100
        # Blend phrase score into keyword score (50/50)
        keyword_score = (keyword_score + phrase_score) / 2

    # --- Prepare keyword lists early (needed for equivalency-aware keyword_score) ---
    matching_keywords = list(analysis.get("matching_keywords", []))
    missing_keywords = list(analysis.get("missing_keywords", []))
    # Filter ignored from both lists
    if ignored:
        matching_keywords = [k for k in matching_keywords if k.lower() not in ignored]
        missing_keywords = [k for k in missing_keywords if k.lower() not in ignored]
    skill_phrases_matched = sorted(list(phrase_overlap))

    # --- Reclassify using equivalencies BEFORE scoring ---
    if equivalencies:
        equiv_map = build_equiv_map(equivalencies)

        # Reclassify NLP-extracted missing keywords via token overlap
        still_missing_nlp = []
        for kw in missing_keywords:
            match = match_keyword_to_equivalencies(kw, equiv_map)
            if not match:
                still_missing_nlp.append(kw)
                continue
            status = match.get("status") or "equivalent"
            if status == "not_applicable":
                continue
            if status == "confirmed_missing":
                still_missing_nlp.append(kw)
                continue
            if kw not in matching_keywords:
                matching_keywords.append(kw)

        missing_keywords = still_missing_nlp

        # Compute equivalency-based keyword coverage directly.
        eq_total = 0
        eq_covered = 0
        for eq in equivalencies:
            status = eq.get("status") or "equivalent"
            if status == "not_applicable":
                continue
            eq_total += 1
            if status != "confirmed_missing":
                eq_covered += 1

        if eq_total > 0:
            equiv_coverage = (eq_covered / eq_total) * 100
            # When all equivalencies are resolved (100% coverage), remaining
            # "missing" keywords are NLP noise — equiv IS the keyword score.
            if equiv_coverage >= 100:
                keyword_score = 100.0
            elif equiv_coverage >= 90:
                keyword_score = equiv_coverage * 0.90 + keyword_score * 0.10
            else:
                keyword_score = equiv_coverage * 0.70 + keyword_score * 0.30

        matching_keywords = sorted(set(matching_keywords))
        missing_keywords = sorted(set(missing_keywords))

    # --- Signal 2: Semantic similarity (20%) ---
    if precomputed_semantic is not None:
        semantic_score = precomputed_semantic
    else:
        # Use effective_job_text (with ignored phrases stripped) for similarity
        semantic_score = score_semantic_alignment(resume_text, effective_job_text)

    # --- Signal 3: Skills match with endorsements (50%) ---
    resume_skill_phrases = [p.lower() for p in extract_skill_phrases(resume_text)]
    all_resume_skills = list(set(resume_skills) | set(resume_skill_phrases))

    # Expand with LinkedIn profile skills — the user's full professional skill set
    if linkedin_profile:
        linkedin_skills = (
            linkedin_profile.get("skills")
            or linkedin_profile.get("skills_and_endorsements")
            or []
        )
        for s in linkedin_skills:
            name = (s.get("name") or s.get("skill") or "").lower().strip()
            if name and len(name) > 2:
                all_resume_skills.append(name)

    # Job side: curated skill phrases, filtered by ignore list
    job_skill_phrases = [p.lower() for p in job_phrases] if job_phrases else []
    if ignored:
        job_skill_phrases = [p for p in job_skill_phrases if p.lower() not in ignored]
    if len(job_skill_phrases) >= 5:
        effective_job_keywords = job_skill_phrases
    else:
        effective_job_keywords = list(
            set(job_skill_phrases) | {kw.lower() for kw in job_keywords if kw.lower() not in ignored}
        )

    # Expand virtual resume skills with saved equivalencies
    if equivalencies:
        for eq in equivalencies:
            status = eq.get("status") or "equivalent"
            if status in ("not_applicable", "confirmed_missing"):
                continue
            job_kw = (eq.get("job_keyword") or "").lower().strip()
            if job_kw:
                all_resume_skills.append(job_kw)

    skills_result = weighted_skill_match(
        all_resume_skills, effective_job_keywords, linkedin_profile
    )
    skills_score = skills_result["weighted_score"]  # 0-100

    # --- Signal 4: Section completeness (10%) ---
    section_checks = {
        "skills": bool(
            re.search(
                r"\b(?:skills|competencies|abilities|technologies)\b", resume_text, re.IGNORECASE
            )
        ),
        "experience": bool(
            re.search(r"\b(?:experience|work history|employment)\b", resume_text, re.IGNORECASE)
        ),
        "education": bool(
            re.search(r"\b(?:education|academic|degree|university)\b", resume_text, re.IGNORECASE)
        ),
        "summary": bool(
            re.search(r"\b(?:summary|profile|objective|about)\b", resume_text, re.IGNORECASE)
        ),
    }
    sections_present = sum(section_checks.values())
    section_score = (sections_present / 4) * 100  # 0-100

    # --- Weighted raw score ---
    raw_score = (
        keyword_score * 0.20 + semantic_score * 0.20 + skills_score * 0.50 + section_score * 0.10
    )

    # --- Calibrate: stretch the usable range ---
    SCORE_FLOOR = 15
    calibrated = (raw_score - SCORE_FLOOR) / (100 - SCORE_FLOOR) * 100
    final_score = int(max(0, min(100, calibrated)))

    return {
        "score": final_score,
        "score_breakdown": {
            "keyword_coverage": keyword_score,
            "semantic_similarity": semantic_score,
            "skills_match": skills_score,
            "section_completeness": section_score,
        },
        "sections_found": section_checks,
        "matching_keywords": matching_keywords,
        "missing_keywords": missing_keywords,
        "skill_phrases_matched": skill_phrases_matched,
        "missing_skills": skills_result.get("missing_skills", []),
    }
