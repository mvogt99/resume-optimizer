from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from iri.ingestion.krisp.oauth import (
    build_authorize_url,
    generate_pkce,
    generate_state,
    token_request_body,
    KRISP_TOKEN_URL
)
from iri.contracts.secret_store import SecretNotFoundError
from iri.ingestion.krisp.token_store import KrispTokens, KrispTokenStore, expiry_from_expires_in

# This module requires the following environment variables to be set:
# - KRISP_CLIENT_ID: The client ID for the Krisp OAuth application.
# - KRISP_REDIRECT_URI: The redirect URI for the Krisp OAuth application.
# The client can be self-registered via Krisp's RFC 7591 endpoint, which returns 200 for an open registration.

iri_krisp = Blueprint('iri_krisp', __name__, url_prefix='/api/iri/krisp')

PENDING_FLOW_PREFIX = "iri_krisp_pending_"
# The redirect from Krisp carries no headers, so the pending record is
# stored under a fixed owner and the user id travels inside it.
PENDING_OWNER = "_iri_pending"

def _secret_store():
    from iri.adapters.local.encrypted_file_secret_store import EncryptedFileSecretStore
    return EncryptedFileSecretStore()

@iri_krisp.route('/connect', methods=['GET'])
def connect():
    user_id = request.headers.get('user-id')
    if not user_id:
        return jsonify({'error': 'User ID is required'}), 401

    client_id = os.getenv('KRISP_CLIENT_ID')
    redirect_uri = os.getenv('KRISP_REDIRECT_URI')

    if not client_id or not redirect_uri:
        return jsonify({'error': 'Configuration error'}), 500

    pkce = generate_pkce()
    state = generate_state()

    # Store the verifier and state server-side, including the user_id
    store = _secret_store()
    store.store_secret(PENDING_OWNER, f"{PENDING_FLOW_PREFIX}{state}", json.dumps({"verifier": pkce.verifier, "user_id": user_id}))

    authorize_url = build_authorize_url(client_id, redirect_uri, pkce.challenge, state)
    return jsonify({'authorize_url': authorize_url})

@iri_krisp.route('/callback', methods=['GET'])
def callback():
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')

    if error:
        return jsonify({'error': error}), 400

    if not code or not state:
        return jsonify({'error': 'Code and state are required'}), 400

    store = _secret_store()

    # CSRF check: Ensure the state is valid and matches the stored state
    try:
        pending_record = store.retrieve_secret(PENDING_OWNER, f"{PENDING_FLOW_PREFIX}{state}")
    except SecretNotFoundError:
        return jsonify({'error': 'Invalid state'}), 400

    pending_data = json.loads(pending_record)
    stored_verifier = pending_data.get('verifier')
    user_id = pending_data.get('user_id')

    client_id = os.getenv('KRISP_CLIENT_ID')
    redirect_uri = os.getenv('KRISP_REDIRECT_URI')

    if not client_id or not redirect_uri:
        return jsonify({'error': 'Configuration error'}), 500

    # Exchange the code for tokens
    import requests
    client_secret = os.getenv("KRISP_CLIENT_SECRET")
    # Krisp issues CONFIDENTIAL clients (token_endpoint_auth_method:
    # client_secret_basic), so the secret goes in the Authorization header via
    # requests' auth=, not the form body. Falls back to a public client if unset.
    auth = (client_id, client_secret) if client_secret else None
    try:
        response = requests.post(
            KRISP_TOKEN_URL,
            data=token_request_body(code, stored_verifier, client_id, redirect_uri),
            auth=auth,
        )
        response.raise_for_status()
        tokens = response.json()
    except requests.exceptions.RequestException:
        # Never echo the provider body: it may contain the authorization code.
        return jsonify({"error": "Failed to exchange code for tokens"}), 502

    # Save the tokens
    expiry = expiry_from_expires_in(tokens['expires_in'], datetime.now(timezone.utc))
    krisp_tokens = KrispTokens(
        access_token=tokens['access_token'],
        refresh_token=tokens.get('refresh_token'),
        expires_at=expiry,
        scopes=tuple(tokens.get('scope', '').split())
    )
    token_store = KrispTokenStore(store, user_id)
    token_store.save(krisp_tokens)

    # Delete the stored state/verifier
    store.delete_secret(PENDING_OWNER, f"{PENDING_FLOW_PREFIX}{state}")

    return jsonify({
        'connected': True,
        'scopes': list(krisp_tokens.scopes),
        'expires_at': krisp_tokens.expires_at.isoformat()
    })

