"""
Adaptive Deep Interview Engine.
LLM-driven interview that probes gaps in the user's professional profile,
adjusting questions based on each answer rather than following hardcoded stages.
"""

import json
import uuid
from datetime import datetime, timezone

from deep_profile import get_deep_profile_engine
from llm_helper import call_llm_quality, extract_json
from models import get_db


def _init_interview_tables():
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS deep_interview_sessions (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                profile_id TEXT,
                mode TEXT DEFAULT 'comprehensive',
                job_text TEXT DEFAULT '',
                working_profile_json TEXT DEFAULT '{}',
                depth_assessment_json TEXT DEFAULT '{}',
                is_finalized INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS deep_interview_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                area TEXT DEFAULT '',
                profile_updates_json TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        conn.commit()


class DeepInterviewer:
    """LLM-driven adaptive interview that probes gaps based on the deep profile."""

    def __init__(self):
        _init_interview_tables()

    def start_session(self, user_id, mode="comprehensive", job_text=None):
        """Start a new adaptive interview session."""
        from deep_interview_handlers import generate_opening, get_opening_suggestions, identify_gaps

        engine = get_deep_profile_engine()
        profile = engine.get_profile(user_id)
        profile_meta = engine.get_profile_with_meta(user_id)

        if not profile:
            profile = engine.build_profile(user_id)
            profile_meta = engine.get_profile_with_meta(user_id)

        profile_id = profile_meta["id"] if profile_meta else ""
        exploration_areas = identify_gaps(profile, mode, job_text)
        opening = generate_opening(profile, exploration_areas, mode, job_text)

        depth_assessment = {
            "technical": "partial" if profile.get("technology_mastery") else "gap",
            "business_impact": "partial" if profile.get("business_impacts") else "gap",
            "leadership": (
                "partial" if profile.get("leadership_profile", {}).get("team_scope") else "gap"
            ),
            "career_narrative": (
                "partial" if profile.get("career_arc", {}).get("phases") else "gap"
            ),
            "differentiators": "partial" if profile.get("differentiators") else "gap",
        }
        if mode == "role_specific" and job_text:
            depth_assessment["role_targeting"] = "gap"

        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        with get_db() as conn:
            conn.execute(
                "INSERT INTO deep_interview_sessions "
                "(id, user_id, profile_id, mode, job_text, working_profile_json, "
                "depth_assessment_json, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    user_id,
                    profile_id,
                    mode,
                    job_text or "",
                    json.dumps(profile, default=str),
                    json.dumps(depth_assessment),
                    now,
                    now,
                ),
            )
            conn.commit()

        self._save_message(session_id, "assistant", opening, area="introduction")

        return {
            "session_id": session_id,
            "message": opening,
            "profile_summary": profile.get("professional_summary", ""),
            "exploration_areas": exploration_areas,
            "depth_assessment": depth_assessment,
            "suggestions": get_opening_suggestions(exploration_areas),
        }

    def send_message(self, session_id, user_message, user_id=None):
        """Process a user message and generate an adaptive response."""
        from deep_interview_handlers import apply_update, build_interview_prompt, fallback_question

        session = self._get_session(session_id, user_id=user_id)
        if not session:
            return {"error": "Session not found"}
        if session["is_finalized"]:
            return {"error": "Session already finalized"}

        self._save_message(session_id, "user", user_message)

        messages = self._get_messages(session_id)
        working_profile = json.loads(session["working_profile_json"] or "{}")
        depth_assessment = json.loads(session["depth_assessment_json"] or "{}")

        prompt = build_interview_prompt(
            working_profile,
            messages,
            depth_assessment,
            session["mode"],
            session["job_text"],
        )

        raw_response = call_llm_quality(prompt, task_type="reasoning", max_tokens=2048)
        parsed = extract_json(raw_response) if raw_response else None

        if parsed and isinstance(parsed, dict):
            ai_message = parsed.get("message", "")
            area = parsed.get("area", "")
            suggestions = parsed.get("suggestions", [])
            new_depth = parsed.get("depth_assessment", depth_assessment)
            profile_updates = parsed.get("profile_updates", [])
            is_complete = parsed.get("exploration_complete", False)
        else:
            ai_message = raw_response or fallback_question(depth_assessment)
            area = ""
            suggestions = []
            new_depth = depth_assessment
            profile_updates = []
            is_complete = False

        updated_insights = []
        for update in profile_updates:
            field = update.get("field", "")
            value = update.get("value")
            if field and value:
                apply_update(working_profile, field, value)
                updated_insights.append(
                    {
                        "area": area,
                        "insight_text": (
                            f"{field}: {value}" if isinstance(value, str) else f"{field} updated"
                        ),
                        "evidence_source": "interview",
                        "significance": update.get("significance", "medium"),
                    }
                )

        self._save_message(
            session_id, "assistant", ai_message, area=area, profile_updates=profile_updates
        )

        now = datetime.now(timezone.utc).isoformat()
        with get_db() as conn:
            conn.execute(
                "UPDATE deep_interview_sessions SET working_profile_json = ?, "
                "depth_assessment_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(working_profile, default=str), json.dumps(new_depth), now, session_id),
            )
            conn.commit()

        return {
            "session_id": session_id,
            "message": ai_message,
            "area": area,
            "suggestions": suggestions[:4],
            "depth_assessment": new_depth,
            "is_complete": is_complete,
            "updated_insights": updated_insights,
        }

    def get_status(self, session_id, user_id=None):
        """Get current session status and depth assessment."""
        session = self._get_session(session_id, user_id=user_id)
        if not session:
            return {"error": "Session not found"}

        messages = self._get_messages(session_id)
        depth_assessment = json.loads(session["depth_assessment_json"] or "{}")

        return {
            "session_id": session_id,
            "mode": session["mode"],
            "is_finalized": bool(session["is_finalized"]),
            "message_count": len(messages),
            "depth_assessment": depth_assessment,
            "created_at": session["created_at"],
            "updated_at": session["updated_at"],
        }

    def get_insights(self, session_id):
        """Get all interview-derived insights so far."""
        messages = self._get_messages(session_id)
        insights = []
        for msg in messages:
            if msg["role"] == "assistant" and msg.get("profile_updates_json"):
                try:
                    updates = json.loads(msg["profile_updates_json"])
                    for u in updates:
                        insights.append(
                            {
                                "area": msg.get("area", ""),
                                "field": u.get("field", ""),
                                "value": u.get("value", ""),
                                "source": "interview",
                                "timestamp": msg.get("created_at", ""),
                            }
                        )
                except (json.JSONDecodeError, TypeError):
                    pass
        return {"session_id": session_id, "insights": insights}

    def finalize_session(self, session_id, user_id=None):
        """Finalize the interview and merge insights into the persistent profile."""
        from deep_interview_handlers import (
            run_final_synthesis,
            summarize_improvements,
            write_to_graph,
        )

        session = self._get_session(session_id, user_id=user_id)
        if not session:
            return {"error": "Session not found"}

        user_id = session["user_id"]
        working_profile = json.loads(session["working_profile_json"] or "{}")
        messages = self._get_messages(session_id)

        final_profile = run_final_synthesis(working_profile, messages, session["job_text"])
        merged = final_profile if final_profile else working_profile

        engine = get_deep_profile_engine()
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as conn:
            existing = conn.execute(
                "SELECT id FROM deep_profiles WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1",
                (user_id,),
            ).fetchone()

            if existing:
                conn.execute(
                    "UPDATE deep_profiles SET profile_json = ?, updated_at = ? WHERE id = ?",
                    (json.dumps(merged, default=str), now, existing["id"]),
                )
            else:
                profile_id = str(uuid.uuid4())
                conn.execute(
                    "INSERT INTO deep_profiles (id, user_id, profile_json, source_summary, "
                    "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        profile_id,
                        user_id,
                        json.dumps(merged, default=str),
                        "Updated via deep interview",
                        now,
                        now,
                    ),
                )

            conn.execute(
                "UPDATE deep_interview_sessions SET is_finalized = 1, "
                "working_profile_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(merged, default=str), now, session_id),
            )
            conn.commit()

        role_synthesis = None
        if session["job_text"]:
            role_synthesis = engine.get_role_synthesis(user_id, session["job_text"])

        write_to_graph(merged)
        insights = self.get_insights(session_id)

        return {
            "profile": merged,
            "role_synthesis": role_synthesis,
            "new_insights": insights.get("insights", []),
            "improvement_summary": summarize_improvements(working_profile, merged),
        }

    # --- DB helpers ---

    def _get_session(self, session_id, user_id=None):
        with get_db() as conn:
            if user_id is not None:
                row = conn.execute(
                    "SELECT * FROM deep_interview_sessions WHERE id = ? AND user_id = ?",
                    (session_id, user_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM deep_interview_sessions WHERE id = ?", (session_id,)
                ).fetchone()
        return dict(row) if row else None

    def _get_messages(self, session_id):
        with get_db() as conn:
            rows = conn.execute(
                "SELECT role, content, area, profile_updates_json, created_at "
                "FROM deep_interview_messages WHERE session_id = ? ORDER BY created_at",
                (session_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def _save_message(self, session_id, role, content, area="", profile_updates=None):
        with get_db() as conn:
            conn.execute(
                "INSERT INTO deep_interview_messages "
                "(session_id, role, content, area, profile_updates_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, role, content, area, json.dumps(profile_updates or [], default=str)),
            )
            conn.commit()


# Singleton
_interviewer = None


def get_deep_interviewer():
    global _interviewer
    if _interviewer is None:
        _interviewer = DeepInterviewer()
    return _interviewer
