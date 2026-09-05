"""The Krisp OAuth handshake: /connect and /callback.

Most of these tests are about what must NOT happen. The verifier must never
reach the browser, an unknown state must never lead to a code exchange, and no
response may carry a token. Each is a property that looks fine in manual testing
whether or not it holds.
"""
from __future__ import annotations

import json
import tempfile
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.fernet import Fernet
from flask import Flask


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("FERNET_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("KRISP_CLIENT_ID", "test-client")
    monkeypatch.setenv("KRISP_REDIRECT_URI", "http://localhost:5000/api/iri/krisp/callback")
    monkeypatch.setenv("IRI_SECRET_DIR", tempfile.mkdtemp())
    import iri.routes.krisp_routes as routes

    app = Flask(__name__)
    app.register_blueprint(routes.iri_krisp)
    return app.test_client()


def _start(client):
    response = client.get("/api/iri/krisp/connect", headers={"user-id": "10"})
    assert response.status_code == 200
    url = response.get_json()["authorize_url"]
    return response, parse_qs(urlparse(url).query)["state"][0]


# --- /connect ---------------------------------------------------------------


def test_connect_requires_identity(client):
    assert client.get("/api/iri/krisp/connect").status_code == 401


def test_connect_returns_an_authorize_url_rather_than_redirecting(client):
    """This is an API; returning the URL lets the caller decide."""
    response, _ = _start(client)
    assert response.get_json()["authorize_url"].startswith("https://api.krisp.ai")


def test_authorize_url_uses_s256(client):
    response, _ = _start(client)
    query = parse_qs(urlparse(response.get_json()["authorize_url"]).query)
    assert query["code_challenge_method"] == ["S256"]


def test_the_verifier_never_reaches_the_browser(client):
    """The verifier is the secret half of PKCE. Handing it to the client
    removes the protection entirely."""
    response, _ = _start(client)
    assert "verifier" not in response.get_data(as_text=True)


def test_missing_configuration_is_a_clear_500(client, monkeypatch):
    monkeypatch.delenv("KRISP_CLIENT_ID", raising=False)
    assert client.get("/api/iri/krisp/connect", headers={"user-id": "10"}).status_code == 500


# --- /callback --------------------------------------------------------------


def test_unknown_state_is_refused_without_exchanging(client):
    """The CSRF check. Without it an attacker can inject their own
    authorization code and bind their Krisp account to this user's data."""
    response = client.get(
        "/api/iri/krisp/callback?code=abc&state=NEVER_ISSUED", headers={"user-id": "10"}
    )
    assert response.status_code == 400


def test_provider_error_is_surfaced_not_swallowed(client):
    _, state = _start(client)
    response = client.get(
        f"/api/iri/krisp/callback?error=access_denied&state={state}", headers={"user-id": "10"}
    )
    assert response.status_code == 400
    assert "access_denied" in response.get_data(as_text=True)


def test_callback_works_with_no_headers_at_all(client, monkeypatch):
    """The callback is reached by a REDIRECT FROM KRISP, which carries no custom
    headers. An earlier version read the user from a `user-id` header and
    returned 401 to every real browser — while every test passed, because the
    tests sent the header. Identity now travels in the OAuth state, the only
    value that round-trips through the provider.
    """
    import requests

    monkeypatch.setattr(
        requests,
        "post",
        lambda url, data=None, **kw: _Response(
            200, {"access_token": "a", "expires_in": 3600, "scope": "user::meetings::list"}
        ),
    )
    _, state = _start(client)
    # deliberately NO headers, exactly as a browser redirect arrives
    response = client.get(f"/api/iri/krisp/callback?code=c&state={state}")
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json()["connected"] is True


def test_missing_code_is_rejected(client):
    _, state = _start(client)
    assert client.get(
        f"/api/iri/krisp/callback?state={state}", headers={"user-id": "10"}
    ).status_code == 400


# --- the exchange -----------------------------------------------------------


class _Response:
    """Enough of requests.Response for the route: status, json(), and
    raise_for_status(), which the handler calls."""

    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if not (200 <= self.status_code < 300):
            import requests

            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)


def test_successful_exchange_stores_tokens_and_returns_none_of_them(client, monkeypatch):
    import iri.routes.krisp_routes as routes

    captured = {}

    def fake_post(url, data=None, **kwargs):
        captured["url"], captured["data"] = url, data
        return _Response(
            200,
            {
                "access_token": "AT-SECRET",
                "refresh_token": "RT-SECRET",
                "expires_in": 3600,
                "scope": "user::meetings::list user::meetings:transcripts::read",
            },
        )

    import requests

    monkeypatch.setattr(requests, "post", fake_post)
    _, state = _start(client)
    response = client.get(
        f"/api/iri/krisp/callback?code=THECODE&state={state}", headers={"user-id": "10"}
    )
    assert response.status_code == 200, response.get_data(as_text=True)

    body = response.get_data(as_text=True)
    assert "AT-SECRET" not in body and "RT-SECRET" not in body
    assert response.get_json()["connected"] is True
    assert "user::meetings::list" in response.get_json()["scopes"]

    # RFC 7636: the exchange must send code_verifier, not "verifier"
    assert "code_verifier" in captured["data"]
    assert captured["url"] == routes.KRISP_TOKEN_URL


def test_state_is_single_use(client, monkeypatch):
    """A replayed state must not exchange a second time."""
    import requests

    monkeypatch.setattr(
        requests,
        "post",
        lambda url, data=None, **kw: _Response(
            200, {"access_token": "a", "expires_in": 3600, "scope": "user::meetings::list"}
        ),
    )
    _, state = _start(client)
    first = client.get(f"/api/iri/krisp/callback?code=c&state={state}", headers={"user-id": "10"})
    assert first.status_code == 200
    replay = client.get(f"/api/iri/krisp/callback?code=c&state={state}", headers={"user-id": "10"})
    assert replay.status_code == 400


def test_token_endpoint_failure_does_not_echo_the_provider_body(client, monkeypatch):
    """The provider body may contain the authorization code."""
    import requests

    monkeypatch.setattr(
        requests, "post", lambda url, data=None, **kw: _Response(400, {"detail": "THECODE-ECHOED"})
    )
    _, state = _start(client)
    response = client.get(
        f"/api/iri/krisp/callback?code=THECODE&state={state}", headers={"user-id": "10"}
    )
    assert response.status_code == 502
    assert "THECODE-ECHOED" not in response.get_data(as_text=True)
