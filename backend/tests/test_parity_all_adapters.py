"""Parity test suite — same CloudLift contract, both adapter backends.

Each test class covers one service contract. Run in both environments to confirm
parity: same input produces equivalent output (within defined tolerance).

  Local (CLOUDLIFT_ENV=local or unset):
    CLOUDLIFT_ENV=local PYTHONPATH=. pytest tests/test_parity_all_adapters.py -v

  AWS (all live services):
    source ~/.zshrc
    CLOUDLIFT_ENV=aws AWS_REGION=us-east-1 PYTHONPATH=. \\
      pytest tests/test_parity_all_adapters.py -v

Parity baseline (Phase 4):
  local 5/5 contracts | aws 5/5 contracts

Contracts covered:
  ILLMInference       — vLLM (local) | Bedrock (aws)
  IRelationalDatabase — SQLite (local) | RDS PostgreSQL (aws)
  IGraphDatabase      — ArangoDB (local) | DynamoDB (aws)
  IMessageQueue       — Artemis STOMP (local) | SQS FIFO (aws)
  IVectorSearch       — Qdrant (local) | OpenSearch (aws)
  IObjectStorage      — N/A: resume-optimizer does not use blob storage
"""
from __future__ import annotations

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

ENV = os.environ.get("CLOUDLIFT_ENV", "local")
IS_AWS = ENV == "aws"
_UID = f"parity-{int(time.time())}"


# ---------------------------------------------------------------------------
# Availability probes (local services only)
# ---------------------------------------------------------------------------

def _vllm_up() -> bool:
    try:
        import httpx
        return httpx.get("http://localhost:8021/v1/models", timeout=3).status_code == 200
    except Exception:
        return False


def _qdrant_up() -> bool:
    try:
        import httpx
        return httpx.get("http://localhost:6333/healthz", timeout=3).status_code == 200
    except Exception:
        return False


def _arango_up() -> bool:
    try:
        import httpx
        return httpx.get("http://localhost:8529/_api/version", timeout=3).status_code == 200
    except Exception:
        return False


def _artemis_up() -> bool:
    """Probe Artemis STOMP port."""
    import socket
    try:
        s = socket.create_connection(("localhost", 61613), timeout=2)
        s.close()
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Contract 1: ILLMInference
#   Local:  RTX 5090 vLLM via smart_llm.call_direct()
#   AWS:    Bedrock (Claude Haiku) via cloudlift_llm_adapter.call_bedrock()
#   Contract: call(prompt) → non-empty string
# ---------------------------------------------------------------------------

class TestLLMInferenceParity:

    def _call(self, prompt: str, max_tokens: int = 128) -> str | None:
        if IS_AWS:
            from cloudlift_llm_adapter import call_bedrock
            return call_bedrock(prompt, task_type="analysis", max_tokens=max_tokens)
        if not _vllm_up():
            pytest.skip("vLLM not running at localhost:8021")
        from smart_llm import call_direct
        return call_direct(prompt, max_tokens=max_tokens)

    @staticmethod
    def _strip_think(text: str) -> str:
        """Remove <think>...</think> blocks from chain-of-thought models."""
        import re
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    def test_inference_returns_nonempty_string(self):
        result = self._call("Respond with exactly one word: yes")
        assert result is not None
        visible = self._strip_think(result)
        assert isinstance(visible, str) and visible, (
            f"Expected non-empty str (after stripping think tags), got {result!r}"
        )

    def test_inference_reflects_prompt_content(self):
        """Model must process the prompt and reach a numeric answer."""
        result = self._call("What is 2 + 2? Reply with only the number.")
        assert result is not None
        visible = self._strip_think(result)
        assert "4" in visible, (
            f"Expected '4' in visible response, got {visible!r} (full: {result!r})"
        )

    def test_adapter_flag_matches_env(self):
        from cloudlift_llm_adapter import is_aws
        assert is_aws() is IS_AWS, (
            f"is_aws()={is_aws()} but CLOUDLIFT_ENV={ENV!r}"
        )


