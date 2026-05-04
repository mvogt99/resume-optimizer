# AI Journey Update Plan — Phases 0-3

Companion to `JOURNEY_UPDATE_PLAN_2026-04-20.md` (entry + protocols) and the JSON state file. Read SS3.3 (quality gate), SS3.4 (reassessment), and SS3.5 (iteration) before starting any phase.

---

## Phase 0 — Preflight & Service Verification

**Objective.** Confirm all required services are running, validate baseline journey data state, create database backup, establish the working directory structure for progress tracking.

**Required model:** Haiku (default). No model switches in this phase.

**Pre-phase reassessment.** SS3.4 baseline only — first phase, no prior phases to audit.

### Deliverables

1. `progress/phase_0_PREFLIGHT.md` — service status, data counts, backup confirmation.
2. `backend/database.db.bak.2026-04-20` — SQLite backup before any mutations.
3. `progress/` directory created for tracking.

### Micro-tasks

| # | Task | task_type | Model | Notes |
|---|---|---|---|---|
| 0.1 | Run `./ro status` — verify backend :5000 and frontend :3000 running | ops | Haiku | If not running, run `./ro start` and wait 10s |
| 0.2 | Verify gateway :8000 health | ops | Haiku | `curl -s http://localhost:8000/health` |
| 0.3 | Verify vLLM :8021 model loaded | ops | Haiku | `curl -s http://localhost:8021/v1/models` |
| 0.4 | Verify PersonaForge :8090 active | ops | Haiku | `curl -s http://localhost:8090/status` |
| 0.5 | Verify ArangoDB :8529 accessible | ops | Haiku | Python `from arango import ArangoClient; db.version()` |
| 0.6 | Verify FTAL harness responds | ops | Haiku | `curl -s http://localhost:8000/api/harness/stats` |
| 0.7 | Record baseline journey data counts (events, sources, narratives) | ops | Haiku | SQLite queries against `backend/database.db` |
| 0.8 | Create database backup | ops | Haiku | `cp backend/database.db backend/database.db.bak.2026-04-20` |
| 0.9 | Create progress directory | ops | Haiku | `mkdir -p working-docs/journey-update-2026-04-20/progress` |
| 0.10 | Write `progress/phase_0_PREFLIGHT.md` with all verification results | docs | Haiku | |
| 0.11 | Update JSON companion `current_state` | ops | Haiku | |

### Quality gate

- All services responding (smoke-pass).
- Baseline data counts match analysis expectations (10,316 events, 12,086 sources, 100 narratives).
- Database backup exists and is non-zero size.
- No mutations or tests needed — this is purely operational.

### Exit criteria

All services confirmed running; baseline documented; backup created; user approves Phase 1 start.

### PersonaForge learnings to save

Service startup behavior; `./ro` vs docker-compose decision rationale; any port conflicts discovered.

---

## Phase 1 — Data Preparation: Governance & SESSION_STATE

**Objective.** Update `roadmap/SESSION_STATE.json` with April 2026 grade history entries so the governance mining method captures recent quality milestones. Prepare any additional data files needed for incremental mining.

**Required model:** Haiku (default). No model switches.

**Pre-phase reassessment.**
- SS3.4 baseline.
- Phase 0 backup confirmed present.
- `roadmap/SESSION_STATE.json` exists and is readable.

### Deliverables

1. Updated `roadmap/SESSION_STATE.json` with April grade history entries.
2. `progress/phase_1_DATA_PREP.md` documenting what was added and why.

### Micro-tasks

