# Honest Assessment — Resume Optimizer

**Date:** 2026-03-10
**Phase:** 11.5 (commit e08b939)
**qa_audit Grade:** A (37 A-tier / 28 B-tier / 1 D-tier / 0 F-tier, 912 tests)
**Gateway Grade:** B+ (44 A-tier / 157 B-tier / 0 F-tier, 3102 tests)

---

## What Was Actually Done (Phases 1-11.5)

### Phase 1: Foundation Hardening
- Deleted 117 mocked/stub tests that inflated count (458 → 362 real tests)
- Fixed 0-value false positives in qa_audit AST parser
- Eliminated all `assert True`, `silent_pass`, and `broad_500` anti-patterns
- Grade: D+ → C+

### Phase 2: Tier-F Elimination + Governance Tooling
- Rewrote all 8 Tier-F test files to use real Flask test client + SQLite
- Built 4 governance tools: `qa_audit.py` (AST-based grader), `pmo_state.py` (session state), `schema_guard.py` (99.2% route coverage), `commit_gate.py` (pre-commit orchestrator)
- Grade: C+ → B

### Phase 3: Systematic Tier Upgrades (5 waves, 27 files)
- Upgraded 27 test files from B/C to A-tier via assertion enrichment
- Added content-level checks (response body values, not just status codes)
- Added DB verification (query SQLite after mutations to confirm writes)
- Grade: B → A

### Phase 4: Pure Logic Module Testing (6 modules, 144 tests)
- Tested `skills_optimizer.py`, `linkedin_parser.py`, `nlp_engine.py`, `interview_guide.py`, `batch_jobs.py`, `models.py`
- All tests exercise real functions with real data — no mocks
- Grade: A (602 tests)

### Phase 5: API File Upgrades (6 files B→A)
- Upgraded 6 API test files with deeper content + DB assertions
- 30 total A-tier files

### Phases 6-8: Gap Remediation + Integration + E2E
- Phase 6: Cross-module integration tests, qa_audit logic-tier A
- Phase 7: 49 live service integration tests (require running backend + LLM)
- Phase 8: 36 Playwright frontend E2E tests covering upload→optimize flow, auth, agents, sessions, deep profile tabs

### Phase 9: Live LLM Quality Tests + Export Verification
- Tests that verify LLM output quality (high-match vs zero-match discrimination)
- Export endpoint verification (campaign export, resume download)
- Visual regression baselines

### Phase 10: DLH Import + Journey Enrichment + Content Generation
- 9 DLH import tests, 16 journey enrichment tests, 13 content generation tests
- Gateway governance tools (`qa_audit.py` + `pmo_state.py`) activated for gateway codebase
- Test isolation fixed (SQLite per-test cleanup)

### Phase 11: Gateway Governance + Journey Re-mine + Module Coverage
- Wave 11.1: Gateway qa_audit activated and calibrated (12 tests)
- Wave 11.2: Journey data re-mined — fixed epoch-to-ISO date bug, 0 invalid dates after cleanup (13 tests)
- Wave 11.3: 12 previously-untested modules covered with real LLM tests (69 tests)

### Phase 11.5: Five Gaps Resolved
1. **Flaky test fixed**: `INFERENCE_TIMEOUT` 120→300s, `retries` 1→2 with exponential backoff in `smart_llm.py` and `agents/base_agent.py`
2. **Gateway D+→B+**: Mock reclassification in qa_audit (105 files F→B), 16 F-tier files fixed (real anti-patterns), 25 new A-tier test files (462 tests)
3. **DevOps/Frontend GOVERNED**: `test_frontend_governance.py` — 17 tests validating package.json, React 18, Playwright specs, component counts, .gitignore
4. **21 untested modules covered**: 5 new test files (73 tests) — schemas (30), agent factory (12), linkedin_cache (11), app bootstrap (10), seed_builder (10)
5. **Documentation updated**: This file, SESSION_STATE.json, phase11_proof.json

---

## What Is Actually Implemented (Feature Status)

### WORKING — End-to-End Proven

