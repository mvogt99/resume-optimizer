# Resume Optimizer — Cloud Rearchitecture Plan
**Status:** DRAFT — Pending user approval before any implementation begins
**Branch:** `feature/cloud-rearchitecture`
**CoE Interview:** Session `3d6846ba` via CloudLift CoE
**Current Readiness:** 2.0 / 5.0
**Target Readiness:** 4.5+ / 5.0
**Recipe:** Event-Driven Microservices (AWS)

---

## Guiding Principles
1. **Existing application is unaffected** until each phase is fully tested and approved
2. **No phase begins without user approval** of the previous phase's plan section
3. **Regression testing uses real data** — not mocks — before any phase is marked Grade A
4. **Grade is honest**: autonomy + functional correctness rubrics, not just "tests pass"
5. **Monorepo vs. separate repos** is a Phase 2 decision (options documented below)

---

## Repository Structure Decision (Resolve at Phase 2 Gate)

### Option A — Monorepo (subdirectories in this repo)
```
resume-optimizer/
├── resume-optimizer-api/       # Flask backend → Lambda-ready
├── resume-optimizer-web/       # React SPA → Lambda@Edge
├── resume-optimizer-workers/   # Async task workers
├── shared/                     # Shared types, adapters
└── PLAN.md                     # This file
```
**Pros:** Single PR covers cross-cutting changes; shared history; simpler local dev
**Cons:** CI must scope per-subdirectory; harder to give separate teams independent access

### Option B — Separate repos
- `resume-optimizer-api` (new repo)
- `resume-optimizer-web` (new repo, from `frontend/`)
- `resume-optimizer-workers` (new repo)
- Shared adapters as a pip package or git submodule

**Pros:** Clean separation; independent deploy pipelines; standard microservices practice
**Cons:** More overhead to bootstrap; cross-repo changes require multiple PRs

> **Decision required from user at Phase 2 approval gate**

---

## Readiness Score Improvement Path

| Category | Current | Target | Blocker to Fix |
|---|---|---|---|
| Containerization | 2/5 | 5/5 | Fix `backend/Dockerfile` (uvicorn → Flask gunicorn) |
| Config Externalization | 2/5 | 5/5 | Replace all hardcoded `localhost` URLs with env vars |
| Service Abstraction | 2/5 | 5/5 | Wrap LLM, DB, queue behind CloudLift bridge adapters |
| Secret Management | 1/5 | 5/5 | Move Artemis creds, OAuth tokens to AWS Secrets Manager |
| Test Coverage | 4/5 | 5/5 | Add cloud integration tests (Bedrock, Neptune, SQS) |
| CI/CD | 1/5 | 5/5 | GitHub Actions pipeline for test → build → deploy |

**To reach 4.5/5.0:** Complete Phases 1 + 2 (Containerization, Config, Secrets, CI/CD, Service Abstraction)
**To reach 5.0/5.0:** Complete all 4 phases including LLM abstraction + cloud-specific tests

---

## Phase 1 — Foundational Infrastructure & Security
**Estimated effort:** 5–6 weeks
**Goal:** Make the existing application deployable to AWS without code changes to business logic
**Approval gate:** Phase 1 complete + regression suite green + user sign-off → Phase 2 begins

### 1.1 Fix Dockerfile & Containerization (Week 1)
- **File:** `backend/Dockerfile`
- **Change:** Replace `uvicorn/main:app` with `gunicorn app:app` (Flask, not ASGI)
- **Test:** `docker build` succeeds; `docker run` starts Flask app; all API endpoints respond
- **Regression:** Run existing backend test suite (`pytest backend/`) against containerized app

### 1.2 Config Externalization (Week 1–2)
- **Files:** `backend/arango_client.py` (hardcoded `http://localhost:8529`), `backend/smart_llm.py` (hardcoded `http://localhost:8021`), all route files with hardcoded URLs
- **Change:** Replace with `os.environ.get("ARANGO_HOST", "localhost")` pattern throughout
- **Standard:** AWS Systems Manager Parameter Store for dynamic config
- **Test:** App starts and functions correctly with env vars set; fails fast with clear error if required vars missing
- **Regression:** All existing API integration tests pass with env-var config

