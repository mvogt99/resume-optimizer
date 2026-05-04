"""
Resume builder orchestrator.
Aggregates resume content from multiple sources (LinkedIn, projects, journey, experiences)
and builds enriched resumes optimized for specific job descriptions.
"""

import json
import uuid

from models import get_db
from nlp_engine import calculate_similarity, extract_keywords, extract_skill_phrases
from resume_builder_loaders import ResumeBuilderLoaderMixin, _safe_json, init_builder_tables


class ResumeBuilder(ResumeBuilderLoaderMixin):
    """Orchestrates resume building from multiple data sources."""

    def __init__(self):
        init_builder_tables()

    def create_session(self, user_id, base_version_id=None, job_text=""):
        """Create a new builder session."""
        session_id = str(uuid.uuid4())
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO builder_sessions (id, user_id, base_version_id, job_text) "
                "VALUES (?, ?, ?, ?)",
                (session_id, user_id, base_version_id, job_text),
            )
            conn.commit()
        return session_id

    def get_session(self, session_id, user_id=None):
        """Get a builder session by ID, optionally filtered by user_id."""
        from models import get_db

        with get_db() as conn:
            if user_id is not None:
                row = conn.execute(
                    "SELECT * FROM builder_sessions WHERE id = ? AND user_id = ?",
                    (session_id, user_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM builder_sessions WHERE id = ?", (session_id,)
                ).fetchone()

        if not row:
            return None

        return {
            "id": row[0],
            "user_id": row[1],
            "base_version_id": row[2],
            "job_text": row[3] or "",
            "sources_json": row[4] or "{}",
            "compiled_text": row[5] or "",
            "status": row[6] or "draft",
            "created_at": row[7],
            "updated_at": row[8],
        }

    def update_session(self, session_id, **kwargs):
        """Update session fields."""
        if not kwargs:
            return
        with get_db() as conn:
            cursor = conn.cursor()
            sets = []
            values = []
            for key, val in kwargs.items():
                sets.append(f"{key} = ?")
                values.append(val)
            sets.append("updated_at = CURRENT_TIMESTAMP")
            values.append(session_id)
            cursor.execute(
                f"UPDATE builder_sessions SET {', '.join(sets)} WHERE id = ?",
                values,
            )
            conn.commit()

    def build_enriched_resume(self, job_text, base_text="", sources=None):
        """
        Build an enriched resume from multiple sources, optimized for a job description.

        Args:
            job_text: Full job description text
            base_text: Optional base resume text
            sources: Dict with keys: linkedin, projects, journey, experiences
                     Each value is the loaded data from load_* methods.

        Returns dict with text, sections, sources_used, relevance_scores.
        """
        sources = sources or {}
        sections = {
            "summary": [],
            "experience": [],
            "skills": [],
            "education": [],
            "accomplishments": [],
        }
        sources_used = []
        relevance_scores = {}

        job_keywords = set(extract_keywords(job_text, 50))  # noqa: F841
        job_phrases = set(extract_skill_phrases(job_text))  # noqa: F841

        # --- Base resume ---
        if base_text.strip():
            sections["summary"].append({"text": base_text, "source": "original"})

        # --- LinkedIn ---
        linkedin = sources.get("linkedin")
        if linkedin and (linkedin.get("skills") or linkedin.get("experience")):
            sources_used.append("linkedin")

            # Skills
            for skill in linkedin.get("skills", []):
                name = skill if isinstance(skill, str) else skill.get("name", "")
                if name:
                    sections["skills"].append({"text": name, "source": "linkedin"})

            # Experience bullets
            for exp in linkedin.get("experience", []):
                title = exp.get("title", "")
                company = exp.get("company", "")
                desc = exp.get("description", "")
                header = f"{title} at {company}" if company else title

                if desc:
                    score = calculate_similarity(desc, job_text)
                    relevance_scores[f"linkedin:{company}"] = round(score * 100, 1)
                    sections["experience"].append(
                        {
                            "text": header,
                            "detail": desc,
                            "source": "linkedin",
                            "relevance": round(score * 100, 1),
                        }
                    )

                for acc in exp.get("accomplishments", []):
                    if acc.strip():
                        sections["accomplishments"].append(
                            {
                                "text": acc,
                                "source": "linkedin",
                            }
                        )

            # Recommendations as endorsements
            for rec in linkedin.get("recommendations", []):
                rec_text = rec.get("text", "") or rec.get("recommendation_text", "")
                if rec_text:
                    score = calculate_similarity(rec_text, job_text)
                    if score > 0.3:
                        sections["accomplishments"].append(
                            {
                                "text": rec_text[:200],
                                "source": "linkedin_recommendation",
                                "relevance": round(score * 100, 1),
                            }
                        )

        # --- Projects (Phase 9) ---
        projects = sources.get("projects")
        if projects:
            sources_used.append("projects")
            for proj in projects:
                client = proj.get("client_name", "Unknown")
                techs = proj.get("technologies", [])
                outcomes = proj.get("outcomes", [])
                contributions = proj.get("role_contributions", [])

                # Add technologies as skills
                for tech in techs:
                    t = tech if isinstance(tech, str) else tech.get("name", "")
                    if t:
                        sections["skills"].append({"text": t, "source": f"project:{client}"})

                # Add outcomes as accomplishments
                for outcome in outcomes:
                    o = outcome if isinstance(outcome, str) else outcome.get("description", "")
                    if o:
                        score = calculate_similarity(o, job_text)
                        sections["accomplishments"].append(
                            {
                                "text": f"{o} ({client})",
                                "source": f"project:{client}",
                                "relevance": round(score * 100, 1),
                            }
                        )
                        relevance_scores[f"project:{client}"] = round(score * 100, 1)

                # Add contributions as experience
                for contrib in contributions:
                    c = contrib if isinstance(contrib, str) else contrib.get("description", "")
                    if c:
                        sections["experience"].append(
                            {
                                "text": f"{c} — {client}",
                                "source": f"project:{client}",
                            }
                        )

        # --- Journey (Phase 10) ---
        journey = sources.get("journey")
        if journey and (journey.get("star_entries") or journey.get("narratives")):
            sources_used.append("journey")

            for entry in journey.get("star_entries", []):
                content = entry.get("content", "")
                if content:
                    score = calculate_similarity(content, job_text)
                    sections["accomplishments"].append(
                        {
                            "text": content,
                            "source": "journey",
                            "relevance": round(score * 100, 1),
                        }
                    )

            for skill in journey.get("skills", []):
                name = skill.get("name", "")
                if name:
                    sections["skills"].append({"text": name, "source": "journey"})

        # --- Experiences (Phase 7) ---
        experiences = sources.get("experiences")
        if experiences:
            sources_used.append("experiences")
            for exp in experiences:
                title = exp.get("title", "")
                employer = exp.get("employer", "")
                client = exp.get("client", "")
                header = f"{title} at {employer}"
                if client:
                    header += f" ({client})"

                bullets = exp.get("bullet_points", [])
                if bullets:
                    detail = "\n".join(f"- {b}" for b in bullets)
                    score = calculate_similarity(detail, job_text)
                    sections["experience"].append(
                        {
                            "text": header,
                            "detail": detail,
                            "source": "experience_interview",
                            "relevance": round(score * 100, 1),
                        }
                    )
                    relevance_scores[f"experience:{employer}"] = round(score * 100, 1)

                for tech in exp.get("technologies", []):
                    sections["skills"].append({"text": tech, "source": "experience_interview"})

        # --- Deduplicate skills ---
        seen_skills = set()
        unique_skills = []
        for s in sections["skills"]:
            key = s["text"].lower().strip()
            if key not in seen_skills and len(key) > 1:
                seen_skills.add(key)
                unique_skills.append(s)
        sections["skills"] = unique_skills

        # --- Sort accomplishments by relevance ---
        sections["accomplishments"].sort(key=lambda x: x.get("relevance", 0), reverse=True)

        # --- Compile final text ---
        text_parts = []

        if sections["summary"]:
            text_parts.append("SUMMARY")
            for item in sections["summary"]:
                text_parts.append(item["text"])
            text_parts.append("")

        if sections["experience"]:
            text_parts.append("EXPERIENCE")
            for item in sections["experience"]:
                text_parts.append(item["text"])
                if item.get("detail"):
                    text_parts.append(item["detail"])
                text_parts.append("")

        if sections["skills"]:
            text_parts.append("SKILLS")
            skill_names = [s["text"] for s in sections["skills"]]
            text_parts.append(", ".join(skill_names))
            text_parts.append("")

        if sections["accomplishments"]:
            text_parts.append("KEY ACCOMPLISHMENTS")
            for item in sections["accomplishments"][:10]:
                text_parts.append(f"- {item['text']}")
            text_parts.append("")

        if sections["education"]:
            text_parts.append("EDUCATION")
            for item in sections["education"]:
                text_parts.append(item["text"])

        return {
            "text": "\n".join(text_parts),
            "sections": sections,
            "sources_used": sources_used,
            "relevance_scores": relevance_scores,
        }


# Module-level singleton
_builder = None


def get_resume_builder():
    global _builder
    if _builder is None:
        _builder = ResumeBuilder()
    return _builder
