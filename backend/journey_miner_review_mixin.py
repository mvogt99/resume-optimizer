"""ReviewMixin: journey review sessions and narrative interview."""

import contextlib
import json
import logging
import uuid

import httpx

logger = logging.getLogger(__name__)

REVIEW_STAGES_TIMELINE = [
    "overview",
    "events_review",
    "skills_review",
    "achievements_review",
    "complete",
]
REVIEW_STAGES_NARRATIVE = [
    "goals",
    "experience",
    "highlights",
    "drafting",
    "refinement",
    "complete",
]


class ReviewMixin:
    """Mixin providing guided review and narrative-building methods for JourneyMiner."""

    def _init_review_tables(self):
        import models

        with models.get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS journey_review_sessions (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    review_type TEXT DEFAULT 'timeline',
                    stage TEXT DEFAULT 'overview',
                    context_json TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_finalized INTEGER DEFAULT 0
                )
            """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS journey_review_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )
            conn.commit()

    def start_review_session(self, user_id, review_type="timeline"):
        """Start guided AI review of journey findings or narrative building."""
        import models

        self._init_review_tables()
        session_id = str(uuid.uuid4())

        if review_type == "timeline":
            stats = self._get_timeline_stats(user_id=user_id)
            context = {"review_type": "timeline", "stats": stats}
            opening = (
                f"Let's review your AI journey timeline. You have "
                f"**{stats.get('events', 0)}** events across "
                f"**{stats.get('skills', 0)}** skills and "
                f"**{stats.get('achievements', 0)}** achievements.\n\n"
                f"I'll walk through your events by category. "
                f"You can confirm, edit, or flag anything that needs correction.\n\n"
                f"Which category would you like to start with? "
                f"(milestones, learning, fixes, development, or all)"
            )
            stage = "overview"
        else:
            narratives = self.get_narratives(user_id)
            has_narratives = len(narratives) > 0
            context = {"review_type": "narrative", "has_existing": has_narratives}
            if has_narratives:
                opening = (
                    f"You have **{len(narratives)}** existing narratives. "
                    f"We can refine them or build new ones.\n\n"
                    f"What's your goal? Resume bullets for a specific role, "
                    f"LinkedIn About section, or campaign content?"
                )
            else:
                opening = (
                    "Let's build professional narratives from your AI journey data.\n\n"
                    "What's your goal for these narratives? For example:\n"
                    "- Resume bullets for a specific role\n"
                    "- LinkedIn About section\n"
                    "- LinkedIn campaign content\n\n"
                    "Also — what roles or positions are you targeting?"
                )
            stage = "goals"

        with models.get_db() as conn:
            conn.execute(
                "INSERT INTO journey_review_sessions "
                "(id, user_id, review_type, stage, context_json) VALUES (?, ?, ?, ?, ?)",
                (session_id, user_id, review_type, stage, json.dumps(context)),
            )
            conn.commit()

        self._save_review_message(session_id, "assistant", opening)
        return {
            "session_id": session_id,
            "message": opening,
            "stage": stage,
            "review_type": review_type,
        }

    def send_review_message(self, session_id, user_message, user_id=None):
        """Handle user response in review/narrative conversation."""
        import models

        self._init_review_tables()
        session = self._get_review_session(session_id, user_id=user_id)
        if not session:
            return {"error": "Session not found"}
        if session["is_finalized"]:
            return {"error": "Session already finalized"}

        self._save_review_message(session_id, "user", user_message)
        context = json.loads(session["context_json"])
        stage = session["stage"]
        review_type = session["review_type"]
        messages = self._get_review_messages(session_id)

        # Advance stage based on message count
        user_count = sum(1 for m in messages if m["role"] == "user")
        stages = REVIEW_STAGES_TIMELINE if review_type == "timeline" else REVIEW_STAGES_NARRATIVE
        try:
            idx = stages.index(stage)
        except ValueError:
            idx = 0

        if user_count >= 2 * (idx + 1) and idx < len(stages) - 1:
            new_stage = stages[idx + 1]
        else:
            new_stage = stage

        ai_response = self._generate_review_response(
            context,
            messages,
            new_stage,
            review_type,
            user_message,
            user_id=session.get("user_id"),
        )

        with models.get_db() as conn:
            conn.execute(
                "UPDATE journey_review_sessions SET stage = ?, context_json = ?, "
                "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (new_stage, json.dumps(context), session_id),
            )
            conn.commit()

        self._save_review_message(session_id, "assistant", ai_response)

        return {
            "session_id": session_id,
            "message": ai_response,
            "stage": new_stage,
            "is_complete": new_stage == "complete",
        }

    def apply_review_updates(self, session_id, user_id=None):
        """Apply confirmed changes from timeline review or save generated narratives."""
        import models

        self._init_review_tables()
        session = self._get_review_session(session_id, user_id=user_id)
        if not session:
            return {"error": "Session not found"}

        messages = self._get_review_messages(session_id)
        review_type = session["review_type"]
        user_id = session["user_id"]

        if review_type == "narrative":
            from journey_synthesizer import JourneySynthesizer

            conversation = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages)
            synthesizer = JourneySynthesizer()
            synthesizer.generate_with_interview_context(user_id, conversation)

        with models.get_db() as conn:
            conn.execute(
                "UPDATE journey_review_sessions SET is_finalized = 1, "
                "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (session_id,),
            )
            conn.commit()

        return {"status": "applied", "session_id": session_id}

    def _generate_review_response(
        self, context, messages, stage, review_type, user_message, user_id=None
    ):
        """Generate AI response for review/narrative conversation."""
        import os

        HARNESS_URL = os.environ.get("HARNESS_URL", "http://localhost:8000/api/harness/run")

        conversation = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages[-8:])

        if review_type == "timeline":
            journey_context = self._get_timeline_context_string(user_id=user_id)
            prompt = (
                "You are an AI career coach reviewing journey timeline data with the user. "
                f"Current stage: {stage}.\n\n"
                f"Timeline data:\n{journey_context}\n\n"
                f"Conversation:\n{conversation}\n\n"
                f"User just said: {user_message}\n\n"
                "Respond helpfully (2-3 sentences). Present relevant events for review, "
                "ask about accuracy, or summarize confirmed changes."
            )
        else:
            journey_context = self._get_timeline_context_string(user_id=user_id)
            stage_guide = {
                "goals": "Ask about narrative goals and target roles.",
                "experience": "Present top skills/milestones, ask which to highlight.",
                "highlights": "Propose 3-5 key themes/stories from the data.",
                "drafting": "Generate narrative drafts based on the conversation.",
                "refinement": "Incorporate user feedback on specific drafts.",
                "complete": "Summarize final versions, thank the user.",
            }
            prompt = (
                "You are an AI career coach building professional narratives. "
                f"Stage: {stage} — {stage_guide.get(stage, '')}.\n\n"
                f"Journey data:\n{journey_context}\n\n"
                f"Conversation:\n{conversation}\n\n"
                f"User just said: {user_message}\n\n"
                "Respond helpfully (2-4 sentences). If in drafting/refinement stage, "
                "include actual narrative text the user can review."
            )

        try:
            resp = httpx.post(
                HARNESS_URL,
                json={"task": prompt, "task_type": "general", "max_tokens": 1024},
                timeout=30,
            )
            if resp.status_code == 200:
                output = resp.json().get("output", "")
                if output and len(output) > 10:
                    return output.strip()
        except Exception:
            pass

        # Fallback
        fallback = {
            "overview": "Which category of events would you like to review first?",
            "events_review": "Let me know if any of these events need corrections.",
            "skills_review": "Are these skills accurately tracked? Any to add or remove?",
            "achievements_review": "Do these achievements look correct? Any metrics to update?",
            "goals": "What roles are you targeting with these narratives?",
            "experience": "Which experiences are most important to highlight?",
            "highlights": "What themes resonate most with your career story?",
            "drafting": "I'll draft some narratives based on our conversation. Click 'Apply' when ready.",  # noqa: E501
            "refinement": "What changes would you like to the drafts?",
            "complete": "Review is complete. Click 'Apply Changes' to save.",
        }
        return fallback.get(stage, "Tell me more about what you'd like to focus on.")

    def _get_timeline_stats(self, user_id=None):
        from models import get_db

        with get_db() as conn:
            if user_id is not None:
                events = conn.execute(
                    "SELECT COUNT(*) FROM journey_events WHERE user_id = ?", (user_id,)
                ).fetchone()[0]
                techs = conn.execute(
                    "SELECT technologies FROM journey_events "
                    "WHERE technologies != '[]' AND user_id = ?",
                    (user_id,),
                ).fetchall()
                achievements = conn.execute(
                    "SELECT COUNT(*) FROM journey_events "
                    "WHERE category IN ('milestone', 'achievement') AND user_id = ?",
                    (user_id,),
                ).fetchone()[0]
            else:
                events = conn.execute("SELECT COUNT(*) FROM journey_events").fetchone()[0]
                techs = conn.execute(
                    "SELECT technologies FROM journey_events WHERE technologies != '[]'"
                ).fetchall()
                achievements = conn.execute(
                    "SELECT COUNT(*) FROM journey_events "
                    "WHERE category IN ('milestone', 'achievement')"
                ).fetchone()[0]

        skill_set = set()
        for row in techs:
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                for t in json.loads(row[0]):
                    skill_set.add(t)

        return {
            "events": events,
            "skills": len(skill_set),
            "achievements": achievements,
        }

    def _get_timeline_context_string(self, user_id=None):
        from models import get_db

        with get_db() as conn:
            if user_id is not None:
                rows = conn.execute(
                    "SELECT event_date, title, category, technologies FROM journey_events "
                    "WHERE user_id = ? ORDER BY event_date DESC LIMIT 30",
                    (user_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT event_date, title, category, technologies FROM journey_events "
                    "ORDER BY event_date DESC LIMIT 30"
                ).fetchall()
        lines = []
        for r in rows:
            lines.append(f"  {r['event_date']}: [{r['category']}] {r['title']}")
        return "\n".join(lines) if lines else "(no events)"

    def _get_review_session(self, session_id, user_id=None):
        from models import get_db

        with get_db() as conn:
            if user_id is not None:
                row = conn.execute(
                    "SELECT * FROM journey_review_sessions WHERE id = ? AND user_id = ?",
                    (session_id, user_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM journey_review_sessions WHERE id = ?", (session_id,)
                ).fetchone()
        return dict(row) if row else None

    def _get_review_messages(self, session_id):
        from models import get_db

        with get_db() as conn:
            rows = conn.execute(
                "SELECT role, content, created_at FROM journey_review_messages "
                "WHERE session_id = ? ORDER BY created_at",
                (session_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def _save_review_message(self, session_id, role, content):
        import models

        with models.get_db() as conn:
            conn.execute(
                "INSERT INTO journey_review_messages (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content),
            )
            conn.commit()

    def get_sources(self, source_type=None, limit=50, user_id=None):
        from models import get_db

        with get_db() as conn:
            base_where = "WHERE user_id = ?" if user_id is not None else "WHERE 1=1"
            base_params = [user_id] if user_id is not None else []

            if source_type:
                rows = conn.execute(
                    "SELECT id, source_type, source_path, title, "
                    f"classification, event_date, content_preview "
                    f"FROM journey_sources {base_where} AND source_type = ? "
                    "ORDER BY event_date DESC LIMIT ?",
                    base_params + [source_type, limit],
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, source_type, source_path, title, "
                    f"classification, event_date, content_preview "
                    f"FROM journey_sources {base_where} "
                    "ORDER BY event_date DESC LIMIT ?",
                    base_params + [limit],
                ).fetchall()
        return [dict(r) for r in rows]
