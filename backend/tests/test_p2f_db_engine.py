"""P2-F: db_engine.py + models.py PostgreSQL connection-layer validation.

Postgres is the sole database backend for this app (DATABASE_URL required).
psycopg2 is mocked where a live database isn't needed; TestModelMethods runs
against the real test database via the `app` fixture.
"""

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# db_engine routing helpers
# ---------------------------------------------------------------------------


class TestRoutingHelpers:
    """is_postgres() URL detection."""

    def test_is_postgres_with_postgresql_scheme(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")
        from db_engine import is_postgres

        assert is_postgres() is True

    def test_is_postgres_with_postgres_scheme(self, monkeypatch):
        """postgres:// (short form) is also recognised as PostgreSQL."""
        monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@localhost:5432/testdb")
        from db_engine import is_postgres

        assert is_postgres() is True

    def test_is_postgres_false_for_non_postgres_url(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./mydb.db")
        from db_engine import is_postgres

        assert is_postgres() is False

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
# get_db_connection() / get_db() — mocked psycopg2
# ---------------------------------------------------------------------------


class TestGetDbConnection:
    """get_db_connection() always returns a _PgConnWrapper."""

    def test_returns_pg_conn_wrapper(self, monkeypatch):
        """get_db_connection() delegates to get_pg_connection_raw()."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")
        fake_wrapper = MagicMock()

        with patch("models.get_pg_connection_raw", return_value=fake_wrapper):
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


class TestGetDbContextManager:
    """get_db() context manager — mocked psycopg2 connection lifecycle."""

    def test_yields_connection_and_closes_on_exit(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")
        fake_conn = MagicMock()

        with patch("models.get_pg_connection") as mock_get_pg:
            mock_get_pg.return_value.__enter__.return_value = fake_conn
            mock_get_pg.return_value.__exit__.return_value = False

            from models import get_db

            with get_db() as conn:
                assert conn is fake_conn
            mock_get_pg.return_value.__exit__.assert_called_once()


class TestInitDb:
    """init_db() requires Postgres and delegates to pg_init_db()."""

    def test_raises_without_postgres_url(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        from models import init_db

        with pytest.raises(RuntimeError, match="DATABASE_URL must be set"):
            init_db()

    def test_routes_to_pg_init_when_postgres_url(self, monkeypatch):
        """init_db() calls pg_init_db() when DATABASE_URL is postgresql://."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
        with patch("db_pg_init.pg_init_db") as mock_pg_init:
            import models

            models.init_db()
            assert mock_pg_init.call_count >= 1


# ---------------------------------------------------------------------------
# Model class methods via get_db() — real Postgres round-trip (app fixture)
# ---------------------------------------------------------------------------


class TestModelMethods:
    """User and Resume CRUD via get_db() round-trips against the test database."""

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
