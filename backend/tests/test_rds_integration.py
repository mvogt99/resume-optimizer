"""Tier 2 regression tests — RDS PostgreSQL (CLOUDLIFT_ENV=aws).

These tests hit a real RDS db.t3.micro instance and are skipped automatically
when CLOUDLIFT_ENV != "aws". They verify that the cloudlift_db_adapter correctly
resolves the DATABASE_URL from Secrets Manager and that the schema is healthy.

Run with:
    source ~/.zshrc
    CLOUDLIFT_ENV=aws AWS_REGION=us-east-1 PYTHONPATH=. pytest tests/test_rds_integration.py -v
"""
from __future__ import annotations

import os
import sys
import threading

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

pytestmark = pytest.mark.skipif(
    os.environ.get("CLOUDLIFT_ENV") != "aws",
    reason="RDS integration tests require CLOUDLIFT_ENV=aws",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_url() -> str:
    import cloudlift_db_adapter
    return cloudlift_db_adapter.resolve_database_url()


def _connect():
    from db_engine import get_pg_connection_raw
    return get_pg_connection_raw(_get_url())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRDSConnection:
    def test_url_is_postgresql(self):
        url = _get_url()
        assert url.startswith("postgresql://"), f"Expected postgresql:// URL, got: {url!r}"

    def test_connect_and_select_1(self):
        conn = _connect()
        try:
            cur = conn.execute("SELECT 1")
            row = cur.fetchone()
            assert row is not None
            assert row[0] == 1
        finally:
            conn.close()


class TestSchemaInitialized:
    REQUIRED_TABLES = [
        "users",
        "resumes",
        "journey_events",
        "journey_sources",
        "journey_mining_runs",
        "client_projects",
        "campaigns",
        "job_postings",
    ]

    def test_required_tables_exist(self):
        conn = _connect()
        try:
            cur = conn.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            )
            existing = {row["tablename"] for row in cur.fetchall()}
            missing = [t for t in self.REQUIRED_TABLES if t not in existing]
            assert not missing, f"Missing tables in RDS: {missing}"
        finally:
            conn.close()


class TestUserCRUD:
    def test_insert_fetch_delete_user(self):
        conn = _connect()
        try:
            test_email = "phase31_rds_test@example.com"
            # Clean up any previous test run
            conn.execute("DELETE FROM users WHERE email = %s", (test_email,))
            conn.commit()

            # Insert
            conn.execute(
                "INSERT INTO users (email, password_hash) VALUES (%s, %s)",
                (test_email, "testhash"),
            )
            conn.commit()

            # Fetch
            cur = conn.execute("SELECT email FROM users WHERE email = %s", (test_email,))
            row = cur.fetchone()
            assert row is not None, "User not found after insert"
            assert row["email"] == test_email

            # Delete
            conn.execute("DELETE FROM users WHERE email = %s", (test_email,))
            conn.commit()

            # Verify gone
            cur = conn.execute("SELECT email FROM users WHERE email = %s", (test_email,))
            assert cur.fetchone() is None
        finally:
            conn.close()


class TestJourneyEventCRUD:
    def test_insert_fetch_delete_journey_event(self):
        conn = _connect()
        try:
            test_user_id = 999901
            # Clean up
            conn.execute("DELETE FROM journey_events WHERE user_id = %s", (test_user_id,))
            conn.commit()

            # Insert
            conn.execute(
                """INSERT INTO journey_events
                   (event_date, title, description, category, user_id)
                   VALUES (%s, %s, %s, %s, %s)""",
                ("2026-05-04", "Phase3.1 RDS test", "Regression test row", "test", test_user_id),
            )
            conn.commit()

            # Fetch
            cur = conn.execute(
                "SELECT title, event_date FROM journey_events WHERE user_id = %s",
                (test_user_id,),
            )
            row = cur.fetchone()
            assert row is not None
            assert row["title"] == "Phase3.1 RDS test"
            assert row["event_date"] == "2026-05-04"

            # Delete
            conn.execute("DELETE FROM journey_events WHERE user_id = %s", (test_user_id,))
            conn.commit()
        finally:
            conn.close()


class TestJourneySourceCRUD:
    def test_insert_fetch_delete_journey_source(self):
        conn = _connect()
        try:
            test_user_id = 999902
            conn.execute("DELETE FROM journey_sources WHERE user_id = %s", (test_user_id,))
            conn.commit()

            conn.execute(
                """INSERT INTO journey_sources
                   (source_type, source_path, title, user_id)
                   VALUES (%s, %s, %s, %s)""",
                ("file", "/tmp/test.txt", "Phase3.1 source test", test_user_id),
            )
            conn.commit()

            cur = conn.execute(
                "SELECT title FROM journey_sources WHERE user_id = %s",
                (test_user_id,),
            )
            row = cur.fetchone()
            assert row is not None
            assert row["title"] == "Phase3.1 source test"

            conn.execute("DELETE FROM journey_sources WHERE user_id = %s", (test_user_id,))
            conn.commit()
        finally:
            conn.close()


class TestTransactionRollback:
    def test_rollback_prevents_commit(self):
        conn = _connect()
        test_email = "rollback_test_phase31@example.com"
        try:
            conn.execute("DELETE FROM users WHERE email = %s", (test_email,))
            conn.commit()

            # Insert then rollback
            conn.execute(
                "INSERT INTO users (email, password_hash) VALUES (%s, %s)",
                (test_email, "hash"),
            )
            conn.rollback()

            # Row must not exist
            cur = conn.execute("SELECT 1 FROM users WHERE email = %s", (test_email,))
            assert cur.fetchone() is None, "Rolled-back row should not be visible"
        finally:
            conn.close()


class TestConcurrentConnections:
    def test_three_concurrent_connections(self):
        errors: list[Exception] = []

        def _query():
            try:
                conn = _connect()
                try:
                    cur = conn.execute("SELECT COUNT(*) FROM users")
                    row = cur.fetchone()
                    assert row is not None
                finally:
                    conn.close()
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_query) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Concurrent connection errors: {errors}"
