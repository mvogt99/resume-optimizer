# Resume Optimizer — Remediation Roadmap (V2)

**Created:** 2026-03-06
**Basis:** Honest Assessment v3, full codebase audit, 370/370 E2E stability proof
**Previous:** `ROADMAP.md` covers Phases 1-14 (all complete). This roadmap is forward-looking.
**Canonical user:** `mvogt99@gmail.com` / `password` (user_id 10, all career data migrated)

---

## Guiding Principles

1. **Fix before build** — No new features until critical bugs are resolved
2. **Real data validation** — Tests use actual OPI/Navitus/AHEAD/Journey data, not synthetic
3. **Honest checkpoints** — Every phase ends with a brutally honest assessment
4. **Dead code elimination** — Remove what isn't used before adding more
5. **Delegate to RTX 5090** — Use FTAL harness for code generation where practical

---

## Phase 15: Critical Bug Fixes (Tier 1)

**Goal:** Fix security vulnerabilities and crash-level bugs.
**Estimated effort:** 1-2 days
**Checkpoint:** All 135 existing tests still pass + new security tests

### 15.1 Agent Auth Bypass (CRITICAL — C1)
- [ ] Replace `_get_user_id()` with `@require_auth` decorator in `agents_routes.py`
- [ ] Add auth check to all 30+ agent routes (scout, pipeline, analytics, status)
- [ ] Write 3 tests: unauthenticated → 401, wrong user → 403, valid user → 200
- [ ] Verify: attempt to access another user's postings → blocked

### 15.2 NLP Engine Crash Guard (CRITICAL — C2)
- [ ] Add sentinel fallback when neither spaCy model is installed
- [ ] `nlp_engine.py`: assign `nlp = None` in except branch, guard all callers
- [ ] Write test: scoring with missing spaCy model returns error, not crash
- [ ] Verify: `pytest backend/tests/` passes even without spaCy models

### 15.3 JWT Secret Hardening (CRITICAL — C3)
- [ ] Move JWT secret to environment variable `JWT_SECRET`
- [ ] Fall back to `.jwt_secret` file only if env var missing (backward compat)
- [ ] Add `.jwt_secret` to `.gitignore`
- [ ] Write test: token generation uses env var when set

### 15.4 LinkedIn Cache Persistence (CRITICAL — C4)
- [ ] Create `linkedin_profiles` table in SQLite (user_id, profile_json, raw_json, updated_at)
- [ ] `linkedin_cache.py`: persist to DB on set, load from DB on get
- [ ] On startup, preload from DB instead of empty dict
- [ ] Write test: cache survives app restart (create profile, restart fixture, verify)

### 15.5 JD File Upload Fix (SIGNIFICANT — S5)
- [ ] Wire `JobDescriptionInput.js` file upload mode to `api.uploadJobDescription()`
- [ ] Support PDF/DOCX/TXT JD files (reuse existing parser)
- [ ] Write test: upload a .txt JD file → gets parsed and scored
- [ ] Remove or fix the broken toggle UI

### 15.6 Foreign Key Enforcement (SIGNIFICANT — S2)
- [ ] Add `PRAGMA foreign_keys = ON` to `models.py` `get_db()` context manager
- [ ] Run full test suite to catch any violated FK constraints
- [ ] Fix any violations found (orphaned rows, missing references)

### 15.7 PDF Download Auth Fix (SIGNIFICANT — S9)
- [ ] `OptimizedResumeView.js`: use Axios instance (with auth interceptor) for downloads
- [ ] Write test: download without token → 401

### Checkpoint 15: Security Audit

**Pass criteria:**
- [ ] All 30+ agent routes require valid JWT
- [ ] No NameError on missing spaCy model
- [ ] JWT secret not in git history
- [ ] LinkedIn data survives restart
- [ ] Foreign keys enforced
- [ ] All 135+ existing tests still pass

**Honest assessment questions:**
- Can user B still access user A's data through any endpoint?
- Does the app degrade gracefully or crash when dependencies are missing?
- Are there any other unauthenticated endpoints?

---

## Phase 16: Scoring Quality Improvements (Tier 2)

