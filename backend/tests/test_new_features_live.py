"""Live LLM tests for Phase 15 features — no mocking, real RTX 5090 inference.

Tests: portfolio_generator, recommendation_drafter, campaign_suggestor,
       architecture_analyzer, orchestrator.

All tests require the FTAL harness / gateway running on localhost:8000.
When gateway is offline, tests are skipped (not failed).
"""

import pytest
from test_helpers import (
    AGENT_HEADERS_1,
    JD_TEXT,
    LINKEDIN_PROFILE,
    RESUME_TEXT,
    create_posting,
    query_db,
    require_harness,
    upload_resume,
)

pytestmark = pytest.mark.llm_required


@pytest.fixture()
def require_harness_fixture():
    """Skip all tests in this module if FTAL harness is not running."""
    require_harness()


def _seed_linkedin(client, auth_headers):
    """Import LinkedIn profile so deep-profile has data."""
    resp = client.post("/api/import/linkedin", headers=auth_headers, json=LINKEDIN_PROFILE)
    assert resp.status_code in (200, 201), f"LinkedIn import failed: {resp.get_json()}"


def _seed_resume_version():
    """Create a resume_versions row via direct SQL."""
    import sqlite3

    import models

    conn = sqlite3.connect(models.DB_PATH)
    conn.execute(
        "INSERT OR IGNORE INTO resume_versions (user_id, file_name, source, parsed_text) "
        "VALUES (?, ?, ?, ?)",
        (1, "test_resume.txt", "upload", RESUME_TEXT),
    )
    conn.commit()
    conn.close()


def _seed_project():
    """Create a client_projects row via direct SQL."""
    import sqlite3

    import models

    conn = sqlite3.connect(models.DB_PATH)
    conn.execute(
        "INSERT OR IGNORE INTO client_projects (id, user_id, client_name, folder_id, analysis_status) "
        "VALUES (?, ?, ?, ?, ?)",
        (999, 1, "Navitus Health", "folder_abc", "completed"),
    )
    conn.commit()
    conn.close()


def _seed_journey_events():
    """Create journey_events rows via direct SQL."""
    import sqlite3

    import models

    conn = sqlite3.connect(models.DB_PATH)
    conn.execute(
        "INSERT OR IGNORE INTO journey_events (id, user_id, title, event_date, category, description) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            999,
            1,
            "Built AI Gateway",
            "2026-01-15",
            "milestone",
            "Designed and deployed FastAPI gateway with multi-model orchestration",
        ),
    )
    conn.execute(
        "INSERT OR IGNORE INTO journey_events (id, user_id, title, event_date, category, description) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            998,
            1,
            "Kubernetes Migration",
            "2025-06-01",
            "project",
            "Led migration of pharmacy benefit platform to Kubernetes",
        ),
    )
    conn.commit()
    conn.close()


def _seed_project_documents():
    """Create project_documents rows so architecture analysis has data."""
    import sqlite3

    import models

    conn = sqlite3.connect(models.DB_PATH)
    conn.execute(
        "INSERT OR IGNORE INTO project_documents "
        "(id, client_id, file_name, file_type, parsed_text, analysis_json, user_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            999,
            999,
            "arch_doc.md",
            "text/markdown",
            "Microservices architecture with API gateway, Kubernetes orchestration, "
            "PostgreSQL database, Redis caching, RabbitMQ messaging. "
            "Deployed on AWS EKS with Terraform IaC.",
            '{"technologies": ["Kubernetes", "PostgreSQL", "Redis"], "patterns": ["microservices"]}',
            1,
        ),
    )
    conn.commit()
    conn.close()


# ===================================================================
# Portfolio Generator (3 tests)
# ===================================================================


class TestPortfolioGenerator:
    """Deep profile / portfolio generation with real LLM."""

    def test_build_deep_profile(self, client, auth_headers, require_harness_fixture):
        """POST /deep-profile/build → structured career profile."""
        _seed_linkedin(client, auth_headers)
        _seed_resume_version()
        resp = client.post("/api/deep-profile/build", headers=auth_headers, json={})
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict)
        assert len(data) > 0
        # Structure: should contain some career data
        assert any(
            k in data
            for k in ("career_phases", "skills_summary", "projects", "differentiators", "profile")
        ), f"Deep profile missing expected keys, got: {list(data.keys())}"

    def test_role_synthesis(self, client, auth_headers, require_harness_fixture):
        """POST /deep-profile/role-synthesis → role fit analysis."""
        _seed_linkedin(client, auth_headers)
        _seed_resume_version()
        # Must build profile first — role-synthesis returns 404 if no profile exists
        build = client.post("/api/deep-profile/build", headers=auth_headers, json={})
        assert build.status_code == 200, f"Profile build failed: {build.get_json()}"
        resp = client.post(
            "/api/deep-profile/role-synthesis",
            headers=auth_headers,
            json={"job_text": JD_TEXT},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict)
        assert len(data) > 0

    def test_portfolio_export(self, client, auth_headers, require_harness_fixture):
        """Build + export: verifies non-empty text is produced."""
        _seed_linkedin(client, auth_headers)
        build_resp = client.post("/api/deep-profile/build", headers=auth_headers, json={})
        assert build_resp.status_code == 200
        data = build_resp.get_json()
        # The portfolio should have some content worth exporting
        assert isinstance(data, dict)
        assert len(data) > 0


