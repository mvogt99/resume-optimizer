"""Core tests for arango_client.py.

SHA-1 keys, constants, collection lists, disconnected behavior.
"""

import hashlib

import arango_client
import pytest

# ---------------------------------------------------------------------------
# _sha1_key
# ---------------------------------------------------------------------------


class TestSha1Key:
    """Tests for _sha1_key() deterministic key generation."""

    def test_returns_sha1_hex(self):
        result = arango_client._sha1_key("test")
        expected = hashlib.sha1(b"test").hexdigest()
        assert result == expected
        assert isinstance(result, str)

    def test_deterministic(self):
        a = arango_client._sha1_key("same input")
        b = arango_client._sha1_key("same input")
        assert a == b
        assert isinstance(a, str)

    def test_different_inputs_different_keys(self):
        a = arango_client._sha1_key("input_a")
        b = arango_client._sha1_key("input_b")
        assert a != b
        assert len(a) == len(b)

    def test_returns_40_char_hex(self):
        result = arango_client._sha1_key("anything")
        assert len(result) == 40
        assert all(c in "0123456789abcdef" for c in result)
        assert isinstance(result, str)

    def test_empty_string(self):
        result = arango_client._sha1_key("")
        expected = hashlib.sha1(b"").hexdigest()
        assert result == expected
        assert len(result) == 40


# ---------------------------------------------------------------------------
# Collection constants
# ---------------------------------------------------------------------------


class TestCollectionConstants:
    """Tests for collection and graph name constants."""

    def test_graph_name(self):
        assert arango_client.GRAPH_NAME == "ro_knowledge_graph"
        assert isinstance(arango_client.GRAPH_NAME, str)

    def test_p9_vertex_collections(self):
        expected = {
            "ro_client_projects",
            "ro_technologies",
            "ro_governance_controls",
            "ro_outcomes",
            "ro_source_documents",
            "ro_skills",
        }
        assert set(arango_client.P9_VERTEX_COLLECTIONS) == expected
        assert len(arango_client.P9_VERTEX_COLLECTIONS) == 6

    def test_p9_edge_collections(self):
        assert len(arango_client.P9_EDGE_COLLECTIONS) == 5
        assert "ro_client_used_tech" in arango_client.P9_EDGE_COLLECTIONS
        assert all(isinstance(c, str) for c in arango_client.P9_EDGE_COLLECTIONS)

    def test_p10_collections(self):
        assert "ro_journey_milestones" in arango_client.P10_VERTEX_COLLECTIONS
        assert "ro_ai_skills" in arango_client.P10_VERTEX_COLLECTIONS
        assert "ro_milestone_demonstrated_skill" in arango_client.P10_EDGE_COLLECTIONS
        assert len(arango_client.P10_VERTEX_COLLECTIONS) >= 2

    def test_p11_collections(self):
        assert "ro_campaigns" in arango_client.P11_VERTEX_COLLECTIONS
        assert "ro_campaign_posts" in arango_client.P11_VERTEX_COLLECTIONS
        assert "ro_campaign_contains_post" in arango_client.P11_EDGE_COLLECTIONS
        assert len(arango_client.P11_EDGE_COLLECTIONS) >= 3

    def test_p13_collections(self):
        assert "ro_business_outcomes" in arango_client.P13_VERTEX_COLLECTIONS
        assert "ro_outcome_driven_by_skill" in arango_client.P13_EDGE_COLLECTIONS
        assert len(arango_client.P13_VERTEX_COLLECTIONS) >= 1

    def test_p14_collections(self):
        assert "ro_deep_profiles" in arango_client.P14_VERTEX_COLLECTIONS
        assert "ro_profile_demonstrates_skill" in arango_client.P14_EDGE_COLLECTIONS
        assert len(arango_client.P14_VERTEX_COLLECTIONS) >= 1

    def test_all_vertex_is_union(self):
        expected = (
            arango_client.P9_VERTEX_COLLECTIONS
            + arango_client.P10_VERTEX_COLLECTIONS
            + arango_client.P11_VERTEX_COLLECTIONS
            + arango_client.P13_VERTEX_COLLECTIONS
            + arango_client.P14_VERTEX_COLLECTIONS
            + arango_client.P2B_VERTEX_COLLECTIONS
        )
        assert arango_client.ALL_VERTEX == expected
        assert isinstance(arango_client.ALL_VERTEX, list)

    def test_all_edge_is_union(self):
        expected = (
            arango_client.P9_EDGE_COLLECTIONS
            + arango_client.P10_EDGE_COLLECTIONS
            + arango_client.P11_EDGE_COLLECTIONS
            + arango_client.P13_EDGE_COLLECTIONS
            + arango_client.P14_EDGE_COLLECTIONS
            + arango_client.P2B_EDGE_COLLECTIONS
        )
        assert arango_client.ALL_EDGE == expected
        assert isinstance(arango_client.ALL_EDGE, list)

    def test_all_collections_prefixed(self):
        all_collections = arango_client.ALL_VERTEX + arango_client.ALL_EDGE
        assert len(all_collections) > 0
        for coll in all_collections:
            assert coll.startswith("ro_"), f"Collection {coll} missing ro_ prefix"

    def test_no_duplicate_vertex_collections(self):
        assert len(arango_client.ALL_VERTEX) == len(set(arango_client.ALL_VERTEX))

    def test_no_duplicate_edge_collections(self):
        assert len(arango_client.ALL_EDGE) == len(set(arango_client.ALL_EDGE))


