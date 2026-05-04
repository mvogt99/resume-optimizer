# Resume Optimizer — Roadmap

> **Last updated:** 2026-04-20
> **Status: CLOSED — All phases complete 2026-04-20. Phases 1–17, D, E, F, 6a–6d, Options C1–C5 all done.**

---

## ✅ Phase D: Alignment Pipeline — Integration, Audit View, Rewrite Workflow

**Status:** Complete (2026-04-13, commit 300696ce)
**Depends on:** Phases A–C (complete — gap classifier, hybrid scorer, rewrite planner, claim auditor, artifact generator, frontend panels)

### Item 9: Alignment Routes Integration Tests
- [x] Integration test suite for all `/api/alignment/*` endpoints (analyze, artifacts, gaps GET)
- [x] Tests cover happy path, missing resume, invalid job_text, unauthenticated access
- [x] Mutation-verified: break each guard condition and confirm test fails (MG1-MG8)
- [x] 23 tests, all passing

### Item 10: Frontend Claim Audit View
- [x] New `ClaimAuditPanel` component — surfaces `claim_auditor.py` results in the UI
- [x] Shows each claim with risk badge (HIGH/MEDIUM/LOW), claim type, evidence refs, suggested revision
- [x] Summary bar: total claims, supported count, high-risk count, by-claim-type breakdown
- [x] Wire into `OptimizedResumeView` alongside Gap Analysis section
- [x] Backend endpoint: `POST /api/alignment/audit-claims` → `audit_claims(resume_text, candidate_profile)`
- [x] Mutation-verified: MA1 (auth), MA2 (resume_id), MA3 (resume 404 + cross-user)

### Item 11: Resume Rewrite Workflow
- [x] Use `rewrite_targets` from Phase C to drive in-UI resume editing
- [x] "Apply Suggestion" button per rewrite target — patches resume text with suggested template
- [x] Side-by-side diff view: original vs. rewritten section
- [x] Re-run alignment score after applying suggestions to show score improvement
- [x] Backend endpoint: `POST /api/alignment/apply-rewrite` → returns updated resume text + new score
- [x] Mutation-verified: MR1 (auth), MR2 (resume_id), MR3 (target dict), MR4 (resume 404 + cross-user)

**Total Phase D: 48/48 tests passing, 11 mutations verified, browser-verified end-to-end.**

---

## ✅ Phase E: Keyword Equivalency Feature (committed 2026-04-13)

**Status:** Complete (committed alongside Phase D follow-on work)

- [x] `keyword_equivalency.py` — LLM-powered equivalency interview + resume rewrite generation
- [x] `keyword_grouper.py` — semantic keyword grouping with persisted equivalency resolution
- [x] `routes/keyword_routes.py` — 6 endpoints: group, interview, rewrite, save/get/delete equivalencies
- [x] `KeywordGroups.jsx` — keyword grouping UI with rename/move controls
- [x] `KeywordEquivalencyPanel.jsx` — conversational interview → rewrite → apply workflow
- [x] `KeywordMatchReview.jsx` — exact + semantic match confirm/deselect stage
- [x] `KeywordRewriteReview.jsx` — accept/reject/inline-edit rewrite cards
- [x] `keyword_matcher.py` — batch LLM semantic matching of missing keywords vs saved equivalencies
- [x] Bug fixes: `.replace()` → `.replaceAll()`, input validation, DoS protection
- [x] Integration tests with mutation verification

---

## ✅ Phase F: Keyword Intelligence & Scoring Upgrades (2026-04-14)

**Status:** Complete (2026-04-14)

### F1: Scoring correctness — equivalency-aware keyword coverage
- [x] `resume_scorer.py`: equivalency reclassification moved BEFORE `raw_score` calculation
- [x] `keyword_coverage` now reflects equivalencies: 60% equivalency-aware ratio + 40% original NLP overlap
- [x] `SCORE_FLOOR` reduced 20→15 so strong resumes with equivalencies score higher
- [x] `skills_match` already used equivalency expansion (unchanged, correct)
- [x] `score_text_endpoint` in `resume_routes.py` now loads `linkedin_cache.get_raw()` + passes `linkedin_profile` to `score_resume()` — rescore has same endorsement-weighted skills path as initial optimize

### F2: Section completeness regression fix
- [x] `_preserve_section_headers()` in `keyword_equivalency.py` — post-processes LLM `proposed_text` to re-prepend section headers the LLM dropped (e.g., "Professional Summary\n\n")
- [x] Called after `_deduplicate_rewrites()` in `generate_rewrites()`
- [x] Prevents completeness score regression from 100% → 75% when rewrites are applied

### F3: Employer keyword/group filtering
- [x] `_EMPLOYER_KEYWORD_BLOCKLIST` in `nlp_engine.py` — 20 phrases ("company culture", "employee perks", "work life balance", etc.) filtered from `extract_keywords()` before return
- [x] `_is_employer_group()` + `_EMPLOYER_GROUP_SIGNALS` in `keyword_grouper.py` — detects groups describing employer perks/culture and sets `employer_group: true`
- [x] Frontend `KeywordGroups.jsx`: employer groups rendered with amber styling, "Not my responsibility" dismiss button, explanatory note; excluded from missing keywords count

### F4: Group name echo filtering
- [x] `keyword_grouper.py`: keywords whose text equals their group name (case-insensitive) are dropped — these are JD section headers, not skill gaps

### F5: Per-keyword dispute mechanism
- [x] `POST /api/keywords/dispute` in `keyword_routes.py` — sends keyword + resume text to RTX 5090; returns `{covered, confidence, needs_interview, rationale, suggested_equivalent}`
- [x] Auto-saves equivalency if covered with confidence ≥ 0.75
- [x] `KeywordGroups.jsx`: `?` button per chip triggers dispute; chip turns green if covered, ⚠ if needs interview, ⚠ CTA opens equivalency interview for flagged keywords
- [x] `api.jsx`: `disputeKeyword(keyword, resumeText, jobDescription)`

### F6: Rewrite versioning
- [x] `rewrite_suggestions_log` table in `models.py` — stores all generated rewrite sets with user_id, resume_id, job_id, rewrites_json, resolved_keywords_json
- [x] `generate_rewrites_endpoint` auto-saves every generated rewrite set to history
- [x] `GET /api/keywords/rewrite-history` endpoint — returns 20 most recent sessions
- [x] `RewriteHistoryDialog.jsx` — modal dialog with collapsible entries; shows rewrite preview, keywords addressed, "Apply These Rewrites" button
- [x] "Rewrite History" button added to Missing Keywords header in `KeywordGroups.jsx`
- [x] `api.jsx`: `getRewriteHistory()`

### F7: Inline resume editing + live ATS rescore
- [x] `OptimizedResumeView.jsx`: "Edit" button → textarea → "Save & Re-score" triggers `api.scoreResumeText()`
- [x] Live ATS score chip updates in-place after any rewrite or manual edit
- [x] Score delta badge (▲/▼ N pts) shown next to chip
- [x] `AtsImprovementPanel` hidden once a live rescore has run (avoids stale score mismatch)

### F8: Gap Analysis & Audit Claims — buttons fixed
- [x] `resume_routes.py` optimize response now includes `"resume_id": resume.id`
- [x] `OptimizedResumeView.jsx`: `effectiveResumeId = resumeId || data?.resume_id` — resolves null in session-restore flows
- [x] Both buttons now have `title` tooltips explaining what each does
- [x] `handleRunAnalysis` and `handleRunAudit` use `effectiveResumeId` throughout

### F9: Apply confirmation dialog
- [x] `KeywordEquivalencyPanel.jsx`: `handleApplyRewrites` tracks applied section names
- [x] After apply: overlay dialog shows green-checkmarked section list + "Score is being recalculated" note

### New/changed files (Phase F)
| File | Change |
|------|--------|
| `backend/resume_scorer.py` | Equiv reclassification moved before scoring; keyword_score blended with equiv coverage; SCORE_FLOOR 20→15 |
| `backend/nlp_engine.py` | `_EMPLOYER_KEYWORD_BLOCKLIST` frozenset; filter applied in `extract_keywords()` |
| `backend/keyword_equivalency.py` | `_SECTION_HEADER_RE` + `_preserve_section_headers()`; called in `generate_rewrites()` |
| `backend/keyword_grouper.py` | `_EMPLOYER_GROUP_SIGNALS` + `_is_employer_group()`; group-name-echo filtering; `employer_group: true` flag |
| `backend/routes/keyword_routes.py` | Auto-save to `rewrite_suggestions_log`; `GET /rewrite-history`; `POST /dispute` |
| `backend/routes/resume_routes.py` | `resume_id` added to optimize response; `linkedin_profile` passed in `score_text_endpoint` |
| `backend/models.py` | `rewrite_suggestions_log` table |
| `frontend/src/components/OptimizedResumeView.jsx` | `effectiveResumeId`; Gap Analysis buttons fixed; inline edit; live rescore; `AtsImprovementPanel` visibility guard; apply confirmation dialog |
| `frontend/src/components/KeywordGroups.jsx` | Dispute button; employer group dismiss; `RewriteHistoryDialog` mount; `handleDismissGroup`; `handleDisputeKeyword` |
| `frontend/src/components/KeywordEquivalencyPanel.jsx` | `applyResult` state; apply confirmation overlay; equivalency interview for disputed keywords |
| `frontend/src/components/RewriteHistoryDialog.jsx` | New component — browse/re-apply past rewrite sets |
| `frontend/src/services/api.jsx` | `disputeKeyword()`, `getRewriteHistory()` |
| `frontend/src/styles/OptimizedResumeView.css` | Employer group styles, dispute chip styles, apply dialog, rewrite history dialog |

---

## ✅ Roadmap Phases 1–17 (Closed 2026-04-10)

All planned phases (1–17) and the Phase 16 E2E coverage sprint are complete. This roadmap is closed as of 2026-04-10.

| Milestone | Status | Commit |
|-----------|--------|--------|
| Phases 1–7 (core app) | ✅ Complete | f59f2ce, b7bc0e8 |
| Phase 8 (agentic AI, waves 1–3) | ✅ Complete | 4498ac3 |
| Phases 9–14 (knowledge, campaigns, deep profile) | ✅ Complete | 61fac3d |
| Phase 15 (resume recommendation) | ✅ Complete | 4b5b8386 |
| Phase 16 (E2E Playwright coverage, 88 tests) | ✅ Complete | 3365c0c9 |
| Phase 17 (practical usefulness sprint, 15 tasks) | ✅ Complete | 2026-03-14 |

**Test counts:** 200 backend unit tests · 33 recommendation tests · 88 Playwright E2E tests

**Key bugs closed via E2E:** `compareResumes` missing from `api.jsx` (Phase 4 gap, silent catch), sentence-transformer cold-start (warm-up thread added), 4 auth/validation bugs (B1–B4).

For future work, open a new roadmap document.

---

## Current State

Full-featured resume optimization app with NLP processing, LinkedIn integration, Google Drive import, conversational experience extraction, interview preparation, client project documentation analysis, AI journey knowledge mining, LinkedIn marketing campaign system, agentic AI document analysis/interview/compilation pipeline, business outcomes extraction, deep career profile synthesis, and multi-resume recommendation ranking. Flask backend (port 5000) + React frontend (port 3000) managed via `./ro` CLI. All phases complete.

