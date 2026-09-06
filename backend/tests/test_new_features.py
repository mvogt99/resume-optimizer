"""Tests for Phase 15 new feature routes — version diff, portfolio,
recommendations, campaign analytics, suggestions, architecture analysis."""

from conftest import ensure_user
import json
import uuid

import pytest

AUTH = {"user-id": "1", "Content-Type": "application/json"}


class TestVersionDiff:
    """Resume version diffing routes."""

    def _create_versions(self, client):
        """Create two resume versions for user 1 in the test DB."""
        import sqlite3

        import models

        ensure_user(1)
        conn = models.get_db_connection()
        conn.execute(
            "INSERT INTO resume_versions (user_id, file_name, source, parsed_text) "
            "VALUES (?, ?, ?, ?)",
            (1, "resume_v1.pdf", "upload", "SKILLS\nPython\nFlask\nSQL"),
        )
        conn.execute(
            "INSERT INTO resume_versions (user_id, file_name, source, parsed_text) "
            "VALUES (?, ?, ?, ?)",
            (1, "resume_v2.pdf", "optimized", "SKILLS\nPython\nFlask\nReact\nDocker"),
        )
        conn.commit()
        # Get the auto-generated IDs
        rows = conn.execute(
            "SELECT id FROM resume_versions WHERE user_id = 1 ORDER BY id"
        ).fetchall()
        conn.close()
        return rows[0][0], rows[1][0]

    def test_list_versions_for_diff(self, client):
        self._create_versions(client)
        resp = client.get("/api/versions/for-diff", headers=AUTH)
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) >= 2

    def test_diff_two_versions(self, client):
        vid_a, vid_b = self._create_versions(client)
        resp = client.post(
            "/api/versions/diff",
            headers=AUTH,
            json={"version_a": vid_a, "version_b": vid_b},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "diff_lines" in data
        assert data["stats"]["added"] > 0

    def test_diff_same_version(self, client):
        vid_a, _ = self._create_versions(client)
        resp = client.post(
            "/api/versions/diff",
            headers=AUTH,
            json={"version_a": vid_a, "version_b": vid_a},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["stats"]["added"] == 0
        assert data["stats"]["removed"] == 0

    def test_diff_nonexistent_version(self, client):
        resp = client.post(
            "/api/versions/diff",
            headers=AUTH,
            json={"version_a": "fake-id", "version_b": "also-fake"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "error" in data

    def test_unauthenticated(self, client):
        resp = client.get("/api/versions/for-diff")
        assert resp.status_code == 401


class TestPortfolio:
    """Portfolio generation routes — monkeypatch at route level."""

    def test_generate_portfolio(self, client, monkeypatch):
        fake_result = {
            "name": "Test User",
            "headline": "Engineer",
            "sections": [{"title": "Projects", "items": []}],
            "skills_summary": ["Python", "Flask"],
            "education": [],
        }
        monkeypatch.setattr(
            "routes.new_features_routes.generate_portfolio", lambda uid: fake_result
        )
        resp = client.post("/api/portfolio/generate", headers=AUTH)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["name"] == "Test User"
        assert "sections" in data

    def test_export_portfolio_text(self, client, monkeypatch):
        fake_result = {"text": "Portfolio content here", "sections": 1, "projects": 2}
        monkeypatch.setattr(
            "routes.new_features_routes.export_portfolio_text", lambda uid: fake_result
        )
        resp = client.get("/api/portfolio/export", headers=AUTH)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "text" in data
        assert isinstance(data["text"], str)

    def test_unauthenticated(self, client):
        resp = client.post("/api/portfolio/generate")
        assert resp.status_code == 401


class TestRecommendationDrafts:
    """Recommendation request drafting routes."""

    def test_create_and_list_drafts(self, client, monkeypatch):
        fake_draft = {
            "id": "test-draft-123",
            "draft": "I recommend this person.",
            "subject": "Recommendation request",
            "target_name": "Alice",
            "relationship": "colleague",
            "char_count": 28,
        }
        monkeypatch.setattr(
            "routes.new_features_routes.draft_recommendation_request",
            lambda uid, tn, rel, sp, sk: fake_draft,
        )
        resp = client.post(
            "/api/recommendations/draft",
            headers=AUTH,
            json={"target_name": "Alice", "relationship": "colleague"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == "test-draft-123"
        assert data["target_name"] == "Alice"

    def test_list_drafts(self, client, monkeypatch):
        monkeypatch.setattr(
            "routes.new_features_routes.list_drafts",
            lambda uid: [{"id": "d1", "target_name": "Bob", "draft_text": "text"}],
        )
        resp = client.get("/api/recommendations/drafts", headers=AUTH)
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) == 1

    def test_update_draft(self, client, monkeypatch):
        monkeypatch.setattr(
            "routes.new_features_routes.update_draft",
            lambda did, uid, txt: {"id": did, "draft_text": txt, "char_count": len(txt)},
        )
        resp = client.put(
            "/api/recommendations/drafts/d1",
            headers=AUTH,
            json={"text": "Updated text"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["draft_text"] == "Updated text"

    def test_delete_draft(self, client, monkeypatch):
        monkeypatch.setattr(
            "routes.new_features_routes.delete_draft",
            lambda did, uid: {"deleted": True, "id": did},
        )
        resp = client.delete("/api/recommendations/drafts/d1", headers=AUTH)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["deleted"] is True

    def test_delete_nonexistent(self, client, monkeypatch):
        monkeypatch.setattr(
            "routes.new_features_routes.delete_draft",
            lambda did, uid: {"error": "Draft not found or not yours"},
        )
        resp = client.delete("/api/recommendations/drafts/fake-uuid", headers=AUTH)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "error" in data

    def test_unauthenticated(self, client):
        resp = client.get("/api/recommendations/drafts")
        assert resp.status_code == 401


class TestCampaignAnalytics:
    """Cross-campaign analytics routes."""

    def test_cross_analytics_empty(self, client):
        resp = client.get("/api/campaigns/cross-analytics", headers=AUTH)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "total_campaigns" in data
        assert data["total_campaigns"] == 0

    def test_campaign_comparison_empty(self, client):
        resp = client.get("/api/campaigns/comparison", headers=AUTH)
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_cross_analytics_with_data(self, client):
        """Insert campaigns and verify analytics."""
        import sqlite3

        import models

        conn = models.get_db_connection()
        # campaigns: id INTEGER PK, campaign_posts: campaign_id INTEGER FK
        conn.execute(
            "INSERT INTO campaigns (user_id, theme, audience, tone, status) VALUES (?, ?, ?, ?, ?)",
            (1, "Technology", "Engineers", "professional", "published"),
        )
        cid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO campaign_posts (campaign_id, content, position, status) VALUES (?, ?, ?, ?)",
            (cid, "Post about #Python and #Flask", 1, "published"),
        )
        conn.commit()
        conn.close()

        resp = client.get("/api/campaigns/cross-analytics", headers=AUTH)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_campaigns"] == 1
        assert data["total_posts"] == 1

    def test_unauthenticated(self, client):
        resp = client.get("/api/campaigns/cross-analytics")
        assert resp.status_code == 401


class TestCampaignSuggestions:
    """Campaign suggestion routes."""

    def test_suggestions(self, client, monkeypatch):
        fake = {
            "suggestions": [
                {
                    "theme": "AI",
                    "audience": "Tech",
                    "rationale": "New trend",
                    "source_type": "event",
                    "source_reference": "AI conf",
                }
            ],
            "based_on": {"new_events": 1, "uncovered_projects": 0, "trending_skills": 0},
        }
        monkeypatch.setattr("routes.new_features_routes.suggest_campaigns", lambda uid, max_s: fake)
        resp = client.get("/api/campaigns/suggestions", headers=AUTH)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "suggestions" in data
        assert len(data["suggestions"]) == 1

    def test_uncovered_topics(self, client, monkeypatch):
        fake = {"uncovered_projects": [], "uncovered_events": []}
        monkeypatch.setattr("routes.new_features_routes.get_uncovered_topics", lambda uid: fake)
        resp = client.get("/api/campaigns/uncovered-topics", headers=AUTH)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "uncovered_projects" in data

    def test_unauthenticated(self, client):
        resp = client.get("/api/campaigns/suggestions")
        assert resp.status_code == 401


class TestArchitectureAnalysis:
    """Architecture analysis routes."""

    def test_analyze_no_docs(self, client, monkeypatch):
        fake = {
            "project": "",
            "components": [],
            "integrations": [],
            "patterns": [],
            "technology_stack": [],
            "recommendations": [],
            "error": "No architecture-related documents found",
        }
        monkeypatch.setattr(
            "routes.new_features_routes.analyze_architecture", lambda uid, pid: fake
        )
        resp = client.post(
            "/api/architecture/analyze",
            headers=AUTH,
            json={"project_id": "nonexistent"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "components" in data

    def test_summary_empty(self, client, monkeypatch):
        fake = {
            "projects_analyzed": 0,
            "common_technologies": [],
            "common_patterns": [],
            "integration_map": {},
        }
        monkeypatch.setattr("routes.new_features_routes.get_architecture_summary", lambda uid: fake)
        resp = client.get("/api/architecture/summary", headers=AUTH)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["projects_analyzed"] == 0

    def test_unauthenticated(self, client):
        resp = client.post("/api/architecture/analyze", json={})
        assert resp.status_code == 401


class TestOrchestratorRoutes:
    """Orchestrator agent routes."""

    def test_orchestrate_status(self, client, monkeypatch):
        class FakeOrch:
            def get_workflow_status(self, uid):
                return {"active": False, "completed": 0}

        # get_orchestrator is imported lazily inside the route function from agents module
        monkeypatch.setattr("agents.get_orchestrator", lambda: FakeOrch())
        resp = client.get("/api/agents/orchestrate/status", headers=AUTH)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "active" in data or "completed" in data

    def test_unauthenticated(self, client):
        resp = client.get("/api/agents/orchestrate/status")
        assert resp.status_code == 401
