# Session Handoff — 2026-03-12

**Purpose:** Full context for a new Claude session to resume work on the resume-optimizer app.

---

## What This App Is

ATS-friendly resume optimization web app. Flask backend (Python 3.13, NLP via spaCy/NLTK) + React 18 SPA frontend. Users upload resumes, paste job descriptions, get optimized resumes with ATS compatibility scores. Extended with LinkedIn integration, Google Drive import, conversational experience extraction, client project analysis, AI journey mining, LinkedIn campaign system, deep career profile synthesis, and a 6-agent career assistant system.

**Location:** `/home/mike/models/source/hybrid-ai-windows/applications/resume-optimizer/`

---

## What Was Just Completed (This Session)

### Phase 14.7: Bug Fixes + Code Quality Hardening

**Commit:** `e4c64ac` (pushed to main)

4 waves of fixes:

| Wave | What | Files Changed |
|------|------|---------------|
| 7.1 | Fixed 3 backend test failures | `tests/conftest.py` (agent_setup fixture), `tests/test_route_experience.py` (table name) |
| 7.2 | Replaced 11 `datetime.utcnow()` → `datetime.now(timezone.utc)` | `deep_profile.py`, `batch_jobs.py`, `deep_interview.py`, `arango_client.py` |
| 7.3 | Eliminated 57 frontend act()/Router v7 warnings | `App.jsx`, 8 test files in `frontend/src/__tests__/` |
| 7.4 | Added logging to silent exceptions, CI markers, Journey re-mine button | `skills_interview.py`, `post_generator.py`, `pytest.ini`, 6 test files, `JourneyMiner.jsx`, `api.jsx` |

**Result:** 0 failures, 0 warnings, Grade A maintained.

---

## Current Quality Metrics

```
qa_audit Grade: A
Files: 95 | Tests: 1645
Tiers: A=51 B=44 C=0 D=0 F=0
GATE: PASS

Backend: 1645 tests (1565 non-LLM pass, 139 LLM-deselectable, 1 skipped)
Frontend: 248 tests, 0 warnings
Deployment: 12 tests
```

---

## All Completed Phases (1–14)

| Phase | Name | Key Result |
|-------|------|-----------|
| 1 | LinkedIn profile parsing | Real data replaces all stubs |
| 2 | Real file parsing | PDF/DOCX/TXT via PyPDF2, python-docx |
| 3 | Smart optimization | Endorsement-weighted skills, accomplishment matching |
| 4 | Google Drive import | OAuth, folder browsing, version management |
| 5 | CLI management | `./ro` start/stop/restart/status/logs |
| 6 | Integration fixes | Auth unified, API paths aligned, interview guide |
| 7 | Experience extraction | 6-stage conversation state machine, LLM follow-up |
| 8 | Agentic AI (Wave 1) | Job Scout (scraping+scoring) + App Tracker (Kanban) |
| 9 | Project analysis | GDrive crawl, multi-format ingestion, ArangoDB graph |
| 10 | Journey mining | workdir/Qdrant/ArangoDB/git mining, timeline, narratives |
| 11 | Campaign system | 7-stage interview, post generation, ArangoDB subgraph |
| 12 | Production readiness | 373 tests, Docker deployment, gateway governance |
| 13 | High-impact features | Templates, job scraper, LinkedIn gen, analytics, 27 endpoints |
| 14 | Deep profile + hardening | Profile synthesis, 555 tests, quality gate A, bug fixes |

---

## What's Left

### Open Roadmap Items

1. **Phase 8 Orchestrator Agent** (Medium priority) — multi-agent coordination to chain Scout→Tailor→Cover Letter→Coach. All 6 individual agents are implemented. Missing: `backend/agents/orchestrator.py` + 2-3 API routes + frontend workflow UI.

2. **Frontend Agent UIs** (Low priority) — Interview Coach chat UI and Cover Letter generator UI. Pattern established by ExperienceChat. Currently API-only.

### Tech Debt

- PyPDF2 → pypdf migration (1 deprecation warning)
- content_validated_pct at 27.3% (target: 50%)
- 33 backend modules without dedicated test files (covered indirectly)
- LinkedIn OAuth deferred ($99/month API)

### Future Ideas (none started)

Resume version diffing, email integration, networking assistant, salary negotiation, portfolio generator, campaign performance tracking, OCR pipeline, architecture diagram analysis.

**Full details:** `roadmap/WHATS_LEFT.md`

---

## Architecture Quick Reference

### Backend (`backend/`)

| File | Purpose |
|------|---------|
| `app.py` | Flask routes — 41 `/api/*` endpoints, CORS, file upload |
| `agents_routes.py` | Flask Blueprint — 17 agent routes (scout, pipeline, analytics) |
| `models.py` | Raw SQLite with static CRUD methods, auto-creates `database.db` |
| `nlp_engine.py` | spaCy + NLTK keyword extraction, similarity scoring |
| `utils.py` | Resume parsing (PDF/DOCX/TXT), optimization logic |
| `smart_llm.py` | LLM routing — prefers local RTX 5090, falls back to FTAL harness |
| `deep_profile.py` | Career profile synthesis from all sources |
| `experience_chat.py` | 6-stage conversation state machine |
| `campaign_interview.py` | 7-stage campaign planning state machine |
| `journey_miner.py` | Multi-source knowledge mining |
| `arango_client.py` | ArangoDB graph client, 16 `ro_`-prefixed collections |
| `batch_jobs.py` | Background job manager (daemon threads + SQLite) |
| `agents/__init__.py` | Agent factory — `get_job_scout()`, `get_app_tracker()`, `get_agent(type)` |
| `agents/base_agent.py` | BaseCareerAgent — LLM routing, audit logging |