# ---------------------------------------------------------------------------
# Contract 2: IRelationalDatabase
#   Local:  SQLite (models.DB_PATH / in-process)
#   AWS:    RDS PostgreSQL (cloudlift_db_adapter + db_engine)
#   Contract: CREATE TABLE → INSERT → SELECT → DELETE → DROP
# ---------------------------------------------------------------------------

class TestRelationalDatabaseParity:

    @pytest.fixture(scope="class")
    def conn(self):
        if IS_AWS:
            import cloudlift_db_adapter
            url = cloudlift_db_adapter.resolve_database_url()
            assert url.startswith("postgresql://"), f"Expected RDS URL, got {url!r}"
            from db_engine import get_pg_connection_raw
            c = get_pg_connection_raw(url)
        else:
            import sqlite3
            c = sqlite3.connect(":memory:")
        yield c
        c.close()

    def test_select_one(self, conn):
        row = conn.execute("SELECT 1").fetchone()
        assert row is not None
        assert row[0] == 1

    def test_create_insert_select_delete(self, conn):
        tbl = f"parity_test_{_UID.replace('-', '_')}"
        try:
            conn.execute(f"CREATE TABLE {tbl} (id TEXT PRIMARY KEY, val TEXT)")
            conn.execute(f"INSERT INTO {tbl} VALUES (?, ?)", (_UID, "hello"))
            rows = conn.execute(f"SELECT val FROM {tbl} WHERE id = ?", (_UID,)).fetchall()
            assert rows, "INSERT then SELECT returned no rows"
            assert rows[0][0] == "hello"
            conn.execute(f"DELETE FROM {tbl} WHERE id = ?", (_UID,))
            rows_after = conn.execute(f"SELECT val FROM {tbl} WHERE id = ?", (_UID,)).fetchall()
            assert not rows_after, "Row still present after DELETE"
        finally:
            try:
                conn.execute(f"DROP TABLE IF EXISTS {tbl}")
            except Exception:
                pass

    def test_parameterized_query_prevents_injection(self, conn):
        result = conn.execute("SELECT ?", ("safe_value",)).fetchone()
        assert result[0] == "safe_value"


# ---------------------------------------------------------------------------
# Contract 3: IGraphDatabase
#   Local:  ArangoDB (get_graph_client → ArangoClient)
#   AWS:    DynamoDB  (get_graph_client → DynamoDBGraphAdapter)
#   Contract: upsert_vertex → get_vertex → upsert_edge → get_neighbors → delete
# ---------------------------------------------------------------------------

class TestGraphDatabaseParity:

    @pytest.fixture(scope="class")
    def graph(self):
        if IS_AWS:
            from arango_client import get_graph_client
            return get_graph_client()
        if not _arango_up():
            pytest.skip("ArangoDB not running at localhost:8529")
        from arango_client import get_graph_client
        return get_graph_client()

    def test_upsert_and_get_vertex(self, graph):
        vid = graph.upsert_vertex(
            "ro_client_projects",
            {"name": f"Parity Corp {_UID}", "user_id": _UID, "folder_id": "f-parity"},
            key_source=f"parity-proj-{_UID}",
        )
        assert "/" in vid, f"Expected collection/key format, got {vid!r}"
        collection, key = vid.split("/", 1)
        doc = graph.get_vertex(collection, key)
        assert doc is not None, f"get_vertex returned None for {vid}"
        assert doc.get("name") == f"Parity Corp {_UID}"

    def test_upsert_edge_and_get_neighbors(self, graph):
        v1 = graph.upsert_vertex(
            "ro_client_projects",
            {"name": f"Parent {_UID}", "user_id": _UID, "folder_id": "fp"},
            key_source=f"parity-parent-{_UID}",
        )
        v2 = graph.upsert_vertex(
            "ro_client_projects",
            {"name": f"Child {_UID}", "user_id": _UID, "folder_id": "fc"},
            key_source=f"parity-child-{_UID}",
        )
        graph.upsert_edge(
            "ro_project_edges",
            from_id=v1,
            to_id=v2,
            data={"rel": "parity-test"},
        )
        neighbors = graph.get_neighbors(v1, "ro_project_edges", direction="OUTBOUND")
        neighbor_ids = [n.get("_id", "") or n.get("id", "") for n in neighbors]
        assert any(v2 in nid for nid in neighbor_ids), (
            f"Expected {v2!r} among OUTBOUND neighbors {neighbor_ids}"
        )

    def test_delete_vertex(self, graph):
        vid = graph.upsert_vertex(
            "ro_client_projects",
            {"name": f"Ephemeral {_UID}", "user_id": _UID, "folder_id": "fe"},
            key_source=f"parity-delete-{_UID}",
        )
        col, key = vid.split("/", 1)
        deleted = graph.delete_vertex(col, key)
        assert deleted, "delete_vertex returned False"
        doc_after = graph.get_vertex(col, key)
        assert doc_after is None, "Vertex still present after delete"


