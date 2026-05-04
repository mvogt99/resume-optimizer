# Resume Optimizer — Cloud Rearchitecture Plan
**Status:** DRAFT — Pending user approval before any implementation begins
**Branch:** `feature/cloud-rearchitecture`
**GitHub:** https://github.com/mvogt99/resume-optimizer
**CoE Interview:** Session `3d6846ba` via CloudLift CoE
**Current Readiness:** 2.0 / 5.0
**Target Readiness:** 4.5+ / 5.0
**Recipe:** Event-Driven Microservices (AWS) — `event-driven-microservices-aws`
**AWS Region (prod):** us-east-2

---

## Guiding Principles
1. **Existing application is unaffected** — feature branch only; `main` is untouched until each phase is approved
2. **Dev environment = local services only** — no AWS in dev (ArangoDB, SQLite, Artemis, RTX 5090, Qdrant, filesystem)
3. **Test/prod = AWS** — bridge adapters route to cloud services based on `CLOUDLIFT_ENV`
4. **No phase begins without user approval** of the previous phase's plan section
5. **Regression testing uses real data** — not mocks — before any phase is marked Grade A
6. **Grade is honest**: autonomy + functional correctness rubrics, not just "tests pass"

---

## Environment Tiers

| Tier | `CLOUDLIFT_ENV` | LLM | DB (relational) | DB (graph) | Queue | Vector | Storage |
|---|---|---|---|---|---|---|---|
| **dev** | `local` | RTX 5090 vLLM | SQLite | ArangoDB | Artemis | Qdrant | filesystem |
| **test** | `aws` (ro-test-*) | Bedrock | RDS PG / S3+Athena | Neptune | SQS | OpenSearch | S3 |
| **prod** | `aws` (ro-prod-*) | Bedrock | RDS PG / S3+Athena | Neptune | SQS | OpenSearch | S3 |

Test and prod share the same AWS account (us-east-2), separated by resource name prefix and VPC.

---

## Repository Structure

**Standalone repo:** `mvogt99/resume-optimizer` (extracted from hybrid-ai-windows)

### Monorepo vs. Separate Repos — Decision at Phase 2 Gate

#### Option A — Monorepo (subdirectories in this repo)
```
resume-optimizer/
├── backend/                    # Existing Flask backend (Phase 1 target)
├── frontend/                   # Existing React SPA
├── resume-optimizer-api/       # Phase 2: Lambda-ready backend service
├── resume-optimizer-web/       # Phase 2: Static SPA → S3+CloudFront
├── resume-optimizer-workers/   # Phase 2: Async workers → ECS Fargate
├── shared/                     # Phase 2: Shared types, bridge adapters
└── PLAN.md
```
**Pros:** Single PR covers cross-cutting changes; shared history; simpler local dev
**Cons:** CI must scope per-subdirectory; harder to give separate teams independent access

#### Option B — Separate repos
- `mvogt99/resume-optimizer-api`
- `mvogt99/resume-optimizer-web` (from `frontend/`)
- `mvogt99/resume-optimizer-workers`
- Shared adapters published as a pip package

**Pros:** Clean separation; independent deploy pipelines; standard microservices practice
**Cons:** More overhead to bootstrap; cross-repo changes require multiple PRs

> **User chooses Option A or B at Phase 2 approval gate**

---

## Readiness Score Improvement Path

| Category | Current | After P1 | After P2 | After P3+4 | Blocker |
|---|---|---|---|---|---|
| Containerization | 2/5 | **5/5** | 5/5 | 5/5 | Fix `backend/Dockerfile` (uvicorn → gunicorn) |
| Config Externalization | 2/5 | **5/5** | 5/5 | 5/5 | Replace all hardcoded `localhost:*` URLs |
| Service Abstraction | 2/5 | 3/5 | **5/5** | 5/5 | Wrap LLM/DB/queue behind bridge adapters |
| Secret Management | 1/5 | **5/5** | 5/5 | 5/5 | Move Artemis creds + OAuth to Secrets Manager |
| Test Coverage | 4/5 | 4/5 | 4/5 | **5/5** | Add cloud integration tests |
| CI/CD | 1/5 | **5/5** | 5/5 | 5/5 | GitHub Actions pipeline |

**After Phase 1:** 2.0 → **4.0/5.0** (containerization, config, secrets, CI/CD fixed)
**After Phase 2:** 4.0 → **4.7/5.0** (service abstraction complete)
**After Phase 3+4:** 4.7 → **5.0/5.0** (cloud test suite, data layer)

