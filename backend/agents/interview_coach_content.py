"""Interview Coach Content — talking points, question prediction, and prep sheets."""

# Module contents:
# generate_talking_points()  — generates position-specific talking points from profile + JD
# predict_questions()        — predicts likely interview questions for a posting
# get_session()              — retrieves session row with messages
# get_sessions()             — lists sessions for a user, optionally filtered by posting
# list_sessions()            — lists all sessions for a user
# get_session_detail()       — retrieves full session detail with messages and scores
# get_assessment()           — retrieves final assessment for a completed session
# generate_prep_sheet()      — generates comprehensive interview prep sheet

import contextlib
import json
import logging
from typing import Any, Dict, List, Optional

from models import get_db

logger = logging.getLogger(__name__)


class _InterviewCoachContentMixin:
    # ──────────────────────────────────────────────
    # Public API — Talking Points & Question Prediction
    # ──────────────────────────────────────────────

    def generate_talking_points(self, user_id: int, posting_id: str) -> Dict[str, Any]:
        """Generate structured talking points for a specific role.

        Analyzes the user's resume, profile, and deep profile against the job
        posting to produce organized talking points.

        Args:
            user_id: User to generate talking points for.
            posting_id: Job posting to target.

        Returns:
            Dict with ``posting_id``, ``title``, ``company``, and organized
            talking points under ``strengths_to_emphasize``, ``gaps_to_address``,
            ``stories_to_tell``, and ``key_messages``.
        """
        posting = self._get_posting(posting_id, user_id=user_id)
        if not posting:
            return {"error": "Posting not found"}

        profile = self._get_user_profile(user_id)
        profile_text = self._profile_summary(profile)

        jd = posting.get("description", "")
        title = posting.get("title", "Unknown Role")
        company = posting.get("company", "Unknown Company")

        prompt = (
            "Generate interview talking points for a candidate preparing for an interview.\n\n"
            "Return ONLY a JSON object:\n"
            "{\n"
            '  "strengths_to_emphasize": [\n'
            '    {"point": "<talking point>", "evidence": "<supporting evidence from profile>"}\n'
            "  ],\n"
            '  "gaps_to_address": [\n'
            '    {"gap": "<skill gap>", "mitigation": "<how to address it in the interview>"}\n'
            "  ],\n"
            '  "stories_to_tell": [\n'
            '    {"theme": "<story theme>", "situation": "<brief STAR setup>", '
            '"why_relevant": "<why this story matters for this role>"}\n'
            "  ],\n"
            '  "key_messages": ["<core message 1>", "<core message 2>", "<core message 3>"]\n'
            "}\n\n"
            f"Role: {title} at {company}\n"
            f"Job Description:\n{jd[:1500]}\n\n"
            f"Candidate Profile:\n{profile_text[:1500]}"
        )

        result, duration = self._timed(self._call_llm_json, prompt, "reasoning", 2048)

        if not result or not isinstance(result, dict):
            result = {
                "strengths_to_emphasize": [],
                "gaps_to_address": [],
                "stories_to_tell": [],
                "key_messages": [
                    f"Express genuine interest in {company}'s mission",
                    f"Highlight relevant experience for {title}",
                    "Demonstrate growth mindset and willingness to learn",
                ],
            }

        self._log_run(
            user_id,
            f"Talking points: {title}",
            {"posting_id": posting_id},
            {"keys": list(result.keys())},
            task_type="reasoning",
            duration_ms=duration,
        )

        return {
            "posting_id": posting_id,
            "title": title,
            "company": company,
            **result,
        }

    def predict_questions(self, user_id: int, posting_id: str, count: int = 10) -> Dict[str, Any]:
        """Predict likely interview questions for a specific role.

        Generates questions across categories (behavioral, technical, role-specific,
        company-specific), each with a suggested approach and STAR response outline.

        Args:
            user_id: User to predict questions for.
            posting_id: Job posting to analyze.
            count: Number of questions to generate (1-20).

        Returns:
            Dict with ``posting_id``, ``title``, ``company``, and ``questions`` list.
            Each question has ``text``, ``category``, ``difficulty``,
            ``suggested_approach``, and ``star_outline``.
        """
        count = max(1, min(count, 20))

        posting = self._get_posting(posting_id, user_id=user_id)
        if not posting:
            return {"error": "Posting not found"}

        profile = self._get_user_profile(user_id)
        profile_text = self._profile_summary(profile)

        jd = posting.get("description", "")
        title = posting.get("title", "Unknown Role")
        company = posting.get("company", "Unknown Company")

        prompt = (
            f"Predict the {count} most likely interview questions for this role.\n\n"
            "Return ONLY a JSON object:\n"
            "{\n"
            '  "questions": [\n'
            "    {\n"
            '      "text": "<the interview question>",\n'
            '      "category": "behavioral|technical|role_specific|company_specific",\n'
            '      "difficulty": "easy|medium|hard",\n'
            '      "suggested_approach": "<1-2 sentences on how to approach this>",\n'
            '      "star_outline": {\n'
            '        "situation": "<what context to set>",\n'
            '        "task": "<what challenge to describe>",\n'
            '        "action": "<what actions to highlight>",\n'
            '        "result": "<what outcomes to quantify>"\n'
            "      }\n"
            "    }\n"
            "  ]\n"
            "}\n\n"
            f"Role: {title} at {company}\n"
            f"Job Description:\n{jd[:1500]}\n\n"
            f"Candidate Profile (for personalized approaches):\n{profile_text[:1000]}"
        )

        result, duration = self._timed(self._call_llm_json, prompt, "reasoning", 4096)

        questions: List[Dict[str, Any]] = []
        if result and isinstance(result, dict):
            questions = result.get("questions", [])
        if not questions:
            questions = self._fallback_questions(title, count)

        self._log_run(
            user_id,
            f"Predict questions: {title}",
            {"posting_id": posting_id, "count": count},
            {"question_count": len(questions)},
            task_type="reasoning",
            duration_ms=duration,
        )

        return {
            "posting_id": posting_id,
            "title": title,
            "company": company,
            "questions": questions[:count],
        }

    # ──────────────────────────────────────────────
    # Public API — Session History
    # ──────────────────────────────────────────────

    def get_session(
        self, session_id: str, user_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Get session with messages and scores.

        Args:
            session_id: Session to retrieve.
            user_id: Optional ownership filter.

        Returns:
            Session dict with parsed JSON fields and ``messages`` list, or None.
        """
        session = self._get_session_row(session_id, user_id=user_id)
        if not session:
            return None

        with get_db() as conn:
            messages = conn.execute(
                "SELECT * FROM interview_coach_messages WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            ).fetchall()

        msg_list: List[Dict[str, Any]] = []
        for m in messages:
            d = dict(m)
            for key in ("score_json",):
                if isinstance(d.get(key), str):
                    with contextlib.suppress(json.JSONDecodeError, TypeError):
                        d[key] = json.loads(d[key])
            msg_list.append(d)

        result = dict(session)
        for key in ("context_json", "scores_json", "overall_assessment_json"):
            if isinstance(result.get(key), str):
                with contextlib.suppress(json.JSONDecodeError, TypeError):
                    result[key] = json.loads(result[key])
        result["messages"] = msg_list
        return result

    def get_sessions(self, user_id: int, posting_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List past mock interview sessions, optionally filtered by posting.

        Args:
            user_id: User whose sessions to list.
            posting_id: Optional posting ID filter.

        Returns:
            List of session summary dicts, newest first.
        """
        with get_db() as conn:
            if posting_id:
                rows = conn.execute(
                    "SELECT id, user_id, posting_id, stage, persona, question_count, "
                    "current_question, is_complete, created_at, updated_at "
                    "FROM interview_coach_sessions WHERE user_id = ? AND posting_id = ? "
                    "ORDER BY created_at DESC",
                    (user_id, posting_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, user_id, posting_id, stage, persona, question_count, "
                    "current_question, is_complete, created_at, updated_at "
                    "FROM interview_coach_sessions WHERE user_id = ? "
                    "ORDER BY created_at DESC",
                    (user_id,),
                ).fetchall()
        return [dict(r) for r in rows]

    def list_sessions(self, user_id: int) -> List[Dict[str, Any]]:
        """List all interview coach sessions for user.

        Alias for ``get_sessions(user_id)`` without posting filter.

        Args:
            user_id: User whose sessions to list.

        Returns:
            List of session summary dicts, newest first.
        """
        return self.get_sessions(user_id)

    def get_session_detail(
        self, session_id: str, user_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Get full session transcript with scores.

        Alias for ``get_session()`` for API naming consistency.

        Args:
            session_id: Session to retrieve.
            user_id: Optional ownership filter.

        Returns:
            Full session dict with messages, or None if not found.
        """
        return self.get_session(session_id, user_id=user_id)

    def get_assessment(
        self, session_id: str, user_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Get overall assessment for a completed session.

        Args:
            session_id: Completed session ID.
            user_id: Optional ownership filter.

        Returns:
            Dict with ``assessment`` and ``scores``, or None if session not found.
            Returns error dict if session is not yet complete.
        """
        session = self._get_session_row(session_id, user_id=user_id)
        if not session:
            return None
        if not session["is_complete"]:
            return {"error": "Session not yet complete"}
        assessment: Dict[str, Any] = {}
        if isinstance(session.get("overall_assessment_json"), str):
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                assessment = json.loads(session["overall_assessment_json"])
        scores: List[Dict[str, Any]] = []
        if isinstance(session.get("scores_json"), str):
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                scores = json.loads(session["scores_json"])
        return {"assessment": assessment, "scores": scores}

    # ──────────────────────────────────────────────
    # Public API — Prep Sheet
    # ──────────────────────────────────────────────

    def generate_prep_sheet(self, user_id: int, posting_id: str) -> Dict[str, Any]:
        """Generate comprehensive interview prep sheet for a specific posting.

        Args:
            user_id: User to generate prep for.
            posting_id: Job posting to prepare for.

        Returns:
            Dict with ``posting_id``, ``title``, ``company``, ``prep_data``,
            ``star_examples``, and ``talking_points``.

        Raises:
            ValueError: If posting is not found.
        """
        posting = self._get_posting(posting_id, user_id=user_id)
        if not posting:
            raise ValueError(f"Posting {posting_id} not found")

        profile = self._get_user_profile(user_id)
        profile_text = self._profile_summary(profile)

        star_examples: List[Dict[str, str]] = []
        try:
            with get_db() as conn:
                rows = conn.execute(
                    "SELECT title, narrative_text FROM journey_narratives "
                    "WHERE user_id = ? AND status = 'approved' LIMIT 5",
                    (user_id,),
                ).fetchall()
            for r in rows:
                star_examples.append({"title": r[0], "text": r[1]})
        except Exception:
            pass

        talking_points: List[Any] = []
        try:
            from interview_guide import generate_interview_guide

            guide = generate_interview_guide(user_id, posting.get("description", ""))
            if guide and "talking_points" in guide:
                talking_points = guide["talking_points"][:5]
        except Exception:
            pass

        jd = posting.get("description", "")
        title = posting.get("title", "Unknown Role")
        company = posting.get("company", "Unknown Company")

        prompt = (
            f"Generate a comprehensive interview prep sheet for:\n"
            f"Role: {title} at {company}\n"
            f"Job Description: {jd[:1500]}\n\n"
            f"Candidate Profile:\n{profile_text[:1000]}\n\n"
            f"Generate:\n"
            f"1. 5 likely interview questions specific to this role\n"
            f"2. Key skills to emphasize from the candidate's background\n"
            f"3. Company research talking points\n"
            f"4. Questions the candidate should ask the interviewer\n"
            f"5. Potential red flags or gaps to prepare for\n"
            f"Return as JSON with keys: questions, skills_to_emphasize, "
            f"company_talking_points, questions_to_ask, preparation_notes"
        )

        result = self._call_llm(prompt)
        prep_data: Dict[str, Any] = {}
        if result:
            try:
                import re as _re

                match = _re.search(r"\{.*\}", result, _re.DOTALL)
                if match:
                    prep_data = json.loads(match.group(0))
            except (json.JSONDecodeError, ValueError):
                prep_data = {"raw_advice": result}

        return {
            "posting_id": posting_id,
            "title": title,
            "company": company,
            "prep_data": prep_data,
            "star_examples": star_examples,
            "talking_points": talking_points,
        }