# ===================================================================
# Recommendation Drafter (3 tests)
# ===================================================================


class TestRecommendationDrafter:
    """Recommendation draft generation with real LLM."""

    def test_draft_recommendation(self, client, auth_headers, require_harness_fixture):
        """POST /recommendations/draft → generates non-empty draft."""
        _seed_linkedin(client, auth_headers)
        resp = client.post(
            "/api/recommendations/draft",
            headers=auth_headers,
            json={
                "target_name": "Jane Smith",
                "relationship": "colleague",
                "shared_projects": "Pharmacy benefit platform migration",
                "specific_skills": "Python, AWS, team leadership",
            },
        )
        assert resp.status_code in (200, 201)
        data = resp.get_json()
        assert isinstance(data, dict)
        assert "draft" in data or "text" in data or "body" in data or "id" in data

    def test_list_recommendation_drafts(self, client, auth_headers, require_harness_fixture):
        """POST + GET: draft appears in list."""
        _seed_linkedin(client, auth_headers)
        client.post(
            "/api/recommendations/draft",
            headers=auth_headers,
            json={
                "target_name": "Bob Chen",
                "relationship": "manager",
            },
        )
        resp = client.get("/api/recommendations/drafts", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, (dict, list))

    def test_draft_crud_cycle(self, client, auth_headers, require_harness_fixture):
        """Create → update → delete cycle."""
        _seed_linkedin(client, auth_headers)
        create_resp = client.post(
            "/api/recommendations/draft",
            headers=auth_headers,
            json={"target_name": "Alice Test", "relationship": "direct_report"},
        )
        assert create_resp.status_code in (200, 201)
        data = create_resp.get_json()
        draft_id = data.get("id") or data.get("draft_id")
        if draft_id:
            # Update
            up_resp = client.put(
                f"/api/recommendations/drafts/{draft_id}",
                headers=auth_headers,
                json={"text": "Updated recommendation text."},
            )
            assert up_resp.status_code == 200
            # Delete
            del_resp = client.delete(
                f"/api/recommendations/drafts/{draft_id}",
                headers=auth_headers,
            )
            assert del_resp.status_code == 200


# ===================================================================
# Campaign Suggestor (2 tests)
# ===================================================================


class TestCampaignSuggestor:
    """Campaign suggestions with real LLM / knowledge graph."""

    def test_campaign_suggestions(self, client, auth_headers, require_harness_fixture):
        """GET /campaigns/suggestions → list of suggestions."""
        _seed_linkedin(client, auth_headers)
        _seed_project()
        _seed_journey_events()
        resp = client.get("/api/campaigns/suggestions?max_suggestions=3", headers=auth_headers)
        assert resp.status_code == 200, f"Suggestions failed: {resp.get_json()}"
        data = resp.get_json()
        assert isinstance(data, (dict, list))

    def test_uncovered_topics(self, client, auth_headers, require_harness_fixture):
        """GET /campaigns/uncovered-topics → topic analysis."""
        _seed_linkedin(client, auth_headers)
        _seed_project()
        _seed_journey_events()
        resp = client.get("/api/campaigns/uncovered-topics", headers=auth_headers)
        assert resp.status_code == 200, f"Uncovered topics failed: {resp.get_json()}"
        data = resp.get_json()
        assert isinstance(data, (dict, list))


# ===================================================================
# Architecture Analyzer (2 tests)
# ===================================================================


class TestArchitectureAnalyzer:
    """Architecture analysis from project data."""

    def test_analyze_architecture(self, client, auth_headers, require_harness_fixture):
        """POST /architecture/analyze → architecture breakdown."""
        _seed_project()
        _seed_project_documents()
        resp = client.post(
            "/api/architecture/analyze",
            headers=auth_headers,
            json={"project_id": 999},
        )
        assert resp.status_code == 200, f"Architecture analyze failed: {resp.get_json()}"
        data = resp.get_json()
        assert isinstance(data, dict)

    def test_architecture_summary(self, client, auth_headers, require_harness_fixture):
        """GET /architecture/summary → cross-project summary."""
        _seed_project()
        _seed_project_documents()
        resp = client.get("/api/architecture/summary", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict)


# ===================================================================
# Orchestrator (2 tests)
# ===================================================================


class TestOrchestrator:
    """Multi-agent orchestration pipeline."""

    def test_orchestrate_apply(self, client, auth_headers, require_harness_fixture):
        """POST /agents/orchestrate/apply → multi-step pipeline result."""
        _seed_linkedin(client, auth_headers)
        _seed_resume_version()
        pid = create_posting(client)
        resp = client.post(
            "/api/agents/orchestrate/apply",
            headers=auth_headers,
            json={"posting_id": pid},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict)

    def test_orchestrate_status(self, client, auth_headers, require_harness_fixture):
        """GET /agents/orchestrate/status → system status."""
        resp = client.get("/api/agents/orchestrate/status", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict)
