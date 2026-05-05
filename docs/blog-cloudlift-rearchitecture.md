# Zero Code Changes: Lifting a Local-First App to AWS with CloudLift

*How we took a multi-service local application from 2.0/5.0 cloud readiness to 5.0/5.0 in four phases — without modifying a single line of application logic.*

**Live result:** [resume-optimizer.concurrentonline.ai](https://resume-optimizer.concurrentonline.ai)

---

## The Problem

Resume Optimizer started as a local-first application. It was fast, capable, and deeply integrated with local infrastructure:

- **ArangoDB** for the knowledge graph (skills, projects, outcomes, career milestones)
- **Qdrant** for vector similarity search
- **ActiveMQ Artemis** for async document analysis jobs
- **SQLite** for relational data
- **RTX 5090 vLLM** for LLM inference (running a local Qwen or DeepSeek model)

The application had 145+ test files, 100+ API endpoints, and a React frontend. It worked exactly as designed — locally.

The problem: none of it could run in the cloud without rewriting every service call. The LLM was hardcoded to `localhost:8021`. ArangoDB queries were scattered across 17 files. The Artemis credentials were hardcoded in `bus_client.py`. There was no CI/CD, no Docker, and no concept of environment configuration.

The [CloudLift](https://github.com/mvogt99/cloudlift) scanner gave it a **2.0/5.0 readiness score** and identified three critical blockers:

1. LLM Service Coupling (CRITICAL) — RTX 5090 gateway hardcoded across 50+ call sites
2. Secrets Management (CRITICAL) — Artemis credentials hardcoded in source
3. No CI/CD Pipeline — zero automation, broken Dockerfile

Estimated migration effort: **10–12 weeks** of manual work.

We did it in four phases using CloudLift's bridge adapter pattern. Here's how.

---

## The Approach: Bridge Adapters

The core insight behind CloudLift is that cloud migration doesn't have to mean rewriting application logic. It means introducing an **abstraction layer** between application code and service implementations.

Instead of:
```python
# Everywhere in the codebase
from arango import ArangoClient
client = ArangoClient(hosts='http://localhost:8529')
db = client.db('hybrid_ai', ...)
db.collection('skills').insert(...)
```

You write:
```python
# Once, in a bridge adapter
from arango_client import get_graph_client
client = get_graph_client()
client.upsert_vertex('ro_ai_skills', {...})
```

And `get_graph_client()` returns an ArangoDB client in dev and a DynamoDB adapter in AWS — the same interface, different implementation, routing via `CLOUDLIFT_ENV`.

This is the bridge adapter pattern. The application code never changes. Only the adapter layer changes based on the environment.

---

## Phase 1: Foundation

**Goal:** Make the application deployable at all.

**What we changed:**
- Fixed the broken Dockerfile (it was referencing `uvicorn/main:app` for a Flask application)
- Added `docker-compose.yml` with proper health checks
- Created GitHub Actions CI (lint + tests)
- Externalized all hardcoded localhost URLs to environment variables
- Created `backend/.env.example` with all required variables documented
- Replaced hardcoded Artemis credentials with env var defaults

**Nothing in the application logic changed.** All routes, all business logic, all NLP processing — untouched.

**Result:** 2.0 → 3.5 readiness. The app could now be containerized and deployed somewhere — it just still required local ArangoDB, Qdrant, Artemis, and an RTX 5090 at the target.

---

## Phase 2: AWS Adapters — LLM, Database, Queue

**Goal:** Route the three highest-impact services to AWS.

### LLM: vLLM → Bedrock

The LLM was the hardest adapter to write. The app used 50+ call sites through `smart_llm.py`, which routed tasks by type to the local RTX 5090. Bedrock uses a completely different API.

The bridge adapter maps task types to Bedrock models:
```python
BEDROCK_MODEL_MAP = {
    "analysis":  "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "reasoning": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    ...
}
```

In `CLOUDLIFT_ENV=local`, the existing `smart_llm.py` is used unchanged. In `CLOUDLIFT_ENV=aws`, `cloudlift_llm_adapter.call_bedrock()` is used instead.

### Relational DB: SQLite → RDS PostgreSQL

`db_engine.py` already supported SQLite and PostgreSQL via a compatibility wrapper (`_PgConnWrapper`) that translates `?` placeholders to `%s` for psycopg2. The bridge adapter just needed to resolve the `DATABASE_URL` from AWS Secrets Manager when running in aws mode:

```python
def resolve_database_url() -> str:
    if os.environ.get("CLOUDLIFT_ENV") != "aws":
        return ""  # app uses SQLite default
    # Fetch from Secrets Manager
    secret = get_secret("ro/test/db")
    return f"postgresql://{secret['username']}:{secret['password']}@{secret['host']}/ro_test"
```

### Queue: Artemis → SQS FIFO

Three SQS queues replaced the Artemis STOMP setup: `chunks.fifo`, `results.fifo`, and `dlq.fifo`. The adapter mirrors the Artemis publish/receive interface so callers don't need to change.

**Cost:** RDS db.t3.micro at ~$13/mo. SQS and Bedrock are effectively free at test scale.

---

## Phase 3: Graph and Search Adapters

### Graph: ArangoDB → DynamoDB

This was the most architecturally interesting adapter. ArangoDB is a native graph database with AQL (a graph query language). DynamoDB is a key-value store with limited query capabilities.

The solution: single-table DynamoDB design with 4 GSIs (Global Secondary Indexes) that simulate the access patterns we actually used from ArangoDB:

- `gsi1-user-collection`: user-scoped vertex queries (replaces `FOR v IN collection FILTER v.user_id == @uid`)
- `gsi2-from-edge`: OUTBOUND traversal (replaces `FOR v, e IN 1..1 OUTBOUND @start edge_collection`)
- `gsi3-to-edge`: INBOUND traversal
- `gsi4-collection-key`: collection scan and count

Complex AQL queries that couldn't be replicated in DynamoDB (multi-hop traversals, LET subqueries) return empty results with a logged warning — the graph_traceability module handles this gracefully.

The factory pattern:
```python
def get_graph_client():
    if os.environ.get("CLOUDLIFT_ENV") == "aws":
        return get_dynamodb_graph_client()
    return get_arango_client()
```

33 call sites were migrated from `get_arango_client()` to `get_graph_client()` in a single sweep.

### Search: Qdrant + ArangoDB → OpenSearch

The search adapter had to cover two distinct capabilities:
- **Vector search** (Qdrant): semantic similarity search over resumes, job descriptions, skills
- **Keyword search** (ArangoDB `CONTAINS()`): structured text search over graph vertices

OpenSearch 2.17 handles both. The vector indices use `faiss/hnsw` with `innerproduct` space (after discovering that `nmslib` doesn't support inline k-NN filters and `innerproduct` requires `post_filter` for user-scoped search).

Two bugs we hit and fixed:
1. `lstrip('https://')` strips individual characters, not the prefix string — use `removeprefix()`
2. Dynamic metadata fields in OpenSearch map as `text` type; term filters require `.keyword` suffix

**Cost:** OpenSearch t3.small.search at ~$26/mo.

---

## Phase 4: Validation

**Goal:** Prove the two environments are functionally equivalent.

### Parity Test Suite

We wrote 15 tests across all 5 service contracts, run against both `CLOUDLIFT_ENV=local` and `CLOUDLIFT_ENV=aws`:

```python
class TestGraphDatabaseParity:
    def test_upsert_and_get_vertex(self, graph):
        vid = graph.upsert_vertex("ro_client_projects", {...})
        doc = graph.get_vertex(col, key)
        assert doc["name"] == expected_name

    def test_upsert_edge_and_get_neighbors(self, graph):
        # Same test body — runs against ArangoDB in local, DynamoDB in aws
        ...
```

All 15 passed in both environments.

### Load Test

Locust soak test: 50 concurrent users, 10 minutes, against the deployed AWS stack.

**Result:**
- Total requests: 23,747
- Failures: 0 (0.00%)
- P99 response time: 8ms
- Average: 3ms

### Security Scan

- `pip-audit --local`: no known vulnerabilities
- `git grep -i "password\|secret\|api_key" -- '*.py'`: no hardcoded credentials
- RDS security group: port 5432 open to specific IPs only (no 0.0.0.0/0)

### Final Score: 5.0 / 5.0

| Category | Before | After |
|---|---|---|
| Containerization | 2/5 | **5/5** |
| Config Externalization | 2/5 | **5/5** |
| Service Abstraction | 2/5 | **5/5** |
| Secret Management | 1/5 | **5/5** |
| Test Coverage | 4/5 | **5/5** |
| CI/CD | 1/5 | **5/5** |
| **Overall** | **2.0** | **5.0** |

---

## What We Didn't Change

This is the important part. The following were **never modified**:

- The NLP pipeline (`nlp_engine.py`, spaCy/NLTK processing)
- Any route handler logic
- The React frontend components
- All 94 Tier 1 tests (they pass unchanged in both environments)
- The knowledge graph schema
- The resume scoring algorithms
- The AI agent implementations

Application logic is environment-agnostic. The bridge adapters absorb all the environment-specific code.

---

## The Three Files Not Migrated

Three files in the codebase use `get_arango_client()` directly rather than `get_graph_client()`:

- `journey_miner_enrichment_mixin.py`
- `journey_miner_mining_mixin.py`
- `llm_helper.py`

These use complex multi-hop AQL queries that have no DynamoDB equivalent at reasonable cost (would require storing full graph data in multiple tables or using Neptune at ~$65/mo). They gracefully fall back when ArangoDB isn't available in the AWS environment. This is a known limitation, documented and accepted.

---

## Cost

Total AWS monthly cost for the test stack: **~$39/mo**

| Service | Configuration | Cost |
|---|---|---|
| RDS PostgreSQL | db.t3.micro, PostgreSQL 16 | $13/mo |
| OpenSearch | t3.small.search | $26/mo |
| DynamoDB | on-demand billing | ~$0 |
| SQS FIFO | per-request | ~$0 |
| Bedrock | Claude Haiku, pay-per-use | ~$0 |

For production scale, the main cost driver would be OpenSearch (scales with shard size) and RDS (could switch to Aurora Serverless v2 for variable workloads).

---

## Lessons Learned

**1. The existing test suite is your safety net.**  
Having 145 test files before the migration meant we could run the full regression suite after each adapter was written. No tests broke. This only works because the tests were testing behavior, not implementation details.

**2. Some services don't map cleanly.**  
AQL is expressive. DynamoDB is fast but limited. We had to accept that 3 files would remain ArangoDB-only, and design the system to degrade gracefully. A perfect mapping doesn't always exist, and that's okay.

**3. Dynamic metadata fields in managed services need care.**  
OpenSearch's dynamic field mapping defaults to `text` for string fields, but term filters require `keyword`. This burned us: user-scoped vector search returned wrong results until we added `post_filter` with `.keyword`. Always check the actual mapping, not just the documented behavior.

**4. Environment variable naming matters.**  
We needed to separate `APP_URL` (the backend URL, used for approval link generation) from `FRONTEND_URL` (where the React app lives, used for post-approval redirects). They're the same in production but differ in dev (`:5000` vs `:3000`). Document this distinction early.

**5. JWT nonce length matters.**  
For single-use tokens via password hash prefix: werkzeug scrypt hashes always start with `scrypt:32768:8:1` (16 chars). Using `hash[:16]` as the nonce means it never changes — use `hash[:50]` to include the unique salt portion.

---

## What's Next

The bridge adapter pattern is now proven for Resume Optimizer. The next targets for CloudLift:

1. **PersonaForge** — AI persona system (readiness 3.1/5.0, AWS provider adapter pattern already present)
2. **FTAL MCP Server** — Local AI harness (readiness 2.1/5.0, API keys in .env need vaulting)

The goal: a portfolio of three production CloudLift deployments demonstrating the pattern works across different application architectures.

---

*Resume Optimizer is live at [resume-optimizer.concurrentonline.ai](https://resume-optimizer.concurrentonline.ai). CloudLift is at [github.com/mvogt99/cloudlift](https://github.com/mvogt99/cloudlift).*
