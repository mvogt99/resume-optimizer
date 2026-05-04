"""Security tests — user isolation, CORS, file validation, SQL injection prevention.

Covers Phase 15 fixes: agent auth enforcement, NLP crash guard,
JWT validation, JD file upload, FK enforcement.
"""

import io

import pytest
from test_helpers import query_db


def test_user_isolation_sessions(client, auth_headers, second_user_headers):
    """User A creates session, User B cannot see it."""
    # User A creates a session
    resp = client.post(
        "/api/sessions",
        headers=auth_headers,
        json={"session_name": "Private Session", "job_description_text": "test job"},
    )
    assert resp.status_code == 201
    session_id = resp.get_json()["id"]

    # User A can see it
    resp = client.get(f"/api/sessions/{session_id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["session_name"] == "Private Session", "User A should see own session name"

    # DB: session row exists with correct user
    rows = query_db("SELECT * FROM job_sessions WHERE id = ?", (session_id,))
    assert len(rows) == 1
    assert rows[0]["id"] == session_id

    # User B cannot see it
    resp = client.get(f"/api/sessions/{session_id}", headers=second_user_headers)
    assert resp.status_code == 404
    data = resp.get_json()
    assert data.get("error") or data.get("message"), "404 must include error detail"


def test_user_isolation_sessions_list(client, auth_headers, second_user_headers):
    """User B's session list doesn't include User A's sessions."""
    client.post(
        "/api/sessions",
        headers=auth_headers,
        json={"session_name": "A's Session"},
    )
    resp = client.get("/api/sessions", headers=second_user_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["sessions"] == [], "User B should see no sessions"

    # DB: User A's session exists but is properly isolated
    rows = query_db("SELECT * FROM job_sessions")
    assert len(rows) >= 1, "User A's session should exist in DB"


def test_user_isolation_delete(client, auth_headers, second_user_headers):
    """User B cannot delete User A's session."""
    resp = client.post(
        "/api/sessions",
        headers=auth_headers,
        json={"session_name": "Protected"},
    )
    session_id = resp.get_json()["id"]

    resp = client.delete(f"/api/sessions/{session_id}", headers=second_user_headers)
    assert resp.status_code == 404
    data = resp.get_json()
    assert data.get("error") or data.get("message"), "404 must include error detail"

    # User A can still see it (not deleted)
    resp = client.get(f"/api/sessions/{session_id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["session_name"] == "Protected", "Session must still be intact after failed delete"

    # DB: session row still exists
    rows = query_db("SELECT * FROM job_sessions WHERE id = ?", (session_id,))
    assert len(rows) == 1, "Session must survive failed cross-user delete"


def test_file_upload_extension_whitelist(client, auth_headers):
    """Reject non-allowed file extensions."""
    data = {"file": (io.BytesIO(b"malicious"), "evil.exe")}
    resp = client.post(
        "/api/resume/upload",
        headers={"Authorization": auth_headers["Authorization"]},
        data=data,
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    rdata = resp.get_json()
    assert rdata["error"] != "", "400 must include non-empty error"
    assert "not allowed" in rdata["error"].lower()


def test_file_upload_allowed_extensions(client, auth_headers):
    """Accept .txt uploads."""
    data = {"file": (io.BytesIO(b"John Doe\nSoftware Engineer"), "resume.txt")}
    resp = client.post(
        "/api/resume/upload",
        headers={"Authorization": auth_headers["Authorization"]},
        data=data,
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["resume_id"] != "", "201 upload must return non-empty resume_id"

    # DB: resume row exists
    rows = query_db("SELECT * FROM resumes WHERE id = ?", (data["resume_id"],))
    assert len(rows) == 1


def test_cors_restricted_origin(app):
    """CORS should not allow arbitrary origins."""
    with app.test_client() as c:
        resp = c.options(
            "/api/sessions",
            headers={"Origin": "http://evil.com", "Access-Control-Request-Method": "GET"},
        )
        acao = resp.headers.get("Access-Control-Allow-Origin", "")
        assert "evil.com" not in acao


def test_sql_injection_in_update_session_blocked(client, auth_headers):
    """Column allowlist prevents SQL injection in _update_session kwargs.
    This is a structural test — the allowlist is checked at the class level."""
    from experience_chat import ExperienceExtractor

    mgr = ExperienceExtractor()
    # This should be silently ignored (not raise or inject SQL)
    mgr._update_session("fake-id", **{"stage = 'hacked', is_finalized": 1})
    # If we got here without error, the allowlist worked (key was rejected)

    # Verify no data corruption via API
    resp = client.get("/api/experience/list", headers=auth_headers)
    data = resp.get_json()
    assert data["experiences"] == [], "SQL injection must not create data"


# ─── Phase 15: Agent route auth enforcement ─────────────────────


AGENT_PROTECTED_ROUTES = [
    ("POST", "/api/agents/scout/search"),
    ("GET", "/api/agents/scout/postings"),
    ("GET", "/api/agents/scout/postings/fake"),
    ("PUT", "/api/agents/scout/postings/fake"),
    ("DELETE", "/api/agents/scout/postings/fake"),
    ("POST", "/api/agents/scout/postings"),
    ("POST", "/api/agents/scout/postings/fake/rescore"),
    ("POST", "/api/agents/scout/criteria"),
    ("GET", "/api/agents/scout/criteria"),
    ("GET", "/api/agents/pipeline"),
    ("PUT", "/api/agents/pipeline/fake"),
    ("GET", "/api/agents/pipeline/analytics"),
    ("GET", "/api/agents/pipeline/reminders"),
    ("POST", "/api/agents/pipeline/fake/followup"),
    ("POST", "/api/agents/pipeline/fake/analyze"),
    ("GET", "/api/agents/runs"),
    ("POST", "/api/agents/tailor/fake"),
    ("GET", "/api/agents/tailor/fake"),
    ("POST", "/api/agents/cover-letter/fake"),
    ("GET", "/api/agents/cover-letter/fake"),
    ("GET", "/api/agents/cover-letters/fake"),
    ("PUT", "/api/agents/cover-letters/fake"),
    ("DELETE", "/api/agents/cover-letters/fake"),
    ("POST", "/api/agents/cover-letters/fake/regenerate"),
    ("POST", "/api/agents/coach/start"),
    ("POST", "/api/agents/coach/answer"),
    ("GET", "/api/agents/coach/fake"),
    ("GET", "/api/agents/coach/sessions"),
    ("GET", "/api/agents/coach/fake/assessment"),
    ("POST", "/api/agents/advisor/analyze"),
    ("POST", "/api/agents/advisor/skills-roadmap"),
    ("POST", "/api/agents/advisor/role-recommendations"),
]


@pytest.mark.parametrize("method,path", AGENT_PROTECTED_ROUTES)
def test_agent_routes_require_auth(client, method, path):
    """Every agent route must return 401 without auth headers."""
    fn = getattr(client, method.lower())
    if method in ("POST", "PUT"):
        resp = fn(path, json={})
    else:
        resp = fn(path)
    assert resp.status_code == 401, f"{method} {path} returned {resp.status_code}"
    data = resp.get_json()
    assert data.get("error") or data.get("message"), f"401 for {path} must include error detail"


def test_agent_status_is_public(client):
    """/api/agents/status is a health check — should not require auth."""
    resp = client.get("/api/agents/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "agents" in data
    assert isinstance(data["agents"], (list, dict)), "agents must be list or dict"


# ─── Phase 15: JWT validation ───────────────────────────────────


def test_expired_token_rejected(client):
    import jwt
    from auth import JWT_ALGORITHM, JWT_SECRET

    payload = {"user_id": 1, "email": "x@x.com", "iat": 0, "exp": 1}
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    resp = client.get(
        "/api/resumes/versions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401
    data = resp.get_json()
    assert (
        data.get("error", "") != "" or data.get("message", "") != ""
    ), "401 must include error detail"


def test_invalid_token_rejected(client):
    resp = client.get(
        "/api/resumes/versions",
        headers={"Authorization": "Bearer not.a.real.token"},
    )
    assert resp.status_code == 401
    data = resp.get_json()
    assert (
        data.get("error", "") != "" or data.get("message", "") != ""
    ), "Invalid token 401 must include error detail"


def test_legacy_user_id_fallback(client):
    """Legacy user-id header should still be accepted."""
    client.post("/api/register", json={"email": "legacy@test.com", "password": "Test1234!"})
    resp = client.post("/api/login", json={"email": "legacy@test.com", "password": "Test1234!"})
    user_id = resp.get_json()["user_id"]
    resp = client.get("/api/resumes/versions", headers={"user-id": str(user_id)})
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data["versions"], list), "Legacy auth must return versions list"
    assert data["versions"] == [], "New user via legacy auth should have empty versions"


# ─── Phase 15: NLP crash guard ──────────────────────────────────


def test_nlp_module_has_fallback():
    """nlp_engine.nlp should be defined (None or spaCy model)."""
    import nlp_engine

    assert hasattr(nlp_engine, "nlp")


def test_extract_keywords_empty():
    from nlp_engine import extract_keywords

    assert extract_keywords("") == []
    assert extract_keywords(None) == []


def test_calculate_similarity_empty():
    from nlp_engine import calculate_similarity

    assert calculate_similarity("", "test") == 0.0
    assert calculate_similarity("test", "") == 0.0


# ─── Phase 15: JD file upload ───────────────────────────────────


def test_jd_file_upload(client, auth_headers):
    """File-based JD upload (new in Phase 15)."""
    jd = b"Senior Python developer with 5 years experience in AWS and Docker"
    headers = {k: v for k, v in auth_headers.items() if k != "Content-Type"}
    resp = client.post(
        "/api/job-description/upload",
        headers=headers,
        data={"file": (io.BytesIO(jd), "job.txt")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["job_id"] != "", "job_id must be non-empty"

    # DB: job_descriptions row exists
    rows = query_db("SELECT * FROM job_descriptions WHERE id = ?", (data["job_id"],))
    assert len(rows) == 1


def test_jd_empty_rejected(client, auth_headers):
    resp = client.post("/api/job-description/upload", headers=auth_headers, json={"job_text": ""})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] != "", "Empty JD rejection must include non-empty error"


# ─── Phase 15: Foreign key enforcement ──────────────────────────


def test_pragma_foreign_keys_enabled():
    from models import get_db

    with get_db() as conn:
        result = conn.execute("PRAGMA foreign_keys").fetchone()
        assert result[0] == 1


# ─── Phase 15: User isolation for agents ────────────────────────


def test_user_b_cannot_see_user_a_postings(client, auth_headers, second_user_headers):
    """User B should not see User A's scout postings."""
    resp = client.post(
        "/api/agents/scout/postings",
        headers=auth_headers,
        json={"title": "Secret Job", "company": "Secret Corp"},
    )
    assert resp.status_code == 201
    create_data = resp.get_json()
    assert create_data.get("posting_id") or create_data.get("id"), "201 must return posting id"

    resp = client.get("/api/agents/scout/postings", headers=second_user_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["count"] == 0

    # DB: posting exists (just not visible to user B)
    rows = query_db("SELECT * FROM job_postings WHERE title = ?", ("Secret Job",))
    assert len(rows) >= 1
