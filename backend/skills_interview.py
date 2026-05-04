"""
Skills interview: LLM-guided conversation to validate skill claims
and generate STAR bullets. Supports single-skill and batch mode.
3-stage state machine: context → depth → complete.
"""

import contextlib
import json
import logging
import os
import uuid

import httpx
from models import get_db

logger = logging.getLogger(__name__)

STAGES = ["context", "depth", "complete"]
HARNESS_URL = os.environ.get("HARNESS_URL", "http://localhost:8000/api/harness/run")


def init_skills_interview_tables():
    """Create skills interview tables if they don't exist."""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS skills_interview_sessions (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                resume_id TEXT DEFAULT '',
                skills TEXT DEFAULT '[]',
                stage TEXT DEFAULT 'context',
                context_json TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_finalized INTEGER DEFAULT 0
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS skills_interview_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        conn.commit()


class SkillsInterviewer:
    """Multi-turn conversation to validate skills and generate STAR bullets."""

    def __init__(self):
        init_skills_interview_tables()

    def start_session(self, user_id, resume_id, skills):
        """Start a new skills interview session (single or batch)."""
        session_id = str(uuid.uuid4())
        context = {"skills": skills, "gathered": {}}

        with get_db() as conn:
            conn.execute(
                "INSERT INTO skills_interview_sessions "
                "(id, user_id, resume_id, skills, stage, context_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    user_id,
                    resume_id,
                    json.dumps(skills),
                    "context",
                    json.dumps(context),
                ),
            )
            conn.commit()

        if len(skills) == 1:
            opening = (
                f"Let's discuss your experience with **{skills[0]}**.\n\n"
                f"What projects or roles have involved {skills[0]}? "
                f"Describe your experience level and how you've used it."
            )
        else:
            skill_list = ", ".join(f"**{s}**" for s in skills)
            opening = (
                f"Let's discuss your experience with {skill_list}.\n\n"
                f"For each skill, tell me about the projects or roles where you used it. "
                f"You can describe them together if they overlap, or one at a time."
            )

        self._save_message(session_id, "assistant", opening)
        return {"session_id": session_id, "message": opening, "stage": "context"}

    def send_message(self, session_id, user_message, user_id=None):
        """Process a user message and advance the conversation."""
        session = self._get_session(session_id, user_id=user_id)
        if not session:
            return {"error": "Session not found"}
        if session["is_finalized"]:
            return {"error": "Session already finalized"}

        self._save_message(session_id, "user", user_message)

        stage = session["stage"]
        context = json.loads(session["context_json"])
        messages = self._get_messages(session_id)

        # Decide whether to advance stage
        user_msg_count = sum(1 for m in messages if m["role"] == "user")
        new_stage = stage
        if stage == "context" and user_msg_count >= 2:
            new_stage = "depth"
        elif stage == "depth" and user_msg_count >= 4:
            new_stage = "complete"

        ai_response = self._generate_response(context, messages, new_stage, user_message)

        with get_db() as conn:
            conn.execute(
                "UPDATE skills_interview_sessions SET stage = ?, context_json = ?, "
                "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (new_stage, json.dumps(context), session_id),
            )
            conn.commit()

        self._save_message(session_id, "assistant", ai_response)

        return {
            "session_id": session_id,
            "message": ai_response,
            "stage": new_stage,
            "is_complete": new_stage == "complete",
        }

    def finalize_session(self, session_id, user_id=None):
        """Generate per-skill verdicts with STAR bullets."""
        session = self._get_session(session_id, user_id=user_id)
        if not session:
            return {"error": "Session not found"}

        skills = json.loads(session["skills"])
        messages = self._get_messages(session_id)

        conversation = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages)

        prompt = (
            "Based on this conversation about the user's skills, generate a JSON array. "
            "For EACH skill listed below, produce one object with these fields:\n"
            '- "skill": the skill name\n'
            '- "has_skill": boolean — does the user demonstrably have this skill?\n'
            '- "confidence": "high", "medium", or "low"\n'
            '- "star_bullet": a STAR-format resume bullet point (action verb + task + result). '
            "Leave empty string if has_skill is false.\n"
            '- "evidence_summary": 1-2 sentence summary of evidence from conversation\n\n'
            f"Skills to evaluate: {', '.join(skills)}\n\n"
            f"Conversation:\n{conversation}\n\n"
            "Return ONLY a JSON array, no extra text."
        )

        raw = self._call_llm(prompt)
        results = self._extract_json_array(raw) if raw else None

        if not results:
            results = [
                {
                    "skill": s,
                    "has_skill": True,
                    "confidence": "medium",
                    "star_bullet": "",
                    "evidence_summary": "User discussed this skill in the interview.",
                }
                for s in skills
            ]

        with get_db() as conn:
            conn.execute(
                "UPDATE skills_interview_sessions SET is_finalized = 1, "
                "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (session_id,),
            )
            conn.commit()

        return results

    def get_summary(self, session_id, user_id=None):
        """Get finalization results (re-finalize if needed)."""
        session = self._get_session(session_id, user_id=user_id)
        if not session:
            return {"error": "Session not found"}
        if not session["is_finalized"]:
            return {"error": "Session not yet finalized"}
        return self.finalize_session(session_id)

    # --- Private methods ---

    def _generate_response(self, context, messages, stage, user_message):
        """Generate AI response via LLM or fallback template."""
        skills = context.get("skills", [])
        skill_list = ", ".join(skills)

        conversation = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages[-8:])

        stage_prompts = {
            "context": (
                f"You are a career coach validating the user's skills: {skill_list}. "
                "Ask about what projects/roles involved these skills and their experience level. "
                "Be encouraging and specific. Keep responses to 2-3 sentences."
            ),
            "depth": (
                f"You are a career coach digging deeper into: {skill_list}. "
                "Ask for specific examples, metrics, outcomes, and team context. "
                "These details will be used to write STAR-format resume bullets. "
                "Keep responses to 2-3 sentences."
            ),
            "complete": (
                f"The user has provided enough detail about: {skill_list}. "
                "Thank them and let them know you have enough information to generate "
                "STAR-format resume bullets. Summarize the key points briefly."
            ),
        }

        prompt = (
            f"{stage_prompts.get(stage, stage_prompts['context'])}\n\n"
            f"Conversation so far:\n{conversation}\n\n"
            f"User just said: {user_message}\n\n"
            "Respond naturally (2-3 sentences)."
        )

        llm_response = self._call_llm(prompt)
        if llm_response and len(llm_response) > 10:
            return llm_response.strip()

        return self._template_response(stage, skills)

    def _template_response(self, stage, skills):
        skill_list = ", ".join(skills)
        templates = {
            "context": (
                f"Thanks for sharing! Can you tell me more about specific projects "
                f"where you used {skill_list}? What was your role?"
            ),
            "depth": (
                "Great context. Can you share any specific outcomes or metrics? "
                "For example, did it save time, reduce costs, or improve a process?"
            ),
            "complete": (
                "I have enough information to generate your STAR bullets now. "
                "Click 'Finalize' to see the results."
            ),
        }
        return templates.get(stage, templates["context"])

    def _call_llm(self, prompt):
        try:
            response = httpx.post(
                HARNESS_URL,
                json={"task": prompt, "task_type": "general", "max_tokens": 512},
                timeout=30,
            )
            if response.status_code == 200:
                data = response.json()
                output = data.get("output", "")
                if output and len(output) > 10:
                    return output.strip()
        except Exception:
            logger.warning("LLM call failed for skills interview", exc_info=True)
        return None

    def _extract_json_array(self, text):
        """Extract a JSON array from LLM output."""
        import re

        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            with contextlib.suppress(json.JSONDecodeError):
                return json.loads(match.group())
        return None

    def _get_session(self, session_id, user_id=None):
        from models import get_db

        with get_db() as conn:
            if user_id is not None:
                row = conn.execute(
                    "SELECT * FROM skills_interview_sessions WHERE id = ? AND user_id = ?",
                    (session_id, user_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM skills_interview_sessions WHERE id = ?",
                    (session_id,),
                ).fetchone()
        return dict(row) if row else None

    def _get_messages(self, session_id):
        with get_db() as conn:
            rows = conn.execute(
                "SELECT role, content, created_at FROM skills_interview_messages "
                "WHERE session_id = ? ORDER BY created_at",
                (session_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def _save_message(self, session_id, role, content):
        with get_db() as conn:
            conn.execute(
                "INSERT INTO skills_interview_messages "
                "(session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content),
            )
            conn.commit()


_interviewer = None


def get_skills_interviewer():
    global _interviewer
    if _interviewer is None:
        _interviewer = SkillsInterviewer()
    return _interviewer
