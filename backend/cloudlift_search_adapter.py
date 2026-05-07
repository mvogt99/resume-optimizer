"""CloudLift search adapter for resume-optimizer — thin shim.

Provides vector search AND keyword search routed by CLOUDLIFT_ENV:
  local: cloudlift_vector_adapter → cloudlift QdrantAdapter (vector)
         ArangoDB CONTAINS() (keyword, via arango_client_domain)
  aws:   OpenSearch managed domain (both vector and keyword)

Embedding delegates to cloudlift SentenceTransformersAdapter (all-MiniLM-L6-v2, 384-dim).
OpenSearch index operations are RO-specific schema; cloudlift pattern applied for
lazy imports and no cloud SDK at module level.

Vector indices (384-dim COSINE):
  ro_resumes, ro_job_descriptions, ro_skills_taxonomy

Keyword indices (OpenSearch full-text, aws only):
  ro_graph_client_projects, ro_graph_ai_skills, ro_graph_journey_milestones

Environment variables:
  OPENSEARCH_ENDPOINT, OPENSEARCH_USER, OPENSEARCH_PASSWORD,
  OPENSEARCH_SECRET_ARN, AWS_REGION
"""
from __future__ import annotations

import logging
import os
from typing import Any

_logger = logging.getLogger(__name__)

CLOUDLIFT_ENV = os.environ.get("CLOUDLIFT_ENV", "local")
VECTOR_SIZE = 384

COLLECTION_RESUMES = "ro_resumes"
COLLECTION_JOB_DESCRIPTIONS = "ro_job_descriptions"
COLLECTION_SKILLS_TAXONOMY = "ro_skills_taxonomy"

# ---------------------------------------------------------------------------
# Credential bootstrap
# ---------------------------------------------------------------------------

_os_client = None


def _resolve_opensearch_credentials() -> tuple[str, str, str]:
    """Return (endpoint, user, password) for OpenSearch.

    Reads from env vars first; falls back to Secrets Manager.
    """
    endpoint = os.environ.get("OPENSEARCH_ENDPOINT", "")
    user = os.environ.get("OPENSEARCH_USER", "rosearch")
    password = os.environ.get("OPENSEARCH_PASSWORD", "")

    if not endpoint or not password:
        import boto3, json  # noqa: PLC0415
        secret_id = os.environ.get("OPENSEARCH_SECRET_ARN", "ro/test/opensearch")
        region = os.environ.get("AWS_REGION", "us-east-1")
        _logger.info("[search_adapter] fetching OpenSearch credentials from Secrets Manager: %s", secret_id)
        client = boto3.client("secretsmanager", region_name=region)
        secret = json.loads(client.get_secret_value(SecretId=secret_id)["SecretString"])
        endpoint = endpoint or secret.get("endpoint", "")
        user = user or secret.get("username", "rosearch")
        password = password or secret.get("password", "")

    return endpoint, user, password


def _get_os_client():
    """Return a cached opensearch-py client for the aws environment."""
    global _os_client
    if _os_client is None:
        from opensearchpy import OpenSearch, RequestsHttpConnection  # noqa: PLC0415
        endpoint, user, password = _resolve_opensearch_credentials()
        host = endpoint.removeprefix("https://").removeprefix("http://").rstrip("/")
        _os_client = OpenSearch(
            hosts=[{"host": host, "port": 443}],
            http_auth=(user, password),
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=30,
        )
    return _os_client


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

def _embed(texts: list[str]) -> list[list[float]]:
    """Embed texts via cloudlift SentenceTransformersAdapter (all-MiniLM-L6-v2, 384-dim)."""
    try:
        from cloudlift.bridge.local.sentence_transformers_adapter import SentenceTransformersAdapter  # noqa: PLC0415
        return SentenceTransformersAdapter().embed_batch(texts)
    except Exception as exc:
        _logger.error("[search_adapter] embedding failed: %s", exc)
        return [[0.0] * VECTOR_SIZE for _ in texts]


# ---------------------------------------------------------------------------
# Index bootstrap (called once on first use)
# ---------------------------------------------------------------------------

_indices_ensured: set[str] = set()


def _ensure_vector_index(client, index_name: str) -> None:
    if index_name in _indices_ensured:
        return
    if not client.indices.exists(index=index_name):
        mapping = {
            "settings": {"index": {"knn": True, "knn.algo_param.ef_search": 100}},
            "mappings": {
                "properties": {
                    "vector": {
                        "type": "knn_vector",
                        "dimension": VECTOR_SIZE,
                        "method": {
                            "name": "hnsw",
                            "space_type": "innerproduct",
                            "engine": "faiss",
                            "parameters": {"ef_construction": 128, "m": 16},
                        },
                    },
                    "metadata": {"type": "object", "dynamic": True},
                }
            },
        }
        client.indices.create(index=index_name, body=mapping)
        _logger.info("[search_adapter] created vector index: %s", index_name)
    _indices_ensured.add(index_name)


