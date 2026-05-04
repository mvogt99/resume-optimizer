# Phase 12: Complete Gap Resolution — Production Readiness

**Date:** 2026-03-10
**Baseline:** Phase 11.5 (commit e08b939), 912 backend tests, Grade A, Gateway B+
**Scope:** 15 of 16 HONEST_ASSESSMENT gaps resolved. Only LinkedIn OAuth deferred.
**Delegation:** E2E tests, error path tests, gateway governance tests, Docker files, React unit tests — ALL delegated to RTX 5090 via direct curl to port 8021.
**Assessment tracking:** Per-wave HONEST_ASSESSMENT files: `HONEST_ASSESSMENT_12_<wave>.md`
**Authorization:** User authorizes all commands. Prompt only at phase gates or clarifying questions.

---

## Audit Findings (Pre-Plan)

### Stub Agent Reality Check

The 4 "stub" agents are **more complete than documented**:

| Agent | HONEST_ASSESSMENT Status | Actual Status | LOC | Routes Wired | DB Tables |
|-------|--------------------------|---------------|-----|-------------|-----------|
| Resume Tailor | "Skeleton code" | 90% ready | 188 | 2 (`/api/agents/tailor/`) | resume_versions ✓ |
| Cover Letter | "Template-based" | 95% ready | 276 | 6 (`/api/agents/cover-letter/`) | cover_letters ✓ |
| Interview Coach | "No mock interview" | 95% ready | 469 | 5 (`/api/agents/coach/`) | coach_sessions ✓, coach_messages ✓ |
| Career Advisor | "Placeholder class" | 50% ready | 176 | 3 (`/api/agents/advisor/`) | **NONE** ❌ |

All 4 inherit from `BaseCareerAgent`, route through RTX 5090 via `call_llm()`, and have routes in `agents_routes.py`. Real gaps: Career Advisor lacks persistence, none have E2E tests, none have frontend React components.

### Frontend Component Inventory

38 React components across 14 phases. **Zero Jest/RTL tests exist.** Only Playwright E2E (7 spec files, 36 tests). Current test infrastructure:
- Build: Vite 7.3.1 (NOT Create React App)
- Dependencies: React 18, React Router 6, Axios
- Missing: `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, `vitest`

### Docker Infrastructure

- Parent project has 30+ services across 10+ profiles (ArangoDB, Qdrant, Artemis all defined)
- Resume-optimizer has **zero** Docker config — no Dockerfile, no docker-compose.yml, no .dockerignore
- Backend creates SQLite in CWD — needs volume mount for persistence
- Frontend builds to `build/` via `npm run build`

---

## Wave 12.1: Quick Wins (dependencies, CI, D-tier fix)

**Effort:** ~2 hours | **Tests added:** ~25 | **User gate:** No
**Assessment file:** `roadmap/HONEST_ASSESSMENT_12_1.md`

### 12.1.1 — Fix requirements.txt

Add missing dynamic imports to `backend/requirements.txt`:
```
qdrant-client>=1.7.0
stomp.py>=8.1.0
```
**Verify:** `pip install -r requirements.txt && python -c "import qdrant_client; import stomp; print('OK')"`

### 12.1.2 — Make LLM Tests CI-Friendly

Convert `require_harness` from hard-fail to skip-friendly.

**File:** `backend/tests/test_helpers.py` (lines 222-231)

Change:
```python
def require_harness():
    if not HARNESS_AVAILABLE:
        pytest.fail("FTAL harness is NOT running...")
```

To:
```python
def require_harness():
    if os.environ.get("REQUIRE_LLM_TESTS", "").lower() == "true":
        pytest.fail("FTAL harness is NOT running (REQUIRE_LLM_TESTS=true)")
    pytest.skip("FTAL harness not available — skipping LLM test")