---

## LLM Call Site Analysis — The Single Injection Point

The entire LLM surface (227 call sites across 60+ files) funnels through **2 files only**.
The bridge adapter is inserted at `smart_llm.py` — no application code changes needed.

```
60+ application files (artifact_generator, agents/*, routes/*, llm_helper, etc.)
         ↓ import
    llm_helper.py  — wrapper functions (call_llm_quality, call_llm_json, etc.)
         ↓ import
    smart_llm.py   ← BRIDGE ADAPTER INJECTED HERE (4 primitive functions)
       ↙                        ↘
  RTX 5090 vLLM            Bedrock / Azure OpenAI
  (CLOUDLIFT_ENV=local)    (CLOUDLIFT_ENV=aws/azure)
```

**Files to modify for the bridge:** 2 (`smart_llm.py` + new `cloudlift_llm_adapter.py`)
**Files automatically updated:** 60+ (zero application code changes required)

### Call Site Breakdown (227 total, ALL production)

| Function | Sites | Layer | Bedrock tier |
|---|---|---|---|
| `call_llm_quality` | 100 | llm_helper wrapper | Sonnet (quality-gated) |
| `call_llm` / `analyze_with_*` | 34 | llm_helper wrapper | Haiku/Sonnet by task_type |
| `call_direct` | 29 | smart_llm primitive | Haiku (direct, no scoring) |
| `call_llm_json` | 22 | llm_helper wrapper | Haiku (JSON extraction) |
| `call_llm_direct` | 10 | llm_helper wrapper | Haiku |
| `call_smart` | 6 | smart_llm primitive | Haiku/Sonnet |
| `call_llm_scored` + misc | 12 | llm_helper wrappers | Sonnet |
| `call_harness` + scored | 7 | smart_llm primitives | Sonnet |
| Misc wrappers | 7 | llm_helper | Sonnet |

**All 227 sites route through Bedrock in test/prod** via the `smart_llm.py` bridge injection.

### Task Type → Bedrock Model Mapping

```python
# Existing TASK_TYPE_MAP in smart_llm.py — maps directly to Bedrock model tiers
BEDROCK_MODEL_MAP = {
    # Claude Haiku (fast, cheap) — structured extraction, classification
    "analysis":  "us.anthropic.claude-haiku-4-5-20251001-v1:0",  # resume_analysis, skills_gap, ats_diagnostic, etc.
    "coding":    "us.anthropic.claude-haiku-4-5-20251001-v1:0",  # json_extraction, technical_extraction, resume_rewrite

    # Claude Sonnet (higher quality) — reasoning, narrative, conversation
    "reasoning": "us.anthropic.claude-sonnet-4-6-20250514-v1:0",  # interview, experience_chat, campaign_planning, narrative_generation
    "planning":  "us.anthropic.claude-sonnet-4-6-20250514-v1:0",  # career_planning, campaign_strategy
}
```

---

## Bridge Contracts Required

| Contract | Status in CloudLift | Local adapter | AWS adapter |
|---|---|---|---|
| `ILLMInference` | exists | vLLM (RTX 5090) | Bedrock |
| `IRelationalDatabase` | exists | SQLite/PostgreSQL | RDS PostgreSQL |
| `IDocumentDatabase` | exists (ArangoDB) | ArangoDB | Neptune |
| `IMessageQueue` | exists | Artemis | SQS/EventBridge |
| `IObjectStorage` | exists | Filesystem | S3 |
| `IVectorSearch` | **NEW — Phase 1** | Qdrant | OpenSearch |

`IVectorSearch` methods: `upsert(id, vector, metadata)`, `search(vector, top_k)`, `delete(id)`, `health()`

---

## ECR Structure (us-east-2)

| ECR Repo | Service | Deployment |
|---|---|---|
| `resume-optimizer/api` | Flask backend | Lambda container image |
| `resume-optimizer/workers` | Async workers | ECS Fargate |
| `resume-optimizer/web` | React SPA | **S3+CloudFront — no ECR** |

---

## Phase 1 — Foundational Infrastructure & Security
**Estimated effort:** 5–6 weeks
**Goal:** Make the existing application deployable to AWS without changes to business logic
**Approval gate:** Phase 1 complete + regression suite green + user sign-off → Phase 2 begins

