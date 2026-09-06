"""Test seed_builder_sources.py — data seeding for builder workflow.

Tests the seeding functions against a temporary SQLite database using the real schema.
"""

from conftest import ensure_user
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from models import get_db_connection

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _create_seeded_db():
    """Create a temp database with real schema and run seed functions."""
    # Use a temp file so seed_builder_sources can use models.DB_PATH
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Temporarily override DB_PATH
    import models

    original_path = models.DB_PATH
    models.DB_PATH = db_path

    # Initialize with real schema
    models.init_db()

    # Now run seed functions
    import importlib

    import seed_builder_sources as sbs

    importlib.reload(sbs)  # pick up new DB_PATH

    ensure_user(1)  # seed_client_projects writes client_projects.user_id = 1
    conn = get_db_connection()
    cursor = conn.cursor()

    sbs.seed_client_projects(cursor)
    conn.commit()

    try:
        sbs.seed_journey_narratives(cursor)
        conn.commit()
    except Exception:
        pass  # May fail if table doesn't exist in this schema version

    try:
        sbs.seed_extracted_experiences(cursor)
        conn.commit()
    except Exception:
        pass

    models.DB_PATH = original_path  # restore
    return conn, db_path


class TestSeedClientProjects:
    def test_seeds_at_least_two_projects(self):
        conn, path = _create_seeded_db()
        rows = conn.execute("SELECT * FROM client_projects").fetchall()
        assert len(rows) >= 2
        os.unlink(path)

    def test_projects_have_client_names(self):
        conn, path = _create_seeded_db()
        rows = conn.execute("SELECT client_name FROM client_projects").fetchall()
        for row in rows:
            assert row["client_name"] is not None
            assert len(row["client_name"]) > 0
        os.unlink(path)

    def test_projects_are_approved(self):
        conn, path = _create_seeded_db()
        rows = conn.execute("SELECT approved FROM client_projects").fetchall()
        for row in rows:
            assert row["approved"] == 1
        os.unlink(path)

    def test_technical_analysis_is_valid_json(self):
        conn, path = _create_seeded_db()
        rows = conn.execute("SELECT technical_analysis_json FROM client_projects").fetchall()
        for row in rows:
            data = json.loads(row["technical_analysis_json"])
            assert "technologies" in data
            assert isinstance(data["technologies"], list)
        os.unlink(path)

    def test_projects_have_folder_ids(self):
        conn, path = _create_seeded_db()
        rows = conn.execute("SELECT folder_id FROM client_projects").fetchall()
        for row in rows:
            assert row["folder_id"] is not None
            assert len(row["folder_id"]) > 0
        os.unlink(path)

    def test_governance_analysis_is_valid_json(self):
        conn, path = _create_seeded_db()
        rows = conn.execute("SELECT governance_analysis_json FROM client_projects").fetchall()
        for row in rows:
            data = json.loads(row["governance_analysis_json"])
            assert isinstance(data, dict)
        os.unlink(path)

    def test_role_analysis_has_contributions(self):
        conn, path = _create_seeded_db()
        rows = conn.execute("SELECT role_analysis_json FROM client_projects").fetchall()
        for row in rows:
            data = json.loads(row["role_analysis_json"])
            assert "contributions" in data or "outcomes" in data
        os.unlink(path)

    def test_projects_have_user_id(self):
        conn, path = _create_seeded_db()
        rows = conn.execute("SELECT user_id FROM client_projects").fetchall()
        for row in rows:
            assert row["user_id"] == 1  # seed uses USER_ID=1
        os.unlink(path)

    def test_projects_have_analysis_status(self):
        conn, path = _create_seeded_db()
        rows = conn.execute("SELECT analysis_status FROM client_projects").fetchall()
        for row in rows:
            assert row["analysis_status"] == "complete"
        os.unlink(path)

    def test_projects_have_document_counts(self):
        conn, path = _create_seeded_db()
        rows = conn.execute("SELECT document_count FROM client_projects").fetchall()
        for row in rows:
            assert row["document_count"] >= 1
        os.unlink(path)