| # | Task | task_type | Model | Notes |
|---|---|---|---|---|
| 1.1 | Read current `roadmap/SESSION_STATE.json` — note existing grade_history entries | ops | Haiku | Understand structure before modifying |
| 1.2 | Gather April milestone data from git log | ops | Haiku | Key dates: Phase D (Apr 13), Phase E (Apr 13), Phase F (Apr 14), 6a-6d (Apr 15), Roadmap close (Apr 20) |
| 1.3 | Gather gateway milestone data | ops | Haiku | Opus V3 120/120 (Apr 18), Phase 61 (Apr 19), CT-1 to CT-13 (Apr 9), circuit breaker (Apr 19) |
| 1.4 | Add grade history entries to SESSION_STATE.json | coding | Haiku | Delegated via FTAL. Entries: dates, grades, test counts, notes. |
| 1.5 | Validate JSON is well-formed after edit | ops | Haiku | `python -c "import json; json.load(open('roadmap/SESSION_STATE.json'))"` |
| 1.6 | Write `progress/phase_1_DATA_PREP.md` | docs | Haiku | |
| 1.7 | Update JSON companion | ops | Haiku | |

### Quality gate

- SESSION_STATE.json is valid JSON.
- Grade history has entries covering April 2026 dates.
- Entries are factually accurate (cross-referenced with git log dates).
- No code changes = no FTAL/mutation needed; factual accuracy verified manually.

### Exit criteria

SESSION_STATE.json contains April grade history; factual accuracy confirmed; user approves Phase 2.

### PersonaForge learnings to save

Grade history entry format; which milestones matter for governance mining; date accuracy verification method.

---

## Phase 2 — Incremental Mining: Git + Local Files + Cost Data

**Objective.** Execute an incremental journey mine via the existing API to capture all new sources and events from 2026-03-10 onward. This uses existing mining code paths for git commits, local files, cost data, and governance data.

**Required model:** Haiku (default). No model switches.

**Pre-phase reassessment.**
- SS3.4 baseline.
- Phase 1 SESSION_STATE.json verified.
- Backend :5000 still running (`./ro status`).
- Confirm `journey_mining_runs` table exists for progress tracking.

### Deliverables

1. New journey sources mined (git_commit, local_file, cost_data, governance).
2. New journey events generated from those sources.
3. `progress/phase_2_MINING.md` — before/after counts, duration, errors.

### Micro-tasks

| # | Task | task_type | Model | Notes |
|---|---|---|---|---|
| 2.1 | Record pre-mine source counts by type | ops | Haiku | `SELECT source_type, COUNT(*) FROM journey_sources WHERE user_id=10 GROUP BY source_type` |
| 2.2 | Record pre-mine event counts by category | ops | Haiku | Same pattern |
| 2.3 | Trigger incremental mine via API | ops | Haiku | `curl -X POST http://localhost:5000/api/journey/mine -H "user-id: 10" -H "Content-Type: application/json" -d '{"since_date":"2026-03-10"}'` |
| 2.4 | Monitor job progress | ops | Haiku | Poll `GET /api/jobs/<job_id>/status` until complete |
| 2.5 | Record post-mine source counts | ops | Haiku | Compare with 2.1 |
| 2.6 | Record post-mine event counts | ops | Haiku | Compare with 2.2 |
| 2.7 | Verify git_commit sources increased (expect ~440+ new) | ops | Haiku | `SELECT COUNT(*) FROM journey_sources WHERE user_id=10 AND source_type='git_commit'` |
| 2.8 | Verify local_file sources increased (expect ~20+ new workdir files) | ops | Haiku | |
| 2.9 | Verify governance sources increased (expect new entries from updated SESSION_STATE) | ops | Haiku | |
| 2.10 | Spot-check 5 random new events for accuracy | ops | Haiku | Cross-reference event titles/dates with git log |
| 2.11 | Verify latest event_date is now >= 2026-04-20 | ops | Haiku | |
| 2.12 | Write `progress/phase_2_MINING.md` with full before/after deltas | docs | Haiku | |
| 2.13 | Update JSON companion | ops | Haiku | |

### Quality gate

- Source count increased by at least 400 (git commits alone should be ~440).
- Event count increased (new milestones, development, achievements from April commits).
- Latest event_date is 2026-04-20 (or close).
- Spot-check passes (5/5 events factually accurate).
- No smoke-test failures on existing journey API endpoints.

### Exit criteria

Mining complete; source/event counts verified increased; date coverage extends to April 2026; user approves Phase 3.

### PersonaForge learnings to save

