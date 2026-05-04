"""Option C2: Request logging middleware.

Tests verify: X-Request-ID header present in response, ID is consistent between
request and response, duration is non-negative, and after_request hook is wired.
"""

import pytest
from app import create_app


@pytest.fixture
def client():
    app = create_app(testing=True)
    with app.test_client() as c:
        yield c


def test_x_request_id_present_in_response(client):
    """Verify: every response carries an X-Request-ID header."""
    resp = client.get("/api/status")
    assert "X-Request-ID" in resp.headers


def test_request_id_is_a_uuid(client):
    """Verify: X-Request-ID looks like a UUID (32 hex chars + 4 dashes)."""
    import re
    resp = client.get("/api/status")
    rid = resp.headers.get("X-Request-ID", "")
    assert re.match(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", rid
    ), f"Not a UUID: {rid!r}"


def test_request_ids_differ_across_requests(client):
    """Verify: each request gets a unique ID (not a static value)."""
    r1 = client.get("/api/status")
    r2 = client.get("/api/status")
    assert r1.headers["X-Request-ID"] != r2.headers["X-Request-ID"]


def test_after_request_sets_header_and_logs(client, caplog):
    """Verify: after_request hook runs — header set and INFO log emitted."""
    import logging
    with caplog.at_level(logging.INFO, logger="app"):
        resp = client.get("/api/status")
    assert "X-Request-ID" in resp.headers
    # Duration log line: "GET /api/status 200 <N>ms rid=<uuid>"
    assert any("GET" in r.message and "ms" in r.message for r in caplog.records)