```

**File:** `backend/tests/conftest.py` (lines 191-198) — same change in fixture.

**Impact:** 9 test files (50+ tests) skip gracefully in CI without GPU. Set `REQUIRE_LLM_TESTS=true` for GPU CI to enforce.

### 12.1.3 — Upgrade test_output_quality.py from D to B+

**File:** `backend/tests/test_output_quality.py` (290 lines, 15 tests, 18 assertions → D-tier)

Add ~15 content-validating assertions across existing tests + 5 new error-path tests:

**New assertions in existing tests:**
1. Score breakdown values are floats between 0.0 and 1.0
2. `keyword_coverage` > 0.3 for high-match scenario
3. `semantic_similarity` > 0.2 for high-match scenario
4. `skills_match` > 0.2 for high-match scenario
5. Zero-match `keyword_coverage` < 0.1
6. Keywords extracted from JD ≥ 5 items
7. Each keyword is a non-empty string
8. Matching keywords are subset of extracted keywords
9. Missing keywords + matching keywords = total JD keywords
10. Section detection returns dict with string values

**New tests:**
1. `test_optimize_empty_jd` — empty/whitespace JD returns 400
2. `test_optimize_no_resume` — nonexistent resume_id returns 404
3. `test_score_breakdown_sums_to_total` — weighted components sum ≈ total score
4. `test_keywords_are_lowercase_normalized` — no duplicates from case variation
5. `test_optimize_preserves_original` — original resume text unchanged after optimization

**Target:** 20 tests, 35+ assertions → B+ tier (>50% content coverage)

### 12.1.4 — Fix Silent Infrastructure Skips

**File:** `backend/tests/conftest.py`

Add session-end reporter for skipped infrastructure tests:
```python
@pytest.fixture(autouse=True, scope="session")
def report_skipped_infrastructure(request):
    yield
    terminal = request.config.pluginmanager.get_plugin("terminalreporter")
    skipped = [r for r in terminal.stats.get("skipped", [])]
    infra_skips = [s for s in skipped if "harness" in str(s) or "arango" in str(s) or "qdrant" in str(s)]
    if infra_skips:
        print(f"\n⚠️  WARNING: {len(infra_skips)} infrastructure tests SKIPPED (services down)")
        for s in infra_skips:
            print(f"   - {s.nodeid}")