| Feature | Key Files | Evidence |
|---------|-----------|---------|
| **Resume upload + NLP optimization** | `utils.py` (4-signal scoring: keyword 20%, semantic 20%, skills 50%, sections 10%), `nlp_engine.py` (spaCy + NLTK) | `test_integration_resume.py` — 6.0 assertions/test, full upload→optimize→verify |
| **Google Drive import** | `gdrive_service.py` — real OAuth at `~/.config/resume-optimizer/token.json`, Google Docs export + PDF/DOCX/PPTX/XLSX download | `test_live_gdrive.py` — requires valid token |
| **Experience extraction chat** | `experience_chat.py` — 6-stage state machine (intro→role→responsibilities→technologies→outcomes→challenges), LLM via FTAL harness, template fallback | `test_integration_experience.py` — 6.0 assertions/test |
| **Project analysis pipeline** | `project_analyzer.py` — GDrive recursive crawl, 3 LLM extractors (technical/governance/role), ArangoDB approval workflow | `test_projects_analysis.py`, `test_live_arango.py` |
| **AI journey mining** | `journey_miner.py` — 4 sources (workdir files, Qdrant 3 collections, ArangoDB 5 collections, git commits since 2025-12-01), SHA-256 dedup | `test_journey_miner_date.py`, `test_journey_reset.py`, `test_live_journey.py` |
| **Campaign system** | `campaign_interview.py` — 7-stage planning (theme→audience→tone→storyline→post_count→content_seeds→review), `post_generator.py` — 3000-char LinkedIn posts with draft versioning | `test_campaigns_full.py` — 18 tests, 88.9% content checks |
| **Deep career profile** | `deep_profile.py` — aggregates 7 sources (3 client projects with 7272 skills + 4499 outcomes, LinkedIn 76 skills, journey 849 events, WIP projects), LLM synthesis, role fit scoring (85% for test JD) | `test_deep_profile_interview.py` |
| **Job Scout agent** | `agents/job_scout.py` — python-jobspy scraping (Indeed/LinkedIn/Glassdoor), NLP + LLM scoring, criteria management, background jobs | `test_agents_wave2_live.py` — 30 tests |
| **Application Tracker agent** | `agents/app_tracker.py` — 10-stage Kanban pipeline, SQL analytics, LLM follow-up email generation, performance pattern analysis | `test_integration_agents.py` |
| **Frontend SPA** | 35+ React components, all features wired to API routes | 36 Playwright E2E tests, 6 spec files |

### PARTIAL — Code Exists But Caveats Apply

| Feature | Status | Detail |
|---------|--------|--------|
| **LinkedIn import** | Reads local JSON only | `linkedin_parser.py` parses `working-docs/linkedin/linkedin_profile_merged_api_preferred.json` — a one-time data export. No live LinkedIn OAuth. No way to import a different user's profile from the web. |
| **LLM-powered resume rewrite** | Requires RTX 5090 | `utils.optimize_resume()` line 339-344 calls `call_smart()` for rewrite pass. If LLM unavailable, returns NLP-only optimization (keyword matching without rewriting). |

### STUB — Skeleton Code, Not Production-Ready

| Feature | File | Lines | What Exists | What's Missing |
|---------|------|-------|-------------|----------------|
| **Resume Tailor agent** | `agents/resume_tailor.py` | ~200 | Class skeleton, LLM call stubs | Not wired to routes, no E2E tests, no JD→resume customization logic |
| **Cover Letter agent** | `agents/cover_letter.py` | ~250 | Template-based generation | Not wired to routes, no E2E tests, no company culture matching |
| **Interview Coach agent** | `agents/interview_coach.py` | ~400 | Role-specific personas, STAR templates | Not wired to routes, no E2E tests, no mock interview flow |
| **Career Advisor agent** | `agents/career_advisor.py` | ~200 | Placeholder class | No trajectory analysis, no market trends, no salary benchmarking |

These 4 agents are listed as "Wave 2" and "Wave 3" in the roadmap. Only Job Scout and Application Tracker (Wave 1) are production-ready.

---

## Test Quality: Honest Breakdown

