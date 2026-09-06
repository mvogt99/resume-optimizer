"""Core tests for models.py — CRUD operations, password hashing, FK constraints, DB schema."""

import json
import sqlite3
import uuid

import pytest
from test_helpers import query_db

# ---------------------------------------------------------------------------
# init_db / schema verification
# ---------------------------------------------------------------------------


class TestInitDB:
    """Verify that init_db() creates all expected tables and indexes."""

    def test_users_table_exists(self, app):
        rows = query_db("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        assert len(rows) == 1

    def test_resumes_table_exists(self, app):
        rows = query_db("SELECT name FROM sqlite_master WHERE type='table' AND name='resumes'")
        assert len(rows) == 1

    def test_job_descriptions_table_exists(self, app):
        rows = query_db(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='job_descriptions'"
        )
        assert len(rows) == 1

    def test_resume_versions_table_exists(self, app):
        rows = query_db(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='resume_versions'"
        )
        assert len(rows) == 1

    def test_job_sessions_table_exists(self, app):
        rows = query_db("SELECT name FROM sqlite_master WHERE type='table' AND name='job_sessions'")
        assert len(rows) == 1

    def test_job_postings_table_exists(self, app):
        rows = query_db("SELECT name FROM sqlite_master WHERE type='table' AND name='job_postings'")
        assert len(rows) == 1

    def test_campaigns_table_exists(self, app):
        rows = query_db("SELECT name FROM sqlite_master WHERE type='table' AND name='campaigns'")
        assert len(rows) == 1

    def test_indexes_created(self, app):
        rows = query_db("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")
        assert len(rows) >= 10, f"Expected >=10 indexes, got {len(rows)}"

    def test_foreign_keys_are_enforced(self, app):
        """PostgreSQL always enforces foreign keys and they cannot be switched
        off per connection, so this asserts the BEHAVIOUR rather than probing a
        pragma (`PRAGMA foreign_keys` is SQLite-only and returns nothing here).

        The property is worth keeping: enforcement is what catches child rows
        written against missing parents, a class of bug this codebase carries a
        lot of because SQLite silently permitted it for years.

        The sentinel id is deliberately large -- the suite pre-seeds a set of
        well-known low ids, and using one of those would let the insert succeed
        and the test pass vacuously.
        """
        import psycopg2
        import models

        with pytest.raises(psycopg2.errors.ForeignKeyViolation):
            with models.get_db() as conn:
                conn.execute(
                    "INSERT INTO client_projects (user_id, folder_id, client_name) "
                    "VALUES (?, ?, ?)",
                    (987654321, "no-such-folder", "Nonexistent Parent"),
                )
                conn.commit()


# ---------------------------------------------------------------------------
# User model
# ---------------------------------------------------------------------------


class TestUserModel:
    """Tests for User CRUD and authentication."""

    def test_create_user(self, app):
        from models import User

        user = User.create("alice@example.com", "SecurePass123!")
        assert user.id is not None
        assert user.email == "alice@example.com"
        assert user.password_hash != "SecurePass123!"  # hashed

    def test_create_user_persists_to_db(self, app):
        from models import User

        User.create("bob@example.com", "Pass456!")
        rows = query_db("SELECT * FROM users WHERE email = ?", ("bob@example.com",))
        assert len(rows) == 1
        assert rows[0]["email"] == "bob@example.com"
        assert rows[0]["password_hash"] != "Pass456!"

    def test_find_by_email_found(self, app):
        from models import User

        User.create("charlie@example.com", "Pass789!")
        found = User.find_by_email("charlie@example.com")
        assert found is not None
        assert found.email == "charlie@example.com"

    def test_find_by_email_not_found(self, app):
        from models import User

        found = User.find_by_email("nonexistent@example.com")
        assert found is None

    def test_authenticate_success(self, app):
        from models import User

        User.create("auth@example.com", "CorrectPassword!")
        user = User.authenticate("auth@example.com", "CorrectPassword!")
        assert user is not None
        assert user.email == "auth@example.com"

    def test_authenticate_wrong_password(self, app):
        from models import User

        User.create("authfail@example.com", "RightPass!")
        user = User.authenticate("authfail@example.com", "WrongPass!")
        assert user is None

    def test_authenticate_nonexistent_email(self, app):
        from models import User

        user = User.authenticate("nobody@example.com", "whatever")
        assert user is None

    def test_duplicate_email_raises(self, app):
        """A duplicate email is rejected by the UNIQUE constraint.

        The exception type is driver-specific: sqlite3 raised IntegrityError,
        psycopg2 raises UniqueViolation. Both derive from their driver's
        integrity-error base, so the assertion targets the PostgreSQL type this
        app actually runs on rather than the SQLite one it used to.
        """
        import psycopg2
        from models import User

        User.create("dupecheck@example.com", "Pass1!")
        with pytest.raises(psycopg2.errors.UniqueViolation):
            User.create("dupecheck@example.com", "Pass2!")

    def test_password_hash_uses_werkzeug(self, app):
        from models import User

        user = User.create("werk@example.com", "TestHash!")
        # werkzeug hashes start with a method prefix
        assert user.password_hash.startswith(("pbkdf2:", "scrypt:"))

    def test_created_at_populated(self, app):
        from models import User

        User.create("timestamp@example.com", "Pass!")
        rows = query_db("SELECT created_at FROM users WHERE email = ?", ("timestamp@example.com",))
        assert rows[0]["created_at"] is not None


# ---------------------------------------------------------------------------
# Resume model
# ---------------------------------------------------------------------------


class TestResumeModel:
    """Tests for Resume CRUD."""

    def test_create_resume(self, app):
        from models import Resume, User

        user = User.create("res@example.com", "Pass!")
        resume = Resume.create(user.id, "my_resume.pdf", "/uploads/my_resume.pdf")
        assert resume.id is not None
        assert resume.user_id == user.id
        assert resume.filename == "my_resume.pdf"
        assert resume.file_path == "/uploads/my_resume.pdf"

    def test_create_resume_persists(self, app):
        from models import Resume, User

        user = User.create("res2@example.com", "Pass!")
        Resume.create(user.id, "doc.docx", "/uploads/doc.docx")
        rows = query_db("SELECT * FROM resumes WHERE user_id = ?", (user.id,))
        assert len(rows) == 1
        assert rows[0]["filename"] == "doc.docx"

    def test_get_by_id_found(self, app):
        from models import Resume, User

        user = User.create("res3@example.com", "Pass!")
        created = Resume.create(user.id, "test.txt", "/uploads/test.txt")
        found = Resume.get_by_id(created.id)
        assert found is not None
        assert found.filename == "test.txt"
        assert found.user_id == user.id

    def test_get_by_id_not_found(self, app):
        from models import Resume

        found = Resume.get_by_id(99999)
        assert found is None


# ---------------------------------------------------------------------------
# JobDescription model
# ---------------------------------------------------------------------------


class TestJobDescriptionModel:
    """Tests for JobDescription CRUD."""

    def test_create_job_description(self, app):
        from models import JobDescription, User

        user = User.create("jd@example.com", "Pass!")
        jd = JobDescription.create(user.id, "Looking for a Python developer")
        assert jd.id is not None
        assert jd.user_id == user.id
        assert jd.text == "Looking for a Python developer"

    def test_get_latest_for_user(self, app):
        from models import JobDescription, User

        user = User.create("jd2@example.com", "Pass!")
        JobDescription.create(user.id, "First JD")
        JobDescription.create(user.id, "Second JD")
        latest = JobDescription.get_latest_for_user(user.id)
        assert latest is not None
        assert latest.text in ("First JD", "Second JD")

    def test_get_latest_for_user_none(self, app):
        from models import JobDescription, User

        user = User.create("jd3@example.com", "Pass!")
        latest = JobDescription.get_latest_for_user(user.id)
        assert latest is None

    def test_create_persists_to_db(self, app):
        from models import JobDescription, User

        user = User.create("jd4@example.com", "Pass!")
        JobDescription.create(user.id, "Python Java AWS")
        rows = query_db("SELECT * FROM job_descriptions WHERE user_id = ?", (user.id,))
        assert len(rows) == 1
        assert "Python" in rows[0]["text"]


# ---------------------------------------------------------------------------
# ResumeVersion model
# ---------------------------------------------------------------------------


class TestResumeVersionModel:
    """Tests for ResumeVersion CRUD."""

    def test_create_resume_version(self, app):
        from models import ResumeVersion, User

        user = User.create("rv@example.com", "Pass!")
        rv = ResumeVersion.create(
            user.id,
            "upload",
            "resume_v1.txt",
            "My resume text",
            source_id="src1",
            file_type="txt",
        )
        assert rv.id is not None
        assert rv.source == "upload"
        assert rv.file_name == "resume_v1.txt"
        assert rv.parsed_text == "My resume text"

    def test_get_by_id(self, app):
        from models import ResumeVersion, User

        user = User.create("rv2@example.com", "Pass!")
        created = ResumeVersion.create(user.id, "gdrive", "gdrive_file.pdf", "Parsed text")
        found = ResumeVersion.get_by_id(created.id)
        assert found is not None
        assert found.source == "gdrive"
        assert found.parsed_text == "Parsed text"

    def test_get_by_id_not_found(self, app):
        from models import ResumeVersion

        found = ResumeVersion.get_by_id(99999)
        assert found is None

    def test_get_all_for_user(self, app):
        from models import ResumeVersion, User

        user = User.create("rv3@example.com", "Pass!")
        ResumeVersion.create(user.id, "upload", "v1.txt", "Text 1")
        ResumeVersion.create(user.id, "gdrive", "v2.docx", "Text 2")
        all_versions = ResumeVersion.get_all_for_user(user.id)
        assert len(all_versions) == 2
        names = {v.file_name for v in all_versions}
        assert "v1.txt" in names
        assert "v2.docx" in names

    def test_get_all_for_user_empty(self, app):
        from models import ResumeVersion, User

        user = User.create("rv4@example.com", "Pass!")
        all_versions = ResumeVersion.get_all_for_user(user.id)
        assert all_versions == []

    def test_metadata_json_stored(self, app):
        from models import ResumeVersion, User

        user = User.create("rv5@example.com", "Pass!")
        meta = json.dumps({"source": "gdrive", "file_id": "abc123"})
        rv = ResumeVersion.create(user.id, "gdrive", "meta.txt", "text", metadata_json=meta)
        assert rv.metadata_json == meta
        rows = query_db("SELECT metadata_json FROM resume_versions WHERE id = ?", (rv.id,))
        assert json.loads(rows[0]["metadata_json"])["file_id"] == "abc123"


# ---------------------------------------------------------------------------
# JobSession model
# ---------------------------------------------------------------------------


class TestJobSessionModel:
    """Tests for JobSession CRUD including update and delete."""

    def test_create_job_session(self, app):
        from models import JobSession, User

        user = User.create("js@example.com", "Pass!")
        session = JobSession.create(
            user.id,
            session_name="My Session",
            job_description_text="Python developer role",
        )
        assert session is not None
        assert session.user_id == user.id
        assert session.session_name == "My Session"
        assert session.status == "draft"

    def test_session_id_is_uuid(self, app):
        from models import JobSession, User

        user = User.create("js2@example.com", "Pass!")
        session = JobSession.create(user.id)
        # Should be a valid UUID
        uuid.UUID(session.id)  # raises ValueError if invalid

    def test_get_by_id(self, app):
        from models import JobSession, User

        user = User.create("js3@example.com", "Pass!")
        created = JobSession.create(user.id, session_name="FindMe")
        found = JobSession.get_by_id(created.id)
        assert found is not None
        assert found.session_name == "FindMe"

    def test_get_by_id_with_user_filter(self, app):
        from models import JobSession, User

        user1 = User.create("js4a@example.com", "Pass!")
        user2 = User.create("js4b@example.com", "Pass!")
        session = JobSession.create(user1.id, session_name="User1Only")
        # Should find with correct user
        assert JobSession.get_by_id(session.id, user_id=user1.id) is not None
        # Should not find with wrong user
        assert JobSession.get_by_id(session.id, user_id=user2.id) is None

    def test_get_all_for_user(self, app):
        from models import JobSession, User

        user = User.create("js5@example.com", "Pass!")
        JobSession.create(user.id, session_name="Session A")
        JobSession.create(user.id, session_name="Session B")
        sessions = JobSession.get_all_for_user(user.id)
        assert len(sessions) == 2

    def test_update_session_name(self, app):
        from models import JobSession, User

        user = User.create("js6@example.com", "Pass!")
        session = JobSession.create(user.id, session_name="OldName")
        JobSession.update(session.id, session_name="NewName")
        updated = JobSession.get_by_id(session.id)
        assert updated.session_name == "NewName"

    def test_update_status(self, app):
        from models import JobSession, User

        user = User.create("js7@example.com", "Pass!")
        session = JobSession.create(user.id)
        assert session.status == "draft"
        JobSession.update(session.id, status="optimized")
        updated = JobSession.get_by_id(session.id)
        assert updated.status == "optimized"

    def test_update_ats_score(self, app):
        from models import JobSession, User

        user = User.create("js8@example.com", "Pass!")
        session = JobSession.create(user.id)
        JobSession.update(session.id, ats_score=78.5)
        updated = JobSession.get_by_id(session.id)
        assert updated.ats_score == 78.5

    def test_update_ignores_disallowed_fields(self, app):
        from models import JobSession, User

        user = User.create("js9@example.com", "Pass!")
        session = JobSession.create(user.id)
        # 'id' is not in allowed set — should be silently ignored
        JobSession.update(session.id, id="hacked")
        same = JobSession.get_by_id(session.id)
        assert same.id == session.id

    def test_delete_session(self, app):
        from models import JobSession, User

        user = User.create("js10@example.com", "Pass!")
        session = JobSession.create(user.id)
        JobSession.delete(session.id)
        assert JobSession.get_by_id(session.id) is None

    def test_to_dict_basic(self, app):
        from models import JobSession, User

        user = User.create("js11@example.com", "Pass!")
        session = JobSession.create(user.id, session_name="DictTest")
        d = session.to_dict()
        assert d["session_name"] == "DictTest"
        assert d["status"] == "draft"
        assert "optimization_result" not in d

    def test_to_dict_include_result(self, app):
        from models import JobSession, User

        user = User.create("js12@example.com", "Pass!")
        session = JobSession.create(user.id)
        result = {"score": 85, "keywords": ["python"]}
        JobSession.update(session.id, optimization_result_json=json.dumps(result))
        updated = JobSession.get_by_id(session.id)
        d = updated.to_dict(include_result=True)
        assert "optimization_result" in d
        assert d["optimization_result"]["score"] == 85

    def test_optimization_result_json_parsing(self, app):
        from models import JobSession, User

        user = User.create("js13@example.com", "Pass!")
        session = JobSession.create(user.id)
        JobSession.update(
            session.id,
            optimization_result_json=json.dumps({"matched": ["aws", "python"]}),
        )
        updated = JobSession.get_by_id(session.id)
        assert updated.optimization_result["matched"] == ["aws", "python"]

    def test_delete_persists_to_db(self, app):
        from models import JobSession, User

        user = User.create("js14@example.com", "Pass!")
        session = JobSession.create(user.id)
        sid = session.id
        JobSession.delete(sid)
        rows = query_db("SELECT * FROM job_sessions WHERE id = ?", (sid,))
        assert len(rows) == 0


# ---------------------------------------------------------------------------
# get_db context manager
# ---------------------------------------------------------------------------


class TestGetDB:
    """Tests for the get_db() context manager."""

    def test_get_db_returns_connection(self, app):
        from models import get_db

        with get_db() as conn:
            assert conn is not None
            result = conn.execute("SELECT 1").fetchone()
            assert result[0] == 1

    def test_get_db_row_factory(self, app):
        from models import get_db

        with get_db() as conn:
            row = conn.execute("SELECT 1 AS val").fetchone()
            # Row factory should allow dict-like access
            assert row["val"] == 1

    def test_get_db_closes_after_context(self, app):
        import models

        with models.get_db() as conn:
            conn.execute("SELECT 1")
        # After exiting context, connection should be closed
        # Attempting to use it should raise
        with pytest.raises(Exception):
            conn.execute("SELECT 1")
