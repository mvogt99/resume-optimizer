"""
Conversational experience extraction via multi-turn chat.
Interviews users in natural language to extract work experience,
then structures it into resume-ready bullet points (STAR format).
"""

import json
import re
import uuid

from models import get_db

# Conversation stages
STAGES = [
    "intro",  # Ask for employer + client
    "role",  # Job title, team, reporting structure
    "responsibilities",  # Day-to-day duties
    "technologies",  # Tech stack, tools, methodologies
    "outcomes",  # Key accomplishments, metrics
    "challenges",  # Difficult problems solved
    "complete",  # All info gathered
]


def init_experience_tables():
    """Create experience chat tables if they don't exist."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS experience_sessions (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                employer TEXT DEFAULT '',
                client TEXT DEFAULT '',
                stage TEXT DEFAULT 'intro',
                context_json TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_finalized INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS experience_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES experience_sessions (id)
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS extracted_experiences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                employer TEXT DEFAULT '',
                client TEXT DEFAULT '',
                title TEXT DEFAULT '',
                duration TEXT DEFAULT '',
                responsibilities TEXT DEFAULT '[]',
                technologies TEXT DEFAULT '[]',
                accomplishments TEXT DEFAULT '[]',
                challenges TEXT DEFAULT '[]',
                bullet_points TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES experience_sessions (id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """
        )
        conn.commit()