**Goal:** Make the relevance score genuinely useful for job search decisions.
**Estimated effort:** 2-3 days
**Checkpoint:** Matched pair score ≥75, mismatched ≤5, new discrimination tests pass

### 16.1 Sentence-Transformer Embeddings
- [ ] Replace `spacy doc.similarity()` with `sentence-transformers all-MiniLM-L6-v2`
- [ ] Model is already available in gateway Qdrant service — reuse or load locally
- [ ] Expected: chef-vs-ML semantic similarity drops from 75% to ~20%
- [ ] Write benchmark test: measure discrimination gap before/after
- [ ] **Delegate to RTX 5090:** Generate the embedding integration code

### 16.2 Formula Reweighting
- [ ] Change weights: `skills_match` 40% → 50%, `keyword_coverage` 40% → 20%
- [ ] `semantic_similarity` 30% → 20%, `section_completeness` 10% → 10%
- [ ] Rationale: `skills_match` (94% for match) is 2x more reliable than `keyword_coverage` (44%)
- [ ] Write test with ACTUAL resume data: Mike Vogt resume vs Solutions Architect JD
- [ ] Write test with ACTUAL data: Mike Vogt resume vs Chef JD → score < 10

### 16.3 Structured JD Parsing (Optional — High Impact)
- [ ] Extract requirements as structured data: years_experience, required_skills, nice_to_have, education
- [ ] Score against resume fields individually (vs raw text comparison)
- [ ] Write parser for common JD formats (Indeed, LinkedIn, Greenhouse)
- [ ] **Delegate to RTX 5090:** Generate JD parsing code with regex + NLP hybrid approach
- [ ] Write test: parse 5 real JDs from the 17 in database, verify field extraction

### Checkpoint 16: Scoring Quality Audit

**Pass criteria:**
- [ ] Matched pair (Enterprise Architect vs Solutions Architect): score ≥ 70
- [ ] Mismatched pair (Chef vs ML Engineer): score ≤ 5
- [ ] Discrimination gap ≥ 65 points
- [ ] 10x regression still 100% pass rate

**Honest assessment questions:**
- Would you trust this score to decide whether to apply to a job?
- Does the score correlate with actual resume-to-JD relevance?
- How does it compare to just reading the JD yourself?

---

## Phase 17: Dead Code Elimination + Platform Cleanup (Tier 3a)

**Goal:** Remove unused code, fix toolchain, add onboarding.
**Estimated effort:** 2-3 days
**Checkpoint:** Leaner codebase, no dead methods, modern build toolchain

### 17.1 Remove Dead API Methods
- [ ] Delete 20 unused methods from `frontend/src/services/api.js`:
  `getInterviewGuide`, `getLinkedInProfile`, `listExperiences`, `cancelJob`,
  `listJobs`, `getCampaignSessionState`, `addCampaignPost`,
  `getSkillsInterviewSummary`, `getAtsImprovedResume`, `getDeepInterviewStatus`,
  `getDeepInterviewInsights`, `getBuilderInterviewStatus`, `scoutGetPosting`,
  `getAgentRuns`, `coachGetAssessment`, `getJourneySources`,
  `getTechnologySummary`, `getClientsByTechnology`, `getKnowledgeContext`,
  `getCampaignAnalytics`
- [ ] Verify: `npm run build` succeeds, no import errors
- [ ] For each deleted method: confirm the backend endpoint is still needed (may be API-only)
- [ ] Document which endpoints are API-only (no frontend consumer)

### 17.2 Migrate react-scripts to Vite
- [ ] Replace `create-react-app` with `vite` (gateway web UI already uses Vite)
- [ ] Update `package.json`, add `vite.config.js`, update imports
- [ ] Verify: `npm run build` produces working bundle
- [ ] Verify: `npm audit` shows 0 high/critical vulnerabilities
- [ ] **Delegate to RTX 5090:** Generate Vite migration config

### 17.3 Add Onboarding Flow
- [ ] Create `Onboarding.js` component — 3-step wizard overlay for new users
  - Step 1: Upload resume (points to ResumeUpload)
  - Step 2: Paste a job description (points to JobDescriptionInput)
  - Step 3: See your relevance score (points to OptimizedResumeView)
