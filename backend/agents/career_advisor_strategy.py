"""Career Advisor Strategy — role fit assessment, role recommendations, market insights."""

# Module contents:
# assess_role_fit()        — scores a job posting against the user's career profile
# recommend_next_roles()   — recommends target roles based on trajectory and skills
# get_market_insights()    — fetches market trend data for the user's domain

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from models import get_db

logger = logging.getLogger(__name__)


class _CareerAdvisorStrategyMixin:

    def assess_role_fit(self, user_id: int, posting_id: str) -> Dict[str, Any]:
        """Score how well a user fits a specific job posting.

        Args:
            user_id: User identifier.
            posting_id: job_postings.id to evaluate.

        Returns dict with overall fit_score (0-100), breakdown by category
        (skills_fit, experience_fit, seniority_fit, industry_fit), plus
        strengths, concerns, and evidence from resume/profile.
        """
        # Load posting
        with get_db() as conn:
            posting = conn.execute(
                "SELECT * FROM job_postings WHERE id = ?", (posting_id,)
            ).fetchone()

        if not posting:
            return {"error": f"Posting {posting_id} not found"}

        context = self._build_career_context(user_id)
        profile_text = context["profile_text"]

        posting_desc = posting["description"] or ""
        posting_info = (
            f"Title: {posting['title']}\nCompany: {posting['company']}\n"
            f"Location: {posting['location'] or 'Not specified'}\n"
            f"Description:\n{posting_desc[:2500]}"
        )

        # Include any previous scoring data
        score_context = ""
        try:
            missing = json.loads(posting["skills_missing"] or "[]")
            overlap = json.loads(posting["skills_overlap"] or "[]")
            nlp_score = posting["match_score"] or 0
            if missing or overlap:
                score_context = (
                    f"\n\nNLP pre-analysis (score={nlp_score}):\n"
                    f"  Skills matched: {', '.join(overlap[:10])}\n"
                    f"  Skills missing: {', '.join(missing[:10])}"
                )
        except (json.JSONDecodeError, TypeError):
            pass

        prompt = f"""Assess how well this candidate fits the job posting below.
Provide a detailed fit analysis with evidence.

Return ONLY a JSON object:
{{
  "fit_score": <0-100 overall fit>,
  "breakdown": {{
    "skills_fit": {{"score": <0-100>, "rationale": "<1 sentence>"}},
    "experience_fit": {{"score": <0-100>, "rationale": "<1 sentence>"}},
    "seniority_fit": {{"score": <0-100>, "rationale": "<1 sentence>"}},
    "industry_fit": {{"score": <0-100>, "rationale": "<1 sentence>"}}
  }},
  "strengths": [
    {{"point": "<strength>", "evidence": "<specific evidence from profile>"}}
  ],
  "concerns": [
    {{"point": "<concern>", "mitigation": "<how to address it>"}}
  ],
  "verdict": "<strong fit | good fit | moderate fit | weak fit>",
  "application_advice": "<1-2 sentences on whether and how to apply>"
}}

Candidate profile:
{profile_text}{score_context}

Job posting:
{posting_info}"""

        result, duration = self._timed(
            self._call_llm_json, prompt, task_type="career_planning", max_tokens=2048
        )

        self._log_run(
            user_id,
            f"Role fit: {posting['title']}",
            {"posting_id": posting_id},
            result or {},
            task_type="career_planning",
            duration_ms=duration,
        )

        if result:
            result["posting_id"] = posting_id
            result["posting_title"] = posting["title"]
            result["posting_company"] = posting["company"]
            self._save_analysis(
                user_id,
                "role_fit",
                result,
                target_role=posting["title"] or "",
            )
        return result or {"error": "Unable to assess role fit — LLM unavailable"}

    def recommend_next_roles(self, user_id: int, count: int = 5) -> Dict[str, Any]:
        """Suggest career moves based on trajectory, skills, and market trends.

        Args:
            user_id: User identifier.
            count: Number of role suggestions to return (1-10, default 5).

        Returns dict with ``recommendations`` list.
        """
        count = max(1, min(count, 10))
        context = self._build_career_context(user_id)
        profile_text = context["profile_text"]
        phases_text = context["phases_text"]
        portfolio = context["skills_portfolio"]

        portfolio_text = ""
        if portfolio:
            sections: List[str] = []
            for cat, skills in portfolio.items():
                if skills:
                    sections.append(f"  {cat}: {', '.join(skills[:15])}")
            if sections:
                portfolio_text = "\n\nSkills portfolio:\n" + "\n".join(sections)

        prompt = f"""Based on this professional's background, recommend {count} ideal next career moves.  # noqa: E501
Consider their skills, experience trajectory, market demand, and growth potential.

Return ONLY a JSON object:
{{
  "recommendations": [
    {{
      "title": "<role title>",
      "industry": "<target industry>",
      "fit_score": <0-100>,
      "salary_range": "<estimated salary range>",
      "reasoning": "<2-3 sentences on why this is a good fit>",
      "growth_potential": "<career growth from this role>",
      "key_requirements": ["<top 3 requirements the candidate meets>"],
      "gaps_to_address": ["<any gaps to close>"]
    }},
    ...{count} roles
  ]
}}

Professional profile:
{profile_text}{phases_text}{portfolio_text}"""

        result, duration = self._timed(
            self._call_llm_json, prompt, task_type="career_planning", max_tokens=2048
        )

        self._log_run(
            user_id,
            "Role recommendations",
            {"count": count},
            result or {},
            task_type="career_planning",
            duration_ms=duration,
        )

        if result:
            self._save_analysis(user_id, "role_recommendations", result)
        return result or {"error": "Unable to generate recommendations — LLM unavailable"}

    def get_market_insights(self, user_id: int) -> Dict[str, Any]:
        """Market trends and opportunities relevant to user's skills.

        Aggregates skills_missing and skills_overlap from all scraped job
        postings.  Produces demand rankings, skill overlap, gap list, and
        actionable recommendations.
        """
        with get_db() as conn:
            rows = conn.execute(
                "SELECT skills_missing, skills_overlap FROM job_postings WHERE user_id = ?",
                (user_id,),
            ).fetchall()

        skills_demand: Dict[str, int] = {}
        skills_have: Dict[str, int] = {}
        for r in rows:
            try:
                missing = json.loads(r["skills_missing"] or "[]")
                for s in missing:
                    k = s.strip().lower() if isinstance(s, str) else str(s).lower()
                    if k:
                        skills_demand[k] = skills_demand.get(k, 0) + 1
            except (json.JSONDecodeError, TypeError):
                pass
            try:
                overlap = json.loads(r["skills_overlap"] or "[]")
                for s in overlap:
                    k = s.strip().lower() if isinstance(s, str) else str(s).lower()
                    if k:
                        skills_have[k] = skills_have.get(k, 0) + 1
            except (json.JSONDecodeError, TypeError):
                pass

        top_demand = sorted(skills_demand.items(), key=lambda x: -x[1])[:15]
        top_have = sorted(skills_have.items(), key=lambda x: -x[1])[:15]
        gap = [s for s, _ in top_demand if s not in skills_have]

        return {
            "total_postings_analyzed": len(rows),
            "most_demanded_skills": [{"skill": s, "count": c} for s, c in top_demand],
            "skills_you_have": [{"skill": s, "count": c} for s, c in top_have],
            "skills_gap": gap[:10],
            "recommendations": self._market_recommendations(top_demand, skills_have, len(rows)),
        }
