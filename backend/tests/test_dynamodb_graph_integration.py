"""Tier 2 regression tests — DynamoDB graph adapter (CLOUDLIFT_ENV=aws).

Tests every public method of DynamoDBGraphAdapter against the live
ro-test-graph table, verifying parity with ArangoClient semantics.

Run with:
    source ~/.zshrc
    CLOUDLIFT_ENV=aws AWS_REGION=us-east-1 PYTHONPATH=. \
      pytest tests/test_dynamodb_graph_integration.py -v
"""
from __future__ import annotations

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

pytestmark = pytest.mark.skipif(
    os.environ.get("CLOUDLIFT_ENV") != "aws",
    reason="DynamoDB graph tests require CLOUDLIFT_ENV=aws",
)

UID = f"test-user-{int(time.time())}"


@pytest.fixture(scope="module")
def adapter():
    from cloudlift_graph_adapter import DynamoDBGraphAdapter
    return DynamoDBGraphAdapter()


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

class TestConnection:
    def test_is_connected(self, adapter):
        assert adapter.is_connected is True

    def test_initialize_returns_true(self, adapter):
        assert adapter.initialize() is True


# ---------------------------------------------------------------------------
# Vertex CRUD
# ---------------------------------------------------------------------------

class TestVertexCRUD:
    def test_upsert_and_get_vertex(self, adapter):
        vid = adapter.upsert_vertex(
            "ro_client_projects",
            {"name": "DDB Test Corp", "user_id": UID, "folder_id": "f1"},
            key_source=f"test-project-{UID}",
        )
        assert vid.startswith("ro_client_projects/")
        key = vid.split("/")[1]

        item = adapter.get_vertex("ro_client_projects", key)
        assert item is not None
        assert item["name"] == "DDB Test Corp"
        assert item["_id"] == vid

    def test_upsert_is_idempotent(self, adapter):
        vid1 = adapter.upsert_vertex("ro_technologies", {"name": "Kafka"},
                                     key_source="tech:Kafka")
        vid2 = adapter.upsert_vertex("ro_technologies", {"name": "Kafka"},
                                     key_source="tech:Kafka")
        assert vid1 == vid2

    def test_get_missing_vertex_returns_none(self, adapter):
        assert adapter.get_vertex("ro_client_projects", "nonexistent-key-xyz") is None

    def test_delete_vertex(self, adapter):
        vid = adapter.upsert_vertex("ro_technologies", {"name": "DeleteMe"},
                                    key_source=f"del-{UID}")
        key = vid.split("/")[1]
        result = adapter.delete_vertex("ro_technologies", key)
        assert result is True
        assert adapter.get_vertex("ro_technologies", key) is None


# ---------------------------------------------------------------------------
# Edge operations
# ---------------------------------------------------------------------------

class TestEdgeOperations:
    def test_upsert_and_traverse_edge(self, adapter):
        proj_id = adapter.upsert_vertex(
            "ro_client_projects", {"name": "EdgeProj", "user_id": UID},
            key_source=f"edge-proj-{UID}"
        )
        tech_id = adapter.upsert_vertex(
            "ro_technologies", {"name": "PostgreSQL"},
            key_source="tech:PostgreSQL"
        )
        edge_id = adapter.upsert_edge("ro_client_used_tech", proj_id, tech_id,
                                      {"confidence": 0.9})
        assert edge_id.startswith("ro_client_used_tech/")

        # OUTBOUND from project → should find PostgreSQL
        neighbors = adapter.get_neighbors(proj_id, "ro_client_used_tech", "outbound")
        names = [n.get("name", "") for n in neighbors if n]
        assert "PostgreSQL" in names

        # INBOUND to tech → should find project
        inbound = adapter.get_neighbors(tech_id, "ro_client_used_tech", "inbound")
        ids = [n.get("_id", "") for n in inbound if n]
        assert proj_id in ids

    def test_edge_upsert_idempotent(self, adapter):
        proj_id = adapter.upsert_vertex(
            "ro_client_projects", {"name": "IdempProj"},
            key_source=f"idemp-proj-{UID}"
        )
        tech_id = adapter.upsert_vertex(
            "ro_technologies", {"name": "Redis"},
            key_source="tech:Redis"
        )
        e1 = adapter.upsert_edge("ro_client_used_tech", proj_id, tech_id)
        e2 = adapter.upsert_edge("ro_client_used_tech", proj_id, tech_id)
        assert e1 == e2


# ---------------------------------------------------------------------------
# Collection scan + user-scoped queries
# ---------------------------------------------------------------------------

class TestCollectionOps:
    def test_scan_collection_returns_inserted(self, adapter):
        adapter.upsert_vertex("ro_ai_skills", {"name": "Python", "user_id": UID},
                              key_source=f"skill:Python:{UID}")
        items = adapter._scan_collection("ro_ai_skills")
        names = [i.get("name", "") for i in items]
        assert "Python" in names

    def test_query_by_user_id(self, adapter):
        adapter.upsert_vertex("ro_journey_milestones",
                              {"title": "DDB Milestone", "user_id": UID},
                              key_source=f"milestone:{UID}")
        results = adapter._query_by_user_id("ro_journey_milestones", UID)
        titles = [r.get("title", "") for r in results]
        assert "DDB Milestone" in titles

    def test_count_collection(self, adapter):
        adapter.upsert_vertex("ro_governance_controls", {"name": "SOC2"},
                              key_source="gov:SOC2")
        count = adapter._count_collection("ro_governance_controls")
        assert isinstance(count, int)
        assert count >= 1


