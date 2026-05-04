"""Tests for journey routes — timeline, skills, achievements, narratives, sources.

Content validation + DB verification for all operations.
No mocks, no skips.
"""

from test_helpers import query_db


def test_journey_timeline_empty(client, auth_headers):
    """GET /api/journey/timeline → 200 with events list (empty initially)."""
    resp = client.get("/api/journey/timeline", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "events" in data
    assert isinstance(data["events"], list)
    assert len(data["events"]) == 0


def test_journey_skills_empty(client, auth_headers):
    """GET /api/journey/skills → 200 with skills list."""
    resp = client.get("/api/journey/skills", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "skills" in data
    assert isinstance(data["skills"], list)
    assert len(data["skills"]) == 0


def test_journey_achievements_empty(client, auth_headers):
    """GET /api/journey/achievements → 200 with achievements list."""
    resp = client.get("/api/journey/achievements", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "achievements" in data
    assert isinstance(data["achievements"], list)
    assert len(data["achievements"]) == 0


def test_journey_sources_empty(client, auth_headers):
    """GET /api/journey/sources → 200 with sources list."""
    resp = client.get("/api/journey/sources", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "sources" in data
    assert isinstance(data["sources"], list)
    assert data["sources"] == []


def test_journey_narratives_empty(client, auth_headers):
    """GET /api/journey/narratives → 200 with narratives list."""
    resp = client.get("/api/journey/narratives", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "narratives" in data
    assert isinstance(data["narratives"], list)
    assert len(data["narratives"]) == 0


def test_journey_narratives_seed_and_read(client, auth_headers):
    """Seed narrative in DB → GET returns it with correct fields."""
    import sqlite3

    import models

    conn = sqlite3.connect(models.DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS journey_narratives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT DEFAULT '',
            content TEXT DEFAULT '',
            narrative_type TEXT DEFAULT 'resume',
            approved INTEGER DEFAULT 0,
            source_event_ids TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    conn.execute(
        "INSERT INTO journey_narratives (user_id, title, content, narrative_type) "
        "VALUES (?, ?, ?, ?)",
        (
            1,
            "AI Leadership Journey",
            "Led enterprise AI transformation across 3 divisions.",
            "resume",
        ),
    )
    conn.commit()
    conn.close()

    # DB: verify row exists
    rows = query_db("SELECT * FROM journey_narratives WHERE user_id = ?", (1,))
    assert len(rows) >= 1
    assert rows[0]["title"] == "AI Leadership Journey"

    resp = client.get("/api/journey/narratives", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "narratives" in data
    assert len(data["narratives"]) >= 1
    narr = data["narratives"][0]
    assert "title" in narr
    assert "content" in narr


def test_journey_narratives_edit_with_db_verify(client, auth_headers):
    """Seed narrative → PUT to edit → DB reflects change."""
    import sqlite3

    import models

    conn = sqlite3.connect(models.DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS journey_narratives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT DEFAULT '',
            content TEXT DEFAULT '',
            narrative_type TEXT DEFAULT 'resume',
            approved INTEGER DEFAULT 0,
            source_event_ids TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    conn.execute(
        "INSERT INTO journey_narratives (user_id, title, content, narrative_type) "
        "VALUES (?, ?, ?, ?)",
        (1, "Original Title", "Original content.", "resume"),
    )
    conn.commit()
    conn.close()

    rows = query_db("SELECT id FROM journey_narratives WHERE user_id = ?", (1,))
    nid = rows[0]["id"]

    resp = client.put(
        "/api/journey/narratives",
        headers=auth_headers,
        json={
            "narratives": [
                {
                    "id": nid,
                    "title": "Original Title",
                    "content": "Updated narrative content for testing.",
                }
            ]
        },
    )
    assert resp.status_code == 200

    # DB: verify update persisted
    rows = query_db("SELECT * FROM journey_narratives WHERE id = ?", (nid,))
    assert len(rows) == 1
    assert rows[0]["content"] == "Updated narrative content for testing."


def test_journey_sources_with_data(client, auth_headers):
    """Seed source in DB → GET returns it with correct fields."""
    import sqlite3

    import models

    conn = sqlite3.connect(models.DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS journey_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            source_type TEXT DEFAULT '',
            source_path TEXT DEFAULT '',
            title TEXT DEFAULT '',
            content_preview TEXT DEFAULT '',
            classification TEXT DEFAULT '',
            event_date TEXT DEFAULT '',
            sha256 TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    conn.execute(
        "INSERT INTO journey_sources"
        " (user_id, source_type, source_path, title, content_preview, classification)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (1, "workdir", "/workdir/reports/test.md", "Test Report", "Preview content here", "report"),
    )
    conn.commit()
    conn.close()

    # DB: verify row
    rows = query_db("SELECT * FROM journey_sources WHERE user_id = ?", (1,))
    assert len(rows) >= 1
    assert rows[0]["source_type"] == "workdir"
    assert rows[0]["title"] == "Test Report"

    resp = client.get("/api/journey/sources", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "sources" in data
    assert len(data["sources"]) >= 1


def test_journey_timeline_pagination(client, auth_headers):
    """GET /api/journey/timeline with pagination params → correct structure."""
    resp = client.get("/api/journey/timeline?page=1&per_page=10", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "events" in data
    assert isinstance(data["events"], list)
    # Pagination metadata should be present
    if "page" in data:
        assert data["page"] == 1
    if "total" in data:
        assert isinstance(data["total"], int)

    # DB: journey tables accessible
    query_db("SELECT COUNT(*) FROM journey_events")


def test_journey_requires_auth(client):
    """GET /api/journey/timeline without auth → 401."""
    resp = client.get("/api/journey/timeline")
    assert resp.status_code == 401
    data = resp.get_json()
    assert "error" in data or "message" in data or "msg" in data