```

---

## Wave 12.2: Career Advisor Agent — Full Production

**Effort:** ~4 hours | **Tests added:** ~20 | **User gate:** No
**Delegation:** Career Advisor persistence code → RTX 5090. E2E tests → RTX 5090.
**Assessment file:** `roadmap/HONEST_ASSESSMENT_12_2.md`

### 12.2.1 — Add Missing Database Tables

**File:** `backend/models.py`

Add `career_analyses` and `learning_progress` tables in `init_db()`:
```sql
CREATE TABLE IF NOT EXISTS career_analyses (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    analysis_type TEXT NOT NULL,  -- trajectory, roadmap, recommendations
    target_role TEXT,
    result_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS learning_progress (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    analysis_id TEXT,
    phase INTEGER,
    skill TEXT NOT NULL,
    status TEXT DEFAULT 'planned',  -- planned, in_progress, completed
    start_date TEXT,
    target_date TEXT,
    completion_date TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (analysis_id) REFERENCES career_analyses(id)
);
```

### 12.2.2 — Add Persistence to Career Advisor (RTX 5090)

**File:** `backend/agents/career_advisor.py`

Delegate to RTX 5090 — add methods:
- `save_analysis(user_id, analysis_type, result, target_role=None)` — persist to `career_analyses`
- `get_history(user_id, analysis_type=None)` — list past analyses
- `get_analysis(analysis_id, user_id=None)` — retrieve specific analysis
- `compare_analyses(analysis_id_1, analysis_id_2)` — diff two analyses
- `save_learning_progress(user_id, analysis_id, skill, status)` — track milestone
- `get_learning_progress(user_id, analysis_id=None)` — retrieve progress

Modify `analyze_career`, `get_skills_roadmap`, `get_role_recommendations` to auto-persist.

### 12.2.3 — Add Routes for Persistence (RTX 5090)

**File:** `backend/agents_routes.py`

Add routes:
- `GET /api/agents/advisor/history` — list analyses
- `GET /api/agents/advisor/analysis/<id>` — get specific
- `POST /api/agents/advisor/analysis/<id>/compare/<id2>` — compare
- `POST /api/agents/advisor/learning-progress` — save progress
- `GET /api/agents/advisor/learning-progress` — get progress

### 12.2.4 — E2E Tests for Career Advisor (RTX 5090)

**File:** `backend/tests/test_career_advisor_e2e.py` (~20 tests)

Delegate test generation to RTX 5090. Tests use real Flask test client + SQLite:
1. `test_analyze_career_returns_trajectory`
2. `test_analyze_career_persists_to_db`
3. `test_skills_roadmap_returns_phases`
4. `test_skills_roadmap_persists`
5. `test_role_recommendations_returns_5`
6. `test_role_recommendations_have_fit_score`
7. `test_history_lists_all_analyses`
8. `test_history_filters_by_type`
9. `test_get_analysis_by_id`
10. `test_compare_two_analyses`
11. `test_save_learning_progress`
12. `test_get_learning_progress`
13. `test_learning_progress_status_transitions`
14. `test_analyze_with_deep_profile_context`
15. `test_analyze_without_profile_fallback`
16. `test_invalid_analysis_id_404`
17. `test_unauthorized_access_denied`
18. `test_roadmap_target_role_stored`
19. `test_multiple_roadmaps_different_roles`
20. `test_analysis_result_json_structure`

---

## Wave 12.3: Remaining Agent E2E Tests (RTX 5090)

**Effort:** ~3 hours | **Tests added:** ~45 | **User gate:** No
**Delegation:** ALL test files delegated to RTX 5090.
**Assessment file:** `roadmap/HONEST_ASSESSMENT_12_3.md`

### 12.3.1 — Resume Tailor E2E Tests (RTX 5090)

**File:** `backend/tests/test_resume_tailor_e2e.py` (~15 tests)

1. `test_tailor_creates_version` — POST creates resume_version
2. `test_tailor_version_has_ats_score` — version includes score
3. `test_tailor_keywords_from_jd` — tailored resume contains JD keywords
4. `test_tailor_preserves_experience` — original experience sections retained
5. `test_tailor_updates_posting_reference` — job_postings.tailored_version_id set
6. `test_get_tailored_returns_version` — GET retrieves tailored version
7. `test_tailor_missing_resume_400` — no resume uploaded → error
8. `test_tailor_missing_posting_404` — invalid posting_id → error
9. `test_tailor_with_linkedin_context` — LinkedIn data enhances tailoring
10. `test_tailor_with_deep_profile` — deep profile data used
11. `test_tailor_second_attempt_overwrites` — re-tailor replaces previous
12. `test_tailor_score_higher_than_original` — tailored score ≥ original
13. `test_tailor_audit_logged` — agent_runs entry created
14. `test_tailor_user_isolation` — can't access other user's tailoring
15. `test_tailor_result_json_structure` — validates response schema

### 12.3.2 — Cover Letter E2E Tests (RTX 5090)

**File:** `backend/tests/test_cover_letter_e2e.py` (~15 tests)

1. `test_generate_cover_letter` — POST creates letter
2. `test_letter_has_four_parts` — subject, greeting, body, closing
3. `test_letter_references_company` — company name in letter
4. `test_letter_references_role` — role title in letter
5. `test_get_letter_by_posting` — GET by posting_id
6. `test_get_letter_by_id` — GET by letter_id
7. `test_update_letter_body` — PUT modifies body
8. `test_delete_letter` — DELETE removes letter
9. `test_regenerate_with_feedback` — regeneration uses feedback
10. `test_regenerate_creates_new_version` — old letter preserved
11. `test_letter_under_3000_chars` — length constraint enforced
12. `test_letter_tone_professional` — default tone applied
13. `test_missing_posting_404` — invalid posting_id → error
14. `test_audit_logged` — agent_runs entry created
15. `test_user_isolation` — can't access other user's letters

### 12.3.3 — Interview Coach E2E Tests (RTX 5090)

**File:** `backend/tests/test_interview_coach_e2e.py` (~15 tests)

1. `test_start_session_returns_opening` — POST creates session with opening
2. `test_session_has_persona` — persona set
3. `test_answer_returns_score` — POST answer gets 4-dimension score
4. `test_score_dimensions_0_to_10` — each dimension 0-10 range
5. `test_adaptive_question_targets_weakness` — next Q addresses low score area
6. `test_5_questions_complete_session` — session completes after question_count
7. `test_assessment_has_strengths` — final assessment lists strengths
8. `test_assessment_has_improvements` — final assessment lists improvements
9. `test_session_history_ordered` — messages in chronological order
10. `test_list_sessions` — GET returns all user sessions
11. `test_multiple_personas` — different personas ask different questions
12. `test_session_state_progression` — prep→mock_questions→feedback→complete
13. `test_invalid_session_404` — bad session_id → error
14. `test_user_isolation` — can't access other user's sessions
15. `test_audit_logged` — agent_runs entry created

---

## Wave 12.4: Error Path Testing (RTX 5090)

**Effort:** ~2 hours | **Tests added:** ~20 | **User gate:** No
**Delegation:** Test file delegated to RTX 5090.
**Assessment file:** `roadmap/HONEST_ASSESSMENT_12_4.md`

### 12.4.1 — Error Path Test File (RTX 5090)

**File:** `backend/tests/test_error_paths.py` (~20 tests)

**Upload errors (4):**
1. `test_upload_empty_file` — 0-byte file → 400
2. `test_upload_wrong_extension` — .exe file → 400
3. `test_upload_oversized_file` — >16MB → 413
4. `test_upload_no_file_field` — missing form field → 400

**Optimization errors (3):**
5. `test_optimize_nonexistent_resume` — bad resume_id → 404
6. `test_optimize_empty_jd` — no job description → 400
7. `test_optimize_no_auth` — missing user-id header → 401

**Agent errors (3):**
8. `test_scout_search_invalid_criteria` — malformed JSON → 400
9. `test_pipeline_move_invalid_stage` — nonexistent stage → 400
10. `test_campaign_start_no_user` — missing user-id → 401

**Data integrity (3):**
11. `test_duplicate_user_registration` — same email → 409
12. `test_resume_version_wrong_user` — access denied → 403/404
13. `test_delete_nonexistent_campaign` — bad ID → 404

**Input validation (3):**
14. `test_jd_too_short` — <50 char JD → 400
15. `test_login_wrong_password` — bad creds → 401
16. `test_experience_message_empty` — blank message → 400

**LLM resilience (4):**
17. `test_optimize_llm_timeout_fallback` — LLM timeout → NLP-only result
18. `test_experience_chat_no_llm` — harness down → template questions
19. `test_campaign_generate_partial_failure` — some posts fail → partial result
20. `test_agent_llm_retry` — first call fails, retry succeeds

---

## Wave 12.5: Gateway Department Governance (RTX 5090)

**Effort:** ~4 hours | **Tests added:** ~80 | **User gate:** Yes (gateway scope)
**Delegation:** ALL governance test files delegated to RTX 5090.
**Assessment file:** `roadmap/HONEST_ASSESSMENT_12_5.md`

### 12.5.1 — Agents Department Tests (RTX 5090)

**File:** `gateway/tests/test_agent_governance.py` (~25 tests)

Tests for `gateway/app/services/agents/`:
1. Base agent initialization + config loading
2. Planning agent task decomposition
3. Reasoning agent chain-of-thought extraction
4. Agent factory dispatch (coding/reasoning/planning/review)
5. Agent retry logic (base_agent retries parameter)
6. Agent audit logging
7. Agent LLM routing (model selection per task type)
8. Agent error handling (LLM timeout → graceful failure)
9. Agent response parsing (JSON extraction from LLM output)
10. Agent context injection (profile data, RAG context)

### 12.5.2 — Observability Department Tests (RTX 5090)

**File:** `gateway/tests/test_observability_governance.py` (~25 tests)

Tests for cost tracking, metrics, logging:
1. Cost per request calculation (local = $0.00)
2. Cost tracking DB schema validation
3. Cost aggregation (daily/weekly/monthly)
4. Teaching effectiveness metrics computation
5. Teaching usage wrapper integration
6. Backend health monitor state transitions
7. Health check interval configuration
8. Circuit breaker state machine (closed→open→half_open→closed)
9. Uptime percentage calculation
10. Latency histogram tracking

### 12.5.3 — API_Surface Department Tests (RTX 5090)

**File:** `gateway/tests/test_api_surface_governance.py` (~30 tests)

Tests for route coverage and contract validation:
1. All routes return proper JSON content-type
2. Auth-required routes reject missing auth
3. CORS headers present on responses
4. Health endpoint returns expected schema
5. Swap API validates model names
6. Cost API returns proper aggregation
7. Model selection API returns valid model
8. Teaching dashboard data structure
9. MCP routes return proper schema
10. Agent API task submission

### 12.5.4 — Update qa_audit Department Map

**File:** `gateway/scripts/qa_audit.py`

Update `DEPARTMENT_MAP` to include new test files and mark departments GOVERNED.

---

## Wave 12.6: React Unit Tests — All 38 Components (RTX 5090)

**Effort:** ~6 hours | **Tests added:** ~150 | **User gate:** No
**Delegation:** ALL test files + test infrastructure delegated to RTX 5090.
**Assessment file:** `roadmap/HONEST_ASSESSMENT_12_6.md`

### 12.6.1 — Install Test Infrastructure

**File:** `frontend/package.json`

Add dev dependencies:
```json
{
  "vitest": "^3.0.0",
  "@testing-library/react": "^16.0.0",
  "@testing-library/jest-dom": "^6.0.0",
  "@testing-library/user-event": "^14.0.0",
  "jsdom": "^25.0.0",
  "@vitest/coverage-v8": "^3.0.0"
}
```

Add script: `"test:unit": "vitest run"`

**File:** `frontend/vitest.config.js`
```js
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/setupTests.js',
  },
});
```

**File:** `frontend/src/setupTests.js`
```js
import '@testing-library/jest-dom';
```

### 12.6.2 — Tier 1: Core & Auth Components (RTX 5090)

**File:** `frontend/src/__tests__/core.test.jsx` (~15 tests)

| Component | Tests | What's Validated |
|-----------|-------|-----------------|
| App.jsx | 3 | Renders login when unauthenticated, redirects to dashboard when authenticated, logout clears state |
| Login.jsx | 5 | Renders form, toggle register mode, validates password match, shows error on failed login, calls onLogin on success |
| Dashboard.jsx | 7 | Renders 9 tabs, default tab is optimize, tab switching works, 3-step wizard progression, logout button calls onLogout, loads sessions, renders child components |

### 12.6.3 — Tier 2: Upload & Optimization Flow (RTX 5090)

**File:** `frontend/src/__tests__/optimization.test.jsx` (~20 tests)

| Component | Tests | What's Validated |
|-----------|-------|-----------------|
| ResumeUpload.jsx | 5 | File input renders, drag-drop zones active, rejects invalid file types, rejects >16MB, calls onUpload with file |
| JobDescriptionInput.jsx | 4 | Textarea renders, enforces 50-char minimum, paste/upload mode toggle, calls onSubmit with text |
| OptimizedResumeView.jsx | 6 | Score ring renders with value, keyword lists populated, download buttons present, improvement chat panel, score breakdown bars, start-over button calls callback |
| SkillsGap.jsx | 5 | Three skill buckets render, endorsement weights displayed, skill confirm/remove actions, interview mode toggle, close button calls onClose |

### 12.6.4 — Tier 3: Google Drive & Experience (RTX 5090)

**File:** `frontend/src/__tests__/gdrive-experience.test.jsx` (~15 tests)

| Component | Tests | What's Validated |
|-----------|-------|-----------------|
| GoogleDriveImport.jsx | 4 | File browser renders, folder navigation works, import button triggers callback, version list displays |
| GDriveFilePicker.jsx | 3 | Folder tree renders, file selection works, import callback fires |
| ExperienceChat.jsx | 5 | Chat bubble list renders, message input works, 6-stage progression, context sidebar shows extraction, finalize button |
| ResumeBuilder.jsx | 3 | Section editor renders, preview updates, source selector works |

### 12.6.5 — Tier 4: Agent Components (RTX 5090)

**File:** `frontend/src/__tests__/agents.test.jsx` (~25 tests)

| Component | Tests | What's Validated |
|-----------|-------|-----------------|
| AgentDashboard.jsx | 3 | Renders agent cards, status indicators, navigation to sub-agents |
| JobScout.jsx | 5 | Search form renders, criteria fields present, postings list displays, star/status toggle works, score display |
| ApplicationPipeline.jsx | 4 | Kanban columns render (10 stages), card displays posting info, analytics section, reminders list |
| InterviewCoach.jsx | 4 | Persona selector renders, question display, answer input, score display with 4 dimensions |
| ResumeTailor.jsx | 3 | Posting selector renders, tailor button triggers, tailored resume displays |
| CoverLetter.jsx | 3 | Generation button renders, 4-part letter display, regenerate with feedback |
| CareerAdvisor.jsx | 3 | Analysis trigger renders, trajectory display, roadmap phases |

### 12.6.6 — Tier 5: Project & Journey Components (RTX 5090)

**File:** `frontend/src/__tests__/project-journey.test.jsx` (~20 tests)

| Component | Tests | What's Validated |
|-----------|-------|-----------------|
| ProjectAnalyzer.jsx | 4 | Project list renders, create form works, analysis trigger, approval workflow |
| ClientAnalysisView.jsx | 3 | Analysis tabs (technical/governance/role) render, editing mode, approval button |
| AnalysisApproval.jsx | 2 | Modal renders, approve button fires callback |
| JourneyMiner.jsx | 3 | Mining trigger renders, progress display, timeline/skills/narratives tabs |
| JourneyTimeline.jsx | 2 | Events render chronologically, category badges display |
| JourneySkills.jsx | 2 | Skills list renders, adoption dates display |
| JourneyNarratives.jsx | 4 | Narrative cards render, edit mode works, approval button, STAR entries display |

### 12.6.7 — Tier 6: Campaign & Deep Analysis (RTX 5090)

**File:** `frontend/src/__tests__/campaign-deep.test.jsx` (~20 tests)

| Component | Tests | What's Validated |
|-----------|-------|-----------------|
| CampaignManager.jsx | 3 | Campaign list renders, create new campaign, navigate to campaign detail |
| CampaignInterview.jsx | 4 | 7-stage state machine, message input, stage indicators, create campaign from interview |
| CampaignCanvas.jsx | 3 | Post grid renders, drag handles present, reorder updates |
| PostEditor.jsx | 3 | Modal renders, char count updates, regenerate with feedback input |
| CampaignList.jsx | 2 | Campaign cards render, status badges display |
| CampaignTimeline.jsx | 2 | Timeline posts render, dates display |
| DeepAnalysis.jsx | 3 | Build profile trigger, career phases display, role fit scoring |

### 12.6.8 — Tier 7: Utility & Remaining (RTX 5090)

**File:** `frontend/src/__tests__/utility.test.jsx` (~10 tests)

| Component | Tests | What's Validated |
|-----------|-------|-----------------|
| BuilderInterview.jsx | 2 | Chat interface renders, message submission |
| BuilderPreview.jsx | 2 | Resume preview renders, formatting correct |
| SourceSelector.jsx | 2 | Source options render, selection callback fires |
| Onboarding.jsx | 2 | Steps render, dismiss button works |
| api.jsx (service) | 2 | Base URL configured, auth header interceptor adds token |

### 12.6.9 — Update Frontend Governance

**File:** `backend/tests/test_frontend_governance.py`

Add tests validating:
- `vitest.config.js` exists
- `setupTests.js` exists
- `__tests__/` directory has ≥7 test files
- `npm run test:unit` script defined in package.json
- Total test count ≥ 100

---

## Wave 12.7: Docker Deployment — Full Stack + Infrastructure

**Effort:** ~3 hours | **Tests added:** ~10 (deployment tests) | **User gate:** No
**Delegation:** ALL Docker files delegated to RTX 5090.
**Assessment file:** `roadmap/HONEST_ASSESSMENT_12_7.md`

### 12.7.1 — Backend Dockerfile (RTX 5090)

**File:** `backend/Dockerfile`

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m spacy download en_core_web_sm
COPY . .
ENV FLASK_DEBUG=0 PYTHONUNBUFFERED=1
EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/agents/status')"
CMD ["python", "app.py"]
```

