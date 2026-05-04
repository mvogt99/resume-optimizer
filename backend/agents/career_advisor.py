"""Career Advisor Agent — trajectory analysis, skills gap, role fit, roadmap, market insights via RTX 5090."""  # noqa: E501

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseCareerAgent
from agents.career_advisor_analysis import _CareerAdvisorAnalysisMixin
from agents.career_advisor_strategy import _CareerAdvisorStrategyMixin
from models import get_db


class CareerAdvisorAgent(_CareerAdvisorStrategyMixin, _CareerAdvisorAnalysisMixin, BaseCareerAgent):
    """Strategic career advisor powered by local LLM.

    Provides trajectory analysis, skills gap assessment, role fit scoring,
    role recommendations, market insights, and application feedback analysis.
    All LLM calls route through RTX 5090 ($0.00).
    """

    agent_type: str = "career_advisor"

    # Navigation — method locations:
    #   career_advisor.py       analyze_career, get_skills_roadmap, get_role_recommendations,
    #                           get_history, market_insights, feedback_analysis,
    #                           analyze_trajectory, analyze_skills_gap
    #   career_advisor_strategy.py  assess_role_fit, recommend_next_roles, get_market_insights
    #   career_advisor_analysis.py  _build_career_context, _extract_career_phases,
    #                               _compute_skills_portfolio, _market_recommendations, _save_analysis
    #   base_agent.py           _call_llm, _log_run, _get_user_profile, _profile_summary,
    #                           _record_claim, _get_arango_context

    # ──────────────────────────────────────────────
    # Public API — existing methods (routes depend on these names)
    # ──────────────────────────────────────────────

    def analyze_career(self, user_id: int) -> Dict[str, Any]:
        """Full career trajectory analysis with LLM-powered insights.

        Returns dict with career_trajectory, strengths, growth_areas,
        market_alignment, recommended_learning, and role_recommendations.
        """
        context = self._build_career_context(user_id)
        profile_text = context["profile_text"]
        journey_text = context["journey_text"]
        phases_text = context["phases_text"]

        # CT-4: Inject ArangoDB skills/milestone context before generation
        arango_ctx = self._get_arango_context(user_id, self.agent_type)
        if arango_ctx:
            profile_text = f"{profile_text}\n\n<arango_context>\n{arango_ctx}\n</arango_context>"

        prompt = f"""Analyze this professional's career and provide strategic advice.

Return ONLY a JSON object:
{{
  "career_trajectory": {{
    "current_phase": "<early career | mid-career | senior | executive>",
    "momentum": "<accelerating | steady | pivoting | stalled>",
    "summary": "<2-3 sentence career trajectory assessment>"
  }},
  "strengths": [
    {{"area": "<strength area>", "evidence": "<why>",
      "leverage": "<how to leverage>"}},
    ...up to 5
  ],
  "growth_areas": [
    {{"area": "<growth area>", "priority": "<high|medium|low>",
      "action": "<specific action to take>"}},
    ...up to 5
  ],
  "market_alignment": {{
    "trending_skills": ["<skill matching market trends>", ...],
    "emerging_gaps": ["<skill the market is moving toward that the candidate lacks>", ...],
    "score": <0-100 market alignment score>
  }},
  "recommended_learning": [
    {{"topic": "<what to learn>", "why": "<market relevance>",
      "format": "<course|project|certification>"}},
    ...up to 5
  ],
  "role_recommendations": [
    {{"title": "<role title>", "fit_score": <0-100>, "reasoning": "<why this role fits>"}},
    ...up to 5
  ]
}}

Professional profile:
{profile_text}{journey_text}{phases_text}"""

        result, duration = self._timed(
            self._call_llm_json, prompt, task_type="career_planning", max_tokens=3072
        )

        self._log_run(
            user_id,
            "Career analysis",
            {},
            result or {},
            task_type="career_planning",
            duration_ms=duration,
        )

        if result:
            self._save_analysis(user_id, "career_analysis", result)

        # CT-1: Record claim for accountability audit
        self._record_claim(
            user_id,
            "career_advisor",
            profile_text[:500],
            str(result.get("career_trajectory", {}) if result else {})[:500],
            metadata={"analysis_type": "career_analysis"},
        )

        return result or {"error": "Unable to analyze career — LLM unavailable"}

    def get_skills_roadmap(self, user_id: int, target_role: str) -> Dict[str, Any]:
        """Generate a phased learning path toward a target role.

        Args:
            user_id: User identifier.
            target_role: Title of the target role (e.g. "VP of Engineering").

        Returns dict with target_role, current_readiness, timeline_months,
        phases (with skills + resources + milestones), quick_wins, key_gap.
        """
        context = self._build_career_context(user_id)
        profile_text = context["profile_text"]
        portfolio = context["skills_portfolio"]

        portfolio_text = ""
        if portfolio:
            sections: List[str] = []
            for cat, skills in portfolio.items():
                if skills:
                    sections.append(f"  {cat}: {', '.join(skills[:15])}")
            if sections:
                portfolio_text = "\n\nSkills portfolio:\n" + "\n".join(sections)

        prompt = f"""Create a skills development roadmap for transitioning to this target role.

Return ONLY a JSON object:
{{
  "target_role": "{target_role}",
  "current_readiness": <0-100 readiness percentage>,
  "timeline_months": <estimated months to be fully ready>,
  "phases": [
    {{
      "phase": <1-based phase number>,
      "name": "<phase name>",
      "duration_weeks": <weeks>,
      "skills": ["<skill to develop>", ...],
      "resources": ["<specific course, book, or project>", ...],
      "milestone": "<what success looks like at end of phase>"
    }},
    ...3-5 phases
  ],
  "quick_wins": ["<things to do this week>", ...up to 3],
  "key_gap": "<the single biggest gap to address>"
}}

Target role: {target_role}

Current profile:
{profile_text}{portfolio_text}"""

        result, duration = self._timed(
            self._call_llm_json, prompt, task_type="career_planning", max_tokens=2048
        )

        self._log_run(
            user_id,
            f"Skills roadmap: {target_role}",
            {"target_role": target_role},
            result or {},
            task_type="career_planning",
            duration_ms=duration,
        )

        if result:
            self._save_analysis(user_id, "skills_roadmap", result, target_role=target_role)
        return result or {"error": "Unable to generate roadmap — LLM unavailable"}

    def get_role_recommendations(self, user_id: int) -> Dict[str, Any]:
        """Suggest ideal next roles with fit reasoning.

        Returns dict with ``recommendations`` list — each entry has title,
        industry, fit_score, salary_range, reasoning, growth_potential,
        key_requirements, and gaps_to_address.
        """
        return self.recommend_next_roles(user_id, count=5)

    def get_history(
        self, user_id: int, analysis_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve past career analyses for a user.

        Args:
            user_id: User identifier.
            analysis_type: Optional filter (e.g. "career_analysis", "skills_roadmap").

        Returns list of analysis records, most recent first.
        """
        with get_db() as conn:
            if analysis_type:
                rows = conn.execute(
                    "SELECT * FROM career_analyses WHERE user_id = ? AND analysis_type = ? "
                    "ORDER BY created_at DESC LIMIT 20",
                    (user_id, analysis_type),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM career_analyses WHERE user_id = ? "
                    "ORDER BY created_at DESC LIMIT 20",
                    (user_id,),
                ).fetchall()
        results: List[Dict[str, Any]] = []
        for row in rows:
            d = dict(row)
            try:  # noqa: SIM105
                d["result_json"] = json.loads(d["result_json"])
            except (json.JSONDecodeError, TypeError):
                pass
            results.append(d)
        return results

    def market_insights(self, user_id: int) -> Dict[str, Any]:
        """Analyze skills demand from all scraped job descriptions.

        Aggregates skills_missing and skills_overlap across all postings
        to surface market trends and gaps.
        """
        return self.get_market_insights(user_id)

    def feedback_analysis(self, user_id: int) -> Dict[str, Any]:
        """Analyze application outcomes for patterns.

        Joins application_feedback with job_postings to find correlations
        between match scores and outcomes.
        """
        with get_db() as conn:
            rows = conn.execute(
                "SELECT af.outcome, af.posting_id, jp.title, jp.company, jp.match_score "
                "FROM application_feedback af "
                "LEFT JOIN job_postings jp ON af.posting_id = jp.id "
                "WHERE af.user_id = ?",
                (user_id,),
            ).fetchall()

        if not rows:
            return {
                "total_applications": 0,
                "outcome_distribution": {},
                "success_patterns": [],
                "recommendations": ["Start applying and recording outcomes to get analysis."],
            }

        outcomes: Dict[str, int] = {}
        scores_by_outcome: Dict[str, List[float]] = {}
        for r in rows:
            o: str = r["outcome"]
            outcomes[o] = outcomes.get(o, 0) + 1
            score = r["match_score"] or 0
            if score > 0:
                scores_by_outcome.setdefault(o, []).append(float(score))

        patterns: List[str] = []
        positive = ["interview", "offer"]
        positive_scores: List[float] = []
        negative_scores: List[float] = []
        for o, scores in scores_by_outcome.items():
            avg = sum(scores) / len(scores) if scores else 0.0
            if o in positive:
                positive_scores.extend(scores)
                patterns.append(f"Positive outcomes ({o}) avg match score: {avg:.0f}")
            else:
                negative_scores.extend(scores)

        if positive_scores and negative_scores:
            avg_pos = sum(positive_scores) / len(positive_scores)
            avg_neg = sum(negative_scores) / len(negative_scores)
            if avg_pos > avg_neg:
                patterns.append(
                    f"Higher-scoring applications ({avg_pos:.0f}) get better outcomes "
                    f"than lower ({avg_neg:.0f})"
                )

        recs: List[str] = []
        total = len(rows)
        ghosted = outcomes.get("ghosted", 0) + outcomes.get("no_response", 0)
        if ghosted > total * 0.5:
            recs.append("Over 50% ghosted — try following up 5-7 days after applying.")
        rejected = outcomes.get("rejected", 0)
        if rejected > total * 0.4:
            recs.append("High rejection rate — review resume keywords and tailor more.")
        if outcomes.get("interview", 0) > 0 and outcomes.get("offer", 0) == 0:
            recs.append("Getting interviews but no offers — focus on interview prep.")
        if not recs:
            recs.append("Keep tracking outcomes to build actionable insights.")

        return {
            "total_applications": total,
            "outcome_distribution": outcomes,
            "success_patterns": patterns,
            "recommendations": recs,
        }

    # ──────────────────────────────────────────────
    # New public API — trajectory, gap, fit, recs, insights
    # ──────────────────────────────────────────────

    def analyze_trajectory(self, user_id: int) -> Dict[str, Any]:
        """Analyze career progression with phase detection and pivot points.

        Uses deep profile, journey events, project history, and skills graph
        to produce a detailed career arc analysis.

        Returns dict with career_phases, growth_rate, trajectory_direction,
        pivot_points, and tenure_analysis.
        """
        context = self._build_career_context(user_id)
        profile = context["profile"]
        journey_events = context["journey_events"]
        projects = context["projects"]

        # Local phase extraction (no LLM needed)
        phases = self._extract_career_phases(profile, projects, journey_events)

        profile_text = context["profile_text"]
        journey_text = context["journey_text"]
        phases_text = context["phases_text"]

        prompt = f"""Analyze this professional's career trajectory in detail.

Return ONLY a JSON object:
{{
  "trajectory_direction": "<upward | lateral | pivoting | accelerating | consolidating>",
  "growth_rate": "<rapid | steady | gradual | stalled>",
  "career_arc_summary": "<3-4 sentence narrative of the overall career arc>",
  "pivot_points": [
    {{"event": "<what changed>", "impact": "<how it shifted the career>",
      "timing": "<when approximately>"}}
  ],
  "tenure_analysis": {{
    "avg_tenure_years": <estimated average years per role>,
    "pattern": "<long tenures | moderate | job-hopper | mixed>",
    "insight": "<what the tenure pattern suggests>"
  }},
  "seniority_progression": {{
    "current_level": "<IC | Lead | Manager | Director | VP | C-level>",
    "trajectory": "<ascending | plateaued | broadening>",
    "next_natural_step": "<likely next career level>"
  }}
}}

Professional profile:
{profile_text}{journey_text}{phases_text}"""

        result, duration = self._timed(
            self._call_llm_json, prompt, task_type="career_planning", max_tokens=2048
        )

        self._log_run(
            user_id,
            "Trajectory analysis",
            {},
            result or {},
            task_type="career_planning",
            duration_ms=duration,
        )

        # Merge local phase data with LLM analysis
        output: Dict[str, Any] = result or {}
        output["career_phases"] = phases
        if not result:
            output["error"] = "LLM unavailable — showing local phase data only"
        else:
            self._save_analysis(user_id, "trajectory_analysis", output)

        return output

    def analyze_skills_gap(
        self,
        user_id: int,
        target_role: Optional[str] = None,
        target_posting_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Compare current skills against target role or specific job posting.

        Args:
            user_id: User identifier.
            target_role: Free-text target role title (e.g. "Staff Engineer").
            target_posting_id: Specific job_postings.id to compare against.

        Returns dict with gaps categorized by priority (critical, important,
        nice_to_have), matched_skills, recommended_learning, and time_estimate.
        """
        context = self._build_career_context(user_id)
        profile_text = context["profile_text"]
        portfolio = context["skills_portfolio"]

        # If a posting is specified, load its description + requirements
        posting_text = ""
        posting_title = target_role or ""
        if target_posting_id:
            with get_db() as conn:
                row = conn.execute(
                    "SELECT title, company, description, skills_missing, skills_overlap "
                    "FROM job_postings WHERE id = ?",
                    (target_posting_id,),
                ).fetchone()
            if row:
                posting_title = row["title"] or posting_title
                desc = row["description"] or ""
                posting_text = (
                    f"\n\nTarget job posting ({row['title']} at {row['company']}):\n{desc[:2000]}"
                )
                # Include existing analysis
                try:
                    existing_missing = json.loads(row["skills_missing"] or "[]")
                    existing_overlap = json.loads(row["skills_overlap"] or "[]")
                    if existing_missing or existing_overlap:
                        posting_text += (
                            f"\n\nPrevious NLP analysis — missing: {', '.join(existing_missing[:15])}"  # noqa: E501
                            f" | overlapping: {', '.join(existing_overlap[:15])}"
                        )
                except (json.JSONDecodeError, TypeError):
                    pass

        if not target_role and not target_posting_id:
            target_role = "next logical career step"

        portfolio_text = ""
        if portfolio:
            sections: List[str] = []
            for cat, skills in portfolio.items():
                if skills:
                    sections.append(f"  {cat}: {', '.join(skills[:15])}")
            if sections:
                portfolio_text = "\n\nCurrent skills portfolio:\n" + "\n".join(sections)

        prompt = f"""Perform a skills gap analysis comparing this professional's current
skills against the target role/position requirements.

Return ONLY a JSON object:
{{
  "target": "{posting_title or target_role}",
  "overall_readiness": <0-100>,
  "matched_skills": [
    {{"skill": "<skill>", "proficiency": "<expert|proficient|familiar>",
      "evidence": "<where demonstrated>"}}
  ],
  "gaps": {{
    "critical": [
      {{"skill": "<must-have skill>", "learning_path": "<how to acquire>",
        "time_estimate_weeks": <weeks>}}
    ],
    "important": [
      {{"skill": "<strongly preferred skill>", "learning_path": "<how to acquire>",
        "time_estimate_weeks": <weeks>}}
    ],
    "nice_to_have": [
      {{"skill": "<bonus skill>", "learning_path": "<how to acquire>",
        "time_estimate_weeks": <weeks>}}
    ]
  }},
  "total_gap_weeks": <estimated total weeks to close all critical + important gaps>,
  "quick_wins": ["<skills that can be demonstrated quickly>", ...up to 3]
}}

Target: {posting_title or target_role}

Professional profile:
{profile_text}{portfolio_text}{posting_text}"""

        result, duration = self._timed(
            self._call_llm_json, prompt, task_type="career_planning", max_tokens=2048
        )

        self._log_run(
            user_id,
            f"Skills gap: {posting_title or target_role}",
            {"target_role": target_role, "posting_id": target_posting_id},
            result or {},
            task_type="career_planning",
            duration_ms=duration,
        )

        if result:
            self._save_analysis(
                user_id,
                "skills_gap",
                result,
                target_role=posting_title or target_role or "",
            )
        return result or {"error": "Unable to analyze skills gap — LLM unavailable"}
