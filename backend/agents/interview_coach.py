"""Interview Coach Agent — mock interviews with per-answer scoring via RTX 5090."""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseCareerAgent
from agents.interview_coach_content import _InterviewCoachContentMixin
from agents.interview_coach_db import _InterviewCoachDBMixin
from agents.interview_coach_helpers import _InterviewCoachHelpersMixin
from agents.interview_coach_session import _InterviewCoachSessionMixin
from models import get_db

logger = logging.getLogger(__name__)

COACH_STAGES = ["prep", "mock_questions", "feedback", "complete"]

INTERVIEW_TYPES: Dict[str, str] = {
    "behavioral": "Past behavior, teamwork, conflict resolution, leadership examples using STAR method",  # noqa: E501
    "technical": "Technical knowledge, system design, coding concepts, architecture decisions",
    "situational": "Hypothetical scenarios, problem-solving approach, decision-making under pressure",  # noqa: E501
    "case_study": "Business case analysis, strategic thinking, data-driven recommendations",
    "panel": "Mixed questions from multiple perspectives — technical, managerial, and cultural",
}

PERSONAS: Dict[str, Dict[str, str]] = {
    "hiring_manager": {
        "name": "Hiring Manager",
        "focus": "Impact, leadership, team dynamics, cultural fit",
    },
    "technical": {
        "name": "Technical Interviewer",
        "focus": "Technical depth, problem-solving, system design",
    },
    "hr_recruiter": {
        "name": "HR Recruiter",
        "focus": "Culture fit, communication, career trajectory",
    },
    "executive": {
        "name": "Executive/VP",
        "focus": "Strategic thinking, business impact, vision alignment",
    },
}


