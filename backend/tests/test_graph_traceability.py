"""P2-B: Graph Traceability tests — TDD first.

Tests:
- ro_resume_versions / ro_version_sourced_from collection constants exist
- write_resume_version_to_graph() upserts vertex + edges
- GET /api/graph/evidence-coverage returns correct structure
- Untapped evidence injected into tailor prompt
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, ".")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def app_ctx():
    import app as flask_app

    with flask_app.app.app_context():
        yield flask_app.app


@pytest.fixture()
def client(app_ctx):
    return app_ctx.test_client()


# ---------------------------------------------------------------------------
# P2-B.1: Collection constants exist
# ---------------------------------------------------------------------------


class TestCollectionConstants:
    def test_resume_versions_vertex_in_all_vertex(self):
        from arango_client import ALL_VERTEX

        assert "ro_resume_versions" in ALL_VERTEX, "ro_resume_versions must be in ALL_VERTEX"

    def test_version_sourced_from_edge_in_all_edge(self):
        from arango_client import ALL_EDGE

        assert "ro_version_sourced_from" in ALL_EDGE, "ro_version_sourced_from must be in ALL_EDGE"

    def test_p2b_vertex_collections_defined(self):
        from arango_client import P2B_VERTEX_COLLECTIONS

        assert "ro_resume_versions" in P2B_VERTEX_COLLECTIONS

    def test_p2b_edge_collections_defined(self):
        from arango_client import P2B_EDGE_COLLECTIONS

        assert "ro_version_sourced_from" in P2B_EDGE_COLLECTIONS


# ---------------------------------------------------------------------------
# P2-B.2: write_resume_version_to_graph() creates vertex + edges
# ---------------------------------------------------------------------------


class TestWriteResumeVersion:
    def test_returns_version_id_string(self):
        from graph_traceability import write_resume_version_to_graph

        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.upsert_vertex.return_value = "ro_resume_versions/abc123"
        mock_client.upsert_edge.return_value = "ro_version_sourced_from/edge1"

        with patch("arango_client.get_arango_client", return_value=mock_client):
            result = write_resume_version_to_graph(
                user_id=3,
                version_id=42,
                source="agent_tailor",
                posting={"title": "Staff Engineer", "company": "Acme"},
                evidence_refs=[],
            )
        assert result is not None
        assert isinstance(result, str)

    def test_upserts_vertex_with_user_id(self):
        from graph_traceability import write_resume_version_to_graph

        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.upsert_vertex.return_value = "ro_resume_versions/abc"

        with patch("arango_client.get_arango_client", return_value=mock_client):
            write_resume_version_to_graph(
                user_id=3,
                version_id=42,
                source="agent_tailor",
                posting={},
                evidence_refs=[],
            )

        call_args = mock_client.upsert_vertex.call_args
        assert call_args[0][0] == "ro_resume_versions"
        vertex_data = call_args[0][1]
        assert vertex_data.get("user_id") == 3
        assert vertex_data.get("version_id") == 42

    def test_writes_edges_for_evidence_refs(self):
        from graph_traceability import write_resume_version_to_graph

        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.upsert_vertex.return_value = "ro_resume_versions/v1"

        evidence_refs = [
            {"_id": "ro_client_projects/abc", "type": "client", "confidence": 0.9},
            {"_id": "ro_business_outcomes/def", "type": "outcome", "confidence": 0.8},
        ]

        with patch("arango_client.get_arango_client", return_value=mock_client):
            write_resume_version_to_graph(
                user_id=3,
                version_id=42,
                source="agent_tailor",
                posting={},
                evidence_refs=evidence_refs,
            )

        assert mock_client.upsert_edge.call_count == 2

    def test_returns_none_when_not_connected(self):
        from graph_traceability import write_resume_version_to_graph

        mock_client = MagicMock()
        mock_client.is_connected = False

        with patch("arango_client.get_arango_client", return_value=mock_client):
            result = write_resume_version_to_graph(
                user_id=3,
                version_id=42,
                source="agent_tailor",
                posting={},
                evidence_refs=[],
            )
        assert result is None


# ---------------------------------------------------------------------------
# P2-B.3: Evidence coverage API
# ---------------------------------------------------------------------------


class TestEvidenceCoverageAPI:
    def test_coverage_endpoint_exists(self, client):
        resp = client.get("/api/graph/evidence-coverage", headers={"user-id": "3"})
        assert resp.status_code in (200, 503), f"Expected 200 or 503, got {resp.status_code}"

    def test_coverage_returns_json(self, client):
        resp = client.get("/api/graph/evidence-coverage", headers={"user-id": "3"})
        assert resp.get_json() is not None

    def test_coverage_200_has_required_fields(self, client):
        resp = client.get("/api/graph/evidence-coverage", headers={"user-id": "3"})
        if resp.status_code == 200:
            data = resp.get_json()
            assert "total_evidence" in data
            assert "evidence_used" in data
            assert "evidence_untapped" in data
            assert "coverage_pct" in data
            assert "untapped_items" in data

    def test_coverage_pct_between_0_and_100(self, client):
        resp = client.get("/api/graph/evidence-coverage", headers={"user-id": "3"})
        if resp.status_code == 200:
            data = resp.get_json()
            pct = data.get("coverage_pct", 0)
            assert 0 <= pct <= 100, f"coverage_pct {pct} out of range"


# ---------------------------------------------------------------------------
# P2-B.3: get_evidence_coverage() unit test
# ---------------------------------------------------------------------------


class TestGetEvidenceCoverage:
    def test_returns_dict_with_required_keys(self):
        from graph_traceability import get_evidence_coverage

        mock_client = MagicMock()
        mock_client.is_connected = True
        mock_client.query.return_value = [5]

        with patch("arango_client.get_arango_client", return_value=mock_client):
            result = get_evidence_coverage()

        assert isinstance(result, dict)
        assert "total_evidence" in result
        assert "evidence_used" in result
        assert "evidence_untapped" in result
        assert "coverage_pct" in result

    def test_returns_zero_coverage_when_not_connected(self):
        from graph_traceability import get_evidence_coverage

        mock_client = MagicMock()
        mock_client.is_connected = False

        with patch("arango_client.get_arango_client", return_value=mock_client):
            result = get_evidence_coverage()

        assert result["total_evidence"] == 0
        assert result["coverage_pct"] == 0.0


# ---------------------------------------------------------------------------
# P2-B.4: Untapped evidence prompt injection
# ---------------------------------------------------------------------------


class TestUntappedEvidenceInjection:
    def test_get_untapped_evidence_returns_list(self):
        from graph_traceability import get_untapped_evidence

        mock_client = MagicMock()
        mock_client.is_connected = True
        # AQL uses RETURN SLICE(...) so cursor wraps result as [[item1, item2]]
        mock_client.query.return_value = [
            [{"type": "client", "name": "AHEAD", "_id": "ro_client_projects/x"}]
        ]

        with patch("arango_client.get_arango_client", return_value=mock_client):
            result = get_untapped_evidence(limit=5)

        assert isinstance(result, list)

    def test_build_untapped_prompt_injection_returns_string(self):
        from graph_traceability import build_untapped_prompt_injection

        untapped = [
            {"type": "client", "name": "AHEAD"},
            {"type": "outcome", "name": "Reduced deployment time 60%"},
        ]
        result = build_untapped_prompt_injection(untapped)
        assert isinstance(result, str)
        assert "AHEAD" in result

    def test_prompt_injection_empty_when_no_untapped(self):
        from graph_traceability import build_untapped_prompt_injection

        result = build_untapped_prompt_injection([])
        assert result == ""
