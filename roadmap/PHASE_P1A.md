# Phase P1-A: SQLite Hardening

**Branch:** `feature/ro-phase-P1A-sqlite-hardening`
**Model:** Sonnet
**Addresses:** Finding F4 (R4)
**Status:** PENDING
**Estimated tests:** 10-15

---

## Objective

Harden SQLite for concurrent agent access. Enable WAL mode, replace all raw
`sqlite3.connect()` with `get_db()` context manager, add busy timeout.

## Tasks

### P1-A.1: Enable WAL mode and busy timeout (Sonnet)
- **Test first:** Test asserting `PRAGMA journal_mode` returns `wal` after init_db()
- **Test first:** Test asserting `PRAGMA busy_timeout` returns 5000
- **Implementation:** Add to `models.py` `init_db()`:
  ```
  PRAGMA journal_mode=WAL
  PRAGMA busy_timeout=5000
  ```
- **Files:** `models.py`

### P1-A.2: Audit and replace raw sqlite3.connect() calls (Sonnet)
- **Test first:** grep-based test asserting zero `sqlite3.connect(DB_PATH)` outside models.py
- **Implementation:** Replace all raw connections with `get_db()`:
  - `context_enrichment.py` (6 functions)
  - `journey_synthesizer.py` (3 functions)
  - `journey_miner.py` (multiple methods)
  - `agents/cover_letter.py` (3 methods)
  - `agents/career_advisor.py`
  - `agents/interview_coach.py`
  - `deep_profile.py`
  - `campaign_interview.py`
  - `post_generator.py`
  - `experience_chat.py`
- **Validation:** Full test suite passes, no `database is locked` errors

### P1-A.3: Concurrent write stress test (Sonnet)
- **Test:** Spawn 4 threads each inserting 50 rows simultaneously
- **Validation:** All 200 rows present, no errors, no data corruption

## Acceptance Criteria

- [ ] WAL mode enabled
- [ ] busy_timeout = 5000ms
- [ ] Zero raw `sqlite3.connect(DB_PATH)` outside models.py
- [ ] Concurrent write stress test passes
- [ ] All existing tests still pass

## User Gate P1-A

**Present:** Raw connection count before/after, WAL mode proof, concurrent test results.