Mining API behavior with since_date filter; actual source delta vs expected; any mining errors encountered; Qdrant scan failure behavior (expected, since decommissioned).

---

## Phase 3 — Code: Replace Qdrant FTAL Path with ArangoDB/Gateway

**Objective.** Replace the dead `_mine_ftal_history()` method (which reads from decommissioned Qdrant) with a new implementation that reads FTAL run history from the gateway's ArangoDB collections or harness API. This restores the FTAL history data pipeline for future mining runs.

**Required model:** Haiku (default). Sonnet for design (3.1) and brutal review (3.9).

**Pre-phase reassessment.**
- SS3.4 baseline.
- Phase 2 mining complete, new events exist.
- `journey_miner_enrichment_mixin.py` current content read.
- Gateway FTAL data source identified (ArangoDB `harness_runs` or `learnings` collection, or REST API `GET /api/harness/history`).

### Deliverables

1. Updated `backend/journey_miner_enrichment_mixin.py` — `_mine_ftal_history()` reads from ArangoDB/gateway instead of Qdrant.
2. New/updated test in `backend/tests/` for the replacement method.
3. `progress/phase_3_MUTATIONS.md` — mutation verification evidence.
4. `progress/phase_3_BRUTAL_REVIEW.md` — Sonnet self-review.

### Micro-tasks

| # | Task | task_type | Model | Notes |
|---|---|---|---|---|
| 3.1 | **Design:** Identify FTAL data source in gateway | analysis | **Sonnet** | MODEL SWITCH REQUIRED. Check: ArangoDB `ftal_gap_history` collection, `harness_runs`, or REST `GET /api/harness/history`. Determine schema, field mapping. |
| 3.2 | TDD: Write test for new `_mine_ftal_history()` | coding | Haiku | Delegated via FTAL. Test uses fixture data matching identified source schema. Must fail first. |
| 3.3 | Implement replacement `_mine_ftal_history()` | coding | Haiku | Delegated. Reads from ArangoDB/gateway. Maps fields to existing source schema (source_type="ftal_history"). |
| 3.4 | Run test — confirm passes | ops | Haiku | `cd backend && python -m pytest tests/test_journey_ftal_mining.py -v` |
| 3.5 | Mutation-verify: break the ArangoDB query -> test fails -> restore -> passes | coding | Haiku | Log to `progress/phase_3_MUTATIONS.md` |
| 3.6 | Integration test: call `_mine_ftal_history()` against live ArangoDB | ops | Haiku | Verify new sources are stored correctly |
| 3.7 | Verify file stays under 500 lines | ops | Haiku | `wc -l backend/journey_miner_enrichment_mixin.py` |
| 3.8 | Run full journey test suite | ops | Haiku | `cd backend && python -m pytest tests/test_journey*.py -v` |
| 3.9 | **Brutal self-review** | review | **Sonnet** | MODEL SWITCH REQUIRED. Write `progress/phase_3_BRUTAL_REVIEW.md`. |
| 3.10 | Update JSON companion | ops | Haiku | |

### Quality gate

1. FTAL gap<10 on the replacement method (delegated, scored).
2. Mutation-verified: break ArangoDB read -> test fails -> restore -> passes.
3. Narrative coherence: new FTAL sources integrate with existing journey data (no orphans).
4. Brutal self-review on Sonnet: 0 P0 items.

### Exit criteria

`_mine_ftal_history()` reads from live ArangoDB/gateway; test suite green; mutation verified; 500-line limit respected; user approves Phase 4.

### Risk callouts

- Gateway FTAL data schema may differ from what Qdrant stored — the design step (3.1) must map fields explicitly.
- ArangoDB connection uses global port 8529 (not the docker-internal one).
- Existing 500 frozen FTAL sources should NOT be deleted — new method adds alongside.

### PersonaForge learnings to save

Gateway FTAL data source schema; ArangoDB collection name for harness results; field mapping from Qdrant format to ArangoDB format; any teaching docs created for FTAL delegation failures.

---

*End of phases 0-3. See `phases_4_to_6.md` for remaining phases.*