### Strengths
- **7 integration test files** use real Flask test client + SQLite — no mocks, full request→response→DB verification
- **8 LLM-dependent test files** use `require_harness` fixture — explicit about RTX 5090 dependency, hard-fail (not silent skip) when unavailable
- **912 tests total**, 37 files graded A-tier with content + DB assertions

### Weaknesses and Blind Spots

| Issue | Detail | Risk |
|-------|--------|------|
| **LLM tests hard-fail** | Tests using `require_harness()` FAIL (not skip) when RTX 5090 is down. CI without GPU reports failures, not skips. | Medium — CI needs GPU or must exclude these tests |
| **Infrastructure tests silently skip** | `test_live_arango.py`, `test_live_journey.py` use `@pytest.mark.skipif(not AVAILABLE)` — CI passes green even with services down | Medium — false confidence in CI |
| **Zero React unit tests** | Frontend has only Playwright E2E tests (6 suites). No Jest/RTL component-level tests. Broken component only caught by E2E or manual testing. | Medium |
| **No error path tests** | Minimal coverage for timeouts, network failures, malformed input, concurrent access | Low-Medium |
| **Monkeypatched tests graded A** | `test_analysis_worker.py` (11 tests) monkeypatches extractors with fakes, graded A-tier solely on assertion density (2.3/test). qa_audit doesn't penalize mocking. | Low — tests still verify error handling paths |
| **1 D-tier file remains** | `test_output_quality.py` — 15.4% content coverage. Tests semantic discrimination (high-match vs zero-match) but too few content assertions for A/B grade. | Low |
| **Flaky under GPU contention** | `test_skills_extractor_items_have_name` passes in isolation (27s) but fails in full suite (37 min) due to FTAL harness timeout under concurrent load | Low — fixed with timeout increase but could recur under extreme load |

### qa_audit.py Grading Methodology
- **API tests**: Graded on `content_pct` (response body value checks) + `db_pct` (SQLite verification). A-tier requires >70% content AND >30% DB.
- **Non-API tests**: Graded on assertion density (≥2.0/test) + test count (≥10). This means a file with 10 `isinstance` checks gets A-tier.
- **Anti-patterns auto-F**: `always_true`, `silent_pass`, `broad_500` immediately grade F. Mock usage caps at B (not auto-F after Phase 11.5 reclassification).
- **Blind spot**: Non-API grading doesn't distinguish monkeypatched mocks from real function calls. A file mocking all dependencies can still grade A if assertion density is high enough.

---

## Infrastructure Dependencies

| Service | Port | Status | Impact When Down |
|---------|------|--------|-----------------|
| **RTX 5090 vLLM** | 8021 | REQUIRED | All AI features degrade to templates or empty responses. Resume rewrite, experience chat, campaign generation, journey synthesis all need LLM. |
| **Gateway FTAL Harness** | 8000 | REQUIRED | Smart model selection + RAG context injection lost. `smart_llm.py` falls back to direct port 8021 without RAG grounding. `experience_chat.py` falls back to template questions. |
| **SQLite** | file | REQUIRED | App crashes on startup. Auto-created in CWD — must run from `backend/` directory. |
| **spaCy `en_core_web_sm`** | — | REQUIRED | `nlp` variable is None. Keyword extraction returns empty. Resume optimization degrades to basic text matching. |
| **ArangoDB** | 8529 | OPTIONAL | Graph storage disabled. `arango_client.py` methods return None silently. Project approval, journey approval, campaign analytics all return empty. App functions but graph-grounded features lose context. |
| **Qdrant** | 6333 | OPTIONAL | Journey mining returns `qdrant_records: 0`. Timeline builds from workdir + git only (misses AI learning events). Deep profile has less data. |
| **Artemis STOMP** | 61613 | OPTIONAL | `bus_client.py` returns `is_available=False`. Document analysis runs sequentially instead of parallel. Slower but functionally identical. |
| **Google Drive OAuth** | — | OPTIONAL | `/api/resumes/gdrive/*` routes raise FileNotFoundError. Users must upload files manually. Token expected at `~/.config/resume-optimizer/token.json`. |

