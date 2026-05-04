# Phase 3.1 Design: Replace Qdrant FTAL Path with ArangoDB

**Date:** 2026-04-20
**Author:** Claude Sonnet 4.6 (architecture design task)
**Status:** APPROVED — proceed to TDD + implementation

---

## Problem Statement

`_mine_ftal_history()` in `backend/journey_miner_enrichment_mixin.py` currently reads from
Qdrant's `hybrid_ai_learnings` collection. Qdrant was decommissioned 2026-03-19. The method
still runs on every mining job but captures zero new records — it only returns data from the
frozen Qdrant snapshot already in SQLite (500 records tagged `ftal_history`).

Gap: 6,325 April FTAL learnings + 55,303 March learnings in ArangoDB are invisible to the
journey system. The method silently returns 0 for new records every time.

---

## Data Source Selection

### Candidate Collections

| Collection | Records | Has Dates | Has FTAL Scores | Verdict |
|------------|---------|-----------|-----------------|---------|
| `learnings` | 66,988 | ✅ `created_at` | ✅ f/t/a/l scores | **PRIMARY** |
| `task_results` | 9,347 | ✅ ISO datetime | ❌ (pass/fail only) | SECONDARY (deferred) |
| `ftal_gap_history` | 7,771 | Unix epoch only | ✅ gap field | SECONDARY (deferred) |
| `harness_results` | 0 | N/A | N/A | EMPTY — skip |
| `hybrid_ai_learnings` | 0 | N/A | N/A | DEAD — old Qdrant ArangoDB sync |

### Decision: `learnings` collection is the replacement target

**Rationale:**
1. `learnings` replaces Qdrant `hybrid_ai_learnings` post-decommission — it IS the same data, migrated forward
2. Has complete FTAL scores (f_score, t_score, a_score, l_score) — richer than the Qdrant payload
3. `created_at` field is ISO format — reliable date filtering without epoch conversion
4. 6,325 April entries alone exceed the 500 frozen Qdrant entries we currently hold

---

## Schema Mapping

### Source: `learnings` document
```json
{
  "_key": "learn_async_subprocess_20260228",
  "title": "Use asyncio.create_subprocess_exec ...",
  "content": "Never use subprocess.run() ...",
  "learning_type": "architecture_pattern",
  "domain": "async",
  "f_score": 40,
  "t_score": 40,
  "a_score": 9,
  "l_score": 9,
  "tags": ["async", "subprocess"],
  "created_at": "2026-02-28",
  "source": "ftal_harness"
}
```

### Target: `_store_source()` call
```python
self._store_source(
    source_type="ftal_history",
    source_path=f"arangodb/learnings/{doc['_key']}",
    content_hash=sha256(f"ftal-arango:{doc['_key']}:{content[:100]}"),
    title=f"FTAL: {learning_type} — {domain}",
    content_preview=content[:500],
    full_text=content,
    classification="ftal_task",
    event_date=created_at[:10],
    metadata={
        "learning_type": learning_type,
        "domain": domain,
        "source_system": "ftal_harness",
        "f_score": f_score,
        "t_score": t_score,
        "a_score": a_score,
        "l_score": l_score,
        "gap": 100 - f_score - t_score - a_score - l_score
    },
    user_id=user_id,
)
```

---

## Implementation Design

### Connection Strategy
- **Library**: python-arango (already in `backend/requirements.txt`)
- **Pattern**: Same as `arango_client.py` — `from arango import ArangoClient as _ArangoClient`
- **Host**: `http://localhost:8529` (or env var `ARANGO_HOST`, defaulting to same)
- **Database**: `hybrid_ai`
- **Credentials**: `root` / `hybrid_ai_root` (or env var `ARANGO_PASSWORD`)

### Watermark Strategy
The `_mine_ftal_history()` has no dedicated watermark. Approach:
1. Query existing SQLite `journey_sources` for `MAX(event_date)` where `source_type='ftal_history'`
2. Use that date as `since_date` filter (AQL: `FILTER doc.created_at >= @since`)
3. Fallback: if no existing ftal_history records, use `"1900-01-01"` (mine everything)
4. Cap at 2000 records per run to avoid overwhelming mining jobs

This is incremental by construction: each mining run only captures new learnings since last run.

### AQL Query
```aql
FOR doc IN learnings
  FILTER doc.created_at >= @since
  SORT doc.created_at ASC
  LIMIT 2000
  RETURN doc
```

### Error Handling
- `ImportError` (python-arango not installed): log warning, return 0
- `ArangoServerError` (server down): log warning, return 0
- Any unexpected exception: log warning, return 0

All failures are graceful — same pattern as existing `_mine_ftal_history()`.

---

## File Impact

**File**: `backend/journey_miner_enrichment_mixin.py`
**Current lines**: 291
**Estimated lines after change**: ~340 (291 + ~50 for new `_mine_ftal_history`)
**Limit**: 500 lines — **SAFE**

**Change**: Replace `_mine_ftal_history()` method body entirely.
The method signature (`def _mine_ftal_history(self, user_id=0)`) stays the same — callers in `journey_miner.py` line 156 are unaffected.

---

## Test Design (for delegation in 3.2)

### Test file: `backend/tests/test_journey_ftal_arangodb.py`

**Test 1: Happy path — records after watermark are stored**
- Mock ArangoDB response with 3 learnings dated after watermark
- Assert `_store_source()` called 3 times
- Assert source_type="ftal_history" in each call
- Assert source_path starts with "arangodb/learnings/"

**Test 2: Watermark filtering — records before watermark are NOT stored**
- Mock ArangoDB response with learnings dated BEFORE watermark
- Assert `_store_source()` NOT called (returns 0)

**Test 3: ArangoDB unavailable — graceful degradation**
- Mock `ArangoClient` to raise `ImportError` or `Exception`
- Assert method returns 0 (no exception propagated)
- Assert warning was logged

**Test 4: Empty collection — returns 0**
- Mock ArangoDB response with empty list
- Assert returns 0, no `_store_source()` calls

**Mutation verification targets:**
- Break AQL `FILTER doc.created_at >= @since` → Test 2 must FAIL (old records get stored)
- Break `content_hash` computation → SHA-256 dedup stops working; Test 1 still passes but mutation caught via hash assertion
- Break `source_path` prefix → Test 1 fails on path assertion

---

## Migration Note

The 500 existing `ftal_history` records in SQLite came from the frozen Qdrant snapshot.
They have source_path format `hybrid_ai_learnings/{uuid}`. New records will have
`arangodb/learnings/{key}`. The SHA-256 hash scheme ensures no duplicates between the two
formats — different paths produce different hashes, so if any records overlap in content,
the hash differs and both are stored (acceptable: one for each source system).

---

## Approval

- [x] Data source identified and schema validated (live introspection)
- [x] python-arango confirmed available in backend requirements
- [x] 6,325 April learnings confirmed available for capture
- [x] Watermark strategy handles incremental runs correctly
- [x] File size impact within 500-line limit
- [x] No downstream callers affected (method signature preserved)
- [x] Test design covers 4 behaviors + 3 mutation targets

**PROCEED TO IMPLEMENTATION (Phase 3.2–3.5)**
