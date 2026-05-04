"""Interview Coach Helpers — LLM-based generation helpers."""

# Module contents:
# _generate_interviewer_persona()  — generates persona traits from job text and interview type
# _generate_opening()              — generates opening statement and first question
# _score_answer()                  — scores candidate answer on 5 dimensions (STAR, clarity, etc.)
# _evaluate_star()                 — evaluates STAR method structure in an answer
# _generate_question()             — generates next follow-up question from context
# _overall_assessment()            — computes session final assessment from accumulated scores

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

INTERVIEW_TYPES: Dict[str, str] = {
    "behavioral": "Past behavior, teamwork, conflict resolution, leadership examples using STAR method",  # noqa: E501
    "technical": "Technical knowledge, system design, coding concepts, architecture decisions",
    "situational": "Hypothetical scenarios, problem-solving approach, decision-making under pressure",  # noqa: E501
    "case_study": "Business case analysis, strategic thinking, data-driven recommendations",
    "panel": "Mixed questions from multiple perspectives — technical, managerial, and cultural",
}


class _InterviewCoachHelpersMixin:
    # ──────────────────────────────────────────────
    # LLM Methods — Persona & Question Generation
    # ──────────────────────────────────────────────

    def _generate_interviewer_persona(self, job_text: str, interview_type: str) -> Dict[str, str]:
        """Generate a role-specific interviewer persona via LLM.

        Args:
            job_text: Job description text for context.
            interview_type: Type of interview (behavioral, technical, etc.).

        Returns:
            Dict with ``name``, ``role``, ``focus``, and ``style`` keys.
        """
        type_desc = INTERVIEW_TYPES.get(interview_type, INTERVIEW_TYPES["behavioral"])

        prompt = (
            "Generate an interviewer persona for a mock interview.\n\n"
            "Return ONLY a JSON object:\n"
            "{\n"
            '  "name": "<realistic interviewer name and title, e.g. Sarah Chen, VP of Engineering>",\n'  # noqa: E501
            '  "role": "<their role at the company>",\n'
            '  "focus": "<what they evaluate: 2-3 focus areas>",\n'
            '  "style": "<interviewing style: direct/conversational/probing/collaborative>"\n'
            "}\n\n"
            f"Interview type: {interview_type} ({type_desc})\n"
            f"Job context: {job_text[:800] if job_text else 'General position'}"
        )

        result = self._call_llm_json(prompt, task_type="reasoning", max_tokens=512)

        if result and isinstance(result, dict) and "name" in result:
            return result

        # Fallback personas by interview type
        fallbacks: Dict[str, Dict[str, str]] = {
            "behavioral": {
                "name": "Hiring Manager",
                "role": "Hiring Manager",
                "focus": type_desc,
                "style": "conversational",
            },
            "technical": {
                "name": "Technical Lead",
                "role": "Senior Engineer",
                "focus": type_desc,
                "style": "probing",
            },
            "situational": {
                "name": "Team Lead",
                "role": "Team Lead",
                "focus": type_desc,
                "style": "direct",
            },
            "case_study": {
                "name": "Director of Strategy",
                "role": "Director",
                "focus": type_desc,
                "style": "collaborative",
            },
            "panel": {
                "name": "Interview Panel",
                "role": "Cross-functional panel",
                "focus": type_desc,
                "style": "mixed",
            },
        }
        return fallbacks.get(interview_type, fallbacks["behavioral"])

    def _generate_opening(self, context: Dict[str, Any]) -> tuple:
        """Generate opening message and first question.

        Args:
            context: Session context dict with persona and posting info.

        Returns:
            Tuple of (opening_message, first_question).
        """
        persona_name = context.get("persona_name", "Hiring Manager")
        title = context.get("posting_title", "this role")
        company = context.get("posting_company", "our company")

        prompt = f"""You are a {persona_name} conducting a mock interview.
Focus area: {context.get('persona_focus', '')}

Generate an opening message and the first interview question.

Return ONLY a JSON object:
{{
  "opening": "<friendly 2-sentence introduction as the interviewer persona>",
  "first_question": "<first interview question appropriate for {persona_name}>"
}}

Role: {title}
Company: {company}
Job description excerpt: {context.get('posting_description', 'General position')[:1000]}

Candidate profile:
{context.get('profile_summary', 'No profile available')}"""

        result = self._call_llm_json(prompt, task_type="reasoning", max_tokens=1024)

        if result and isinstance(result, dict):
            opening = result.get(
                "opening", f"Hello! I'm your {persona_name} for this mock interview."
            )
            question = result.get("first_question", "Tell me about yourself and your background.")
            return opening, question

        return (
            f"Hello! I'm your {persona_name} for today's mock "
            f"interview about the {title} position at "
            f"{company}. Let's get started!",
            "Tell me about yourself and why you're interested in this role.",
        )

    def _score_answer(
        self, question: str, answer: str, context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Score an interview answer on 4 dimensions.

        Args:
            question: The question that was asked.
            answer: The candidate's response.
            context: Session context with persona and role info.

        Returns:
            Dict with ``expertise``, ``communication``, ``relevance``,
            ``star_quality`` (each 0-10), ``feedback``, and ``improved_answer``.
            Returns None if LLM call fails.
        """
        persona = context.get("persona_name", "Hiring Manager")
        prompt = f"""Score this interview answer. You are a {persona}.

Scoring guidance:
- 8-10: Excellent — clear, specific, quantified results, well-structured
- 6-7: Good — solid answer with concrete details, minor gaps
- 4-5: Adequate — relevant but vague or missing key elements
- 1-3: Weak — off-topic, no specifics, or incomplete
- For star_quality: award 6+ if answer contains situation context, actions taken,
  and results, even if not explicitly labeled as STAR format

Return ONLY a JSON object:
{{
  "expertise": <0-10 score for domain expertise demonstrated>,
  "communication": <0-10 score for clarity and articulation>,
  "relevance": <0-10 score for relevance to the question>,
  "star_quality": <0-10 score for STAR method usage (Situation, Task, Action, Result)>,
  "feedback": "<2-3 sentences of constructive feedback>",
  "improved_answer": "<a stronger version of the answer in 3-4 sentences>"
}}

Question: {question}

Candidate's answer: {answer}

Role context: {context.get('posting_title', '')} at {context.get('posting_company', '')}"""

        return self._call_llm_json(prompt, task_type="reasoning", max_tokens=1024)

    def _evaluate_star(self, question: str, response: str) -> Dict[str, Any]:
        """Evaluate a response for STAR method completeness via LLM.

        Args:
            question: The interview question.
            response: The candidate's answer.

        Returns:
            Dict with STAR component scores and feedback.
        """
        return self.evaluate_response(question, response)

    def _generate_question(
        self,
        context: Dict[str, Any],
        question_idx: int,
        previous_scores: List[Dict[str, Any]],
    ) -> str:
        """Generate the next interview question based on context and previous performance.

        Adapts question focus based on weak areas detected in previous scores.

        Args:
            context: Session context with persona and posting info.
            question_idx: 1-based index of the question being generated.
            previous_scores: List of score dicts from prior questions.

        Returns:
            Question text string.
        """
        weak_areas: List[str] = []
        for s in previous_scores:
            if isinstance(s, dict):
                if s.get("star_quality", 10) < 5:
                    weak_areas.append("STAR method")
                if s.get("expertise", 10) < 5:
                    weak_areas.append("technical depth")
                if s.get("communication", 10) < 5:
                    weak_areas.append("communication")

        focus_hint = ""
        if weak_areas:
            focus_hint = f"\nFocus on probing: {', '.join(set(weak_areas))}"

        persona = context.get("persona_name", "Hiring Manager")
        interview_type = context.get("interview_type", "")
        type_hint = ""
        if interview_type and interview_type in INTERVIEW_TYPES:
            type_hint = f"\nInterview type: {interview_type} ({INTERVIEW_TYPES[interview_type]})"

        prompt = f"""Generate interview question #{question_idx} as a {persona}.
Focus area: {context.get('persona_focus', '')}
{focus_hint}{type_hint}

Return ONLY the question text, no JSON, no explanation.

Role: {context.get('posting_title', '')} at {context.get('posting_company', '')}
Job description excerpt: {context.get('posting_description', '')[:800]}"""

        result = self._call_llm(prompt, task_type="reasoning", max_tokens=256)
        if result:
            return result.strip().strip('"')
        return "Can you describe a challenging project you've worked on recently?"

    def _overall_assessment(
        self,
        scores: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate overall assessment from all per-question scores.

        Args:
            scores: List of per-question score dicts.
            context: Session context with persona and role info.

        Returns:
            Dict with ``overall_score`` (0-100), ``strengths``, ``improvements``,
            and ``recommendation``.
        """
        if not scores:
            return {"overall_score": 0, "strengths": [], "improvements": [], "recommendation": ""}

        scores_text = "\n".join(
            f"Q{i + 1}: expertise={s.get('expertise', 0)}, "
            f"communication={s.get('communication', 0)}, "
            f"relevance={s.get('relevance', 0)}, "
            f"star_quality={s.get('star_quality', 0)}"
            for i, s in enumerate(scores)
            if isinstance(s, dict)
        )

        prompt = f"""Assess this candidate's overall mock interview performance.

Return ONLY a JSON object:
{{
  "overall_score": <0-100 overall readiness score>,
  "strengths": ["<strength 1>", "<strength 2>", "<strength 3>"],
  "improvements": ["<improvement 1>", "<improvement 2>", "<improvement 3>"],
  "recommendation": "<one paragraph summary recommendation>"
}}

Interview persona: {context.get('persona_name', '')}
Role: {context.get('posting_title', '')} at {context.get('posting_company', '')}

Per-question scores:
{scores_text}"""

        result = self._call_llm_json(prompt, task_type="reasoning", max_tokens=1024)
        if result and isinstance(result, dict):
            return result

        # Fallback: compute from raw scores
        all_scores: List[float] = []
        for s in scores:
            if isinstance(s, dict):
                avg = (
                    s.get("expertise", 0)
                    + s.get("communication", 0)
                    + s.get("relevance", 0)
                    + s.get("star_quality", 0)
                ) / 4
                all_scores.append(avg)
        overall = int(sum(all_scores) / max(len(all_scores), 1) * 10)
        return {
            "overall_score": overall,
            "strengths": ["Completed all questions"],
            "improvements": ["Practice STAR method for behavioral questions"],
            "recommendation": f"Overall score: {overall}/100. Keep practicing!",
        }
