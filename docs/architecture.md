# Architecture: CloudLift Bridge Adapter Pattern

## Overview

Resume Optimizer uses the **bridge adapter pattern** introduced by [CloudLift](https://github.com/mvogt99/cloudlift) to decouple application code from the underlying service implementations. A single environment variable (`CLOUDLIFT_ENV`) routes all service calls to either local or cloud backends — no code changes required.

---

## Bridge Adapter Pattern

```mermaid
graph TB
    App["Application Code<br/>(routes, agents, services)"]

    subgraph Adapters ["Bridge Adapters (cloudlift_*_adapter.py)"]
        DB["cloudlift_db_adapter<br/>IRelationalDatabase"]
        Graph["cloudlift_graph_adapter<br/>IGraphDatabase"]
        Search["cloudlift_search_adapter<br/>IVectorSearch"]
        Queue["cloudlift_queue_adapter<br/>IMessageQueue"]
        LLM["cloudlift_llm_adapter<br/>ILLMInference"]
    end

    subgraph Local ["CLOUDLIFT_ENV=local (dev)"]
        SQLite["SQLite"]
        Arango["ArangoDB"]
        Qdrant["Qdrant + ArangoDB CONTAINS()"]
        Artemis["ActiveMQ Artemis STOMP"]
        VLLM["RTX 5090 vLLM"]
    end

    subgraph AWS ["CLOUDLIFT_ENV=aws (test/prod)"]
        RDS["RDS PostgreSQL"]
        Dynamo["DynamoDB"]
        OS["OpenSearch 2.17<br/>(faiss/hnsw/innerproduct)"]
        SQS["SQS FIFO"]
        Bedrock["Bedrock<br/>(Claude Haiku)"]
    end

    App --> DB
    App --> Graph
    App --> Search
    App --> Queue
    App --> LLM

    DB -->|local| SQLite
    DB -->|aws| RDS
    Graph -->|local| Arango
    Graph -->|aws| Dynamo
    Search -->|local| Qdrant
    Search -->|aws| OS
    Queue -->|local| Artemis
    Queue -->|aws| SQS
    LLM -->|local| VLLM
    LLM -->|aws| Bedrock

    style Local fill:#e8f5e9,stroke:#4caf50
    style AWS fill:#e3f2fd,stroke:#2196f3
    style Adapters fill:#fff3e0,stroke:#ff9800
```

---

## Service Mapping Detail

| Contract Interface | Local Adapter | AWS Adapter | Notes |
|---|---|---|---|
| `IRelationalDatabase` | SQLite (via db_engine.py) | RDS PostgreSQL db.t3.micro | `cloudlift_db_adapter.resolve_database_url()` fetches credentials from Secrets Manager |
| `IGraphDatabase` | ArangoDB localhost:8529 | DynamoDB `ro-test-graph` | Single-table design, 4 GSIs for traversal; `get_graph_client()` factory |
| `IVectorSearch` | Qdrant localhost:6333 | OpenSearch managed domain | 384-dim cosine (all-MiniLM-L6-v2); `post_filter` for user-scoped search |
| `IMessageQueue` | Artemis STOMP localhost:61613 | SQS FIFO `ro-test-analysis-*.fifo` | 3 queues: chunks, results, DLQ |
| `ILLMInference` | vLLM localhost:8021 (smart_llm.py) | Bedrock Claude Haiku | Task-type routing (analysis→Haiku, reasoning→Sonnet) |

---

## AWS Resource Map

```mermaid
graph LR
    App["Resume Optimizer<br/>(Docker on VPS)"]

    subgraph AWS_us_east_1 ["AWS us-east-1"]
        RDS["RDS ro-test-pg<br/>db.t3.micro / PG16<br/>~$13/mo"]
        SM_RDS["Secrets Manager<br/>ro/test/db"]
        DDB["DynamoDB ro-test-graph<br/>on-demand<br/>~$0"]
        OS["OpenSearch ro-test-search<br/>t3.small.search<br/>~$26/mo"]
        SM_OS["Secrets Manager<br/>ro/test/opensearch"]
        SQS1["SQS ro-test-analysis-chunks.fifo"]
        SQS2["SQS ro-test-analysis-results.fifo"]
        SQSD["SQS ro-test-analysis-dlq.fifo"]
        BR["Bedrock<br/>Claude Haiku 4.5<br/>pay-per-use"]
    end

    App -->|DATABASE_URL| RDS
    SM_RDS -->|credentials| RDS
    App -->|USER_TABLE=users_prod| RDS
    App -->|graph queries| DDB
    App -->|vector + keyword search| OS
    SM_OS -->|credentials| OS
    App -->|chunk dispatch| SQS1
    App -->|result collection| SQS2
    SQS1 -->|dead letter| SQSD
    App -->|LLM inference| BR
```

**Total AWS cost:** ~$39/mo (RDS $13 + OpenSearch $26; DynamoDB/SQS/Bedrock are pay-per-use at near-zero test scale)

---

## Environment-Specific User Tables

All three environments that use PostgreSQL share the same RDS instance but use **separate user tables** to prevent cross-environment user pollution:

| Environment | `USER_TABLE` env var | Table on RDS |
|---|---|---|
| Dev (SQLite) | `users` | `users` (SQLite, isolated by file) |
| Docker AWS test | `users_test` | `users_test` on `ro_test` DB |
| Production VPS | `users_prod` | `users_prod` on `ro_test` DB |

---

## OpenSearch Index Design

Three vector indices (384-dim cosine, all-MiniLM-L6-v2, faiss/hnsw/innerproduct):
- `ro_resumes` — resume text chunk embeddings
- `ro_job_descriptions` — job description embeddings
- `ro_skills_taxonomy` — canonical skill name embeddings

Three keyword indices (BM25 full-text):
- `ro_graph_client_projects` — project vertex data
- `ro_graph_ai_skills` — AI skills vertex data
- `ro_graph_journey_milestones` — journey milestone data

User-scoped search uses `post_filter` on `metadata.user_id.keyword` (dynamic field mapped as text, requiring `.keyword` for exact match).

---

## DynamoDB Graph Schema

Single-table design (`ro-test-graph`):

| Key | Format | Purpose |
|---|---|---|
| `pk` | `vertex#{collection}` or `edge#{collection}` | Entity type |
| `sk` | SHA-1 hex of key source | Deterministic dedup |
| GSI `gsi1-user-collection` | PK=user_id, SK=collection | User-scoped vertex queries |
| GSI `gsi2-from-edge` | PK=from_id, SK=edge_collection | OUTBOUND traversal |
| GSI `gsi3-to-edge` | PK=to_id, SK=edge_collection | INBOUND traversal |
| GSI `gsi4-collection-key` | PK=collection, SK=sk | Collection scan / count |

Floats are stored as `Decimal` (DynamoDB requirement) and converted back on read.

---

## Deployment Topology

```mermaid
graph TB
    User["User Browser"]

    subgraph CF ["Cloudflare (CDN + DDoS)"]
        CF_Edge["Edge Cache"]
    end

    subgraph VPS ["Hostinger VPS (82.180.130.7)"]
        nginx["nginx:alpine<br/>TLS termination<br/>Port 443"]
        Frontend["nginx:alpine<br/>React SPA<br/>(static build)"]
        Backend["Python 3.11 + Flask<br/>gunicorn 4 workers<br/>Port 5000"]
        Vol["Docker Volume<br/>SQLite + uploads"]
    end

    User -->|HTTPS| CF_Edge
    CF_Edge -->|proxied| nginx
    nginx -->|/api/*| Backend
    nginx -->|/*| Frontend
    Backend --> Vol
    Backend -->|CLOUDLIFT_ENV=aws| AWS_us_east_1["AWS us-east-1<br/>(RDS, DDB, OS, SQS, Bedrock)"]

    style CF fill:#f0a500,color:#fff
    style VPS fill:#e8eaf6,stroke:#3f51b5
```

**nginx routes:**
- `/*.well-known/acme-challenge/` → Certbot (Let's Encrypt renewal)
- `/api/*` → Flask backend container
- `/*` → React SPA (nginx static file server)

---

## CI/CD Pipeline

```mermaid
graph LR
    Push["git push main"] --> GH["GitHub Actions"]
    GH --> Lint["ruff check backend/"]
    GH --> Tests["pytest CLOUDLIFT_ENV=local"]
    GH --> Build["docker build (validate)"]
    Tests --> Pass{All green?}
    Pass -->|yes| Manual["Manual: Tier 2 parity tests<br/>(live AWS)"]
    Manual --> Deploy["rsync → VPS<br/>docker compose restart"]
```

Tier 2 parity tests (hitting live RDS, OpenSearch, DynamoDB) run on-demand before production deploys — they cost real AWS money and aren't run in CI.