**What works today:**
- User registration and login (SQLite, werkzeug password hashing)
- File upload with real PDF/DOCX/TXT parsing via PyPDF2 and python-docx
- LinkedIn profile import (auto-loaded on startup, 76 skills, 5 jobs, 9 recommendations)
- Job description input with real NLP keyword extraction
- Resume optimization with real similarity scoring and keyword gap analysis
- Endorsement-weighted skills gap analysis with accomplishment/recommendation matching
- Dynamic interview guide with role-specific personas and STAR examples
- Google Drive resume import with re-import, editing, and version management
- Conversational experience extraction with LLM-powered follow-up questions and apply-to-resume
- Client project documentation analysis — GDrive folder crawl, multi-format ingestion, LLM extraction (technical/governance/role), ArangoDB graph approval
- AI journey knowledge mining — workdir/Qdrant/ArangoDB/git mining, timeline construction, skills extraction, STAR narrative synthesis
- Background job management with progress tracking (batch_jobs.py)
- ArangoDB knowledge graph with 16 ro_-prefixed collections
- 9-tab Dashboard UI (Optimize, Builder, Google Drive, Experience Interview, Client Projects, AI Journey, Campaigns, Deep Analysis, AI Agents)
- Resume source tracking in optimization results (LinkedIn/Upload/GDrive/Experience)
- `./ro` CLI for start/stop/restart/status/logs of both services
- Frontend/backend API paths aligned, auth model unified (user-id header)
- **Agentic Document Analysis** (Phase 12) — multi-pass pipeline: classify → context-aware extract → skills extract → correlate → synthesize. Direct RTX 5090 model calls for clean JSON extraction.
- **Agentic Gap Interview** (Phase 12) — cross-source context, gap re-prioritization, LLM followup with project details, STAR bullet extraction, gap tracking metrics
- **Agentic Resume Compilation** (Phase 12) — 6-step pipeline: strategic selection → assemble → rewrite bullets → score → strengthen → compile
- **Business Outcomes Extraction** (Phase 13) — structured outcome extraction (11 types), confidence scoring, pipeline integration as Phase 3d, fully operational across all clients (OPI: 458, AHEAD: 463, Navitus: 3578 outcomes)
- **Smart Document Sampling** (Phase 12a) — `smart_sample_chunks()` replaces 50K truncation with strategic chunk sampling (first 2 + last 2 + evenly spaced middle), no content loss from large files
- **Message Bus Parallel Analysis** (Phase 12b) — Artemis STOMP integration for parallel document extraction, `bus_client.py` + `analysis_worker.py`, sequential fallback when broker unavailable
- **Deep Career Profile** (Phase 14) — `deep_profile.py` synthesizes all sources (3 client projects, 3 WIP projects, LinkedIn, AI journey, resumes) into career phases, higher-order skills, technology mastery, business impacts, and differentiators. Role synthesis with fit scoring. Frontend: DeepAnalysis tab.

**Remaining gaps:** None — roadmap closed 2026-04-10.

**Recently completed:**
- ~~Phase 8 Waves 2-3~~ — **Complete** (commit 4498ac3): ResumeTailor, CoverLetter, InterviewCoach, CareerAdvisor, Orchestrator. 200 tests pass. 5 agent files split into 14 modules.
- ~~Phase 12a: Smart document sampling~~ — **Complete** (smart_sample_chunks replaces truncation)
- ~~Phase 12b: Message bus integration~~ — **Complete** (Artemis STOMP parallel analysis with sequential fallback)
- ~~Phase 13: Business outcomes extraction + downstream wiring~~ — **Complete** (4499 outcomes, graph populated, compiler/interview/campaign/post all wired)
- ~~Phase 14: Deep career profile~~ — **Complete** (synthesis engine + role matching + frontend)
- ~~Phase 15: Resume Recommendation~~ — **Complete** (commit 4b5b8386): Multi-resume compare, LLM rationale, frontend step 2.5, E2E session linking. 33 tests pass (10 scorer + 13 recommender + 10 E2E + rationale).
- ~~Phase 16: E2E Playwright Coverage~~ — **Complete** (commit 3365c0c9): 88 Playwright tests across all frontend flows. **Bug discovered:** `compareResumes` was missing from `api.jsx` (Phase 4 implementation gap) — Dashboard silently fell back to direct optimization, hiding the bug. **Fix:** Added `compareResumes`, `selectRecommendation`, `listRecommendations` to `api.jsx`. Also added sentence-transformer warm-up thread in `app.py` to eliminate cold-start penalty on first optimization.

---

## Phase 1: Replace stub data with LinkedIn profile parsing

**Status:** Complete (Wave 1, commit f59f2ce)
**Priority:** High — removes the biggest gap (demo data → real data)
**Depends on:** Nothing

### Tasks

- [x] Create `backend/linkedin_parser.py` — loads and normalizes LinkedIn JSON into the same schema `process_resume()` returns
- [x] Refactor `utils.py` `process_resume()` — real PDF/DOCX/TXT parsing with NLP keyword extraction
- [x] Refactor `utils.py` `optimize_resume()` — real similarity scoring and keyword gap analysis
- [x] Add `POST /api/import/linkedin`, `GET /api/profile/linkedin`, `POST /api/resume/from-linkedin` endpoints
- [x] Add LinkedIn import button to frontend ResumeUpload component
- [x] Auto-load LinkedIn profile on backend startup

### Data source

Use `working-docs/linkedin/linkedin_profile_merged_api_preferred.json` as the canonical source. Fields available:

| Field | Content |
|-------|---------|
| `full_name` | Mike Vogt |
| `headline` | Data Team Lead, Analytics Architect, Data Platforms Strategist |
| `summary` | Detailed professional summary with expertise areas |
| `current_job` | Principal Technical Consultant at AHEAD |
| `previous_jobs[]` | 4 roles: PwC Director, SPR Exec Director, NVISIA Director, PSC Group VP — all with accomplishment bullets |
| `education_history[]` | Stevens Institute of Technology (MEng), USMMA (BS) |
| `skills_and_endorsements[]` | 70+ skills with endorsement counts |
| `recommendations_received[]` | 9 recommendations with author info and full text |

---

## Phase 2: Real file parsing (PDF/DOCX)

**Status:** Complete (Wave 1, commit f59f2ce)
**Priority:** High — core feature for users who upload resume files
**Depends on:** Phase 1 (shared resume data schema)

### Tasks

- [x] Implement PDF text extraction in `utils.py` using `PyPDF2`
- [x] Implement DOCX text extraction in `utils.py` using `python-docx`
- [x] Implement TXT passthrough (read file content directly)
- [x] Route `process_resume(file_path)` to correct parser based on file extension
- [x] Wire `nlp_engine.py` `extract_keywords()` into the actual extracted text
- [x] Wire `nlp_engine.py` `calculate_similarity()` into optimize via `analyze_resume_vs_job()`
- [x] Wire `nlp_engine.py` `analyze_resume_vs_job()` into optimize endpoint
- [x] Basic section detection via regex heuristics (experience headers, education patterns, date ranges)

---

## Phase 3: Smarter optimization using LinkedIn-specific fields

**Status:** Complete (Wave 2, commit b7bc0e8)
**Priority:** Medium — differentiator feature, makes optimization meaningfully better
**Depends on:** Phase 1

### Tasks

- [x] **Endorsement-weighted skill ranking** — `backend/skills_optimizer.py` `get_endorsement_weighted_skills()` and `weighted_skill_match()`
- [x] **Accomplishment injection** — `get_relevant_accomplishments()` uses NLP similarity to match LinkedIn accomplishments against job descriptions
- [x] **Recommendation snippet matching** — `match_recommendations()` scores recommendation text against job description themes
- [x] **Skills gap analysis** — `analyze_skills_gap()` returns three buckets: `skills_already_shown`, `skills_to_emphasize`, `skills_to_acquire` with coverage percentage
- [x] New endpoint: `GET /api/skills-gap/<resume_id>` — returns the three-bucket analysis with accomplishments and recommendations
- [x] Frontend component: `SkillsGap.js` — SVG progress ring, 3-column layout, endorsement badges, relevance bars

---

## Phase 4: Google Drive multi-format resume ingestion via MCP

**Status:** Complete (Wave 2, commits b7bc0e8 + gap close)
**Priority:** Medium — enables pulling all historical resume versions from Google Drive in any format
**Depends on:** Phase 2 (file parsing needed for PDF/DOCX/DOC/TXT content extraction)

### Context

A `google-docs` MCP server is available with authenticated access to the user's Google Drive. The Resumes folder may contain files in mixed formats: native Google Docs, uploaded PDFs, Word documents (.doc/.docx), and plain text files. The frontend must let the user browse, select, and import resumes in any of these formats for local ingestion, updating, and customization.

### Available MCP tools

| Tool | Purpose |
|------|---------|
| `mcp__google-docs__listFolderContents(folderId)` | List all files in a folder (up to 100) — returns file IDs, names, mimeTypes |
| `mcp__google-docs__readDocument(documentId, format)` | Read **native Google Docs only** as text, markdown, or raw JSON |
| `mcp__google-docs__searchDocuments(query, modifiedAfter)` | Search docs by name/content with date filtering |
| `mcp__google-docs__getDocumentInfo(documentId)` | Get doc metadata (title, created/modified dates, owner) |
| `mcp__google-docs__getFolderInfo(folderId)` | Get folder metadata and sharing status |
| `mcp__google-docs__copyFile(fileId)` | Copy a file within Drive (useful for creating working copies) |

### Format-specific ingestion strategy

| Format | MIME type | Ingestion path |
|--------|-----------|----------------|
| Google Docs | `application/vnd.google-apps.document` | MCP `readDocument(id, format="text")` — direct text extraction |
| PDF | `application/pdf` | Download via Google Drive API (`google-api-python-client`), parse locally with `PyPDF2` |
| DOCX | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | Download via Drive API, parse locally with `python-docx` |
| DOC | `application/msword` | Download via Drive API, parse locally with `python-docx` (or convert to DOCX first) |
| TXT | `text/plain` | Download via Drive API, read content directly |

**Key limitation:** MCP `readDocument` only works on native Google Docs. For PDF/DOCX/DOC/TXT files stored in Drive, the backend must use `google-api-python-client` to download the binary file, then parse it locally using the Phase 2 parsers (PyPDF2, python-docx).

### Tasks

#### Backend — Drive integration

- [x] Add `google-api-python-client` and `google-auth` to `requirements.txt`
- [x] Create `backend/gdrive_service.py` — wraps Drive API for Google Docs export and binary file download
- [x] Implement folder browsing: locate Resumes folder by name or user-configured folder ID
- [x] Implement file listing: return all files with name, format, modified date, size, sorted chronologically
- [x] Implement Google Docs ingestion: export as plain text via Drive API
- [x] Implement binary file download: use Drive API to download PDF/DOCX/DOC/TXT to temp directory
- [x] Route downloaded files through Phase 2 parsers (PyPDF2 for PDF, python-docx for DOCX/DOC, direct read for TXT)
- [x] Add `resume_versions` table to database
- [x] New endpoint: `GET /api/resumes/gdrive` — list all files in Resumes folder with format, date, size
- [x] New endpoint: `POST /api/resumes/gdrive/import` — ingests file locally, stores parsed content in DB
- [x] New endpoint: `GET /api/resumes/versions` — list all locally-ingested resume versions across all sources
- [x] New endpoint: `GET /api/resumes/versions/<version_id>` — get full parsed content for a specific version

#### Frontend — multi-format file picker

- [x] New component: `GoogleDriveImport` — browseable list with format icons, checkbox multi-select, per-file import progress
- [x] Add `GoogleDriveImport` as a new tab in Dashboard alongside existing optimize flow
- [x] Resume versions panel integrated into `GoogleDriveImport` — shows source, format, preview, edit button
- [x] Update `OptimizedResumeView` to show which source version was used (source badge + name)

#### Local editing workflow

- [x] After import, resume content lives locally in SQLite — user can edit/customize without affecting the Google Drive original
- [x] New endpoint: `PUT /api/resumes/versions/<version_id>` — save user edits to an imported resume
- [x] Frontend inline editor: edit modal in `GoogleDriveImport` for tweaking imported resume text
- [x] "Re-import" action: `POST /api/resumes/gdrive/reimport/<version_id>` re-fetches from Google Drive, updates local version

---

## Phase 5: Project management CLI (`ro` command)

**Status:** Complete (commit 7150e6e)
**Priority:** High — quality of life for local development
**Depends on:** Nothing

### Tasks

- [x] Create `ro` bash script at project root (chmod +x)
- [x] `status` subcommand — checks ports 5000/3000 via `ss -tlnp`, shows PIDs
- [x] `start backend` — activates `.venv`, runs `python app.py`, writes PID to `.ro/backend.pid`
- [x] `start frontend` — runs `npx react-scripts start`, writes PID to `.ro/frontend.pid`
- [x] `stop` — SIGTERM then SIGKILL after 5s, cleans PID files, kills port processes
- [x] `restart` — stop then start
- [x] `logs` — `tail -f` on `.ro/{backend,frontend}.log`
- [x] Edge cases: stale PID files, port already in use, missing venv/node_modules

---

## Phase 6: Fix existing integration issues

**Status:** Complete (Wave 1 commit f59f2ce + Wave 2 commit b7bc0e8)
**Priority:** High — required for the app to function end-to-end
**Depends on:** Nothing

### Tasks

- [x] **Fix API path mismatch** — frontend `api.js` paths aligned with backend routes (changed frontend)
- [x] **Unify auth model** — standardized on `user-id` header (removed Bearer token from frontend)
- [x] **Wire interview guide to real data** — `backend/interview_guide.py` generates dynamic personas, STAR examples, and talking points from real resume + LinkedIn data
- [x] **Upgrade password hashing** — replaced SHA-256 with `werkzeug.security.generate_password_hash`