- [ ] Show only on first login (localStorage flag)
- [ ] Add "Show guide" button to Dashboard for repeat viewing

### 17.4 Fix Inline Styles
- [ ] Move remaining inline `style={{}}` attributes to CSS classes
- [ ] Consolidate duplicate CSS across `App.css` and component-specific styles

### Checkpoint 17: Codebase Quality Audit

**Pass criteria:**
- [ ] 0 dead API methods in `api.js`
- [ ] `npm audit` reports 0 high/critical vulnerabilities
- [ ] New users see onboarding on first visit
- [ ] No inline styles in components

**Honest assessment questions:**
- Is every API method in `api.js` actually called from a component?
- Is every backend endpoint actually needed? (Check for backend-only dead routes too)
- Would a new developer understand the codebase structure?

---

## Phase 18: Comprehensive Test Coverage (Tier 3b)

**Goal:** Cover all 119 endpoints with tests using REAL career data.
**Estimated effort:** 3-5 days
**Checkpoint:** 95%+ endpoint coverage, 10x regression stability

### 18.1 Endpoint Coverage — Journey Routes (6 untested)
- [ ] `POST /api/journey/mine` — Start mining (mock GDrive, verify job created)
- [ ] `PUT /api/journey/narratives` — Update narrative text
- [ ] `POST /api/journey/approve` — Approve narratives
- [ ] `POST /api/journey/review/start` — Start review session
- [ ] `POST /api/journey/review/message` — Send review message
- [ ] `POST /api/journey/review/apply` — Apply review edits
- [ ] Use ACTUAL journey data: verify 3,355 sources and 2,221 events are queryable

### 18.2 Endpoint Coverage — Profile/Deep Routes (8 untested)
- [ ] `POST /api/import/linkedin` — Import LinkedIn profile
- [ ] `GET /api/deep-profile` — Get deep profile
- [ ] `POST /api/deep-profile/role-synthesis` — Synthesize role fit
- [ ] `POST /api/deep-interview/start` — Start deep interview
- [ ] `POST /api/deep-interview/message` — Send message
- [ ] `GET /api/deep-interview/{id}/status` — Check status
- [ ] `POST /api/deep-interview/{id}/finalize` — Finalize
- [ ] `GET /api/deep-interview/{id}/insights` — Get insights
- [ ] Use ACTUAL deep profile: verify synthesis against real JDs

### 18.3 Endpoint Coverage — Project Routes (5 untested)
- [ ] `POST /api/projects/{id}/analyze` — Start analysis (mock GDrive)
- [ ] `PUT /api/projects/{id}/analysis` — Update analysis
- [ ] `GET /api/projects/folders` — Browse folders
- [ ] `POST /api/projects/{id}/reanalyze` — Reanalyze
- [ ] `POST /api/projects/{id}/reset-status` — Reset status
- [ ] Use ACTUAL project data: verify OPI (118 docs), AHEAD (44), Navitus (477)

### 18.4 Endpoint Coverage — Agent Wave 2+3 Routes (~17 untested)
- [ ] Resume Tailor: tailor, get tailored, score breakdown
- [ ] Cover Letter: generate, list, get, edit, download
- [ ] Interview Coach: start session, get questions, submit answer, get assessment
- [ ] Career Advisor: start analysis, get recommendations, track progress
- [ ] Test both LLM-available and LLM-unavailable paths

### 18.5 NLP Unit Tests (currently zero)
- [ ] Test keyword extraction with ACTUAL Mike Vogt resume text
- [ ] Test semantic similarity: matched pair, mismatched pair, edge cases
- [ ] Test skills vocabulary matching against real JDs from database
- [ ] Test section detection: verify it finds SUMMARY, EXPERIENCE, EDUCATION in real resume
- [ ] Test floor correction formula with boundary values (0, 20, 50, 80, 100)

### 18.6 Edge Case + Concurrent Access Tests
- [ ] Empty resume text → graceful error
- [ ] 100KB resume → handled without timeout
- [ ] Unicode characters in resume/JD → no crashes
- [ ] Simultaneous scoring from 2 users → no cross-contamination
- [ ] Missing database → clear error message

