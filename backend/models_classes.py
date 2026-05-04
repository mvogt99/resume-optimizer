import json
import uuid
from models import get_db
from werkzeug.security import check_password_hash, generate_password_hash

class User:
    def __init__(self, id, email, password_hash):
        self.id = id
        self.email = email
        self.password_hash = password_hash

    @staticmethod
    def create(email, password):
        hashed = generate_password_hash(password)
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                (email, hashed),
            )
            conn.commit()
            return User(cursor.lastrowid, email, hashed)

    @staticmethod
    def find_by_email(email):
        with get_db() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if row:
                return User(row["id"], row["email"], row["password_hash"])
            return None

    @staticmethod
    def authenticate(email, password):
        user = User.find_by_email(email)
        if user and check_password_hash(user.password_hash, password):
            return user
        return None


class Resume:
    def __init__(self, id, user_id, filename, file_path):
        self.id = id
        self.user_id = user_id
        self.filename = filename
        self.file_path = file_path

    @staticmethod
    def create(user_id, filename, file_path):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO resumes (user_id, filename, file_path) VALUES (?, ?, ?)",
                (user_id, filename, file_path),
            )
            conn.commit()
            return Resume(cursor.lastrowid, user_id, filename, file_path)

    @staticmethod
    def get_by_id(resume_id):
        with get_db() as conn:
            row = conn.execute("SELECT * FROM resumes WHERE id = ?", (resume_id,)).fetchone()
            if row:
                return Resume(row["id"], row["user_id"], row["filename"], row["file_path"])
            return None


class JobDescription:
    def __init__(self, id, user_id, text):
        self.id = id
        self.user_id = user_id
        self.text = text

    @staticmethod
    def create(user_id, text):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO job_descriptions (user_id, text) VALUES (?, ?)",
                (user_id, text),
            )
            conn.commit()
            return JobDescription(cursor.lastrowid, user_id, text)

    @staticmethod
    def get_latest_for_user(user_id):
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM job_descriptions WHERE user_id = ? "
                "ORDER BY uploaded_at DESC LIMIT 1",
                (user_id,),
            ).fetchone()
            if row:
                return JobDescription(row["id"], row["user_id"], row["text"])
            return None


class ResumeVersion:
    def __init__(
        self, id, user_id, source, source_id, file_name, file_type, parsed_text, metadata_json
    ):
        self.id = id
        self.user_id = user_id
        self.source = source
        self.source_id = source_id
        self.file_name = file_name
        self.file_type = file_type
        self.parsed_text = parsed_text
        self.metadata_json = metadata_json

    @staticmethod
    def create(
        user_id, source, file_name, parsed_text, source_id="", file_type="", metadata_json="{}"
    ):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO resume_versions "
                "(user_id, source, source_id, file_name, file_type, parsed_text, metadata_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, source, source_id, file_name, file_type, parsed_text, metadata_json),
            )
            conn.commit()
            return ResumeVersion(
                cursor.lastrowid,
                user_id,
                source,
                source_id,
                file_name,
                file_type,
                parsed_text,
                metadata_json,
            )

    @staticmethod
    def get_by_id(version_id):
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM resume_versions WHERE id = ?", (version_id,)
            ).fetchone()
            if row:
                return ResumeVersion(
                    row["id"],
                    row["user_id"],
                    row["source"],
                    row["source_id"],
                    row["file_name"],
                    row["file_type"],
                    row["parsed_text"],
                    row["metadata_json"],
                )
            return None

    @staticmethod
    def get_all_for_user(user_id):
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM resume_versions WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
            return [
                ResumeVersion(
                    r["id"],
                    r["user_id"],
                    r["source"],
                    r["source_id"],
                    r["file_name"],
                    r["file_type"],
                    r["parsed_text"],
                    r["metadata_json"],
                )
                for r in rows
            ]


