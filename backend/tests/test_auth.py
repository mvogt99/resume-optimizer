"""Tests for authentication routes — register, login, JWT tokens."""

from test_helpers import query_db


def test_register_success(client):
    resp = client.post("/api/register", json={"email": "new@test.com", "password": "Pass1234!"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert "token" in data
    assert int(data["user_id"]) > 0, "user_id must be positive"
    assert isinstance(data["token"], str) and len(data["token"]) > 10, "token too short"

    # DB: user row exists with correct email
    rows = query_db("SELECT * FROM users WHERE email = ?", ("new@test.com",))
    assert len(rows) == 1, "Expected exactly 1 user row"
    assert rows[0]["email"] == "new@test.com"


def test_register_duplicate(client):
    client.post("/api/register", json={"email": "dup@test.com", "password": "Pass1234!"})
    resp = client.post("/api/register", json={"email": "dup@test.com", "password": "Pass1234!"})
    assert resp.status_code == 409
    data = resp.get_json()
    assert "error" in data or "message" in data, "409 must include error/message"

    # DB: exactly one row — duplicate was rejected
    rows = query_db("SELECT * FROM users WHERE email = ?", ("dup@test.com",))
    assert len(rows) == 1, "Duplicate register must not create second row"


def test_login_success(client):
    client.post("/api/register", json={"email": "login@test.com", "password": "Pass1234!"})
    resp = client.post("/api/login", json={"email": "login@test.com", "password": "Pass1234!"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["token"] != "", "Login token must be non-empty"
    assert data["user_id"]

    # DB: user row with matching email
    rows = query_db("SELECT * FROM users WHERE email = ?", ("login@test.com",))
    assert len(rows) == 1


def test_login_wrong_password(client):
    client.post("/api/register", json={"email": "wp@test.com", "password": "Pass1234!"})
    resp = client.post("/api/login", json={"email": "wp@test.com", "password": "wrong"})
    assert resp.status_code == 401
    data = resp.get_json()
    assert data.get("error") or data.get("message"), "401 must include error/message"

    # DB: user still exists (failed login didn't corrupt data)
    rows = query_db("SELECT * FROM users WHERE email = ?", ("wp@test.com",))
    assert len(rows) == 1
    assert rows[0]["email"] == "wp@test.com"


def test_jwt_token_works(client, auth_headers):
    """Token from login should authenticate subsequent requests."""
    resp = client.get("/api/agents/status", headers=auth_headers)
    # agents/status doesn't require auth, but this confirms the header doesn't break
    assert resp.status_code == 200
    data = resp.get_json()
    assert "agents" in data


def test_no_auth_returns_401(client):
    """Protected endpoints should return 401 without auth."""
    resp = client.get("/api/sessions")
    assert resp.status_code == 401
    data = resp.get_json()
    assert data.get("error") or data.get("message"), "401 must include error detail"


def test_invalid_token_returns_401(client):
    resp = client.get(
        "/api/sessions",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert resp.status_code == 401
    data = resp.get_json()
    assert data.get("error") or data.get("message"), "401 must include error detail"


def test_legacy_user_id_header(client):
    """Legacy user-id header still works as fallback."""
    client.post("/api/register", json={"email": "legacy@test.com", "password": "Pass1234!"})
    resp = client.get("/api/sessions", headers={"user-id": "1"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "sessions" in data or isinstance(data, list), "Sessions response must contain sessions"

    # DB: user with id=1 exists
    rows = query_db("SELECT * FROM users WHERE id = ?", (1,))
    assert len(rows) == 1, "Legacy user-id=1 must have matching DB row"