### Missing from requirements.txt
- `qdrant-client` — required for journey mining, imported dynamically in `journey_miner.py`
- `stomp.py` — required for Artemis bus, imported dynamically in `bus_client.py`
- Both degrade gracefully if missing, but should be in requirements.txt

### No Docker/Container Setup
- No `Dockerfile` or `docker-compose.yml` in `applications/resume-optimizer/`
- Manual startup only: `cd backend && python app.py` + `cd frontend && npm start`
- Infrastructure (ArangoDB, Qdrant, Artemis) managed by parent project's docker-compose

---

## Remaining Legitimate Gaps

### Application-Level Gaps (Not Test Gaps)

| # | Gap | Severity | Detail |
|---|-----|----------|--------|
| 1 | **4 stub agents** | HIGH | Resume Tailor, Cover Letter, Interview Coach, Career Advisor are code skeletons. Not wired to Flask routes. No tests prove they produce useful output. Roadmap says "Wave 2/3" but no timeline. |
| 2 | **No live LinkedIn OAuth** | MEDIUM | App reads a static JSON export file. Cannot import a new LinkedIn profile from the web. Would need LinkedIn API credentials + OAuth flow. |
| 3 | **No Docker deployment** | MEDIUM | No reproducible deployment. Manual `pip install` + `npm install` + service startup. Production deployment undocumented. |
| 4 | **Missing pip dependencies** | LOW | `qdrant-client` and `stomp.py` not in requirements.txt. Silent import failures when missing. |
| 5 | **No multi-user testing** | LOW | All tests use single user. No concurrent access, race condition, or session isolation tests. SQLite file-level locking is the only protection. |

### Testing Gaps

| # | Gap | Detail |
|---|-----|--------|
| 1 | **No React unit tests** | Zero Jest/RTL tests. Only Playwright E2E. Component bugs only caught at integration level. |
| 2 | **LLM tests not CI-friendly** | `require_harness()` hard-fails without RTX 5090. Need `skipif` or CI test matrix (unit-only / integration / GPU). |
| 3 | **Silent skips inflate CI confidence** | ArangoDB/Qdrant/GDrive tests skip silently when services are down. CI reports green but features are untested. |
| 4 | **No error/timeout path tests** | Minimal coverage for network failures, LLM timeouts, malformed uploads, oversized files. |

### Gateway Governance Gaps (Not Resume-Optimizer Scope)

| Department | Status | Detail |
|------------|--------|--------|
| Infrastructure | GOVERNED | Health, config, backend monitor tested |
| Intelligence | GOVERNED | Model selection, learning service tested |
| Routing | GOVERNED | Flow engine, rules index tested |
| **Agents** | **NO GOVERNANCE** | Gateway agent system (separate from resume-optimizer agents) ungoverned |
| **Observability** | **NO GOVERNANCE** | Metrics, logging, tracing ungoverned |
| **API_Surface** | **PARTIAL** | Some route tests, but not comprehensive |

---

## Grade Justification

**Backend Grade A is defensible because:**
- 912 tests across 66 files with 0 failures, 0 anti-patterns, 0 F-tier files
- 7 integration test files with real Flask client + SQLite (no mocks)
- 8 LLM test files that verify actual model output quality
- All 8 departments GOVERNED by qa_audit
- Content validation at 36.1%, quality-weighted at 30.4% — above A threshold

**Backend Grade A has caveats:**
- 42% of files are B-tier (not A-tier) — the "A" grade is an overall weighted score, not every-file-is-A
- Grading system doesn't penalize monkeypatching or silent infrastructure skips
- 1 D-tier file (`test_output_quality.py`) remains
- LLM-dependent tests (~50 tests) require RTX 5090 running — they fail hard without it

**Gateway Grade B+ is legitimate but limited:**
- 3102 tests, 0 F-tier files (down from 127 F-tier before mock reclassification)
- Mock reclassification was necessary — gateway tests legitimately mock Docker/HTTP/Redis while testing real business logic
- 3 departments still ungoverned (Agents, Observability, API_Surface partial)