### 18.7 Realistic Validation Suite
- [ ] Create `test_realistic_validation.py` using ACTUAL data:
  - Login as `mvogt99@gmail.com` / `password`
  - Upload Mike Vogt's real resume (from database)
  - Score against 5 different real JDs (from database)
  - Verify scores are sensible (Enterprise Architect JD → high, irrelevant JD → low)
  - Verify skills gap returns real tech skills (Python, AWS, Docker, etc.)
  - Verify interview guide generates role-appropriate personas
  - Verify journey timeline has 2,221+ events
  - Verify project analysis has OPI/AHEAD/Navitus data
  - Verify campaign has LinkedIn post drafts
- [ ] Run 10x to verify stability

### 18.8 Updated 10x Regression Suite
- [ ] Merge new tests into `test_regression_e2e.py` or create `test_regression_v2.py`
- [ ] Target: 80+ tests covering all endpoint groups
- [ ] Run 10 consecutive times, report to `roadmap/REGRESSION_V2_10X_REPORT.md`
- [ ] Zero flaky tests allowed

### Checkpoint 18: Test Coverage Audit

**Pass criteria:**
- [ ] ≥95% endpoint coverage (113+ of 119 endpoints tested)
- [ ] 10x regression: 100% pass rate
- [ ] Zero flaky tests
- [ ] Real data validation suite passes
- [ ] NLP unit tests cover all 4 scoring signals

**Honest assessment questions:**
- Are there endpoints that exist but serve no purpose? (Remove them)
- Do the tests actually verify behavior, or just check status codes?
- Would these tests catch a real regression (e.g., scoring algorithm change)?

---

## Phase 19: Complete ArangoDB Knowledge Graph (Tier 3c)

**Goal:** Write journey, campaign, and deep profile data to ArangoDB.
**Estimated effort:** 2-3 days
**Checkpoint:** All 31 `ro_*` collections populated, graph queries return connected data

### 19.1 Journey → ArangoDB
- [ ] Wire `POST /api/journey/approve` to write events to `ro_journey_milestones`
- [ ] Create edges: `ro_milestone_demonstrated_skill`, `ro_milestone_belongs_to_project`
- [ ] Populate `ro_ai_skills` from journey technology extraction
- [ ] Verify: graph traversal from milestone → skill → client returns connected data
- [ ] Use ACTUAL data: 2,221 journey events should produce meaningful graph

### 19.2 Campaign → ArangoDB
- [ ] Wire campaign creation to write to `ro_campaigns`
- [ ] Wire post creation to write to `ro_campaign_posts`
- [ ] Create edges: `ro_campaign_contains_post`, `ro_post_references_client/skill/milestone`
- [ ] Verify: graph traversal from campaign → post → referenced client/skill

### 19.3 Deep Profile → ArangoDB
- [ ] Wire deep profile build to write to `ro_deep_profiles`
- [ ] Create edges: `ro_profile_demonstrates_skill`, `ro_profile_achieved_outcome`
- [ ] Verify: graph traversal from profile → skills → outcomes → clients

### 19.4 Graph Query API Enhancement
- [ ] Add `GET /api/graph/journey-milestones` — query milestones by skill/date
- [ ] Add `GET /api/graph/career-path` — full career trajectory from graph
- [ ] Write tests using ACTUAL data: verify OPI skills connect to OPI outcomes

### Checkpoint 19: Knowledge Graph Audit

**Pass criteria:**
- [ ] All 31 `ro_*` collections have data (was: only 13/31)
- [ ] Graph traversal: skill → clients → outcomes returns real data
- [ ] Graph traversal: milestone → skills → projects returns connected data
- [ ] Journey approve + campaign create both write to graph

**Honest assessment questions:**
- Does the graph add value beyond what SQLite already provides?
- Can a user actually explore the graph? (Need visualization in Phase 20)
- Is the graph data consistent with SQLite data?

---

## Phase 20: Strategic Enhancements (Tier 4 — Optional)

**Goal:** Features that would make this a genuinely differentiated product.
**Estimated effort:** 2-4 weeks (pick and choose)

