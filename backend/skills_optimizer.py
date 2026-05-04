"""
Endorsement-weighted skill optimization and skills gap analysis.
Uses LinkedIn profile data (endorsement counts) to prioritize skills
and match accomplishments/recommendations against job descriptions.
"""

import re

from nlp_engine import calculate_similarity, extract_keywords, extract_skill_phrases


def get_endorsement_weighted_skills(linkedin_profile, top_n=30):
    """
    Return skills sorted by endorsement count (descending).
    Each entry: {"name": str, "endorsements": int, "weight": float}
    Weight is normalized 0-1 relative to the highest endorsement count.
    """
    skills_data = linkedin_profile.get("skills", [])
    if not skills_data:
        return []

    # Handle both parsed formats: {"skill": ..., "endorsements_count": ...}
    # and normalized: {"name": ..., "endorsements": ...}
    normalized = []
    for s in skills_data:
        name = s.get("name") or s.get("skill", "")
        endorsements = s.get("endorsements", 0) or s.get("endorsements_count", 0)
        if name:
            normalized.append({"name": name, "endorsements": endorsements})

    sorted_skills = sorted(normalized, key=lambda x: x["endorsements"], reverse=True)
    max_endorsements = sorted_skills[0]["endorsements"] if sorted_skills else 1

    result = []
    for s in sorted_skills[:top_n]:
        weight = s["endorsements"] / max_endorsements if max_endorsements > 0 else 0
        result.append(
            {
                "name": s["name"],
                "endorsements": s["endorsements"],
                "weight": round(weight, 3),
            }
        )

    return result


def weighted_skill_match(resume_skills, job_keywords, linkedin_profile=None):
    """
    Match resume skills against job keywords with endorsement weighting.
    Returns a dict with matching/missing skills and a weighted match score.
    """
    resume_lower = {s.lower() for s in resume_skills}

    # Build endorsement lookup from LinkedIn data
    endorsement_map = {}
    if linkedin_profile:
        linkedin_skills = (
            linkedin_profile.get("skills")
            or linkedin_profile.get("skills_and_endorsements")
            or []
        )
        for s in linkedin_skills:
            name = s.get("name") or s.get("skill", "")
            count = s.get("endorsements", 0) or s.get("endorsements_count", 0)
            if name:
                endorsement_map[name.lower()] = count

    matching = []
    missing = []
    weighted_match_total = 0
    weighted_possible_total = 0

    for kw in job_keywords:
        kw_lower = kw.lower()
        # Weight: endorsement count + 1 (so un-endorsed skills still count)
        weight = endorsement_map.get(kw_lower, 0) + 1
        weighted_possible_total += weight

        if kw_lower in resume_lower or any(
            kw_lower in rs or rs in kw_lower for rs in resume_lower if len(rs) > 3
        ):
            matching.append(
                {
                    "keyword": kw,
                    "endorsements": endorsement_map.get(kw_lower, 0),
                    "weight": weight,
                }
            )
            weighted_match_total += weight
        else:
            missing.append(
                {
                    "keyword": kw,
                    "endorsements": endorsement_map.get(kw_lower, 0),
                    "priority": "high" if endorsement_map.get(kw_lower, 0) > 10 else "normal",
                }
            )

    score = (
        int((weighted_match_total / weighted_possible_total) * 100)
        if weighted_possible_total > 0
        else 0
    )

    return {
        "matching_skills": matching,
        "missing_skills": missing,
        "weighted_score": score,
        "total_job_keywords": len(job_keywords),
    }


def get_relevant_accomplishments(linkedin_profile, job_text, top_n=5):
    """
    Find accomplishments from LinkedIn experience that are most relevant
    to the target job description. Uses NLP similarity scoring.
    """
    accomplishments = []

    for exp in linkedin_profile.get("experience", []):
        desc = exp.get("description", "")
        # Extract bullet points (lines starting with - or *)
        bullets = re.findall(r"[-*]\s*(.+)", desc)
        # Also check for KEY ACCOMPLISHMENTS sections
        for acc in exp.get("accomplishments", []):
            if acc.strip():
                bullets.append(acc.strip())

        for bullet in bullets:
            bullet = bullet.strip()
            if len(bullet) > 20:  # Skip very short fragments
                score = calculate_similarity(bullet, job_text)
                accomplishments.append(
                    {
                        "text": bullet,
                        "source_title": exp.get("title", ""),
                        "source_company": exp.get("company", ""),
                        "relevance_score": round(score * 100, 1),
                    }
                )

    # Sort by relevance and return top N
    accomplishments.sort(key=lambda x: x["relevance_score"], reverse=True)
    return accomplishments[:top_n]


