"""Live Qdrant Cloud integration tests — requires CLOUDLIFT_ENV=aws.

Tests the three ro_* collections in mv-test-cluster (us-east-2).

Usage:
  CLOUDLIFT_ENV=aws QDRANT_API_KEY=<key> pytest tests/test_vector_integration.py -v
"""
import os
import time
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("CLOUDLIFT_ENV") != "aws",
    reason="Qdrant Cloud tests require CLOUDLIFT_ENV=aws",
)


def test_qdrant_cloud_health():
    import sys; sys.path.insert(0, ".")
    from cloudlift_vector_adapter import health
    assert health(), "Qdrant Cloud cluster unreachable"


def test_upsert_and_search_resume():
    import sys; sys.path.insert(0, ".")
    from cloudlift_vector_adapter import upsert_resume, search_similar_resumes

    uid = f"test-user-{time.time_ns()}"
    rid = f"test-resume-{time.time_ns()}"
    chunks = [
        "Python developer with 5 years experience in Django and PostgreSQL",
        "Led team of 4 engineers, improved API latency by 40%",
    ]
    count = upsert_resume(rid, uid, chunks)
    assert count == 2, f"Expected 2 chunks upserted, got {count}"

    # Qdrant Cloud requires a few seconds for vector indexing
    time.sleep(4)
    results = search_similar_resumes("Python Django backend engineer", uid, top_k=3)
    assert len(results) >= 1, "No results returned for resume search"
    assert results[0]["score"] > 0.3, f"Similarity score too low: {results[0]['score']}"
    assert results[0]["payload"]["resume_id"] == rid


def test_upsert_and_search_job_description():
    import sys; sys.path.insert(0, ".")
    from cloudlift_vector_adapter import upsert_job_description, search_similar_jobs

    uid = f"test-user-{time.time_ns()}"
    jid = f"test-jd-{time.time_ns()}"
    ok = upsert_job_description(
        jd_id=jid, user_id=uid, title="Senior Python Engineer",
        company="Acme Corp",
        text="We are looking for a senior Python engineer with Django, PostgreSQL, and AWS experience.",
    )
    assert ok, "upsert_job_description returned False"

    time.sleep(4)
    results = search_similar_jobs("Python AWS backend role", uid, top_k=3)
    assert len(results) >= 1, "No results returned for job search"
    assert results[0]["payload"]["jd_id"] == jid


def test_collections_exist():
    """All three ro_* collections must exist in the cluster."""
    import sys; sys.path.insert(0, ".")
    from cloudlift_vector_adapter import _get_client, COLLECTION_RESUMES, COLLECTION_JOB_DESCRIPTIONS, COLLECTION_SKILLS_TAXONOMY
    client = _get_client()
    names = {c.name for c in client.get_collections().collections}
    for expected in (COLLECTION_RESUMES, COLLECTION_JOB_DESCRIPTIONS, COLLECTION_SKILLS_TAXONOMY):
        assert expected in names, f"Collection {expected!r} missing from cluster"
