"""ATS Score Improvement Chat — state machine: diagnose → improve → confirming → rewrite → review.

Modules:
  ats_improvement_db.py      — DB CRUD helpers
  ats_improvement_prompts.py — LLM prompt builders
  resume_corrections.py      — persistent user corrections (Fix A + Fix B)
"""

import uuid

import ats_improvement_db as _db
import ats_improvement_prompts as _p
from resume_corrections import apply_corrections, get_corrections, save_correction

STAGES = ["diagnose", "improve", "confirming", "rewrite", "review"]

_instance = None


def get_ats_improvement_chat():
    global _instance
    if _instance is None:
        _instance = ATSImprovementChat()
    return _instance


class ATSImprovementChat:
    def __init__(self):
        _db.init_ats_tables()

    # ── Public API ──────────────────────────────────────────────────────────

    def start_session(self, user_id, resume_id, score_data):
        """Create session. Opening message includes remembered corrections (Fix E)."""
        session_id = str(uuid.uuid4())
        _db.create_session(session_id, user_id, resume_id, score_data)

        # Fix E: load and display remembered corrections
        remembered = get_corrections(user_id=user_id, resume_id=str(resume_id) if resume_id else None)
        opening = _p.build_diagnostic(score_data, remembered_count=len(remembered))
        _db.save_message(session_id, "assistant", opening)
        return {"session_id": session_id, "message": opening, "stage": "diagnose"}

    def send_message(self, session_id, user_message, user_id=None):
        session = _db.get_session(session_id, user_id=user_id)
        if not session:
            return {"message": "Session not found.", "stage": "unknown", "is_complete": False}
        _db.save_message(session_id, "user", user_message)
        stage = session["stage"]
        import json
        score_data = json.loads(session["score_json"] or "{}")
        messages = _db.get_messages(session_id)
        handlers = {
            "diagnose":   lambda: self._handle_diagnose(session_id, user_message, score_data, messages),
            "improve":    lambda: self._handle_improve(session_id, user_message, score_data, session, messages),
            "confirming": lambda: self._handle_confirming(session_id, user_message, score_data, session, messages),
            "rewrite":    lambda: self._handle_rewrite(session_id, user_message, score_data, session, messages),
            "review":     lambda: self._handle_review(session_id, user_message, session, score_data),
        }
        return handlers.get(stage, lambda: {"message": "Session complete.", "stage": stage, "is_complete": True})()

    def get_improved_resume(self, session_id, user_id=None):
        session = _db.get_session(session_id, user_id=user_id)
        return session["optimized_resume_text"] if session else None

    # ── Corrections management (Fix A / Fix E) ──────────────────────────────

    def add_correction(self, user_id, old_text, new_text, resume_id=None):
        return save_correction(user_id, old_text, new_text, resume_id=resume_id)

    def list_corrections(self, user_id, resume_id=None):
        return get_corrections(user_id, resume_id=resume_id)

    # ── Stage handlers ───────────────────────────────────────────────────────

    def _handle_diagnose(self, session_id, user_message, score_data, messages):
        msg_lower = user_message.lower()
        # Fix E: handle "show corrections" command
        if "show corrections" in msg_lower or "show remembered" in msg_lower:
            session = _db.get_session(session_id)
            return self._show_corrections_message(session_id, session)

        focus = "keywords"
        if any(w in msg_lower for w in ["keyword", "missing", "term", "1", "one"]):
            focus = "keywords"
        elif any(w in msg_lower for w in ["semantic", "language", "tone", "rephras", "2", "two"]):
            focus = "semantic"
        elif any(w in msg_lower for w in ["skill", "endors", "3", "three"]):
            focus = "skills"
        elif any(w in msg_lower for w in ["section", "structure", "heading", "4", "four"]):
            focus = "sections"
        elif any(w in msg_lower for w in ["all", "everything", "comprehensive"]):
            focus = "comprehensive"

        _db.update_session(session_id, stage="improve", improvement_focus=focus)
        response = _p.generate_improvement_suggestions(score_data, focus, messages)
        _db.save_message(session_id, "assistant", response)
        return {"message": response, "stage": "improve", "is_complete": False}

    def _handle_improve(self, session_id, user_message, score_data, session, messages):
        msg_lower = user_message.lower()

        # Fix D: if user is modifying/approving suggestions, go to confirming stage
        has_corrections = "replace" in msg_lower and "with" in msg_lower
        wants_apply = has_corrections or any(w in msg_lower for w in [
            "apply", "go ahead", "proceed", "do it", "generate", "yes", "make the following",
            "with the following", "then rescore", "rewrite", "use suggestions",
        ])

        if wants_apply:
            # Extract any inline corrections before confirming
            inline = _p.extract_user_corrections([{"role": "user", "content": user_message}])
            # Build summary of what will be applied for user confirmation (Fix D)
            summary_lines = ["Based on your instructions, I'll apply these changes:"]
            for old, new in inline:
                summary_lines.append(f'- Replace **"{old[:80]}"** → **"{new[:80]}"**')
            if not inline:
                summary_lines.append("- Apply the suggestions discussed above as-is.")

            # Save pending suggestion context
            _db.update_session(session_id, stage="confirming")
            response = _p.build_confirmation("\n".join(summary_lines))
            _db.save_message(session_id, "assistant", response)
            return {"message": response, "stage": "confirming", "is_complete": False}

        # Continue discussion
        response = _p.chat_with_context(score_data, session, messages, user_message)
        _db.save_message(session_id, "assistant", response)
        return {"message": response, "stage": "improve", "is_complete": False}

    def _handle_confirming(self, session_id, user_message, score_data, session, messages):
        """Fix D: user sees the confirmation summary and either approves or adjusts."""
        msg_lower = user_message.lower()
        confirmed = any(w in msg_lower for w in ["yes", "correct", "go ahead", "proceed", "ok", "looks good"])

        if confirmed:
            _db.update_session(session_id, stage="rewrite")
            # Fix A: pass persisted corrections into the LLM prompt AND apply post-hoc
            persisted = self._get_persisted_list(session)
            improved = _p.generate_improved_resume(score_data, session, messages,
                                                    persisted_corrections=persisted)
            improved = self._apply_persisted(improved, session)
            _db.update_session(session_id, optimized_resume_text=improved)
            response = (
                "Here's your improved resume:\n\n---\n"
                f"{improved}\n---\n\n"
                "Review the changes. Say **accept** to finalize, describe adjustments, or say **re-score**."
            )
            _db.save_message(session_id, "assistant", response)
            return {"message": response, "stage": "rewrite", "is_complete": False, "improved_text": improved}

        # User wants to adjust — go back to improve
        _db.update_session(session_id, stage="improve")
        response = _p.chat_with_context(score_data, session, messages, user_message)
        _db.save_message(session_id, "assistant", response)
        return {"message": response, "stage": "improve", "is_complete": False}

    def _handle_rewrite(self, session_id, user_message, score_data, session, messages):
        msg_lower = user_message.lower()

        if any(w in msg_lower for w in ["re-score", "rescore", "score it", "what's my score", "what is my score"]):
            current_text = session.get("optimized_resume_text", "")
            _db.save_message(session_id, "assistant", "Rescoring your improved resume…")
            return {"message": "Rescoring your improved resume…", "stage": "rewrite",
                    "is_complete": False, "rescore_request": True, "improved_text": current_text}

        if any(w in msg_lower for w in ["accept", "looks good", "done", "finalize", "perfect"]):
            _db.update_session(session_id, stage="review", is_finalized=1)
            response = "Saved. Use the Re-Score button for the updated ATS score, or describe more changes."
            _db.save_message(session_id, "assistant", response)
            return {"message": response, "stage": "review", "is_complete": True,
                    "improved_text": session["optimized_resume_text"]}

        # Fix A: inline replace instructions — apply directly + persisted corrections
        corrections = _p.extract_user_corrections([{"role": "user", "content": user_message}])
        current_text = session.get("optimized_resume_text", "")
        if corrections and current_text:
            improved = _p.enforce_corrections(current_text, corrections)
            improved = self._apply_persisted(improved, session)
            if improved != current_text:
                _db.update_session(session_id, optimized_resume_text=improved)
                applied = [f'"{old[:60]}" → "{new[:60]}"' for old, new in corrections]
                response = (
                    f"Applied {len(applied)} correction(s):\n"
                    + "\n".join(f"- {a}" for a in applied)
                    + "\n\nSay **accept** to finalize, **re-score**, or describe more changes."
                )
                _db.save_message(session_id, "assistant", response)
                return {"message": response, "stage": "rewrite", "is_complete": False, "improved_text": improved}

        persisted = self._get_persisted_list(session)
        improved = _p.generate_improved_resume(score_data, session, messages,
                                                persisted_corrections=persisted)
        improved = self._apply_persisted(improved, session)
        _db.update_session(session_id, optimized_resume_text=improved)
        response = (
            "Here's the updated version:\n\n---\n"
            f"{improved}\n---\n\n"
            "Say **accept** to finalize, **re-score**, or describe more changes."
        )
        _db.save_message(session_id, "assistant", response)
        return {"message": response, "stage": "rewrite", "is_complete": False, "improved_text": improved}

    def _handle_review(self, session_id, user_message, session, score_data):
        msg_lower = user_message.lower()

        if any(w in msg_lower for w in ["re-score", "rescore", "score"]):
            current_text = session.get("optimized_resume_text", "")
            _db.save_message(session_id, "assistant", "Rescoring your improved resume…")
            return {"message": "Rescoring your improved resume…", "stage": "review",
                    "is_complete": True, "rescore_request": True, "improved_text": current_text}

        if any(w in msg_lower for w in ["change", "adjust", "update", "modify", "improve",
                                         "fix", "edit", "replace", "make", "add", "remove"]):
            _db.update_session(session_id, stage="rewrite", is_finalized=0)
            response = "Sure — describe the changes or use 'replace \"X\" with \"Y\"'. Say **accept** when done."
            _db.save_message(session_id, "assistant", response)
            return {"message": response, "stage": "rewrite", "is_complete": False,
                    "improved_text": session["optimized_resume_text"]}

        # Fix E: handle show corrections
        if "show corrections" in msg_lower:
            return self._show_corrections_message(session_id, session)

        response = "Finalized. Use the Re-Score button or describe any further changes."
        _db.save_message(session_id, "assistant", response)
        return {"message": response, "stage": "review", "is_complete": True,
                "improved_text": session["optimized_resume_text"]}

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _get_persisted_list(self, session: dict) -> list:
        """Return persisted corrections for this session's user/resume as a list of dicts."""
        user_id = session.get("user_id")
        resume_id = session.get("resume_id")
        if not user_id:
            return []
        return get_corrections(
            user_id=user_id,
            resume_id=str(resume_id) if resume_id else None,
        )

    def _apply_persisted(self, text: str, session: dict) -> str:
        """Fix A: apply all persisted corrections for this user/resume after LLM generation."""
        user_id = session.get("user_id")
        resume_id = session.get("resume_id")
        if not user_id:
            return text
        corrected, applied, failed = apply_corrections(
            text, user_id=user_id, resume_id=str(resume_id) if resume_id else None
        )
        return corrected

    def _show_corrections_message(self, session_id: str, session: dict) -> dict:
        """Fix E: display remembered corrections with removal instructions."""
        user_id = session.get("user_id") if session else None
        resume_id = session.get("resume_id") if session else None
        corrections = get_corrections(
            user_id=user_id,
            resume_id=str(resume_id) if resume_id else None,
        ) if user_id else []
        if not corrections:
            response = "No remembered corrections saved yet."
        else:
            lines = [f"**{len(corrections)} remembered correction(s)** that apply to every generated resume:\n"]
            for c in corrections:
                scope = f" (resume {c['resume_id']})" if c["resume_id"] else " (all resumes)"
                lines.append(f"**#{c['id']}**{scope}: \"{c['old_text'][:60]}\" → \"{c['new_text'][:60]}\"")
            lines.append("\nTo remove one, use the corrections panel in the UI or reply **remove #ID**.")
            response = "\n".join(lines)
        _db.save_message(session_id, "assistant", response)
        stage = session.get("stage", "diagnose") if session else "diagnose"
        return {"message": response, "stage": stage, "is_complete": False}