class JobSession:
    def __init__(self, row_dict):
        self.id = row_dict["id"]
        self.user_id = row_dict["user_id"]
        self.session_name = row_dict.get("session_name", "")
        self.resume_id = row_dict.get("resume_id")
        self.resume_version_id = row_dict.get("resume_version_id")
        self.job_description_text = row_dict.get("job_description_text", "")
        self.ats_score = row_dict.get("ats_score", 0)
        self.status = row_dict.get("status", "draft")
        self.recommendation_id = row_dict.get("recommendation_id")
        self.posting_id = row_dict.get("posting_id")
        self.created_at = row_dict.get("created_at", "")
        self.updated_at = row_dict.get("updated_at", "")
        raw = row_dict.get("optimization_result_json", "{}")
        if isinstance(raw, str):
            try:
                self.optimization_result = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                self.optimization_result = {}
        else:
            self.optimization_result = raw or {}

    def to_dict(self, include_result=False):
        resume_id = self.resume_id
        resume_version_id = self.resume_version_id
        if resume_id and isinstance(resume_id, str):
            try:
                resume_id = int(resume_id)
            except (ValueError, TypeError):
                pass
        if resume_version_id and isinstance(resume_version_id, str):
            try:
                resume_version_id = int(resume_version_id)
            except (ValueError, TypeError):
                pass

        d = {
            "id": self.id,
            "user_id": self.user_id,
            "session_name": self.session_name,
            "resume_id": resume_id,
            "resume_version_id": resume_version_id,
            "job_description_text": self.job_description_text,
            "ats_score": self.ats_score,
            "status": self.status,
            "recommendation_id": self.recommendation_id,
            "posting_id": self.posting_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if include_result:
            d["optimization_result"] = self.optimization_result
        return d

    @staticmethod
    def create(
        user_id, session_name="", resume_id=None, resume_version_id=None, job_description_text=""
    ):
        session_id = str(uuid.uuid4())
        with get_db() as conn:
            conn.execute(
                "INSERT INTO job_sessions "
                "(id, user_id, session_name, resume_id, resume_version_id, job_description_text) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    user_id,
                    session_name,
                    resume_id,
                    resume_version_id,
                    job_description_text,
                ),
            )
            conn.commit()
        return JobSession.get_by_id(session_id)

    @staticmethod
    def get_by_id(session_id, user_id=None):
        with get_db() as conn:
            if user_id is not None:
                row = conn.execute(
                    "SELECT * FROM job_sessions WHERE id = ? AND user_id = ?",
                    (session_id, user_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM job_sessions WHERE id = ?", (session_id,)
                ).fetchone()
            if row:
                return JobSession(dict(row))
            return None

    @staticmethod
    def get_all_for_user(user_id):
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM job_sessions WHERE user_id = ? ORDER BY updated_at DESC",
                (user_id,),
            ).fetchall()
            return [JobSession(dict(r)) for r in rows]

    @staticmethod
    def update(session_id, **fields):
        allowed = {
            "session_name",
            "resume_id",
            "resume_version_id",
            "job_description_text",
            "optimization_result_json",
            "ats_score",
            "status",
            "recommendation_id",
            "posting_id",
        }
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return
        updates["updated_at"] = "CURRENT_TIMESTAMP"
        set_clauses = []
        values = []
        for k, v in updates.items():
            if v == "CURRENT_TIMESTAMP":
                set_clauses.append(f"{k} = CURRENT_TIMESTAMP")
            else:
                set_clauses.append(f"{k} = ?")
                values.append(v)
        values.append(session_id)
        with get_db() as conn:
            conn.execute(
                f"UPDATE job_sessions SET {', '.join(set_clauses)} WHERE id = ?",
                values,
            )
            conn.commit()

    @staticmethod
    def delete(session_id):
        with get_db() as conn:
            conn.execute("DELETE FROM job_sessions WHERE id = ?", (session_id,))
            conn.commit()


class ResumeRecommendation:
    """Stores multi-resume comparison results and recommended resume ID."""

    def __init__(
        self, id, user_id, job_description_text, resume_scores_json,
        recommended_resume_id=None, recommended_version_id=None,
        rationale="", user_chosen_resume_id=None, user_chosen_version_id=None,
        session_id=None, created_at=None
    ):
        self.id = id
        self.user_id = user_id
        self.job_description_text = job_description_text
        self.resume_scores_json = resume_scores_json
        self.recommended_resume_id = recommended_resume_id
        self.recommended_version_id = recommended_version_id
        self.rationale = rationale
        self.user_chosen_resume_id = user_chosen_resume_id
        self.user_chosen_version_id = user_chosen_version_id
        self.session_id = session_id
        self.created_at = created_at

    def save(self):
        with get_db() as conn:
            conn.execute(
                """INSERT INTO resume_recommendations
                (id, user_id, job_description_text, resume_scores_json,
                 recommended_resume_id, recommended_version_id, rationale,
                 user_chosen_resume_id, user_chosen_version_id, session_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (self.id, self.user_id, self.job_description_text, self.resume_scores_json,
                 self.recommended_resume_id, self.recommended_version_id, self.rationale,
                 self.user_chosen_resume_id, self.user_chosen_version_id, self.session_id,
                 self.created_at)
            )
            conn.commit()

    @staticmethod
    def get_by_id(recommendation_id, user_id):
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM resume_recommendations WHERE id = ? AND user_id = ?",
                (recommendation_id, user_id)
            ).fetchone()
            if row:
                return ResumeRecommendation(
                    row["id"], row["user_id"], row["job_description_text"],
                    row["resume_scores_json"], row["recommended_resume_id"],
                    row["recommended_version_id"], row["rationale"],
                    row["user_chosen_resume_id"], row["user_chosen_version_id"],
                    row["session_id"], row["created_at"]
                )
            return None

    @staticmethod
    def get_all_for_user(user_id):
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM resume_recommendations WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,)
            ).fetchall()
            return [
                ResumeRecommendation(
                    row["id"], row["user_id"], row["job_description_text"],
                    row["resume_scores_json"], row["recommended_resume_id"],
                    row["recommended_version_id"], row["rationale"],
                    row["user_chosen_resume_id"], row["user_chosen_version_id"],
                    row["session_id"], row["created_at"]
                )
                for row in rows
            ]

    def select(self, chosen_resume_id, chosen_version_id, session_id):
        """Record user's selection and link to session."""
        with get_db() as conn:
            conn.execute(
                """UPDATE resume_recommendations
                SET user_chosen_resume_id = ?, user_chosen_version_id = ?, session_id = ?
                WHERE id = ?""",
                (chosen_resume_id, chosen_version_id, session_id, self.id)
            )
            conn.commit()
        self.user_chosen_resume_id = chosen_resume_id
        self.user_chosen_version_id = chosen_version_id
        self.session_id = session_id