class ExperienceExtractor:
    """Multi-turn conversation state machine for extracting work experience."""

    def __init__(self):
        init_experience_tables()

    def start_session(self, user_id, employer="", client=""):
        """Start a new experience extraction session."""
        from experience_chat_stages import enrich_session_context

        session_id = str(uuid.uuid4())
        context = {
            "employer": employer,
            "client": client,
            "title": "",
            "responsibilities": [],
            "technologies": [],
            "outcomes": [],
            "challenges": [],
        }

        enrichment_summary = ""
        if employer or client:
            enrichment_summary = enrich_session_context(context, user_id, employer, client)

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO experience_sessions "
                "(id, user_id, employer, client, stage, context_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, user_id, employer, client, "intro", json.dumps(context)),
            )
            conn.commit()

        if employer and client:
            opening = (
                f"Great! Let's document your experience at **{employer}** "
                f"working with **{client}**."
            )
            if enrichment_summary:
                opening += f"\n\n{enrichment_summary}"
            opening += "\n\nWhat was your job title or role in this engagement?"
            stage = "role"
            self._update_session(session_id, stage=stage)
        elif employer:
            opening = f"Let's document your experience at **{employer}**."
            if enrichment_summary:
                opening += f"\n\n{enrichment_summary}"
            opening += (
                "\n\nWere you working with a specific client or project? "
                "If so, who? Otherwise, just tell me your job title."
            )
            stage = "intro"
        else:
            opening = (
                "Let's document a work experience for your resume.\n\n"
                "Which employer and role would you like to start with?"
            )
            stage = "intro"

        self._save_message(session_id, "assistant", opening)
        return {"session_id": session_id, "stage": stage, "message": opening}

    def process_message(self, session_id, user_message, user_id=None):
        """Process a user message and advance the conversation."""
        from experience_chat_stages import (
            enrich_from_themes,
            enrich_session_context,
            extract_from_message,
        )

        session = self._get_session(session_id, user_id=user_id)
        if not session:
            return {"error": "Session not found"}
        if session["is_finalized"]:
            return {"error": "Session already finalized", "session_id": session_id}

        self._save_message(session_id, "user", user_message)

        context = json.loads(session["context_json"])
        stage = session["stage"]

        context = extract_from_message(context, stage, user_message, self._split_items)

        if stage == "intro" and not context.get("_enrichment"):
            employer = context.get("employer", "")
            client = context.get("client", "")
            if employer or client:
                enrich_session_context(context, session["user_id"], employer, client)

        if stage in ("responsibilities", "technologies", "outcomes", "challenges"):
            enrich_from_themes(context, session["user_id"], stage, user_message, self._split_items)

        new_stage = self._advance_stage(stage, context, user_message)
        ai_response = self._generate_response(session_id, context, new_stage, user_message)

        self._update_session(
            session_id,
            stage=new_stage,
            context_json=json.dumps(context),
            employer=context.get("employer", session["employer"]),
            client=context.get("client", session["client"]),
        )
        self._save_message(session_id, "assistant", ai_response)

        return {
            "session_id": session_id,
            "stage": new_stage,
            "message": ai_response,
            "context": context,
            "is_complete": new_stage == "complete",
        }

    def get_summary(self, session_id, user_id=None):
        """Get a structured summary of the extracted experience."""
        from experience_chat_stages import generate_bullet_points

        session = self._get_session(session_id, user_id=user_id)
        if not session:
            return {"error": "Session not found"}

        context = json.loads(session["context_json"])
        messages = self._get_messages(session_id)
        bullet_points = generate_bullet_points(context)

        return {
            "session_id": session_id,
            "employer": context.get("employer", session["employer"]),
            "client": context.get("client", session["client"]),
            "title": context.get("title", ""),
            "responsibilities": context.get("responsibilities", []),
            "technologies": context.get("technologies", []),
            "outcomes": context.get("outcomes", []),
            "challenges": context.get("challenges", []),
            "bullet_points": bullet_points,
            "stage": session["stage"],
            "is_finalized": bool(session["is_finalized"]),
            "message_count": len(messages),
        }

    def finalize_session(self, session_id, user_id, edits=None):
        """Finalize the session and save extracted experience to DB."""
        from experience_chat_stages import generate_bullet_points

        session = self._get_session(session_id, user_id=user_id)
        if not session:
            return {"error": "Session not found"}

        context = json.loads(session["context_json"])
        if edits:
            for key in [
                "title",
                "employer",
                "client",
                "responsibilities",
                "technologies",
                "outcomes",
                "challenges",
            ]:
                if key in edits:
                    context[key] = edits[key]

        bullet_points = generate_bullet_points(context)

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO extracted_experiences "
                "(session_id, user_id, employer, client, title, responsibilities, "
                "technologies, accomplishments, challenges, bullet_points) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    user_id,
                    context.get("employer", ""),
                    context.get("client", ""),
                    context.get("title", ""),
                    json.dumps(context.get("responsibilities", [])),
                    json.dumps(context.get("technologies", [])),
                    json.dumps(context.get("outcomes", [])),
                    json.dumps(context.get("challenges", [])),
                    json.dumps(bullet_points),
                ),
            )
            cursor.execute(
                "UPDATE experience_sessions SET is_finalized = 1, "
                "context_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (json.dumps(context), session_id),
            )
            conn.commit()
            experience_id = cursor.lastrowid

        return {
            "experience_id": experience_id,
            "session_id": session_id,
            "bullet_points": bullet_points,
            "status": "finalized",
        }

    def get_extracted_experiences(self, user_id):
        """Get all finalized experiences for a user."""
        from experience_chat_db import get_extracted_experiences

        return get_extracted_experiences(user_id)

    def inject_context(self, session_id, user_id=None, uploaded_text="", source_filename=""):
        """Inject uploaded document context into an active session."""
        from experience_chat_stages import extract_fields_from_text

        session = self._get_session(session_id, user_id=user_id)
        if not session:
            return {"error": "Session not found"}
        if session["is_finalized"]:
            return {"error": "Session already finalized"}

        context = json.loads(session["context_json"])
        fields_updated = []

        uploaded_contexts = context.get("uploaded_contexts", [])
        uploaded_contexts.append({"source": source_filename, "text": uploaded_text[:8000]})
        context["uploaded_contexts"] = uploaded_contexts
        fields_updated.append("uploaded_contexts")

        extracted = extract_fields_from_text(uploaded_text)

        for field in ("responsibilities", "technologies", "outcomes", "challenges"):
            new_items = extracted.get(field, [])
            if new_items:
                existing = context.get(field, [])
                existing_lower = {item.lower() for item in existing}
                for item in new_items:
                    if item.lower() not in existing_lower:
                        existing.append(item)
                        existing_lower.add(item.lower())
                context[field] = existing
                fields_updated.append(field)

        if extracted.get("title") and not context.get("title"):
            context["title"] = extracted["title"]
            fields_updated.append("title")

        self._update_session(session_id, context_json=json.dumps(context))
        self._save_message(
            session_id,
            "assistant",
            f"I've reviewed the uploaded document ({source_filename}). "
            f"I found additional context for: "
            f"{', '.join(fields_updated) if fields_updated else 'general reference'}. "
            "Let me continue with more targeted questions based on this new information.",
        )

        return {"fields_updated": fields_updated, "stage": session["stage"]}

    # --- Private methods ---

    _SKIP_PHRASES = {
        "skip",
        "n/a",
        "na",
        "none",
        "no",
        "nothing",
        "not applicable",
        "don't know",
        "dont know",
        "not sure",
        "pass",
        "next",
    }

    def _is_sparse_response(self, message):
        """Check if user's response indicates they want to skip this stage."""
        msg = message.strip().lower().rstrip(".!?")
        if msg in self._SKIP_PHRASES:
            return True
        if len(msg) < 5 and not any(c.isdigit() for c in msg):
            return True
        return False

    def _advance_stage(self, current_stage, context, user_message):
        """Determine if we should advance to the next stage."""
        try:
            current_idx = STAGES.index(current_stage)
        except ValueError:
            return "intro"
        if current_stage == "complete":
            return "complete"
        skip = 1
        if current_stage not in ("intro", "role") and self._is_sparse_response(user_message):
            skip = 2
        next_idx = min(current_idx + skip, len(STAGES) - 1)
        return STAGES[next_idx]

    def _generate_response(self, session_id, context, new_stage, user_message):
        """Generate an AI response for the current stage."""
        from experience_chat_stages import call_llm_for_response, generate_template_question

        llm_response = call_llm_for_response(session_id, context, new_stage, user_message)
        if llm_response:
            return llm_response
        return generate_template_question(context, new_stage)

    def _split_items(self, text):
        """Split user text into individual items."""
        items = re.split(r"[,\n]|[-*•]\s+", text)
        return [item.strip() for item in items if item.strip() and len(item.strip()) > 2]

    def _get_session(self, session_id, user_id=None):
        """Fetch session from DB."""
        from experience_chat_db import get_session

        return get_session(session_id, user_id=user_id)

    def _get_messages(self, session_id):
        """Fetch all messages for a session."""
        from experience_chat_db import get_messages

        return get_messages(session_id)

    def _save_message(self, session_id, role, content):
        """Save a message to the session history."""
        from experience_chat_db import save_message

        save_message(session_id, role, content)

    def _update_session(self, session_id, **kwargs):
        """Update session fields."""
        from experience_chat_db import update_session

        update_session(session_id, **kwargs)


# Module-level singleton
_extractor = None


def get_experience_extractor():
    """Get singleton ExperienceExtractor instance."""
    global _extractor
    if _extractor is None:
        _extractor = ExperienceExtractor()
    return _extractor
