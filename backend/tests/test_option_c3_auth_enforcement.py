"""Option C3: Auth enforcement on alignment routes.

Tests verify: routes in alignment_routes and alignment_audit_routes return 401
without any auth header, and do not return 401 when a valid user-id header is
supplied. @require_auth is the enforcement mechanism — removing it causes
g.user_id to be unset, which raises AttributeError and returns 500, NOT 401.
"""

import pytest
from app import create_app

VALID_HEADERS = {"user-id": "1"}


@pytest.fixture
def client():
    app = create_app(testing=True)
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# alignment_routes.py tests
# ---------------------------------------------------------------------------


def test_parse_jd_no_auth_returns_401(client):
    """alignment_routes /parse-jd: no auth header → 401."""
    resp = client.post("/api/alignment/parse-jd", json={"job_text": "x" * 60})
    assert resp.status_code == 401


def test_parse_jd_valid_auth_not_401(client):
    """alignment_routes /parse-jd: valid user-id header → not 401."""
    resp = client.post(
        "/api/alignment/parse-jd",
        json={"job_text": "x" * 60},
        headers=VALID_HEADERS,
    )
    assert resp.status_code != 401


def test_normalize_no_auth_returns_401(client):
    """alignment_routes /normalize: no auth header → 401."""
    resp = client.post("/api/alignment/normalize", json={})
    assert resp.status_code == 401


def test_gaps_get_no_auth_returns_401(client):
    """alignment_routes /gaps/<id>: no auth header → 401."""
    resp = client.get("/api/alignment/gaps/1")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# alignment_audit_routes.py tests
# ---------------------------------------------------------------------------


def test_audit_claims_no_auth_returns_401(client):
    """alignment_audit_routes /audit-claims: no auth header → 401."""
    resp = client.post("/api/alignment/audit-claims", json={"resume_id": 1})
    assert resp.status_code == 401


def test_audit_claims_valid_auth_not_401(client):
    """alignment_audit_routes /audit-claims: valid user-id header → not 401."""
    resp = client.post(
        "/api/alignment/audit-claims",
        json={"resume_id": 1},
        headers=VALID_HEADERS,
    )
    assert resp.status_code != 401
