"""Route tests for campaigns_routes.py — interview, CRUD, posts, export, analytics.

Pure API tests. Monkeypatches LLM for campaign interview state machine.
"""

import json
import sqlite3

import pytest
from test_helpers import JD_TEXT, query_db

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _patch_campaign_llm(monkeypatch):
    """Block LLM — campaign_interview uses template fallback."""

    def fake_call_llm(prompt, task_type="coding", max_tokens=2048):
        return None

    monkeypatch.setattr("llm_helper.call_llm", fake_call_llm)


@pytest.fixture()
def campaign_id(client, auth_headers, app):
    """Create a campaign via direct DB insert (skipping interview)."""
    import models

    conn = sqlite3.connect(models.DB_PATH)
    conn.execute(
        "INSERT INTO campaigns "
        "(user_id, theme, audience, tone, storyline, post_count, cadence, status) "
        "VALUES (1, 'AI Thought Leadership', 'ML Engineers', 'professional', "
        "'Story of local AI deployment', 5, 'weekly', 'active')"
    )
    conn.commit()
    cid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return cid


# ---------------------------------------------------------------------------
# Campaign Interview
# ---------------------------------------------------------------------------


class TestCampaignInterview:
    def test_start_interview(self, client, auth_headers):
        resp = client.post(
            "/api/campaigns/interview/start",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code in (200, 201)
        data = resp.get_json()
        assert "session_id" in data
        assert isinstance(data["session_id"], str)
        # DB: session created
        rows = query_db("SELECT id FROM campaign_sessions WHERE user_id = 1")
        assert len(rows) >= 1

    def test_start_interview_with_theme(self, client, auth_headers):
        resp = client.post(
            "/api/campaigns/interview/start",
            headers=auth_headers,
            json={"theme": "AI Infrastructure"},
        )
        assert resp.status_code in (200, 201)
        data = resp.get_json()
        assert "session_id" in data

    def test_interview_message(self, client, auth_headers):
        start = client.post(
            "/api/campaigns/interview/start",
            headers=auth_headers,
            json={},
        )
        sid = start.get_json()["session_id"]
        resp = client.post(
            "/api/campaigns/interview/message",
            headers=auth_headers,
            json={"session_id": sid, "message": "AI Infrastructure and local models"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict)
        # Should have some response (question or status)
        assert "error" not in data
        # DB: messages stored
        rows = query_db("SELECT role FROM campaign_messages WHERE session_id = ?", (sid,))
        assert len(rows) >= 1

    def test_interview_state(self, client, auth_headers):
        start = client.post(
            "/api/campaigns/interview/start",
            headers=auth_headers,
            json={},
        )
        sid = start.get_json()["session_id"]
        resp = client.get(
            f"/api/campaigns/interview/{sid}/state",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "stage" in data or "state" in data or "context" in data


# ---------------------------------------------------------------------------
# Campaign CRUD
# ---------------------------------------------------------------------------


class TestCampaignCRUD:
    def test_list_campaigns_empty(self, client, auth_headers):
        resp = client.get("/api/campaigns", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list) or "campaigns" in data
        campaigns = data if isinstance(data, list) else data.get("campaigns", [])
        assert len(campaigns) == 0

    def test_list_campaigns_with_data(self, client, auth_headers, campaign_id):
        resp = client.get("/api/campaigns", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        campaigns = data if isinstance(data, list) else data.get("campaigns", [])
        assert len(campaigns) >= 1
        camp = campaigns[0]
        assert camp["theme"] == "AI Thought Leadership"
        assert camp["audience"] == "ML Engineers"
        # DB: verify
        rows = query_db("SELECT theme FROM campaigns WHERE user_id = 1")
        assert len(rows) >= 1

    def test_get_campaign(self, client, auth_headers, campaign_id):
        resp = client.get(f"/api/campaigns/{campaign_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["theme"] == "AI Thought Leadership"
        assert data["tone"] == "professional"
        assert data["post_count"] == 5

    def test_get_campaign_not_found(self, client, auth_headers):
        resp = client.get("/api/campaigns/99999", headers=auth_headers)
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data

    def test_update_campaign(self, client, auth_headers, campaign_id):
        resp = client.put(
            f"/api/campaigns/{campaign_id}",
            headers=auth_headers,
            json={"theme": "Updated Theme", "cadence": "biweekly"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "message" in data
        # DB: verify update persisted
        rows = query_db("SELECT theme, cadence FROM campaigns WHERE id = ?", (campaign_id,))
        assert rows[0]["theme"] == "Updated Theme"
        assert rows[0]["cadence"] == "biweekly"

    def test_update_campaign_not_found(self, client, auth_headers):
        resp = client.put(
            "/api/campaigns/99999",
            headers=auth_headers,
            json={"theme": "X"},
        )
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data

    def test_delete_campaign(self, client, auth_headers, campaign_id):
        resp = client.delete(f"/api/campaigns/{campaign_id}", headers=auth_headers)
        assert resp.status_code == 200
        # DB: verify deleted
        rows = query_db("SELECT id FROM campaigns WHERE id = ?", (campaign_id,))
        assert len(rows) == 0

    def test_delete_campaign_not_found(self, client, auth_headers):
        resp = client.delete("/api/campaigns/99999", headers=auth_headers)
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data


# ---------------------------------------------------------------------------
# Campaign Posts
# ---------------------------------------------------------------------------


class TestCampaignPosts:
    def test_list_posts_empty(self, client, auth_headers, campaign_id):
        resp = client.get(f"/api/campaigns/{campaign_id}/posts", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        posts = data if isinstance(data, list) else data.get("posts", [])
        assert len(posts) == 0

    def test_add_post(self, client, auth_headers, campaign_id):
        resp = client.post(
            f"/api/campaigns/{campaign_id}/posts",
            headers=auth_headers,
            json={
                "title": "Why Local AI Matters",
                "content": "In 2026, running AI locally on consumer GPUs is not just possible—it's practical.",
                "hashtags": "#AI #LocalAI #RTX5090",
            },
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert "id" in data or "post_id" in data
        pid = data.get("id") or data.get("post_id")
        # DB: verify post stored
        rows = query_db("SELECT title, content FROM campaign_posts WHERE id = ?", (pid,))
        assert len(rows) == 1
        assert rows[0]["title"] == "Why Local AI Matters"
        assert "practical" in rows[0]["content"]

    def test_update_post(self, client, auth_headers, campaign_id):
        # Add post first
        add = client.post(
            f"/api/campaigns/{campaign_id}/posts",
            headers=auth_headers,
            json={"title": "Original", "content": "First draft."},
        )
        pid = add.get_json().get("id") or add.get_json().get("post_id")

        resp = client.put(
            f"/api/campaigns/{campaign_id}/posts/{pid}",
            headers=auth_headers,
            json={"title": "Revised", "content": "Updated draft with more detail."},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "message" in data
        # DB: verify update persisted
        rows = query_db("SELECT title, content FROM campaign_posts WHERE id = ?", (pid,))
        assert rows[0]["title"] == "Revised"

    def test_delete_post(self, client, auth_headers, campaign_id):
        add = client.post(
            f"/api/campaigns/{campaign_id}/posts",
            headers=auth_headers,
            json={"title": "Delete Me", "content": "Temp."},
        )
        pid = add.get_json().get("id") or add.get_json().get("post_id")

        resp = client.delete(
            f"/api/campaigns/{campaign_id}/posts/{pid}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "message" in data
        # DB: verify deleted
        rows = query_db("SELECT id FROM campaign_posts WHERE id = ?", (pid,))
        assert len(rows) == 0

    def test_reorder_posts(self, client, auth_headers, campaign_id):
        ids = []
        for i in range(3):
            add = client.post(
                f"/api/campaigns/{campaign_id}/posts",
                headers=auth_headers,
                json={"title": f"Post {i}", "content": f"Content {i}"},
            )
            pid = add.get_json().get("id") or add.get_json().get("post_id")
            ids.append(pid)

        # Reverse order
        resp = client.put(
            f"/api/campaigns/{campaign_id}/posts/reorder",
            headers=auth_headers,
            json={"order": list(reversed(ids))},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "message" in data or "posts" in data


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


class TestCampaignExport:
    def test_export_empty_campaign(self, client, auth_headers, campaign_id):
        resp = client.get(f"/api/campaigns/{campaign_id}/export", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "text" in data or "export" in data
        assert "post_count" in data or isinstance(data.get("posts"), list)

    def test_export_with_posts(self, client, auth_headers, campaign_id):
        client.post(
            f"/api/campaigns/{campaign_id}/posts",
            headers=auth_headers,
            json={"title": "Post 1", "content": "Content here."},
        )
        resp = client.get(f"/api/campaigns/{campaign_id}/export", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        export_text = data.get("text", data.get("export", ""))
        assert "Post 1" in export_text or "Content here" in export_text

    def test_export_not_found(self, client, auth_headers):
        resp = client.get("/api/campaigns/99999/export", headers=auth_headers)
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data


# ---------------------------------------------------------------------------
# Isolation
# ---------------------------------------------------------------------------


class TestCampaignIsolation:
    def test_user2_cannot_see_user1_campaign(
        self, client, auth_headers, second_user_headers, campaign_id
    ):
        resp = client.get(f"/api/campaigns/{campaign_id}", headers=second_user_headers)
        assert resp.status_code == 404

    def test_user2_cannot_delete_user1_campaign(
        self, client, auth_headers, second_user_headers, campaign_id
    ):
        resp = client.delete(f"/api/campaigns/{campaign_id}", headers=second_user_headers)
        assert resp.status_code == 404
        # Verify still exists for user1
        resp2 = client.get(f"/api/campaigns/{campaign_id}", headers=auth_headers)
        assert resp2.status_code == 200


# ---------------------------------------------------------------------------
# Campaign Engagement Tracking (Phase 17.14) — 5090-generated, expert-validated
# ---------------------------------------------------------------------------


class TestCampaignEngagement:
    """Tests for engagement update + summary endpoints."""

    def _seed_campaign_with_posts(self):
        import sqlite3

        import models

        conn = sqlite3.connect(models.DB_PATH)
        conn.execute(
            "INSERT OR IGNORE INTO campaigns (id, user_id, theme, status) "
            "VALUES (99, 1, 'AI Journey', 'active')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO campaign_posts (id, campaign_id, title, content, char_count) "
            "VALUES (991, 99, 'Post A', 'Content A', 9)"
        )
        conn.execute(
            "INSERT OR IGNORE INTO campaign_posts (id, campaign_id, title, content, char_count) "
            "VALUES (992, 99, 'Post B', 'Content B', 9)"
        )
        conn.commit()
        conn.close()

    def test_engagement_update(self, client, auth_headers):
        self._seed_campaign_with_posts()
        resp = client.put(
            "/api/campaigns/99/posts/991/engagement",
            headers=auth_headers,
            json={"impressions": 100, "reactions": 25, "comments_count": 5, "shares": 3},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["impressions"] == 100
        assert data["reactions"] == 25
        assert data["shares"] == 3

    def test_engagement_summary_empty(self, client, auth_headers):
        self._seed_campaign_with_posts()
        resp = client.get("/api/campaigns/99/engagement-summary", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_impressions"] == 0
        assert data["posts_with_engagement"] == 0
        assert data["total_posts"] == 2

    def test_engagement_summary_with_data(self, client, auth_headers):
        self._seed_campaign_with_posts()
        # Record engagement on both posts
        client.put(
            "/api/campaigns/99/posts/991/engagement",
            headers=auth_headers,
            json={"impressions": 100, "reactions": 25, "comments_count": 5, "shares": 3},
        )
        client.put(
            "/api/campaigns/99/posts/992/engagement",
            headers=auth_headers,
            json={"impressions": 150, "reactions": 30, "comments_count": 7, "shares": 4},
        )

        resp = client.get("/api/campaigns/99/engagement-summary", headers=auth_headers)
        data = resp.get_json()
        assert data["total_impressions"] == 250
        assert data["total_reactions"] == 55
        assert data["total_comments"] == 12
        assert data["total_shares"] == 7
        assert data["posts_with_engagement"] == 2
        assert data["avg_engagement_rate"] > 0
        assert data["top_performing_post"] is not None
        assert data["top_performing_post"]["reactions"] == 30

    def test_engagement_not_found(self, client, auth_headers):
        resp = client.put(
            "/api/campaigns/999/posts/1/engagement", headers=auth_headers, json={"impressions": 100}
        )
        assert resp.status_code == 404

    def test_engagement_auth_required(self, client):
        resp = client.put("/api/campaigns/99/posts/991/engagement", json={"impressions": 100})
        assert resp.status_code == 401