class InterviewCoachAgent(
    _InterviewCoachSessionMixin,
    _InterviewCoachContentMixin,
    _InterviewCoachHelpersMixin,
    _InterviewCoachDBMixin,
    BaseCareerAgent,
):  # noqa: E501
    """Mock interview agent with STAR evaluation, question prediction, and talking points."""

    agent_type = "interview_coach"

    # Navigation — method locations:
    #   interview_coach.py         start_session, start_mock_interview, continue_interview,
    #                              end_interview
    #   interview_coach_session.py evaluate_response
    #   interview_coach_content.py generate_talking_points, predict_questions, get_session,
    #                              get_sessions, list_sessions, get_session_detail,
    #                              get_assessment, generate_prep_sheet
    #   interview_coach_helpers.py _generate_interviewer_persona, _generate_opening,
    #                              _score_answer, _evaluate_star, _generate_question,
    #                              _overall_assessment
    #   interview_coach_db.py      _get_session_row, _save_message, _get_last_question,
    #                              _get_posting, _fallback_questions
    #   base_agent.py              _call_llm, _log_run, _get_user_profile, _profile_summary,
    #                              _record_claim, _get_arango_context

    # ──────────────────────────────────────────────
    # Public API — Mock Interview Sessions
    # ──────────────────────────────────────────────

    def start_session(
        self,
        user_id: int,
        posting_id: str = "",
        persona: str = "hiring_manager",
        question_count: int = 5,
    ) -> Dict[str, Any]:
        """Start a new mock interview session."""
        session_id = str(uuid.uuid4())
        persona_info = PERSONAS.get(persona, PERSONAS["hiring_manager"])

        posting = self._get_posting(posting_id) if posting_id else None
        profile = self._get_user_profile(user_id)
        profile_text = self._profile_summary(profile)

        arango_ctx = self._get_arango_context(user_id, self.agent_type)
        if arango_ctx:
            profile_text = f"{profile_text}\n\n<arango_context>\n{arango_ctx}\n</arango_context>"

        context: Dict[str, Any] = {
            "persona": persona,
            "persona_name": persona_info["name"],
            "persona_focus": persona_info["focus"],
            "posting_title": posting.get("title", "") if posting else "",
            "posting_company": posting.get("company", "") if posting else "",
            "posting_description": posting.get("description", "")[:2000] if posting else "",
            "profile_summary": profile_text[:1500],
        }

        opening, first_question = self._generate_opening(context)

        with get_db() as conn:
            conn.execute(
                "INSERT INTO interview_coach_sessions "
                "(id, user_id, posting_id, stage, persona, question_count, current_question, "
                "context_json, scores_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id, user_id, posting_id, "mock_questions", persona,
                    question_count, 1, json.dumps(context), "[]",
                ),
            )
            conn.commit()

        self._save_message(session_id, "assistant", opening, question_index=0)
        self._save_message(session_id, "assistant", first_question, question_index=1)

        self._log_run(
            user_id, f"Interview coach: {persona_info['name']}",
            {"posting_id": posting_id, "persona": persona},
            {"session_id": session_id}, task_type="reasoning",
        )

        posting_desc = context.get("posting_description", "")
        self._record_claim(
            user_id, "interview_coach", posting_desc[:500],
            f"{opening} {first_question}"[:500],
            metadata={"session_id": session_id, "persona": persona},
        )

        return {
            "session_id": session_id, "message": opening, "question": first_question,
            "persona": persona_info["name"], "question_count": question_count,
            "current_question": 1,
        }

    def start_mock_interview(
        self,
        user_id: int,
        posting_id: str = "",
        interview_type: str = "behavioral",
    ) -> Dict[str, Any]:
        """Start a mock interview with a dynamically generated interviewer persona."""
        if interview_type not in INTERVIEW_TYPES:
            interview_type = "behavioral"

        posting = self._get_posting(posting_id) if posting_id else None
        profile = self._get_user_profile(user_id)
        profile_text = self._profile_summary(profile)

        job_text = posting.get("description", "")[:2000] if posting else ""
        title = posting.get("title", "") if posting else ""
        company = posting.get("company", "") if posting else ""

        persona_info = self._generate_interviewer_persona(job_text, interview_type)

        context: Dict[str, Any] = {
            "persona": interview_type,
            "persona_name": persona_info.get("name", "Interviewer"),
            "persona_focus": persona_info.get("focus", INTERVIEW_TYPES[interview_type]),
            "interview_type": interview_type,
            "posting_title": title,
            "posting_company": company,
            "posting_description": job_text,
            "profile_summary": profile_text[:1500],
        }

        opening, first_question = self._generate_opening(context)

        session_id = str(uuid.uuid4())
        question_count = 5

        with get_db() as conn:
            conn.execute(
                "INSERT INTO interview_coach_sessions "
                "(id, user_id, posting_id, stage, persona, question_count, current_question, "
                "context_json, scores_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id, user_id, posting_id, "mock_questions", interview_type,
                    question_count, 1, json.dumps(context), "[]",
                ),
            )
            conn.commit()

        self._save_message(session_id, "assistant", opening, question_index=0)
        self._save_message(session_id, "assistant", first_question, question_index=1)

        self._log_run(
            user_id, f"Mock interview ({interview_type}): {persona_info.get('name', '')}",
            {"posting_id": posting_id, "interview_type": interview_type},
            {"session_id": session_id}, task_type="reasoning",
        )

        return {
            "session_id": session_id, "message": opening, "question": first_question,
            "persona": persona_info.get("name", "Interviewer"),
            "interview_type": interview_type, "question_count": question_count,
            "current_question": 1,
        }

    def continue_interview(
        self, session_id: str, user_response: str, user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Evaluate the user's response and return feedback plus the next question."""
        return self.process_answer(session_id, user_response, user_id=user_id)

    def end_interview(self, session_id: str, user_id: Optional[int] = None) -> Dict[str, Any]:
        """End an interview session early and generate summary scores."""
        session = self._get_session_row(session_id, user_id=user_id)
        if not session:
            return {"error": "Session not found"}

        if session["is_complete"]:
            return {"error": "Session already complete"}

        context = json.loads(session["context_json"] or "{}")
        scores = json.loads(session["scores_json"] or "[]")

        assessment = self._overall_assessment(scores, context)

        # CT-9 L6: Capture effectiveness before DB write (durability)
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

        summary_text = assessment.get("recommendation", "Interview ended early.")
        self._save_message(session_id, "assistant", summary_text, question_index=-1)

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

        return {
            "overall_score": assessment.get("overall_score", 0),
            "strengths": assessment.get("strengths", []),
            "improvements": assessment.get("improvements", []),
            "recommendation": assessment.get("recommendation", ""),
            "questions_answered": session["current_question"],
            "total_questions": session["question_count"],
        }
