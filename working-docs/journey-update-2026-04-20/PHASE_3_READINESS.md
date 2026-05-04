# Phase 3 Readiness — Code Changes for FTAL/ArangoDB

**Prepared:** 2026-04-20
**Status:** Ready for Phase 3 execution (pending Phase 2 completion)

---

## Phase 3 Overview

**Objective:** Replace dead `_mine_ftal_history()` Qdrant path with ArangoDB/gateway source.

**Key Files to Modify:**
- `backend/journey_miner_enrichment_mixin.py` — Contains the legacy `_mine_ftal_history()` method
- New test file: `backend/tests/test_journey_ftal_arangodb.py` — TDD approach

---

## Current State Assessment

### Legacy FTAL History Mining (Current - Qdrant-based)

**Location:** `backend/journey_miner_enrichment_mixin.py`
**Current implementation:** `_mine_ftal_history()` method that reads from Qdrant

**Status:** ⚠️ DEAD CODE
- Qdrant was decommissioned 2026-03-19
- Method still exists but cannot execute
- No tests currently cover this path

### New ArangoDB/Gateway FTAL Source

**Data available in gateway ArangoDB:**
- Collection: `harness_runs` (from gateway logs)
- Fields: execution_id, model, timestamp, tokens_in, tokens_out, gap, ftal_score
- Accessible via: Gateway API → `/api/harness/history` or direct ArangoDB query

**Gateway service:** `http://localhost:8000`
**ArangoDB service:** `http://localhost:8529` (creds: root/hybrid_ai_root)

---

## Phase 3 Micro-Tasks

### 3.1 Design: Identify FTAL data source in gateway ArangoDB
**Model:** Sonnet (architecture design)
**Deliverable:** Design document specifying:
- Query strategy (gateway API vs direct ArangoDB)
- Data mapping (harness_runs → journey_events structure)
- Deduplication strategy (by execution_id)
- Date range filtering (from latest watermark)

### 3.2-3.4 TDD: Write test → Implement → Run test
**Model:** Haiku (coding)
**Approach:**
1. Write failing test: `test_mine_ftal_history_arangodb()`
2. Implement: New `_mine_ftal_history()` that queries ArangoDB
3. Run test: Verify passes

### 3.5 Mutation Verification
**Approach:**
- Break ArangoDB query (remove WHERE clause) → test fails ✓
- Break date filtering → test fails ✓
- Break deduplication → test fails ✓

### 3.6-3.8 Integration & Quality
- Integration test against live ArangoDB (no mocks)
- Verify file under 500 lines
- Full journey test suite passes

### 3.9 Brutal Self-Review
**Model:** Sonnet (review)
**Gate:** FTAL gap < 10, zero P0 issues

---

## Expected Outcomes

| Metric | Target | Notes |
|--------|--------|-------|
| New FTAL sources captured | 50-200 | From gateway harness_runs since 2026-03-10 |
| Journey events increase | 50-200 | Mapped from FTAL executions |
| Test count | 3-5 | TDD: 1 unit + 1 integration + mutations |
| FTAL gap | < 10 | Design + code quality |
| File size | < 500 lines | Modular architecture |

---

## Dependency on Phase 2

✋ **Waiting for Phase 2 mining completion**

Once Phase 2 completes:
1. Post-mine metrics will show latest event_date = 2026-04-20
2. Source counts will be finalized
3. Phase 3 can begin ArangoDB mining integration

**Current mining job:** 3fd324b1-3f88-4546-8ede-52f47c42e22e (in narrative generation phase)

---

## Pre-Phase 3 Checklist

- [x] Gateway ArangoDB confirmed accessible
- [x] Backend health verified
- [x] Test infrastructure ready
- [x] Design scope clear
- [ ] Phase 2 mining complete (BLOCKING)

---

**Next:** Phase 3 begins after Phase 2 completes and post-mine metrics recorded.