### 1.0 IVectorSearch Contract in CloudLift (Week 1, parallel with 1.1)
- Add `IVectorSearch` protocol to `cloudlift/core/bridge/contracts/`
- Implement local Qdrant adapter (`cloudlift/core/bridge/local/qdrant_adapter.py`)
- Stub AWS OpenSearch adapter (fully implemented in Phase 2)
- Register in `AdapterResolver` under `"vector_search"` key

### 1.1 Fix Dockerfile (Week 1)
- **File:** `backend/Dockerfile`
- **Change:** `uvicorn/main:app` → `gunicorn app:app -w 4 -b 0.0.0.0:8000`
- **Regression (real data):** `pytest backend/tests/` passes against containerized app with real SQLite DB

### 1.2 Config Externalization (Weeks 1–2)
- **Files:** `backend/arango_client.py` (`localhost:8529`), `backend/smart_llm.py` (`localhost:8021`, `localhost:8000`), all route files with hardcoded URLs
- **Change:** All service URLs → environment variables with local defaults
- **Dev:** `docker-compose.local.yml` sets all env vars; zero AWS calls in dev
- **Regression (real data):** All existing API integration tests pass with env-var config

### 1.3 Secrets Management (Weeks 2–3)
- **Files:** `backend/bus_client.py:10-15`, `backend/analysis_worker.py:12-13`
- **Change:** AWS Secrets Manager for test/prod; `docker-compose.local.yml` env vars for dev
- **Also:** Google OAuth token → `ro-{env}-config/oauth/token.json` in S3 (test/prod) or local file (dev)
- **Regression (real data):** Google OAuth + JWT auth flows work end-to-end in both dev and test environments

### 1.4 CI/CD Pipeline (Weeks 3–4)
- **File:** `.github/workflows/ci.yml`
- **Stages:** lint → unit tests (real SQLite fixtures) → integration tests → docker build → push to ECR (test tag)
- **Regression (real data):** All backend tests pass in CI with real fixture data; docker image pushed to ECR

### 1.5 Bridge Adapter Wiring — LLM (Weeks 4–5)
- **Files:** `backend/smart_llm.py` (modify 4 primitives) + new `backend/cloudlift_llm_adapter.py`
- **Change:** `CLOUDLIFT_ENV=local` → RTX 5090 (unchanged); `CLOUDLIFT_ENV=aws` → Bedrock
- **No application code changes** — all 60+ files continue working without modification
- **Test (dev):** `CLOUDLIFT_ENV=local` — all 227 call sites produce same results as before
- **Test (aws):** `CLOUDLIFT_ENV=aws` — 5 real resume analysis calls through Bedrock return valid results

### Phase 1 Regression Test Requirements (all using real data)
1. `pytest backend/tests/` — all tests pass against real SQLite DB (not in-memory)
2. Docker: `docker run resume-optimizer/api` — spot-check 10 representative endpoints respond correctly
3. Dev stack: `docker-compose.local.yml up` — Flask + ArangoDB + Artemis + Qdrant + RTX 5090 all start
4. Secrets: `git grep -ri "password\|artemis\|secret" -- '*.py' | grep -v test | grep -v example` → empty
5. Bedrock: 5 real resume analysis calls via `ILLMInference` → Bedrock return valid, non-empty results

---

## Phase 2 — Service Decomposition & Event-Driven Architecture
**Estimated effort:** 8–12 weeks
**Goal:** Split monolith into Lambda/Fargate services; replace Artemis with SQS; Qdrant → OpenSearch
**Approval gate:** Phase 1 Grade A + repo structure decision + Phase 2 plan approved

### 2.1 Repo Structure Decision (at Phase 2 gate)
User selects Option A or B from the options documented above.

### 2.2 LLM Bridge — All 14 Task Types (Weeks 1–4)
- Complete `ILLMInference` testing for all 14 task types via Bedrock
- Deploy Lambda-backed `resume-optimizer-api`; validate all endpoints
- **Regression:** 20 real resumes via Bedrock; ≥95% semantic similarity vs RTX 5090 baseline

### 2.3 Messaging: Artemis → SQS + EventBridge (Weeks 3–5)
- Replace `bus_client.py` + `analysis_worker.py`
- Events: `resume_uploaded`, `analysis_requested`, `analysis_complete`, `job_match_requested`
- Dead-letter queues for error handling
- **Regression:** Async analysis completes end-to-end with real resume data via SQS

