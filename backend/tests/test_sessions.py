"""Tests for session CRUD routes — DB verified.

No mocks, no skips. DB verification after every write.
"""

from test_helpers import query_db


def test_create_session(client, auth_headers):
    """POST /sessions → session created, DB row verified."""
    resp = client.post(
        "/api/sessions",
        headers=auth_headers,
        json={"session_name": "My Session", "job_description_text": "Python developer role"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["session_name"] == "My Session"
    sid = data["id"]

    # DB: job_sessions row exists
    rows = query_db("SELECT * FROM job_sessions WHERE id = ?", (sid,))
    assert len(rows) == 1, f"No job_sessions row for {sid}"
    assert rows[0]["session_name"] == "My Session"
    assert rows[0]["status"] == "draft"


def test_list_sessions(client, auth_headers):
    """GET /sessions → lists user's sessions."""
    client.post("/api/sessions", headers=auth_headers, json={"session_name": "S1"})
    client.post("/api/sessions", headers=auth_headers, json={"session_name": "S2"})
    resp = client.get("/api/sessions", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.get_json()["sessions"]) == 2

    # DB: 2 rows
    rows = query_db("SELECT * FROM job_sessions")
    assert len(rows) >= 2


def test_get_session(client, auth_headers):
    """GET /sessions/<id> → returns session detail."""
    resp = client.post("/api/sessions", headers=auth_headers, json={"session_name": "Get Me"})
    sid = resp.get_json()["id"]
    resp = client.get(f"/api/sessions/{sid}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["session_name"] == "Get Me"


def test_update_session(client, auth_headers):
    """PUT /sessions/<id> → updates fields, DB verified."""
    resp = client.post("/api/sessions", headers=auth_headers, json={"session_name": "Original"})
    sid = resp.get_json()["id"]
    resp = client.put(
        f"/api/sessions/{sid}",
        headers=auth_headers,
        json={"session_name": "Updated"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["session_name"] == "Updated"

    # DB: verify update
    rows = query_db("SELECT * FROM job_sessions WHERE id = ?", (sid,))
    assert rows[0]["session_name"] == "Updated"


def test_delete_session(client, auth_headers):
    """DELETE /sessions/<id> → removed, DB verified."""
    resp = client.post("/api/sessions", headers=auth_headers, json={"session_name": "Delete Me"})
    sid = resp.get_json()["id"]
    resp = client.delete(f"/api/sessions/{sid}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["message"] == "Session deleted"
    resp = client.get(f"/api/sessions/{sid}", headers=auth_headers)
    assert resp.status_code == 404

    # DB: row gone
    rows = query_db("SELECT * FROM job_sessions WHERE id = ?", (sid,))
    assert len(rows) == 0, "Session row still exists after DELETE"


def test_session_not_found(client, auth_headers):
    """GET /sessions/nonexistent → 404."""
    resp = client.get("/api/sessions/nonexistent-uuid", headers=auth_headers)
    assert resp.status_code == 404
    data = resp.get_json()
    assert data["error"] == "Session not found"