### 1.3 Secrets Management (Weeks 2–3)
- **Files:** `backend/bus_client.py` lines 10–15 (hardcoded Artemis credentials), `backend/analysis_worker.py` lines 12–13
- **Change:** AWS Secrets Manager integration; secrets fetched at startup, never in source
- **Also:** Google OAuth token moved from `~/.config/resume-optimizer/token.json` to encrypted S3 with IAM role access
- **Test:** App retrieves secrets from Secrets Manager; no credentials in environment variables or source
- **Regression:** Auth flows (Google OAuth, JWT session) work correctly with Secrets Manager path

### 1.4 CI/CD Pipeline (Weeks 3–4)
- **File:** `.github/workflows/ci.yml` (new)
- **Change:** GitHub Actions: lint → unit tests → integration tests → Docker build → push to ECR
- **Also:** Fix flaky tests identified during pipeline setup
- **Test:** PR triggers pipeline; pipeline catches regressions; deployment only on green
- **Regression:** All existing tests pass in CI environment

### Phase 1 Regression Test Requirements
- All `pytest backend/` tests pass **against real SQLite data** (not in-memory test DB)
- All `pytest frontend/` tests pass (if applicable)
- Docker container serves all 100+ endpoints correctly
- `docker-compose up` brings full stack up (backend + frontend + ArangoDB + Artemis)
- No hardcoded credentials remain (`git grep -i "password\|secret\|key" -- '*.py' | grep -v test`)

---

## Phase 2 — Service Decomposition & Event-Driven Architecture
**Estimated effort:** 8–12 weeks
**Goal:** Split monolith into deployable microservices; replace Artemis with SQS; deploy to AWS Lambda
**Approval gate:** Phase 1 signed off + repository structure decision made + Phase 2 plan approved

### 2.1 Repository Structure Decision (at Phase 2 gate)
User chooses Option A (monorepo) or Option B (separate repos) from the options documented above.

### 2.2 LLM Agent Decoupling (Weeks 1–4)
- **Files:** `backend/smart_llm.py` and 50+ call sites
- **Change:** Extract into `resume-optimizer-api` Lambda layer; implement CloudLift `ILLMInference` bridge adapter
- **Adapter:** `BedrockAdapter` (AWS) / `AzureOpenAIAdapter` (Azure) implementing same interface
- **Test:** All LLM-dependent endpoints produce equivalent output via Bedrock vs. RTX 5090
- **Regression:** Run a batch of real resume analysis jobs against both backends; compare outputs; pass threshold = ≥95% semantic similarity

### 2.3 Messaging Migration: Artemis → SQS (Weeks 3–5)
- **Files:** `backend/bus_client.py`, `backend/analysis_worker.py`
- **Change:** SQS FIFO queue replaces ActiveMQ Artemis; EventBridge for cross-service events
- **Events:** `resume_uploaded`, `analysis_requested`, `analysis_complete`
- **Test:** Async analysis jobs complete end-to-end via SQS
- **Regression:** Existing async analysis workflows produce identical results via SQS vs. Artemis

### 2.4 Microservices Split
- **resume-optimizer-api:** Core REST API (Flask → Lambda via Mangum adapter)
- **resume-optimizer-web:** React SPA (Lambda@Edge or S3+CloudFront)
- **resume-optimizer-workers:** Analysis workers (Lambda triggered by SQS)
- **Test:** All services deploy independently; API gateway routes correctly
- **Regression:** Full end-to-end user flow (upload resume → analysis → results) works across split services

### Phase 2 Regression Test Requirements
- **Real data test suite:** Run 20 real resumes through the complete analysis pipeline via AWS
- **LLM equivalence:** Bedrock output vs. RTX 5090 output ≥95% semantic similarity on same inputs
- **Latency:** P99 API response time ≤ current baseline + 20%
- **Cost:** AWS monthly estimate ≤ budget agreed at Phase 2 approval
- **Zero data loss:** All resume records, analysis results, and user accounts intact after migration

---

