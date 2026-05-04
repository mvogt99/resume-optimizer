"""Cover Letter Agent — generates targeted cover letters via RTX 5090."""

import logging
import uuid
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseCareerAgent
from agents.cover_letter_helpers import STYLES, _CoverLetterHelpersMixin
from models import get_db

logger = logging.getLogger(__name__)


class CoverLetterAgent(_CoverLetterHelpersMixin, BaseCareerAgent):
    """Generates targeted cover letters with culture analysis, scoring, and refinement."""

    agent_type = "cover_letter"

    # ── Public API ──────────────────────────────────

    def generate_cover_letter(
        self,
        user_id: str,
        posting_id: str,
        style: str = "professional",
        preferences: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate a targeted cover letter for a job posting."""
        posting = self._get_posting(posting_id, user_id=user_id)
        if not posting:
            return {"error": "Posting not found"}
        jd_text = posting.get("description", "")
        if not jd_text:
            return {"error": "Posting has no job description"}

        profile = self._get_user_profile(user_id)
        profile_text = self._profile_summary(profile)

        # CT-4: Inject ArangoDB milestone context before generation
        arango_ctx = self._get_arango_context(user_id, self.agent_type)
        if arango_ctx:
            profile_text = f"{profile_text}\n\n<arango_context>\n{arango_ctx}\n</arango_context>"

        style = (style or "professional").lower()
        if style not in STYLES:
            style = "professional"

        company_name = posting.get("company", "")
        culture, c_dur = self._timed(self._analyze_company_culture, jd_text, company_name)
        if not culture:
            culture = self._fallback_culture(jd_text)

        job_req, r_dur = self._timed(self._extract_job_requirements, jd_text)
        structure = self._build_letter_structure(profile, job_req, culture, style)
        letter_result, g_dur = self._timed(
            self._generate_letter, structure, profile_text, posting, preferences
        )

        if not letter_result or not isinstance(letter_result, dict):
            self._log_run(
                user_id,
                f"Cover letter: {posting.get('title', '')}",
                {"posting_id": posting_id, "style": style},
                {"error": "LLM failed"},
                task_type="narrative_generation",
                duration_ms=c_dur + r_dur + g_dur,
                status="failed",
            )
            return {"error": "Failed to generate cover letter"}

        for f in ("subject", "greeting", "body", "closing"):
            if letter_result.get(f):
                letter_result[f] = self._replace_placeholders(letter_result[f], posting)

        score_result = self._score_letter(letter_result.get("body", ""), job_req, culture)
        version_num = self._next_version(user_id, posting_id)
        letter_id = str(uuid.uuid4())

        with get_db() as conn:
            conn.execute(
                "INSERT INTO cover_letters (id, user_id, posting_id, subject, greeting, "
                "body, closing, tone, company, role_title) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    letter_id,
                    user_id,
                    posting_id,
                    letter_result.get("subject", ""),
                    letter_result.get("greeting", ""),
                    letter_result.get("body", ""),
                    letter_result.get("closing", ""),
                    letter_result.get("tone", style),
                    company_name,
                    posting.get("title", ""),
                ),
            )
            conn.execute(
                "UPDATE job_postings SET cover_letter_id=?, "
                "updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (letter_id, posting_id),
            )
            conn.commit()

        self._log_run(
            user_id,
            f"Cover letter: {posting.get('title', '')}",
            {"posting_id": posting_id, "style": style, "preferences": preferences},
            {"letter_id": letter_id, "score": score_result.get("overall_score", 0)},
            task_type="narrative_generation",
            duration_ms=c_dur + r_dur + g_dur,
        )

        letter_result.update(
            id=letter_id,
            score=score_result.get("overall_score", 0),
            score_breakdown=score_result.get("breakdown", {}),
            style=style,
            version=version_num,
        )

        # CT-1: Record claim for accountability audit
        self._record_claim(
            user_id,
            "cover_letter",
            jd_text[:500],
            letter_result.get("body", "")[:500],
            metadata={
                "posting_id": posting_id,
                "style": style,
                "score": score_result.get("overall_score", 0),
            },
        )

        return letter_result

    def generate(
        self,
        user_id: str,
        posting_id: str,
        style: str = "professional",
        preferences: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Alias for generate_cover_letter (backward-compatible with routes)."""
        return self.generate_cover_letter(user_id, posting_id, style, preferences)

    def refine(self, user_id: str, posting_id: str, feedback: str) -> Dict[str, Any]:
        """Refine the latest cover letter for a posting based on feedback."""
        if not feedback or not feedback.strip():
            return {"error": "Feedback is required for refinement"}
        letter = self.get_for_posting(user_id, posting_id)
        if not letter:
            return {"error": "No cover letter found for this posting. Generate one first."}
        return self.regenerate(user_id, letter["id"], feedback)

    def regenerate(self, user_id: str, letter_id: str, feedback: str = "") -> Dict[str, Any]:
        """Regenerate a cover letter with optional user feedback."""
        letter = self.get_letter(letter_id, user_id=user_id)
        if not letter:
            return {"error": "Cover letter not found"}

        posting_id = letter.get("posting_id", "")
        posting = self._get_posting(posting_id, user_id=user_id) if posting_id else None
        profile_text = self._profile_summary(self._get_user_profile(user_id))
        jd_text = posting.get("description", "")[:2000] if posting else ""

        fb_section = ""
        if feedback:
            fb_section = f"\n\nUser feedback on the previous version:\n{feedback}"
        if letter.get("body"):
            fb_section += f"\n\nPrevious version (improve upon this):\n{letter['body'][:1500]}"

        style_name = letter.get("tone", "professional")
        prompt = (
            "Rewrite this cover letter based on the feedback provided.\n\n"
            f"STYLE: {style_name} — {STYLES.get(style_name, STYLES['professional'])}\n\n"
            'Return ONLY a JSON object: {{"subject":"...","greeting":"...","body":"...",'
            f'"closing":"...","tone":"{style_name}"}}\n\n'
            f"Job title: {letter.get('role_title', '')}\nCompany: {letter.get('company', '')}\n"
        )
        if jd_text:
            prompt += f"Job description:\n{jd_text}\n\n"
        prompt += f"Candidate profile:\n{profile_text}{fb_section}"

        result, duration = self._timed(
            self._call_llm_json, prompt, task_type="narrative_generation", max_tokens=2048
        )
        if not result or not isinstance(result, dict):
            return {"error": "Failed to regenerate cover letter"}

        for f in ("subject", "greeting", "body", "closing"):
            if result.get(f):
                result[f] = self._replace_placeholders(result[f], posting)

        job_req = self._extract_job_requirements(jd_text) if jd_text else {}
        culture = self._fallback_culture(jd_text) if jd_text else {}
        score_result = self._score_letter(result.get("body", ""), job_req, culture)
        version_num = self._next_version(user_id, posting_id)

        with get_db() as conn:
            conn.execute(
                "UPDATE cover_letters SET subject=?, greeting=?, body=?, closing=?, "
                "tone=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (
                    result.get("subject", letter.get("subject", "")),
                    result.get("greeting", letter.get("greeting", "")),
                    result.get("body", letter.get("body", "")),
                    result.get("closing", letter.get("closing", "")),
                    result.get("tone", style_name),
                    letter_id,
                ),
            )
            conn.commit()

        self._log_run(
            user_id,
            f"Regenerate cover letter: {letter.get('role_title', '')}",
            {"letter_id": letter_id, "feedback": feedback[:200]},
            {"letter_id": letter_id, "score": score_result.get("overall_score", 0)},
            task_type="narrative_generation",
            duration_ms=duration,
        )

        result.update(
            id=letter_id,
            score=score_result.get("overall_score", 0),
            score_breakdown=score_result.get("breakdown", {}),
            style=style_name,
            version=version_num,
        )
        return result

    def get_for_posting(self, user_id: str, posting_id: str) -> Optional[Dict[str, Any]]:
        """Get the latest cover letter for a posting."""
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM cover_letters WHERE user_id=? AND posting_id=? "
                "ORDER BY created_at DESC LIMIT 1",
                (user_id, posting_id),
            ).fetchone()
        return dict(row) if row else None

    def get_letter(self, letter_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get cover letter by ID."""
        from models import get_db

        with get_db() as conn:
            if user_id is not None:
                row = conn.execute(
                    "SELECT * FROM cover_letters WHERE id=? AND user_id=?", (letter_id, user_id)
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM cover_letters WHERE id=?", (letter_id,)
                ).fetchone()
        return dict(row) if row else None

    def get_versions(self, user_id: str, posting_id: str) -> List[Dict[str, Any]]:
        """List all cover letter versions for a posting, newest first."""
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM cover_letters WHERE user_id=? AND posting_id=? "
                "ORDER BY created_at DESC",
                (user_id, posting_id),
            ).fetchall()
        return [dict(r) for r in rows]

    def update(
        self, letter_id: str, updates: Dict[str, Any], user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Update cover letter fields (subject, greeting, body, closing, tone)."""
        allowed = {"subject", "greeting", "body", "closing", "tone"}
        sets: List[str] = []
        vals: List[Any] = []
        for k, v in updates.items():
            if k in allowed:
                sets.append(f"{k}=?")
                vals.append(v)
        if not sets:
            return None
        sets.append("updated_at=CURRENT_TIMESTAMP")
        from models import get_db

        with get_db() as conn:
            if user_id is not None:
                vals += [letter_id, user_id]
                conn.execute(
                    f"UPDATE cover_letters SET {','.join(sets)} WHERE id=? AND user_id=?", vals
                )
            else:
                vals.append(letter_id)
                conn.execute(f"UPDATE cover_letters SET {','.join(sets)} WHERE id=?", vals)
            conn.commit()
        return self.get_letter(letter_id, user_id=user_id)

    def delete(self, letter_id: str, user_id: Optional[str] = None) -> None:
        """Delete a cover letter."""
        from models import get_db

        with get_db() as conn:
            if user_id is not None:
                conn.execute(
                    "DELETE FROM cover_letters WHERE id=? AND user_id=?", (letter_id, user_id)
                )
            else:
                conn.execute("DELETE FROM cover_letters WHERE id=?", (letter_id,))
            conn.commit()
