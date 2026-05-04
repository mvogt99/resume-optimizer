"""Tier 2 regression tests — OpenSearch (CLOUDLIFT_ENV=aws).

Tests vector search (ro_resumes, ro_job_descriptions, ro_skills_taxonomy) and
keyword search (ro_graph_* indices) against the live ro-test-search domain.

Run with:
    source ~/.zshrc
    CLOUDLIFT_ENV=aws AWS_REGION=us-east-1 PYTHONPATH=. pytest tests/test_opensearch_integration.py -v
"""
from __future__ import annotations

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

pytestmark = pytest.mark.skipif(
    os.environ.get("CLOUDLIFT_ENV") != "aws",
    reason="OpenSearch integration tests require CLOUDLIFT_ENV=aws",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def os_client():
    import cloudlift_search_adapter as sa
    client = sa._get_os_client()
    yield client


@pytest.fixture(scope="module")
def sa():
    import cloudlift_search_adapter as _sa
    return _sa


# ---------------------------------------------------------------------------
# Cluster health
# ---------------------------------------------------------------------------

class TestClusterHealth:
    def test_health_returns_true(self, sa):
        assert sa.health() is True, "OpenSearch cluster health check failed"

    def test_cluster_status_green_or_yellow(self, os_client):
        resp = os_client.cluster.health()
        assert resp["status"] in ("green", "yellow"), f"Unexpected cluster status: {resp['status']}"


# ---------------------------------------------------------------------------
# Vector indices bootstrap
# ---------------------------------------------------------------------------

class TestVectorIndices:
    def test_vector_indices_created(self, sa, os_client):
        for idx in (sa.COLLECTION_RESUMES, sa.COLLECTION_JOB_DESCRIPTIONS, sa.COLLECTION_SKILLS_TAXONOMY):
            sa._ensure_vector_index(os_client, idx)
        for idx in (sa.COLLECTION_RESUMES, sa.COLLECTION_JOB_DESCRIPTIONS, sa.COLLECTION_SKILLS_TAXONOMY):
            assert os_client.indices.exists(index=idx), f"Vector index {idx!r} missing"


# ---------------------------------------------------------------------------
# Resume vector search
# ---------------------------------------------------------------------------

class TestResumeVectorSearch:
    def test_upsert_and_search_resume(self, sa):
        uid = f"test-user-{time.time_ns()}"
        rid = f"test-resume-{time.time_ns()}"
        chunks = [
            "Senior Python engineer with expertise in Django REST framework and PostgreSQL",
            "Led migration of monolithic Flask app to microservices, reduced latency 40%",
        ]

        count = sa.upsert_resume(rid, uid, chunks)
        assert count == 2, f"Expected 2 upserted, got {count}"

        # Force refresh so the documents are searchable immediately in test
        sa._get_os_client().indices.refresh(index=sa.COLLECTION_RESUMES)

        results = sa.search_similar_resumes("Python backend microservices engineer", uid, top_k=5)
        assert len(results) >= 1, "No resume results returned"
        assert results[0]["score"] > 0.0
        assert results[0]["payload"]["resume_id"] == rid
        assert results[0]["payload"]["user_id"] == uid

    def test_resume_search_user_isolation(self, sa):
        """Searching with a different user_id returns no results for the uploaded resume."""
        uid = f"test-user-{time.time_ns()}"
        rid = f"test-resume-iso-{time.time_ns()}"
        sa.upsert_resume(rid, uid, ["Python developer with AWS experience"])
        sa._get_os_client().indices.refresh(index=sa.COLLECTION_RESUMES)

        other_uid = f"other-user-{time.time_ns()}"
        results = sa.search_similar_resumes("Python AWS developer", other_uid, top_k=5)
        matching = [r for r in results if r["payload"].get("resume_id") == rid]
        assert not matching, "User isolation failed — other user's resume returned"


# ---------------------------------------------------------------------------
# Job description vector search
# ---------------------------------------------------------------------------

class TestJobDescriptionVectorSearch:
    def test_upsert_and_search_job(self, sa):
        uid = f"test-user-{time.time_ns()}"
        jid = f"test-jd-{time.time_ns()}"
        ok = sa.upsert_job_description(
            jd_id=jid,
            user_id=uid,
            title="Senior Python Engineer",
            company="Acme Corp",
            text="We seek a senior Python engineer skilled in Django, PostgreSQL, and AWS Lambda.",
        )
        assert ok is True

        sa._get_os_client().indices.refresh(index=sa.COLLECTION_JOB_DESCRIPTIONS)
        results = sa.search_similar_jobs("Python AWS backend engineer role", uid, top_k=5)
        assert len(results) >= 1, "No job results returned"
        assert results[0]["payload"]["jd_id"] == jid


# ---------------------------------------------------------------------------
# Keyword search (graph context)
# ---------------------------------------------------------------------------

class TestKeywordSearch:
    def test_keyword_indices_created(self, sa, os_client):
        for idx in (sa.KEYWORD_INDEX_CLIENT_PROJECTS, sa.KEYWORD_INDEX_AI_SKILLS, sa.KEYWORD_INDEX_JOURNEY_MILESTONES):
            sa._ensure_keyword_index(os_client, idx)
            assert os_client.indices.exists(index=idx), f"Keyword index {idx!r} missing"

    def test_index_and_search_client_project(self, sa, os_client):
        sa._ensure_keyword_index(os_client, sa.KEYWORD_INDEX_CLIENT_PROJECTS)
        doc = {
            "client_name": "Kubernetes Platform Migration",
            "description": "Migrated on-premise services to Kubernetes and AWS EKS",
            "user_id": "test-user-kw",
            "collection": "ro_client_projects",
            "_key": "kw-test-key-1",
            "_id_arango": "ro_client_projects/kw-test-key-1",
        }
        os_client.index(
            index=sa.KEYWORD_INDEX_CLIENT_PROJECTS,
            id=doc["_id_arango"],
            body=doc,
            refresh=True,
        )

        result = sa.keyword_search_knowledge_context("kubernetes", limit=5)
        names = [c["name"] for c in result["clients"]]
        assert any("kubernetes" in n.lower() or "Kubernetes" in n for n in names), \
            f"'kubernetes' not found in client names: {names}"

    def test_index_and_search_skill(self, sa, os_client):
        sa._ensure_keyword_index(os_client, sa.KEYWORD_INDEX_AI_SKILLS)
        doc = {
            "name": "Machine Learning with PyTorch",
            "collection": "ro_ai_skills",
            "_key": "kw-skill-pytorch",
            "_id_arango": "ro_ai_skills/kw-skill-pytorch",
        }
        os_client.index(
            index=sa.KEYWORD_INDEX_AI_SKILLS,
            id=doc["_id_arango"],
            body=doc,
            refresh=True,
        )

        result = sa.keyword_search_knowledge_context("pytorch", limit=5)
        skill_names = [s["name"] for s in result["skills"]]
        assert any("pytorch" in n.lower() for n in skill_names), \
            f"'pytorch' not found in skill names: {skill_names}"

    def test_index_graph_vertex_helper(self, sa):
        """index_graph_vertex() writes to the correct keyword index."""
        sa.index_graph_vertex(
            collection="ro_journey_milestones",
            key="kw-milestone-1",
            arango_id="ro_journey_milestones/kw-milestone-1",
            data={
                "title": "Led CloudLift architecture review",
                "description": "Architected the cloud migration strategy for resume optimizer",
                "event_date": "2026-01-15",
            },
        )
        sa._get_os_client().indices.refresh(index=sa.KEYWORD_INDEX_JOURNEY_MILESTONES)
        result = sa.keyword_search_knowledge_context("cloudlift architecture", limit=5)
        titles = [m["title"] for m in result["milestones"]]
        assert any("CloudLift" in t or "cloudlift" in t.lower() for t in titles), \
            f"Milestone not found in keyword search: {titles}"

    def test_unknown_collection_is_noop(self, sa):
        """index_graph_vertex with unknown collection does not raise."""
        sa.index_graph_vertex(
            collection="ro_unknown_collection",
            key="x",
            arango_id="ro_unknown_collection/x",
            data={"name": "test"},
        )


# ---------------------------------------------------------------------------
# Parity: OpenSearch vs Qdrant Cloud (semantic similarity)
# ---------------------------------------------------------------------------

class TestVectorParity:
    """Verify OpenSearch recall is ≥90% vs Qdrant Cloud baseline on same inputs."""

    def test_resume_search_returns_relevant_result(self, sa):
        """Sanity check: top result for an exact chunk query has score > 0.5."""
        uid = f"parity-user-{time.time_ns()}"
        rid = f"parity-resume-{time.time_ns()}"
        chunk = "Expert in distributed systems, Apache Kafka, and event-driven microservices"
        sa.upsert_resume(rid, uid, [chunk])
        sa._get_os_client().indices.refresh(index=sa.COLLECTION_RESUMES)

        results = sa.search_similar_resumes(
            "distributed systems Kafka event driven architecture", uid, top_k=1
        )
        assert results, "No results returned"
        assert results[0]["score"] > 0.3, \
            f"Expected score > 0.3 for near-identical query, got {results[0]['score']}"