## Phase 3 — Data Layer Modernization
**Estimated effort:** 6–8 weeks
**Goal:** Migrate SQLite/PostgreSQL to ORC data lake (S3+Athena); ArangoDB to Neptune
**Approval gate:** Phase 2 signed off + Phase 3 plan approved

### 3.1 ORC Data Lake (S3 + Athena + Iceberg)
- **Current:** SQLite (dev) / PostgreSQL (prod) — 16 tables
- **Target:** AWS S3 in ORC format (write-heavy analytics), Parquet (read-heavy scoring queries)
- **Schema evolution:** Apache Iceberg for versioned schema changes
- **Athena catalog:** AWS Glue Catalog for SQL querying
- **Test:** All 16 tables migrated; SQL queries via Athena produce same results as PostgreSQL

### 3.2 Graph DB Migration: ArangoDB → Neptune
- **Current:** ArangoDB — 22 collections, Gremlin-compatible queries
- **Target:** Amazon Neptune (Gremlin API)
- **Test:** All graph traversal queries produce identical results via Neptune vs. ArangoDB
- **Regression:** Knowledge graph features (journey mining, skill graphs) work correctly via Neptune

### 3.3 Vector Search: Qdrant → OpenSearch (Optional / Evaluate)
- **Decision point:** Evaluate whether Amazon OpenSearch is cost-effective vs. keeping managed Qdrant
- **Only migrate if:** OpenSearch total cost ≤ Qdrant cost + migration effort amortized over 12 months

### Phase 3 Regression Test Requirements
- **Data integrity:** Row counts match between source DB and target (S3/Athena/Neptune)
- **Query equivalence:** 50 representative queries produce identical results before/after migration
- **Real resume scoring:** Existing resumes produce same scores before/after data layer migration

---

## Phase 4 — LLM Abstraction & Cloud Readiness
**Estimated effort:** 4–6 weeks
**Goal:** Complete LLM abstraction; cloud-ready testing; readiness score 4.5+
**Approval gate:** Phase 3 signed off + Phase 4 plan approved

### 4.1 Complete LLM Abstraction
- **Bridge adapter:** Full `ILLMInference` implementation covering all task types (resume tailoring, keyword extraction, analysis, scoring)
- **Rate limiting:** AWS API Gateway throttling + Cost Explorer budget alerts
- **Fallback:** Bedrock primary, Azure OpenAI secondary, RTX 5090 dev-only

### 4.2 Cloud-Ready Testing Suite
- **Load tests:** Locust scripts simulating 50 concurrent users
- **Security scan:** AWS Inspector + OWASP dependency check
- **Acceptance tests:** 20 real resumes through full pipeline, scored against human baseline

### 4.3 Final Readiness Assessment
- Run CloudLift readiness scan on deployed AWS environment
- Target: 4.5/5.0 minimum (all categories ≥4 except CI/CD ≥5)
- **Grade is earned, not assumed:** failing a rubric item blocks phase completion

---

## Execution Gates Summary

| Gate | Condition | Who approves |
|---|---|---|
| Phase 1 start | This plan approved | User |
| Phase 2 start | Phase 1 Grade A + regression green | User |
| Phase 2 repo decision | Options A/B reviewed | User |
| Phase 3 start | Phase 2 Grade A + regression green | User |
| Phase 4 start | Phase 3 Grade A + data integrity verified | User |
| Deploy to production | Phase 4 Grade A + load test passed | User |

---

## Not In Scope
- Blog post / demo video (deferred to Phase 5 Polish)
- Multi-tenancy (single user/owner model maintained)
- Azure deployment (AWS primary; Azure bridge adapters added but not deployed in this plan)

---

## Open Questions (resolve before Phase 1 implementation)
1. Which AWS account/region for deployment? (dev vs. prod account separation)
2. Is there an existing ECR registry or should a new one be created?
3. GitHub repo: push existing `feature/cloud-rearchitecture` branch to remote, or create new GitHub repo?
4. LLM task types: complete list of `smart_llm.py` task types needed for Bedrock equivalence testing?

---

*Generated from CoE interview session `3d6846ba` via CloudLift. All implementation requires explicit user approval per gate above.*
