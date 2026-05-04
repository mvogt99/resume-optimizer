# Resume Optimizer — Remaining Work Plan

**Date:** 2026-03-28
**Status:** Post-FINAL merge. All P0–P3 complete on main.
**Workflow:** Same as P0–P3 — TDD (tests first), honest assessment, user gate before merge.

---

## Phase P4-A: Test Infrastructure Fixes

**Model:** Sonnet | **Effort:** ~1 session | **Branch:** `feature/ro-phase-P4A-test-fixes`

### Fix 1: 79 non-E2E errors — stale mock target

**Root cause:** `test_agent_job_scout.py:14` patches `agents.base_agent.call_llm`
but post-P1-B the module imports `call_llm_scored` (not `call_llm`). One autouse
fixture fails at setup for all 29+ tests in the file.

**Fix:** Change the patch target and update the lambda return type:
```
"agents.base_agent.call_llm" → "agents.base_agent.call_llm_scored"
lambda return: None → ("", MagicMock())  # (text, scores) tuple
```

### Fix 2: 4 E2E test failures — FK constraint

**Root cause:** `AGENT_HEADERS_1 = {"user-id": "1"}` in `test_regression_e2e.py`
uses legacy auth which sets `g.user_id = 1`, but no row exists in `users` for
`id=1`. `job_postings.user_id` FK constraint fires on INSERT.

**Fix:** Add a class-level or module-level fixture to `TestGroupJ_Agents` and
`TestGroupL_MultiUser` that creates a user with id=1 (or uses the SQLite
`INSERT OR IGNORE` pattern already used elsewhere).

### Gate
- 0 non-E2E errors (was 79)
- 0 E2E test failures in Group J + L (was 4)
- Pre-commit clean
- Honest assessment A- or better

---

## Phase P2-F: PostgreSQL Migration

**Model:** Sonnet | **Effort:** 2-3 sessions | **Branch:** `feature/ro-phase-P2F-postgres`

> Note: `db_engine.py` and `db_pg_init.py` already exist from Phase 44
> (gateway-level work). The resume-optimizer backend still uses raw `sqlite3`
> throughout. This phase migrates the backend to use SQLAlchemy via db_engine.py,
> keeping SQLite as the test/dev backend.

### Session 1: Schema + models.py

- Audit all `sqlite3.connect()` calls across the backend
- Wrap `models.py` schema creation to use `db_engine.py`'s engine
- Ensure `get_db_connection()` / `get_db()` return engine-backed connections
- Test: schema creation works with both `sqlite://` and `postgresql://` URLs

### Session 2: Routes + agents

- Replace all direct `sqlite3.connect(DB_PATH)` calls in `routes/` and `agents/`
  with `get_db_connection()` / `get_db()` context managers
- Ensure transaction handling is consistent (no raw `conn.commit()` without context)
- Run non-E2E suite after each batch of files

### Session 3: E2E validation + honest assessment

- Spin up a test PostgreSQL instance (Docker)
- Run full E2E suite against Postgres
- Fix any type coercion issues (SQLite is lenient; Postgres is strict)
- Honest assessment, merge to main

### Gate
- All non-E2E tests pass on SQLite (no regression)
- E2E suite passes on PostgreSQL
- No raw `sqlite3.connect()` calls outside of test helpers
- Honest assessment A- or better

---

## Phase P4-B: Frontend — Staleness + Correlation UI

**Model:** Sonnet | **Effort:** 1-2 sessions | **Branch:** `feature/ro-phase-P4B-frontend`

### Component 1: ProfileStaleWarning banner

When `tailor_for_posting()` returns `profile_stale: true`, surface a yellow
warning banner in the optimized resume view:

```
⚠ Your career profile may be outdated (reason).
  Rebuild your deep profile → [Build Now]
```

Wire into `OptimizedResumeView.js` and `AgentDashboard.js`.

**Tests (Jest):**
- Renders warning when `profileStale=true` and `staleReason` prop set
- Hidden when `profileStale=false`
- "Build Now" link navigates to `/deep-profile`

### Component 2: CorrelationDashboard

Fetch `GET /api/agents/feedback/correlations` and display:
- Callback rate %
- Average ATS score for callbacks vs rejections
- Total applications tracked

Wire into `ApplicationPipeline.js` sidebar.

**Tests (Jest):**
- Renders stats correctly with mock API response
- Handles empty state (no feedback rows yet)
- Shows loading state while fetching

### Gate
- Both components render correctly in isolation (Jest)
- Integration: dashboard shows real data from feedback rows
- No console errors
- Honest assessment A- or better

---

## Execution Order

```
P4-A (1 session, Sonnet) → quick wins, fixes existing test debt
    ↓
P2-F session 1 (Sonnet) → schema migration
    ↓
P2-F session 2 (Sonnet) → routes + agents
    ↓
P2-F session 3 (Sonnet + Opus for assessment)
    ↓
P4-B (Sonnet) → frontend polish
    ↓
FINAL-2: full E2E on main (Opus assessment)
```

---

## Model Usage

| Phase | Model | Rationale |
|-------|-------|-----------|
| P4-A | Sonnet | Mechanical — 2 targeted patches |
| P2-F sessions 1-2 | Sonnet | Mechanical migration |
| P2-F session 3 | Sonnet → Opus for assessment | E2E + architecture assessment |
| P4-B | Sonnet | React components, no complex reasoning needed |
| FINAL-2 | Opus | Full retrospective assessment |
