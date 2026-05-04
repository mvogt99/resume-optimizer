"""Interview Coach DB — database access and fallback helpers."""

# Module contents:
# _get_session_row()      — fetches session row from SQLite by session_id + user_id
# _save_message()         — saves a chat message to the session
# _get_last_question()    — retrieves the question text at a given question_index
# _get_posting()          — fetches job posting row by posting_id
# _fallback_questions()   — returns template question list when LLM is unavailable

import logging
from typing import Any, Dict, List, Optional

from models import get_db

logger = logging.getLogger(__name__)


class _InterviewCoachDBMixin:
    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────

    def _get_session_row(
        self, session_id: str, user_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Load a session row from the database.

        Args:
            session_id: Session to look up.
            user_id: Optional ownership filter.

        Returns:
            Session dict or None.
        """
        from models import get_db

        with get_db() as conn:
            if user_id is not None:
                row = conn.execute(
                    "SELECT * FROM interview_coach_sessions WHERE id = ? AND user_id = ?",
                    (session_id, user_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM interview_coach_sessions WHERE id = ?", (session_id,)
                ).fetchone()
        return dict(row) if row else None

    def _save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        question_index: int = -1,
        score_json: str = "{}",
    ) -> None:
        """Save a message to the interview_coach_messages table.

        Args:
            session_id: Session the message belongs to.
            role: Message role (``assistant``, ``user``, or ``system``).
            content: Message content text.
            question_index: Which question this relates to (-1 for general).
            score_json: JSON string of score data for system messages.
        """
        with get_db() as conn:
            conn.execute(
                "INSERT INTO interview_coach_messages "
                "(session_id, role, content, question_index, score_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, role, content, question_index, score_json),
            )
            conn.commit()

    def _get_last_question(self, session_id: str, question_index: int) -> str:
        """Retrieve the last assistant question for a given question index.

        Args:
            session_id: Session to search in.
            question_index: Question number to look up.

        Returns:
            Question text, or a default fallback.
        """
        with get_db() as conn:
            row = conn.execute(
                "SELECT content FROM interview_coach_messages "
                "WHERE session_id = ? AND role = 'assistant' AND question_index = ? "
                "ORDER BY id DESC LIMIT 1",
                (session_id, question_index),
            ).fetchone()
        return row[0] if row else "Tell me about yourself."

    def _get_posting(
        self, posting_id: str, user_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Load a job posting from the database.

        Args:
            posting_id: Posting to look up.
            user_id: Optional ownership filter.

        Returns:
            Posting dict or None.
        """
        if not posting_id:
            return None
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

    def _fallback_questions(self, title: str, count: int) -> List[Dict[str, Any]]:
        """Generate fallback questions when LLM is unavailable.

        Args:
            title: Job title for context.
            count: Number of questions to generate.

        Returns:
            List of question dicts with default structure.
        """
        templates = [
            {
                "text": "Tell me about yourself and why you're interested in this role.",
                "category": "behavioral",
                "difficulty": "easy",
                "suggested_approach": "Give a concise career narrative ending with why this role.",
                "star_outline": {
                    "situation": "Your current professional context",
                    "task": "Your career goals and motivations",
                    "action": "Steps you've taken toward this direction",
                    "result": "Why this role is the natural next step",
                },
            },
            {
                "text": "Describe a challenging project you led and its outcome.",
                "category": "behavioral",
                "difficulty": "medium",
                "suggested_approach": "Pick a project with measurable business impact.",
                "star_outline": {
                    "situation": "Project context and constraints",
                    "task": "Your specific responsibility",
                    "action": "Key decisions and execution steps",
                    "result": "Quantified outcomes and lessons learned",
                },
            },
            {
                "text": f"What technical skills make you a strong fit for {title}?",
                "category": "technical",
                "difficulty": "medium",
                "suggested_approach": "Map your skills directly to the job requirements.",
                "star_outline": {
                    "situation": "Context where you applied these skills",
                    "task": "Technical challenge you solved",
                    "action": "Technologies and approaches used",
                    "result": "Impact on system performance or team productivity",
                },
            },
            {
                "text": "How do you handle disagreements with team members?",
                "category": "behavioral",
                "difficulty": "medium",
                "suggested_approach": "Show empathy, active listening, and collaborative resolution.",  # noqa: E501
                "star_outline": {
                    "situation": "Specific disagreement context",
                    "task": "What needed to be resolved",
                    "action": "How you facilitated resolution",
                    "result": "Positive outcome and strengthened relationship",
                },
            },
            {
                "text": "Where do you see yourself in 3-5 years?",
                "category": "behavioral",
                "difficulty": "easy",
                "suggested_approach": "Align your growth trajectory with the company's direction.",
                "star_outline": {
                    "situation": "Your current career phase",
                    "task": "Growth areas you want to develop",
                    "action": "Steps you're taking toward those goals",
                    "result": "How this role accelerates your trajectory",
                },
            },
            {
                "text": "Describe a time you had to learn a new technology quickly.",
                "category": "technical",
                "difficulty": "medium",
                "suggested_approach": "Emphasize your learning process and speed of contribution.",
                "star_outline": {
                    "situation": "Why the new technology was needed",
                    "task": "Timeline and expectations",
                    "action": "Your learning strategy and milestones",
                    "result": "Time to productivity and impact",
                },
            },
            {
                "text": "How do you prioritize when you have multiple competing deadlines?",
                "category": "situational",
                "difficulty": "medium",
                "suggested_approach": "Show a systematic approach to prioritization.",
                "star_outline": {
                    "situation": "Multiple competing priorities",
                    "task": "Deliver on all commitments",
                    "action": "Prioritization framework used",
                    "result": "All deadlines met and stakeholder satisfaction",
                },
            },
            {
                "text": "What questions do you have about our team and culture?",
                "category": "company_specific",
                "difficulty": "easy",
                "suggested_approach": "Ask thoughtful questions showing research and genuine interest.",  # noqa: E501
                "star_outline": {
                    "situation": "N/A — this is your chance to ask",
                    "task": "Demonstrate curiosity and preparation",
                    "action": "Ask about team dynamics, growth, or strategy",
                    "result": "Show you're evaluating mutual fit",
                },
            },
            {
                "text": "Tell me about a time you failed and what you learned.",
                "category": "behavioral",
                "difficulty": "hard",
                "suggested_approach": "Be honest, show self-awareness and growth.",
                "star_outline": {
                    "situation": "The project or initiative that didn't go as planned",
                    "task": "What you were responsible for",
                    "action": "What went wrong and your response",
                    "result": "Lessons learned and how you applied them",
                },
            },
            {
                "text": f"Why should we hire you for {title} over other candidates?",
                "category": "role_specific",
                "difficulty": "hard",
                "suggested_approach": "Highlight your unique combination of skills and experience.",
                "star_outline": {
                    "situation": "Your unique professional background",
                    "task": "Meeting the specific role requirements",
                    "action": "Evidence of your differentiated capabilities",
                    "result": "The value you'll deliver from day one",
                },
            },
        ]
        return templates[:count]