### 2.4 Qdrant → OpenSearch via IVectorSearch (Weeks 4–6)
- Implement OpenSearch adapter for `IVectorSearch` (stubbed in Phase 1)
- Migrate vector index
- **Regression:** Semantic search returns equivalent results (≥90% recall at P99 ≤200ms)

### 2.5 Microservices Split
- `resume-optimizer-api`: Flask → Lambda via Mangum
- `resume-optimizer-web`: React SPA → S3+CloudFront
- `resume-optimizer-workers`: long-running workers → ECS Fargate
- **Regression:** Full user flow (upload → analyze → results) works across split services

### Phase 2 Regression Test Requirements (real data)
- 20 real resumes through full AWS pipeline (LLM + graph + async queue)
- LLM equivalence: Bedrock ≥95% semantic similarity vs RTX 5090 on same inputs
- Latency: P99 API response ≤ current local baseline + 20%
- Zero data loss: all resume records, analysis results, user accounts intact
- Cost: AWS monthly estimate reviewed and approved by user before proceeding

---

## Phase 3 — Data Layer Modernization
**Estimated effort:** 6–8 weeks
**Goal:** Migrate relational data to S3+Athena (ORC/Parquet + Iceberg); finalize Neptune
**Approval gate:** Phase 2 Grade A + Phase 3 plan approved

### 3.1 ORC/Parquet Data Lake (S3 + Iceberg + Athena)
- Write-heavy (analytics, job logs): ORC format
- Read-heavy (resume scoring): Parquet format
- Iceberg for schema evolution; Glue Catalog for Athena queries
- **Regression:** All 16 relational tables migrated; 50 representative queries produce identical results

### 3.2 Neptune Graph DB (finalize)
- ArangoDB AQL → Gremlin translation complete
- **Regression:** All graph traversal queries equivalent; journey mining, skill graphs functional

### 3.3 Remove Qdrant dependency
- Remove `qdrant-client` from requirements; OpenSearch is sole vector backend
- **Regression:** ≥90% recall; P99 latency ≤200ms

---

## Phase 4 — Cloud-Ready Testing & Final Readiness
**Estimated effort:** 4–6 weeks
**Goal:** Full validation suite; readiness score 5.0/5.0; production-ready
**Approval gate:** Phase 3 Grade A + Phase 4 plan approved

### 4.1 Complete Bridge Adapter Test Suite
- Real-data integration test for every contract: ILLMInference, IRelationalDB, IDocumentDB, IMessageQueue, IObjectStorage, IVectorSearch
- Same test suite runs against both `local` and `aws` CLOUDLIFT_ENV

### 4.2 Load & Security Testing
- Locust: 50 concurrent users, 10-minute soak test
- AWS Inspector + OWASP dependency scan
- Cost Explorer alert if spend > agreed monthly threshold

### 4.3 Final CloudLift Readiness Scan
- Target: 5.0/5.0 all categories
- Grade is earned: failing any rubric item blocks completion and must be fixed

---

## Execution Gates Summary

| Gate | Required Condition | Who Approves |
|---|---|---|
| Phase 1 start | This plan approved | User |
| Phase 2 start | Phase 1 Grade A + regression green (real data) | User |
| Repo structure choice | Options A/B reviewed | User |
| Phase 3 start | Phase 2 Grade A + regression green | User |
| Phase 4 start | Phase 3 Grade A + data integrity verified | User |
| Merge to main | Phase 4 Grade A + load test passed | User |
| Production deploy | main merged + smoke test green | User |

---

## Open Questions — All Resolved

| # | Question | Answer |
|---|---|---|
| GitHub repo | New standalone or push to hybrid-ai-windows? | New: `mvogt99/resume-optimizer` |
| Test env | Same AWS account as prod? | Yes — `ro-test-*` vs `ro-prod-*` naming, same us-east-2 |
| call_llm scope | All 227 sites or subset? | ALL 227 — injected at `smart_llm.py` (2 files) |
| IVectorSearch | New CloudLift contract? | Yes — Phase 1.0 |
| AWS region | Which region? | us-east-2 |
| ECR | Structure? | `resume-optimizer/api` + `/workers`; web → S3+CloudFront |

---

## Not In Scope
- Blog post / demo video
- Multi-tenancy
- Azure deployment (bridge adapters stubbed but not deployed in this plan)
- Prod data migration strategy (separate plan when prod is ready)

---

*Plan authored via CloudLift CoE interview session `3d6846ba`. Implementation requires explicit user approval per gate above.*
