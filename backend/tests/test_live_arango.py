"""Live ArangoDB integration tests — verifies arango_client.py against real ArangoDB.

Tests: initialize, CRUD, SHA-1 deterministic keys, graph traversal, campaign/profile writes.
Requires ArangoDB running on localhost:8529 with credentials root/hybrid_ai_root.
Skips gracefully if ArangoDB unavailable.
"""

import hashlib
import os
import sys

import pytest
import requests

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


def _arango_up():
    try:
        r = requests.get(
            "http://localhost:8529/_api/version",
            auth=("root", "hybrid_ai_root"),
            timeout=3,
        )
        return r.status_code == 200
    except Exception:
        return False


ARANGO_AVAILABLE = _arango_up()
pytestmark = pytest.mark.skipif(not ARANGO_AVAILABLE, reason="ArangoDB not running")


@pytest.fixture(scope="module")
def arango():
    """Return initialized ArangoClient instance."""
    from arango_client import ArangoClient

    client = ArangoClient()
    success = client.initialize()
    assert success, "ArangoClient.initialize() must return True"
    return client


# ===================================================================
# Initialization & Connection (3 tests)
# ===================================================================


class TestArangoInit:
    """ArangoDB connection and collection setup."""

    def test_initialize_returns_true(self, arango):
        """initialize() succeeds and sets is_connected."""
        assert arango.is_connected

    def test_collections_exist(self, arango):
        """All ro_-prefixed collections created after initialize."""
        r = requests.get(
            "http://localhost:8529/_db/hybrid_ai/_api/collection",
            auth=("root", "hybrid_ai_root"),
            timeout=5,
        )
        cols = {c["name"] for c in r.json().get("result", [])}
        expected_vertex = {
            "ro_client_projects",
            "ro_technologies",
            "ro_governance_controls",
            "ro_outcomes",
            "ro_source_documents",
            "ro_skills",
            "ro_journey_milestones",
            "ro_ai_skills",
            "ro_journey_projects",
            "ro_campaigns",
            "ro_campaign_posts",
            "ro_business_outcomes",
            "ro_deep_profiles",
        }
        for name in expected_vertex:
            assert name in cols, f"Missing vertex collection: {name}"

    def test_graph_exists(self, arango):
        """Named graph ro_knowledge_graph exists."""
        r = requests.get(
            "http://localhost:8529/_db/hybrid_ai/_api/gharial/ro_knowledge_graph",
            auth=("root", "hybrid_ai_root"),
            timeout=5,
        )
        assert r.status_code == 200, f"Graph not found: {r.text}"


# ===================================================================
# CRUD Operations (5 tests)
# ===================================================================


class TestArangoCRUD:
    """Vertex and edge CRUD with SHA-1 deterministic keys."""

    def test_upsert_vertex_creates_and_returns_id(self, arango):
        """upsert_vertex → creates vertex, returns collection/key."""
        vid = arango.upsert_vertex(
            "ro_technologies",
            {"name": "test_tech_python", "category": "language"},
            key_source="test_tech_python",
        )
        assert vid is not None
        assert vid.startswith("ro_technologies/")

    def test_upsert_vertex_deterministic_key(self, arango):
        """Same key_source → same SHA-1 key (idempotent)."""
        vid1 = arango.upsert_vertex(
            "ro_technologies",
            {"name": "determ_test", "category": "test"},
            key_source="determ_test_key",
        )
        vid2 = arango.upsert_vertex(
            "ro_technologies",
            {"name": "determ_test_updated", "category": "test"},
            key_source="determ_test_key",
        )
        assert vid1 == vid2, "Same key_source must produce same vertex ID"

        # Verify update happened
        key = vid1.split("/")[1]
        vertex = arango.get_vertex("ro_technologies", key)
        assert vertex is not None
        assert vertex["name"] == "determ_test_updated"

    def test_upsert_edge_creates_and_returns_id(self, arango):
        """upsert_edge → creates edge between vertices."""
        v1 = arango.upsert_vertex(
            "ro_client_projects",
            {"name": "test_client_edge", "client_name": "EdgeTestCo"},
            key_source="test_client_edge",
        )
        v2 = arango.upsert_vertex(
            "ro_technologies",
            {"name": "test_tech_edge", "category": "framework"},
            key_source="test_tech_edge",
        )
        eid = arango.upsert_edge("ro_client_used_tech", v1, v2, {"strength": 0.9})
        assert eid is not None
        assert eid.startswith("ro_client_used_tech/")

    def test_get_vertex_retrieves(self, arango):
        """get_vertex → returns upserted vertex data."""
        key_source = "test_get_vertex_retrieve"
        arango.upsert_vertex(
            "ro_skills",
            {"name": "test_retrieval_skill", "category": "test"},
            key_source=key_source,
        )
        key = hashlib.sha1(key_source.encode()).hexdigest()
        vertex = arango.get_vertex("ro_skills", key)
        assert vertex is not None
        assert vertex["name"] == "test_retrieval_skill"

    def test_delete_vertex(self, arango):
        """delete_vertex → vertex no longer retrievable."""
        key_source = "test_delete_target"
        arango.upsert_vertex(
            "ro_skills",
            {"name": "delete_me", "category": "test"},
            key_source=key_source,
        )
        key = hashlib.sha1(key_source.encode()).hexdigest()
        assert arango.get_vertex("ro_skills", key) is not None

        result = arango.delete_vertex("ro_skills", key)
        assert result is True
        assert arango.get_vertex("ro_skills", key) is None