### 12.7.2 — Frontend Dockerfile (RTX 5090)

**File:** `frontend/Dockerfile`

Multi-stage build:
```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s CMD wget -qO- http://localhost/health || exit 1
CMD ["nginx", "-g", "daemon off;"]
```

### 12.7.3 — Nginx Config (RTX 5090)

**File:** `frontend/nginx.conf`

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;

    location /health { return 200 'ok'; add_header Content-Type text/plain; }

    location /assets/ {
        add_header Cache-Control "public, max-age=31536000, immutable";
        try_files $uri =404;
    }

    location /api/ {
        proxy_pass http://backend:5000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300s;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

### 12.7.4 — Docker Compose (RTX 5090)

**File:** `docker-compose.yml`

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    container_name: ro-backend
    ports: ["5000:5000"]
    environment:
      - FLASK_DEBUG=0
      - ARANGO_ENABLED=true
      - ARANGO_HOST=arangodb
      - ARANGO_PORT=8529
      - QDRANT_HOST=qdrant
      - QDRANT_PORT=6333
      - ARTEMIS_HOST=artemis
      - ARTEMIS_PORT=61613
      - CORS_ORIGIN=http://localhost
    volumes:
      - db-data:/app/data
      - uploads:/app/uploads
    depends_on:
      arangodb: { condition: service_healthy }
      qdrant: { condition: service_healthy }
    networks: [ro-network]
    restart: unless-stopped

  frontend:
    build: ./frontend
    container_name: ro-frontend
    ports: ["80:80"]
    depends_on: [backend]
    networks: [ro-network]
    restart: unless-stopped

  arangodb:
    image: arangodb:3.12
    container_name: ro-arangodb
    ports: ["8529:8529"]
    environment:
      - ARANGO_ROOT_PASSWORD=resume_optimizer
    volumes:
      - arango-data:/var/lib/arangodb3
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8529/_api/version"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks: [ro-network]

  qdrant:
    image: qdrant/qdrant:latest
    container_name: ro-qdrant
    ports: ["6333:6333"]
    volumes:
      - qdrant-data:/qdrant/storage
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/healthz"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks: [ro-network]

  artemis:
    image: apache/activemq-artemis:latest
    container_name: ro-artemis
    ports:
      - "61613:61613"
      - "8161:8161"
    environment:
      - ARTEMIS_USER=admin
      - ARTEMIS_PASSWORD=admin
    volumes:
      - artemis-data:/var/lib/artemis-instance
    networks: [ro-network]

networks:
  ro-network:
    driver: bridge

volumes:
  db-data:
  uploads:
  arango-data:
  qdrant-data:
  artemis-data:
```

### 12.7.5 — .dockerignore (RTX 5090)

**File:** `.dockerignore`

```
__pycache__
*.pyc
.pytest_cache
.venv
venv
node_modules
.git
*.db
uploads/
build/
dist/
.env.local
frontend/test-results/
```

### 12.7.6 — Environment Template

**File:** `.env.example`

```bash
# Resume Optimizer — Docker Environment
FLASK_DEBUG=0
ARANGO_ENABLED=true
ARANGO_ROOT_PASSWORD=resume_optimizer
CORS_ORIGIN=http://localhost
# Optional: Gateway integration
# HARNESS_URL=http://host.docker.internal:8000/api/harness/run
# VLLM_URL=http://host.docker.internal:8021/v1
```

### 12.7.7 — Deployment Tests (RTX 5090)

**File:** `backend/tests/test_docker_deployment.py` (~10 tests)

Tests that validate Docker deployment artifacts (file inspection, no containers needed):
1. `test_backend_dockerfile_exists` — Dockerfile present
2. `test_frontend_dockerfile_exists` — Dockerfile present
3. `test_docker_compose_exists` — docker-compose.yml present
4. `test_compose_has_5_services` — backend, frontend, arangodb, qdrant, artemis
5. `test_compose_has_healthchecks` — each service has healthcheck
6. `test_compose_has_volumes` — persistent data volumes defined
7. `test_compose_has_network` — ro-network defined
8. `test_dockerignore_excludes_db` — *.db in .dockerignore
9. `test_env_example_exists` — .env.example present
10. `test_nginx_config_proxies_api` — nginx.conf has `/api/` location

---

## Wave 12.8: Documentation + Regression + Final Gate

**Effort:** ~1.5 hours | **Tests added:** 0 | **User gate:** Yes (final acceptance)
**Assessment file:** `roadmap/HONEST_ASSESSMENT_12_8.md` (final cumulative)

### 12.8.1 — Full Regression

```bash
# Backend
cd backend && python -m pytest tests/ -q --tb=line
cd backend && python scripts/qa_audit.py

# Frontend
cd frontend && npm run test:unit

# Gateway
cd gateway && python scripts/qa_audit.py
```

### 12.8.2 — Update HONEST_ASSESSMENT.md (Cumulative)

Move all resolved gaps. Update feature status table. Update test metrics.

### 12.8.3 — Update SESSION_STATE.json

```json
{
  "current_phase": 12,
  "tests_total": "912 + ~290 new backend + ~150 React unit",
  "gateway_departments": "ALL GOVERNED",
  "docker_deployment": "COMPLETE"
}
```

### 12.8.4 — Create phase12_proof.json

**File:** `roadmap/assessments/phase12_proof.json`

Machine-readable proof with per-wave results.

---

## Execution Summary

| Wave | Scope | Tests | Effort | RTX 5090 | User Gate |
|------|-------|-------|--------|----------|-----------|
| 12.1 | Quick wins (deps, CI, D→B+, skip reporting) | ~25 | 2h | No | No |
| 12.2 | Career Advisor full production | ~20 | 4h | Yes | No |
| 12.3 | Agent E2E tests (tailor, cover, coach) | ~45 | 3h | Yes | No |
| 12.4 | Error path tests | ~20 | 2h | Yes | No |
| 12.5 | Gateway governance (3 departments) | ~80 | 4h | Yes | Yes |
| 12.6 | React unit tests (all 38 components) | ~150 | 6h | Yes | No |
| 12.7 | Docker deployment (full stack + infra) | ~10 | 3h | Yes | No |
| 12.8 | Regression + docs + final gate | 0 | 1.5h | No | Yes |
| **Total** | **15/16 gaps** | **~350** | **~25.5h** | | |

---

## Gap Coverage Matrix (15/16)

| # | Gap (from HONEST_ASSESSMENT) | Wave | Resolution |
|---|------------------------------|------|-----------|
| 1 | **4 stub agents** (HIGH) | 12.2-12.3 | Career Advisor persistence + all 4 E2E tested |
| 2 | **No live LinkedIn OAuth** (MEDIUM) | DEFERRED | Only deferred item. Requires LinkedIn API credentials + OAuth infrastructure. |
| 3 | **No Docker deployment** (MEDIUM) | 12.7 | Full stack docker-compose: backend + frontend + ArangoDB + Qdrant + Artemis |
| 4 | **Missing pip dependencies** (LOW) | 12.1.1 | `qdrant-client` and `stomp.py` added to requirements.txt |
| 5 | **No multi-user testing** (LOW) | 12.3-12.4 | User isolation tests in each agent E2E file + error path tests |
| 6 | **No React unit tests** (MEDIUM) | 12.6 | 150 Jest/RTL tests across all 38 components (7 test files) |
| 7 | **LLM tests not CI-friendly** (HIGH) | 12.1.2 | `require_harness` → `pytest.skip` with `REQUIRE_LLM_TESTS` override |
| 8 | **Silent skips inflate CI** (MEDIUM) | 12.1.4 | Session-end skip reporter |
| 9 | **No error/timeout path tests** (MEDIUM) | 12.4 | 20 error path tests covering upload, optimization, agents, LLM |
| 10 | **1 D-tier file** (LOW) | 12.1.3 | test_output_quality.py D → B+ |
| 11 | **Gateway: Agents NO GOVERNANCE** | 12.5.1 | 25 agent governance tests |
| 12 | **Gateway: Observability NO GOVERNANCE** | 12.5.2 | 25 observability governance tests |
| 13 | **Gateway: API_Surface PARTIAL** | 12.5.3 | 30 API surface governance tests |
| 14 | **LLM tests hard-fail** (MEDIUM) | 12.1.2 | Same fix as #7 — `pytest.skip` with env override |
| 15 | **Monkeypatched tests graded A** (LOW) | 12.1.3 | Document as qa_audit known limitation in HONEST_ASSESSMENT |

## Deferred Items (1 of 16)

| Item | Why Deferred | What Would Be Needed |
|------|-------------|---------------------|
| **Live LinkedIn OAuth** | Requires LinkedIn API credentials ($99/month), app review process (weeks), OAuth2 infrastructure. Current local JSON import is functional for the app owner. | LinkedIn Developer App, OAuth2 flow with PKCE, callback endpoint, token refresh daemon, rate limit handling |

---

## RTX 5090 Delegation Matrix

| Task | Delegate to RTX 5090 | Method |
|------|----------------------|--------|
| Career Advisor persistence code (12.2) | **Yes** | curl port 8021 |
| Career Advisor E2E tests (12.2.4) | **Yes** | curl port 8021 |
| Resume Tailor E2E tests (12.3.1) | **Yes** | curl port 8021 |
| Cover Letter E2E tests (12.3.2) | **Yes** | curl port 8021 |
| Interview Coach E2E tests (12.3.3) | **Yes** | curl port 8021 |
| Error path tests (12.4.1) | **Yes** | curl port 8021 |
| Gateway Agents governance (12.5.1) | **Yes** | curl port 8021 |
| Gateway Observability governance (12.5.2) | **Yes** | curl port 8021 |
| Gateway API_Surface governance (12.5.3) | **Yes** | curl port 8021 |
| React unit tests (12.6.2-12.6.8) | **Yes** | curl port 8021 |
| Docker files (12.7.1-12.7.6) | **Yes** | curl port 8021 |
| Deployment tests (12.7.7) | **Yes** | curl port 8021 |
| requirements.txt edit (12.1.1) | No | Trivial 2-line edit |
| test_helpers.py CI fix (12.1.2) | No | 5-line change |
| test_output_quality.py upgrade (12.1.3) | No | Assertion additions |
| conftest.py skip reporter (12.1.4) | No | 10-line fixture |
| qa_audit.py department map (12.5.4) | No | Config update |
| Documentation (12.8) | No | Assessment writing |

---

## HONEST_ASSESSMENT File Convention

Each wave produces its own assessment file:

| File | Created After | Contents |
|------|--------------|----------|
| `roadmap/HONEST_ASSESSMENT_12_1.md` | Wave 12.1 | deps, CI, D→B+, skip reporter results |
| `roadmap/HONEST_ASSESSMENT_12_2.md` | Wave 12.2 | Career Advisor persistence, E2E results |
| `roadmap/HONEST_ASSESSMENT_12_3.md` | Wave 12.3 | Agent E2E test results (3 agents) |
| `roadmap/HONEST_ASSESSMENT_12_4.md` | Wave 12.4 | Error path test results |
| `roadmap/HONEST_ASSESSMENT_12_5.md` | Wave 12.5 | Gateway governance results |
| `roadmap/HONEST_ASSESSMENT_12_6.md` | Wave 12.6 | React unit test results |
| `roadmap/HONEST_ASSESSMENT_12_7.md` | Wave 12.7 | Docker deployment results |
| `roadmap/HONEST_ASSESSMENT_12_8.md` | Wave 12.8 | Final cumulative assessment |

Each file includes: what was done, test counts, pass/fail, qa_audit grade changes, remaining gaps, next wave preview.

---

## Success Criteria

- [ ] All backend tests pass (0 failures)
- [ ] qa_audit Grade A maintained (GATE: PASS)
- [ ] Gateway Grade B+ maintained (GATE: PASS)
- [ ] test_output_quality.py ≥ B tier
- [ ] 0 untested agents with routes
- [ ] Career Advisor has persistence (career_analyses table populated)
- [ ] All 4 agents have E2E test files
- [ ] Error path coverage ≥ 20 new tests
- [ ] LLM tests CI-friendly (skip, not fail)
- [ ] Gateway: Agents department GOVERNED
- [ ] Gateway: Observability department GOVERNED
- [ ] Gateway: API_Surface department GOVERNED
- [ ] React unit tests: all 38 components tested (≥150 tests)
- [ ] Docker: `docker-compose up` builds and serves app
- [ ] Docker: 5 services defined (backend, frontend, arangodb, qdrant, artemis)
- [ ] HONEST_ASSESSMENT per-wave files created (8 files)
- [ ] Missing pip dependencies in requirements.txt
- [ ] phase12_proof.json created with all wave results