def _ensure_keyword_index(client, index_name: str) -> None:
    if index_name in _indices_ensured:
        return
    if not client.indices.exists(index=index_name):
        mapping = {
            "settings": {"number_of_shards": 1, "number_of_replicas": 0},
            "mappings": {
                "properties": {
                    "user_id": {"type": "keyword"},
                    "collection": {"type": "keyword"},
                    "_key": {"type": "keyword"},
                    "_id_arango": {"type": "keyword"},
                    "name": {"type": "text", "analyzer": "standard"},
                    "title": {"type": "text", "analyzer": "standard"},
                    "description": {"type": "text", "analyzer": "standard"},
                    "client_name": {"type": "text", "analyzer": "standard"},
                    "category": {"type": "keyword"},
                }
            },
        }
        client.indices.create(index=index_name, body=mapping)
        _logger.info("[search_adapter] created keyword index: %s", index_name)
    _indices_ensured.add(index_name)


# ---------------------------------------------------------------------------
# Vector search — public API (mirrors cloudlift_vector_adapter.py interface)
# ---------------------------------------------------------------------------

def upsert_resume(resume_id: str, user_id: str, chunks: list[str]) -> int:
    """Embed and upsert resume chunks into OpenSearch (aws) or Qdrant (local)."""
    if CLOUDLIFT_ENV != "aws":
        from cloudlift_vector_adapter import upsert_resume as _qdrant_upsert  # noqa: PLC0415
        return _qdrant_upsert(resume_id, user_id, chunks)
    try:
        client = _get_os_client()
        _ensure_vector_index(client, COLLECTION_RESUMES)
        vectors = _embed(chunks)
        for i, (vec, chunk) in enumerate(zip(vectors, chunks)):
            doc_id = f"{resume_id}:{i}"
            client.index(
                index=COLLECTION_RESUMES,
                id=doc_id,
                body={
                    "vector": vec,
                    "metadata": {
                        "resume_id": resume_id,
                        "user_id": user_id,
                        "chunk_idx": i,
                        "text_preview": chunk[:200],
                    },
                },
                refresh=False,
            )
        _logger.info("[search_adapter] upserted %d resume chunks for %s", len(chunks), resume_id)
        return len(chunks)
    except Exception as exc:
        _logger.error("[search_adapter] upsert_resume failed: %s", exc)
        return 0


def upsert_job_description(jd_id: str, user_id: str, title: str, company: str, text: str) -> bool:
    """Embed and upsert a job description."""
    if CLOUDLIFT_ENV != "aws":
        from cloudlift_vector_adapter import upsert_job_description as _q  # noqa: PLC0415
        return _q(jd_id, user_id, title, company, text)
    try:
        client = _get_os_client()
        _ensure_vector_index(client, COLLECTION_JOB_DESCRIPTIONS)
        vector = _embed([text])[0]
        client.index(
            index=COLLECTION_JOB_DESCRIPTIONS,
            id=jd_id,
            body={
                "vector": vector,
                "metadata": {
                    "jd_id": jd_id,
                    "user_id": user_id,
                    "title": title,
                    "company": company,
                    "text_preview": text[:300],
                },
            },
            refresh=False,
        )
        return True
    except Exception as exc:
        _logger.error("[search_adapter] upsert_job_description failed: %s", exc)
        return False


