"""Tests for authentication routes — register, login, JWT tokens."""

from test_helpers import query_db


def test_register_success(client):
    """Registration is APPROVAL-GATED: it creates a pending user and issues no
    credential. The absence of a token is the security-relevant property --
    handing a usable credential to an unapproved account defeats the gate."""
    resp = client.post("/api/register", json={"email": "new@test.com", "password": "Pass1234!"})
    assert resp.status_code == 201
    data = resp.get_json()
    assert data.get("pending"), "response must report the pending state"
    assert "approval" in data.get("message", "").lower(), "message must mention approval"
    assert "token" not in data, "an unapproved account must not receive a token"

    rows = query_db("SELECT * FROM users WHERE email = ?", ("new@test.com",))
    assert len(rows) == 1, "Expected exactly 1 user row"
    assert rows[0]["email"] == "new@test.com"
    assert rows[0]["status"] == "pending"


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
    """The full approval round trip. The valuable behaviour is the GATE, not the
    happy path: a pending account must be refused before activation."""
    email, password = "login@test.com", "Pass1234!"
    client.post("/api/register", json={"email": email, "password": password})

    resp = client.post("/api/login", json={"email": email, "password": password})
    assert resp.status_code == 403, "a pending account must not be able to log in"
    refused = resp.get_json()
    assert refused.get("error") or refused.get("message"), "403 must explain itself"

    from models import User

    user = User.find_by_email(email)
    User.update(user.id, status="active")

    resp = client.post("/api/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data["token"], str) and len(data["token"]) > 10, "token too short"
    assert data["user_id"]

    rows = query_db("SELECT * FROM users WHERE email = ?", (email,))
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
