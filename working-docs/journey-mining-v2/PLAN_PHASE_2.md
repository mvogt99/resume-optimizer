# Phase 2: ArangoDB Embedding Pipeline

**Model:** ↑ SWAP TO SONNET (architectural integration, embedding pipeline design)
**Estimated scope:** ~200 lines new module, ~80 lines test
**Status:** NOT STARTED
**Depends on:** Phase 1 (watermarks for incremental embed tracking)

---

## Objective

Build an ArangoDB-native embedding pipeline using the gateway's existing `all-MiniLM-L6-v2` model. Store 384D vectors directly in ArangoDB documents. Replaces Qdrant as the vector store for journey operations.

## Architecture

```
EmbeddingService (gateway, existing)
    ↓ embed_batch(texts) → List[List[float]]

ArangoEmbeddingService (new, backend/arango_embedding_service.py)
    ↓ embed_and_store(collection, doc_key, text)
    ↓ find_similar(collection, query_text, threshold=0.92, limit=10)
    ↓ batch_embed_collection(collection, text_field, embedding_field)

ArangoDB document:
    { _key: "...", content: "...", embedding_384: [0.01, ...], embedded_at: "..." }
```

## Design Decisions

1. **Embedding field**: `embedding_384` (typed name prevents model-change confusion)
2. **Similarity search**: AQL with cosine distance (ArangoDB 3.12+ native, or manual dot-product)
3. **Batch size**: 64 texts per `embed_batch()` call (GPU memory safe)
4. **Cache**: Reuse gateway EmbeddingService cache (MD5-keyed, 10K max)
5. **Fallback**: If embedding service unavailable, store `null`, mark `embedded_at: null`
6. **Reference implementation**: Qdrant pipeline in `gateway/app/services/embedding_service.py` — use as pattern for ArangoDB adapter

## Key AQL — Cosine Similarity Search

```aql
FOR doc IN @@collection
  FILTER doc.embedding_384 != null
  LET sim = (
    SUM(FOR i IN 0..LENGTH(doc.embedding_384)-1
      RETURN doc.embedding_384[i] * @query[i])
  ) / (
    SQRT(SUM(FOR v IN doc.embedding_384 RETURN v*v)) *
    SQRT(SUM(FOR v IN @query RETURN v*v))
  )
  FILTER sim >= @threshold
  SORT sim DESC
  LIMIT @limit
  RETURN { doc, similarity: sim }
```

(Verify ArangoDB version supports this pattern; fallback: Python-side cosine if needed)

## Tasks

- [ ] **2.1** Create `backend/arango_embedding_service.py` — wraps gateway EmbeddingService via HTTP or direct import
- [ ] **2.2** Add `embedding_384` field handling to `arango_client.py` — upsert accepts optional embedding
- [ ] **2.3** Write `find_similar()` AQL similarity search method
- [ ] **2.4** Write `batch_embed_collection()` — iterate unembedded docs, embed in batches of 64, update in place
- [ ] **2.5** Add `POST /api/journey/embed` route — triggers batch embedding (background job)
- [ ] **2.6** Verify ArangoDB version, test AQL cosine performance on 12K docs

## TDD Contract

| Test | Mutation Target | Pass Criteria |
|------|----------------|---------------|
| `test_embed_stores_vector` | Remove embedding_384 from upsert | Must fail: doc must have 384D vector |
| `test_find_similar_returns_matches` | Change threshold 0.92→0.01 | Must fail: returns too many |
| `test_find_similar_excludes_below` | Set threshold to 0.99 | Must fail if expecting moderate matches |
| `test_batch_skips_already_embedded` | Remove `embedded_at != null` filter | Must fail: re-embedding wastes compute |
| `test_embedding_null_on_service_down` | Mock service unavailable | Must pass: graceful fallback |

## Acceptance Criteria

- 384D vectors stored in ArangoDB documents
- Cosine similarity search returns correct top-K
- Batch embedding: 12K sources in < 5 minutes on RTX 5090
- Embedding service failure doesn't crash pipeline

**After Phase 2 tests pass:** ↓ SWAP BACK TO HAIKU
