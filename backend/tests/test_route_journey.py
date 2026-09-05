"""Route tests for journey_routes.py — timeline, skills, narratives, sources, review.

Pure API tests. Seeds journey_events for read endpoints.
"""

import json
import sqlite3

import pytest
from test_helpers import query_db

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def seeded_journey(app):
    """Seed journey_events, journey_sources, journey_narratives for user 1."""
    import models

    conn = models.get_db_connection()
    # Sources
    for i in range(3):
        conn.execute(
            "INSERT INTO journey_sources (user_id, source_type, source_path) " "VALUES (1, ?, ?)",
            (["workdir", "qdrant", "git"][i], f"/path/to/source_{i}"),
        )
    # Events
    for i in range(8):
        conn.execute(
            "INSERT INTO journey_events "
            "(user_id, event_date, title, category, technologies, source_ids) "
            "VALUES (1, ?, ?, ?, ?, ?)",
            (
                f"2026-01-{10 + i:02d}",
                f"Built component {i}",
                ["coding", "deployment", "analysis", "planning"][i % 4],
                json.dumps(["Python", "Docker"] if i % 2 == 0 else ["React"]),
                json.dumps([f"src_{i}"]),
            ),
        )
    # Narratives
    for ntype in ["resume_entry", "linkedin_headline", "campaign_seed"]:
        conn.execute(
            "INSERT INTO journey_narratives (user_id, narrative_type, title, content) "
            "VALUES (1, ?, ?, ?)",
            (ntype, f"Test {ntype}", f"Content for {ntype}"),
        )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------


class TestJourneyTimeline:
    def test_timeline_empty(self, client, auth_headers):
        resp = client.get("/api/journey/timeline", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "events" in data
        assert isinstance(data["events"], list)
        assert len(data["events"]) == 0

    def test_timeline_with_data(self, client, auth_headers, seeded_journey):
        resp = client.get("/api/journey/timeline", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["events"]) == 8
        # Events should have date/title/category
        event = data["events"][0]
        assert "event_date" in event or "date" in event
        assert "title" in event
        assert "category" in event
        # DB: verify count
        rows = query_db("SELECT COUNT(*) as cnt FROM journey_events WHERE user_id = 1")
        assert rows[0]["cnt"] == 8

    def test_timeline_pagination(self, client, auth_headers, seeded_journey):
        resp = client.get("/api/journey/timeline?per_page=3&page=1", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["events"]) <= 3

    def test_timeline_category_filter(self, client, auth_headers, seeded_journey):
        resp = client.get("/api/journey/timeline?category=coding", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        for event in data["events"]:
            assert event["category"] == "coding"


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------


class TestJourneySkills:
    def test_skills_empty(self, client, auth_headers):
        resp = client.get("/api/journey/skills", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "skills" in data
        assert isinstance(data["skills"], list)

    def test_skills_with_data(self, client, auth_headers, seeded_journey):
        resp = client.get("/api/journey/skills", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["skills"]) >= 1
        # Skills should have name and count/frequency
        skill = data["skills"][0]
        assert isinstance(skill, (dict, list, str))


# ---------------------------------------------------------------------------
# Achievements
# ---------------------------------------------------------------------------


class TestJourneyAchievements:
    def test_achievements_empty(self, client, auth_headers):
        resp = client.get("/api/journey/achievements", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "achievements" in data
        assert isinstance(data["achievements"], list)


# ---------------------------------------------------------------------------
# Narratives
# ---------------------------------------------------------------------------


class TestJourneyNarratives:
    def test_narratives_empty(self, client, auth_headers):
        resp = client.get("/api/journey/narratives", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "narratives" in data
        assert isinstance(data["narratives"], list)

    def test_narratives_with_data(self, client, auth_headers, seeded_journey):
        resp = client.get("/api/journey/narratives", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["narratives"]) == 3
        types = [n["narrative_type"] for n in data["narratives"]]
        assert "resume_entry" in types
        assert "linkedin_headline" in types
        # DB: verify count
        rows = query_db("SELECT COUNT(*) as cnt FROM journey_narratives WHERE user_id = 1")
        assert rows[0]["cnt"] == 3

    def test_update_narratives(self, client, auth_headers, seeded_journey):
        # Get existing narratives
        resp = client.get("/api/journey/narratives", headers=auth_headers)
        narratives = resp.get_json()["narratives"]
        narr = narratives[0]
        narr_id = narr.get("id")

        resp = client.put(
            "/api/journey/narratives",
            headers=auth_headers,
            json={"narratives": [{"id": narr_id, "content": "Updated content"}]},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "message" in data


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------


class TestJourneySources:
    def test_sources_empty(self, client, auth_headers):
        resp = client.get("/api/journey/sources", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "sources" in data
        assert isinstance(data["sources"], list)

    def test_sources_with_data(self, client, auth_headers, seeded_journey):
        resp = client.get("/api/journey/sources", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["sources"]) == 3
        types = [s["source_type"] for s in data["sources"]]
        assert "workdir" in types
        assert "qdrant" in types
        assert "git" in types
        # DB: verify count
        rows = query_db("SELECT COUNT(*) as cnt FROM journey_sources WHERE user_id = 1")
        assert rows[0]["cnt"] == 3

    def test_sources_filter_by_type(self, client, auth_headers, seeded_journey):
        resp = client.get("/api/journey/sources?type=workdir", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        for src in data["sources"]:
            assert src["source_type"] == "workdir"


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------


class TestJourneyReset:
    def test_reset_clears_data(self, client, auth_headers, seeded_journey):
        resp = client.delete("/api/journey/reset", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "message" in data
        # DB: verify data cleared
        events = query_db("SELECT COUNT(*) as cnt FROM journey_events WHERE user_id = 1")
        assert events[0]["cnt"] == 0
        sources = query_db("SELECT COUNT(*) as cnt FROM journey_sources WHERE user_id = 1")
        assert sources[0]["cnt"] == 0


# ---------------------------------------------------------------------------
# Approve
# ---------------------------------------------------------------------------


class TestJourneyApprove:
    def test_approve_empty_narratives(self, client, auth_headers):
        """Approve with no narratives — returns 200 with message."""
        resp = client.post("/api/journey/approve", headers=auth_headers, json={})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "message" in data
        assert isinstance(data["message"], str)


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------


class TestJourneyReview:
    def test_review_start(self, client, auth_headers):
        resp = client.post(
            "/api/journey/review/start",
            headers=auth_headers,
            json={"review_type": "timeline"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "session_id" in data
        assert isinstance(data["session_id"], str)

    def test_review_message_missing_fields(self, client, auth_headers):
        resp = client.post(
            "/api/journey/review/message",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_review_apply_missing_session(self, client, auth_headers):
        resp = client.post(
            "/api/journey/review/apply",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
