"""Resume Tailor Scoring — ATS scoring, refinement, and data helpers."""

# Module contents:
# _fuzzy_skill_match()    — fuzzy substring match for skill names against resume text
# _score_ats_match()      — computes ATS match score across keyword, skill, and role buckets
# _apply_refinement()     — applies LLM refinement pass to improve ATS score
# _get_posting()          — fetches job posting row by posting_id from SQLite
# _load_deep_profile()    — loads deep career profile from deep_profile table
# _build_resume_data()    — builds structured resume data dict for optimization
# _run_nlp_fallback()     — NLP keyword overlap fallback scoring when LLM is unavailable

import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class _ResumeTailorScoringMixin:
    """Mixin providing ATS scoring, refinement application, and data helpers."""

    # ──────────────────────────────────────────────
    # Step 4: ATS scoring
    # ──────────────────────────────────────────────

    @staticmethod
    def _fuzzy_skill_match(skill: str, text_lower: str) -> bool:
        """Check if a skill appears in text using fuzzy matching.

        Handles multi-word phrases by checking if all significant words appear
        nearby in the text, plus direct substring match.
        """
        skill_lower = skill.lower().strip()
        if not skill_lower:
            return False
        # Direct substring match
        if skill_lower in text_lower:
            return True
        # Split into significant words (skip short stop-words)
        words = [w for w in skill_lower.split() if len(w) > 2]
        if not words:
            return False
        # Single-word skill: check word boundary
        if len(words) == 1:
            return bool(re.search(r"\b" + re.escape(words[0]) + r"\b", text_lower))
        # Multi-word: all significant words present anywhere in text
        return all(w in text_lower for w in words)

    def _score_ats_match(
        self,
        tailored_text: str,
        job_requirements: Dict[str, Any],
        job_text: str = "",
    ) -> Dict[str, Any]:
        """Score a tailored resume against ATS criteria.

        Uses a hybrid approach: fuzzy keyword overlap + section analysis +
        semantic similarity.

        Returns dict with overall_score (0-100), breakdown, matching/added keywords.
        """
        result: Dict[str, Any] = {
            "overall_score": 0,
            "breakdown": {},
            "matching_keywords": [],
            "added_keywords": [],
        }

        text_lower = tailored_text.lower()

        # --- Signal 1: Required skills coverage (40%) ---
        required_skills = job_requirements.get("required_skills", [])
        matched_required = []
        missing_required = []
        for skill in required_skills:
            if self._fuzzy_skill_match(skill, text_lower):
                matched_required.append(skill)
            else:
                missing_required.append(skill)
        required_coverage = (
            (len(matched_required) / len(required_skills) * 100) if required_skills else 50
        )

        # --- Signal 2: Industry keyword coverage (25%) ---
        industry_kw = job_requirements.get("industry_keywords", [])
        preferred = job_requirements.get("preferred_skills", [])
        all_keywords = list(set(industry_kw + preferred))
        matched_kw = [kw for kw in all_keywords if self._fuzzy_skill_match(kw, text_lower)]
        keyword_coverage = (len(matched_kw) / len(all_keywords) * 100) if all_keywords else 50

        # --- Signal 3: Section completeness (15%) ---
        section_patterns = {
            "summary": r"\b(?:summary|profile|objective|about)\b",
            "experience": r"\b(?:experience|work history|employment|professional)\b",
            "education": r"\b(?:education|academic|degree|university|college)\b",
            "skills": r"\b(?:skills|competencies|technologies|technical)\b",
        }
        sections_found = sum(
            1 for pat in section_patterns.values() if re.search(pat, tailored_text, re.IGNORECASE)
        )
        section_score = (sections_found / len(section_patterns)) * 100

        # --- Signal 4: Semantic similarity to job text (20%) ---
        semantic_score = 50.0  # default if similarity unavailable
        if job_text:
            try:
                from nlp_engine import calculate_similarity

                sim = calculate_similarity(tailored_text[:3000], job_text[:3000])
                semantic_score = sim * 100
            except Exception as exc:
                logger.debug("Semantic similarity unavailable: %s", exc)

        # --- Weighted score ---
        raw_score = (
            required_coverage * 0.40
            + keyword_coverage * 0.25
            + section_score * 0.15
            + semantic_score * 0.20
        )

        final_score = int(max(0, min(100, round(raw_score))))

        result["overall_score"] = final_score
        result["breakdown"] = {
            "required_skills_coverage": round(required_coverage, 1),
            "keyword_coverage": round(keyword_coverage, 1),
            "section_completeness": round(section_score, 1),
            "semantic_relevance": round(semantic_score, 1),
        }
        result["matching_keywords"] = matched_required + matched_kw
        result["added_keywords"] = missing_required

        return result

    # ──────────────────────────────────────────────
    # Step 5: Refinement (LLM)
    # ──────────────────────────────────────────────

    def _apply_refinement(
        self,
        current_text: str,
        job_text: str,
        feedback: str,
        job_requirements: Dict[str, Any],
    ) -> Optional[str]:
        """Apply user feedback to refine the tailored resume via LLM.

        Args:
            current_text: The current tailored resume text.
            job_text: The original job description.
            feedback: User's natural-language feedback.
            job_requirements: Structured job requirements dict.

        Returns:
            Refined resume text, or None on failure.
        """
        required_skills = ", ".join(job_requirements.get("required_skills", [])[:15])

        prompt = (
            "You are refining a previously tailored resume based on user feedback.\n\n"
            "INSTRUCTIONS:\n"
            "- Apply the user's feedback to improve the resume\n"
            "- Keep all factual information accurate\n"
            "- Maintain ATS-friendly formatting\n"
            "- Continue to target the required skills: " + required_skills + "\n"
            "- Return ONLY the revised resume text, no commentary\n\n"
            f"USER FEEDBACK:\n{feedback}\n\n"
            f"JOB DESCRIPTION (for context):\n{job_text[:2000]}\n\n"
            f"CURRENT RESUME:\n{current_text[:6000]}"
        )

        result = self._call_llm(prompt, task_type="reasoning", max_tokens=4096)
        if result and len(result.strip()) > 100:
            return result.strip()
        return None

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────

    def _get_posting(self, posting_id: str, user_id: Optional[str] = None) -> Optional[Dict]:
        """Load a job posting from the database."""
        from models import get_db

        with get_db() as conn:
            if user_id is not None:
                row = conn.execute(
                    "SELECT * FROM job_postings WHERE id = ? AND user_id = ?",
                    (posting_id, user_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM job_postings WHERE id = ?", (posting_id,)
                ).fetchone()
        return dict(row) if row else None

    def _load_deep_profile(self, user_id: str) -> Optional[Dict]:
        """Load deep career profile data if available."""
        try:
            from deep_profile import get_deep_profile_engine

            engine = get_deep_profile_engine()
            meta = engine.get_profile_with_meta(user_id)
            if meta:
                profile_data = meta.get("profile", meta)
                logger.debug(
                    "Deep profile loaded for user %s: %d keys",
                    user_id,
                    len(profile_data) if isinstance(profile_data, dict) else 0,
                )
                return profile_data
        except Exception as exc:
            logger.debug("Deep profile unavailable for user %s: %s", user_id, exc)
        return None

    def _build_resume_data(self, resume_text: str, user_id: str) -> Dict[str, Any]:
        """Build resume_data dict with text and skills, enriched with confirmed skills."""
        try:
            from nlp_engine import extract_keywords

            resume_skills = extract_keywords(resume_text, 20)
        except Exception:
            resume_skills = []

        resume_data: Dict[str, Any] = {"text": resume_text, "skills": resume_skills}

        # Inject confirmed skills from skills interviews
        try:
            from skills_enrichment import enrich_resume_data_with_confirmed_skills

            resume_data = enrich_resume_data_with_confirmed_skills(resume_data, user_id)
        except Exception:
            pass

        return resume_data

    def _run_nlp_fallback(
        self,
        resume_data: Dict[str, Any],
        jd_text: str,
        user_id: str,
        deep_profile_data: Optional[Dict] = None,
    ) -> tuple:
        """Fallback to NLP-only optimization when LLM is unavailable.

        Returns (optimized_text, duration_ms) tuple.
        """
        # Load LinkedIn profile for fallback optimization
        linkedin_profile = None
        try:
            import linkedin_cache

            linkedin_profile = linkedin_cache.get_raw(user_id)
        except (ImportError, AttributeError):
            pass

        try:
            from nlp_engine import extract_skill_phrases

            job_keywords = extract_skill_phrases(jd_text, use_llm_fallback=False)
        except Exception:
            job_keywords = []

        from utils import optimize_resume

        result, duration = self._timed(
            optimize_resume,
            resume_data,
            job_keywords,
            job_text=jd_text,
            linkedin_profile=linkedin_profile,
            deep_profile=deep_profile_data,
        )

        if result and result.get("optimized_text"):
            return result["optimized_text"], duration
        return None, duration
