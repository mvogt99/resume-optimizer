"""Tests for campaign routes — CRUD, error handling, auth.

Content validation + DB verification for all operations.
No mocks, no skips. Complements test_campaigns_full.py (lifecycle with LLM).
"""

from test_helpers import query_db


def test_list_campaigns_empty(client, auth_headers):
    """GET /api/campaigns with no campaigns → empty list."""
    resp = client.get("/api/campaigns", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "campaigns" in data
    assert isinstance(data["campaigns"], list)
    assert len(data["campaigns"]) == 0


def test_campaigns_require_auth(client):
    """GET /api/campaigns without auth → 401."""
    resp = client.get("/api/campaigns")
    assert resp.status_code == 401
    data = resp.get_json()
    assert "error" in data or "message" in data or "msg" in data


def test_campaign_not_found(client, auth_headers):
    """GET /api/campaigns/99999 → 404 with error message."""
    resp = client.get("/api/campaigns/99999", headers=auth_headers)
    assert resp.status_code == 404
    data = resp.get_json()
    assert "error" in data
    assert isinstance(data["error"], str)
    assert len(data["error"]) > 0


def test_campaign_delete_not_found(client, auth_headers):
    """DELETE /api/campaigns/99999 → 404 with error message."""
    resp = client.delete("/api/campaigns/99999", headers=auth_headers)
    assert resp.status_code == 404
    data = resp.get_json()
    assert "error" in data


def test_campaign_create_and_get(client, auth_headers):
    """Create campaign via DB → GET returns correct structure."""
    # Insert campaign directly (campaign_interview creates them via 7-stage flow,
    # but for CRUD testing we insert directly)
    import sqlite3

    import models

    conn = models.get_db_connection()
    conn.execute(
        """CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            theme TEXT DEFAULT '',
            audience TEXT DEFAULT '',
            tone TEXT DEFAULT '',
            storyline TEXT DEFAULT '',
            post_count INTEGER DEFAULT 5,
            cadence TEXT DEFAULT 'weekly',
            status TEXT DEFAULT 'draft',
            metadata_json TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    conn.execute(
        "INSERT INTO campaigns (user_id, theme, audience, tone, status) " "VALUES (?, ?, ?, ?, ?)",
        ("1", "AI Leadership", "Tech executives", "professional", "draft"),
    )
    conn.commit()
    conn.close()

    resp = client.get("/api/campaigns", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "campaigns" in data
    assert len(data["campaigns"]) >= 1

    campaign = data["campaigns"][0]
    assert "id" in campaign
    assert campaign["theme"] == "AI Leadership"
    assert campaign["audience"] == "Tech executives"
    assert campaign["tone"] == "professional"
    assert campaign["status"] == "draft"

    # DB: verify row
    rows = query_db("SELECT * FROM campaigns WHERE user_id = ?", ("1",))
    assert len(rows) >= 1
    assert rows[0]["theme"] == "AI Leadership"


def test_campaign_update_success(client, auth_headers):
    """Create campaign → PUT to update → DB reflects change."""
    import sqlite3

    import models

    conn = models.get_db_connection()
    conn.execute(
        """CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            theme TEXT DEFAULT '',
            audience TEXT DEFAULT '',
            tone TEXT DEFAULT '',
            storyline TEXT DEFAULT '',
            post_count INTEGER DEFAULT 5,
            cadence TEXT DEFAULT 'weekly',
            status TEXT DEFAULT 'draft',
            metadata_json TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    conn.execute(
        "INSERT INTO campaigns (user_id, theme, audience, tone, status) " "VALUES (?, ?, ?, ?, ?)",
        ("1", "Original Theme", "Original Audience", "formal", "draft"),
    )
    conn.commit()
    conn.close()

    # Get campaign ID
    rows = query_db("SELECT id FROM campaigns WHERE user_id = ?", ("1",))
    cid = rows[0]["id"]

    resp = client.put(
        f"/api/campaigns/{cid}",
        headers=auth_headers,
        json={"theme": "Updated Theme", "tone": "casual"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["message"] == "Campaign updated"

    # DB: verify update persisted
    rows = query_db("SELECT * FROM campaigns WHERE id = ?", (cid,))
    assert len(rows) == 1
    assert rows[0]["theme"] == "Updated Theme"
    assert rows[0]["tone"] == "casual"


def test_campaign_delete_success(client, auth_headers):
    """Create campaign → DELETE → DB row removed."""
    import sqlite3

    import models

    conn = models.get_db_connection()
    conn.execute(
        """CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            theme TEXT DEFAULT '',
            audience TEXT DEFAULT '',
            tone TEXT DEFAULT '',
            storyline TEXT DEFAULT '',
            post_count INTEGER DEFAULT 5,
            cadence TEXT DEFAULT 'weekly',
            status TEXT DEFAULT 'draft',
            metadata_json TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    conn.execute(
        "INSERT INTO campaigns (user_id, theme, status) VALUES (?, ?, ?)",
        ("1", "Deletable Campaign", "draft"),
    )
    conn.commit()
    conn.close()

    rows = query_db("SELECT id FROM campaigns WHERE user_id = ?", ("1",))
    cid = rows[0]["id"]

    resp = client.delete(f"/api/campaigns/{cid}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "message" in data

    # DB: verify row removed
    rows = query_db("SELECT * FROM campaigns WHERE id = ?", (cid,))
    assert len(rows) == 0


def test_campaign_update_not_found(client, auth_headers):
    """PUT /api/campaigns/99999 → 404."""
    resp = client.put(
        "/api/campaigns/99999",
        headers=auth_headers,
        json={"theme": "Updated Theme"},
    )
    assert resp.status_code == 404
    data = resp.get_json()
    assert data["error"] == "Campaign not found"