# ---------------------------------------------------------------------------
# Contract 4: IMessageQueue
#   Local:  Artemis STOMP (bus_client.ResumeAnalysisBus — publisher only)
#   AWS:    SQS FIFO (cloudlift_queue_adapter — bidirectional)
#   Contract:
#     Local: publish_chunk returns True + bus.is_available() (worker-side consume
#            is out of scope for unit parity; Artemis is fire-and-forget dispatch)
#     AWS:   publish_chunk → receive_chunks → body matches → delete (full round-trip)
# ---------------------------------------------------------------------------

class TestMessageQueueParity:

    def _drain_sqs(self, max_iter: int = 30) -> None:
        from cloudlift_queue_adapter import receive_chunks, delete_message
        for _ in range(max_iter):
            msgs = receive_chunks(max_messages=10, wait_seconds=1)
            if not msgs:
                break
            for m in msgs:
                delete_message(m["receipt_handle"])

    def test_queue_available(self):
        if IS_AWS:
            import cloudlift_queue_adapter
            assert cloudlift_queue_adapter.is_aws(), "Expected is_aws()=True with CLOUDLIFT_ENV=aws"
        else:
            if not _artemis_up():
                pytest.skip("Artemis STOMP not available at localhost:61613")
            from bus_client import ResumeAnalysisBus
            bus = ResumeAnalysisBus()
            assert bus.is_available(), "ResumeAnalysisBus not connected to Artemis"

    def test_publish_chunk(self):
        unique_id = f"{_UID}-{time.time_ns()}"

        if IS_AWS:
            from cloudlift_queue_adapter import publish_chunk
            sent = publish_chunk(
                doc_id=unique_id,
                chunk_idx=0,
                chunk_text="Parity test: Python engineer with AWS experience",
                context="resume",
                extractors=["tech"],
            )
            assert sent, "publish_chunk returned False"
        else:
            if not _artemis_up():
                pytest.skip("Artemis STOMP not available at localhost:61613")
            from bus_client import ResumeAnalysisBus
            bus = ResumeAnalysisBus()
            sent = bus.publish_chunk(
                doc_id=unique_id,
                chunk_idx=0,
                chunk_text="Parity test: Python engineer with AWS experience",
                context="resume",
                extractors=["tech"],
            )
            assert sent, "bus.publish_chunk returned False"

    def test_publish_receive_delete_round_trip(self):
        """Full round-trip: publish → receive → body verified → delete.

        AWS only: SQS supports consumer-side polling in the same process.
        Artemis is designed for worker-process consumption; round-trip is
        validated by the end-to-end test suite instead.
        """
        if not IS_AWS:
            pytest.skip("Round-trip receive requires CLOUDLIFT_ENV=aws (SQS)")

        from cloudlift_queue_adapter import publish_chunk, receive_chunks, delete_message
        self._drain_sqs()

        unique_id = f"{_UID}-rt-{time.time_ns()}"
        sent = publish_chunk(
            doc_id=unique_id,
            chunk_idx=0,
            chunk_text="Parity round-trip: senior Django developer",
            context="resume",
            extractors=["tech"],
        )
        assert sent, "publish_chunk returned False"

        messages = receive_chunks(max_messages=1, wait_seconds=10)
        assert messages, "No messages received from SQS after publish"

        body = messages[0]["body"]
        assert body["doc_id"] == unique_id, (
            f"doc_id mismatch: expected {unique_id!r}, got {body.get('doc_id')!r}"
        )
        assert body["chunk_idx"] == 0
        assert "Parity" in body["chunk_text"]
        delete_message(messages[0]["receipt_handle"])


