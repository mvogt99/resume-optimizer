"""_InterviewCoachSessionMixin — process_answer and evaluate_response for InterviewCoachAgent."""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class _InterviewCoachSessionMixin:
    """Handles answer processing and standalone evaluation."""

    def process_answer(
        self, session_id: str, answer: str, user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Score the answer and return feedback + next question or assessment."""
        from models import get_db

        session = self._get_session_row(session_id, user_id=user_id)
        if not session:
            return {"error": "Session not found"}

        if session["is_complete"]:
            return {"error": "Session already complete"}

        context = json.loads(session["context_json"] or "{}")
        scores: List[Dict[str, Any]] = json.loads(session["scores_json"] or "[]")
        current_q: int = session["current_question"]
        total_q: int = session["question_count"]

        last_question = self._get_last_question(session_id, current_q)
        self._save_message(session_id, "user", answer, question_index=current_q)

        score_result, duration = self._timed(self._score_answer, last_question, answer, context)

        if not score_result:
            score_result = {
                "expertise": 5, "communication": 5, "relevance": 5, "star_quality": 5,
                "feedback": "Unable to score.", "improved_answer": "",
            }

        self._save_message(
            session_id, "system", json.dumps(score_result),
            question_index=current_q, score_json=json.dumps(score_result),
        )
        scores.append(score_result)

        try:
            from agents.interview_effectiveness import get_or_create_tracker

            answer_score = score_result.get("expertise", 5)
            get_or_create_tracker(session_id).record_answer_score(answer_score)
        except Exception as _e:
            logger.debug("[CT-9] Effectiveness tracking failed (non-blocking): %s", _e)

        if current_q >= total_q:
            assessment = self._overall_assessment(scores, context)

            # CT-9 L6: Capture effectiveness before DB write so it's persisted (durability)
            ef_result: dict = {}
            try:
                from agents.interview_effectiveness import get_or_create_tracker

                ef_result = get_or_create_tracker(session_id).complete_session()
                if ef_result.get("pf_action") != "none":
                    assessment = dict(assessment or {})
                    assessment["coaching_effectiveness"] = ef_result.get("effectiveness")
                    assessment["coaching_action"] = ef_result.get("pf_action")
                    assessment["coaching_message"] = ef_result.get("message", "")
            except Exception as _e:
                logger.debug("[CT-9] Effectiveness capture failed (non-blocking): %s", _e)

            with get_db() as conn:
                conn.execute(
                    "UPDATE interview_coach_sessions SET stage = 'complete', is_complete = 1, "
                    "scores_json = ?, overall_assessment_json = ?, "
                    "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (json.dumps(scores), json.dumps(assessment or {}), session_id),
                )
                conn.commit()

            # CT-9 L6: Fire-and-forget PF note (non-blocking)
            try:
                if ef_result.get("pf_action") != "none":
                    from personaforge_client import CAREER_NAMESPACE, pf_remember

                    pf_remember(
                        CAREER_NAMESPACE,
                        ef_result.get("message", ""),
                        metadata={"session_id": session_id, "action": ef_result.get("pf_action")},
                    )
            except Exception as _e:
                logger.debug("[CT-9] PF note failed (non-blocking): %s", _e)

            self._save_message(
                session_id, "assistant",
                f"Interview complete! {assessment.get('recommendation', '')}",
                question_index=current_q,
            )

            uid = user_id or session.get("user_id", "")
            self._record_claim(
                uid, "interview_coach", answer[:500],
                assessment.get("recommendation", "")[:500],
                metadata={
                    "session_id": session_id,
                    "final_score": assessment.get("overall_score", 0),
                    "questions_answered": current_q,
                },
            )

            return {
                "score": score_result, "is_complete": True, "assessment": assessment,
                "current_question": current_q, "total_questions": total_q,
            }
        else:
            next_q = current_q + 1
            next_question = self._generate_question(context, next_q, scores)

            with get_db() as conn:
                conn.execute(
                    "UPDATE interview_coach_sessions SET current_question = ?, "
                    "scores_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (next_q, json.dumps(scores), session_id),
                )
                conn.commit()

            self._save_message(session_id, "assistant", next_question, question_index=next_q)

            return {
                "score": score_result,
                "feedback": score_result.get("feedback", ""),
                "improved_answer": score_result.get("improved_answer", ""),
                "next_question": next_question,
                "is_complete": False,
                "current_question": next_q,
                "total_questions": total_q,
            }

    def evaluate_response(
        self,
        question: str,
        response: str,
        job_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Evaluate a single interview response using the STAR method."""
        title = (job_context or {}).get("title", "")
        company = (job_context or {}).get("company", "")
        description = (job_context or {}).get("description", "")[:1000]

        role_context = ""
        if title or company:
            role_context = f"\nRole: {title} at {company}"
        if description:
            role_context += f"\nJob description excerpt: {description}"

        prompt = (
            "Evaluate this interview response using the STAR method "
            "(Situation, Task, Action, Result).\n\n"
            "Return ONLY a JSON object:\n"
            "{\n"
            '  "score": <0-100 overall score>,\n'
            '  "star_breakdown": {\n'
            '    "situation": <0-25 score for setting the context>,\n'
            '    "task": <0-25 score for explaining the challenge>,\n'
            '    "action": <0-25 score for describing what was done>,\n'
            '    "result": <0-25 score for quantifying the outcome>\n'
            "  },\n"
            '  "completeness": <0-10 STAR coverage>,\n'
            '  "relevance": <0-10 relevance to the question>,\n'
            '  "specificity": <0-10 use of concrete details and metrics>,\n'
            '  "impact_quantification": <0-10 quantified business impact>,\n'
            '  "feedback": "<2-3 sentences of constructive feedback>",\n'
            '  "suggestions": ["<suggestion 1>", "<suggestion 2>", "<suggestion 3>"]\n'
            "}\n\n"
            f"Question: {question}\n\n"
            f"Response: {response}"
            f"{role_context}"
        )

        result = self._call_llm_json(prompt, task_type="reasoning", max_tokens=1024)

        if result and isinstance(result, dict) and "score" in result:
            return result

        word_count = len(response.split())
        has_numbers = any(c.isdigit() for c in response)
        score = min(100, max(10, word_count // 2 + (20 if has_numbers else 0)))

        return {
            "score": score,
            "star_breakdown": {
                "situation": score // 4, "task": score // 4,
                "action": score // 4, "result": score // 4,
            },
            "completeness": min(10, word_count // 20),
            "relevance": 5,
            "specificity": 5 if has_numbers else 3,
            "impact_quantification": 5 if has_numbers else 2,
            "feedback": "LLM evaluation unavailable. Practice structuring your answer "
            "with a clear Situation, Task, Action, and Result.",
            "suggestions": [
                "Start with the specific situation and context",
                "Describe your personal actions, not the team's",
                "End with quantified results and business impact",
            ],
        }
