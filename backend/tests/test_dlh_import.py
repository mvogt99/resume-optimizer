"""Tests for DLH platform structured analysis import (Track A, Phase 10).

Verifies import_structured_analysis() correctly transforms the DLH JSON
into the project_analyzer schema, stores in SQLite, and writes to ArangoDB.
"""

from conftest import ensure_user
import contextlib
import json
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import models
from project_analyzer import get_project_analyzer

# Path to the actual DLH analysis file
DLH_FILE = os.path.join(
    os.path.dirname(__file__), "..", "..", "uploads", "dlh_platform_analysis.json"
)


@pytest.fixture(autouse=True)
def _ensure_dlh_user():
    """Function-scoped: the per-test truncation wipes users, so seeding this in
    the module-scoped fixture only survived the first test in the file."""
    ensure_user(1)


@pytest.fixture(scope="module", autouse=True)
def _isolated_db(tmp_path_factory):
    """Create an isolated database so full-suite runs don't clobber DB_PATH."""

    original_db_path = models.DB_PATH

    tmp_dir = tmp_path_factory.mktemp("dlh_import")
    db_path = str(tmp_dir / "test.db")

    # Patch DB_PATH in models and all loaded modules
    models.DB_PATH = db_path
    for mod in list(sys.modules.values()):
        if mod is None or mod is models:
            continue
        if hasattr(mod, "DB_PATH") and isinstance(mod.DB_PATH, str):
            with contextlib.suppress(AttributeError, TypeError):
                mod.DB_PATH = db_path

    models.init_db()

    # Reset project_analyzer singleton so it uses the new DB
    import project_analyzer as _pa

    _pa._analyzer = None

    yield db_path

    # Restore original DB_PATH
    models.DB_PATH = original_db_path
    for mod in list(sys.modules.values()):
        if mod is None or mod is models:
            continue
        if hasattr(mod, "DB_PATH") and isinstance(mod.DB_PATH, str):
            with contextlib.suppress(AttributeError, TypeError):
                mod.DB_PATH = original_db_path
    _pa._analyzer = None