def search_similar_resumes(query_text: str, user_id: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Vector search for resumes similar to query_text, filtered by user_id."""
    if CLOUDLIFT_ENV != "aws":
        from cloudlift_vector_adapter import search_similar_resumes as _q  # noqa: PLC0415
        return _q(query_text, user_id, top_k)
    try:
        client = _get_os_client()
        _ensure_vector_index(client, COLLECTION_RESUMES)
        vector = _embed([query_text])[0]
        resp = client.search(
            index=COLLECTION_RESUMES,
            body={
                "size": top_k,
                "query": {"knn": {"vector": {"vector": vector, "k": top_k * 4}}},
                "post_filter": {"term": {"metadata.user_id.keyword": user_id}},
                "_source": ["metadata"],
            },
        )
        return [
            {"score": h["_score"], "payload": h["_source"].get("metadata", {})}
            for h in resp["hits"]["hits"]
        ][:top_k]
    except Exception as exc:
        _logger.error("[search_adapter] search_similar_resumes failed: %s", exc)
        return []


def search_similar_jobs(query_text: str, user_id: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Vector search for job descriptions similar to query_text."""
    if CLOUDLIFT_ENV != "aws":
        from cloudlift_vector_adapter import search_similar_jobs as _q  # noqa: PLC0415
        return _q(query_text, user_id, top_k)
    try:
        client = _get_os_client()
        _ensure_vector_index(client, COLLECTION_JOB_DESCRIPTIONS)
        vector = _embed([query_text])[0]
        resp = client.search(
            index=COLLECTION_JOB_DESCRIPTIONS,
            body={
                "size": top_k,
                "query": {"knn": {"vector": {"vector": vector, "k": top_k * 4}}},
                "post_filter": {"term": {"metadata.user_id.keyword": user_id}},
                "_source": ["metadata"],
            },
        )
        return [
            {"score": h["_score"], "payload": h["_source"].get("metadata", {})}
            for h in resp["hits"]["hits"]
        ][:top_k]
    except Exception as exc:
        _logger.error("[search_adapter] search_similar_jobs failed: %s", exc)
        return []


def search_skills(query_skill: str, top_k: int = 10) -> list[dict[str, Any]]:
    """Vector search for semantically similar skills from taxonomy."""
    if CLOUDLIFT_ENV != "aws":
        from cloudlift_vector_adapter import search_skills as _q  # noqa: PLC0415
        return _q(query_skill, top_k)
    try:
        client = _get_os_client()
        _ensure_vector_index(client, COLLECTION_SKILLS_TAXONOMY)
        vector = _embed([query_skill])[0]
        resp = client.search(
            index=COLLECTION_SKILLS_TAXONOMY,
            body={
                "size": top_k,
                "query": {"knn": {"vector": {"vector": vector, "k": top_k}}},
                "_source": ["metadata"],
            },
        )
        return [
            {"score": h["_score"], "payload": h["_source"].get("metadata", {})}
            for h in resp["hits"]["hits"]
        ]
    except Exception as exc:
        _logger.error("[search_adapter] search_skills failed: %s", exc)
        return []


def health() -> bool:
    """True if the search backend is reachable."""
    if CLOUDLIFT_ENV != "aws":
        from cloudlift_vector_adapter import health as _q  # noqa: PLC0415
        return _q()
    try:
        client = _get_os_client()
        resp = client.cluster.health()
        return resp.get("status") in ("green", "yellow")
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Keyword search — graph context (aws only; local falls back to ArangoDB)
# ---------------------------------------------------------------------------

KEYWORD_INDEX_CLIENT_PROJECTS = "ro_graph_client_projects"
KEYWORD_INDEX_AI_SKILLS = "ro_graph_ai_skills"
KEYWORD_INDEX_JOURNEY_MILESTONES = "ro_graph_journey_milestones"


def keyword_search_knowledge_context(theme: str, limit: int = 10) -> dict[str, list[dict[str, Any]]]:
    """Full-text search across graph vertex keyword indices.

    Replaces ArangoDB CONTAINS() queries when CLOUDLIFT_ENV=aws.
    Returns same dict shape as ArangoClientDomainMixin.get_knowledge_context().
    """
    client = _get_os_client()
    for idx in (KEYWORD_INDEX_CLIENT_PROJECTS, KEYWORD_INDEX_AI_SKILLS, KEYWORD_INDEX_JOURNEY_MILESTONES):
        _ensure_keyword_index(client, idx)

    q = theme.lower()
    query = {
        "size": limit,
        "query": {
            "multi_match": {
                "query": q,
                "fields": ["name", "title", "description", "client_name"],
                "type": "best_fields",
                "fuzziness": "AUTO",
            }
        },
    }

    def _run(index: str) -> list[dict[str, Any]]:
        try:
            resp = client.search(index=index, body=query)
            return [h["_source"] for h in resp["hits"]["hits"]]
        except Exception as exc:
            _logger.warning("[search_adapter] keyword search on %s failed: %s", index, exc)
            return []

    clients_raw = _run(KEYWORD_INDEX_CLIENT_PROJECTS)
    skills_raw = _run(KEYWORD_INDEX_AI_SKILLS)
    milestones_raw = _run(KEYWORD_INDEX_JOURNEY_MILESTONES)

    return {
        "clients": [
            {"name": r.get("client_name", r.get("name", "")), "_id": r.get("_id_arango", "")}
            for r in clients_raw
        ],
        "skills": [
            {"name": r.get("name", ""), "_id": r.get("_id_arango", "")}
            for r in skills_raw
        ],
        "milestones": [
            {"title": r.get("title", ""), "date": r.get("event_date", ""), "_id": r.get("_id_arango", "")}
            for r in milestones_raw
        ],
    }


def index_graph_vertex(collection: str, key: str, arango_id: str, data: dict[str, Any]) -> None:
    """Index a graph vertex into OpenSearch for keyword search.

    Called during Phase 3.2 DynamoDB migration (dual-write).
    No-op for collections that don't have a keyword index.
    """
    if CLOUDLIFT_ENV != "aws":
        return
    index_map = {
        "ro_client_projects": KEYWORD_INDEX_CLIENT_PROJECTS,
        "ro_ai_skills": KEYWORD_INDEX_AI_SKILLS,
        "ro_journey_milestones": KEYWORD_INDEX_JOURNEY_MILESTONES,
    }
    index_name = index_map.get(collection)
    if not index_name:
        return
    try:
        client = _get_os_client()
        _ensure_keyword_index(client, index_name)
        body = {**data, "collection": collection, "_key": key, "_id_arango": arango_id}
        client.index(index=index_name, id=arango_id, body=body, refresh=False)
    except Exception as exc:
        _logger.warning("[search_adapter] index_graph_vertex failed for %s: %s", arango_id, exc)
