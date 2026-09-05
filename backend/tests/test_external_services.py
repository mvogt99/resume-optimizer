"""E2E tests for external service integrations — ArangoDB, Google Drive, Qdrant.

These tests verify live connectivity and basic operations against real services.
No LLM required. No mocks, no skips. If a service is down, tests FAIL.
"""

import pytest

# E2E against live ArangoDB / Google Drive / Qdrant (see docstring above).
# CI runs none of those, so these are deselected there via
# -m "not integration"; they still run locally against a real stack.
pytestmark = pytest.mark.integration


import os

import requests

# ---------------------------------------------------------------------------
# Service connectivity — fail (not skip) if not running
# ---------------------------------------------------------------------------

ARANGO_URL = "http://localhost:8529"
ARANGO_USER = "root"
ARANGO_PASS = "hybrid_ai_root"
ARANGO_DB = "hybrid_ai"

QDRANT_URL = "http://localhost:6333"

GDRIVE_TOKEN_PATH = os.path.expanduser("~/.config/google-docs-mcp/token.json")


# ===================================================================
# ArangoDB Tests
# ===================================================================


class TestArangoDB:
    """Verify ArangoDB connectivity, CRUD, and graph traversal."""

    def test_arango_connection(self):
        """ArangoDB reachable and authenticated."""
        resp = requests.get(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/version",
            auth=(ARANGO_USER, ARANGO_PASS),
            timeout=5,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "version" in data

    def test_arango_upsert_and_query(self):
        """Write a test document and read it back from an ro_ collection."""
        # Ensure collection exists
        requests.post(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/collection",
            auth=(ARANGO_USER, ARANGO_PASS),
            json={"name": "ro_test_e2e", "type": 2},
            timeout=5,
        )

        # Upsert via AQL (handles both insert and update)
        resp = requests.post(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
            auth=(ARANGO_USER, ARANGO_PASS),
            json={
                "query": "UPSERT {_key: @key} INSERT {_key: @key, type: @type, content: @content} "
                "UPDATE {type: @type, content: @content} IN ro_test_e2e RETURN NEW",
                "bindVars": {
                    "key": "test_e2e_doc_001",
                    "type": "test",
                    "content": "e2e test data",
                },
            },
            timeout=5,
        )
        assert resp.status_code == 201, f"Upsert failed: {resp.text}"

        # Read back
        resp2 = requests.get(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/document/ro_test_e2e/test_e2e_doc_001",
            auth=(ARANGO_USER, ARANGO_PASS),
            timeout=5,
        )
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["content"] == "e2e test data"

    def test_arango_aql_query(self):
        """Execute an AQL query via the cursor API."""
        resp = requests.post(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
            auth=(ARANGO_USER, ARANGO_PASS),
            json={"query": "RETURN 1 + 1"},
            timeout=5,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["result"] == [2]


# ===================================================================
# Qdrant Tests
# ===================================================================


class TestQdrant:
    """Verify Qdrant connectivity and search operations."""

    def test_qdrant_health(self):
        """Qdrant health endpoint responds OK."""
        resp = requests.get(f"{QDRANT_URL}/healthz", timeout=5)
        assert resp.status_code == 200

    def test_qdrant_collections_list(self):
        """Qdrant lists collections without error."""
        resp = requests.get(f"{QDRANT_URL}/collections", timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert "result" in data
        assert "collections" in data["result"]

    def test_qdrant_search_with_vector(self):
        """Search an existing collection with a dummy vector."""
        # List collections to find one with known dimensionality
        resp = requests.get(f"{QDRANT_URL}/collections", timeout=5)
        collections = resp.json()["result"]["collections"]
        assert len(collections) >= 1, "No Qdrant collections available to search"

        coll_name = collections[0]["name"]
        # Get collection info for vector dimension
        info = requests.get(f"{QDRANT_URL}/collections/{coll_name}", timeout=5)
        assert info.status_code == 200
        config = info.json()["result"]["config"]
        params = config.get("params", {})
        vectors_config = params.get("vectors", {})

        # Determine vector size
        if isinstance(vectors_config, dict) and "size" in vectors_config:
            dim = vectors_config["size"]
        elif isinstance(vectors_config, dict):
            # Named vectors — pick first
            first_key = next(iter(vectors_config), None)
            if first_key and isinstance(vectors_config[first_key], dict):
                dim = vectors_config[first_key].get("size", 384)
            else:
                dim = 384
        else:
            dim = 384

        # Search with zero vector (valid but low-quality results — we just test the API)
        search_resp = requests.post(
            f"{QDRANT_URL}/collections/{coll_name}/points/search",
            json={"vector": [0.0] * dim, "limit": 3},
            timeout=10,
        )
        assert search_resp.status_code == 200
        assert "result" in search_resp.json()


# ===================================================================
# Google Drive Tests
# ===================================================================


class TestGoogleDrive:
    """Verify Google Drive integration via the app's GDrive service."""

    def test_gdrive_list_folder(self, client, auth_headers):
        """Google Drive folder listing returns files via app endpoint."""
        assert os.path.exists(
            GDRIVE_TOKEN_PATH
        ), f"Google Drive OAuth token not found at {GDRIVE_TOKEN_PATH}"
        resp = client.get("/api/projects/folders", headers=auth_headers)
        assert resp.status_code == 200, f"GDrive folder listing failed: {resp.status_code}"

    def test_gdrive_resumes_list(self, client, auth_headers):
        """GDrive resume list endpoint responds."""
        assert os.path.exists(
            GDRIVE_TOKEN_PATH
        ), f"Google Drive OAuth token not found at {GDRIVE_TOKEN_PATH}"
        resp = client.get("/api/resumes/gdrive", headers=auth_headers)
        assert resp.status_code == 200, f"GDrive resume listing failed: {resp.status_code}"
