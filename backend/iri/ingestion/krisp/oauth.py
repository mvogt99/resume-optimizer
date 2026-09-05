from __future__ import annotations
import base64
import hashlib
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

# These endpoints were read from https://mcp.krisp.ai/.well-known/oauth-protected-resource and the authorization server metadata.
KRISP_AUTHORIZE_URL = "https://api.krisp.ai/platform/v1/oauth2/authorize"
KRISP_TOKEN_URL = "https://api.krisp.ai/platform/v1/oauth2/token"
KRISP_MCP_URL = "https://mcp.krisp.ai/mcp"

# Deliberately the minimum: the server also offers write and telephony scopes that IRI must never request.
SCOPES = ("user::meetings::list", "user::meetings:metadata::read", "user::meetings:transcripts::read")

# Krisp advertises `code_challenge_methods_supported: ["S256"]` and nothing else, so plain PKCE is not an option.
@dataclass(frozen=True)
class PkceChallenge:
    """
    The VERIFIER is a secret: it must be stored via ISecretStore between the authorize redirect and the token exchange, and never
    logged or placed in a URL. The challenge is the public half.
    """
    verifier: str
    challenge: str

def generate_pkce() -> PkceChallenge:
    verifier = secrets.token_urlsafe(96)  # 43-128 characters from the unreserved set
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('ascii')).digest()).decode('ascii').rstrip('=')
    return PkceChallenge(verifier, challenge)

def build_authorize_url(client_id: str, redirect_uri: str, challenge: str, state: str, scopes: tuple[str, ...] = SCOPES) -> str:
    params = {
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': ' '.join(scopes),
        'state': state,
        'code_challenge': challenge,
        'code_challenge_method': 'S256'
    }
    return f"{KRISP_AUTHORIZE_URL}?{urlencode(params)}"

def generate_state() -> str:
    """
    A cryptographically random opaque value. It is the CSRF defence for the redirect, and a caller that does not compare
    the returned state against the one it sent has no protection at all.
    """
    return secrets.token_urlsafe(32)

def token_request_body(code: str, verifier: str, client_id: str, redirect_uri: str) -> dict[str, str]:
    """
    Constructs the request body for exchanging an authorization code for an access token using PKCE.
    
    :param code: The authorization code received from the authorization server.
    :param verifier: The PKCE verifier that matches the challenge sent during the authorization request.
    :param client_id: The client ID of the application.
    :param redirect_uri: The redirect URI used in the authorization request. It must be byte-identical to the one used in the authorize request.
    :return: A dictionary containing the request body for the token exchange. This dictionary contains a SECRET and must never be logged.
    """
    return {
        'grant_type': 'authorization_code',
        'code': code,
        'code_verifier': verifier,
        'client_id': client_id,
        'redirect_uri': redirect_uri
    }

def refresh_request_body(refresh_token: str, client_id: str) -> dict[str, str]:
    return {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': client_id
    }
