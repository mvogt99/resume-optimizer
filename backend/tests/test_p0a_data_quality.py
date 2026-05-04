import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "migrations"))
from data_quality_p0a import (
    clean_journey_events,
    dedup_client_projects,
    insert_milestone_events,
    run_migration,
)


@pytest.fixture(scope="function")
def db_conn():
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE client_projects (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            client_name TEXT,
            folder_id TEXT,
            created_at TEXT
        )
    """
    )
    cursor.execute(
        """
        CREATE TABLE journey_events (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            title TEXT,
            description TEXT,
            event_date TEXT,
            category TEXT,
            source_ids TEXT,
            technologies TEXT,
            metrics TEXT,
            confidence REAL,
            created_at TEXT
        )
    """
    )
    conn.commit()
    yield conn
    conn.close()


def test_dedup_removes_older_duplicates(db_conn):
    cursor = db_conn.cursor()
    cursor.executemany(
        "INSERT INTO client_projects"
        " (id, user_id, client_name, folder_id, created_at) VALUES (?, ?, ?, ?, ?)",
        [
            (1, 1, "AHEAD", "F1", "2023-01-01"),
            (2, 1, "AHEAD", "F2", "2023-01-02"),
            (3, 1, "AHEAD", "F3", "2023-01-03"),
        ],
    )
    db_conn.commit()
    result = dedup_client_projects(db_conn)
    cursor.execute('SELECT COUNT(*) FROM client_projects WHERE client_name="AHEAD"')
    assert cursor.fetchone()[0] == 1
    assert result["AHEAD"]["kept_id"] == 3


def test_dedup_preserves_unique_clients(db_conn):
    cursor = db_conn.cursor()
    cursor.executemany(
        "INSERT INTO client_projects"
        " (id, user_id, client_name, folder_id, created_at) VALUES (?, ?, ?, ?, ?)",
        [
            (1, 1, "AHEAD", "F1", "2023-01-01"),
            (2, 2, "OPI", "F2", "2023-01-02"),
        ],
    )
    db_conn.commit()
    dedup_client_projects(db_conn)
    cursor.execute('SELECT COUNT(*) FROM client_projects WHERE client_name IN ("AHEAD", "OPI")')
    assert cursor.fetchone()[0] == 2


def test_dedup_idempotent(db_conn):
    cursor = db_conn.cursor()
    cursor.executemany(
        "INSERT INTO client_projects"
        " (id, user_id, client_name, folder_id, created_at) VALUES (?, ?, ?, ?, ?)",
        [
            (1, 1, "AHEAD", "F1", "2023-01-01"),
            (2, 1, "AHEAD", "F2", "2023-01-02"),
            (3, 1, "AHEAD", "F3", "2023-01-03"),
        ],
    )
    db_conn.commit()
    dedup_client_projects(db_conn)
    dedup_client_projects(db_conn)
    cursor.execute('SELECT COUNT(*) FROM client_projects WHERE client_name="AHEAD"')
    assert cursor.fetchone()[0] == 1


def test_clean_removes_session_prefix(db_conn):
    cursor = db_conn.cursor()
    cursor.execute("INSERT INTO journey_events (title) VALUES (?)", ("SESSION HANDOFF 2026",))
    db_conn.commit()
    clean_journey_events(db_conn)
    cursor.execute("SELECT COUNT(*) FROM journey_events")
    assert cursor.fetchone()[0] == 0


def test_clean_removes_archive_prefix(db_conn):
    cursor = db_conn.cursor()
    cursor.execute("INSERT INTO journey_events (title) VALUES (?)", ("ARCHIVE REVIEW REPORT",))
    db_conn.commit()
    clean_journey_events(db_conn)
    cursor.execute("SELECT COUNT(*) FROM journey_events")
    assert cursor.fetchone()[0] == 0


def test_clean_removes_stub_words(db_conn):
    cursor = db_conn.cursor()
    cursor.executemany(
        "INSERT INTO journey_events (title) VALUES (?)",
        [("teaching",), ("learnings",), ("---",)],
    )
    db_conn.commit()
    clean_journey_events(db_conn)
    cursor.execute("SELECT COUNT(*) FROM journey_events")
    assert cursor.fetchone()[0] == 0


def test_clean_removes_short_titles(db_conn):
    cursor = db_conn.cursor()
    cursor.execute("INSERT INTO journey_events (title) VALUES (?)", ("abc",))
    db_conn.commit()
    clean_journey_events(db_conn)
    cursor.execute("SELECT COUNT(*) FROM journey_events")
    assert cursor.fetchone()[0] == 0


def test_clean_preserves_good_events(db_conn):
    cursor = db_conn.cursor()
    cursor.execute(
        "INSERT INTO journey_events (title) VALUES (?)",
        ("Led enterprise data platform modernization at Navitus",),
    )
    db_conn.commit()
    clean_journey_events(db_conn)
    cursor.execute("SELECT COUNT(*) FROM journey_events")
    assert cursor.fetchone()[0] == 1


def test_clean_idempotent(db_conn):
    cursor = db_conn.cursor()
    cursor.execute("INSERT INTO journey_events (title) VALUES (?)", ("teaching",))
    db_conn.commit()
    clean_journey_events(db_conn)
    clean_journey_events(db_conn)
    cursor.execute("SELECT COUNT(*) FROM journey_events")
    assert cursor.fetchone()[0] == 0


def test_insert_milestones_creates_4_events(db_conn):
    result = insert_milestone_events(db_conn)
    cursor = db_conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM journey_events")
    assert cursor.fetchone()[0] == 4
    assert len(result["inserted"]) == 4


def test_insert_milestones_idempotent(db_conn):
    insert_milestone_events(db_conn)
    result = insert_milestone_events(db_conn)
    cursor = db_conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM journey_events")
    assert cursor.fetchone()[0] == 4
    assert len(result["skipped"]) == 4


def test_run_migration_returns_keys(tmp_path):
    db_path = str(tmp_path / "test.db")
    # Need to pre-create tables for standalone run_migration
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE client_projects (
        id INTEGER PRIMARY KEY, user_id INTEGER, client_name TEXT,
        folder_id TEXT, created_at TEXT)"""
    )
    conn.execute(
        """CREATE TABLE journey_events (
        id INTEGER PRIMARY KEY, user_id INTEGER, title TEXT, description TEXT,
        event_date TEXT, category TEXT, source_ids TEXT, technologies TEXT,
        metrics TEXT, confidence REAL, created_at TEXT)"""
    )
    conn.commit()
    conn.close()
    result = run_migration(db_path)
    assert isinstance(result, dict)
    assert "dedup_clients" in result
    assert "cleaned_events" in result
    assert "inserted_milestones" in result
