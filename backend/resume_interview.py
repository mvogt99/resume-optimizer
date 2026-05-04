"""
Guided resume interview — builds a resume from scratch via conversational interview.

For non-tech users (teachers, nurses, tradespeople) with no existing resume.
8 fixed stages, loops for multiple jobs and education entries.
State machine in resume_interview_stages.py, parsing in resume_interview_parsers.py.
"""

import json
import logging
import uuid

from models import get_db

logger = logging.getLogger(__name__)

_EMPTY_EXPERIENCE = {"title": "", "employer": "", "start_date": "", "end_date": "", "duties": []}
_EMPTY_EDUCATION = {"degree": "", "school": "", "year": "", "honors": ""}


class ResumeInterviewer:
    """Public API for the guided resume interview state machine."""

    def start_session(self, user_id):
        """Start a new interview session and return the opening message."""
        from resume_interview_stages import TEMPLATE_QUESTIONS, progress_info

        session_id = str(uuid.uuid4())
        context = {
            "name": "",
            "preferred_name": "",
            "email": "",
            "phone": "",
            "location": "",
            "career_field": "",
            "years_experience": "",
            "objective": "",
            "experiences": [],
            "education": [],
            "hard_skills": [],
            "soft_skills": [],
            "certifications": [],
            "volunteer": "",
            "awards": "",
            "languages": "",
            "publications": "",
        }

        with get_db() as conn:
            conn.execute(
                "INSERT INTO resume_interview_sessions "
                "(id, user_id, stage, sub_stage, context_json, experience_index, education_index) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, int(user_id), "welcome", "", json.dumps(context), 0, 0),
            )
            conn.commit()

        opening = TEMPLATE_QUESTIONS["welcome"]
        self._save_message(session_id, "assistant", opening, "welcome")

        return {
            "session_id": session_id,
            "stage": "welcome",
            "sub_stage": "",
            "message": opening,
            "progress": progress_info("welcome"),
        }

    def process_message(self, session_id, user_message, user_id=None):
        """Process a user message and advance the conversation."""
        from resume_interview_stages import advance_stage, progress_info

        session = self._get_session(session_id, user_id=user_id)
        if not session:
            return {"error": "Session not found"}
        if session["is_finalized"]:
            return {"error": "Session already finalized", "session_id": session_id}

        self._save_message(session_id, "user", user_message, session["stage"])

        stage = session["stage"]
        sub_stage = session["sub_stage"] or ""
        context = json.loads(session["context_json"])
        exp_idx = session["experience_index"]
        edu_idx = session["education_index"]

        # Extract structured data from the message
        context, exp_idx, edu_idx = self._extract_data(
            stage, sub_stage, user_message, context, exp_idx, edu_idx
        )

        # Advance to the next stage
        new_stage, new_sub, new_exp_idx, new_edu_idx = advance_stage(
            stage, sub_stage, user_message, context, exp_idx, edu_idx
        )

        # Generate the response
        ai_response = self._generate_response(
            new_stage, new_sub, user_message, context, new_exp_idx
        )

        with get_db() as conn:
            conn.execute(
                "UPDATE resume_interview_sessions "
                "SET stage=?, sub_stage=?, context_json=?, experience_index=?, "
                "education_index=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (new_stage, new_sub, json.dumps(context), new_exp_idx, new_edu_idx, session_id),
            )
            conn.commit()

        self._save_message(session_id, "assistant", ai_response, new_stage)

        return {
            "session_id": session_id,
            "stage": new_stage,
            "sub_stage": new_sub,
            "message": ai_response,
            "context": context,
            "progress": progress_info(new_stage),
            "is_complete": new_stage == "complete",
            "show_finalize": new_stage == "review",
        }

    def get_session_state(self, session_id, user_id=None):
        """Return current state and full message history."""
        from resume_interview_stages import progress_info

        session = self._get_session(session_id, user_id=user_id)
        if not session:
            return {"error": "Session not found"}

        messages = self._get_messages(session_id)
        context = json.loads(session["context_json"])

        return {
            "session_id": session_id,
            "stage": session["stage"],
            "sub_stage": session["sub_stage"] or "",
            "context": context,
            "messages": messages,
            "progress": progress_info(session["stage"]),
            "is_finalized": bool(session["is_finalized"]),
            "show_finalize": session["stage"] == "review",
        }

    def compile_preview(self, session_id, user_id=None):
        """Compile context into resume text without saving."""
        from resume_interview_compiler import compile_resume

        session = self._get_session(session_id, user_id=user_id)
        if not session:
            return {"error": "Session not found"}

        context = json.loads(session["context_json"])
        resume_text = compile_resume(context)

        return {
            "session_id": session_id,
            "compiled_text": resume_text,
            "context": context,
        }

    def finalize_to_resume(self, session_id, edits=None, user_id=None):
        """Compile and save the resume as a resume_version + resumes row."""
        import os

        from flask import current_app
        from models import Resume, ResumeVersion
        from resume_interview_compiler import compile_resume

        session = self._get_session(session_id, user_id=user_id)
        if not session:
            return {"error": "Session not found"}

        context = json.loads(session["context_json"])
        if edits and isinstance(edits, dict):
            context.update(edits)

        resume_text = compile_resume(context)
        name = context.get("preferred_name") or context.get("name") or "Resume"
        file_name = f"Resume — {name} (Interview)"

        version = ResumeVersion.create(
            user_id=int(user_id),
            source="interview",
            file_name=file_name,
            parsed_text=resume_text,
            source_id=session_id,
            metadata_json=json.dumps(
                {
                    "career_field": context.get("career_field", ""),
                    "interview_session_id": session_id,
                }
            ),
        )

        filename = f"{uuid.uuid4()}_interview_resume.txt"
        upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
        file_path = os.path.join(upload_folder, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(resume_text)

        resume = Resume.create(int(user_id), file_name, file_path)

        with get_db() as conn:
            conn.execute(
                "UPDATE resume_interview_sessions "
                "SET is_finalized=1, compiled_text=?, context_json=?, "
                "updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (resume_text, json.dumps(context), session_id),
            )
            conn.commit()

        return {
            "session_id": session_id,
            "version_id": version.id,
            "resume_id": resume.id,
            "file_name": file_name,
            "compiled_text": resume_text,
            "status": "saved",
            "message": "Your resume has been saved!",
        }

    # ─── Private helpers ──────────────────────────────────────────────────────

    def _get_session(self, session_id, user_id=None):
        with get_db() as conn:
            if user_id is not None:
                row = conn.execute(
                    "SELECT * FROM resume_interview_sessions WHERE id=? AND user_id=?",
                    (session_id, int(user_id)),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM resume_interview_sessions WHERE id=?",
                    (session_id,),
                ).fetchone()
        return dict(row) if row else None

    def _save_message(self, session_id, role, content, stage=""):
        with get_db() as conn:
            conn.execute(
                "INSERT INTO resume_interview_messages (session_id, role, content, stage) "
                "VALUES (?, ?, ?, ?)",
                (session_id, role, content, stage),
            )
            conn.commit()

    def _get_messages(self, session_id):
        with get_db() as conn:
            rows = conn.execute(
                "SELECT role, content, stage, created_at FROM resume_interview_messages "
                "WHERE session_id=? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def _extract_data(self, stage, sub_stage, message, context, exp_idx, edu_idx):
        """Parse user message and store structured data in context."""
        from resume_interview_parsers import (
            extract_dates,
            extract_email,
            extract_honors,
            extract_location,
            extract_name,
            extract_phone,
            extract_skills,
            split_duties,
        )

        msg = message.strip()

        if stage == "welcome":
            if not context.get("name"):
                context["name"] = extract_name(msg)
                context["preferred_name"] = context["name"]
            elif not context.get("_welcome_done"):
                from resume_interview_parsers import is_affirmative

                if not is_affirmative(msg):
                    alt = extract_name(msg)
                    if alt:
                        context["preferred_name"] = alt
                context["_welcome_done"] = True

        elif stage == "contact":
            email = extract_email(msg)
            phone = extract_phone(msg)
            if email:
                context["email"] = email
            if phone:
                context["phone"] = phone
            if context.get("email") and context.get("phone") and not context.get("location"):
                loc = extract_location(msg)
                if loc:
                    context["location"] = loc
            elif not context.get("location") and not email and not phone:
                context["location"] = extract_location(msg) or msg.strip()

        elif stage == "objective":
            if not context.get("career_field"):
                context["career_field"] = msg
                import re

                years_match = re.search(r"(\d+)\s*(?:year|yr)", msg, re.I)
                if years_match:
                    context["years_experience"] = years_match.group(1)
            elif not context.get("objective"):
                context["objective"] = msg

        elif stage == "experience":
            while len(context["experiences"]) <= exp_idx:
                context["experiences"].append(dict(_EMPTY_EXPERIENCE))
            exp = context["experiences"][exp_idx]
            if sub_stage in ("", "exp_title"):
                if not exp.get("title"):
                    exp["title"] = msg.strip()
            elif sub_stage == "exp_employer":
                exp["employer"] = msg.strip()
            elif sub_stage == "exp_dates":
                start, end = extract_dates(msg)
                exp["start_date"] = start
                exp["end_date"] = end
            elif sub_stage in ("exp_duties", "exp_more"):
                exp["duties"].extend(split_duties(msg))
            context["experiences"][exp_idx] = exp

        elif stage == "education":
            while len(context["education"]) <= edu_idx:
                context["education"].append(dict(_EMPTY_EDUCATION))
            edu = context["education"][edu_idx]
            if sub_stage in ("", "edu_degree"):
                edu["degree"] = msg.strip()
            elif sub_stage == "edu_school":
                edu["school"] = msg.strip()
            elif sub_stage == "edu_year":
                import re

                year_match = re.search(r"(\d{4})", msg)
                edu["year"] = year_match.group(1) if year_match else msg.strip()
                honors = extract_honors(msg)
                if honors:
                    edu["honors"] = honors
            context["education"][edu_idx] = edu

        elif stage == "skills":
            context = extract_skills(msg, context)

        elif stage == "optional":
            low = msg.lower()
            if not any(w in low[:20] for w in ["none", "skip", "no "]):
                if any(w in low for w in ["volunteer", "coach", "church", "community"]):
                    context["volunteer"] = msg
                if any(w in low for w in ["award", "recognition", "honor", "employee of", "dean"]):
                    context["awards"] = msg
                if any(w in low for w in ["language", "spanish", "french", "bilingual"]):
                    context["languages"] = msg
                if any(w in low for w in ["publish", "article", "paper", "book", "project"]):
                    context["publications"] = msg
                if not any(
                    [
                        context.get("volunteer"),
                        context.get("awards"),
                        context.get("languages"),
                        context.get("publications"),
                    ]
                ):
                    context["volunteer"] = msg

        return context, exp_idx, edu_idx

    def _generate_response(self, stage, sub_stage, user_message, context, exp_idx):
        """Generate AI response — LLM first, template fallback."""
        try:
            return self._llm_response(stage, sub_stage, user_message, context, exp_idx)
        except Exception as e:
            logger.debug("LLM unavailable, using template: %s", e)
            from resume_interview_stages import get_template_response

            return get_template_response(stage, sub_stage, context, exp_idx)

    def _llm_response(self, stage, sub_stage, user_message, context, exp_idx):
        """Ask the local LLM for a warm, contextual response."""
        from resume_interview_stages import get_template_response
        from smart_llm import call_smart

        name = context.get("preferred_name") or context.get("name") or "there"
        next_q = get_template_response(stage, sub_stage, context, exp_idx)

        if sub_stage == "exp_more":
            # For exp_more, the template already contains duty confirmation + strength
            # feedback. The LLM must not re-ask what they did or add examples.
            system = (
                "You are a warm, encouraging resume coach. "
                "The user just shared job responsibilities. "
                "Write ONE short sentence acknowledging what they contributed "
                "(e.g. 'That sounds like meaningful work!'). "
                "Then output the NEXT MESSAGE below EXACTLY — do not paraphrase, "
                "do not add examples, do not ask them to list more duties again."
            )
            prompt = (
                f"{system}\n\n"
                f"User's name: {name}.\n"
                f'They just said: "{user_message[:300]}"\n\n'
                f"ONE warm sentence, then output exactly:\n{next_q}"
            )
        else:
            system = (
                "You are a warm, encouraging resume coach helping a non-technical user "
                "build their resume from scratch. Use simple, friendly language. No jargon. "
                "Keep your response to 2-3 sentences. Acknowledge what they said, "
                "then ask the next question exactly as provided."
            )
            prompt = (
                f"{system}\n\n"
                f"User's name: {name}. Current stage: {stage} / {sub_stage}.\n"
                f'They said: "{user_message}"\n\n'
                f"Acknowledge warmly (1 sentence), then ask:\n{next_q}"
            )

        response = call_smart(
            prompt,
            task_type="interview",
            task_hint="resume coaching non-tech friendly",
            max_tokens=300,
            temperature=0.7,
        )
        return response if response and len(response) > 20 else next_q


# ─── Singleton ────────────────────────────────────────────────────────────────

_interviewer = None


def get_resume_interviewer():
    global _interviewer
    if _interviewer is None:
        _interviewer = ResumeInterviewer()
    return _interviewer