# ---------------------------------------------------------------------------
# Limited AQL translator
# ---------------------------------------------------------------------------

class TestAQLTranslator:
    def test_return_length(self, adapter):
        adapter.upsert_vertex("ro_technologies", {"name": "Docker"},
                              key_source="tech:Docker")
        result = adapter.query("RETURN LENGTH(ro_technologies)")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0] >= 1

    def test_filter_by_user_id(self, adapter):
        uid2 = f"aql-user-{int(time.time())}"
        adapter.upsert_vertex("ro_client_projects", {"name": "AQL Corp", "user_id": uid2},
                              key_source=f"aql-proj-{uid2}")
        rows = adapter.query(
            "FOR c IN ro_client_projects FILTER c.user_id == @uid RETURN {name: c.name}",
            {"uid": uid2}
        )
        names = [r.get("name") for r in rows]
        assert "AQL Corp" in names

    def test_complex_aql_returns_empty(self, adapter):
        result = adapter.query("""
            LET used = (FOR c IN ro_client_projects
                LET edges = (FOR e IN ro_version_sourced_from FILTER e._to == c._id RETURN 1)
                FILTER LENGTH(edges) > 0 RETURN 1)
            RETURN LENGTH(used)
        """)
        assert result == []


# ---------------------------------------------------------------------------
# Domain methods
# ---------------------------------------------------------------------------

class TestDomainMethods:
    def test_get_technology_summary(self, adapter):
        result = adapter.get_technology_summary()
        assert isinstance(result, list)
        for entry in result:
            assert "name" in entry
            assert "client_count" in entry

    def test_write_campaign_to_graph(self, adapter):
        campaign = {"theme": "AI Engineering", "audience": "CTOs",
                    "tone": "professional", "id": f"camp-{UID}"}
        posts = [
            {"title": "Post 1", "content": "Content 1", "position": 0, "source_refs": []},
            {"title": "Post 2", "content": "Content 2", "position": 1, "source_refs": []},
        ]
        result = adapter.write_campaign_to_graph(campaign, posts)
        assert result is True

        campaigns = adapter._scan_collection("ro_campaigns")
        themes = [c.get("theme", "") for c in campaigns]
        assert "AI Engineering" in themes

    def test_write_deep_profile(self, adapter):
        profile = {
            "professional_summary": "Experienced cloud architect",
            "career_arc": {"trajectory": "IC to Staff", "years_total": 12},
            "technology_mastery": [
                {"name": "Kubernetes", "proficiency": "expert", "evidence": ["proj1"]},
            ],
            "business_impacts": [
                {"title": "Reduced latency 40%", "context": "API redesign", "scope": "company"},
            ],
        }
        result = adapter.write_deep_profile_to_graph(profile)
        assert result is True

        skills = adapter._scan_collection("ro_ai_skills")
        names = [s.get("name", "") for s in skills]
        assert "Kubernetes" in names

    def test_get_knowledge_context_returns_dict(self, adapter):
        result = adapter.get_knowledge_context("Python", limit=5)
        assert isinstance(result, dict)
        assert "clients" in result
        assert "skills" in result
        assert "milestones" in result

    def test_get_campaign_coverage_returns_dict(self, adapter):
        result = adapter.get_campaign_coverage()
        assert isinstance(result, dict)
        assert "total_clients" in result
        assert "overall_coverage_pct" in result
        assert 0.0 <= result["overall_coverage_pct"] <= 100.0

    def test_query_projects_by_user(self, adapter):
        adapter.upsert_vertex("ro_client_projects",
                              {"name": "User Project", "user_id": UID, "outcomes": ["shipped product"]},
                              key_source=f"proj-ct4-{UID}")
        results = adapter.query_projects_by_user(UID, limit=10)
        names = [r.get("name", "") for r in results]
        assert "User Project" in names

    def test_query_journey_milestones_by_user(self, adapter):
        adapter.upsert_vertex("ro_journey_milestones",
                              {"title": "Promoted to Staff", "user_id": UID},
                              key_source=f"ms-ct4-{UID}")
        results = adapter.query_journey_milestones(UID, limit=10)
        events = [r.get("event", "") for r in results]
        assert "Promoted to Staff" in events

    def test_query_business_outcomes_by_user(self, adapter):
        adapter.upsert_vertex("ro_business_outcomes",
                              {"title": "Saved $2M annually", "user_id": UID},
                              key_source=f"bo-ct4-{UID}")
        results = adapter.query_business_outcomes(UID, limit=10)
        descs = [r.get("description", "") for r in results]
        assert "Saved $2M annually" in descs

    def test_query_skills_inventory_by_user(self, adapter):
        adapter.upsert_vertex("ro_skills",
                              {"name": "Terraform", "user_id": UID,
                               "first_seen": "2022-01-01", "projects_count": 3},
                              key_source=f"skill-ct4-{UID}")
        results = adapter.query_skills_inventory(UID, limit=10)
        skills = [r.get("skill", "") for r in results]
        assert "Terraform" in skills


# ---------------------------------------------------------------------------
# Factory: get_graph_client() routes correctly
# ---------------------------------------------------------------------------

class TestGraphClientFactory:
    def test_aws_env_returns_dynamodb_adapter(self):
        from arango_client import get_graph_client
        from cloudlift_graph_adapter import DynamoDBGraphAdapter
        client = get_graph_client()
        assert isinstance(client, DynamoDBGraphAdapter)
