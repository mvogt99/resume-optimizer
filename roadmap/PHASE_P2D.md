# Phase P2-D: requests to httpx Migration

**Branch:** `feature/ro-phase-P2D-httpx-migration`
**Model:** Sonnet
**Addresses:** Finding F6 (R6)
**Status:** PENDING
**Estimated tests:** 8-10

---

## Objective

Migrate from synchronous `requests` to `httpx` with connection pooling. Gateway
completed this in Phase 24B. Resume optimizer still blocks Flask workers during
300s inference calls.

## Tasks

### P2-D.1: Replace requests in smart_llm.py (Sonnet)
- **Test first:** Tests asserting httpx.Client used with connection pooling
- **Implementation:**
  - Replace `requests.post()` with `httpx.Client()` + `.post()`
  - Configure connection pool: `max_connections=10`, `max_keepalive_connections=5`
  - Maintain same timeout config (SELECT_TIMEOUT, INFERENCE_TIMEOUT, etc.)
  - Maintain same fallback behavior
- **Files:** `smart_llm.py`

### P2-D.2: Replace requests in journey_miner.py (Sonnet)
- **Test first:** Tests asserting harness calls use httpx
- **Implementation:** Replace `requests.post(HARNESS_URL, ...)` with httpx
- **Files:** `journey_miner.py`

### P2-D.3: Audit remaining requests usage (Sonnet)
- Grep for any other `import requests` or `requests.` usage
- Migrate remaining call sites

### P2-D.4: Update requirements.txt (Sonnet)
- Add `httpx>=0.27`
- Remove `requests` if no other module needs it (check carefully)
- Keep `requests` if third-party deps need it (e.g., python-arango)

## Acceptance Criteria

- [ ] Zero `requests.post()` or `requests.get()` in resume-optimizer code
- [ ] httpx.Client with connection pooling configured
- [ ] Same timeout and fallback behavior preserved
- [ ] requirements.txt updated
- [ ] All existing tests pass

## User Gate P2-D

**Present:** Import audit before/after, connection pool config, test results.