# ---------------------------------------------------------------------------
# Contract 5: IVectorSearch
#   Local:  Qdrant (localhost:6333) via cloudlift_search_adapter → cloudlift_vector_adapter
#   AWS:    OpenSearch (managed domain) via cloudlift_search_adapter
#   Contract: upsert_resume → search_similar_resumes → recall ≥ 1 result with score > 0.3
#             upsert_job_description → search_similar_jobs → same recall guarantee
# ---------------------------------------------------------------------------

def _ensure_qdrant_collections() -> None:
    """Create Qdrant collections if they don't exist (local only)."""
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams

    VECTOR_SIZE = 384
    client = QdrantClient(host="localhost", port=6333, timeout=5)
    existing = {c.name for c in client.get_collections().collections}
    for name in ("ro_resumes", "ro_job_descriptions", "ro_skills_taxonomy"):
        if name not in existing:
            client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )


class TestVectorSearchParity:

    def _check_local_prereqs(self) -> None:
        if not _qdrant_up():
            pytest.skip("Qdrant not running at localhost:6333")
        _ensure_qdrant_collections()

    def test_upsert_and_search_resume(self):
        if not IS_AWS:
            self._check_local_prereqs()

        from cloudlift_search_adapter import upsert_resume, search_similar_resumes

        rid = f"parity-resume-{_UID}"
        chunks = [
            f"Parity test resume — Python developer with 5 years Django experience [{_UID}]",
            "Led cloud migration from on-premises to AWS, reduced latency by 40%",
        ]
        count = upsert_resume(rid, _UID, chunks)
        assert count == len(chunks), f"Expected {len(chunks)} chunks upserted, got {count}"

        # Allow indexing lag (OpenSearch ~1s; Qdrant near-instant)
        time.sleep(3 if IS_AWS else 1)

        results = search_similar_resumes("Python Django backend engineer AWS", _UID, top_k=5)
        assert len(results) >= 1, (
            f"Expected ≥1 search result, got {len(results)}"
        )
        assert results[0]["score"] > 0.3, (
            f"Top result score too low: {results[0]['score']:.3f} (threshold 0.3)"
        )

    def test_upsert_and_search_job_description(self):
        if not IS_AWS:
            self._check_local_prereqs()

        from cloudlift_search_adapter import upsert_job_description, search_similar_jobs

        jid = f"parity-jd-{_UID}"
        ok = upsert_job_description(
            jd_id=jid,
            user_id=_UID,
            title="Senior Python Engineer",
            company="Parity Labs",
            text=f"Looking for a senior Python/Django engineer with AWS and PostgreSQL experience [{_UID}]",
        )
        assert ok, "upsert_job_description returned False"

        time.sleep(3 if IS_AWS else 1)

        results = search_similar_jobs("Python AWS backend role senior", _UID, top_k=5)
        assert len(results) >= 1, (
            f"Expected ≥1 search result, got {len(results)}"
        )
        assert results[0]["score"] > 0.3, (
            f"Top result score too low: {results[0]['score']:.3f} (threshold 0.3)"
        )

    def test_search_adapter_health(self):
        if not IS_AWS:
            if not _qdrant_up():
                pytest.skip("Qdrant not running at localhost:6333")
        from cloudlift_search_adapter import health
        assert health(), "cloudlift_search_adapter.health() returned False"
