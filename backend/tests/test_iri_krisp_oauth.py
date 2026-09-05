"""Krisp OAuth 2.0 + PKCE.

The endpoints and constraints here were READ from Krisp's published metadata at
https://mcp.krisp.ai/.well-known/oauth-protected-resource, not guessed. Krisp
advertises code_challenge_methods_supported: ["S256"] and nothing else, so PKCE
is mandatory and there is no fallback that would quietly work if it were wrong.

Several assertions check parameter NAMES against RFC 7636. That is deliberate:
a misnamed parameter carries a correct value, looks entirely plausible, and is
rejected only by the real server as invalid_grant — which reads like a
credential problem rather than a spelling one.
"""
from __future__ import annotations

import base64
import hashlib
import re
from urllib.parse import parse_qs, urlparse

import pytest

from iri.ingestion.krisp.oauth import (
    KRISP_AUTHORIZE_URL,
    KRISP_MCP_URL,
    KRISP_TOKEN_URL,
    build_authorize_url,
    generate_pkce,
    generate_state,
    refresh_request_body,
    token_request_body,
)


def test_endpoints_are_the_published_ones():
    assert KRISP_AUTHORIZE_URL == "https://api.krisp.ai/platform/v1/oauth2/authorize"
    assert KRISP_TOKEN_URL == "https://api.krisp.ai/platform/v1/oauth2/token"
    assert KRISP_MCP_URL == "https://mcp.krisp.ai/mcp"


# --- PKCE, per RFC 7636 -----------------------------------------------------


def test_verifier_length_is_within_spec():
    assert 43 <= len(generate_pkce().verifier) <= 128


def test_verifier_uses_only_unreserved_characters():
    assert re.fullmatch(r"[A-Za-z0-9\-._~]+", generate_pkce().verifier)


def test_challenge_is_unpadded_base64url_sha256_of_the_verifier():
    pkce = generate_pkce()
    expected = base64.urlsafe_b64encode(
        hashlib.sha256(pkce.verifier.encode("ascii")).digest()
    ).decode().rstrip("=")
    assert pkce.challenge == expected
    assert "=" not in pkce.challenge


def test_each_pkce_is_freshly_random():
    """A fixed verifier would make PKCE decorative."""
    assert generate_pkce().verifier != generate_pkce().verifier


def test_state_is_freshly_random():
    """State is the CSRF defence; a constant one defends nothing."""
    first, second = generate_state(), generate_state()
    assert first != second and len(first) >= 16


# --- the authorize URL ------------------------------------------------------


@pytest.fixture
def authorize_query():
    pkce = generate_pkce()
    url = build_authorize_url("cid", "https://app.example/cb", pkce.challenge, "st8")
    assert url.startswith(KRISP_AUTHORIZE_URL)
    return parse_qs(urlparse(url).query), pkce


def test_authorize_url_carries_the_required_parameters(authorize_query):
    query, pkce = authorize_query
    assert query["response_type"] == ["code"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"] == [pkce.challenge]
    assert query["state"] == ["st8"]


def test_the_verifier_never_appears_in_the_authorize_url(authorize_query):
    """The verifier is the secret half; only the challenge may be public."""
    query, pkce = authorize_query
    assert pkce.verifier not in str(query)


# --- least privilege --------------------------------------------------------


def test_requests_only_the_three_read_scopes(authorize_query):
    query, _ = authorize_query
    assert set(query["scope"][0].split()) == {
        "user::meetings::list",
        "user::meetings:metadata::read",
        "user::meetings:transcripts::read",
    }


@pytest.mark.parametrize("forbidden", ["write", "kagent", "import", "subscriptions"])
def test_never_requests_a_write_or_telephony_scope(authorize_query, forbidden):
    """Krisp offers write and telephony scopes. An ingestion integration asking
    for write access is asking to be the cause of a data-loss incident."""
    query, _ = authorize_query
    assert forbidden not in query["scope"][0]


# --- token exchange ---------------------------------------------------------


def test_token_body_uses_the_rfc_parameter_name():
    """RFC 7636 §4.5 names it code_verifier. `verifier` is silently rejected."""
    body = token_request_body("thecode", "theverifier", "cid", "https://app.example/cb")
    assert body["code_verifier"] == "theverifier"
    assert "verifier" not in body


def test_token_body_is_the_authorization_code_grant():
    body = token_request_body("thecode", "v", "cid", "https://app.example/cb")
    assert body["grant_type"] == "authorization_code"
    assert body["code"] == "thecode"
    assert body["redirect_uri"] == "https://app.example/cb"


def test_refresh_body_is_the_refresh_token_grant():
    body = refresh_request_body("rtok", "cid")
    assert body["grant_type"] == "refresh_token"
    assert body["refresh_token"] == "rtok"


def test_oauth_module_makes_no_network_calls():
    """Building and verifying values is separable from exchanging them, which
    is what lets PKCE be tested without a network."""
    from pathlib import Path

    import iri.ingestion.krisp.oauth as module

    source = Path(module.__file__).read_text()
    for marker in ("requests.", "httpx.", "urlopen", "urllib.request"):
        assert marker not in source
