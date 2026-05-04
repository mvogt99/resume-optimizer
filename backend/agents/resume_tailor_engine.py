"""Resume Tailor Engine — job analysis, experience matching, resume generation."""

# Module contents:
# _analyze_job_requirements()    — LLM-based extraction of required skills and keywords from JD
# _fallback_job_analysis()       — regex-based fallback job analysis when LLM is unavailable
# _match_experience()            — matches user's profile experience against JD requirements
# _generate_tailored_resume()    — generates ATS-optimized tailored resume text

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class _ResumeTailorEngineMixin:
    """Mixin providing job analysis, experience matching, and resume generation."""

    # ──────────────────────────────────────────────
    # Step 1: Analyze job requirements (LLM)
    # ──────────────────────────────────────────────

    def _analyze_job_requirements(self, job_text: str) -> Optional[Dict[str, Any]]:
        """Extract structured job requirements from a posting via LLM.

        Returns a dict with keys: required_skills, preferred_skills,
        experience_level, key_responsibilities, industry_keywords,
        education, certifications, soft_skills.
        """
        if not job_text or len(job_text.strip()) < 20:
            return None

        prompt = (
            "Analyze this job posting and extract structured requirements. "
            "Return ONLY a JSON object with these keys:\n"
            "{\n"
            '  "required_skills": ["skill1", "skill2", ...],\n'
            '  "preferred_skills": ["skill1", "skill2", ...],\n'
            '  "experience_level": "entry|mid|senior|lead|executive",\n'
            '  "years_experience": <int or null>,\n'
            '  "key_responsibilities": ["resp1", "resp2", ...],\n'
            '  "industry_keywords": ["keyword1", "keyword2", ...],\n'
            '  "education": "requirement or null",\n'
            '  "certifications": ["cert1", ...],\n'
            '  "soft_skills": ["skill1", "skill2", ...]\n'
            "}\n\n"
            f"Job posting:\n{job_text[:4000]}"
        )

        result = self._call_llm_json(prompt, task_type="analysis", max_tokens=2048)
        if isinstance(result, dict) and "required_skills" in result:
            return result
        return None

    def _fallback_job_analysis(self, job_text: str) -> Dict[str, Any]:
        """NLP-only fallback when LLM is unavailable for job analysis.

        Uses spaCy/NLTK keyword extraction to build a basic requirements dict.
        """
        requirements: Dict[str, Any] = {
            "required_skills": [],
            "preferred_skills": [],
            "experience_level": "mid",
            "years_experience": None,
            "key_responsibilities": [],
            "industry_keywords": [],
            "education": None,
            "certifications": [],
            "soft_skills": [],
        }

        try:
            from nlp_engine import extract_skill_phrases

            skills = extract_skill_phrases(job_text, use_llm_fallback=False)
            requirements["required_skills"] = list(skills)[:20]
            requirements["industry_keywords"] = list(skills)[:30]
        except Exception as exc:
            logger.debug("NLP skill extraction failed: %s", exc)

        try:
            from nlp_engine import extract_keywords

            keywords = extract_keywords(job_text, 30)
            # Merge keywords not already in required_skills
            existing = {s.lower() for s in requirements["required_skills"]}
            for kw in keywords:
                if kw.lower() not in existing:
                    requirements["industry_keywords"].append(kw)
        except Exception:
            pass

        # Simple heuristic for experience level
        text_lower = job_text.lower()
        if "senior" in text_lower or "lead" in text_lower or "principal" in text_lower:
            requirements["experience_level"] = "senior"
        elif "junior" in text_lower or "entry" in text_lower or "associate" in text_lower:
            requirements["experience_level"] = "entry"

        # Try to extract years of experience
        years_match = re.search(r"(\d+)\+?\s*(?:years?|yrs?)\s*(?:of\s+)?experience", text_lower)
        if years_match:
            requirements["years_experience"] = int(years_match.group(1))

        return requirements

    # ──────────────────────────────────────────────
    # Step 2: Match experience to requirements
    # ──────────────────────────────────────────────

    def _match_experience(
        self,
        resume_data: Dict[str, Any],
        job_requirements: Dict[str, Any],
        profile: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Find the best matching experiences from resume/profile against job requirements.

        Returns a list of match dicts, each with:
            requirement, matched_experience, relevance (high/medium/low), source.
        """
        matches: List[Dict[str, Any]] = []
        resume_text = resume_data.get("text", "").lower()
        resume_skills = {s.lower() for s in resume_data.get("skills", [])}

        # Enrich with profile data
        if profile:
            for skill in profile.get("higher_order_skills", []):
                resume_skills.add(skill.lower())
            for tech in profile.get("top_technologies", []):
                resume_skills.add(tech.lower())

        required = job_requirements.get("required_skills", [])
        preferred = job_requirements.get("preferred_skills", [])

        # Match required skills
        for skill in required:
            skill_lower = skill.lower()
            found_in_skills = skill_lower in resume_skills
            found_in_text = skill_lower in resume_text
            if found_in_skills or found_in_text:
                matches.append(
                    {
                        "requirement": skill,
                        "matched_experience": skill,
                        "relevance": "high",
                        "source": "skills" if found_in_skills else "resume_text",
                        "is_required": True,
                    }
                )
            else:
                matches.append(
                    {
                        "requirement": skill,
                        "matched_experience": None,
                        "relevance": "gap",
                        "source": None,
                        "is_required": True,
                    }
                )

        # Match preferred skills
        for skill in preferred:
            skill_lower = skill.lower()
            found_in_skills = skill_lower in resume_skills
            found_in_text = skill_lower in resume_text
            if found_in_skills or found_in_text:
                matches.append(
                    {
                        "requirement": skill,
                        "matched_experience": skill,
                        "relevance": "medium",
                        "source": "skills" if found_in_skills else "resume_text",
                        "is_required": False,
                    }
                )

        # Match LinkedIn experience entries if available
        li_experience = (profile or {}).get("linkedin", {}).get("experience", [])
        responsibilities = job_requirements.get("key_responsibilities", [])
        for resp in responsibilities[:5]:
            resp_lower = resp.lower()
            for exp in li_experience:
                if not isinstance(exp, dict):
                    continue
                exp_title = str(exp.get("title", "")).lower()
                exp_desc = str(exp.get("description", "")).lower()
                if any(word in exp_title or word in exp_desc for word in resp_lower.split()[:3]):
                    matches.append(
                        {
                            "requirement": resp,
                            "matched_experience": (
                                f"{exp.get('title', '')} at {exp.get('company', '')}"
                            ),
                            "relevance": "high",
                            "source": "linkedin",
                            "is_required": True,
                        }
                    )
                    break

        return matches

    # ──────────────────────────────────────────────
    # Step 3: Generate tailored resume (LLM)
    # ──────────────────────────────────────────────

    def _generate_tailored_resume(
        self,
        resume_data: Dict[str, Any],
        job_requirements: Dict[str, Any],
        experience_matches: List[Dict[str, Any]],
        profile_text: str,
        posting: Dict[str, Any],
        preferences: Optional[Dict[str, Any]] = None,
        success_context: str = "",
    ) -> Optional[str]:
        """Use LLM to rewrite the resume, emphasizing matched experience.

        Returns the tailored resume text, or None on failure.
        """
        resume_text = resume_data.get("text", "")
        if not resume_text:
            return None

        # Build match summary for the prompt
        strong_matches = [m for m in experience_matches if m["relevance"] == "high"]
        gaps = [m for m in experience_matches if m["relevance"] == "gap"]
        match_summary = ""
        if strong_matches:
            match_summary += "Strong matches to emphasize:\n"
            for m in strong_matches[:10]:
                match_summary += f"- {m['requirement']}"
                if m.get("matched_experience"):
                    match_summary += f" (from: {m['matched_experience']})"
                match_summary += "\n"
        if gaps:
            match_summary += "\nSkill gaps to address via transferable skills:\n"
            for m in gaps[:5]:
                match_summary += f"- {m['requirement']}\n"

        # Preferences
        pref_text = ""
        if preferences:
            tone = preferences.get("tone", "professional")
            emphasis = preferences.get("emphasis", [])
            length = preferences.get("length", "standard")
            pref_parts = [f"Tone: {tone}", f"Length: {length}"]
            if emphasis:
                pref_parts.append(f"Extra emphasis on: {', '.join(emphasis)}")
            pref_text = "\n".join(pref_parts)

        title = posting.get("title", "the role")
        company = posting.get("company", "the company")

        prompt = (
            f"Rewrite the following resume to be highly tailored for the position of "
            f"{title} at {company}.\n\n"
            "INSTRUCTIONS:\n"
            "- Preserve all factual information (dates, companies, degrees)\n"
            "- Rewrite bullet points to emphasize relevant experience and skills\n"
            "- Use ATS-friendly formatting (clear section headers, no tables/graphics)\n"
            "- Incorporate industry keywords naturally, not as a keyword dump\n"
            "- For skill gaps, highlight transferable skills that map to the requirement\n"
            "- Keep the resume concise (2 pages max equivalent)\n"
            "- Return ONLY the rewritten resume text, no commentary\n\n"
            f"TARGET ROLE REQUIREMENTS:\n"
            f"Required skills: {', '.join(job_requirements.get('required_skills', []))}\n"
            f"Experience level: {job_requirements.get('experience_level', 'not specified')}\n\n"
            f"EXPERIENCE MATCHING:\n{match_summary}\n"
        )

        if pref_text:
            prompt += f"USER PREFERENCES:\n{pref_text}\n\n"

        if profile_text and profile_text != "No profile data available.":
            prompt += f"ADDITIONAL PROFILE CONTEXT:\n{profile_text[:1000]}\n\n"

        # P2-C: Inject success context from historical application feedback
        if success_context:
            prompt += f"HISTORICAL SUCCESS PATTERNS:\n{success_context}\n\n"

        # P2-B.4: Inject untapped evidence to encourage broader coverage
        try:
            from graph_traceability import build_untapped_prompt_injection, get_untapped_evidence

            untapped = get_untapped_evidence(limit=5)
            injection = build_untapped_prompt_injection(untapped)
            if injection:
                prompt += f"\n{injection}\n\n"
        except Exception:
            pass

        prompt += f"ORIGINAL RESUME:\n{resume_text[:6000]}"

        result = self._call_llm(prompt, task_type="reasoning", max_tokens=4096)
        if result and len(result.strip()) > 100:
            return result.strip()
        return None