### 20.1 Knowledge Graph Visualization (2-3 days)
- [ ] Add D3.js or vis.js force-directed graph component
- [ ] Show: clients → skills → outcomes → milestones as interactive network
- [ ] Click a node to see details, filter by client/date/skill category
- [ ] Use ACTUAL data: visualize 6,124 skills + 4,235 outcomes

### 20.2 Resume Format Analysis (1 day)
- [ ] Parse PDF structure: detect tables, multi-column layouts, images, headers/footers
- [ ] Add `format_score` signal (10-15% weight) to relevance scoring
- [ ] Flag ATS-unfriendly patterns with specific fix recommendations
- [ ] Write test with ACTUAL resume PDF

### 20.3 Mobile-Responsive Layout (2 days)
- [ ] Add viewport meta, responsive breakpoints, touch-friendly controls
- [ ] Priority: scoring view, skills gap, interview guide (most useful on mobile)
- [ ] Test on actual phone screen sizes

### 20.4 Export to Google Docs Round-Trip (1 day)
- [ ] Export optimized resume as Google Doc (not just clipboard copy)
- [ ] Enable edit-in-Drive → re-import workflow
- [ ] Use Google Docs API `documents.create` + `batchUpdate`

### 20.5 Campaign Scheduling + LinkedIn API (3 days)
- [ ] LinkedIn OAuth 2.0 integration for post publishing
- [ ] Calendar view for campaign scheduling
- [ ] Draft → scheduled → published workflow
- [ ] Analytics: track engagement metrics post-publish

### 20.6 Make Swap-Wait Async (4 hours)
- [ ] When LLM model swap needed, return job_id immediately
- [ ] Frontend polls for completion (reuse batch_jobs pattern)
- [ ] Show progress: "Loading model... (estimated 2-3 minutes)"
- [ ] Prevents 660s request thread blocking

### Checkpoint 20: Feature Value Audit

**Honest assessment questions:**
- Which of these features would you actually use in a real job search?
- Is the knowledge graph visualization useful or just cool-looking?
- Does mobile support matter for this audience (small group of tech professionals)?
- Is LinkedIn API integration worth the OAuth complexity for personal use?

---

## Phase 21: FTAL Harness Improvements

**Goal:** Make the delegation pipeline reliable for ongoing development.
**Estimated effort:** 1-2 days
**Status:** Critical field mapping bug FIXED (2026-03-06). Remaining items below.

### 21.1 Fixes Applied (2026-03-06)
- [x] MCP server field mapping: `ftal_score{}` → `ftal_f/ftal_t/ftal_a/ftal_gap` (flat keys)
- [x] Added `analysis` to valid task types in gateway
- [x] Added async delegation tool (`delegate_task_async` + `check_job`)
- [x] Increased timeout from 300s to 660s (matches swap timeout)
- [x] Added error handling (ConnectError, TimeoutException, HTTPStatusError)
- [x] Added FTAL score persistence to `agent_jobs` table (ftal_f, ftal_t, ftal_a, ftal_gap columns)
- [x] Persisted scores from both `/run` (blocking) and `/submit` (async) paths

### 21.2 Remaining Improvements
- [ ] Verify `harness_stats` `avg_confidence` now returns real values (not 0.0)
- [ ] Verify `harness_history` returns FTAL scores for new jobs
- [ ] Add `model_used` field to MCP output (map `endpoint_used` to model name)
- [ ] Add structured code extraction: parse code blocks from result, return separately
- [ ] Test MCP tools from Claude Code: `delegate_task`, `delegate_task_async`, `check_job`
- [ ] Run 10 test delegations, verify all show correct FTAL scores

### 21.3 Evaluation Summary

**Strengths:**
- Clean 3-tier architecture (harness core → REST API → MCP bridge)
- Context augmentation (ArangoDB rules + Qdrant knowledge + teaching docs)
- 89.8% success rate across 512 historical jobs
- $23 cloud cost avoided

**Weaknesses (fixed):**
- ~~Field mapping bug showed Gap=100% for all tasks~~ → FIXED
- ~~FTAL scores not persisted~~ → FIXED
- ~~`analysis` task type rejected~~ → FIXED
- ~~No async polling for long tasks~~ → FIXED
- ~~300s timeout too low for model swaps~~ → FIXED

