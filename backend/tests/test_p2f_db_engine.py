"""P2-F Session 1: DB engine + models.py dual-backend validation.

Tests that init_db(), get_db(), and get_db_connection() work correctly
on both SQLite (default) and PostgreSQL (mocked) paths.
No live PostgreSQL instance required — psycopg2 is mocked where needed.
"""

import contextlib
import os
import sqlite3
import tempfile
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def fresh_db():
    """Yield a temporary DB path and clean up after."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        yield path
    finally:
        with contextlib.suppress(OSError):
            os.unlink(path)


# ---------------------------------------------------------------------------
# db_engine routing helpers
# ---------------------------------------------------------------------------


class TestRoutingHelpers:
    """is_postgres() / is_sqlite() URL detection."""

    def test_is_sqlite_no_env(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        from db_engine import is_postgres, is_sqlite

        assert is_sqlite() is True
        assert is_postgres() is False

    def test_is_postgres_with_postgresql_scheme(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")
        from db_engine import is_postgres, is_sqlite

        assert is_postgres() is True
        assert is_sqlite() is False

    def test_is_postgres_with_postgres_scheme(self, monkeypatch):
        """postgres:// (short form) is also recognised as PostgreSQL."""
        monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@localhost:5432/testdb")
        from db_engine import is_postgres

        assert is_postgres() is True

    def test_is_sqlite_with_sqlite_url(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./mydb.db")
        from db_engine import is_sqlite

        assert is_sqlite() is True

    def test_get_pg_connection_raises_for_non_pg_url(self, monkeypatch):
        from db_engine import get_pg_connection

        with (
            pytest.raises(ValueError, match="Expected a PostgreSQL URL"),
            get_pg_connection("sqlite:///./test.db"),
        ):
            pass

    def test_get_pg_connection_raw_raises_for_non_pg_url(self, monkeypatch):
        from db_engine import get_pg_connection_raw

        with pytest.raises(ValueError, match="Expected a PostgreSQL URL"):
            get_pg_connection_raw("sqlite:///./test.db")

    def test_get_pg_connection_raises_import_error_without_psycopg2(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/testdb")
        with patch.dict("sys.modules", {"psycopg2": None}):
            from db_engine import get_pg_connection

            with pytest.raises((ImportError, TypeError)), get_pg_connection():
                pass


# ---------------------------------------------------------------------------
# SQLite path: get_db_connection()
# ---------------------------------------------------------------------------


class TestGetDbConnectionSQLite:
    """get_db_connection() with SQLite (no DATABASE_URL)."""

    def test_returns_sqlite_connection(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        from models import get_db_connection

        with fresh_db() as path:
            conn = get_db_connection(db_path=path)
            assert isinstance(conn, sqlite3.Connection)
            conn.close()

    def test_can_execute_query(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        from models import get_db_connection

        with fresh_db() as path:
            conn = get_db_connection(db_path=path)
            result = conn.execute("SELECT 1").fetchone()
            assert result[0] == 1
            conn.close()

    def test_row_factory_is_set(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        from models import get_db_connection

        with fresh_db() as path:
            conn = get_db_connection(db_path=path)
            assert conn.row_factory is sqlite3.Row
            conn.close()

    def test_uses_db_path_default(self, monkeypatch):
        """Calling without db_path uses models.DB_PATH."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with fresh_db() as path:
            monkeypatch.setattr("models.DB_PATH", path)
            from models import get_db_connection

            conn = get_db_connection()
            assert isinstance(conn, sqlite3.Connection)
            conn.close()


# ---------------------------------------------------------------------------
# PostgreSQL path: get_db_connection() with mocked psycopg2
# ---------------------------------------------------------------------------


class TestGetDbConnectionPostgres:
    """get_db_connection() returns _PgConnWrapper when DATABASE_URL is postgres."""

    def test_returns_pg_conn_wrapper(self, monkeypatch):
        """get_db_connection() delegates to get_pg_connection_raw() for postgresql:// URL."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")
        fake_wrapper = MagicMock()

        with (
            patch("models.is_postgres", return_value=True),
            patch("models.get_pg_connection_raw", return_value=fake_wrapper),
        ):
            import models

            conn = models.get_db_connection()
            assert conn is fake_wrapper

    def test_pg_connection_raw_returns_wrapper(self, monkeypatch):
        """get_pg_connection_raw() calls psycopg2.connect and wraps the result."""
        import sys

        mock_psycopg2 = MagicMock()
        mock_pg_conn = MagicMock()
        mock_psycopg2.connect.return_value = mock_pg_conn
        pg_url = "postgresql://user:pass@localhost:5432/testdb"

        monkeypatch.setitem(sys.modules, "psycopg2", mock_psycopg2)
        import db_engine

        conn = db_engine.get_pg_connection_raw(pg_url)
        assert isinstance(conn, db_engine._PgConnWrapper)
        mock_psycopg2.connect.assert_called_once()
        conn.close()


# ---------------------------------------------------------------------------
# SQLite path: get_db() context manager
# ---------------------------------------------------------------------------


class TestGetDbContextManager:
    """get_db() context manager with SQLite."""

    def test_yields_connection(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with fresh_db() as path:
            monkeypatch.setattr("models.DB_PATH", path)
            from models import get_db

            with get_db() as conn:
                assert conn is not None
                result = conn.execute("SELECT 1").fetchone()
                assert result[0] == 1

    def test_connection_closed_after_context(self, monkeypatch):
        """Connection is closed when context exits (no double-close error)."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with fresh_db() as path:
            monkeypatch.setattr("models.DB_PATH", path)
            from models import get_db

            with get_db() as conn:
                pass
            # After context exits, further operations on a closed connection fail
            with pytest.raises(sqlite3.ProgrammingError):
                conn.execute("SELECT 1")


# ---------------------------------------------------------------------------
# init_db() — schema creation on SQLite
# ---------------------------------------------------------------------------


CORE_TABLES = [
    "users",
    "resumes",
    "job_descriptions",
    "resume_versions",
    "job_postings",
    "search_criteria",
    "agent_runs",
    "cover_letters",
    "interview_coach_sessions",
    "campaigns",
    "campaign_posts",
    "application_feedback",
    "career_analyses",
]


class TestInitDb:
    """init_db() creates all required tables on SQLite."""

    def _get_tables(self, db_path):
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        conn.close()
        return {r[0] for r in rows}

    def test_creates_core_tables(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with fresh_db() as path:
            monkeypatch.setattr("models.DB_PATH", path)
            from models import init_db

            init_db()
            tables = self._get_tables(path)
            for table in CORE_TABLES:
                assert table in tables, f"Table '{table}' not created by init_db()"

    def test_idempotent_double_call(self, monkeypatch):
        """Calling init_db() twice does not raise (IF NOT EXISTS guards)."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with fresh_db() as path:
            monkeypatch.setattr("models.DB_PATH", path)
            from models import init_db

            init_db()
            init_db()  # Should not raise
            tables = self._get_tables(path)
            assert "users" in tables

    def test_routes_to_pg_init_when_postgres_url(self, monkeypatch):
        """init_db() calls pg_init_db() when DATABASE_URL is postgresql://."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
        # Patch at the models module level where it imports pg_init_db inside init_db()
        with (
            patch("db_engine.is_postgres", return_value=True),
            patch("db_pg_init.pg_init_db") as mock_pg_init,
        ):
            import models

            models.init_db()
            assert mock_pg_init.call_count >= 1


# ---------------------------------------------------------------------------
# Model class methods via get_db() — SQLite
# ---------------------------------------------------------------------------


class TestModelMethods:
    """User and Resume CRUD via get_db() round-trips on SQLite."""

    def test_user_create_and_find(self, app):
        from models import User

        u = User.create("dbtest@example.com", "Pass1234!")
        assert u.id is not None
        found = User.find_by_email("dbtest@example.com")
        assert found is not None
        assert found.email == "dbtest@example.com"

    def test_user_authenticate_correct_password(self, app):
        from models import User

        User.create("auth@example.com", "GoodPass1!")
        result = User.authenticate("auth@example.com", "GoodPass1!")
        assert result is not None

    def test_user_authenticate_wrong_password(self, app):
        from models import User

        User.create("auth2@example.com", "GoodPass1!")
        result = User.authenticate("auth2@example.com", "WrongPass!")
        assert result is None

    def test_resume_create_and_get(self, app):
        from models import Resume, User

        user = User.create("resume@example.com", "Pass1234!")
        r = Resume.create(user.id, "cv.pdf", "/uploads/cv.pdf")
        assert r.id is not None
        found = Resume.get_by_id(r.id)
        assert found is not None
        assert found.filename == "cv.pdf"
        assert found.user_id == user.id