---

## Phase 7: Conversational experience extraction

**Status:** Complete (Wave 2, commits b7bc0e8 + gap close)
**Priority:** High — unlocks the most valuable data source: the user's own memory of recent work
**Depends on:** Phase 1 (LinkedIn data provides the skeleton; conversation fills in the gaps)

### Context

Users know details about their recent work that never make it into a resume — specific projects, clients, technologies used, quantified outcomes, challenges overcome. A conversational AI component should interview the user in natural language to systematically extract this information, structured enough to merge into a resume version.

The user specifies which employer and which client the experience was with, then the AI conducts a guided conversation to pull out as much detail as possible: role, responsibilities, technologies, team size, outcomes, metrics, duration, and lessons learned.

### Conversation flow

```
User: "I want to add my recent project at AHEAD for the BlueCross client"

AI: "Great — let's capture that. What was your role on this project?"
User: "I was the lead data architect."

AI: "What was the primary objective or problem you were solving for BlueCross?"
User: "Migrating their legacy data warehouse to a cloud-native platform on Azure..."

AI: "What technologies and tools did you use?"
User: "Azure Synapse, Data Factory, Databricks, Power BI..."

AI: "Can you quantify any outcomes — cost savings, performance improvements, team size, timeline?"
User: "We reduced query times by 80% and cut their monthly cloud spend by $40K..."

AI: "Were there any notable challenges you overcame?"
User: "The legacy system had 15 years of undocumented schema drift..."

[AI continues until it has a complete picture, then generates structured experience entry]
```

### Extraction targets

The conversation should extract and structure these fields:

| Field | Example |
|-------|---------|
| `employer` | AHEAD |
| `client` | BlueCross |
| `role_title` | Lead Data Architect |
| `project_name` | Cloud Data Platform Migration |
| `duration` | Jun 2023 – Present |
| `objective` | Migrate legacy data warehouse to Azure cloud-native platform |
| `technologies[]` | Azure Synapse, Data Factory, Databricks, Power BI |
| `team_size` | 8 engineers |
| `responsibilities[]` | Led architecture design, mentored 3 junior engineers, ... |
| `outcomes[]` | 80% query time reduction, $40K/month cost savings |
| `challenges[]` | 15 years of undocumented schema drift |
| `skills_demonstrated[]` | Data Architecture, Azure, ETL, Team Leadership |

### Tasks

#### Backend — conversation engine

- [x] Create `backend/experience_chat.py` — `ExperienceExtractor` class managing multi-turn conversation state machine
- [x] Define conversation stages: intro, role, responsibilities, technologies, outcomes, challenges, complete
- [x] Implement LLM-powered follow-up question generation — calls FTAL harness API with template fallback
- [x] Implement structured extraction — `_extract_from_message()` parses user responses by stage, `_split_items()` handles comma/newline/bullet formats
- [x] At end of conversation, generate structured experience JSON via `get_summary()`
- [x] Generate resume-ready text: `_generate_bullet_points()` produces STAR-format bullets from extracted context
- [x] New endpoint: `POST /api/experience/start` — begin a new experience extraction session, returns session ID
- [x] New endpoint: `POST /api/experience/message` — send user message, returns AI follow-up question + extracted fields so far
- [x] New endpoint: `GET /api/experience/summary/<session_id>` — get the structured extraction result
- [x] New endpoint: `POST /api/experience/apply/<session_id>` — merge extracted experience into a resume version
- [x] New endpoint: `POST /api/experience/finalize/<session_id>` — save finalized experience to `extracted_experiences` table
- [x] Add `experience_sessions` table — store conversation history, extracted fields, completion status
- [x] Add `extracted_experiences` table — store finalized structured experiences linked to user

#### Frontend — chat interface

- [x] New component: `ExperienceChat` — conversational UI with chat bubbles, 7-stage progress indicator, live extraction sidebar
- [x] Review panel integrated into `ExperienceChat` — editable/reorderable/deletable bullet points before finalizing
- [x] "Apply to Resume" button after finalization — creates a resume version from extracted experience
- [x] Add "Experience Interview" tab in Dashboard

---

## Phase 8: Agentic AI integration

**Status:** Complete — all 3 waves delivered (commit 4498ac3)
**Priority:** Medium-High — transforms the app from a tool into an autonomous career assistant
**Depends on:** Phases 1-4 (data foundation), Phase 7 (experience extraction)

### Wave 1 (Complete)
- **Job Scout Agent** (`agents/job_scout.py`) — python-jobspy scraping (LinkedIn, Indeed, Glassdoor), NLP keyword scoring + LLM enrichment (culture fit, seniority, growth, skills alignment) via RTX 5090, duplicate URL detection, background job processing
- **Application Tracker Agent** (`agents/app_tracker.py`) — Kanban pipeline (10 stages), SQL analytics (response rate, avg days, top sources), follow-up email generation via RTX 5090, performance pattern analysis via RTX 5090
- **Agent foundation** (`agents/base_agent.py`) — shared LLM call routing, audit logging (`agent_runs` table), user profile loading (LinkedIn + resume + deep profile), profile summarization for LLM prompts
- **17 API routes** (`agents_routes.py`) — search, CRUD, criteria, pipeline, analytics, reminders, follow-up, performance analysis, agent runs, system status
- **3 DB tables** — `job_postings`, `search_criteria`, `agent_runs`
- **Frontend** — AgentDashboard, JobScout (criteria form + results table + detail expand), ApplicationPipeline (Kanban columns + analytics + reminders + follow-up generation)

### Wave 2 (Complete — commit 4498ac3)
- **Resume Tailor Agent** — semantic rewriting, endorsement-weighted skills, ATS compliance check
- **Cover Letter Agent** — targeted cover letters matching company culture and user's voice
- **Interview Coach Agent** — mock interviews with role-specific personas, STAR method evaluation

### Wave 3 (Complete — commit 4498ac3)
- **Career Advisor Agent** — trajectory analysis, market trend intelligence, skills gap with learning recs, salary benchmarking
- **Orchestrator Agent** — multi-agent coordination
- **500-line splits** — 5 agent files split into 14 modules using mixin pattern (commit e8465b2)
- **200 tests pass** across all waves

### Context

The current app is a manual pipeline: user uploads resume, pastes job description, clicks optimize. Agentic AI transforms this into an autonomous system where specialized agents collaborate to handle the entire job search lifecycle — from finding relevant postings to tailoring materials to tracking applications.

