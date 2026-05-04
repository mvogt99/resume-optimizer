# HONEST ASSESSMENT — Phase 14, Wave 14.4

**Date:** 2026-03-11
**Wave:** 14.4 — Agent Subclass Tests + Tier Uplift
**Status:** COMPLETE

---

## What Was Done

### New Agent Test Files (87 tests)

| Test File | Module | Tests | Focus |
|-----------|--------|-------|-------|
| `test_agent_job_scout.py` | `agents/job_scout.py` (520 LOC) | 30 | get_postings (5 filters), get/update/delete/add posting, criteria CRUD, _score_posting NLP, _log_run audit |
| `test_agent_app_tracker.py` | `agents/app_tracker.py` (322 LOC) | 28 | PIPELINE_STAGES (10), get_pipeline, move_posting, get_analytics, get_reminders, generate_followup, DB verification |
| `test_agent_subclasses.py` | 4 agents + factory + base | 29 | ResumeTailor, CoverLetter, InterviewCoach (PERSONAS), CareerAdvisor, AgentFactory (7), BaseAgentBehavior (4) |
| **Total** | | **87** | |

### Tier Uplift Edits (6 files)

| File | Before | After | Changes |
|------|--------|-------|---------|
| `test_agent_enhancements.py` | C (65.4% content, 0% db) | B | +4 `query_db()` calls (postings, feedback, patterns verification) |
| `test_analytics.py` | C (69% content, 0% db) | B | +4 `query_db()` calls (postings, feedback, agent_runs verification) |
| `test_linkedin_generator.py` | C (44% content, 4.8% db) | C (47.6% content, 23.8% db) | +3 `query_db()` calls + content field assertions |
| `test_resume_templates.py` | C (40.3% content, 3.2% db) | C (41.9% content, 12.9% db) | +3 `query_db()` calls + delete/update verification |
| `test_job_scraper.py` | D (12% content, 0% db) | D (12% content, 8% db) | +2 `query_db()` calls + error response + location assertions |
| `test_output_quality.py` | D (11.1% content, 0% db) | D (11.1% content, 16.7% db) | +3 `query_db()` calls + response field assertions, removed sys.path hack |

## Metrics

| Metric | Before (14.3) | After (14.4) | Delta |
|--------|---------------|--------------|-------|
| Backend tests | 1413 | 1530 | +117 |
| Tier-A files | 40 | 40 | 0 |
| Tier-B files | 37 | 39 | +2 |
| Tier-C files | 7 | 5 | -2 |
| Tier-D files | 2 | 2 | 0 |
| Tier-F files | 0 | 0 | 0 |
| Grade | A- | A- | — |
| GATE | PASS | PASS | — |

## RTX 5090 Delegation

Not attempted for Wave 14.4 agent test writing. Per Wave 14.3 findings, conceptual teaching effectiveness is LOW for tests requiring:
- Exact DB schema knowledge (column names, table relationships)
- Exact API response format knowledge (field names, types, nested structures)
- Singleton reset patterns and fixture dependencies

The 87 agent tests required deep understanding of 6 agent classes, their DB interactions, response structures, and the conftest fixture ecosystem. Previous RTX 5090 attempts (Wave 14.3: batch_jobs Gap=57%, smart_llm Gap=84%) confirmed that full rewrites are needed even after teaching.

## Fixes During Verification

1. **`agents.job_scout` has no attribute `call_llm`** — Monkeypatched wrong target. `job_scout.py` doesn't import `call_llm` at module level — it inherits via `BaseCareerAgent._call_llm()`. Removed bad monkeypatch; `agents.base_agent.call_llm` suffices.

2. **`get_pipeline` returns flat structure** — Test assumed `stages` was list of dicts. Actual: `{"stages": [str_list], "columns": {name: [postings]}, "total": int}`.

3. **`move_posting`/`generate_followup` nonexistent posting** — Returns `{"error": "Posting not found"}` not `None`. Changed assertions.

4. **`_insert_resume_version` INTEGER PRIMARY KEY** — Used UUID string for `id` but `resume_versions.id` is `INTEGER PRIMARY KEY AUTOINCREMENT`. Fixed by using `cursor.lastrowid`.

5. **`is_starred` SQLite boolean** — `assert result["is_starred"] is True` fails with `1`. Fixed: `assert result["is_starred"] in (True, 1)`.

6. **`test_output_quality.py` wrong table** — Upload API stores in `resumes` table, not `resume_versions`. Fixed `query_db()` calls.

7. **`test_output_quality.py` wrong field name** — Optimize API returns `ats_compliance_score` not `score`. Fixed assertions.

## Why D-Tier Files Didn't Move

`test_job_scraper.py` and `test_output_quality.py` are fundamentally mixed: unit tests (testing Python functions directly) + API tests (using Flask test client) in the same file. qa_audit classifies the ENTIRE file as API when ANY test uses `client`. For API files, tier is based on content_pct = (content_checked_tests / total_tests) × 100.

- `test_job_scraper.py`: 14 unit tests + 11 route tests = 25 total. Only route tests can have content (get_json). Max content_pct = 11/25 = 44%. **Structurally capped below B threshold (50%).**
- `test_output_quality.py`: 15 script tests + 3 API tests = 18 total. Max content_pct = 3/18 = 16.7%. **Structurally capped below C threshold (30%).**

The correct fix would be splitting each into two files (pure unit tests → A-tier via assertion density; pure route tests → A/B via content/db). This is a low-priority cosmetic change since GATE passes and both files test real functionality with good assertion density.

## Patterns Established

- **Agent monkeypatch target:** `agents.base_agent.call_llm` blocks all agent LLM calls (inherited). Don't patch module-level targets that don't exist.
- **SQLite boolean compatibility:** Always use `in (True, 1)` or `in (False, 0)` for boolean field assertions.
- **Resume table structure:** Upload → `resumes` table. LinkedIn/import → `resume_versions` table. Optimize API returns `ats_compliance_score`.
- **Mixed file tier ceiling:** Files with both unit and API tests are structurally limited in content_pct. Split for proper tier classification.
- **Pipeline API format:** `get_pipeline()` returns stages as string list with separate columns dict, not list of dicts.

## Honest Gaps

- D-tier files still at D (structural issue, not test quality issue)
- test_agents_e2e.py has 2 pre-existing failures (ResumeTailor tailor/retrieve) — not addressed in this wave
- No new A-tier files this wave (agent test files are script-type → automatic A)
- test_linkedin_generator.py and test_resume_templates.py improved but stayed C (need more content assertions in route tests)

## Next

Wave 14.5: Route Tests + Remaining Modules — dedicated route-level test files for high-traffic blueprints (resume, campaigns, builder, experience, journey). Pure API tests → should achieve A-tier.
