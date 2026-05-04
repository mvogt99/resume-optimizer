"""Resume template management — multiple base resumes per role type."""

from models import get_db

VALID_ROLE_TYPES = ("architect", "manager", "ic", "consultant", "executive", "general")


class ResumeTemplate:
    def __init__(self, id, user_id, name, role_type, base_content, created_at, updated_at):
        self.id = id
        self.user_id = user_id
        self.name = name
        self.role_type = role_type
        self.base_content = base_content
        self.created_at = created_at
        self.updated_at = updated_at

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "role_type": self.role_type,
            "base_content": self.base_content,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @staticmethod
    def _from_row(row):
        if row is None:
            return None
        return ResumeTemplate(
            row["id"],
            row["user_id"],
            row["name"],
            row["role_type"],
            row["base_content"],
            row["created_at"],
            row["updated_at"],
        )

    @staticmethod
    def create(user_id, name, role_type, base_content):
        if role_type not in VALID_ROLE_TYPES:
            raise ValueError(f"Invalid role_type. Must be one of: {VALID_ROLE_TYPES}")
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO resume_templates "
                "(user_id, name, role_type, base_content) VALUES (?, ?, ?, ?)",
                (user_id, name, role_type, base_content),
            )
            conn.commit()
            return ResumeTemplate(
                cursor.lastrowid, user_id, name, role_type, base_content, None, None
            )

    @staticmethod
    def get_by_id(template_id, user_id=None):
        with get_db() as conn:
            if user_id is not None:
                row = conn.execute(
                    "SELECT * FROM resume_templates WHERE id = ? AND user_id = ?",
                    (template_id, user_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM resume_templates WHERE id = ?", (template_id,)
                ).fetchone()
            return ResumeTemplate._from_row(row)

    @staticmethod
    def get_all_for_user(user_id):
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM resume_templates WHERE user_id = ? ORDER BY updated_at DESC",
                (user_id,),
            ).fetchall()
            return [ResumeTemplate._from_row(r) for r in rows]

    @staticmethod
    def update(template_id, user_id, **fields):
        allowed = {"name", "role_type", "base_content"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return False
        if "role_type" in updates and updates["role_type"] not in VALID_ROLE_TYPES:
            raise ValueError(f"Invalid role_type. Must be one of: {VALID_ROLE_TYPES}")
        set_parts = [f"{k} = ?" for k in updates]
        set_parts.append("updated_at = CURRENT_TIMESTAMP")
        values = list(updates.values()) + [template_id, user_id]
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE resume_templates SET {', '.join(set_parts)} "
                "WHERE id = ? AND user_id = ?",
                values,
            )
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def delete(template_id, user_id):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM resume_templates WHERE id = ? AND user_id = ?",
                (template_id, user_id),
            )
            conn.commit()
            return cursor.rowcount > 0


def customize_for_job(template_id, user_id, job_description):
    """Customize a resume template for a specific job description.

    Returns optimization result dict with optimized_text, ats_score, etc.
    """
    template = ResumeTemplate.get_by_id(template_id, user_id)
    if not template:
        raise ValueError("Template not found")

    from nlp_engine import extract_keywords
    from utils import (
        _extract_education_from_text,
        _extract_experience_from_text,
        analyze_job_description,
        optimize_resume,
    )

    # Build resume_data dict from template text (same shape as process_resume())
    resume_data = {
        "text": template.base_content,
        "skills": extract_keywords(template.base_content, 20),
        "experience": _extract_experience_from_text(template.base_content),
        "education": _extract_education_from_text(template.base_content),
    }
    job_analysis = analyze_job_description(job_description)
    job_keywords = job_analysis.get("keywords", [])

    result = optimize_resume(resume_data, job_keywords, job_text=job_description)
    result["template_id"] = template.id
    result["template_name"] = template.name
    return result
