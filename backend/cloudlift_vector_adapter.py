"""CloudLift vector adapter for resume-optimizer — thin shim.

Delegates embedding to cloudlift SentenceTransformersAdapter.
Qdrant operations use qdrant-client directly (cloudlift QdrantAdapter v1
does not support payload filtering required by RO's multi-user isolation).

  local: Qdrant at QDRANT_HOST:QDRANT_PORT (host-running hybrid-ai-windows container)
  aws:   Qdrant Cloud (QDRANT_CLOUD_URL + QDRANT_API_KEY)

Collections (vector_size=384, distance=COSINE, all-MiniLM-L6-v2):
  ro_resumes, ro_job_descriptions, ro_skills_taxonomy
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

CLOUDLIFT_ENV = os.environ.get("CLOUDLIFT_ENV", "local")
QDRANT_CLOUD_URL = os.environ.get(
    "QDRANT_CLOUD_URL",
    "https://fb46d143-3577-43a4-a9d5-c09ea6f2f59a.us-east-2-0.aws.cloud.qdrant.io",
)
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "")
QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))

VECTOR_SIZE = 384
COLLECTION_RESUMES = "ro_resumes"
COLLECTION_JOB_DESCRIPTIONS = "ro_job_descriptions"
COLLECTION_SKILLS_TAXONOMY = "ro_skills_taxonomy"


def is_aws() -> bool:
    return CLOUDLIFT_ENV == "aws"


# ---------------------------------------------------------------------------
# Embedding — delegates to cloudlift SentenceTransformersAdapter
# ---------------------------------------------------------------------------

def _embed(texts: list[str]) -> list[list[float]]:
    """Embed texts using cloudlift SentenceTransformersAdapter (all-MiniLM-L6-v2, 384-dim, CPU)."""
    try:
        from cloudlift.bridge.local.sentence_transformers_adapter import SentenceTransformersAdapter  # noqa: PLC0415
        return SentenceTransformersAdapter().embed_batch(texts)
    except Exception as exc:
        logger.error("[vector] embedding failed: %s", exc)
        return [[0.0] * VECTOR_SIZE for _ in texts]


# ---------------------------------------------------------------------------
# Qdrant client factory — lazy import, cloudlift pattern
# ---------------------------------------------------------------------------

def _get_client():
    """Return a QdrantClient for the current environment."""
    from qdrant_client import QdrantClient  # noqa: PLC0415
    if is_aws():
        return QdrantClient(url=QDRANT_CLOUD_URL, api_key=QDRANT_API_KEY, timeout=15, check_compatibility=False)
    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=5)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def upsert_resume(resume_id: str, user_id: str, chunks: list[str]) -> int:
    """Embed and upsert resume text chunks into ro_resumes."""
    try:
        from qdrant_client.models import PointStruct  # noqa: PLC0415
        client = _get_client()
        vectors = _embed(chunks)
        points = [
            PointStruct(
                id=abs(hash(f"{resume_id}:{i}")) % (2**53),
                vector=vectors[i],
                payload={"resume_id": resume_id, "user_id": user_id, "chunk_idx": i, "text_preview": chunks[i][:200]},
            )
            for i in range(len(chunks))
        ]
        client.upsert(collection_name=COLLECTION_RESUMES, points=points)
        logger.info("[vector] upserted %d resume chunks for resume_id=%s", len(points), resume_id)
        return len(points)
    except Exception as exc:
        logger.error("[vector] upsert_resume failed: %s", exc)
        return 0


def upsert_job_description(jd_id: str, user_id: str, title: str, company: str, text: str) -> bool:
    """Embed and upsert a job description into ro_job_descriptions."""
    try:
        from qdrant_client.models import PointStruct  # noqa: PLC0415
        client = _get_client()
        vector = _embed([text])[0]
        client.upsert(
            collection_name=COLLECTION_JOB_DESCRIPTIONS,
            points=[PointStruct(
                id=abs(hash(jd_id)) % (2**53),
                vector=vector,
                payload={"jd_id": jd_id, "user_id": user_id, "title": title, "company": company, "text_preview": text[:300]},
            )],
        )
        return True
    except Exception as exc:
        logger.error("[vector] upsert_job_description failed: %s", exc)
        return False


def search_similar_resumes(query_text: str, user_id: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Find resume chunks semantically similar to query_text for a given user."""
    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue  # noqa: PLC0415
        client = _get_client()
        vector = _embed([query_text])[0]
        response = client.query_points(
            collection_name=COLLECTION_RESUMES,
            query=vector,
            query_filter=Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]),
            limit=top_k,
            with_payload=True,
        )
        return [{"score": r.score, "payload": r.payload} for r in response.points]
    except Exception as exc:
        logger.error("[vector] search_similar_resumes failed: %s", exc)
        return []


def search_similar_jobs(query_text: str, user_id: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Find job descriptions semantically similar to query_text."""
    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue  # noqa: PLC0415
        client = _get_client()
        vector = _embed([query_text])[0]
        response = client.query_points(
            collection_name=COLLECTION_JOB_DESCRIPTIONS,
            query=vector,
            query_filter=Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]),
            limit=top_k,
            with_payload=True,
        )
        return [{"score": r.score, "payload": r.payload} for r in response.points]
    except Exception as exc:
        logger.error("[vector] search_similar_jobs failed: %s", exc)
        return []


def search_skills(query_skill: str, top_k: int = 10) -> list[dict[str, Any]]:
    """Find semantically similar skills from the taxonomy collection."""
    try:
        client = _get_client()
        vector = _embed([query_skill])[0]
        response = client.query_points(
            collection_name=COLLECTION_SKILLS_TAXONOMY,
            query=vector,
            limit=top_k,
            with_payload=True,
        )
        return [{"score": r.score, "payload": r.payload} for r in response.points]
    except Exception as exc:
        logger.error("[vector] search_skills failed: %s", exc)
        return []


def health() -> bool:
    """True if the Qdrant cluster is reachable."""
    try:
        client = _get_client()
        client.get_collections()
        return True
    except Exception:
        return False
