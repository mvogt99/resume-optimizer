# Demo Guide

**Live URL:** [resume-optimizer.concurrentonline.ai](https://resume-optimizer.concurrentonline.ai)

This guide walks through the key features for a demo or product walkthrough.

---

## 1. Registration & Approval Flow (2 min)

**Shows:** Admin-gated access, ZOHO email integration, pending state

1. Open the app and click **Register**
2. Enter a test email and a password meeting complexity requirements (e.g., `Demo@test99!`)
3. Submit — you'll see "Registration submitted. Awaiting admin approval."
4. Admin (`mvogt99@gmail.com`) receives an email: "Resume Optimizer Access Request - Production"
5. Click **Approve** in the email → user status changes to active
6. User can now log in

**Key talking points:**
- All environments (dev, test, production) have the same approval flow
- Approve/Reject links are single-use JWT tokens (15-min for password reset, 7-day for registration approval)
- Rejecting an already-approved user shows "Already Processed" — no accidental deletions

---

## 2. Resume Optimization (3 min)

**Shows:** Core ATS scoring, gap analysis, keyword matching

1. Click **Optimize Resume** (default tab)
2. Upload a resume PDF or paste resume text
3. Paste a job description in the right panel
4. Click **Analyze** → scores appear: ATS match %, missing keywords, gap analysis
5. Click **Rewrite** → AI rewrites resume sections to target the job description
6. Compare original vs optimized with the **Version Diff** tab

**Key talking points:**
- spaCy NLP extracts skills, job titles, and requirements
- Keyword matching uses both TF-IDF and semantic similarity (all-MiniLM-L6-v2 embeddings)
- In production, LLM calls go to Bedrock (Claude Haiku); in dev, to local RTX 5090 vLLM

---

## 3. AI Journey Mining (3 min)

**Shows:** Knowledge graph, career event extraction, multi-source intelligence

1. Click **AI Journey** tab
2. Click **Mine Journey** → the system scans uploaded documents
3. Events appear on a timeline: roles, projects, skills, achievements
4. Click an event to see which source documents it came from
5. Click **Knowledge Graph** (Campaigns tab) to see the graph visualization

**Key talking points:**
- Career data is stored as a graph: projects → technologies, outcomes → skills
- In dev: ArangoDB native graph with AQL traversal
- In AWS: DynamoDB single-table design with 4 GSIs for OUTBOUND/INBOUND traversal
- Same application code, different backend, via `get_graph_client()` factory

---

## 4. AI Agents (3 min)

**Shows:** LLM-powered agents, multi-step reasoning, career intelligence

1. Click **AI Agents** tab
2. Try **Job Scout** — paste a job URL or description, get a fit assessment
3. Try **Interview Coach** — select a job posting, run a mock interview with feedback
4. Try **Career Advisor** — get role recommendations based on your journey graph

**Key talking points:**
- In production: Claude Haiku (Bedrock) handles analysis tasks; would use Sonnet for reasoning (currently mapped to Haiku due to regional availability)
- In dev: RTX 5090 running local models via vLLM
- The `cloudlift_llm_adapter.py` bridges both — application code never calls Bedrock or vLLM directly

---

## 5. Admin Panel (1 min)

**Shows:** Role-based access control, user management

1. Log in as admin (`mvogt99@gmail.com`)
2. Click the **Admin** button (top-right header — only visible to admins)
3. See the user table: email, role, status, actions
4. Demo: change a user's role from `user` to `admin`
5. Demo: disable an account (user gets "Your account has been suspended" on login)
6. Demo: create a new user (password auto-set to a default they can reset)

---

## 6. CloudLift Bridge Adapters (dev audience — 3 min)

**Shows:** The core technical innovation

1. Open a terminal: `echo $CLOUDLIFT_ENV` → `local`
2. Show `backend/cloudlift_graph_adapter.py` — DynamoDB implementation of graph operations
3. Show `backend/arango_client.py` `get_graph_client()` — the factory that routes
4. Start the AWS test environment: `docker compose -f docker-compose.aws.yml up`
5. Same UI, port 3001, now talking to RDS + DynamoDB + OpenSearch + Bedrock

**Key talking points:**
- 5 adapters, ~$39/mo full AWS stack
- 0 application code changes between local and AWS
- 15-test parity suite proves equivalence: same operations, same behavior, both environments
- Locust soak test: 50 users, 10 min, P99=8ms, 0 failures

---

## Architecture Diagram Talking Points

```
User → Cloudflare → nginx → React SPA (static)
                          → /api/* → Flask (gunicorn) → CLOUDLIFT_ENV=aws → RDS, DDB, OS, SQS, Bedrock
```

- **Frontend:** Static React build, served by nginx, edge-cached by Cloudflare
- **Backend:** Flask + gunicorn (4 workers), container on Hostinger VPS
- **No Lambda:** The microservice split (Lambda API + Fargate workers) was scaffolded in Phase 2 but the monolith-on-VPS approach was chosen for simplicity at this scale
- **Cost:** ~$39/mo AWS + ~$8/mo VPS = **~$47/mo total** for a production-grade multi-service app

---

## Reset Password Demo (1 min)

1. Click **Forgot Password?** on the login page
2. Enter `mvogt99@gmail.com`
3. Check email — "Resume Optimizer — Password Reset" arrives
4. Click reset link → dedicated `/reset-password/:token` page
5. Enter a new password — live strength bar shows: weak → fair → strong
6. Requirements checklist updates in real time (8 chars, upper, lower, number, symbol)
7. Submit → redirected to login

**Key talking points:**
- Single-use: JWT token contains `password_hash[:50]` as nonce
- After reset, the hash changes → old token is invalidated (try clicking it again: "Invalid or expired")
- 15-minute expiry enforced by JWT `exp` claim

---

## What to Highlight for Different Audiences

| Audience | Key Demo Points |
|---|---|
| **Hiring managers / recruiters** | 1 (approval flow) + 2 (resume optimization) + 5 (admin panel) |
| **Engineers / technical** | 6 (bridge adapters) + architecture diagram + parity tests |
| **Product / startup founders** | 2–4 (feature depth) + cost breakdown ($47/mo total) |
| **DevOps / infrastructure** | Architecture diagram + CI/CD + Locust results |
