"""
Gap-driven agentic interview for the resume builder.
Identifies gaps between resume + selected sources vs job description,
then conducts a multi-topic interview to fill those gaps.
"""

import json
import os
import sqlite3
import uuid

from models import get_db

HARNESS_URL = os.environ.get("HARNESS_URL", "http://localhost:8000/api/harness/run")


def init_builder_interview_tables():
    """Create builder interview tables if they don't exist."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS builder_interview_sessions (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                builder_session_id TEXT NOT NULL,
                job_text TEXT DEFAULT '',
                gaps_json TEXT DEFAULT '[]',
                extracted_json TEXT DEFAULT '[]',
                stage TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS builder_interview_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES builder_interview_sessions (id)
            )
        """
        )
        try:  # noqa: SIM105
            cursor.execute(
                "ALTER TABLE builder_interview_sessions "
                "ADD COLUMN cross_source_json TEXT DEFAULT '{}'"
            )
        except sqlite3.OperationalError:
            pass  # Column already exists
        conn.commit()


class BuilderInterviewer:
    """Gap-driven interview that identifies and fills resume gaps."""

    def __init__(self):
        init_builder_interview_tables()

    def start_session(self, user_id, builder_session_id, job_text, current_gaps):
        """Start a new gap-driven interview session."""
        from builder_interview_stages import build_cross_source_context, generate_gap_question

        session_id = str(uuid.uuid4())
        cross_source = build_cross_source_context(builder_session_id)

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO builder_interview_sessions "
                "(id, user_id, builder_session_id, job_text, gaps_json, cross_source_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    user_id,
                    builder_session_id,
                    job_text,
                    json.dumps(current_gaps),
                    json.dumps(cross_source),
                ),
            )
            conn.commit()

        gap_count = len(current_gaps)
        if gap_count == 0:
            opening = (
                "Your resume already covers the job requirements well! "
                "Is there any additional experience you'd like to highlight?"
            )
        else:
            categories = {}
            for gap in current_gaps:
                cat = gap.get("category", "general")
                categories.setdefault(cat, []).append(gap.get("skill", ""))

            gap_summary = []
            for cat, skills in categories.items():
                gap_summary.append(f"**{cat.title()}**: {', '.join(skills[:5])}")

            opening = (
                f"I've identified {gap_count} areas where your resume could be strengthened "
                f"for this role:\n\n"
                + "\n".join(gap_summary)
                + "\n\nLet's start with the most important gaps. "
            )

            first_gap = current_gaps[0]
            first_outcome_hint = (
                cross_source.get("outcomes", [None])[0] if cross_source.get("outcomes") else None
            )
            opening += generate_gap_question([first_gap], {}, outcome_hint=first_outcome_hint)

        self._save_message(session_id, "assistant", opening)

        return {
            "session_id": session_id,
            "message": opening,
            "gaps_identified": gap_count,
            "gap_tracking": self._build_gap_tracking(current_gaps, []),
        }

    def process_message(self, session_id, user_message, user_id=None):
        """Process user response, extract content, generate follow-up."""
        from builder_interview_stages import (
            call_llm_followup,
            call_llm_followup_v2,
            extract_bullets_from_response,
            extract_bullets_llm,
            generate_gap_question,
            reprioritize_gaps,
        )

        session = self._get_session(session_id, user_id=user_id)
        if not session:
            return {"error": "Session not found"}

        if session["stage"] == "complete":
            extracted = self._get_extracted(session_id)
            return {
                "session_id": session_id,
                "message": "This interview is already complete. Review your extracted content.",
                "extracted_bullets": extracted,
                "gaps_remaining": 0,
                "is_complete": True,
                "gap_tracking": self._build_gap_tracking([], extracted),
            }

        self._save_message(session_id, "user", user_message)

        gaps = json.loads(session["gaps_json"])
        extracted = json.loads(session["extracted_json"])
        job_text = session.get("job_text", "")
        cross_source = {}
        if session.get("cross_source_json"):
            try:  # noqa: SIM105
                cross_source = json.loads(session["cross_source_json"])
            except (json.JSONDecodeError, TypeError):
                pass

        new_bullets = extract_bullets_llm(user_message, gaps, job_text, HARNESS_URL)
        if not new_bullets:
            new_bullets = extract_bullets_from_response(user_message, gaps)
        extracted.extend(new_bullets)

        addressed_skills = set()
        for bullet in extracted:
            for skill in bullet.get("related_skills", []):
                addressed_skills.add(skill.lower())

        remaining_gaps = [g for g in gaps if g.get("skill", "").lower() not in addressed_skills]

        if remaining_gaps and len(remaining_gaps) > 1:
            reprioritized = reprioritize_gaps(remaining_gaps, extracted, user_message, job_text)
            if reprioritized:
                remaining_gaps = reprioritized

        is_complete = len(remaining_gaps) == 0
        if is_complete:
            response = (
                "Excellent! I've captured enough to address the key gaps. "
                "You can review the extracted content and add it to your resume."
            )
            stage = "complete"
        else:
            response = call_llm_followup_v2(
                session_id, remaining_gaps, extracted, user_message, cross_source
            )
            if not response:
                response = call_llm_followup(session_id, remaining_gaps, extracted, user_message)
            if not response:
                next_outcome_hint = None
                if cross_source.get("outcomes") and remaining_gaps:
                    next_skill = remaining_gaps[0].get("skill", "").lower()
                    for o in cross_source.get("outcomes", []):
                        if next_skill in o.get("title", "").lower():
                            next_outcome_hint = o
                            break
                    if not next_outcome_hint:
                        next_outcome_hint = (
                            cross_source["outcomes"][0] if cross_source["outcomes"] else None
                        )
                response = generate_gap_question(
                    remaining_gaps,
                    {"last_message": user_message},
                    outcome_hint=next_outcome_hint,
                )
            stage = "active"

        self._save_message(session_id, "assistant", response)
        self._update_session(
            session_id,
            extracted_json=json.dumps(extracted),
            gaps_json=json.dumps(remaining_gaps),
            stage=stage,
        )

        bullets_with_metrics = sum(1 for b in extracted if b.get("has_metrics"))
        bullets_star_complete = sum(1 for b in extracted if b.get("star_complete"))

        return {
            "session_id": session_id,
            "message": response,
            "extracted_bullets": extracted,
            "gaps_remaining": len(remaining_gaps),
            "is_complete": is_complete,
            "gap_tracking": {
                "total_gaps": len(remaining_gaps) + len(addressed_skills),
                "addressed": len(addressed_skills),
                "remaining": len(remaining_gaps),
                "coverage_percent": round(
                    len(addressed_skills)
                    / max(len(remaining_gaps) + len(addressed_skills), 1)
                    * 100,
                    1,
                ),
                "bullets_with_metrics": bullets_with_metrics,
                "bullets_star_complete": bullets_star_complete,
            },
        }

    def get_extracted_content(self, session_id):
        """Return all extracted STAR bullets organized by skill."""
        session = self._get_session(session_id)
        if not session:
            return {"error": "Session not found"}

        extracted = json.loads(session["extracted_json"])
        by_skill = {}
        for bullet in extracted:
            for skill in bullet.get("related_skills", ["general"]):
                by_skill.setdefault(skill, []).append(bullet)

        return {
            "session_id": session_id,
            "bullets": extracted,
            "by_skill": by_skill,
            "total": len(extracted),
            "stage": session["stage"],
        }

    # --- Helper: Gap tracking summary ---

    def _build_gap_tracking(self, all_gaps, extracted):
        """Build gap tracking summary dict."""
        addressed = set()
        for bullet in extracted:
            for skill in bullet.get("related_skills", []):
                addressed.add(skill.lower())
        total = len(all_gaps) + len(addressed)
        bullets_with_metrics = sum(1 for b in extracted if b.get("has_metrics"))
        bullets_star_complete = sum(1 for b in extracted if b.get("star_complete"))
        return {
            "total_gaps": total if total > 0 else len(all_gaps),
            "addressed": len(addressed),
            "remaining": max(total - len(addressed), len(all_gaps)),
            "coverage_percent": round(len(addressed) / max(total, 1) * 100, 1),
            "bullets_with_metrics": bullets_with_metrics,
            "bullets_star_complete": bullets_star_complete,
        }

    def _get_session(self, session_id, user_id=None):
        """Fetch session from DB, optionally filtering by user_id."""
        with get_db() as conn:
            if user_id is not None:
                row = conn.execute(
                    "SELECT * FROM builder_interview_sessions WHERE id = ? AND user_id = ?",
                    (session_id, user_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM builder_interview_sessions WHERE id = ?",
                    (session_id,),
                ).fetchone()

        if not row:
            return None

        result = {
            "id": row[0],
            "user_id": row[1],
            "builder_session_id": row[2],
            "job_text": row[3] or "",
            "gaps_json": row[4] or "[]",
            "extracted_json": row[5] or "[]",
            "stage": row[6] or "active",
            "created_at": row[7],
            "updated_at": row[8],
        }
        if len(row) > 9:
            result["cross_source_json"] = row[9] or "{}"
        return result

    def _get_extracted(self, session_id):
        """Get just the extracted bullets for a session."""
        session = self._get_session(session_id)
        if not session:
            return []
        return json.loads(session["extracted_json"])

    def _save_message(self, session_id, role, content):
        """Save a message to the session history."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO builder_interview_messages "
                "(session_id, role, content) VALUES (?, ?, ?)",
                (session_id, role, content),
            )
            conn.commit()

    _ALLOWED_COLUMNS = {"stage", "context_json", "is_finalized", "extracted_json", "gaps_json"}

    def _update_session(self, session_id, **kwargs):
        """Update session fields (column allowlist prevents SQL injection)."""
        if not kwargs:
            return

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
                f"UPDATE builder_interview_sessions SET {', '.join(sets)} WHERE id = ?",
                values,
            )
            conn.commit()


# Module-level singleton
_interviewer = None


def get_builder_interviewer():
    """Get singleton BuilderInterviewer instance."""
    global _interviewer
    if _interviewer is None:
        _interviewer = BuilderInterviewer()
    return _interviewer