@pytest.fixture(scope="module")
def dlh_json():
    """Load the real DLH platform analysis JSON."""
    with open(DLH_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture()
def imported_client(dlh_json):
    # FUNCTION-scoped deliberately. The suite truncates every table before each
    # test, so a module-scoped import survives only until the second test in the
    # file and every later one then asserts against an empty database.
    """Import DLH data and return client_id."""
    analyzer = get_project_analyzer()
    client_id = analyzer.import_structured_analysis(
        user_id=1,
        analysis_json=dlh_json,
        client_name="Navitus",
    )
    return client_id


class TestDLHImport:
    """Tests for DLH platform import into Navitus project."""

    def test_import_creates_navitus_project(self, imported_client):
        """Project exists in DB with analysis_status=completed."""
        conn = models.get_db_connection()
        row = conn.execute(
            "SELECT client_name, analysis_status FROM client_projects WHERE id = ?",
            (imported_client,),
        ).fetchone()
        conn.close()

        assert row is not None, "Navitus project must exist after import"
        assert row["client_name"] == "Navitus"
        assert row["analysis_status"] == "completed"

    def test_dlh_technologies_stored(self, imported_client):
        """technical_analysis_json contains key DLH technologies."""
        analyzer = get_project_analyzer()
        client = analyzer.get_analysis(imported_client)
        assert client is not None

        tech_items = client.get("technical_analysis_json", [])
        tech_names = [t["name"] for t in tech_items if isinstance(t, dict)]

        # Core DLH platform technologies must be present
        assert any("CDK" in n for n in tech_names), f"AWS CDK not found in {tech_names}"
        assert any("Lambda" in n for n in tech_names), f"Lambda not found in {tech_names}"
        assert any("Iceberg" in n for n in tech_names), f"Iceberg not found in {tech_names}"
        assert any("Athena" in n for n in tech_names), f"Athena not found in {tech_names}"
        assert any("Glue" in n for n in tech_names), f"Glue not found in {tech_names}"

    def test_dlh_governance_stored(self, imported_client):
        """governance_analysis_json contains security + DQ controls."""
        analyzer = get_project_analyzer()
        client = analyzer.get_analysis(imported_client)
        gov_items = client.get("governance_analysis_json", [])

        gov_names = [g["name"].lower() for g in gov_items if isinstance(g, dict)]
        assert any(
            "quality" in n for n in gov_names
        ), f"Data quality not in governance: {gov_names}"

    def test_dlh_skills_stored(self, imported_client):
        """skills_json contains DLH endorsement keywords."""
        analyzer = get_project_analyzer()
        client = analyzer.get_analysis(imported_client)
        skills = client.get("skills_json", [])

        skill_names = [s["name"] for s in skills if isinstance(s, dict)]
        assert len(skill_names) >= 10, f"Expected 10+ skills, got {len(skill_names)}"
        assert any("Data Lakehouse" in n for n in skill_names), "Data Lakehouse skill missing"

    def test_dlh_achievements_stored(self, imported_client):
        """role_analysis_json captures architect achievements."""
        analyzer = get_project_analyzer()
        client = analyzer.get_analysis(imported_client)
        roles = client.get("role_analysis_json", [])

        assert len(roles) >= 5, f"Expected 5+ achievements, got {len(roles)}"
        titles = [r["title"] for r in roles if isinstance(r, dict)]
        assert any(
            "event" in t.lower() or "serverless" in t.lower() for t in titles
        ), f"No event-driven/serverless achievement found in {titles[:5]}"

    def test_dlh_outcomes_stored(self, imported_client):
        """business_outcomes_json has quantifiable metrics."""
        analyzer = get_project_analyzer()
        client = analyzer.get_analysis(imported_client)
        outcomes = client.get("business_outcomes_json", [])

        assert len(outcomes) >= 5, f"Expected 5+ outcomes, got {len(outcomes)}"
        descriptions = " ".join(o.get("description", "") for o in outcomes)
        assert (
            "24" in descriptions or "CDK" in descriptions.lower()
        ), "Expected CDK stack count (24) in outcomes"

    def test_dlh_idempotent_reimport(self, dlh_json):
        """Re-importing with same client_name reuses existing project."""
        analyzer = get_project_analyzer()
        id1 = analyzer.import_structured_analysis(
            user_id=1, analysis_json=dlh_json, client_name="Navitus"
        )
        id2 = analyzer.import_structured_analysis(
            user_id=1, analysis_json=dlh_json, client_name="Navitus"
        )
        assert id1 == id2, "Re-import must reuse existing project"


class TestDLHArangoApproval:
    """Tests for DLH approval → ArangoDB write."""

    def test_approve_writes_to_arango(self, imported_client):
        """Approving the analysis writes to ArangoDB knowledge graph."""
        analyzer = get_project_analyzer()
        result = analyzer.approve_analysis(imported_client)
        assert result is True, "approve_analysis must succeed"

        # Verify approval flag in DB
        conn = models.get_db_connection()
        row = conn.execute(
            "SELECT approved FROM client_projects WHERE id = ?",
            (imported_client,),
        ).fetchone()
        conn.close()
        assert row["approved"] == 1, "approved flag must be set"

    def test_arango_has_navitus_project(self, imported_client):
        """ArangoDB ro_client_projects has the Navitus entry."""
        try:
            from arango_client import get_arango_client

            arango = get_arango_client()
            if not arango.is_connected:
                pytest.skip("ArangoDB not connected")
        except Exception:
            pytest.skip("ArangoDB not available")

        # Query ArangoDB for Navitus
        import hashlib

        key = hashlib.sha1("project:Navitus".encode()).hexdigest()
        result = arango._db.collection("ro_client_projects").get(key)
        assert result is not None, "Navitus project must exist in ArangoDB"
        assert result["name"] == "Navitus"