**Remaining weaknesses:**
- History shows no FTAL scores for pre-migration jobs (DB column didn't exist)
- Raw text output requires manual code extraction
- No streaming support for long-running tasks

**Recommendation:** The FTAL harness is now **usable** for delegation. The critical bugs are
fixed. Use `delegate_task` for quick tasks (<60s), `delegate_task_async` + `check_job` for
anything requiring a model swap.

---

## Regression Testing Strategy

### Test Tiers

| Tier | File | Tests | Data | Purpose |
|------|------|-------|------|---------|
| 1 | `test_regression_e2e.py` | ~37 | Synthetic Mike Vogt | Fast, portable, CI-safe |
| 2 | `test_integration_*.py` | ~98 | Synthetic | Feature-specific integration |
| 3 | `test_realistic_validation.py` | ~20 | ACTUAL OPI/Navitus/Journey | Real-world validation |
| 4 | `test_security.py` | ~15 | Any | Auth bypass, IDOR, input validation |
| 5 | `test_nlp_unit.py` | ~15 | ACTUAL resume text | Scoring signal quality |

### 10x Regression Protocol

After each phase:
1. Run all tiers: `pytest backend/tests/ -v --tb=short`
2. Run 10 consecutive times via `run_regression_10x.sh`
3. Generate report: `roadmap/REGRESSION_V2_10X_REPORT.md`
4. Criteria: 100% pass rate, zero flaky, zero regressions

### Real Data Validation

Tests in Tier 3 use actual career data (user `mvogt99@gmail.com`, id=10):
- 14 resumes, 12 job descriptions
- 7 client projects (OPI: 118 docs, AHEAD: 44, Navitus: 477)
- 3,355 journey sources, 2,221 events, 70 narratives
- 146 job postings, 1 deep profile, 3 role syntheses
- 2 campaigns with 10 posts

---

## Overall Timeline

| Phase | Effort | Dependencies | Focus |
|-------|--------|-------------|-------|
| **15: Critical Fixes** | 1-2 days | None | Security, stability |
| **16: Scoring Quality** | 2-3 days | After 15 | Core value proposition |
| **17: Cleanup** | 2-3 days | After 15 | Dead code, toolchain |
| **18: Test Coverage** | 3-5 days | After 15-17 | Comprehensive validation |
| **19: Knowledge Graph** | 2-3 days | After 18 | Data completeness |
| **20: Enhancements** | 2-4 weeks | After 18 | Optional features |
| **21: FTAL Harness** | 1-2 days | Started | Delegation reliability |

**Minimum viable completion:** Phases 15 + 16 + 18 (7-10 days)
**Full completion:** All phases (4-6 weeks)

---

## Honest Meta-Assessment

### What This Roadmap Addresses

- All 4 CRITICAL issues (C1-C4)
- All 10 SIGNIFICANT issues (S1-S10)
- All 3 MINOR issues (M1-M3)
- Test coverage from 52% to 95%+
- Scoring quality from B- to A-
- Knowledge graph from 42% to 100% populated
- FTAL harness from broken to usable

### What This Roadmap Does NOT Address

- **Actual usage validation** — The biggest gap is that nobody has used this tool for a
  real job search. No roadmap can substitute for that. After Phase 15-16, spend a week
  actually searching for jobs and applying. The usage will reveal what matters.
- **Multi-user scalability** — SQLite is fine for 1-5 users. Beyond that, migrate to
  PostgreSQL. Not worth doing until there are actually multiple users.
- **CI/CD pipeline** — No automated testing on push. Worth adding once the test suite
  is comprehensive (after Phase 18).
- **Monitoring/alerting** — No production monitoring. Appropriate for personal use but
  needs addition if shared with a group.

### The Honest Question

After Phases 15-18, this will be a well-tested, secure, well-scored career management
tool. But the real test is: **does it help you get interviews?**

The recommendation: complete Phase 15 (fixes) and Phase 16 (scoring), then pause
development and use the tool for 2-4 weeks of actual job searching. Let real usage
drive the priority of remaining phases.