# ---------------------------------------------------------------------------
# ArangoClient disconnected behavior
# ---------------------------------------------------------------------------


class TestDisconnectedClient:
    """Tests for ArangoClient methods when not connected (no ArangoDB)."""

    @pytest.fixture
    def disconnected(self):
        c = arango_client.ArangoClient()
        # Do NOT call initialize — simulates no ArangoDB
        return c

    def test_is_connected_false(self, disconnected):
        assert disconnected.is_connected is False
        assert disconnected._db is None

    def test_upsert_vertex_returns_none(self, disconnected):
        result = disconnected.upsert_vertex("ro_technologies", {"name": "Python"})
        assert result is None
        assert disconnected.is_connected is False

    def test_upsert_edge_returns_none(self, disconnected):
        result = disconnected.upsert_edge("ro_client_used_tech", "a/1", "b/2")
        assert result is None
        assert disconnected.is_connected is False

    def test_query_returns_empty_list(self, disconnected):
        result = disconnected.query("FOR doc IN ro_technologies RETURN doc")
        assert result == []
        assert isinstance(result, list)

    def test_get_vertex_returns_none(self, disconnected):
        result = disconnected.get_vertex("ro_technologies", "some_key")
        assert result is None
        assert disconnected.is_connected is False

    def test_get_neighbors_returns_empty(self, disconnected):
        result = disconnected.get_neighbors("ro_technologies/key", "ro_client_used_tech")
        assert result == []
        assert isinstance(result, list)

    def test_delete_vertex_returns_false(self, disconnected):
        result = disconnected.delete_vertex("ro_technologies", "some_key")
        assert result is False
        assert isinstance(result, bool)

    def test_get_clients_by_technology_returns_empty(self, disconnected):
        result = disconnected.get_clients_by_technology("Python")
        assert result == []
        assert isinstance(result, list)

    def test_get_technology_summary_returns_empty(self, disconnected):
        result = disconnected.get_technology_summary()
        assert result == []
        assert isinstance(result, list)

    def test_get_knowledge_context_returns_empty(self, disconnected):
        result = disconnected.get_knowledge_context("AI")
        assert result == {"clients": [], "skills": [], "milestones": []}
        assert "clients" in result
        assert "skills" in result

    def test_get_campaign_coverage_returns_empty(self, disconnected):
        result = disconnected.get_campaign_coverage()
        assert result["total_clients"] == 0
        assert result["overall_coverage_pct"] == 0.0
        assert isinstance(result, dict)

    def test_write_campaign_to_graph_returns_false(self, disconnected):
        result = disconnected.write_campaign_to_graph({}, [])
        assert result is False
        assert isinstance(result, bool)

    def test_write_deep_profile_to_graph_returns_false(self, disconnected):
        result = disconnected.write_deep_profile_to_graph({})
        assert result is False
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# Connection settings
# ---------------------------------------------------------------------------


class TestConnectionSettings:
    """Tests for connection constant defaults."""

    def test_default_host(self):
        assert "8529" in arango_client.ARANGO_HOST
        assert isinstance(arango_client.ARANGO_HOST, str)

    def test_default_db(self):
        assert arango_client.ARANGO_DB == "hybrid_ai"
        assert isinstance(arango_client.ARANGO_DB, str)

    def test_default_user(self):
        assert arango_client.ARANGO_USER == "root"
        assert isinstance(arango_client.ARANGO_USER, str)
