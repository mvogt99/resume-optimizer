# Phase 1: Foundation — Mining Runs Table + Watermarks

**Model:** Haiku (mechanical schema + CRUD, no reasoning required)
**Estimated scope:** ~120 lines backend, ~20 lines test
**Status:** NOT STARTED
**Depends on:** Nothing

---

## Objective

Create `journey_mining_runs` table to track when mining occurred, what sources were scanned, and the high-water mark per source type. This enables incremental updates in Phase 6.

## Schema

```sql
CREATE TABLE journey_mining_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    status TEXT DEFAULT 'running',        -- running | completed | failed | cancelled
    opts_json TEXT DEFAULT '{}',          -- criteria used for this run
    watermarks_json TEXT DEFAULT '{}',    -- {git: "2026-04-15", files: "2026-04-15T12:00:00", arango: "2026-04-15"}
    sources_scanned INTEGER DEFAULT 0,
    events_added INTEGER DEFAULT 0,
    events_updated INTEGER DEFAULT 0,
    events_deduplicated INTEGER DEFAULT 0,
    error_message TEXT DEFAULT '',
    FOREIGN KEY (user_id) REFERENCES users (id)
)
```

## Tasks

- [ ] **1.1** Add table to `models.py` `init_db()` CREATE TABLE block
- [ ] **1.2** Add `get_latest_watermarks(user_id)` helper — returns dict of per-source-type watermarks from most recent completed run
- [ ] **1.3** Update `start_mining()` to create a run record, pass `run_id` to `_mining_worker`
- [ ] **1.4** Update `_mining_worker()` to: (a) read previous watermarks, (b) apply as defaults when `opts` doesn't specify dates, (c) write new watermarks on completion, (d) record stats
- [ ] **1.5** Add `GET /api/journey/mining-history` route — returns last 10 runs
- [ ] **1.6** Frontend: show last mining run date + stats in JourneyMiner header

## TDD Contract

| Test | Mutation Target | Pass Criteria |
|------|----------------|---------------|
| `test_mining_run_created` | DELETE the INSERT INTO journey_mining_runs | Must fail: run record not created |
| `test_watermarks_persisted` | Remove watermarks_json UPDATE on completion | Must fail: next run sees empty watermarks |
| `test_incremental_uses_watermarks` | Remove `--since={watermark}` from git cmd | Must fail: git should only fetch post-watermark |
| `test_run_stats_accurate` | Hardcode `events_added = 0` | Must fail: stats must reflect actual count |

## Acceptance Criteria

- Mining run records survive server restart (SQLite)
- Second run with no new content adds 0 new sources
- `mining-history` returns correct chronological list