Research sources informing this design:
- [Multi-agent resume tailoring workflows](https://medium.com/illumination/one-ats-friendly-resume-for-each-job-description-using-agentic-ai-95-13260b3b9f62)
- [AIHawk autonomous job application agent](https://github.com/feder-cr/Jobs_Applier_AI_Agent_AIHawk)
- [CrewAI LinkedIn Resume Builder](https://github.com/achuajays/LinkedIn-Resume-Builder)
- [JobSpy multi-board job scraper](https://github.com/speedyapply/JobSpy)
- [Steve: LLM-powered career progression chatbot](https://arxiv.org/html/2504.03789v1)
- [Agent Factory for end-to-end career workflows](https://monday.com/blog/ai-agents/best-ai-for-resume/)
- [Agentic framework comparison: LangGraph vs CrewAI](https://dev.to/topuzas/the-great-ai-agent-showdown-of-2026-openai-autogen-crewai-or-langgraph-1ea8)
- [2026 resume trends — evidence-based, ATS-semantic](https://www.resumeadapter.com/blog/resume-trends-2026)
- [AI interview preparation platforms](https://www.clever.cv/blog/ai-powered-interview-preparation-2026)

### Proposed agent architecture

A multi-agent system where each agent has a specialized role. Agents run on local GPU (RTX 5090) to keep costs at $0.00. Framework options: the gateway's existing agent infrastructure, or CrewAI/LangGraph for orchestration.

```
┌─────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR AGENT                            │
│         Coordinates all agents, manages workflow state           │
├─────────┬──────────┬──────────┬───────────┬──────────┬─────────┤
│ Job     │ Resume   │ Cover    │ Interview │ Career   │ App     │
│ Scout   │ Tailor   │ Letter   │ Coach     │ Advisor  │ Tracker │
│ Agent   │ Agent    │ Agent    │ Agent     │ Agent    │ Agent   │
└─────────┴──────────┴──────────┴───────────┴──────────┴─────────┘
```

### Agent descriptions

#### 1. Job Scout Agent
**Purpose:** Autonomously find relevant job postings based on user's profile and preferences.

- Scrape job boards (LinkedIn, Indeed, Glassdoor) using [JobSpy](https://github.com/speedyapply/JobSpy) library
- Accept user criteria: target roles, locations, salary range, remote preference, industries
- Score each posting against the user's LinkedIn profile and resume using `nlp_engine.py` similarity scoring
- Filter and rank results by match score
- Monitor boards on a schedule (daily/weekly) and alert user to new high-match postings
- Store discovered jobs in DB with match scores and status

#### 2. Resume Tailor Agent
**Purpose:** Automatically customize the user's resume for each specific job posting.

- Takes a job description + user's master resume (from any source: LinkedIn, Google Drive, manual upload, experience chat)
- Analyzes job requirements using NER and keyword extraction
- Selects the most relevant experiences, skills, and accomplishments from the user's full profile
- Rewrites bullet points to mirror the job description's language (semantic matching, not just keyword stuffing)
- Applies endorsement-weighted skill prioritization (Phase 3)
- Runs ATS compliance check on the tailored version
- Produces a confidence score: "This resume is an X% match for this posting"
- Can batch-tailor: generate a customized resume for each of the top N job postings from Job Scout

#### 3. Cover Letter Agent
**Purpose:** Generate targeted cover letters that complement the tailored resume.

- Analyzes company culture signals from the job posting and company website
- Pulls relevant recommendation snippets (Phase 3) that align with the role
- Matches user's accomplishments to the posting's stated challenges
- Generates a cover letter in the user's voice (trained on their LinkedIn summary and past writing)
- Multiple tone options: formal, conversational, technical

#### 4. Interview Coach Agent
**Purpose:** Prepare the user for interviews specific to each application.

- Generates role-specific interview questions based on the job description and company
- Creates interviewer personas (HR, hiring manager, technical lead) with different focus areas
- Conducts mock interviews via conversational AI (builds on Phase 7 chat infrastructure)
- Evaluates user's practice answers for STAR method completeness, keyword coverage, and confidence
- Suggests improvements and alternative phrasings
- Generates a "cheat sheet" of key talking points per interview

#### 5. Career Strategy Advisor Agent
**Purpose:** Provide high-level career guidance beyond individual applications.

- Analyze the user's career trajectory from LinkedIn history (title progression, industry moves, skill evolution)
- Identify market trends: which skills are growing in demand for the user's target roles
- Skills gap analysis with learning recommendations (courses, certifications)
- Salary benchmarking based on role, location, and experience level
- Long-term career path suggestions: "Based on your trajectory, consider targeting X roles in Y industry"
- Track and visualize the user's professional growth over time

#### 6. Application Tracker Agent
**Purpose:** Track the full lifecycle of every job application.

- Kanban-style pipeline: Discovered → Tailored → Applied → Phone Screen → Interview → Offer → Accepted/Rejected
- Auto-update status based on email signals (if email integration added later)
- Follow-up reminders: "You applied to X 10 days ago — consider following up"
- Analytics: application volume, response rate, time-to-response, which resume versions perform best
- A/B insights: "Resumes emphasizing skill X got 3x more callbacks than those emphasizing skill Y"

### Implementation approach

#### Framework decision

| Option | Pros | Cons |
|--------|------|------|
| **Gateway agent infrastructure** (existing) | Already built, runs on RTX 5090, proven bus/harness system | Designed for code tasks, would need adaptation |
| **CrewAI** | Purpose-built for role-based multi-agent crews, 44K+ GitHub stars, simple API | External dependency, may not integrate cleanly with existing gateway |
| **LangGraph** | Fine-grained control via state graphs, best for complex workflows with branching | Steeper learning curve, heavier framework |
| **Lightweight custom** | Minimal deps, each agent is a Python class with an LLM client + tools | More code to write, but full control and no framework lock-in |

**Recommended:** Start with lightweight custom agents that call the local RTX 5090 models directly (same pattern as the existing FTAL harness). Migrate to CrewAI/LangGraph later if orchestration complexity warrants it.

#### Local execution

All agents run on local GPU via the existing vLLM infrastructure:
- Planning/strategy tasks → DeepSeek-R1-32B or 70B via swap
- Code/writing tasks → Qwen3-Coder-30B
- Fast classification/NER → smaller model or spaCy

No cloud API spend for agent execution. Cloud models only as fallback if user explicitly approves.

### Tasks

- [ ] Design agent interface contract: `class BaseCareerAgent` with `run(context) -> AgentResult`
- [ ] Implement `JobScoutAgent` — integrate JobSpy for multi-board scraping, scoring pipeline
- [ ] Implement `ResumeTailorAgent` — automated per-posting resume customization
- [ ] Implement `CoverLetterAgent` — targeted cover letter generation
- [ ] Implement `InterviewCoachAgent` — mock interview and prep materials
- [ ] Implement `CareerAdvisorAgent` — trajectory analysis and market intelligence
- [ ] Implement `ApplicationTrackerAgent` — pipeline tracking and analytics
- [ ] Implement `OrchestratorAgent` — workflow coordination, agent dispatch, state management
- [ ] Add `applications` table — track every job application through its lifecycle
- [ ] Add `agent_runs` table — log agent executions for debugging and analytics
- [ ] Frontend: Agent dashboard showing active agents, recent runs, and results
- [ ] Frontend: Job Scout results view with match scores and one-click "Tailor Resume" action
- [ ] Frontend: Application tracker Kanban board
- [ ] Frontend: Interview Coach chat interface (reuses Phase 7 chat UI)

---

## Phase 9: Client Project Documentation Analysis

**Status:** Complete (commit 61fac3d)
**Priority:** High — unlocks the richest source of professional experience data
**Depends on:** Phase 4 (Google Drive integration), ArangoDB graph RAG (gateway infrastructure)
**Build order:** Parallel with Phase 10, prerequisite for Phase 11

### Context

The user has uploaded extensive project documentation for 5-10 clients to Google Drive, organized as one top-level folder per client with sub-folders by project phase, deliverable type, or workstream. Total estimated volume: 100-500 documents across all clients. The user was the overall solution architect and development lead on these engagements.

These documents contain the raw material for a complete professional profile: technical architectures, data governance frameworks, project deliverables, team structures, and outcomes. The system must deeply analyze all documents to extract a structured technical picture and data governance picture per client, store the analysis in ArangoDB graph RAG, and use it to update the user's resume, LinkedIn profile, and LinkedIn marketing campaigns.

**Confidentiality model:** Private use only — full client details stored internally. Sanitization happens manually by the user when crafting public-facing content (LinkedIn posts, resume bullets).

### Architecture

```
Google Drive (per client)
  └── Sub-folders (phase/type/workstream)
       └── Mixed formats: Google Docs, PDF, DOCX, PPTX, XLSX, TXT

           ↓ MCP + Drive API + document_parser.py

Ingestion Pipeline (batch, resumable)
  ├── Recursive folder crawler (MCP listFolderContents)
  ├── Format router (Google Docs → MCP readDocument, binary → Drive download + local parse)
  └── Progress tracker (per-client, per-file status in SQLite)

           ↓ LLM analysis (RTX 5090, $0.00)

Analysis Engine
  ├── Technical Picture Extractor
  │   ├── Technologies & platforms identified
  │   ├── Architecture patterns recognized
  │   ├── Integration points mapped
  │   ├── Data flows documented
  │   └── Delivery outcomes quantified
  ├── Data Governance Extractor
  │   ├── Data classifications identified
  │   ├── Compliance frameworks (SOX, HIPAA, GDPR, etc.)
  │   ├── Security controls documented
  │   ├── PII handling patterns
  │   └── Regulatory requirements cataloged
  └── Role & Impact Extractor
      ├── User's specific contributions
      ├── Team structure and leadership scope
      └── Quantified business impact

           ↓ User approval workflow

ArangoDB Graph RAG
  ├── client_projects (vertex) — one per client engagement
  ├── technologies (vertex) — deduped across all clients
  ├── governance_controls (vertex) — compliance, security
  ├── outcomes (vertex) — quantified achievements
  ├── documents (vertex) — source document metadata
  └── edges: client_used_technology, client_required_governance,
      client_produced_outcome, document_supports_claim

           ↓ JSON export

Per-Client Analysis JSON → Resume update, LinkedIn profile, Campaign content
```

### Tasks

#### Backend — ingestion pipeline

- [x] Create `backend/project_analyzer.py` — orchestrates the full pipeline per client (507 lines)
- [x] Implement recursive Google Drive folder crawler — walks sub-folder tree via Drive API, catalogs all files with path, type, size, modified date
- [x] Implement format-aware batch ingester — routes each file to correct parser:
  - Google Docs → Drive API export as text
  - PDF → Drive API download + PyPDF2
  - DOCX → Drive API download + python-docx
  - PPTX → Drive API download + `document_parser.py` (python-pptx)
  - XLSX → Drive API download + `document_parser.py` (openpyxl)
  - TXT/MD/CSV → Drive API download + direct read
- [x] Implement batch job manager — `batch_jobs.py` with daemon threads, SQLite job tracking, pause/cancel support
- [x] Implement progress tracking — per-client, per-file status with phase and current_file in progress JSON
- [x] Add `client_projects` table — client name, folder ID, analysis status, document count, last analyzed
- [x] Add `project_documents` table — file ID, client ID, file name, mime type, parsed text, analysis status, source path

#### Backend — LLM analysis engine

- [x] Create `backend/technical_extractor.py` — sends parsed document text to RTX 5090 via FTAL harness with structured extraction prompt, returns JSON with technologies, architectures, integrations, data flows, outcomes
- [x] Create `backend/governance_extractor.py` — sends parsed document text to RTX 5090 via FTAL harness with governance-focused prompt, returns JSON with data classifications, compliance frameworks, security controls, PII handling
- [x] Create `backend/role_extractor.py` — extracts user's specific contributions, leadership scope, quantified business impact
- [x] Implement chunking strategy — 6000-char chunks with 500-char overlap via `llm_helper.py`, results merged with deduplication by key field
- [x] Implement cross-document synthesis — aggregate findings from all documents per client into unified client profile via `_synthesize_client()`
- [x] Implement confidence scoring — each extracted fact tagged with 0.0-1.0 confidence

#### Backend — ArangoDB graph storage

- [x] Design ArangoDB graph schema for client knowledge:
  - Vertex collections: `ro_client_projects`, `ro_technologies`, `ro_governance_controls`, `ro_outcomes`, `ro_source_documents`
  - Edge collections: `ro_client_used_tech`, `ro_client_required_governance`, `ro_client_produced_outcome`, `ro_document_supports`
- [x] Implement graph writer — upsert extracted analysis into ArangoDB with SHA-1 deterministic keys and proper edge relationships
- [ ] Implement graph query API — traverse client → technologies, client → governance, technology → clients (reverse lookup)
- [ ] Implement vector search over client analysis — embed analysis text for semantic retrieval during resume/campaign generation

#### Backend — user approval workflow

- [x] New endpoint: `POST /api/projects/<id>/analyze` — kicks off batch analysis for a client folder (returns job ID)
- [x] New endpoint: `GET /api/jobs/<id>/status` — progress, files processed, phase (shared job status endpoint)
- [x] New endpoint: `GET /api/projects/<id>/analysis` — returns extracted technical + governance + role analysis as JSON
- [x] New endpoint: `PUT /api/projects/<id>/analysis` — user edits extracted analysis
- [x] New endpoint: `POST /api/projects/<id>/approve` — locks approved analysis into ArangoDB graph
- [x] New endpoint: `GET /api/projects` — list all clients with analysis status and summary stats
- [x] New endpoint: `POST /api/projects` — create client with folder_id
- [x] New endpoint: `GET /api/projects/<id>/documents` — list documents for client
- [x] New endpoint: `GET /api/projects/folders` — browse Drive folders for client folder selection

#### Frontend — project analysis UI

- [x] New component: `ProjectAnalyzer` — client cards, folder browser modal, progress polling, analysis start (306 lines)
- [x] New component: `ClientAnalysisView` — 3-column grid (technical/governance/role), document list, edit mode, approval button (238 lines)
- [x] New component: `AnalysisApproval` — confirmation dialog before ArangoDB write (36 lines)
- [x] Progress dashboard: per-client progress bars, file-level status, phase display
- [x] Add "Client Projects" tab in Dashboard
- [x] CSS: `ProjectAnalyzer.css` with `proj-` prefix (389 lines)

### Gaps / known limitations

- No OCR — scanned PDFs will have no extractable text
- No image/diagram analysis — architecture diagrams in PNG/JPG won't be understood (text in PPTX slides will be)
- PPTX extraction is text-only, no visual layout context
- Large XLSX files may have limited analysis (formulas not evaluated, just cell values)
- MCP calls are sequential per file — 500 files at ~2s each = ~17 minutes minimum crawl time

---

## Phase 10: AI Journey Knowledge Mining

**Status:** Complete (commit 61fac3d)
**Priority:** High — captures the user's independent AI learning journey as professional experience
**Depends on:** ArangoDB graph RAG (gateway infrastructure), Qdrant (existing)
**Build order:** Parallel with Phase 9, prerequisite for Phase 11

### Context

Since December 2025, the user has been on an intensive AI/agentic AI/cloud economics journey, building the hybrid-ai-windows gateway and its ecosystem. This body of work — documented across 939 files (9.3MB) in `~/models/source/hybrid-ai-windows/workdir/`, plus Qdrant and SurrealDB RAG stores, plus the full git history — represents significant independent professional experience outside of the user's current employer.

The system must mine all of these sources to construct a comprehensive narrative of the user's AI expertise, suitable for resume updates, LinkedIn profile enhancement, and LinkedIn marketing campaigns.

### Data sources

| Source | Location | Volume | Content type |
|--------|----------|--------|--------------|
| Reports | `workdir/reports/` | 275 files | Phase completions, validation proofs, implementation summaries |
| Teaching docs | `workdir/teaching/` | 166 files | AI-generated learning documents, coding/planning/reasoning patterns |
| Session state | `workdir/sessions/` | 42 files | JSON conversation states with timestamps |
| Task specs | `workdir/tasks/` | 30+ files | JSON task specifications with acceptance criteria |
| Qdrant | `hybrid_ai_knowledge` (port 6333) | 3 collections | Embeddings of knowledge, learnings, execution history |
| SurrealDB | Configured (port 8000) | Minimal | Structured data store |
| ArangoDB | `hybrid_ai` (port 8529) | 5 vertex collections | Knowledge items, learnings, rules, teachings, task results |
| Git history | `~/models/source/hybrid-ai-windows/` | 200+ commits since Dec 2025 | Commit messages, file change stats, feature timeline |

### Architecture

```
Source Mining
  ├── Local file harvester (workdir/ tree walker)
  ├── Qdrant collection scanner (3 collections)
  ├── ArangoDB vertex scanner (5 collections)
  ├── SurrealDB query (structured data)
  └── Git log parser (commits, branches, tags since 2025-12-01)

           ↓ Deduplication + timeline reconstruction

Journey Timeline
  ├── Chronological events with source attribution
  ├── Technology adoption timeline
  ├── Milestone achievements
  └── Learning progression arc

           ↓ LLM synthesis (RTX 5090, $0.00)

Knowledge Extraction
  ├── Skills & technologies mastered
  │   ├── AI frameworks (vLLM, FTAL harness, agentic patterns)
  │   ├── Infrastructure (ArangoDB, Qdrant, Artemis, Docker orchestration)
  │   ├── Cloud economics (local GPU vs cloud API cost analysis)
  │   └── Development practices (autonomous testing, teaching loops)
  ├── Quantified achievements
  │   ├── System metrics (20/20 FTAL pass rate, 0 cloud spend, etc.)
  │   ├── Architecture deliverables (8-service Qdrant migration, 4-agent bus system)
  │   └── Performance improvements (128s→12ms health check, etc.)
  ├── Project narratives
  │   ├── Per-phase story arcs with before/after
  │   ├── Problem → approach → outcome format
  │   └── Technical depth appropriate for resume vs LinkedIn
  └── Thought leadership themes
      ├── Local AI economics (RTX 5090 vs cloud)
      ├── Agentic AI patterns (FTAL, teaching loops, autonomous execution)
      └── Enterprise AI architecture (gateway pattern, multi-model routing)

           ↓ User review + approval

ArangoDB Graph RAG (ai_journey subgraph)
  ├── journey_milestones (vertex) — dated achievements
  ├── ai_skills (vertex) — technologies learned/built
  ├── journey_projects (vertex) — major subsystems built
  └── edges: milestone_demonstrated_skill, project_used_skill, milestone_belongs_to_project

           ↓ JSON export

Resume experience entries + LinkedIn profile sections + Campaign content seeds
```

### Tasks

#### Backend — source mining

- [x] Create `backend/journey_miner.py` — orchestrates mining across all sources (686 lines)
- [x] Implement local file harvester — walks `workdir/` tree, classifies each file by directory (report, teaching, session, task, spec, etc.), extracts text and metadata, SHA-256 content hashing
- [x] Implement Qdrant collection scanner — reads records from `hybrid_ai_knowledge`, `hybrid_ai_learnings`, `hybrid_ai_rules` collections with metadata
- [x] Implement ArangoDB vertex scanner — reads `learnings`, `rules`, `teachings`, `incidents`, `task_results` collections
- [x] Implement SurrealDB query — skipped (minimal data, not worth mining)
- [x] Implement git log parser — extracts commits since 2025-12-01 with hash, date, message, file change stats
- [x] Implement cross-source deduplication — SHA-256 content hash grouping, keeps first occurrence

#### Backend — timeline reconstruction

- [x] Implement chronological event builder — groups sources by date, classifies into categories (milestone, achievement, fix, learning, planning, development)
- [x] Implement technology adoption timeline — keyword-based extraction from event text, tracks first/last seen dates and event counts per technology
- [x] Implement achievement quantifier — events classified as milestone/achievement with source attribution
- [x] Implement learning progression arc — `journey_synthesizer.py` generates learning_arc narrative via LLM (Phase 10 quality roadmap Track D)

#### Backend — LLM synthesis

- [x] Create `backend/journey_synthesizer.py` — sends mined data to RTX 5090 via FTAL harness for narrative generation (152 lines)
- [x] Generate resume-ready experience entries — STAR-format bullets with employer="Independent / Personal Project"
- [x] Generate LinkedIn-ready sections — headline addition, summary paragraph, featured project descriptions
- [x] Generate campaign content seeds — themes with post angles and target audience for Phase 11
- [x] Implement theme extractor — `journey_synthesizer.py` generates theme_index (5-10 themes) via LLM (Phase 10 quality roadmap Track D)

#### Backend — storage and APIs

- [x] Design ArangoDB subgraph schema: `ro_journey_milestones`, `ro_ai_skills`, `ro_journey_projects` vertices + `ro_milestone_demonstrated_skill`, `ro_project_used_skill`, `ro_milestone_belongs_to_project` edges
- [x] Implement graph writer for journey data — upserts milestones and skills with demonstrated_skill edges
- [x] New endpoint: `POST /api/journey/mine` — kicks off full mining job (returns job ID)
- [x] New endpoint: `GET /api/jobs/<id>/status` — mining progress (shared job status endpoint)
- [x] New endpoint: `GET /api/journey/timeline` — returns chronological event timeline with pagination and category filter
- [x] New endpoint: `GET /api/journey/skills` — returns all AI skills/technologies with first/last seen dates and event counts
- [x] New endpoint: `GET /api/journey/achievements` — returns events classified as milestone/achievement
- [x] New endpoint: `GET /api/journey/narratives` — returns synthesized experience entries for resume/LinkedIn
- [x] New endpoint: `PUT /api/journey/narratives` — user edits synthesized narratives
- [x] New endpoint: `POST /api/journey/approve` — locks approved narratives into ArangoDB
- [x] New endpoint: `GET /api/journey/sources` — mined sources with optional type filter

#### Frontend — journey dashboard

- [x] New component: `JourneyMiner` — trigger mining, progress bars per source phase, summary stats cards, sub-nav (183 lines)
- [x] New component: `JourneyTimeline` — vertical timeline with category color coding, filters, pagination (123 lines)
- [x] New component: `JourneySkills` — skill grid with counts, sort options, category badges (96 lines)
- [x] New component: `JourneyNarratives` — tabbed view (Resume Entries/LinkedIn/Campaign Seeds), editable cards, per-narrative and batch approval (223 lines)
- [x] Add "AI Journey" tab in Dashboard
- [x] CSS: `JourneyMiner.css` with `journey-` prefix (466 lines)

---

## Phase 11: LinkedIn Marketing Campaign System

**Status:** Complete
**Priority:** High — transforms analyzed knowledge into professional visibility
**Depends on:** Phase 9 (client knowledge), Phase 10 (AI journey knowledge), ArangoDB graph RAG
**Build order:** After Phases 9 + 10

### Context

With deep professional knowledge extracted from client projects (Phase 9) and AI journey (Phase 10), the user needs a system to plan, create, and manage LinkedIn marketing campaigns. The system uses an agentic conversational interview to align on themes and storylines with the user, then generates series of LinkedIn posts grounded in real experience data.

The interaction model is a **chat + canvas hybrid**: chat-based interview for ideation and storyline alignment, then a visual canvas for post sequencing, editing, and campaign timeline management.

**LinkedIn posting approach:** Hybrid — generate polished post drafts for manual copy-paste to LinkedIn now, with the architecture designed so LinkedIn API integration can be plugged in later without rearchitecting.

**Storage:** ArangoDB (graph-linked) — campaigns have edges to client projects, technologies, skills, and journey milestones, enabling knowledge-grounded content generation.

### Architecture

```
Knowledge Sources (Phases 9 + 10)
  ├── Client project analysis (ArangoDB graph)
  ├── AI journey milestones (ArangoDB graph)
  ├── Skills and technologies (ArangoDB graph)
  ├── Quantified achievements (ArangoDB graph)
  └── LinkedIn profile data (SQLite)

           ↓ Campaign interview (Chat phase)

Campaign Interview Engine
  ├── Theme discovery — "What professional story do you want to tell?"
  ├── Audience targeting — "Who should see these posts?"
  ├── Tone calibration — "What voice do you want to use?"
  ├── Storyline arc — "How should the series progress?"
  ├── Knowledge grounding — pull relevant facts from graph RAG
  └── Collaborative refinement — user feedback loop on each aspect

           ↓ Post generation (Canvas phase)

Campaign Canvas
  ├── Visual post timeline / calendar view
  ├── Drag-and-drop post reordering
  ├── Per-post editor with:
  │   ├── Generated draft (LLM-powered, grounded in knowledge graph)
  │   ├── User edit interface
  │   ├── Hashtag suggestions
  │   ├── Character count / LinkedIn formatting
  │   └── Source references (which client/achievement/skill this draws from)
  ├── Campaign-level controls:
  │   ├── Publishing cadence (2x/week, daily, custom)
  │   ├── Theme coherence check
  │   └── Campaign status (draft, ready, in-progress, complete)
  └── Export: copy-to-clipboard, future LinkedIn API publish

           ↓ Storage

ArangoDB (campaigns subgraph)
  ├── campaigns (vertex) — theme, audience, tone, status, created_date
  ├── campaign_posts (vertex) — content, position, hashtags, status, scheduled_date
  ├── post_drafts (vertex) — draft versions with feedback history
  └── edges: campaign_contains_post, post_references_client, post_references_skill,
      post_references_milestone, draft_belongs_to_post
```

### Campaign interview stages

The interview follows a progressive flow, with the AI asking questions and presenting options grounded in the user's actual knowledge graph:

| Stage | AI asks | Draws from |
|-------|---------|------------|
| 1. Theme | "What professional theme should this campaign focus on?" + suggests themes based on knowledge graph | Phases 9+10: client project themes, AI journey themes, skill clusters |
| 2. Audience | "Who are you writing for? Hiring managers? Peers? Industry?" | LinkedIn profile: headline, skills, industry |
| 3. Tone | "What voice? Technical thought leader? Practical builder? Strategic advisor?" | Existing LinkedIn summary, recommendation text |
| 4. Storyline | "How should the series arc? Chronological? Problem→solution? Building blocks?" | Journey timeline, project timelines |
| 5. Post count | "How many posts? Suggest N based on the depth of material available" | Knowledge graph: count relevant facts and stories |
| 6. Content seeds | "Here are the key points per post — review and adjust" | Graph traversal: facts → posts mapping |
| 7. Review | "Here's the full campaign outline — ready to generate drafts?" | All above |

### Multi-campaign support

Users can run multiple campaigns in parallel targeting different themes:

| Example campaign | Theme | Audience | Post count |
|------------------|-------|----------|------------|
| Enterprise Architecture Leadership | 15 years of solution architecture across client engagements | Hiring managers, CTOs | 8-10 posts |
| Local AI Revolution | Building production AI on consumer GPUs ($0 cloud spend) | AI engineers, tech leaders | 6-8 posts |
| Cloud Economics Reality | Cost analysis: local inference vs cloud API | Finance, engineering leadership | 4-5 posts |
| Data Governance in Practice | Real governance frameworks from client projects | Data leaders, compliance | 5-6 posts |

### Tasks

#### Backend — campaign interview engine

- [x] Create `backend/campaign_interview.py` — multi-stage conversation state machine for campaign planning (extends ExperienceChat pattern)
- [x] Implement 7-stage interview flow: theme → audience → tone → storyline → post_count → content_seeds → review
- [x] Implement knowledge graph grounding — at each stage, query ArangoDB for relevant client projects, skills, milestones to suggest options
- [x] Implement LLM-powered question generation — dynamic follow-ups based on user responses (RTX 5090)
- [x] Implement collaborative refinement loop — user can go back to any stage and adjust, with downstream stages updating
- [x] Implement content seed generator — maps knowledge graph facts to individual post topics with suggested talking points

#### Backend — post generation engine

- [x] Create `backend/post_generator.py` — generates LinkedIn post drafts from content seeds + knowledge graph context
- [x] Implement knowledge-grounded generation — each post draft cites specific achievements, technologies, or experiences from the graph
- [x] Implement tone consistency — maintain the user's chosen voice across all posts in a campaign
- [x] Implement hashtag suggestion — generate relevant hashtags based on post content and LinkedIn best practices
- [x] Implement LinkedIn formatting — respect character limits (3000 chars), apply formatting (line breaks, bullet points, emoji placement)
- [x] Implement draft versioning — save multiple draft versions per post with edit history

#### Backend — ArangoDB campaign storage

- [x] Design ArangoDB campaign subgraph schema:
  - Vertex collections: `ro_campaigns`, `ro_campaign_posts`
  - Edge collections: `ro_campaign_contains_post`, `ro_post_references_client`, `ro_post_references_skill`, `ro_post_references_milestone`
- [x] Implement campaign CRUD — create, read, update, delete campaigns with full graph relationships
- [x] Implement post ordering — maintain explicit position ordering within a campaign
- [x] Implement graph traversal queries — "which posts reference this client?", "which skills are covered across all campaigns?"
- [x] Implement campaign analytics — coverage analysis: what percentage of the user's knowledge graph is represented in campaigns

#### Backend — API endpoints

- [x] New endpoint: `POST /api/campaigns/interview/start` — begin campaign planning interview (returns session ID)
- [x] New endpoint: `POST /api/campaigns/interview/message` — send user response, get AI follow-up + current campaign state
- [x] New endpoint: `GET /api/campaigns/interview/<session_id>/state` — current interview state and extracted campaign plan
- [x] New endpoint: `POST /api/campaigns/create` — finalize interview into a campaign with posts
- [x] New endpoint: `GET /api/campaigns` — list all campaigns with status, post count, theme
- [x] New endpoint: `GET /api/campaigns/<id>` — full campaign detail with all posts
- [x] New endpoint: `PUT /api/campaigns/<id>` — update campaign metadata (theme, audience, tone, cadence)
- [x] New endpoint: `POST /api/campaigns/<id>/generate` — generate/regenerate post drafts for the campaign
- [x] New endpoint: `GET /api/campaigns/<id>/posts` — list posts in order
- [x] New endpoint: `PUT /api/campaigns/<id>/posts/<post_id>` — edit post content, reorder
- [x] New endpoint: `POST /api/campaigns/<id>/posts/<post_id>/regenerate` — regenerate single post with optional feedback
- [x] New endpoint: `DELETE /api/campaigns/<id>/posts/<post_id>` — remove post from campaign
- [x] New endpoint: `POST /api/campaigns/<id>/posts` — add a new post to the campaign
- [x] New endpoint: `GET /api/campaigns/<id>/export` — export campaign as copyable text (all posts formatted for LinkedIn)
- [x] New endpoint: `PUT /api/campaigns/<id>/posts/reorder` — bulk reorder posts
- [x] New endpoint: `POST /api/campaigns/<id>/update-interview` — restart interview to update an existing campaign with new knowledge

#### Frontend — campaign interview (Chat phase)

- [x] New component: `CampaignInterview` — chat-based interview UI (extends ExperienceChat pattern), 7-stage progress indicator, knowledge graph suggestions in sidebar
- [x] Sidebar shows: suggested themes from graph, relevant client projects, available achievements — clickable to reference in responses
- [x] Stage-specific UI elements: theme cards, audience selector, tone examples, storyline visualizer

#### Frontend — campaign canvas (Visual phase)

- [x] New component: `CampaignCanvas` — visual post timeline/calendar with drag-and-drop reordering
- [x] New component: `PostEditor` — rich text editor for individual posts with:
  - Generated draft display
  - User edit area
  - Character count and LinkedIn preview
  - Hashtag suggestions (toggleable)
  - Source references panel (which graph nodes this post draws from)
  - "Regenerate" button with optional feedback input
  - Draft version history
- [x] New component: `CampaignTimeline` — calendar/timeline view showing planned post dates based on cadence
- [x] New component: `CampaignList` — all campaigns with status badges, post counts, theme summaries
- [x] Campaign-level controls: publishing cadence selector, theme coherence check (AI verifies all posts align), campaign status workflow (draft → ready → in-progress → complete)
- [x] Export modal: copy all posts as formatted text, copy individual post, future "Publish to LinkedIn" button placeholder

#### Frontend — integration

- [x] Add "Campaigns" tab in Dashboard
- [x] Campaign interview transitions to canvas automatically after interview completion
- [x] "Update Campaign" action reopens interview with existing campaign context
- [x] Cross-link: from campaign post, click source reference to view the client analysis or journey milestone it draws from

### LinkedIn API future-proofing

The export mechanism is designed with a `PublishStrategy` interface:

```python
class PublishStrategy:
    async def publish(self, post_content: str, metadata: dict) -> PublishResult: ...

class ClipboardStrategy(PublishStrategy):     # Phase 11 — copy to clipboard
class LinkedInAPIStrategy(PublishStrategy):   # Future — direct publish via OAuth
```

This allows LinkedIn API integration to be added later by implementing `LinkedInAPIStrategy` without changing any campaign logic.

---

## Phase 12: Agentic Document Analysis Pipeline (3-Stage Enhancement)

**Status:** Complete (all 3 stages verified end-to-end)
**Priority:** High — transforms one-shot analysis into comprehensive, multi-pass, context-aware extraction
**Depends on:** Phase 9 (project analysis foundation)
**Cost:** $0.00 (all LLM calls on local RTX 5090)
**Last updated:** 2026-03-03

### Context

Phase 9's project analysis used one-shot LLM calls per document chunk — no cross-document context, no document classification, and skills only extracted within the technical extractor. Phase 12 transforms this into a multi-stage agentic pipeline where each document is classified, analyzed with cross-document context, comprehensively skills-extracted, and cross-document correlated.

### Stage 1: Agentic Document Analysis — Complete

Enhanced `project_analyzer.py` with a 5-phase pipeline:

```
Phase 1: Crawl Google Drive folder (unchanged)
Phase 2: Ingest documents (unchanged, added dedup guard)
Phase 3a: Classify documents (NEW — LLM classifies each doc by type, extracts entities)
Phase 3b: Context-aware extraction (MODIFIED — inject cross-doc context into tech/gov/role extractors)
Phase 3c: Comprehensive skills extraction (NEW — dedicated skills extractor, 5 categories)
Phase 4: Cross-document correlation (NEW — LLM identifies tech clusters, reinforced accomplishments)
Phase 5: Synthesize (ENHANCED — includes skills + correlation data)
```

#### Files modified/created

| File | Action | Description |
|------|--------|-------------|
| `backend/llm_helper.py` | Modified | Added `call_llm_direct()` for clean JSON extraction (bypasses FTAL harness context injection), `analyze_with_context()` for cross-doc context, `call_llm_harness()` preserved for RAG tasks |
| `backend/skills_extractor.py` | **NEW** | Comprehensive skills extraction across 5 categories: explicit technologies, implied technical skills, soft skills, methodologies, domain expertise. 15-30 skills per chunk. |
| `backend/technical_extractor.py` | Modified | Added `context_summary` parameter, uses `analyze_with_context()` when context available |
| `backend/governance_extractor.py` | Modified | Added `context_summary` parameter |
| `backend/role_extractor.py` | Modified | Added `context_summary` parameter |
| `backend/project_analyzer.py` | Modified | Multi-pass pipeline: `_classify_documents()`, `_build_context_for_doc()`, `_extract_all_skills()`, `_correlate_cross_document()`. Added resumability (skip already-analyzed docs), dedup on ingest, data file skipping, 50K char truncation for large docs. |
| `backend/models.py` | Modified | Added columns: `classification_json`, `skills_json`, `correlation_json`, `cross_source_json` |

#### Key design decisions

- **Direct model calls for JSON extraction:** FTAL harness injects ArangoDB context/teachings that confuse the model for structured output tasks. `call_llm_direct()` calls the model at `localhost:8021` directly via OpenAI-compatible API.
- **50K char truncation:** Very large spreadsheets (1.3M+ chars) are truncated to 50K chars (~9 chunks) to prevent single-doc analysis from taking hours. See Phase 12a for the smart sampling alternative.
- **Data file skipping:** CSV/TSV files over 100K chars (raw claim records, ETL data dumps) are auto-skipped — no useful technical content for resume building.
- **Resumability:** All phases skip already-completed work: ingestion checks `file_id` dedup, classification loads existing `classification_json`, analysis only queries `status='parsed'` docs.

#### Tasks

- [x] Create `skills_extractor.py` with 5-category extraction prompt
- [x] Add `analyze_with_context()` to `llm_helper.py`
- [x] Add `context_summary` parameter to all 3 extractors (tech/gov/role)
- [x] Implement `_classify_documents()` in `project_analyzer.py`
- [x] Implement `_build_context_for_doc()` for cross-document context injection
- [x] Implement `_extract_all_skills()` with dedicated skills extractor
- [x] Implement `_correlate_cross_document()` for technology clusters and skill proficiency
- [x] Add resumability (dedup ingest, skip classified, skip analyzed)
- [x] Add 50K char truncation + data file skipping
- [x] Add schema columns: `classification_json`, `skills_json`, `correlation_json`
- [x] Test with AHEAD Databricks Data Platform folder (118 docs) — classification quality verified
- [x] Test with Navitus folder (477 docs, 8,052 skills extracted)
- [x] Verify skills_json and correlation_json populated — verified for both AHEAD and Navitus
- [ ] End-to-end: analysis → approval → ArangoDB with skills graph

### Stage 2: Agentic Gap Interview — Complete

Enhanced `builder_interview.py` with 5 agentic improvements:

1. **Cross-source context loading** — `_build_cross_source_context()` loads approved project analyses, journey events, extracted experiences. Cached in session's `cross_source_json`.
2. **Gap re-prioritization** — `_reprioritize_gaps()` uses LLM to re-rank remaining gaps after each response by job emphasis, natural follow-on, ATS impact.
3. **LLM followup v2** — `_call_llm_followup_v2()` references specific project details in questions ("I see you worked with Kubernetes at AHEAD..."), probes for STAR specifics (metrics, team size, business impact). Falls back to original method.
4. **LLM bullet extraction** — `_extract_bullets_llm()` produces polished STAR bullets with `has_metrics` and `star_complete` flags. Falls back to regex method.
5. **Gap tracking** — Every `process_message` return includes `gap_tracking: {total_gaps, addressed, remaining, coverage_percent, bullets_with_metrics, bullets_star_complete}`.

#### Tasks

- [x] Implement `_build_cross_source_context()` with DB queries and caching
- [x] Implement `_reprioritize_gaps()` with LLM re-ranking
- [x] Implement `_call_llm_followup_v2()` with project detail references
- [x] Implement `_extract_bullets_llm()` with STAR format output
- [x] Add `gap_tracking` dict to all response paths
- [x] Add `cross_source_json` column to `builder_interview_sessions`
- [x] Test: questions reference AHEAD/Navitus project details — follow-up v2 references project context
- [x] Test: gap re-prioritization after each response — LLM re-ranking working
- [x] Test: extracted bullets are STAR-formatted — all bullets `star_complete: true`

### Stage 3: Agentic Resume Compilation — Complete

New `agentic_compiler.py` with 6-step pipeline:

1. **Strategic selection** — LLM analyzes job description → `{must_have, nice_to_have, ats_keywords}`. Score each content item: similarity (50%) + must-have matches (30%) + ATS keywords (20%).
2. **Section assembly** — Weave interview bullets into matching experience entries (by employer/skill similarity). Only unmatched bullets go to "Additional Experience".
3. **Bullet rewriting** — Batch rewrite (10 per LLM call): action verbs, preserve real metrics, incorporate ATS keywords naturally, don't invent facts.
4. **Score and identify weaknesses** — LLM scores draft 0-100, identifies weaknesses, missing keywords, strongest/weakest sections.
5. **Strengthen weak sections** — If score < 80: find unused source content relevant to weak sections, generate additional bullets.
6. **Final compilation** — Skills ordered by job emphasis (must-have first), experience sorted by strategic score, accomplishments capped at top 10.

#### Tasks

- [x] Create `agentic_compiler.py` with `AgenticCompiler` class
- [x] Implement all 6 pipeline steps with LLM calls
- [x] Integrate into `app.py` `builder_compile` endpoint with fallback to mechanical compilation
- [x] Response includes `compilation_method`, `ats_score`, `weaknesses`, `missing_keywords`
- [x] Test: compile resume with AHEAD/Navitus sources — ATS score 92
- [x] Test: interview bullets woven into experience — bronze/medallion refs in Experience section
- [x] Test: ATS score significantly higher — 92/100 via agentic method

#### Bugs fixed during testing

1. `resume_builder.py:load_project_insights()` — list vs dict format handling for `technical_analysis_json` and `role_analysis_json`
2. `builder_interview.py` — switched from FTAL harness to direct model calls (`call_llm_direct`) to avoid context injection confusing JSON extraction
3. `builder_interview.py` — regex fallback similarity threshold was too permissive (NLP `en_core_web_sm` has no word vectors, matched everything at 0.3); replaced with exact substring match

---

## Phase 12a: Smart Document Sampling (Large File Handling)

**Status:** Complete (2026-03-03)
**Priority:** Medium — prevents content loss from truncation
**Depends on:** Phase 12 Stage 1

### Problem

Phase 12 truncates documents >50K chars to avoid excessive LLM calls. This means a 1.3M char spreadsheet only gets the first 50K chars analyzed — potentially missing important content in later sections.

### Solution: Strategic chunk sampling

Instead of hard-truncating, sample chunks strategically to cover the full document:

```python
def smart_sample_chunks(text, max_chunks=10, chunk_size=6000, overlap=500):
    """Sample representative chunks from a large document.

    Strategy:
    - Always include first 2 chunks (headers, intro, context)
    - Always include last 2 chunks (conclusions, summaries)
    - Sample remaining chunks evenly from the middle
    - Total: max_chunks chunks regardless of document size
    """
    all_chunks = chunk_text(text, chunk_size, overlap)
    if len(all_chunks) <= max_chunks:
        return all_chunks

    # First 2 + last 2 + evenly spaced middle
    sampled = all_chunks[:2]
    middle = all_chunks[2:-2]
    if middle and max_chunks > 4:
        step = max(1, len(middle) // (max_chunks - 4))
        sampled.extend(middle[::step][:max_chunks - 4])
    sampled.extend(all_chunks[-2:])
    return sampled
```

### Benefits

- **No content loss** — every section of the document is represented
- **Predictable cost** — max 10 chunks × 3 extractors = 30 LLM calls regardless of doc size
- **Better quality** — conclusions/summaries often contain the most extractable content
- **Same budget as truncation** — 10 × 6K = 60K chars ≈ 50K truncation

### Tasks

- [x] Implement `smart_sample_chunks()` in `llm_helper.py` — first 2 + last 2 + evenly spaced middle, returns `(chunks, total_count)`
- [x] Replace truncation in `_analyze_documents()` with smart sampling — removes >100K skip and >50K truncation
- [x] Replace truncation in `_extract_all_skills()` with smart sampling
- [x] Replace truncation in `_extract_business_outcomes()` with smart sampling
- [x] Add document coverage metadata to `analysis_json` (`"sampling": {"sampled": true, "chunks_used": N, "chunks_total": M}`)
- [x] Verified: `smart_sample_chunks('x' * 200000)` → 10 of 37 chunks sampled

---

## Phase 12b: Message Bus Integration for Document Analysis

**Status:** Complete (2026-03-03)
**Priority:** Medium — enables parallel extraction and natural backpressure
**Depends on:** Phase 12 Stage 1, existing Artemis message bus infrastructure

### Problem

Current analysis is single-threaded: one document at a time, one chunk at a time, blocking on each LLM call (~15s). For 783 Navitus documents, this means hours of sequential processing.

### Solution: Artemis message bus for parallel document extraction

Leverage the existing ActiveMQ Artemis broker (already running for gateway agent infrastructure) to parallelize document analysis.

### Architecture

```
project_analyzer.py                     Artemis Broker
       │                                     │
       ├─ Phase 1: Crawl (unchanged)         │
       ├─ Phase 2: Ingest (unchanged)        │
       ├─ Phase 3a: Classify (unchanged)     │
       │                                     │
       ├─ Phase 3b: Publish chunks ─────────►│ resume.analysis.chunks
       │   (one message per doc chunk)        │     ├─ {doc_id, chunk_idx, chunk_text, context, extractors: ["tech","gov","role"]}
       │                                     │     ├─ Consumer 1 (RTX 5090 slot 1)
       │                                     │     └─ Consumer 2 (RTX 5090 slot 2, if model supports concurrent)
       │                                     │
       │◄──────────── Results ────────────────│ resume.analysis.results
       │   (one message per completed chunk)  │     {doc_id, chunk_idx, technical: [...], governance: [...], role: [...]}
       │                                     │
       ├─ Phase 3c: Skills (same pattern)    │ resume.analysis.skills
       ├─ Phase 4: Correlation (single call) │
       └─ Phase 5: Synthesize               │
```

### Key design decisions

- **New topic prefix:** `resume.analysis.*` — isolated from gateway agent traffic
- **Consumer group:** `resume-optimizer` — only resume optimizer workers consume these messages
- **Backpressure:** Queue depth monitored, workers pull at their own pace
- **Resumability:** Unprocessed messages survive broker restart (persistent delivery mode)
- **Parallelism:** Even with single RTX 5090 model, can overlap network/DB I/O with LLM inference
- **Future scaling:** Additional GPU workers can subscribe to the same topic

### Implementation plan

1. **Create `backend/bus_client.py`** — lightweight Artemis STOMP client for resume optimizer (reuse gateway pattern from `gateway/app/services/bus/client.py`)
2. **Create `backend/analysis_worker.py`** — consumer that pulls chunk messages, calls extractors, publishes results
3. **Modify `project_analyzer.py`** — Phase 3b publishes chunks to bus instead of processing inline; collects results from results topic
4. **Add progress tracking** — track completed chunks vs total, update `batch_jobs` progress
5. **Fallback:** If Artemis unavailable, fall back to current sequential processing

### Tasks

- [x] Design message schema: chunks `{doc_id, chunk_idx, chunk_text, context, extractors}`, results `{doc_id, chunk_idx, technical, governance, role, skills, outcomes}`
- [x] Create `backend/bus_client.py` — `ResumeAnalysisBus` class, stomp.py v8 API, `_ResultListener`, thread-safe publish/collect, `drain_results()`, singleton `get_analysis_bus()`
- [x] Create `backend/analysis_worker.py` — `handle_chunk()` for inline use, `_WorkerListener` for STOMP consumer, lazy extractor imports, standalone `start_worker()` entry point
- [x] Modify `_analyze_documents()` — bus path via `_analyze_documents_bus()` with per-doc fallback to `handle_chunk()` if publish fails, sequential fallback if Artemis unavailable
- [x] Queue topology: `/queue/resume.analysis.chunks`, `/queue/resume.analysis.results` (persistent delivery)
- [x] Verified: Artemis connection (`hybrid-artemis` port 61613), graceful degradation (bus `is_available()` → False when broker down → sequential fallback)

---

## Phase 13: Business Outcomes Extraction Agent

**Status:** Complete (2026-03-04) — extractor, pipeline integration, and re-extraction all operational. OPI: 458 outcomes (43/118 docs), AHEAD: 463 outcomes (36/44 docs), Navitus: 3578 outcomes (376/477 docs).
**Priority:** High — quantified business impact is the highest-value content for resumes, LinkedIn, and campaigns
**Depends on:** Phase 12 Stage 1 (extraction pipeline), Phase 9 (project analysis), Phase 11 (campaigns)

### Context

The current extraction pipeline captures technologies (what), governance (constraints), roles (who did what), and skills (capabilities). **Missing: quantified business outcomes** — the most impactful content for resume differentiation, LinkedIn credibility, and campaign engagement.

The user specifically asked for this as a "separate agentic AI" that extracts business outcomes for use across resume, LinkedIn content, and campaigns.

### What business outcomes look like

| Outcome Type | Example | Resume Value |
|-------------|---------|--------------|
| Revenue growth | "Increased annual revenue by $4.5M" | Highest — directly demonstrates business impact |
| Cost reduction | "Reduced operational costs by $2.1M through automation" | Very high — shows ROI mindset |
| Efficiency improvement | "Reduced processing time from 48h to 4h (92% improvement)" | High — quantifiable technical achievement |
| Scale achievement | "Processed 10M claims daily across 5 systems" | High — demonstrates enterprise scale |
| Quality improvement | "Reduced defect rate from 12% to 1.5%" | Medium-high — shows quality focus |
| Customer satisfaction | "Improved NPS from 32 to 67" | Medium-high — business empathy |
| Risk reduction | "Reduced compliance audit findings by 75%" | Medium — governance credibility |
| Team/org impact | "Led team of 50 engineers across 3 time zones" | Medium — leadership scope |
| Process automation | "Automated 80% of manual data reconciliation" | Medium — efficiency narrative |
| Capability enablement | "Enabled self-service analytics for 200+ business users" | Medium — transformation story |

### Current gap

`role_extractor.py` captures a `"metrics"` field but it's:
- **Freetext** — not structured (no baseline/outcome/unit breakdown)
- **Role-scoped** — only extracted when attached to a "contribution" or "leadership" entry
- **Not independently scored** — metrics inherit parent confidence
- **Not cross-referenced** — no link to which skills/technologies produced the outcome
- **Not leveraged downstream** — `agentic_compiler.py` treats outcomes as plain text accomplishments

### Dedicated Business Outcomes Extractor

**File:** `backend/business_outcomes_extractor.py` (NEW)

Structured extraction with 11 outcome types, baseline/outcome value pairs, metric units, time periods, beneficiaries, and independent confidence scoring.

**Output schema per outcome:**
```json
{
  "outcome_title": "Reduced operational costs by $2.1M",
  "outcome_type": "cost_reduction",
  "description": "Migrated legacy data pipeline to cloud-native architecture, eliminating $2.1M in annual infrastructure and maintenance costs",
  "metric_name": "annual operational spend",
  "metric_unit": "$",
  "baseline_value": 7000000,
  "outcome_value": 4900000,
  "improvement_magnitude": "$2.1M (30%)",
  "time_period": "Q3 2024",
  "beneficiary": "company",
  "evidenced_by": "quarterly financial report",
  "confidence": 0.91
}
```

### Downstream consumers

#### Resume optimization (`agentic_compiler.py`)
- Rank outcomes by impact magnitude (revenue > cost savings > efficiency)
- Top 5 outcomes become featured accomplishments
- Bullet rewriting emphasizes quantified metrics with action verbs
- ATS keyword injection from metric-rich language

#### LinkedIn profile
- Headline/summary crafted with signature achievements (top 2-3 outcomes)
- Experience entries enriched with quantified impact per role
- Skills section ordered by outcome-driving capability

#### LinkedIn campaigns (Phase 11)
- Campaign seeds grounded in specific business outcomes with real numbers
- Post generation references measurable impact, increasing credibility and engagement
- Outcome-anchored posts: "How we saved $2M by rearchitecting our data pipeline"

#### Interview preparation
- STAR stories anchored in measurable results
- Behavioral question answers seeded with outcome data
- Metric confidence levels guide which stories to emphasize

#### Skills gap analysis
- Rank skills by outcome impact magnitude (which skills drove the biggest results?)
- Outcome-driven prioritization: skills with high-value outcomes emphasized over those without

### Confidence scoring

| Threshold | Action |
|-----------|--------|
| ≥0.85 | Auto-include in resume/LinkedIn (high confidence) |
| 0.70-0.84 | Include but flag for user review |
| 0.60-0.69 | Show in draft but don't auto-include |
| <0.60 | Suppress (too uncertain for professional documents) |

**Confidence boosters:** Baseline + outcome both present (+0.15), metric unit is quantifiable (+0.10), evidenced by formal source (+0.10), mentioned in multiple documents (+0.10).

### Storage

- **SQLite:** `client_projects.business_outcomes_json` column (aggregated per client)
- **Per-document:** `project_documents.outcomes_json` column (per document, pre-aggregation)
- **ArangoDB (optional):** `ro_business_outcomes` vertices, `ro_outcome_driven_by_skill` edges, `ro_outcome_enabled_by_tech` edges

### Pipeline integration

Runs as Phase 3d in `project_analyzer._analysis_worker()`:

```
Phase 3a: Classify documents
Phase 3b: Context-aware extraction (tech/gov/role)
Phase 3c: Comprehensive skills extraction
Phase 3d: Business outcomes extraction (NEW)
Phase 4:  Cross-document correlation (ENHANCED — includes outcome-skill cross-refs)
Phase 5:  Synthesize (ENHANCED — includes outcome aggregation)
```

### Tasks

#### Backend — extractor
- [x] Create `backend/business_outcomes_extractor.py` — LLM prompt with 11 outcome types, structured schema
- [x] Implement `extract_business_outcomes(document_text, context_summary="")` following extractor pattern
- [x] Add `context_summary` support (same as other extractors)

#### Backend — pipeline integration
- [x] Add `_extract_business_outcomes()` method to `project_analyzer.py`
- [x] Insert as Phase 3d in `_analysis_worker()` — combined skills+outcomes extraction
- [x] Add outcome deduplication with confidence boosting for multi-document mentions
- [x] Add `outcomes_json` column to `project_documents` table
- [x] Add `business_outcomes_json` column to `client_projects` table
- [x] Re-extraction support via `reextract_only` mode on `/api/projects/<id>/reanalyze`

#### Backend — downstream wiring
- [x] Enhance `agentic_compiler.py` — rank outcomes by impact type (OUTCOME_TYPE_RANK), feature top 5 in accomplishments (commit ee0fd46)
- [x] Enhance `agentic_compiler.py` — bullet rewriting emphasizes quantified metrics ("LEAD WITH METRICS" rule) (commit ee0fd46)
- [x] Enhance `builder_interview.py` — interview questions reference specific outcomes via outcome_hint param (commit ee0fd46)
- [x] Enhance `journey_synthesizer.py` — campaign seeds grounded in business outcomes via _get_business_outcomes_summary() (commit ee0fd46)
- [x] Enhance `post_generator.py` — posts reference measurable impact + SQLite fallback for outcomes (commit ee0fd46)
- [x] Add outcome-skill cross-referencing in `_correlate_cross_document()` (already implemented — 5 links per project; key fix in commit 1584397)

#### Backend — ArangoDB (optional, if graph active)
- [x] Add `ro_business_outcomes` vertex collection (Phase 13/14, commit 03422a7)
- [x] Add `ro_outcome_driven_by_skill` edge collection (Phase 13, commit 03422a7)
- [x] Add `ro_outcome_enabled_by_tech` edge collection (Phase 13, commit 03422a7)
- [x] Wire into `_write_to_arango()` for approved outcomes (Phase 14, commit 03422a7)
- [x] Add `ro_post_references_outcome` edge collection + edge map routing (commit ee0fd46)

#### Frontend
- [x] Display outcomes in `ClientAnalysisView.js` with confidence badges (Phase 13, commit 03422a7)
- [x] Separate outcomes section in analysis approval UI (Phase 13, commit 03422a7)
- [x] Filter/sort outcomes by type and confidence (commit ee0fd46)
- [x] Expandable "Driven by" skill links per outcome (commit ee0fd46)

---

## Phase 14: Deep Career Profile Synthesis

**Status:** Complete (2026-03-04)
**Priority:** High — unified view of all career data enables intelligent resume tailoring and role matching
**Depends on:** Phase 9 (client projects), Phase 10 (AI journey), Phase 13 (business outcomes)

### Overview

Synthesizes all available career data sources into a comprehensive career profile using LLM analysis. Provides career phase narrative, higher-order skills inference, technology mastery mapping, business impact summary, and unique differentiators. Includes role synthesis with fit scoring against job descriptions.

### Data sources aggregated

| Source | Data |
|--------|------|
| Client projects (3) | OPI (831 skills, 458 outcomes), AHEAD (836 skills, 463 outcomes), Navitus (5605 skills, 3578 outcomes) |
| WIP projects (3) | personaforge, resume-optimizer, linkedin-extractor — technologies, architecture patterns, demonstrated skills from source code |
| LinkedIn profile | 76 skills with endorsements, 5 positions, 9 recommendations |
| AI Journey | 849 events, 55 narratives, timeline with technology adoption dates |
| Resumes | All uploaded resume versions |

### Profile output schema

```json
{
  "career_phases": [{"phase": "...", "period": "...", "narrative": "...", "key_achievements": [...]}],
  "higher_order_skills": [{"skill": "...", "proficiency": "expert|advanced|intermediate", "demonstrated_in": [...], "evidence": [...]}],
  "technology_mastery": [{"technology": "...", "proficiency": "...", "contexts": [...], "years_active": N}],
  "business_impact": [{"domain": "...", "impact_statement": "...", "quantified_results": [...]}],
  "differentiators": [{"angle": "...", "evidence": "...", "positioning": "..."}]
}
```

### Implementation

| File | Purpose |
|------|---------|
| `backend/deep_profile.py` | Core engine — `DeepProfileBuilder` class with `build_profile()`, `synthesize_for_role()` |
| `backend/deep_profile.py` `_get_wip_projects()` | Scans `applications/` directory for active projects, extracts technologies/architecture from source |
| `backend/deep_profile.py` `_scan_project_dir()` | Parses README/CLAUDE.md, requirements.txt, package.json, Python imports for technology signals |
| `backend/deep_profile.py` `_condense_raw_for_llm()` | Dynamic scaling — condenses all sources to fit 28K char LLM context with per-project scaling |
| `backend/deep_profile.py` `_synthesize_profile()` | LLM synthesis with higher-order skills inference (design thinking, agentic AI, graph engineering, etc.) |
| `backend/app.py` | API routes: `POST /api/deep-profile/build`, `POST /api/deep-profile/synthesize-role` |
| `frontend/src/components/DeepAnalysis.js` | Full-page component with career phases, higher-order skills, technology mastery, business impact, differentiators |

### Key design decisions

- **Cross-user project visibility**: `_get_project_data()` fetches ALL completed projects regardless of `user_id` (same person, different auth contexts)
- **Dynamic condensation**: Per-project limits scale inversely with project count (`max_skills = max(10, 30 // n_proj)`) to stay within 28K context
- **WIP project scanning**: No LLM calls — pure filesystem analysis of requirements.txt, package.json, and Python import patterns (18 architecture signal patterns)
- **Higher-order skills**: LLM infers meta-skills (solution architecture, agentic AI design, graph-based knowledge engineering) from journey events and WIP project signals
- **Duplicate elimination**: AHEAD-Databricks (#8) identified as 100% duplicate of OPI (#5) — same 118 Drive files, deleted to prevent double-counting

### Tasks

- [x] Implement `DeepProfileBuilder` class with `build_profile()` and `synthesize_for_role()`
- [x] Implement `_get_wip_projects()` + `_scan_project_dir()` — filesystem scanning for active projects
- [x] Implement `_condense_raw_for_llm()` with dynamic per-project scaling
- [x] Implement `_build_source_summary()` — human-readable data source summary
- [x] Implement `_synthesize_profile()` — LLM synthesis with higher-order skills schema
- [x] Fix `_get_project_data()` to fetch all completed projects (cross-user)
- [x] Add higher-order skills rendering to `DeepAnalysis.js` frontend
- [x] Complete re-extraction of all client projects (OPI, AHEAD, Navitus) with combined skills+outcomes
- [x] Delete duplicate AHEAD-Databricks project (#8)
- [x] Verify role synthesis — 85% fit score for Oshkosh Principal Data Engineer JD
- [x] Wire into Dashboard as "Deep Analysis" tab

---

## Known Gaps — Remediation Tracking

Gaps disclosed in `roadmap/HONEST_ASSESSMENT.md`. Each tracked until addressed or explicitly deferred.

| # | Gap | Status | Remediation |
|---|-----|--------|-------------|
| 1 | 33/40 backend modules without dedicated test files | Deferred | Covered indirectly via integration/E2E/live tests. Dedicated files would add coverage but not new functionality. Track as tech debt. |
| 2 | LLM output quality not evaluated | **Fixed** (Phase 9) | 13 deterministic quality tests (scoring discrimination, content preservation, NLP extraction) + 8 live RTX 5090 tests (semantic assertions, no mocks, no skips). |
| 3 | Live tests skip when services unavailable | **Fixed** (Phase 9) | All `@pytest.mark.skipif` removed from LLM tests. Tests fail (not skip) if LLM unavailable. |
| 4 | Journey miner date extraction bug | **Fixed** (Phase 9) | `_extract_date()` validates YYYY (2000-2099), MM (1-12), DD (1-31). 18 tests covering valid/invalid/edge cases. |
| 5 | Journey miner `_build_timeline` bug | **Fixed** (Phase 7) | `conn.commit()` moved inside `with get_db()` block. Committed in `eeef497`. |
| 6 | FTAL harness returns 422 for simple prompts | Accepted | Harness schema validation rejects prompts without proper task structure. Not a bug — harness designed for structured tasks. |
| 7 | No frontend E2E tests | **Fixed** (Phase 16) | 36 Playwright tests (Phase 8). Expanded to 54 (Phase 9), then 88 (Phase 16): recommendation flow, LinkedIn import, merge mode, skills gap, all 19 tabs, export/download. |
| 8 | No visual export quality verification | **Fixed** (Phase 9) | 10 content verification tests (PDF/DOCX text extraction → headings, skills, employers) + 6 visual regression screenshot baselines. |
| 9 | 4 stub agents (Tailor, Cover Letter, Coach, Advisor) | **Corrected** (Phase 12.2) | All 4 were already fully implemented — "stub" characterization was wrong. Career Advisor now has persistence table. 27 agent E2E tests written. |
| 10 | No error/timeout path tests | **Fixed** (Phase 12.4) | 20 error path tests covering upload, optimization, auth, agent routes, data validation. Found 4 real bugs (see Bug Tracker above). |
| 11 | Register endpoint crashes on None input | **Fixed** (Phase 12.4) | Bug B1 fixed: null check added to auth_routes.py. Test updated from pytest.raises to assert 400. |
| 12 | No input validation on register/JD endpoints | **Fixed** (Phase 12.4) | Bugs B2-B4 fixed: email regex, password min length 8, JD min 50 chars. 2 new tests added (22 total in test_error_paths.py). |
| 13 | Gateway Agents department: NO GOVERNANCE | **Fixed** (Phase 12.5) | 4 test files added (test_coding_agent.py, test_reasoning_agent.py, test_planning_agent.py, test_review_agent.py) — 48 tests covering class attributes, inherited methods, pure logic. |
| 14 | Gateway Observability department: NO GOVERNANCE | **Fixed** (Phase 12.5) | 3 test files added (test_incidents.py, test_watchdog.py, test_cost_monitor.py) — 36 tests covering Pydantic models, classify_incident logic, cost calculations. |
| 15 | `compareResumes` missing from `api.jsx` — Phase 4 implementation gap | **Fixed** (Phase 16) | Dashboard called `api.compareResumes()` which was undefined → TypeError → silent catch block fell back to direct optimization → step 2.5 never rendered in E2E. Fixed by adding all three recommendation API methods to `api.jsx`. Discovered via Playwright E2E. |
| 16 | Sentence-transformer cold-start penalty on first optimization (~3-5s) | **Fixed** (Phase 16) | Background warm-up thread added to `app.py` startup. `_get_st_model()` called in daemon thread; first real user request no longer pays model-load cost. |

---

## Bugs Found — Fix Tracking

Bugs discovered during Phase 12 testing. All must be fixed — no skips, no stubs.

| # | Bug | Severity | File | Found In | Status | Fix |
|---|-----|----------|------|----------|--------|-----|
| B1 | Register endpoint crashes (AttributeError) when email=None | MEDIUM | routes/auth_routes.py | Wave 12.4 | **FIXED** | Added null check: `if not email or not password: return 400` |
| B2 | Register endpoint accepts any email format (no validation) | LOW | routes/auth_routes.py | Wave 12.4 | **FIXED** | Added regex validation `^[^@\s]+@[^@\s]+\.[^@\s]+$` |
| B3 | Register endpoint accepts any password length (no minimum) | LOW | routes/auth_routes.py | Wave 12.4 | **FIXED** | Added `len(password) >= 8` check |
| B4 | JD upload accepts very short text (<50 chars) | LOW | routes/resume_routes.py | Wave 12.4 | **FIXED** | Added `len(job_text.strip()) < 50: return 400` guard |

**Policy:** Each bug fix must include a regression test that fails before the fix and passes after. Tests already exist in `test_error_paths.py` — update assertions from `pytest.raises`/lenient ranges to exact expected behavior after fixing.

---

## Phase 17: Practical Usefulness Sprint

**Status:** Complete (2026-03-14)
**Priority:** CRITICAL — closes gaps that prevent real-world job search use
**Depends on:** Phases 8-14 (all agents + knowledge management + deep profile)

### Overview

Comprehensive gap closure sprint addressing 15 practical usefulness gaps identified via full application audit. Focuses on: wiring disconnected agents into end-to-end workflows, closing data flow silos, adding feedback loops, and improving UX for real job seekers.

**Detailed plan:** [`roadmap/PHASE17_PLAN.md`](PHASE17_PLAN.md)
**Machine-readable state:** [`roadmap/PHASE17_STATE.json`](PHASE17_STATE.json)

### Task Summary (dependency-ordered execution)

| # | Task | Severity | Status |
|---|------|----------|--------|
| 17.01 | Wire Resume Tailor agent routes + frontend | CRITICAL | Complete (9 tests) |
| 17.02 | Orchestrated apply workflow (Scout → Tailor → CL → Track) | CRITICAL | Complete (7 tests) |
| 17.03 | Interview Coach linked from pipeline stage transitions | MEDIUM | Complete (5 tests) |
| 17.04 | Cover Letter prompt on pipeline "applied" transition | MEDIUM | Complete (4 tests) |
| 17.05 | Feedback loop: application outcomes → optimization scoring | HIGH | Complete (10 tests) |
| 17.06 | Cross-posting JD analysis: skill demand patterns | HIGH | Complete (6 tests) |
| 17.07 | Experience extraction → Resume Builder auto-populate | HIGH | Complete (6 tests) |
| 17.08 | Salary intelligence: surface compensation data | HIGH | Complete (4 tests) |
| 17.09 | Deep Profile feeds into Job Scout scoring | MEDIUM | Complete (4 tests) |
| 17.10 | Follow-up reminder notifications (browser + badge) | HIGH | Complete (3 tests) |
| 17.11 | Skills interview results → optimization scoring | MEDIUM | Complete (7 tests) |
| 17.12 | Cross-session optimization learning | MEDIUM | Complete (9 tests) |
| 17.13 | Ready-to-apply checklist per posting | MEDIUM | Complete (4 tests) |
| 17.14 | Campaign post engagement tracking + feedback | MEDIUM | Complete (5 tests) |
| 17.15 | Guided new-user onboarding flow | MEDIUM | Complete (8 tests) |

**User gate:** Each task gets an honest assessment + blocking approval before proceeding.
**Delegation:** Backend → RTX 5090 ($0.00). Frontend → Expert AI.

---

## Future Ideas (Unprioritized)

- Email integration for auto-tracking application status from inbox
- Networking assistant agent — draft outreach messages to hiring managers and mutual connections
- LinkedIn API OAuth integration — programmatic publishing from campaign system (requires LinkedIn developer app approval)
- OCR pipeline for scanned PDFs — Tesseract or cloud OCR for image-based documents in Phase 9
- Architecture diagram analysis — vision model (GPT-4V or local multimodal) to extract insights from architecture diagrams in PPTX/PNG
- Auto-suggest new campaigns — based on new knowledge added (new client analysis, new AI milestone), suggest campaign topics