def match_recommendations(linkedin_profile, job_text, top_n=3):
    """
    Match recommendation text against job description themes.
    Returns the most relevant recommendations to highlight.
    """
    recommendations = linkedin_profile.get("recommendations", [])
    if not recommendations:
        return []

    scored = []
    for rec in recommendations:
        text = rec.get("text", "") or rec.get("recommendation_text", "")
        if not text:
            continue

        score = calculate_similarity(text, job_text)
        scored.append(
            {
                "text": text[:300] + ("..." if len(text) > 300 else ""),
                "author": rec.get("author", "") or rec.get("recommender_name", ""),
                "relationship": rec.get("relationship", "") or rec.get("recommender_title", ""),
                "relevance_score": round(score * 100, 1),
            }
        )

    scored.sort(key=lambda x: x["relevance_score"], reverse=True)
    return scored[:top_n]


def analyze_skills_gap(
    resume_data, job_text, linkedin_profile=None, project_journey_evidence=None, deep_profile=None
):
    """
    Full skills gap analysis comparing resume + LinkedIn profile against a job description.
    Returns categorized skills: have (emphasize), have (already shown), and need to acquire.

    project_journey_evidence: optional list of dicts with keys:
        - source: str (e.g., "Client Project: OPI")
        - detail: str (e.g., "Used in project documentation")
        - skills: list[str] of skill names found in that source

    deep_profile: optional deep profile dict with technology_mastery[] and business_impacts[]
    """
    # Use curated skill-phrase extraction for meaningful, matchable terms
    # Enable LLM fallback for job descriptions (they're the target we match against)
    job_skills = extract_skill_phrases(job_text, use_llm_fallback=True)
    # Fall back to keyword extraction if skill phrases yield too few results
    if len(job_skills) < 5:
        kw = extract_keywords(job_text, 30)
        # Only keep 2-word combos from known domains, skip random trigrams and single words
        for k in kw:
            words = k.split()
            if 1 < len(words) <= 2 and k.lower() not in {s.lower() for s in job_skills}:
                job_skills.append(k)
    job_keywords = job_skills[:30]

    # Extract skill phrases from resume text for better matching
    resume_text = resume_data.get("text", "")
    resume_skills_from_phrases = extract_skill_phrases(resume_text, use_llm_fallback=True)
    # Also include the original extracted skills (for broader coverage)
    resume_skills = list(
        {s.lower() for s in resume_data.get("skills", [])}
        | {s.lower() for s in resume_skills_from_phrases}
    )

    # LinkedIn skills with endorsements
    linkedin_skills = {}
    if linkedin_profile:
        for s in linkedin_profile.get("skills", []):
            name = s.get("name") or s.get("skill", "")
            count = s.get("endorsements", 0) or s.get("endorsements_count", 0)
            if name:
                linkedin_skills[name.lower()] = count

    # Build evidence lookup from project/journey data
    evidence = {}  # skill_lower → {source, detail}
    if project_journey_evidence:
        for item in project_journey_evidence:
            for skill in item.get("skills", []):
                skill_key = skill.lower()
                if skill_key not in evidence:
                    evidence[skill_key] = {
                        "source": item.get("source", ""),
                        "detail": item.get("detail", ""),
                    }

    # Deep profile: proficiency levels and business impacts as evidence
    deep_proficiency = {}  # skill_lower → proficiency level
    deep_impacts = {}  # skill_lower → [impact titles]
    if deep_profile:
        for tech in deep_profile.get("technology_mastery", []):
            name = tech.get("name", "")
            if name:
                deep_proficiency[name.lower()] = tech.get("proficiency", "intermediate")
                # Add deep profile evidence to evidence lookup
                if name.lower() not in evidence:
                    contexts = tech.get("contexts", [])
                    ctx_str = ", ".join(contexts[:2]) if contexts else "deep profile"
                    evidence[name.lower()] = {
                        "source": "Deep Profile",
                        "detail": f"{tech.get('proficiency', 'known')} level; used in {ctx_str}",
                    }
        for impact in deep_profile.get("business_impacts", []):
            for src in impact.get("evidence_sources", []):
                impact_title = impact.get("title", "")
                src_lower = src.lower()
                if src_lower not in deep_impacts:
                    deep_impacts[src_lower] = []
                deep_impacts[src_lower].append(impact_title)

    skills_to_emphasize = []  # Have skill + matches job, but not prominent in resume
    skills_already_shown = []  # Have skill + matches job + already in resume
    skills_to_acquire = []  # Don't have skill, job requires it

    resume_text_lower = resume_text.lower()
    resume_skills_set = set(resume_skills)

    for kw in job_keywords:
        kw_lower = kw.lower()
        # Check exact match in skills list OR substring match in full resume text
        in_resume = kw_lower in resume_skills_set or kw_lower in resume_text_lower
        in_linkedin = kw_lower in linkedin_skills
        in_evidence = kw_lower in evidence
        in_deep = kw_lower in deep_proficiency

        if in_resume:
            entry = {
                "skill": kw,
                "endorsements": linkedin_skills.get(kw_lower, 0),
                "status": "shown",
            }
            if in_evidence:
                entry["evidence_source"] = evidence[kw_lower]["source"]
            if in_deep:
                entry["proficiency"] = deep_proficiency[kw_lower]
                prof = deep_proficiency[kw_lower]
                if prof in ("expert", "advanced"):
                    entry["tip"] = f"Strong: {prof}-level proficiency verified across sources"
                elif prof == "beginner":
                    entry["tip"] = (
                        "Listed but only beginner-level — consider adding recent examples"
                    )
            skills_already_shown.append(entry)
        elif in_deep and deep_proficiency[kw_lower] in ("expert", "advanced"):
            # Deep profile shows high proficiency but not in resume — emphasize
            entry = {
                "skill": kw,
                "endorsements": linkedin_skills.get(kw_lower, 0),
                "status": "emphasize",
                "proficiency": deep_proficiency[kw_lower],
                "tip": f"Deep profile shows {deep_proficiency[kw_lower]}-level — add to your resume",  # noqa: E501
            }
            if in_evidence:
                entry["evidence_source"] = evidence[kw_lower]["source"]
            skills_to_emphasize.append(entry)
        elif in_linkedin:
            entry = {
                "skill": kw,
                "endorsements": linkedin_skills.get(kw_lower, 0),
                "status": "emphasize",
                "tip": (
                    f"Add '{kw}' to your resume"
                    f" - you have {linkedin_skills[kw_lower]} endorsements"
                ),
            }
            if in_evidence:
                entry["evidence_source"] = evidence[kw_lower]["source"]
            skills_to_emphasize.append(entry)
        elif in_evidence:
            # Skill found in project/journey data but NOT in resume or LinkedIn
            # Classify as "emphasize" (amber) instead of "acquire" (red)
            ev = evidence[kw_lower]
            skills_to_emphasize.append(
                {
                    "skill": kw,
                    "endorsements": 0,
                    "status": "emphasize",
                    "tip": f"Found in {ev['source']}: {ev['detail']} \u2014 add to your resume",
                    "evidence_source": ev["source"],
                }
            )
        else:
            skills_to_acquire.append(
                {
                    "skill": kw,
                    "status": "acquire",
                    "tip": f"Consider gaining experience with '{kw}' for this role",
                }
            )

    total = len(job_keywords)
    coverage = (len(skills_already_shown) + len(skills_to_emphasize)) / total if total > 0 else 0

    return {
        "skills_already_shown": skills_already_shown,
        "skills_to_emphasize": skills_to_emphasize,
        "skills_to_acquire": skills_to_acquire,
        "coverage_percent": round(coverage * 100, 1),
        "total_job_keywords": total,
        "gap_summary": {
            "shown": len(skills_already_shown),
            "can_add": len(skills_to_emphasize),
            "need_to_learn": len(skills_to_acquire),
        },
    }
