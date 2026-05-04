"""Cover Letter Helpers — analysis, generation, and scoring helpers."""

import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

STYLES: Dict[str, str] = {
    "professional": "Formal, confident, achievement-focused. Structured paragraphs.",
    "conversational": "Warm, personable, genuine enthusiasm. Natural first-person.",
    "technical": "Technical depth first. Specific technologies, quantified achievements.",
    "executive": "Strategic, high-level. Leadership, vision, business impact, P&L.",
}


class _CoverLetterHelpersMixin:
    """Private helper methods for CoverLetterAgent — culture, requirements, generation, scoring."""

    # ── Step 1: Culture analysis ────────────────────

    def _analyze_company_culture(
        self,
        job_text: str,
        company_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Extract company culture signals from job posting via LLM."""
        if not job_text or len(job_text.strip()) < 30:
            return None
        ctx = f" at {company_name}" if company_name else ""
        prompt = (
            f"Analyze the culture and values of this company{ctx} based on the job posting. "
            "Return ONLY a JSON object:\n"
            '{"company_tone":"<formal|casual|startup|corporate|mission-driven>",'
            '"values":["..."],"work_style":"<collaborative|independent|hybrid|agile>",'
            '"emphasis":["..."],"team_culture":"<description>",'
            '"role_positioning":"<leadership|IC|hybrid>",'
            '"language_tone":"<enthusiastic|neutral|formal|urgent>"}\n\n'
            f"Job posting:\n{job_text[:3000]}"
        )
        result = self._call_llm_json(prompt, task_type="analysis", max_tokens=1024)
        return result if isinstance(result, dict) and "company_tone" in result else None

    def _fallback_culture(self, job_text: str) -> Dict[str, Any]:
        """Heuristic culture analysis when LLM is unavailable."""
        t = (job_text or "").lower()
        culture: Dict[str, Any] = {
            "company_tone": "corporate",
            "values": [],
            "work_style": "collaborative",
            "emphasis": [],
            "team_culture": "",
            "role_positioning": "individual contributor",
            "language_tone": "neutral",
        }
        if any(w in t for w in ("startup", "fast-paced", "disrupt", "scrappy")):
            culture.update(company_tone="startup", language_tone="enthusiastic")
        elif any(w in t for w in ("mission", "impact", "purpose", "community")):
            culture["company_tone"] = "mission-driven"
        _val_kws = {
            "innovation": ["innovat", "cutting-edge", "pioneer", "transform"],
            "collaboration": ["collaborat", "team", "cross-functional", "partner"],
            "diversity": ["divers", "inclusion", "equit", "belonging"],
            "growth": ["grow", "scale", "expand", "develop"],
            "excellence": ["excellen", "quality", "best-in-class", "world-class"],
        }
        for val, kws in _val_kws.items():
            if any(kw in t for kw in kws):
                culture["values"].append(val)
        if any(w in t for w in ("agile", "scrum", "sprint")):
            culture["work_style"] = "agile"
        elif any(w in t for w in ("independent", "autonomous")):
            culture["work_style"] = "independent"
        if any(w in t for w in ("lead", "director", "vp", "head of", "manage")):
            culture["role_positioning"] = "leadership"
        return culture

    # ── Step 2: Job requirements ────────────────────

    def _extract_job_requirements(self, job_text: str) -> Dict[str, Any]:
        """Extract structured requirements from job posting (LLM with NLP fallback)."""
        if not job_text or len(job_text.strip()) < 20:
            return {}
        prompt = (
            "Extract key requirements from this job posting. Return ONLY a JSON object:\n"
            '{"required_skills":["..."],"preferred_skills":["..."],'
            '"experience_level":"entry|mid|senior|lead|executive",'
            '"industry_keywords":["..."],"key_responsibilities":["..."]}\n\n'
            f"Job posting:\n{job_text[:3000]}"
        )
        result = self._call_llm_json(prompt, task_type="analysis", max_tokens=1024)
        if isinstance(result, dict) and "required_skills" in result:
            return result
        return self._fallback_requirements(job_text)

    def _fallback_requirements(self, job_text: str) -> Dict[str, Any]:
        """Keyword-based requirement extraction fallback."""
        req: Dict[str, Any] = {
            "required_skills": [],
            "preferred_skills": [],
            "experience_level": "mid",
            "industry_keywords": [],
            "key_responsibilities": [],
        }
        try:
            from nlp_engine import extract_skill_phrases

            skills = list(extract_skill_phrases(job_text, use_llm_fallback=False))
            req["required_skills"], req["industry_keywords"] = skills[:15], skills[:20]
        except Exception:
            pass
        t = job_text.lower()
        if any(w in t for w in ("senior", "lead", "principal", "staff")):
            req["experience_level"] = "senior"
        elif any(w in t for w in ("junior", "entry", "associate", "intern")):
            req["experience_level"] = "entry"
        return req

    # ── Step 3: Build letter structure ──────────────

    def _build_letter_structure(
        self, profile: Dict[str, Any], job_req: Dict[str, Any], culture: Dict[str, Any], style: str
    ) -> Dict[str, Any]:
        """Create structured outline mapping candidate strengths to role needs."""
        cand: set[str] = set()
        li = profile.get("linkedin", {})
        for s in li.get("skills", []):
            name = s.get("skill", s.get("name", str(s))) if isinstance(s, dict) else str(s)
            cand.add(name.lower())
        for t in profile.get("top_technologies", []):
            cand.add(t.lower())
        for s in profile.get("higher_order_skills", []):
            cand.add(s.lower())
        required = job_req.get("required_skills", [])
        matched = [s for s in required if s.lower() in cand]
        gaps = [s for s in required if s.lower() not in cand]
        exps = [
            {
                "title": e.get("title", ""),
                "company": e.get("company", ""),
                "description": str(e.get("description", ""))[:300],
            }
            for e in li.get("experience", [])[:3]
            if isinstance(e, dict)
        ]
        return {
            "style": style,
            "style_guidance": STYLES.get(style, STYLES["professional"]),
            "opening_hook_inputs": {
                "headline": li.get("headline", ""),
                "top_match": matched[:3],
                "role_positioning": culture.get("role_positioning", ""),
            },
            "experience_mapping": {
                "matched_skills": matched,
                "gap_skills": gaps,
                "relevant_experience": exps,
                "key_responsibilities": job_req.get("key_responsibilities", [])[:5],
            },
            "culture_fit_signals": {
                "company_values": culture.get("values", []),
                "candidate_differentiators": profile.get("differentiators", []),
                "work_style": culture.get("work_style", "collaborative"),
                "company_tone": culture.get("company_tone", "corporate"),
            },
            "closing_strategy": {
                "experience_level": job_req.get("experience_level", "mid"),
                "language_tone": culture.get("language_tone", "neutral"),
            },
        }

    # ── Step 4: Generate letter (LLM) ──────────────

    def _generate_letter(
        self,
        structure: Dict[str, Any],
        profile_text: str,
        posting: Dict[str, Any],
        preferences: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Generate the cover letter via LLM using the prepared structure."""
        title = posting.get("title", "the role")
        company = posting.get("company", "the company")
        style_name = structure.get("style", "professional")
        exp_map = structure.get("experience_mapping", {})

        skills_ctx = ""
        if exp_map.get("matched_skills"):
            skills_ctx += f"Skills that match: {', '.join(exp_map['matched_skills'][:10])}\n"
        if exp_map.get("gap_skills"):
            skills_ctx += f"Gaps to bridge: {', '.join(exp_map['gap_skills'][:5])}\n"

        exp_ctx = "".join(
            f"- {e['title']} at {e['company']}: {e['description'][:200]}\n"
            for e in exp_map.get("relevant_experience", [])[:3]
        )

        culture_fit = structure.get("culture_fit_signals", {})
        culture_ctx = ""
        if culture_fit.get("company_values"):
            culture_ctx += f"Company values: {', '.join(culture_fit['company_values'])}\n"
        if culture_fit.get("candidate_differentiators"):
            culture_ctx += (
                f"Differentiators: {', '.join(culture_fit['candidate_differentiators'])}\n"
            )

        pref_ctx = ""
        if preferences:
            length = preferences.get("length", "standard")
            if length == "short":
                pref_ctx += "Keep concise — 2-3 short paragraphs.\n"
            elif length == "detailed":
                pref_ctx += "Write thoroughly — 4-5 detailed paragraphs.\n"
            if preferences.get("focus_areas"):
                pref_ctx += f"Emphasize: {', '.join(preferences['focus_areas'])}\n"
            if preferences.get("avoid"):
                pref_ctx += f"Avoid: {', '.join(preferences['avoid'])}\n"

        prompt = (
            f"Write a compelling cover letter for {title} at {company}.\n\n"
            f"STYLE: {style_name} — {structure.get('style_guidance', '')}\n\n"
            "Return ONLY a JSON object:\n"
            '{"subject":"<email subject>","greeting":"<salutation>",'
            '"body":"<3-4 paragraph letter>","closing":"<sign-off>",'
            f'"tone":"{style_name}"}}\n\n'
            f"SKILLS:\n{skills_ctx}"
        )
        if exp_ctx:
            prompt += f"\nEXPERIENCE:\n{exp_ctx}"
        if culture_ctx:
            prompt += f"\nCULTURE FIT:\n{culture_ctx}"
        if pref_ctx:
            prompt += f"\nPREFERENCES:\n{pref_ctx}"
        prompt += f"\nPROFILE:\n{profile_text}\n\nJOB DESCRIPTION:\n{posting.get('description', '')[:2500]}"  # noqa: E501

        return self._call_llm_json(prompt, task_type="narrative_generation", max_tokens=2048)

    # ── Step 5: Quality scoring ─────────────────────

    def _score_letter(
        self,
        letter_text: str,
        job_requirements: Dict[str, Any],
        culture: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Score cover letter: keyword coverage, structure, culture, professionalism, readability."""  # noqa: E501
        if not letter_text:
            return {"overall_score": 0, "breakdown": {}}

        text_lower = letter_text.lower()

        # Signal 1: Keyword coverage (35%)
        all_kw = list(
            set(
                job_requirements.get("required_skills", [])
                + job_requirements.get("industry_keywords", [])
            )
        )
        matched_kw = [kw for kw in all_kw if kw.lower() in text_lower]
        kw_score = (len(matched_kw) / len(all_kw) * 100) if all_kw else 50.0

        # Signal 2: Structure quality (20%)
        paras = [p.strip() for p in letter_text.split("\n\n") if p.strip()]
        words = len(letter_text.split())
        struct = 50.0
        struct += 25.0 if 3 <= len(paras) <= 5 else (10.0 if 2 <= len(paras) <= 6 else 0)
        struct += 25.0 if 200 <= words <= 500 else (10.0 if 150 <= words <= 600 else 0)
        struct = min(100.0, struct)

        # Signal 3: Culture alignment (20%)
        culture_terms = culture.get("values", []) + culture.get("emphasis", [])
        if culture_terms:
            cult = (
                sum(1 for t in culture_terms if t.lower() in text_lower) / len(culture_terms) * 100
            )
        else:
            cult = 50.0

        # Signal 4: Professionalism (15%)
        prof = 80.0
        if re.search(r"\[(?:Your|Candidate|Company|Position|Hiring)\s+\w+\]", letter_text, re.I):
            prof -= 30.0
        for gp in (
            "i am writing to apply",
            "i believe i am a great fit",
            "please find attached",
            "to whom it may concern",
        ):
            if gp in text_lower:
                prof -= 10.0
        prof = max(0.0, prof)

        # Signal 5: Readability (10%)
        sents = [s.strip() for s in re.split(r"[.!?]+", letter_text) if len(s.strip()) > 5]
        read = 50.0
        if sents:
            avg = sum(len(s.split()) for s in sents) / len(sents)
            read = 80.0 if 12 <= avg <= 28 else (60.0 if 8 <= avg <= 35 else 50.0)
            if len(sents) >= 3:
                lens = [len(s.split()) for s in sents]
                if max(lens) - min(lens) >= 5:
                    read = min(100.0, read + 20.0)

        raw = kw_score * 0.35 + struct * 0.20 + cult * 0.20 + prof * 0.15 + read * 0.10
        return {
            "overall_score": int(max(0, min(100, raw))),
            "breakdown": {
                "keyword_coverage": round(kw_score, 1),
                "structure_quality": round(struct, 1),
                "culture_alignment": round(cult, 1),
                "professionalism": round(prof, 1),
                "readability": round(read, 1),
            },
            "matched_keywords": matched_kw,
            "word_count": words,
            "paragraph_count": len(paras),
        }

    # ── Helpers ─────────────────────────────────────

    def _get_posting(
        self, posting_id: str, user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        if not posting_id:
            return None
        from models import get_db

        with get_db() as conn:
            q = "SELECT * FROM job_postings WHERE id=?" + (
                " AND user_id=?" if user_id is not None else ""
            )
            row = conn.execute(
                q, (posting_id, user_id) if user_id is not None else (posting_id,)
            ).fetchone()
        return dict(row) if row else None

    def _next_version(self, user_id: str, posting_id: str) -> int:
        from models import get_db

        with get_db() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM cover_letters WHERE user_id=? AND posting_id=?",
                (user_id, posting_id),
            ).fetchone()
        return (row[0] if row else 0) + 1
