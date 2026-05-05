# Resume Optimizer

**AI-powered resume optimization** — ATS scoring, job matching, career coaching, and multi-channel content generation. Designed local-first, deployed cloud-native via [CloudLift](https://github.com/mvogt99/cloudlift).

🌐 **Live:** [resume-optimizer.concurrentonline.ai](https://resume-optimizer.concurrentonline.ai)

---

## What it does

Resume Optimizer helps professionals at every stage of a job search:

- **ATS Optimization** — Score and rewrite resumes against any job description using NLP keyword extraction and gap analysis
- **Resume Builder** — Guided interview-style builder that constructs resume content from scratch
- **AI Career Agents** — Job Scout, Interview Coach, Cover Letter Generator, Career Advisor
- **Knowledge Graph** — ArangoDB graph of skills, projects, outcomes, and career milestones powers contextual recommendations
- **Journey Mining** — Extracts career events from unstructured documents (PDFs, Docs, LinkedIn exports)
- **Campaign Studio** — Multi-post LinkedIn campaign builder with AI-generated content
- **Analytics** — ATS score trends, skills demand, funnel tracking

---

## Architecture

This project is a case study for the **CloudLift bridge adapter pattern** — the same codebase runs against local services in development and AWS services in production, controlled by a single environment variable.

```
CLOUDLIFT_ENV=local   →   local services  (dev, zero cloud cost)
CLOUDLIFT_ENV=aws     →   AWS services    (test/prod, ~$39/mo)
```

### Service Mapping

| Service Type | Local (dev) | AWS (prod) | Bridge Adapter |
|---|---|---|---|
| Graph Database | ArangoDB | DynamoDB | `cloudlift_graph_adapter.py` |
| Relational DB | SQLite | RDS PostgreSQL | `cloudlift_db_adapter.py` |
| Vector + Search | Qdrant + ArangoDB | OpenSearch | `cloudlift_search_adapter.py` |
| Message Queue | Artemis STOMP | SQS FIFO | `cloudlift_queue_adapter.py` |
| LLM Inference | RTX 5090 vLLM | Bedrock (Claude) | `cloudlift_llm_adapter.py` |

### Bridge Adapter Flow

```
Application code
      │
      ▼
cloudlift_*_adapter.py   ←── reads CLOUDLIFT_ENV
      │
      ├── local ──► ArangoDB / SQLite / Qdrant / Artemis / vLLM
      │
      └── aws   ──► DynamoDB / RDS / OpenSearch / SQS / Bedrock
```

See [docs/architecture.md](docs/architecture.md) for full diagrams.

---

## Environments

| Environment | URL | Backend | Command |
|---|---|---|---|
| **Dev** (local services) | `localhost:3000` | `localhost:5000` | `./start-dev.sh` |
| **Test** (AWS services) | `localhost:3001` | `localhost:5001` | `docker compose -f docker-compose.aws.yml up` |
| **Production** | [resume-optimizer.concurrentonline.ai](https://resume-optimizer.concurrentonline.ai) | AWS (RDS + OpenSearch + DynamoDB + Bedrock) | VPS — Docker + nginx + Cloudflare |

---

## Quick Start

### Prerequisites

- Python 3.11+, Node.js 18+, Docker

### Dev environment (local services)

```bash
git clone https://github.com/mvogt99/resume-optimizer.git
cd resume-optimizer

# Install backend
cd backend && pip install -r requirements.txt
python -m spacy download en_core_web_sm

# Install frontend
cd ../frontend && npm install

# Start both (backend :5000, frontend :3000)
cd .. && ./start-dev.sh
```

**Local services** (Docker):
```bash
docker run -d --name hybrid-arangodb -p 8529:8529 \
  -e ARANGO_ROOT_PASSWORD=hybrid_ai_root arangodb:3.12
docker run -d --name hybrid-qdrant    -p 6333:6333 qdrant/qdrant
docker run -d --name hybrid-artemis   -p 61613:61613 apache/activemq-artemis
```

### AWS test environment

```bash
# Requires AWS credentials + services provisioned (see docs/architecture.md)
cp backend/.env.example backend/.env  # fill in your values
docker compose -f docker-compose.aws.yml up
# Frontend: http://localhost:3001 / API: http://localhost:5001
```

---

## User Management

All environments use an **admin-approval registration flow**:

1. New users register → account is **pending**
2. Admin receives an email with one-click Approve / Reject links
3. Only approved users can log in

**Admin panel:** Log in as admin → "Admin" button → manage users, roles, and access.

**Password requirements:** ≥8 chars, uppercase, lowercase, number, symbol, not contain email prefix.

**Forgot Password:** Link on the login page — sends a 15-minute single-use reset link.

---

## Tech Stack

**Backend:** Python 3.12, Flask 3.1, SQLAlchemy, spaCy, NLTK, psycopg2, boto3

**Frontend:** React 18, React Router 6, Vite, axios

**Local services:** ArangoDB 3.12, Qdrant, ActiveMQ Artemis, SQLite

**AWS services:** RDS PostgreSQL (db.t3.micro), DynamoDB (on-demand, 4 GSIs), OpenSearch 2.17 (faiss/hnsw/innerproduct), SQS FIFO, Bedrock (Claude Haiku)

**Infrastructure:** Docker, nginx, Cloudflare, Let's Encrypt, GitHub Actions CI

**Rearchitected by:** [CloudLift](https://github.com/mvogt99/cloudlift)

---

## Project Structure

```
resume-optimizer/
├── backend/
│   ├── cloudlift_db_adapter.py     SQLite ↔ RDS PostgreSQL bridge
│   ├── cloudlift_graph_adapter.py  ArangoDB ↔ DynamoDB bridge
│   ├── cloudlift_search_adapter.py Qdrant+ArangoDB ↔ OpenSearch bridge
│   ├── cloudlift_queue_adapter.py  Artemis STOMP ↔ SQS FIFO bridge
│   ├── cloudlift_llm_adapter.py    vLLM ↔ Bedrock bridge
│   ├── routes/                     Flask blueprints (auth, admin, agents, …)
│   └── tests/                      Unit, integration, parity, load tests
├── frontend/src/
│   ├── components/                 ~60 React components
│   └── pages/                      Full-page routes (ResetPasswordPage, …)
├── docker-compose.yml              Full local stack
├── docker-compose.aws.yml          AWS-backed stack (~$39/mo)
├── start-dev.sh                    One-command local dev startup
└── docs/
    ├── architecture.md             Bridge adapter diagrams + AWS resource map
    └── blog-cloudlift-rearchitecture.md  How CloudLift rearchitected this app
```

---

## CloudLift Readiness: 5.0 / 5.0

4-phase rearchitecture from a local-only app to a cloud-native deployment:

| Phase | What changed | Score |
|---|---|---|
| Phase 1 | Config externalization, Docker fix, CI/CD | 2.0 → 3.5 |
| Phase 2 | LLM + DB + Queue AWS adapters (Bedrock, RDS, SQS) | 3.5 → 4.2 |
| Phase 3 | Graph + Search adapters (DynamoDB, OpenSearch) | 4.2 → 4.8 |
| Phase 4 | Parity tests, Locust soak, security scan | 4.8 → **5.0** |

Full story: [docs/blog-cloudlift-rearchitecture.md](docs/blog-cloudlift-rearchitecture.md)

---

## License

MIT
