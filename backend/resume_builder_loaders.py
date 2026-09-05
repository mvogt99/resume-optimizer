"""
ResumeBuilderLoaderMixin — data-loading methods for ResumeBuilder.

Split from resume_builder.py to comply with 500-line file limit.
Inherited by ResumeBuilder.
"""

import json

from models import get_db


def init_builder_tables():
    """No-op — builder_sessions is created centrally by db_pg_init.py."""


class ResumeBuilderLoaderMixin:
    """Mixin providing data-loading methods for ResumeBuilder."""

    def load_base_resume(self, version_id):
        """Load base resume text from resume_versions table."""
        if not version_id:
            return {"text": "", "source": "blank"}

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT parsed_text, source, file_name FROM resume_versions WHERE id = ?",
                (version_id,),
            )
            row = cursor.fetchone()

        if not row:
            return {"text": "", "source": "not_found"}

        return {
            "text": row[0] or "",
            "source": row[1] or "file",
            "file_name": row[2] or "",
        }

    def load_linkedin_profile(self, linkedin_raw=None):
        """
        Load LinkedIn profile data.
        Accepts the cached raw profile from app.py or returns empty structure.
        """
        if not linkedin_raw:
            return {"skills": [], "experience": [], "recommendations": [], "text": ""}

        skills = []
        # Support both "skills_and_endorsements" (archive format) and "skills" (parser format)
        for s in linkedin_raw.get("skills_and_endorsements", linkedin_raw.get("skills", [])):
            name = s.get("name") or s.get("skill", "")
            endorsements = s.get("endorsements", 0) or s.get("endorsements_count", 0)
            if name:
                skills.append({"name": name, "endorsements": endorsements})

        experience = []
        # Support "previous_jobs"/"current_job" (archive format) and "experience" (parser format)
        exp_list = linkedin_raw.get("experience", [])
        if not exp_list:
            if linkedin_raw.get("current_job"):
                exp_list = [linkedin_raw["current_job"]]
            exp_list = (
                exp_list
                + linkedin_raw.get("additional_positions", [])
                + linkedin_raw.get("previous_jobs", [])
            )
        for exp in exp_list:
            experience.append(
                {
                    "title": exp.get("title", ""),
                    "company": exp.get("company", ""),
                    "description": exp.get("description", ""),
                    "accomplishments": exp.get("accomplishments", []),
                    "start_date": exp.get("started_on", exp.get("start_date", "")),
                    "end_date": exp.get("finished_on", exp.get("end_date", "")),
                }
            )

        # Support "recommendations_received" (archive) and "recommendations" (parser format)
        recommendations = linkedin_raw.get(
            "recommendations_received", linkedin_raw.get("recommendations", [])
        )

        return {
            "skills": skills,
            "experience": experience,
            "recommendations": recommendations,
            "text": linkedin_raw.get("summary", ""),
        }

    def load_project_insights(self, project_ids=None):
        """Load approved project analyses from client_projects table."""
        with get_db() as conn:
            cursor = conn.cursor()

            if project_ids:
                placeholders = ",".join("?" for _ in project_ids)
                cursor.execute(
                    f"SELECT id, client_name, technical_analysis_json, role_analysis_json, "
                    f"skills_json, correlation_json, business_outcomes_json "
                    f"FROM client_projects WHERE approved = 1 AND id IN ({placeholders})",
                    project_ids,
                )
            else:
                cursor.execute(
                    "SELECT id, client_name, technical_analysis_json, role_analysis_json, "
                    "skills_json, correlation_json, business_outcomes_json "
                    "FROM client_projects WHERE approved = 1"
                )

            rows = cursor.fetchall()

        results = []
        for row in rows:
            technical = _safe_json(row[2])
            role = _safe_json(row[3])
            skills = _safe_json(row[4]) if len(row) > 4 else []
            correlation = _safe_json(row[5]) if len(row) > 5 else {}
            business_outcomes = _safe_json(row[6]) if len(row) > 6 else []

            # Handle both formats:
            # Old: {"technologies": [...], "outcomes": [...]}
            # New (agentic): [{name, category, context, confidence}, ...]
            if isinstance(technical, list):
                technologies = technical
            else:
                technologies = technical.get("technologies", [])

            if isinstance(role, list):
                contributions = [
                    item.get("description", item.get("title", ""))
                    for item in role
                    if isinstance(item, dict)
                ]
                outcomes = [
                    item.get("description", "")
                    for item in role
                    if isinstance(item, dict) and item.get("metrics")
                ]
            else:
                contributions = role.get("contributions", [])
                outcomes = role.get(
                    "outcomes",
                    (technical.get("outcomes", []) if isinstance(technical, dict) else []),
                )

            if not isinstance(skills, list):
                skills = []
            if not isinstance(correlation, dict):
                correlation = {}
            if not isinstance(business_outcomes, list):
                business_outcomes = []

            results.append(
                {
                    "id": row[0],
                    "client_name": row[1],
                    "technologies": technologies,
                    "outcomes": outcomes,
                    "role_contributions": contributions,
                    "skills": skills,
                    "correlation": correlation,
                    "business_outcomes": business_outcomes,
                }
            )

        return results

    def load_journey_data(self):
        """Load approved journey narratives."""
        with get_db() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "SELECT narrative_type, title, content, source_event_ids "
                    "FROM journey_narratives WHERE approved = 1"
                )
                rows = cursor.fetchall()
            except Exception:  # noqa: BLE001
                rows = []

        star_entries = []
        skills = []
        narratives = []

        for row in rows:
            ntype, title, content, _ = (
                row[0],
                row[1],
                row[2] or "",
                row[3],
            )
            if ntype == "star_entry":
                star_entries.append({"title": title, "content": content})
            elif ntype == "skill":
                skills.append({"name": title, "description": content})
            else:
                narratives.append({"type": ntype, "title": title, "content": content})

        return {
            "star_entries": star_entries,
            "skills": skills,
            "narratives": narratives,
        }

    def load_experiences(self, session_ids=None):
        """Load extracted experiences from Phase 7 interviews."""
        with get_db() as conn:
            cursor = conn.cursor()

            try:
                if session_ids:
                    placeholders = ",".join("?" for _ in session_ids)
                    cursor.execute(
                        "SELECT employer, client, title, bullet_points, technologies "
                        f"FROM extracted_experiences WHERE session_id IN ({placeholders})",
                        session_ids,
                    )
                else:
                    cursor.execute(
                        "SELECT employer, client, title, bullet_points, technologies "
                        "FROM extracted_experiences"
                    )
                rows = cursor.fetchall()
            except Exception:  # noqa: BLE001
                rows = []

        results = []
        for row in rows:
            results.append(
                {
                    "employer": row[0] or "",
                    "client": row[1] or "",
                    "title": row[2] or "",
                    "bullet_points": (
                        _safe_json(row[3]) if isinstance(row[3], str) else (row[3] or [])
                    ),
                    "technologies": (
                        _safe_json(row[4]) if isinstance(row[4], str) else (row[4] or [])
                    ),
                }
            )

        return results

    def get_available_sources(self, user_id):
        """Check what data sources are available for this user."""
        with get_db() as conn:
            cursor = conn.cursor()

            def _safe_count(query, params=()):
                try:
                    cursor.execute(query, params)
                    return cursor.fetchone()[0]
                except Exception:  # noqa: BLE001
                    return 0

            project_count = _safe_count("SELECT COUNT(*) FROM client_projects WHERE approved = 1")
            journey_count = _safe_count(
                "SELECT COUNT(*) FROM journey_narratives WHERE approved = 1"
            )
            experience_count = _safe_count(
                "SELECT COUNT(*) FROM extracted_experiences WHERE user_id = ?",
                (user_id,),
            )

        return {
            "linkedin": {
                "available": False,  # Set by caller with profile data
                "skills_count": 0,
            },
            "projects": {
                "available": project_count > 0,
                "count": project_count,
            },
            "journey": {
                "available": journey_count > 0,
                "count": journey_count,
            },
            "experiences": {
                "available": experience_count > 0,
                "count": experience_count,
            },
        }


def _safe_json(text):
    """Safely parse JSON string, returning {} on failure."""
    if not text:
        return {}
    try:
        result = json.loads(text)
        return result if isinstance(result, (dict, list)) else {}
    except (json.JSONDecodeError, TypeError):
        return {}
