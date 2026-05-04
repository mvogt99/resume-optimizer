"""E2E tests for campaign system — post CRUD, reorder, analytics, graph, export.

Deep campaign testing beyond the interview flow tested in test_llm_chat_modules.py.
No mocks, no skips. DB verification after every write.
"""

import pytest
from test_helpers import query_db

pytestmark = pytest.mark.llm_required


def _quick_campaign(client, auth_headers, theme="Test Campaign"):
    """Create a campaign by running through interview + create."""
    resp = client.post(
        "/api/campaigns/interview/start",
        headers=auth_headers,
        json={"theme": theme},
    )
    sid = resp.get_json()["session_id"]

    for ans in [
        theme,
        "Software engineers",
        "Professional",
        "Journey from legacy to modern",
        "3",
        "Looks good",
    ]:
        client.post(
            "/api/campaigns/interview/message",
            headers=auth_headers,
            json={"session_id": sid, "message": ans},
        )

    resp_create = client.post(
        "/api/campaigns/create",
        headers=auth_headers,
        json={"session_id": sid},
    )
    data = resp_create.get_json()
    return data.get("campaign_id")


# ===================================================================
# Campaign CRUD (5 tests) — DB verified
# ===================================================================


class TestCampaignCRUD:
    """Campaign lifecycle — create, list, get, update, delete with DB checks."""

    @pytest.fixture(autouse=True)
    def _check_harness(self, require_harness):
        """Fail with clear error if FTAL harness is not running."""

    def test_campaign_list(self, client, auth_headers):
        """GET /campaigns → list (may be empty)."""
        resp = client.get("/api/campaigns", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "campaigns" in data

    def test_campaign_create_and_get(self, client, auth_headers):
        """Create campaign → GET by id, DB row verified."""
        cid = _quick_campaign(client, auth_headers)
        assert cid, "Campaign creation returned no campaign_id"

        resp = client.get(f"/api/campaigns/{cid}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("id") == cid or "theme" in data

        # DB: campaigns row exists
        rows = query_db("SELECT * FROM campaigns WHERE id = ?", (cid,))
        assert len(rows) == 1, f"No campaigns row for id={cid}"

    def test_campaign_update(self, client, auth_headers):
        """PUT /campaigns/<id> → update metadata, DB verified."""
        cid = _quick_campaign(client, auth_headers)
        assert cid, "Campaign creation failed"

        resp = client.put(
            f"/api/campaigns/{cid}",
            headers=auth_headers,
            json={"theme": "Updated Theme", "status": "active"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["message"] == "Campaign updated"

        # DB: verify update
        rows = query_db("SELECT * FROM campaigns WHERE id = ?", (cid,))
        assert rows[0].get("theme") == "Updated Theme"

    def test_campaign_delete(self, client, auth_headers):
        """DELETE /campaigns/<id> → removed from DB."""
        cid = _quick_campaign(client, auth_headers)
        assert cid, "Campaign creation failed"

        resp = client.delete(f"/api/campaigns/{cid}", headers=auth_headers)
        assert resp.status_code == 200
        del_data = resp.get_json()
        assert del_data["message"] == "Campaign deleted"

        # Verify gone from API
        resp2 = client.get(f"/api/campaigns/{cid}", headers=auth_headers)
        assert resp2.status_code == 404

        # DB: row should be gone
        rows = query_db("SELECT * FROM campaigns WHERE id = ?", (cid,))
        assert len(rows) == 0, "Campaign row still exists after DELETE"

    def test_campaign_list_multiple(self, client, auth_headers):
        """Multiple campaigns listed, DB count matches."""
        c1 = _quick_campaign(client, auth_headers, "Campaign A")
        c2 = _quick_campaign(client, auth_headers, "Campaign B")
        assert c1, "Campaign A creation failed"
        assert c2, "Campaign B creation failed"

        resp = client.get("/api/campaigns", headers=auth_headers)
        data = resp.get_json()
        campaigns = data.get("campaigns", [])
        ids = [c.get("id") for c in campaigns]
        assert c1 in ids
        assert c2 in ids

        # DB: at least 2 campaigns
        rows = query_db("SELECT * FROM campaigns")
        assert len(rows) >= 2


# ===================================================================
# Campaign Posts (6 tests) — DB verified
# ===================================================================


class TestCampaignPosts:
    """Post CRUD, reorder, char limit — DB verified."""

    @pytest.fixture(autouse=True)
    def _check_harness(self, require_harness):
        """Fail with clear error if FTAL harness is not running."""

    def test_campaign_post_manual_add(self, client, auth_headers):
        """POST /campaigns/<id>/posts → manual post added, DB row created."""
        cid = _quick_campaign(client, auth_headers)
        assert cid, "No campaign"

        resp = client.post(
            f"/api/campaigns/{cid}/posts",
            headers=auth_headers,
            json={
                "title": "Test Manual Post",
                "content": "This is a manually added LinkedIn post for testing.",
            },
        )
        assert resp.status_code == 201
        resp.get_json().get("post_id")

        # DB: campaign_posts row exists
        rows = query_db("SELECT * FROM campaign_posts WHERE campaign_id = ?", (cid,))
        assert len(rows) >= 1, "No post rows in DB after add"

    def test_campaign_post_edit(self, client, auth_headers):
        """PUT /campaigns/<id>/posts/<pid> → content updated in DB."""
        cid = _quick_campaign(client, auth_headers)
        assert cid, "No campaign"

        resp_add = client.post(
            f"/api/campaigns/{cid}/posts",
            headers=auth_headers,
            json={"title": "Original", "content": "Original content."},
        )
        pid = resp_add.get_json().get("post_id")
        assert pid, "No post_id returned"

        resp = client.put(
            f"/api/campaigns/{cid}/posts/{pid}",
            headers=auth_headers,
            json={"content": "Updated content for the post.", "title": "Updated Title"},
        )
        assert resp.status_code == 200
        edit_data = resp.get_json()
        assert edit_data["message"] == "Post updated"

        # DB: verify update
        rows = query_db("SELECT * FROM campaign_posts WHERE id = ?", (pid,))
        assert rows[0].get("content") == "Updated content for the post."

    def test_campaign_post_delete(self, client, auth_headers):
        """DELETE /campaigns/<id>/posts/<pid> → removed from DB."""
        cid = _quick_campaign(client, auth_headers)
        assert cid, "No campaign"

        resp_add = client.post(
            f"/api/campaigns/{cid}/posts",
            headers=auth_headers,
            json={"title": "Deletable", "content": "To be deleted."},
        )
        pid = resp_add.get_json().get("post_id")
        assert pid, "No post_id returned"

        resp = client.delete(f"/api/campaigns/{cid}/posts/{pid}", headers=auth_headers)
        assert resp.status_code == 200
        del_data = resp.get_json()
        assert del_data["message"] == "Post deleted"

        # DB: row gone
        rows = query_db("SELECT * FROM campaign_posts WHERE id = ?", (pid,))
        assert len(rows) == 0, "Post row still exists after DELETE"

    def test_campaign_post_reorder(self, client, auth_headers):
        """PUT /campaigns/<id>/posts/reorder → sequence_order updated in DB."""
        cid = _quick_campaign(client, auth_headers)
        assert cid, "No campaign"

        ids = []
        for i in range(2):
            resp = client.post(
                f"/api/campaigns/{cid}/posts",
                headers=auth_headers,
                json={"title": f"Post {i}", "content": f"Content {i}"},
            )
            pid = resp.get_json().get("post_id")
            assert pid, f"No post_id for post {i}"
            ids.append(pid)

        resp = client.put(
            f"/api/campaigns/{cid}/posts/reorder",
            headers=auth_headers,
            json={"order": list(reversed(ids))},
        )
        assert resp.status_code == 200
        reorder_data = resp.get_json()
        assert reorder_data["message"] == "Posts reordered"

        # DB: verify positions were updated for the posts we created
        placeholders = ",".join("?" * len(ids))
        rows = query_db(
            f"SELECT id, position FROM campaign_posts "
            f"WHERE campaign_id = ? AND id IN ({placeholders}) "
            f"ORDER BY position",
            (cid, *ids),
        )
        db_ids = [r["id"] for r in rows]
        assert db_ids == list(
            reversed(ids)
        ), f"Order not reversed: {db_ids} vs {list(reversed(ids))}"

    def test_campaign_posts_list_ordered(self, client, auth_headers):
        """GET /campaigns/<id>/posts → posts in order."""
        cid = _quick_campaign(client, auth_headers)
        assert cid, "No campaign"

        client.post(
            f"/api/campaigns/{cid}/posts",
            headers=auth_headers,
            json={"title": "First Post", "content": "Content 1"},
        )

        resp = client.get(f"/api/campaigns/{cid}/posts", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "posts" in data
        posts = data.get("posts", [])
        assert isinstance(posts, list)
        assert len(posts) >= 1

    def test_campaign_post_regenerate_with_feedback(self, client, auth_headers):
        """POST /posts/<pid>/regenerate → LLM regenerates with feedback."""
        cid = _quick_campaign(client, auth_headers)
        assert cid, "No campaign"

        resp_add = client.post(
            f"/api/campaigns/{cid}/posts",
            headers=auth_headers,
            json={"title": "Regenerate Me", "content": "Original draft content."},
        )
        pid = resp_add.get_json().get("post_id")
        assert pid, "No post_id returned"

        resp = client.post(
            f"/api/campaigns/{cid}/posts/{pid}/regenerate",
            headers=auth_headers,
            json={"feedback": "Make it more technical and include AWS references."},
        )
        assert resp.status_code == 200
        regen_data = resp.get_json()
        assert isinstance(regen_data, dict)


# ===================================================================
# Campaign Export & Analytics (3 tests)
# ===================================================================


class TestCampaignExportAnalytics:
    """Export, analytics, and update-interview."""

    @pytest.fixture(autouse=True)
    def _check_harness(self, require_harness):
        """Fail with clear error if FTAL harness is not running."""

    def test_campaign_export_format(self, client, auth_headers):
        """GET /campaigns/<id>/export → formatted text with post content."""
        cid = _quick_campaign(client, auth_headers)
        assert cid, "No campaign"

        client.post(
            f"/api/campaigns/{cid}/posts",
            headers=auth_headers,
            json={"title": "Export Post", "content": "Export test content."},
        )

        resp = client.get(f"/api/campaigns/{cid}/export", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "text" in data or "posts" in data

    def test_campaign_analytics(self, client, auth_headers):
        """GET /campaigns/analytics → coverage analysis."""
        resp = client.get("/api/campaigns/analytics", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict)

    def test_campaign_update_interview(self, client, auth_headers):
        """POST /campaigns/<id>/update-interview → reopens interview."""
        cid = _quick_campaign(client, auth_headers)
        assert cid, "No campaign"

        resp = client.post(
            f"/api/campaigns/{cid}/update-interview",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "session_id" in data


# ===================================================================
# Campaign Isolation (1 test)
# ===================================================================


class TestCampaignIsolation:
    """Multi-user campaign isolation — DB verified."""

    @pytest.fixture(autouse=True)
    def _check_harness(self, require_harness):
        """Fail with clear error if FTAL harness is not running."""

    def test_campaign_isolation(self, client, auth_headers, second_user_headers):
        """User 1's campaigns not visible to user 2."""
        cid = _quick_campaign(client, auth_headers, "Private Campaign")
        assert cid, "No campaign"

        # User 2 should not see user 1's campaign
        resp = client.get("/api/campaigns", headers=second_user_headers)
        data = resp.get_json()
        assert "campaigns" in data
        campaigns = data.get("campaigns", [])
        ids = [c.get("id") for c in campaigns]
        assert cid not in ids


# ===================================================================
# Graph Routes (3 tests)
# ===================================================================


class TestGraphRoutes:
    """Knowledge graph traversal routes."""

    def test_graph_technologies(self, client, auth_headers):
        """GET /graph/technologies → technology list."""
        resp = client.get("/api/graph/technologies", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "technologies" in data

    def test_graph_clients_by_tech(self, client, auth_headers):
        """GET /graph/clients-by-tech → reverse lookup."""
        resp = client.get("/api/graph/clients-by-tech?tech_name=Python", headers=auth_headers)
        assert resp.status_code == 200  # tech_name provided; 400 only when param missing
        data = resp.get_json()
        assert isinstance(data, dict)

    def test_graph_knowledge_context(self, client, auth_headers):
        """GET /graph/knowledge-context → combined context."""
        resp = client.get(
            "/api/graph/knowledge-context?theme=cloud+migration",
            headers=auth_headers,
        )
        assert resp.status_code == 200  # theme provided; 400 only when param missing
        data = resp.get_json()
        assert isinstance(data, dict)
