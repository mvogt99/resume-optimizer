"""
Campaign interview — 7-stage chat state machine for LinkedIn campaign planning.
Mirrors experience_chat.py pattern. Grounded in ArangoDB knowledge graph.
"""

import json
import uuid

from campaign_interview_responses import CampaignInterviewerResponseMixin
from llm_helper import call_llm, call_llm_quality
from models import get_db

# Interview stages
STAGES = [
    "theme",  # Campaign theme selection
    "audience",  # Target audience definition
    "tone",  # Voice and tone
    "storyline",  # Narrative arc
    "post_count",  # How many posts / cadence
    "content_seeds",  # Specific post ideas with source refs
    "review",  # Full outline confirmation
]

STAGE_DESCRIPTIONS = {
    "theme": "selecting the campaign theme",
    "audience": "defining the target audience",
    "tone": "setting the voice and tone",
    "storyline": "crafting the narrative arc",
    "post_count": "deciding post count and cadence",
    "content_seeds": "generating specific post ideas",
    "review": "reviewing the full campaign outline",
}


class CampaignInterviewer(CampaignInterviewerResponseMixin):
    """7-stage interview to plan a LinkedIn marketing campaign."""

    def start_session(self, user_id, initial_theme=""):
        """Start a new campaign interview session."""
        session_id = str(uuid.uuid4())
        context = {
            "theme": initial_theme,
            "audience": "",
            "tone": "",
            "storyline": "",
            "post_count": 0,
            "cadence": "",
            "seeds": [],
        }

        stage = "theme"
        with get_db() as conn:
            conn.execute(
                "INSERT INTO campaign_sessions "
                "(id, user_id, stage, context_json) VALUES (?, ?, ?, ?)",
                (session_id, user_id, stage, json.dumps(context)),
            )
            conn.commit()

        # Get theme suggestions from graph
        suggestions = self._get_theme_suggestions()

        if initial_theme:
            opening = (
                f'Great, let\'s build a LinkedIn campaign around **"{initial_theme}"**.\n\n'
                "What specific angle or sub-topic would you like to focus on? "
                "For example: lessons learned, technical deep-dives, leadership insights..."
            )
        else:
            suggestion_text = ""
            if suggestions:
                top = [s.get("theme", s.get("name", "")) for s in suggestions[:5]]
                suggestion_text = (
                    "\n\nBased on your knowledge graph, here are some theme ideas:\n"
                    + "\n".join(f"- **{t}**" for t in top if t)
                )
            opening = (
                "Let's plan a LinkedIn content campaign!\n\n"
                "What theme would you like to build your campaign around? "
                "This could be a technology area, leadership topic, or industry insight."
                f"{suggestion_text}"
            )

        self._save_message(session_id, "assistant", opening)

        return {
            "session_id": session_id,
            "stage": stage,
            "message": opening,
            "suggestions": suggestions,
        }

    def process_message(self, session_id, user_message, user_id=None):
        """Process user message and advance the interview."""
        session = self._get_session(session_id, user_id=user_id)
        if not session:
            return {"error": "Session not found"}

        if session["is_finalized"]:
            return {"error": "Session already finalized", "session_id": session_id}

        self._save_message(session_id, "user", user_message)

        context = json.loads(session["context_json"])
        stage = session["stage"]

        # Extract info from message
        context = self._extract_from_message(context, stage, user_message)

        # Advance stage
        new_stage = self._advance_stage(stage, context)

        # Generate response with graph grounding
        suggestions = self._get_stage_suggestions(new_stage, context)
        ai_response = self._generate_response(context, new_stage, user_message, suggestions)

        self._update_session(
            session_id,
            stage=new_stage,
            context_json=json.dumps(context),
        )
        self._save_message(session_id, "assistant", ai_response)

        return {
            "session_id": session_id,
            "stage": new_stage,
            "message": ai_response,
            "context": context,
            "suggestions": suggestions,
            "is_review": new_stage == "review",
        }

    def get_session_state(self, session_id, user_id=None):
        """Get current session state + messages."""
        session = self._get_session(session_id, user_id=user_id)
        if not session:
            return {"error": "Session not found"}

        messages = self._get_messages(session_id)
        context = json.loads(session["context_json"])

        return {
            "session_id": session_id,
            "stage": session["stage"],
            "context": context,
            "messages": messages,
            "is_finalized": bool(session["is_finalized"]),
        }

    def finalize_to_campaign(self, session_id, user_id):
        """Create a campaigns row from the interview context."""
        session = self._get_session(session_id, user_id=user_id)
        if not session:
            return {"error": "Session not found"}

        context = json.loads(session["context_json"])

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO campaigns "
                "(user_id, session_id, theme, audience, tone, storyline, cadence, "
                "status, post_count, metadata_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?)",
                (
                    user_id,
                    session_id,
                    context.get("theme", ""),
                    context.get("audience", ""),
                    context.get("tone", ""),
                    context.get("storyline", ""),
                    context.get("cadence", ""),
                    context.get("post_count", 0),
                    json.dumps({"seeds": context.get("seeds", [])}),
                ),
            )
            campaign_id = cursor.lastrowid

            # Create empty post stubs from seeds
            for i, seed in enumerate(context.get("seeds", [])):
                cursor.execute(
                    "INSERT INTO campaign_posts "
                    "(campaign_id, position, title, source_refs, status) "
                    "VALUES (?, ?, ?, ?, 'stub')",
                    (
                        campaign_id,
                        i,
                        seed.get("title", f"Post {i + 1}"),
                        json.dumps(seed.get("source_refs", [])),
                    ),
                )

            # Mark session as finalized
            cursor.execute(
                "UPDATE campaign_sessions SET is_finalized = 1, "
                "campaign_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (campaign_id, session_id),
            )

            conn.commit()

        return {
            "campaign_id": campaign_id,
            "session_id": session_id,
            "theme": context.get("theme", ""),
            "post_count": context.get("post_count", 0),
        }

    # Response/suggestion/seed generation methods are in CampaignInterviewerResponseMixin
    # (campaign_interview_responses.py): _extract_from_message, _advance_stage,
    # _generate_response, _call_llm_for_stage, _template_response, _format_seeds,
    # _format_review, _get_theme_suggestions, _get_theme_suggestions_from_db,
    # _get_stage_suggestions, _generate_seeds.

    # --- Private: DB helpers ---

    def _get_session(self, session_id, user_id=None):
        from models import get_db

        with get_db() as conn:
            if user_id is not None:
                row = conn.execute(
                    "SELECT * FROM campaign_sessions WHERE id = ? AND user_id = ?",
                    (session_id, user_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM campaign_sessions WHERE id = ?", (session_id,)
                ).fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "user_id": row[1],
            "stage": row[2],
            "context_json": row[3],
            "campaign_id": row[4],
            "created_at": row[5],
            "updated_at": row[6],
            "is_finalized": row[7],
        }

    def _get_messages(self, session_id):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role, content, created_at FROM campaign_messages "
                "WHERE session_id = ? ORDER BY created_at",
                (session_id,),
            )
            rows = cursor.fetchall()
        return [{"role": r[0], "content": r[1], "created_at": r[2]} for r in rows]

    def _save_message(self, session_id, role, content):
        with get_db() as conn:
            conn.execute(
                "INSERT INTO campaign_messages (session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content),
            )
            conn.commit()

    _ALLOWED_COLUMNS = {"stage", "context_json", "is_finalized", "theme"}

    def _update_session(self, session_id, **kwargs):
        if not kwargs:
            return
        from models import get_db

        sets, values = [], []
        for key, val in kwargs.items():
            if key not in self._ALLOWED_COLUMNS:
                continue
            sets.append(f"{key} = ?")
            values.append(val)
        if not sets:
            return
        sets.append("updated_at = CURRENT_TIMESTAMP")
        values.append(session_id)
        with get_db() as conn:
            conn.execute(
                f"UPDATE campaign_sessions SET {', '.join(sets)} WHERE id = ?",
                values,
            )
            conn.commit()


# Module-level singleton
_interviewer = None


def get_campaign_interviewer():
    global _interviewer
    if _interviewer is None:
        _interviewer = CampaignInterviewer()
    return _interviewer