### Frontend (`frontend/`)

React 18 + React Router 6 + Axios. Vite dev server (port 3000).

9-tab Dashboard: Optimize, Builder, Google Drive, Experience Interview, Client Projects, AI Journey, Campaigns, Deep Analysis, AI Agents.

API client: `frontend/src/services/api.jsx` — Axios instance, base URL `http://localhost:5000/api`.

### Testing

| Item | Location |
|------|----------|
| Backend test fixtures | `backend/tests/conftest.py` |
| Shared test data | `backend/tests/test_helpers.py` (RESUME_TEXT, JD_TEXT, LINKEDIN_PROFILE) |
| LLM test marker | `backend/pytest.ini` — `llm_required` marker |
| Quality audit | `backend/scripts/qa_audit.py` |
| Frontend tests | `frontend/src/__tests__/*.test.jsx` (Vitest + React Testing Library) |

### Auth Model

Simple `user-id` header (no JWT/sessions). Password hashing via werkzeug.

### Database

SQLite (`backend/database.db`), auto-created by `models.py`. 20+ tables including `users`, `resumes`, `resume_versions`, `job_descriptions`, `experience_sessions`, `batch_jobs`, `client_projects`, `journey_sources`, `campaigns`, `campaign_posts`, `agent_runs`, `scout_postings`, etc.

---

## Infrastructure

| Service | Port | Purpose |
|---------|------|---------|
| Flask backend | 5000 | API server |
| React frontend | 3000 | SPA dev server |
| ArangoDB | 8529 | Knowledge graph (root/hybrid_ai_root) |
| Qdrant | 6333 | Vector DB for RAG |
| Artemis | 61613 | STOMP message bus |
| RTX 5090 | 8021 | Local LLM (Qwen3-Coder-30B-AWQ) |
| Gateway | 8000 | FTAL harness, model routing |

---

## How to Verify

```bash
cd /home/mike/models/source/hybrid-ai-windows/applications/resume-optimizer
source .venv/bin/activate

# Backend (non-LLM, ~50 min)
cd backend && python -m pytest tests/ -m "not llm_required" -q --tb=short
# Expected: 1565 passed, 0 failed, 139 deselected

# Frontend (~30 sec)
cd ../frontend && npx vitest run
# Expected: 248 passed, 0 warnings

# Quality gate
cd ../backend && python scripts/qa_audit.py
# Expected: Grade A, A=51 B=44 C=0 D=0 F=0, GATE: PASS
```

---

## Key Documents

| Document | Path |
|----------|------|
| Project CLAUDE.md | `CLAUDE.md` (comprehensive — architecture, API endpoints, all phases) |
| Roadmap | `roadmap/ROADMAP.md` |
| Session state (JSON) | `roadmap/SESSION_STATE.json` |
| What's left | `roadmap/WHATS_LEFT.md` |
| Honest assessments | `roadmap/HONEST_ASSESSMENT-phase-*.md` (per-phase) |
| Daily assessments | `roadmap/assessments/2026-03-*.md` |

---

## RTX 5090 Delegation Rules

This project follows the F/T/A/L workflow:
- **Expert AI (Claude):** Validation and teaching ONLY — no code generation, no execution
- **RTX 5090:** All code generation AND execution
- **Conceptual teaching:** Never provide exact code — teach HOW to solve
- **Exception:** If RTX 5090 unavailable, ASK user permission before using cloud tokens

See root `CLAUDE.md` for full delegation protocol.

---

## Commit History (Recent)

```
e4c64ac fix(resume-optimizer): Phase 14.7 — bug fixes, deprecation cleanup, CI markers, 0 failures
c3e0dc2 data(resume-optimizer): add Dusan Roganovic LinkedIn recommendation
0a927ae feat(resume-optimizer): Phase 13 — high-impact features, 131 new tests, 27 endpoints
44b9fe8 feat(resume-optimizer): Phase 12 — production readiness, 373 new tests, Docker deployment
e30256d docs(resume-optimizer): rewrite HONEST_ASSESSMENT.md with substantive detail
e08b939 feat(resume-optimizer): Phase 11 + 11.5 — all 5 gaps resolved, gateway D+ → B+
```

---

## Grade History

```
2026-03-06  D+  458 tests  (pre-mock-deletion, 117 mocked tests)
2026-03-07  C+  362 tests  (post-mock-deletion, 0 mocks)
2026-03-07  B-  400 tests  (Phase 2, all Tier-F → Tier-A)
2026-03-08  B   489 tests  (Phase 3 waves)
2026-03-08  A-  489 tests  (Phase 3 Wave 4)
2026-03-09  A   602 tests  (Phases 4-5)
2026-03-09  A   696 tests  (Phases 6-8)
2026-03-10  A   912 tests  (Phases 10-11.5)
2026-03-10  A-  971 tests  (Phase 12)
2026-03-11  A-  1090 tests (Phase 13)
2026-03-11  A   1645 tests (Phase 14 Waves 14.1-14.6)
2026-03-12  A   1645 tests (Phase 14.7 — bug fixes, 0 failures)
```