# ===================================================================
# Graph Traversal (4 tests)
# ===================================================================


class TestArangoTraversal:
    """Graph traversal queries."""

    @pytest.fixture(autouse=True)
    def _setup_graph_data(self, arango):
        """Create a small subgraph for traversal tests."""
        self.client_vid = arango.upsert_vertex(
            "ro_client_projects",
            {"name": "TraversalCo", "client_name": "TraversalCo"},
            key_source="traversal_co",
        )
        self.tech_vid = arango.upsert_vertex(
            "ro_technologies",
            {"name": "FastAPI", "category": "framework"},
            key_source="traversal_fastapi",
        )
        self.tech2_vid = arango.upsert_vertex(
            "ro_technologies",
            {"name": "Docker", "category": "devops"},
            key_source="traversal_docker",
        )
        arango.upsert_edge("ro_client_used_tech", self.client_vid, self.tech_vid)
        arango.upsert_edge("ro_client_used_tech", self.client_vid, self.tech2_vid)

    def test_get_neighbors_outbound(self, arango):
        """get_neighbors OUTBOUND → finds connected technologies."""
        neighbors = arango.get_neighbors(
            self.client_vid,
            "ro_client_used_tech",
            direction="outbound",
        )
        assert len(neighbors) >= 2
        names = {n.get("name") for n in neighbors}
        assert "FastAPI" in names
        assert "Docker" in names

    def test_get_clients_by_technology(self, arango):
        """get_clients_by_technology → INBOUND traversal finds clients."""
        clients = arango.get_clients_by_technology("FastAPI")
        assert len(clients) >= 1
        client_names = {c.get("name") or c.get("client_name") for c in clients}
        assert "TraversalCo" in client_names

    def test_get_technology_summary(self, arango):
        """get_technology_summary → returns all techs with client counts."""
        summary = arango.get_technology_summary()
        assert isinstance(summary, list)
        assert len(summary) >= 1
        # Each item should have name and client_count
        for item in summary:
            assert "name" in item
            assert "client_count" in item

    def test_raw_aql_query(self, arango):
        """query() → executes raw AQL, returns results."""
        results = arango.query(
            "FOR t IN ro_technologies FILTER t.name == @name RETURN t",
            bind_vars={"name": "FastAPI"},
        )
        assert len(results) >= 1
        assert results[0]["name"] == "FastAPI"


# ===================================================================
# Campaign & Profile Writes (3 tests)
# ===================================================================


class TestArangoCampaignProfile:
    """Campaign subgraph and deep profile writes."""

    def test_write_campaign_to_graph(self, arango):
        """write_campaign_to_graph → campaign + posts + edges created."""
        campaign = {
            "id": "test_campaign_live",
            "theme": "AI Leadership",
            "audience": "CTOs",
            "tone": "professional",
            "user_id": "1",
        }
        posts = [
            {
                "id": "test_post_1",
                "title": "AI in Enterprise",
                "content": "Post content about AI",
                "order_index": 0,
                "references": [],
            },
        ]
        result = arango.write_campaign_to_graph(campaign, posts)
        assert result is True

        # Verify campaign vertex exists — key_source is "campaign-{id}"
        key = hashlib.sha1("campaign-test_campaign_live".encode()).hexdigest()
        v = arango.get_vertex("ro_campaigns", key)
        assert v is not None

    def test_get_knowledge_context(self, arango):
        """get_knowledge_context → returns clients, skills, milestones for theme."""
        context = arango.get_knowledge_context("technology", limit=5)
        assert isinstance(context, dict)
        assert "clients" in context
        assert "skills" in context
        assert "milestones" in context

    def test_write_deep_profile_to_graph(self, arango):
        """write_deep_profile_to_graph → profile vertex created."""
        profile = {
            "user_id": "test_user_live",
            "career_phases": [{"phase": "Early Career", "years": "2000-2005"}],
            "higher_order_skills": [
                {"name": "Systems Thinking", "proficiency": 0.9, "evidence_count": 5},
            ],
            "business_impacts": [
                {"description": "Reduced costs", "category": "efficiency"},
            ],
            "differentiators": ["Full-stack AI"],
        }
        result = arango.write_deep_profile_to_graph(profile)
        assert result is True
