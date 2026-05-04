import os
# p7-revert-test
import re

from linkedin_parser import get_default_linkedin_path, parse_linkedin_json
from nlp_engine import (
    calculate_similarity,
    extract_entities,
    extract_keywords,
)
from resume_scorer import score_resume
from skills_optimizer import (
    get_relevant_accomplishments,
    match_recommendations,
)


def process_resume(file_path):
    """Process resume file and extract text content (.txt, .pdf, .docx)."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Resume file not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext == ".txt":
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        elif ext == ".pdf":
            from pypdf import PdfReader

            text = ""
            with open(file_path, "rb") as f:
                reader = PdfReader(f)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        elif ext in (".docx", ".doc"):
            from docx import Document

            doc = Document(file_path)
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        else:
            # Fallback: try reading as plain text
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
    except ImportError as e:
        raise ImportError(
            f"Missing library for {ext} files: {e}. " "Install with: pip install pypdf python-docx"
        )

    text = text.strip()
    if not text:
        return {
            "text": "",
            "skills": [],
            "experience": [],
            "education": [],
        }

    skills = extract_keywords(text, 20)

    experience = _extract_experience_from_text(text)
    education = _extract_education_from_text(text)

    return {
        "text": text,
        "skills": skills,
        "experience": experience,
        "education": education,
    }


def _extract_experience_from_text(text):
    """Extract experience entries from raw resume text using heuristics."""
    experience = []
    lines = text.split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        title_match = re.search(
            r"(senior|junior|lead|principal|manager|director|developer|engineer|"
            r"consultant|architect|analyst|specialist)",
            line,
            re.IGNORECASE,
        )
        date_match = re.search(r"(\d{4})\s*[-–—]\s*(\d{4}|[Pp]resent)", line)

        if title_match and date_match:
            experience.append(
                {
                    "title": line.split(" at ")[0].strip() if " at " in line else line,
                    "company": line.split(" at ")[1].strip() if " at " in line else "",
                    "duration": date_match.group(0),
                }
            )

    return experience


def _extract_education_from_text(text):
    """Extract education entries from raw resume text using heuristics."""
    education = []
    lines = text.split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        edu_match = re.search(
            r"(B\.?S\.?|M\.?S\.?|B\.?A\.?|M\.?A\.?|Ph\.?D\.?|MBA|Bachelor|Master|Doctor)",
            line,
            re.IGNORECASE,
        )
        if edu_match:
            education.append(
                {
                    "degree": line,
                    "institution": "",
                }
            )

    return education


def analyze_job_description(text):
    """Analyze job description and extract key elements using NLP."""
    required_skills = extract_keywords(text, 15)

    entities = extract_entities(text)
    org_names = [ent[0] for ent in entities if ent[1] == "ORG"]

    responsibilities = []
    qualifications = []

    lines = text.split("\n")
    section = None
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        lower = stripped.lower()
        if any(kw in lower for kw in ["responsibilities", "duties", "what you'll do", "role"]):
            section = "responsibilities"
            continue
        elif any(
            kw in lower
            for kw in [
                "qualifications",
                "requirements",
                "what you need",
                "must have",
            ]
        ):
            section = "qualifications"
            continue

        if stripped.startswith(("-", "*", "•", "–")):
            item = stripped.lstrip("-*•– ").strip()
            if item:
                if section == "qualifications":
                    qualifications.append(item)
                else:
                    responsibilities.append(item)

    return {
        "required_skills": required_skills,
        "responsibilities": responsibilities,
        "qualifications": qualifications,
        "companies_mentioned": org_names,
    }


def optimize_resume(
    resume_data, job_keywords, job_text="", linkedin_profile=None, deep_profile=None,
    equivalencies=None, ignored_keywords=None,
):
    """Optimize resume using multi-signal ATS scoring + content enhancement."""
    resume_text = resume_data.get("text", "")

    # If no full job text, reconstruct from keywords
    if not job_text:
        job_text = " ".join(job_keywords)

    # --- Multi-signal scoring (delegated to resume_scorer) ---
    scoring = score_resume(
        resume_data, job_keywords, job_text, linkedin_profile,
        equivalencies=equivalencies, ignored_keywords=ignored_keywords,
    )
    final_score = scoring["score"]
    section_checks = scoring["sections_found"]
    matching_keywords = scoring["matching_keywords"]
    missing_keywords = scoring["missing_keywords"]
    phrase_overlap = set(scoring.get("skill_phrases_matched", []))
    skills_result = {"missing_skills": scoring.get("missing_skills", [])}
    keyword_score = scoring["score_breakdown"]["keyword_coverage"]
    semantic_score = scoring["score_breakdown"]["semantic_similarity"]
    skills_score = scoring["score_breakdown"]["skills_match"]
    section_score = scoring["score_breakdown"]["section_completeness"]

    # --- Content enhancement ---
    optimized_text = resume_text.rstrip()

    # Inject accomplishment bullets from LinkedIn if available
    accomplishments = []
    recommendations = []
    if linkedin_profile:
        accomplishments = get_relevant_accomplishments(linkedin_profile, job_text, top_n=5)
        recommendations = match_recommendations(linkedin_profile, job_text, top_n=3)

        # Add endorsement-backed skills that are missing from resume
        endorsed_missing = [
            s["keyword"]
            for s in skills_result.get("missing_skills", [])
            if s.get("endorsements", 0) > 0
        ]
        if endorsed_missing:
            optimized_text += "\n\nEndorsed Skills: " + ", ".join(endorsed_missing)

        # Add relevant accomplishment bullets
        if accomplishments:
            optimized_text += "\n\nKey Accomplishments:"
            for acc in accomplishments:
                if acc["relevance_score"] > 30:
                    optimized_text += f"\n- {acc['text']} ({acc['source_company']})"

        # Add relevant recommendation excerpts
        if recommendations:
            optimized_text += "\n\nProfessional Endorsements:"
            for rec in recommendations:
                if rec["relevance_score"] > 30:
                    author = rec.get("author", "")
                    optimized_text += f'\n- "{rec["text"]}" — {author}'
    else:
        # Fallback: append missing keywords (old behavior)
        if missing_keywords:
            optimized_text += "\n\nAdditional Relevant Skills: " + ", ".join(missing_keywords[:20])

    # Enhance with deep profile differentiators and business impacts
    deep_bullets = []
    if deep_profile:
        for impact in deep_profile.get("business_impacts", []):
            bullet = impact.get("star_bullet", "")
            if bullet and calculate_similarity(bullet, job_text) > 0.3:
                deep_bullets.append(bullet)
        if deep_bullets and "Key Accomplishments" not in optimized_text:
            optimized_text += "\n\nKey Accomplishments:"
            for bullet in deep_bullets[:3]:
                optimized_text += f"\n- {bullet}"

        for diff in deep_profile.get("differentiators", []):
            narrative = diff.get("narrative", "")
            if (
                narrative
                and len(narrative) > 20
                and calculate_similarity(narrative, job_text) > 0.25
            ):  # noqa: E501
                if "\nProfessional Highlights:" not in optimized_text:
                    optimized_text += "\n\nProfessional Highlights:"
                optimized_text += f"\n- {narrative[:200]}"

    # LLM rewrite pass (when available)
    if job_text and len(resume_text) > 100:
        rewritten = _llm_rewrite_resume(
            resume_text, job_text, accomplishments, recommendations, deep_profile
        )
        if rewritten and len(rewritten) > len(resume_text) * 0.5:
            optimized_text = _restore_missing_sections(rewritten, resume_text)

    return {
        "original_text": resume_text,
        "optimized_text": optimized_text,
        "added_keywords": missing_keywords,
        "matching_keywords": matching_keywords,
        "ats_compliance": final_score >= 50,
        "score": final_score,
        "score_breakdown": {
            "keyword_coverage": round(keyword_score, 1),
            "semantic_similarity": round(semantic_score, 1),
            "skills_match": round(skills_score, 1),
            "section_completeness": round(section_score, 1),
        },
        "sections_found": section_checks,
        "accomplishments": accomplishments,
        "recommendations": recommendations,
        "skill_phrases_matched": sorted(phrase_overlap),
        "deep_profile_bullets": deep_bullets,
    }


_RESTORE_HEADERS = (r'(?:^|\n)((?:Education|Certifications?|Awards?|'
                    r'Additional Information|Technical Skills|'
                    r'Selected Prior Engagements|Earlier Career|'
                    r'Prior Leadership|Licenses?|Volunteer)[^\n]*)\n')


def _restore_missing_sections(rewritten: str, original: str) -> str:
    """Re-append well-known sections from the original that the LLM dropped."""
    rewritten_lower = rewritten.lower()
    missing = []
    for m in re.finditer(_RESTORE_HEADERS, original, re.IGNORECASE):
        header = m.group(1).strip()
        if header.split()[0].lower() in rewritten_lower:
            continue
        start = m.start() + (1 if original[m.start()] == '\n' else 0)
        rest = original[start:]
        nxt = re.search(r'\n(?=[A-Z][A-Za-z\s&]+\n)', rest[len(header)+1:])
        chunk = rest[:len(header) + 1 + nxt.start()].strip() if nxt else rest.strip()
        if chunk:
            missing.append(chunk)
    if missing:
        rewritten = rewritten.rstrip() + "\n\n" + "\n\n".join(missing)
    return rewritten


def _llm_rewrite_resume(resume_text, job_text, accomplishments, recommendations, deep_profile):
    """Use LLM to rewrite resume sections for JD alignment."""
    from llm_helper import call_llm_quality

    # Build enhancement context
    acc_text = ""
    if accomplishments:
        acc_text = "\n".join(
            f"- {a['text']} ({a['source_company']})"
            for a in accomplishments[:5]
            if a.get("relevance_score", 0) > 30
        )

    rec_text = ""
    if recommendations:
        rec_text = "\n".join(
            f'- "{r["text"]}" — {r.get("author", "")}'
            for r in recommendations[:3]
            if r.get("relevance_score", 0) > 30
        )

    deep_text = ""
    if deep_profile:
        bullets = deep_profile.get("business_impacts", [])[:3]
        deep_text = "\n".join(
            f"- {b.get('star_bullet', '')}" for b in bullets if b.get("star_bullet")
        )
        diffs = deep_profile.get("differentiators", [])[:2]
        if diffs:
            deep_text += "\n" + "\n".join(f"- {d.get('narrative', '')[:200]}" for d in diffs)

    prompt = (
        "You are an expert ATS resume optimizer. Rewrite the resume below to maximize "
        "keyword alignment with the target job description "
        "while preserving all factual content.\n\n"
        f"TARGET JOB DESCRIPTION:\n{job_text[:3000]}\n\n"
        f"CURRENT RESUME:\n{resume_text[:6000]}\n\n"
    )

    if acc_text:
        prompt += f"RELEVANT ACCOMPLISHMENTS (weave into Experience section):\n{acc_text}\n\n"
    if rec_text:
        prompt += f"ENDORSEMENT QUOTES (use sparingly):\n{rec_text}\n\n"
    if deep_text:
        prompt += f"CAREER HIGHLIGHTS (integrate where relevant):\n{deep_text}\n\n"

    prompt += (
        "RULES:\n"
        "- Preserve ALL dates, company names, job titles, and education exactly\n"
        "- Do NOT invent metrics, certifications, or experience\n"
        "- Weave JD keywords naturally into existing bullet points\n"
        "- Add accomplishment bullets under the relevant Experience entry\n"
        "- Strengthen the Summary/Profile section to mirror JD language\n"
        "- Keep standard ATS-friendly section headers (Summary, Experience, Skills, Education)\n"
        "- Output the full rewritten resume text, nothing else\n"
    )

    try:
        result = call_llm_quality(prompt, task_type="reasoning", max_tokens=4096)
        return result
    except Exception:
        return None


def validate_resume_format(resume_text):
    """Validate resume format for ATS compatibility."""
    issues = []
    if not re.search(r"\b(?:skills|competencies|abilities)\b", resume_text, re.IGNORECASE):
        issues.append("Missing skills section")
    if not re.search(r"\b(?:experience|work history)\b", resume_text, re.IGNORECASE):
        issues.append("Missing experience section")
    if not re.search(r"\b(?:education|academic background)\b", resume_text, re.IGNORECASE):
        issues.append("Missing education section")
    return {"is_ats_compliant": len(issues) == 0, "issues": issues}


def generate_ats_guidelines():
    """Generate ATS optimization guidelines."""
    return {
        "formatting": ["Use standard file formats (.docx, .pdf)",
                        "Avoid tables, columns, and complex layouts",
                        "Use simple fonts (Arial, Calibri, Times New Roman)"],
        "content": ["Include relevant keywords from job description",
                     "Use standard section headers (Experience, Education)",
                     "List skills in bullet points", "Include dates in MM/YYYY format"],
        "best_practices": ["Keep resume to 1-2 pages",
                            "Use action verbs (developed, implemented, managed)",
                            "Quantify achievements where possible",
                            "Match resume to job description"],
    }


def process_linkedin_profile(linkedin_path=None):
    """Process a LinkedIn profile JSON and convert to the same format as process_resume()."""
    if linkedin_path is None:
        linkedin_path = get_default_linkedin_path()

    if not os.path.exists(linkedin_path):
        raise FileNotFoundError(f"LinkedIn JSON not found: {linkedin_path}")

    profile = parse_linkedin_json(linkedin_path)

    # Build experience list in process_resume format
    experience = []
    for exp in profile.get("experience", []):
        start = exp.get("start_date", "")
        end = exp.get("end_date", "")
        duration = f"{start} - {end}" if start else ""
        experience.append(
            {
                "title": exp.get("title", ""),
                "company": exp.get("company", ""),
                "duration": duration,
                "description": exp.get("description", ""),
                "accomplishments": exp.get("accomplishments", []),
            }
        )

    # Build education list
    education = []
    for edu in profile.get("education", []):
        degree = edu.get("degree", "")
        field = edu.get("field", "")
        degree_str = f"{degree} in {field}" if degree and field else degree or field
        education.append(
            {
                "degree": degree_str,
                "institution": edu.get("school", ""),
            }
        )

    # Build skills list (sorted by endorsement count)
    skills_data = profile.get("skills", [])
    skills_sorted = sorted(skills_data, key=lambda s: s.get("endorsements", 0), reverse=True)
    skills = [s["name"] for s in skills_sorted if s.get("name")]

    # Build formatted text from profile data
    lines = []
    if profile.get("name"):
        lines.append(profile["name"])
    if profile.get("headline"):
        lines.append(profile["headline"])
    if profile.get("summary"):
        lines.append("")
        lines.append("Summary")
        lines.append(profile["summary"])

    if experience:
        lines.append("")
        lines.append("Experience")
        for exp in experience:
            lines.append(f"{exp['title']} at {exp['company']} ({exp['duration']})")
            if exp.get("description"):
                lines.append(exp["description"])

    if education:
        lines.append("")
        lines.append("Education")
        for edu in education:
            lines.append(f"{edu['degree']} — {edu['institution']}")

    if skills:
        lines.append("")
        lines.append("Skills")
        lines.append(", ".join(skills[:30]))

    text = "\n".join(lines)

    return {
        "text": text,
        "skills": skills,
        "experience": experience,
        "education": education,
        "recommendations": profile.get("recommendations", []),
    }
