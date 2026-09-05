# Detailed Design — Interview & Rejection Intelligence (IRI)
## Resume Optimizer — Phase 18

> **Document type:** Detailed design. **This is not an implementation plan.** No sequencing, estimates, task breakdown or milestones.
> **Version:** 1.0 · **Date:** 2026-09-03 · **Status:** Draft for review
> **Satisfies:** `REQUIREMENTS_Interview_Rejection_Intelligence_2026-09-03.md` (171 requirements)
> **CoE consultation:** `advise_call_id: 8a05b0ee-aeda-41f6-8cdb-4b879b983c29`
> **CoE-cited:** `multi-cloud-bridge-adapter-abstraction`, `cloudlift-deployment-plane`, `bridge-adapter-interface-pattern`, `multi-tenant-saas`, `rag-service-with-vector-search-and-llm-inference`, **`local-to-azure-service-mapping`**
> **Revision 1.1 (2026-09-04):** Azure verified complete against the CloudLift source tree and the CoE's live-validated Azure mapping. §5.2, §5.3, §13, §14 and OI-1 revised accordingly; DD-09, DD-10 added.
> **Revision 1.2 (2026-09-04):** OI-9, OI-11 and OI-12 resolved by Mike; DD-11, DD-12, DD-13 added. `CLOUDLIFT_ENV` confirmed as the single environment variable.
> **Revision 1.3 (2026-09-04):** OI-2 through OI-8, OI-10 and OI-13 resolved; DD-14 to DD-20 added. **P-3 amended** — the local GPU is now inside the trust boundary (DD-15). All open items are now closed.
>
> **Revision 2.0 (2026-09-05):** **Three-way parity is real, and DD-27's caveat is retired.** CloudLift ran the first genuine three-way capture (`docs/parity_three_way_results.md`, commit `6a2deb8`, all three captured at the same instant): **4 contracts in full three-way parity — `IObjectStorage`, `IRelationalDatabase`, `ILLMInference`, `IEmbeddingService` — 7 more in two-way, and 0 divergences across all 11 comparable contracts.** Per-environment coverage local 11/12, aws 8/12, azure 8/12. Total cost under $1. Every gap is an absent service, named rather than skipped, not an adapter defect.
>
> **DD-27 PROVEN.** The Gremlin container from `0f309cf` was applied for this run and Azure `IGraphDatabase` passed `upsert/list/traverse/delete` at the exact contract score formula. The container naming and partition key are correct against a real Cosmos account. IRI's provisioner should still verify existence — a tenant's container is created per tenant, and only the `az091` tenant's was exercised — but the *mechanism* is no longer unproven. What the apply proved is narrower and worth stating exactly: **the Terraform-created graph works** — `edge_is_listed`, `traverse_reaches_target`, `score_follows_contract` and `endpoints_populated` all true against a container created by `apply` rather than by a script. So the naming (`t_<tenant uuid with underscores>_<collection>`) and the `/_pk` partition key are correct against a real Cosmos account. *(Corrected 2026-09-05: an earlier revision credited this apply with catching the Gremlin factory's SQL-account-key defect. It did not — that was one of the nine defects AZ-091's live round trips found in commit `6892242` at 11:45, nearly five hours before the Gremlin Terraform existed in `0f309cf` at 16:24. Verified against git history. Two different applies, merged in my reading.)*
>
> ⚠ **Two coverage gaps IRI should note.** `IGraphDatabase` has **no AWS arm** (Neptune has no public endpoint at any setting — it is VPC-only, so covering it needs the suite to run inside the VPC, which is different work rather than more spend), and `IVectorSearch` has **no Azure arm** (westus3 had no `basic` AI Search capacity; free tier cannot do vector search and `standard` is ~$250/mo). Both are contracts IRI depends on. Neither is broken — both are simply uncompared in one environment.
>
> **Revision 1.9 (2026-09-05):** **DD-24 confirmed — AWS parity now exists.** CloudLift provisioned the zero-hourly-cost AWS services and ran the first genuine AWS comparison: **7/12 contracts live, 3 in parity with local, 0 divergences**. Offline `--capture-dir`/`--compare` removes the need for all three environments to be up simultaneously, so Azure being destroyed no longer blocks three-way. IRI keeps DD-24 and builds no adapter parity of its own.
>
> **DD-27 partially delivered, explicitly unproven.** The Gremlin graph container is wired in CloudLift's Terraform (`0f309cf`) — the `cosmosdb` module always supported `var.containers`; the stack simply never passed any. **It has not been applied**, and `terraform validate` cannot see Azure control-plane semantics. IRI's provisioner verifying existence and refusing to activate a tenant remains load-bearing, not belt-and-braces.
>
> **DD-26 cleared for parity:** the `IGraphDatabase` scenario asserts on traversal results, edge endpoints and the score formula — never on collection layout — so the deliberate one-container-vs-six shape divergence will not false-flag.
>
> **Revision 1.8 (2026-09-05):** **DD-26 and DD-27 added**, resolving the two questions DD-22 raised. Azure uses **one graph container per tenant** with edge type as a property (600 containers → 100), and **CloudLift's Terraform creates it** while IRI's provisioner verifies. Together these make the cross-session ask small and keep Cosmos-specific code out of IRI.
>
> **Revision 1.7 (2026-09-05):** **DD-25 added — LLM endpoint pinned.** The FTAL harness was found to fall back to Anthropic's API unconditionally on local-inference failure; IRI now routes analysis through CloudLift's `ILLMInference` adapter instead, which fails closed. Enforced by test, not convention.
>
> **Revision 1.6 (2026-09-05):** **DD-23 amended** — CloudLift fixed the AI Search metadata divergence (new `metadata_json` field; arbitrary metadata now round-trips local↔azure). Metadata carriage is portable; **filtering on it is not**, so the relational join survives for query paths only. ⚠ **The Azure dev stack is now DESTROYED** (42/42 complete). Any future Azure verification needs a ~25 min rebuild — see §14.3. **New operational constraint:** Azure PITR does not survive a destroy (unlike an AWS RDS final snapshot), so **if IRI ever holds real data in an Azure stack, it must be exported before teardown** — what persists is infrastructure, not data.
>
> **Revision 1.5 (2026-09-04):** **OI-10's premise is withdrawn.** CloudLift **AZ-061 is now built and validated** (cloudlift-c1): `core/testing/parity/three_way.py` + one scenario per contract + `scripts/azure_parity_run.sh`, live result **10 in parity / 0 divergences** local vs azure (IEmbeddingService and IFunctionExecution unavailable locally, reported as such). **DD-24 added.** IRI no longer builds adapter-level parity; it consumes AZ-061 and owns only finding-level parity plus whatever AZ-061 normalises away. ⚠ **Also material:** AZ-061 found that local `IMessageQueue` **could never receive a message** (an `int()` on the boolean `redelivered` header killed every inbound message inside the stomp.py callback) and that Artemis auto-created destinations with MULTICAST routing, silently discarding messages published before a subscriber attached. Both are fixed. Every worker in §6 depends on `IMessageQueue`; that dependency was untested-and-broken until 2026-09-04.
>
> **Revision 1.4 (2026-09-04):** Amended by **measurement** against the live Azure dev stack — see `IRI_S0_Azure_Spike_Findings_2026-09-04.md`. DD-10 confirmed and quantified (Gremlin visibility lag 562 ms, writes 2164 ms). **DD-21, DD-22, DD-23 added** from three findings the spike surfaced: AI Search is also not read-your-writes; Gremlin edge collections must be pre-provisioned per tenant; the AI Search index schema is fixed at `id`/`content`/`embedding` and rejects arbitrary metadata. OI-13's `supports_feature` caveat is **withdrawn** — the member is present on the live adapter.

---

## 1. Purpose and scope

This document specifies **how** the IRI capability is built. It covers component decomposition, adapter contracts, data design, processing pipeline, privacy mechanics, analysis engine, multi-tenancy, environment mapping, and interfaces.

Requirement identifiers (`REQ-nnn`) trace back to the requirements document. Design decisions with material trade-offs are recorded as `DD-nn` in §20.

## 2. Design principles

| # | Principle | Derived from |
|---|---|---|
| P-1 | **No cloud SDK in application logic.** All external service access goes through a bridge adapter with a contract interface. | REQ-432, CoE `bridge-adapter-interface-pattern` |
| P-2 | **Evidence is immutable.** Ingested content is never mutated; all derivation produces new records carrying lineage. | REQ-121, REQ-461 |
| P-3 | **Privacy controls fail closed** *on any path that leaves the machine*. Any failure in redaction, isolation or retention blocks the operation rather than degrading it. **Amended in Rev 1.3 (DD-15): self-hosted models running on the user's own hardware are inside the trust boundary and receive unredacted content; every cloud model call is redacted and fails closed.** | REQ-485, REQ-593 |
| P-4 | **Machine output is provisional until adjudicated.** Nothing automated becomes authoritative without human confirmation. | REQ-330, REQ-236 |
| P-5 | **Environment differences are configuration, never code paths in business logic.** | REQ-431, REQ-434, REQ-439 |
| P-6 | **Idempotency everywhere.** Every pipeline stage is safely re-runnable, keyed on content hash plus stage version. | REQ-530, REQ-316 |
| P-7 | **Analysis is auditable.** Every conclusion carries its evidence, the model that produced it, and the prompt version. | REQ-181, REQ-216 |

## 3. System context

IRI is a subsystem of the existing Resume Optimizer, not a standalone product.

```
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│    Krisp     │   │    Gmail     │   │  MS365 /     │   │   Manual     │
│  (meetings)  │   │              │   │  Teams       │   │   upload     │
└──────┬───────┘   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
       │  OAuth (per user) │                  │                  │
       └──────────┬────────┴─────────┬────────┴─────────┬────────┘
                  ▼                  ▼                  ▼
        ╔═══════════════════════════════════════════════════════╗
        ║   IRI SUBSYSTEM  (backend/iri/ + workers/iri/)         ║
        ║   Connectors → Pipeline → Analysis → Adjudication      ║
        ╚═══════════════════════════════════════════════════════╝
                  │                  │                  │
                  ▼                  ▼                  ▼
        ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
        │   Tracker    │   │  Verified-   │   │  Postmortem  │
        │  (postings)  │   │ Skills Record│   │   artifacts  │
        └──────────────┘   └──────────────┘   └──────────────┘
                  All access via CloudLift bridge adapters
```

**Trust boundary:** everything inside the IRI subsystem and its adapters is trusted, **and per DD-15 that boundary includes self-hosted models running on the user's own hardware**. A call to the local vLLM instance does not leave the machine and is not redacted. **Every call to a cloud-hosted model crosses the boundary and is redacted, failing closed on any detection failure** (§9).

## 4. Component decomposition

Per **DD-02** (§20), IRI extends the existing Flask backend and the existing workers service rather than introducing a new deployable.

### 4.1 Backend components — `backend/iri/`

| Component | Responsibility |
|---|---|
| `connectors/` | Per-source retrieval. One module per source implementing `IEvidenceSource`. Owns OAuth flow initiation, token refresh, incremental cursors. |
| `ingestion.py` | Normalises source payloads into the canonical evidence representation; deduplicates; computes content hashes; persists raw and normalised forms. |
| `classification.py` | Outcome detection and classification. Deterministic rules first, model-assisted second. Emits confidence. |
| `correlation.py` | Links evidence and outcomes to tracked postings. Multi-signal scoring. |
| `redaction.py` | Deterministic pseudonymisation, vault management, reversal for display. |
| `analysis/` | Forensic analysis orchestration, second opinion, reconciliation. |
| `claims.py` | Claim extraction and discrepancy detection against the verified-skills record. |
| `skills_record.py` | Read/write interface to the verified-skills record (hybrid store). |
| `postmortem.py` | Artifact composition and rendering. |
| `aggregation.py` | Cross-outcome pattern analysis. |
| `review.py` | Human review queue and adjudication state machine. |
| `routes/iri_routes.py` | Flask Blueprint — the HTTP API (§15). |

### 4.2 Worker components — `resume-optimizer-workers/workers/iri/`

| Worker | Consumes | Responsibility |
|---|---|---|
| `ingest_worker.py` | `iri.ingest.requested` | Pull from a source, normalise, persist, emit `iri.evidence.ingested` |
| `classify_worker.py` | `iri.evidence.ingested` | Classify outcome, emit `iri.outcome.detected` |
| `correlate_worker.py` | `iri.outcome.detected` | Correlate to posting, emit `iri.outcome.correlated` |
| `analysis_worker.py` | `iri.analysis.requested` | Redact → primary analysis → second opinion → reconcile → emit `iri.analysis.completed` |
| `aggregate_worker.py` | `iri.analysis.completed`, schedule | Recompute cross-outcome patterns |
| `retention_worker.py` | schedule | Enforce retention, execute purges, verify cascade |

Workers are **stateless**; all state lives in adapter-backed stores. Concurrency control is via the queue adapter's visibility semantics plus an idempotency key (P-6).

### 4.3 Frontend components — `frontend/src/components/iri/`

`ConnectorManager` · `OutcomeTimeline` · `PostmortemView` · `ClaimAdjudication` · `PatternDashboard` · `ReviewQueue` · `RetentionPanel`

## 5. Adapter contracts

### 5.1 Reused adapters
`cloudlift_db_adapter` · `cloudlift_graph_adapter` · `cloudlift_vector_adapter` · `cloudlift_search_adapter` · `cloudlift_queue_adapter` · `cloudlift_llm_adapter`

### 5.2 Existing CloudLift contracts IRI consumes

**Verified against the CloudLift source tree and confirmed by the CloudLift maintainer session, 2026-09-04.** CloudLift registers **12 bridge contracts**, and `registered_for_env()` returns **12 for local, 12 for aws, 12 for azure** — 36 registrations. (`IAdminAdapter` and `ISystemAdapter` also exist in `contracts/` but are not registered service contracts; an earlier "14 contracts / 28 adapters" figure circulating in the CoE is **wrong**.) IRI uses:

| Contract | IRI use |
|---|---|
| `IRelationalDatabase` | System of record — claims, adjudications, outcomes, analyses, correlations, retention state |
| `IGraphDatabase` | Skill/engagement/person/outcome projection |
| `IVectorSearch` | Retrieval over long transcripts during analysis (§10.2) |
| `IEmbeddingService` | Embedding generation for that retrieval — **a first-class contract; do not fold it into the vector adapter** |
| `IMessageQueue` | Pipeline stage decoupling |
| `ILLMInference` | Primary and second-opinion analysis |
| **`IObjectStorage`** | **Already exists** — raw evidence payloads, transcript archives, rendered postmortems |
| `IDocumentDatabase` | Candidate store for normalised evidence documents (design-time choice vs relational + object storage) |
| `ILifecycleDatabase` | Candidate store for retention and purge state |
| `IFunctionExecution` | Candidate execution surface for scheduled work (see `IScheduler` below) |

### 5.2.1 New adapter contracts genuinely required (REQ-433)

**Corrected from Revision 1.0**, which listed four. `IObjectStorage` already exists. Source inspection of `core/bridge/contracts/` confirms **no secrets, scheduler, or notification contract**, so three remain genuinely new:

| Contract | Purpose | local | aws | azure |
|---|---|---|---|---|
| **`ISecretStore`** | Per-user OAuth tokens and refresh tokens; connector credentials. | Encrypted local store / OS keyring | Secrets Manager | Key Vault |
| **`IScheduler`** | Cadence triggers for polling, aggregation and retention. | APScheduler in-process | EventBridge Scheduler | Timer-triggered Functions |
| **`INotifier`** | Outcome detection, analysis completion, connector-failure notifications. | Local relay / UI-only | SES / SNS | Communication Services |

**All three confirmed absent by the CloudLift maintainer**, not merely absent from the contracts directory:
- **`ISecretStore`** — no contract, no adapter, in any environment. A Key Vault Terraform module exists, but *nothing in the bridge layer talks to it*.
- **`IScheduler`** — CloudLift has scheduling machinery (`HibernationSchedule` + Celery Beat) but it is **control-plane infrastructure for managing deployments, not a contract an application calls**. `IFunctionExecution` is invocation, not scheduling. IRI's scheduler is genuinely new.
- **`INotifier`** — an internal `app/services/email.py` exists for operator alerts; nothing contract-shaped, nothing on Communication Services.

⚠ **Key Vault naming constraint** applies to `ISecretStore` on Azure: names are **globally unique and soft-delete reserves them**, so a deleted-and-recreated environment cannot reuse a name for the retention period.

**`IEvidenceSource`** is deliberately **not** a CloudLift adapter. Krisp, Gmail and Microsoft Graph are external SaaS reached identically from every environment (REQ-436); they vary by *user*, not by *cloud*. Treating them as CloudLift adapters would wrongly imply per-cloud implementations.

```
IEvidenceSource
  authorize_url(user_id)             -> str
  complete_authorization(user_id, code) -> ConnectionState
  refresh(user_id)                   -> ConnectionState
  revoke(user_id)                    -> None
  health(user_id)                    -> SourceHealth
  fetch_since(user_id, cursor, limit)-> (list[RawEvidence], next_cursor)
```

### 5.3 How IRI consumes adapters — corrected

**Revision 1.0 recorded a finding that Azure was missing at the app level and might be unbuilt. That was wrong, and the correction changes the design (DD-09).**

Verified 2026-09-04 against `/home/mike/models/source/projects/cloudlift`:

- **12 Azure adapters are implemented** in `core/bridge/azure/` — Blob, Postgres, Cosmos (Core/SQL), Cosmos Gremlin, Cosmos Lifecycle, AI Search, Managed Redis, Service Bus, Azure OpenAI, Azure OpenAI Embedding, Functions, Synapse.
- **They are registered**, not merely present: `core/bridge/defaults.py` imports and registers all twelve, and its docstring states registration runs automatically on `core/bridge/__init__` import.
- **`azure` is a first-class environment** in `core/settings.py` (`self.environment in ("aws", "azure", "neon")`).
- **The CoE records the mapping as `validated`**, with a live round-trip run in **westus3 on 2026-09-04: 12 passed, 0 failed, 0 skipped** (`scripts/azure_az091_run.sh`).

The gap is therefore **not** in CloudLift — it is that the resume-optimizer's *own* shims (`backend/cloudlift_*_adapter.py`) reimplement a narrow subset for local and aws only, bypassing CloudLift entirely.

**IRI does not extend those shims. It consumes CloudLift's real adapters.**

⚠ **The reason the shims exist is no longer true.** `cloudlift_llm_adapter.py` carries a comment saying the `cloudlift.bridge.*` namespace "suffers from module identity split (core.* vs cloudlift.*) that breaks the tenant context system." **That was fixed.** `cloudlift/` is now a meta-path alias package redirecting `cloudlift.*` → `core.*`, so both names resolve to the *same module objects* (`cloudlift.bridge.contracts.IObjectStorage is core.bridge.contracts.IObjectStorage` → `True`, verified by the maintainer session). **`cloudlift.bridge.*` is the supported, stable import path for exactly this case.**

Supported usage:

```python
import cloudlift.bridge                                    # registers the defaults
from cloudlift.bridge.contracts import ILLMInference
from cloudlift.bridge.resolver import AdapterResolver
from cloudlift.bridge.tenant_context import explicit_tenant

resolver = AdapterResolver(env=os.environ["CLOUDLIFT_ENV"])
with explicit_tenant(tenant_uuid):
    llm = resolver.resolve(tenant_uuid, ILLMInference)
```

The resolver selects the registered factory for the environment and caches per `(tenant_id, contract)`.

> The maintainer session's judgement, recorded verbatim because it bears on DD-09: *"App-level shims re-implementing per provider is precisely the failure mode that produced the mess I spent this initiative cleaning up."*

✅ **Environment variable — resolved (DD-11).** **`CLOUDLIFT_ENV` is the single source of truth** for the resume-optimizer and IRI, matching what `./ro`, `start-dev.sh` and the existing shims already set.

The ambiguity is **designed out rather than reconciled**: IRI never relies on CloudLift's implicit settings lookup. It passes the environment explicitly at construction, which the resolver supports —

```python
resolver = AdapterResolver(env=os.environ["CLOUDLIFT_ENV"])
```

`AdapterResolver.__init__(env: str | None = None)` documents that it "reads CLOUDLIFT_ENV (via Settings.environment) to select the active environment, **unless overridden at construction**." Passing it explicitly means IRI's environment selection cannot drift from `./ro`'s, regardless of what CloudLift's own settings layer reads or how that changes later. No change is required in either codebase.

ℹ Worth noting for whoever maintains CloudLift: its `resolver.py` docstring says `CLOUDLIFT_ENV` while `settings.py` documents `CLOUDLIFT_ENVIRONMENT`. Explicit construction sidesteps the inconsistency entirely.

ℹ CloudLift also registers **`neon`** and a `paas/` provider family beyond local/aws/azure. IRI targets the three named in the requirements; the resolver imposes no barrier to the others.

## 6. Data design

Per **DD-01**, the verified-skills record and IRI data use a **hybrid relational + graph** model.

### 6.1 Division of responsibility

| Concern | Store | Rationale |
|---|---|---|
| System of record for claims, adjudications, outcomes, analyses, correlations, retention state | **Relational** (`IRelationalDatabase`) | Transactional integrity, auditability, straightforward cascade deletion, simple isolation predicates |
| Relationship-heavy queries — which engagement evidenced which skill, which interviewers recur, which skill clusters co-occur in rejections | **Graph** (`IGraphDatabase`) | Traversal is the natural query shape; matches the existing `ro_` knowledge graph |
| Large payloads — raw transcripts, email bodies, rendered artifacts | **Object storage** (`IObjectStorage`) | Size; relational rows hold references, not content |
| Semantic retrieval over evidence during analysis | **Vector** (`IVectorStore`) | Retrieval-augmented analysis of long transcripts (§10.2) |

**The relational store is authoritative.** The graph is a projection, rebuilt from relational state. This keeps deletion cascades (REQ-465, REQ-488) tractable — purge relationally, then reproject.

### 6.2 Core relational entities

Conceptual, not DDL:

- **`evidence_item`** — user, source, native id, content hash, kind (transcript/email/upload), captured timestamp, object-storage reference, ingestion state, partial-retrieval flag
- **`evidence_participant`** — evidence item, role (candidate/interviewer/recruiter/other), display name, pseudonym token, resolved identity reference
- **`outcome_event`** — user, kind, detected timestamp, confidence, classification method, contributing evidence, human-confirmed flag
- **`correlation`** — outcome/evidence → posting, confidence, signals used, human-confirmed flag, correction history
- **`analysis`** — outcome, role (primary/second-opinion), model identifier, prompt version, produced timestamp, cost, structured findings, status
- **`reconciliation`** — the two analyses, agreement set, divergence set, confidence assessment
- **`claim`** — extracted from evidence: subject technology/skill, assertion type (experience/recommendation/aspiration), verbatim quote, source location
- **`skill_record`** — the verified-skills record: canonical skill, status (verified/refuted/unverified), depth, provenance references, last adjudicated
- **`discrepancy`** — claim vs skill_record: direction (over-claim/under-claim/record-error), severity, adjudication status, decision, rationale
- **`postmortem`** — outcome, version, object-storage reference, generated timestamp, superseded-by
- **`aggregate_finding`** — pattern kind, supporting outcomes, sample size, confidence, first/last observed
- **`retention_policy`** / **`purge_log`** — per-user retention windows and executed purges
- **`access_log`** / **`model_call_log`** — REQ-481, REQ-482

Every table carries `user_id`; isolation is enforced at the data-access layer (§13).

### 6.3 Graph projection

Vertices: `Skill` · `Engagement` · `Employer` · `Person` (pseudonymised) · `Outcome` · `EvidenceItem`
Edges: `EVIDENCED_BY` · `CLAIMED_IN` · `REFUTED_BY` · `PARTICIPATED_IN` · `APPLIED_TO` · `CO_OCCURS_WITH`

This answers questions the relational model answers poorly: *which skills co-occur in rejected applications*, *which interviewers appear across multiple processes*, *which engagement is the provenance root for a contested claim*.

## 7. Processing pipeline

Six stages, each a queue-decoupled worker, each idempotent on `(content_hash, stage, stage_version)`.

```
 [trigger] ──► INGEST ──► NORMALISE ──► CLASSIFY ──► CORRELATE ──► ANALYSE ──► ADJUDICATE
                 │            │            │             │            │            │
              raw to      canonical     outcome      posting     redact →      human
              object      form +        + conf.      link +      primary →     decision
              storage     dedupe                     conf.       2nd → recon   → durable
```

**Stage versioning** enables selective re-processing: bumping the analysis stage version re-runs analysis without re-ingesting (REQ-553).

**Back-pressure:** the queue adapter provides natural back-pressure. Analysis is the expensive stage; it consumes from a dedicated queue so ingestion is never blocked by model latency.

### 7.1 Triggers (REQ-310 to REQ-313)

| Trigger | Mechanism |
|---|---|
| Scheduled | `IScheduler` → emits `iri.ingest.requested` per user per enabled source |
| Manual | API call → same event |
| Event/webhook | Provider push (Gmail watch, Graph subscription) → webhook endpoint → same event |
| Tracker status change | Domain event on posting status → registers a focused watch window, biasing correlation toward that posting |

All four converge on the same event, so no trigger has a privileged code path. De-duplication at the queue level satisfies REQ-314.

## 8. Correlation design

Multi-signal scoring rather than a single key, because no reliable join key exists across sources.

| Signal | Weight class | Notes |
|---|---|---|
| Requisition identifier in text | Strong | e.g. `R-50446` — near-decisive when present |
| Sender/participant email domain ↔ employer | Strong | |
| Employer name match (normalised) | Medium | Reuses the existing skills/entity normaliser |
| Role title similarity | Medium | Vector similarity against posting title |
| Temporal proximity to known application dates | Medium | |
| Calendar/meeting subject match | Medium | |
| Thread continuity (email `In-Reply-To`) | Strong | Propagates correlation across a thread |

Scores combine into a confidence value. Above the high threshold → auto-correlate. Between thresholds → correlate and flag for review. Below → present unlinked with candidate suggestions (REQ-161, REQ-163).

**Multiple concurrent applications to the same employer** (REQ-164) is the hard case. Employer-only matches never auto-correlate; the design requires at least one of {requisition id, role-title similarity above threshold, thread continuity} before assigning.

**Human corrections are sticky** (REQ-165): a correction writes a durable override keyed on the evidence's native identifier, consulted before scoring on any re-run.

## 9. Redaction and pseudonymisation

Per **DD-03**, deterministic pseudonymisation.

### 9.1 Mechanism

```
detect entities → resolve to stable identity → substitute token → analyse → rehydrate for display
```

- **Detection** identifies person names, email addresses, phone numbers, and organisation-affiliated identifiers of third parties. The candidate's own identity is also tokenised for consistency.
- **Resolution** maps a detected entity to a stable per-user identity record.
- **Substitution** replaces the entity with a stable token: `INTERVIEWER_A`, `RECRUITER_1`, `EMPLOYER_3`. The **same person receives the same token across every document for that user**, preserving the model's ability to reason that the same interviewer appeared in two rounds (the analytical value that pure masking destroys).
- **Vault** — the token↔identity mapping lives in the relational store, never leaves the trust boundary, and is never included in a model payload.
- **Rehydration** occurs only at render time for the owning user.

### 9.2 Fail-closed enforcement (REQ-485) — scoped by trust boundary (DD-15)

All model invocation is reachable **only** through the **redaction gateway**, which remains the single choke point for cost attribution (REQ-406), quota enforcement (REQ-407) and model-call logging (REQ-482). The gateway routes by destination:

| Destination | Redaction | Failure behaviour |
|---|---|---|
| **Self-hosted model on the user's own hardware** (local vLLM) | **None.** Content does not leave the machine. | n/a |
| **Any cloud-hosted model** (Bedrock, Azure OpenAI, external API) | **Mandatory** deterministic pseudonymisation (§9.1) | **Blocks.** A payload that has not passed redaction, or where detection reported low confidence on a span, is rejected and queued for human review. There is no bypass. |

**Residual risk, stated plainly and unchanged for the cloud path:** entity detection is imperfect; a name in unusual transcript phrasing may be missed. Mitigations are conservative detection (over-redaction preferred), an outbound scan of payloads for known vault values as a second gate, and complete model-call logging so a leak is discoverable after the fact. **This does not eliminate the risk** — it bounds and records it.

⚠ **Consequence for parity (§14.2).** Under normal operation `local` sees raw text while `aws` and `azure` see pseudonymised text, so the three environments are not receiving identical input. **The parity suite therefore forces redaction on in `local`** via a test-only setting, so all three compare on equivalent input. Normal local operation is unaffected. Without this the parity assertions in REQ-435 would be comparing different things and would be meaningless.

### 9.3 Tiering
Although DD-03 selects pseudonymisation uniformly, the gateway supports a per-environment strictness setting so that a future policy could redact more aggressively for cloud-hosted models without code change.

## 10. Analysis engine

### 10.1 Structure

Analysis is decomposed into **discrete analytical questions** rather than one monolithic prompt. Each produces structured output with mandatory evidence citations.

| Analyser | Produces | Requirements |
|---|---|---|
| `FeedbackExtractor` | Explicit interviewer feedback, especially responses to candidate feedback requests | REQ-182 |
| `QuestionCoverage` | Questions asked vs answered; redirect/rephrase/re-ask events with counts | REQ-183, REQ-184 |
| `TechnologyLedger` | Every technology named, by whom, and in what modality (claimed experience / recommendation / employer requirement) | REQ-185, REQ-230 |
| `StrengthFinder` | Evidenced positives, explicitly forbidden from inventing them | REQ-186 |
| `NonTechnicalFactors` | Compensation, level, geography, timing signals | REQ-189 |
| `CrossStageContext` | Concerns raised at earlier stages of the same application | REQ-188 |
| `CauseSynthesiser` | Primary cause + ranked contributing factors, consuming all of the above | REQ-180, REQ-187 |
| `GuidanceGenerator` | Specific forward-looking actions derived from findings | REQ-190 |

Decomposition matters for three reasons: each analyser is independently testable against the regression corpus (REQ-592); failures are partial and resumable (REQ-532); and each can use a model tier appropriate to its difficulty, controlling cost.

### 10.2 Long transcript handling

A 66-minute transcript is ~9,000 words; a three-hour one (REQ-512) exceeds comfortable context for structured extraction.

**Strategy:** segment the transcript on speaker-turn boundaries into overlapping windows, index windows in the vector store, and give each analyser retrieval over the full transcript plus a always-present structural summary (participants, agenda, phase boundaries). Analysers that require whole-conversation reasoning — `CauseSynthesiser` — consume the *outputs* of the extractive analysers rather than raw text, which keeps their input bounded regardless of transcript length.

**Uncertainty is explicit:** where an analyser's retrieval returns weak support, it is required to return "insufficient evidence" rather than infer (REQ-191).

### 10.3 Second opinion and reconciliation

- The second-opinion model receives **the same redacted evidence and the same analytical questions**, and **never** the primary analysis (REQ-211).
- Reconciliation is **deterministic, not model-driven**: findings are compared on claim identity and evidence citation. Agreement raises confidence; divergence is surfaced verbatim from both sides (REQ-213 to REQ-215).
- Reconciliation never picks a winner. Divergence is a finding, presented to the user.

### 10.4 Model routing

Routing is configuration, not code (REQ-437). Each environment declares a primary and a second-opinion model reference, resolved through `ILLMInference`.

⚠ **Azure cannot currently satisfy the second-opinion requirement.** The validated Azure OpenAI deployments are **`gpt-4o`** (chat) and **`text-embedding-3-small`** (embeddings, 1536-dim), API version `2024-10-21`. **`gpt-4o-mini` sits behind a disabled feature flag** — the only version catalogued in the region is deprecated for deployment. That leaves **one chat model**, so the "deployment A / deployment B" plan in Revision 1.0 does not hold on Azure.

✅ **Resolved (DD-13): `azure` adopts the DD-04 pattern.** Single-model analysis by default, explicitly labelled as degraded per REQ-217, with the second opinion available as a per-user opt-in — identical to `local`.

The opt-in path on Azure requires a **second Azure OpenAI deployment of a different model family**, declared in configuration. Two rules govern it:

1. If no second deployment is configured, the system **reports the second opinion as unavailable and labels the analysis single-model.** It does not queue, retry, or degrade silently.
2. It **never falls back cross-cloud.** An Azure deployment reaching out to Bedrock or an external API to obtain a second opinion would break single-cloud containment — which is likely the reason someone chose Azure — and would do so invisibly. If a second opinion matters enough, the answer is to deploy a second model, not to leave the boundary.

This makes `aws` the only environment where a second opinion is available by default, and that is an honest reflection of what each environment can actually do rather than a design aspiration.

| Environment | Primary | Second opinion |
|---|---|---|
| `local` | RTX 5090 vLLM | **None by default** (single-model, labelled). Cloud model only on explicit per-user opt-in — DD-04 |
| `aws` | Bedrock model A | Bedrock model B (different family) |
| `azure` | Azure OpenAI **`gpt-4o`** | **None by default** (single-model, labelled). Second Azure OpenAI deployment of a different family, on explicit opt-in only — never cross-cloud (DD-13) |

## 11. Claim discrepancy design

```
TechnologyLedger claims ──► normalise ──► match to skill_record ──► classify direction ──► queue for adjudication
```

**Normalisation** reuses the existing skills normaliser so `"Cosmos"`, `"Cosmos DB"` and `"Azure Cosmos DB"` resolve to one canonical skill.

**Direction classification** (REQ-232 to REQ-234):

| Condition | Direction |
|---|---|
| Claimed as experience; skill_record says not verified | **Over-claim** |
| skill_record says verified; absent from recent application materials | **Under-claim** |
| Claimed as experience with specific corroborating detail; skill_record says not verified | **Suspected record error** |

The third case exists because it is what actually occurred: the Employer A review found two record errors and one over-claim. A confident, detailed first-person claim is evidence *about the record*, not only about the candidate.

**Severity** distinguishes a stated past-experience claim from a forward-looking recommendation (REQ-235) — recommending Cosmos DB for a design is materially different from saying you deployed on it.

**Adjudication** (REQ-236 to REQ-238) is a human state machine: `pending → {confirmed_overclaim | confirmed_underclaim | record_corrected | dismissed}`. On `record_corrected`, the skill_record is updated **and** an impact query identifies every resume, cover letter and tracker note referencing the affected skill, surfaced for review.

## 12. Postmortem and aggregation

**Postmortem** is composed from persisted structured findings, not regenerated by a model. This makes rendering deterministic, versioned (REQ-275) and cheap. It is written to object storage in a portable format and referenced relationally.

**Aggregation** operates over structured findings across outcomes. Because findings are structured rather than prose, aggregation is a query rather than an LLM task — cheaper and more stable. Small-sample guarding (REQ-293) applies a minimum support threshold before a pattern is labelled anything other than provisional.

## 13. Multi-tenancy

- **Isolation is built on CloudLift's existing tenant-context system, not reinvented.** `cloudlift.bridge.tenant_context` provides a `ContextVar[UUID]` with `set_tenant()` / `explicit_tenant()`, propagating across async boundaries and **restorable from message headers by background consumers** — which is exactly what IRI's workers (§4.2) need. It has **no default and no "system" tenant**: a caller who forgets raises `MissingTenantContextError` rather than silently reading another tenant's data. **That is precisely the fail-closed isolation REQ-402 demands, already implemented and enforced per-adapter** (Postgres uses a per-tenant schema, Gremlin derives the graph name from the tenant). Adapters bind a tenant at construction *and* read the ContextVar; the resolver caches per `(tenant, contract)`.
- ✅ **One IRI user = one CloudLift tenant (DD-12).** Each user is assigned a tenant UUID v4 at account creation, and that UUID is the tenant context for every adapter call made on their behalf.

  **Why this over an organisation-tenant model:** REQ-402 requires that cross-user access be *impossible through any interface*. Mapping user→tenant makes **CloudLift's per-adapter isolation the enforcement mechanism** — a per-tenant Postgres schema, a per-tenant Gremlin graph name — with `MissingTenantContextError` as the fail-closed default. The alternative, a shared tenant with user-scoping layered above it, would place the single strongest requirement in the design on IRI's own query code, which is materially weaker. Nothing in the requirements references organisations or teams, and the evidence involved is intensely personal — including the recorded voices of third parties who never opted in (§11). The strongest available boundary is the correct one.

  **Consequences, stated plainly:**
  - N users means N Postgres schemas and N Gremlin graphs. At the scale these requirements imply — an individual or a small cohort — this is fine. **It is not a model that scales to thousands of users**, and crossing into that range means revisiting DD-12, not stretching it.
  - `Settings.multi_tenant_enabled` must remain `True` (its default).
  - Per-user data export and deletion (REQ-408) become **tenant** export and deletion, which makes the cascade cleaner than a filtered delete across shared tables.
  - Tenant is the *isolation* boundary; it is **not** credential storage. Per-user OAuth tokens live in `ISecretStore` (§5.2.1) under a per-tenant key namespace. **IRI must not conflate the two** — a point the CloudLift maintainer made explicitly.
- **Credentials** live in `ISecretStore` under a per-user key namespace; they are never read into logs or returned by any API (REQ-403).
- **Cost attribution** (REQ-406): every model call logs user, tokens, model and computed cost, written by the redaction gateway which all calls already traverse — the single choke point makes attribution unavoidable rather than best-effort.
- **Quotas** (REQ-407) are enforced at the same choke point.
- **Export and deletion** (REQ-408) walk the relational schema from `user_id`, then purge object storage by reference and reproject the graph.

## 14. Environment mapping

**Azure column is the CoE's live-validated mapping** (`local-to-azure-service-mapping`, maturity `validated`, 12/12 round trips in westus3 on 2026-09-04). Rows in **bold** are new contracts IRI must specify.

| Capability | Contract | local | aws | azure |
|---|---|---|---|---|
| Relational | `IRelationalDatabase` | SQLite / Postgres | RDS PostgreSQL | **Postgres Flexible Server** |
| Document | `IDocumentDatabase` | — | — | **Cosmos DB (Core/SQL)** |
| Graph | `IGraphDatabase` | ArangoDB | DynamoDB | **Cosmos DB (Gremlin)** |
| Vector | `IVectorSearch` | Qdrant | OpenSearch | **Azure AI Search (HNSW)** |
| Embeddings | `IEmbeddingService` | local model | Bedrock | **Azure OpenAI `text-embedding-3-small` (1536-dim)** |
| Cache | `ICacheStore` | Redis | ElastiCache | **Azure Managed Redis** |
| Queue | `IMessageQueue` | Artemis STOMP | SQS FIFO | **Service Bus** |
| LLM | `ILLMInference` | vLLM (RTX 5090) | Bedrock | **Azure OpenAI `gpt-4o`, API `2024-10-21`** |
| Lifecycle | `ILifecycleDatabase` | — | — | **Cosmos DB** |
| Data lake | `IDataLake` | — | — | **Synapse serverless SQL (read-only)** |
| Functions | `IFunctionExecution` | — | — | **Azure Functions** |
| Object storage | `IObjectStorage` | Filesystem | S3 | **Blob Storage** |
| **Secrets** | **`ISecretStore`** | Encrypted local store | Secrets Manager | Key Vault | *(new — §5.2.1)* |
| **Scheduler** | **`IScheduler`** | APScheduler | EventBridge Scheduler | Timer Functions | *(new)* |
| **Notification** | **`INotifier`** | Local relay | SES / SNS | Communication Services | *(new)* |

### 14.1 Azure constraints that change IRI's design

From `cloudlift/docs/azure_consumer_guide.md` §4. These are not deployment trivia — four of them alter component behaviour:

| Constraint | Consequence for IRI |
|---|---|
| **Cosmos Gremlin is NOT read-your-writes** | §6.3 graph projection cannot be read back immediately after write. Projection must be **asynchronous and eventually consistent**, and no read path may depend on a just-written vertex. Reinforces DD-01: the relational store is authoritative and the graph is a rebuildable projection. |
| **Azure AI Search is near-real-time; its index is data-plane only (Terraform cannot create it)** | §10.2 retrieval cannot assume a transcript is queryable the instant it is indexed. The analysis stage must **wait on an index-visibility signal** rather than proceeding on write-acknowledgement. Index creation is a provisioning step outside IaC. |
| **Service Bus does not auto-create queues, and a missing queue surfaces as an *auth* error** | Pipeline queues (§7) must be explicitly provisioned. A misleading "auth failure" on a missing queue would otherwise send debugging in entirely the wrong direction. |
| **`IEmbeddingService.embed` is synchronous; `dimension` is a property, not a method** | Embedding calls block a worker thread; the analysis worker must size concurrency accordingly rather than assuming async I/O. |
| Gremlin is a **separate Cosmos account with its own key** (the API is fixed at account creation) | Two Cosmos accounts and two credential sets to manage via `ISecretStore`. |
| `IDataLake` (Synapse serverless) is **read-only** | Not an IRI write path. |
| Managed Redis TLS is **port 10000**, not 6380 | Configuration only. |

### 14.2 ⚠ Parity testing — a requirement that cannot currently be met on Azure

REQ-435 and REQ-591 require a parity suite proving equivalent behaviour across all three environments. **The CloudLift Azure parity suite (AZ-061) is explicitly NOT built**, along with the smoke suite (AZ-062), cost actuals (AZ-070), discovery/import (AZ-080), snapshot/restore (AZ-081) and hibernation/wake (AZ-082).

What *does* exist is `scripts/azure_az091_run.sh` — a live round-trip check of all 12 contracts (12 passed / 0 failed / 0 skipped, westus3). That proves **the adapters work**; it does not prove **IRI behaves equivalently** across environments.

IRI's parity suite is therefore **IRI's own deliverable**, not something inherited. See **OI-10**.

**Parity assertions target *structural* equivalence** — same primary cause identified, same discrepancies found, same evidence cited — not token-identical prose, since models differ legitimately by environment.

### 14.3 Azure target maturity — stated honestly
The CloudLift as-built audit grades the Azure target **A−**, and names three reasons it is not an A:
1. `IDataLake` uses SQL authentication rather than the service-principal identity every other adapter uses (pymssql cannot do AAD SP auth). A documented divergence — and irrelevant to IRI, which does not use `IDataLake`.
2. Seven conformance gaps tracked as `xfail(strict=True)`, mostly pre-existing AWS/local gaps, plus `CosmosGremlinAdapter` missing v1.1 extension methods. **This one touches IRI** — verify the graph operations §6.3 needs are among the implemented members.
3. **Private endpoints are off** (a cost decision) and the compute tier is minimal. **Production posture is not yet proven.**

ℹ The Azure dev stack is **live now** (21 resources, ~$150/month) and was deliberately left up for this work. Teardown (AZ-092) is intentionally open — **do not run `scripts/azure_teardown.sh` without asking Mike.** Validate against it while it exists; `scripts/azure_deploy.sh dev` rebuilds it.

## 15. API design

New Flask Blueprint at `/api/iri/*`, following existing conventions (`user-id` header auth, consistent with the current app).

| Method | Path | Purpose |
|---|---|---|
| GET/POST/DELETE | `/connectors`, `/connectors/{source}` | List, connect, revoke |
| GET | `/connectors/{source}/authorize` | Begin OAuth |
| POST | `/connectors/{source}/callback` | Complete OAuth |
| POST | `/scan` | Manual scan trigger |
| POST | `/evidence/upload` | Manual upload |
| GET | `/evidence`, `/evidence/{id}` | List, retrieve (rehydrated) |
| GET | `/outcomes`, `/outcomes/{id}` | List, detail with timeline |
| POST | `/outcomes/{id}/confirm` | Human confirmation |
| PUT | `/outcomes/{id}/correlation` | Correct correlation |
| POST | `/outcomes/{id}/analyze` | Request/re-request analysis |
| GET | `/outcomes/{id}/postmortem` | Retrieve artifact |
| GET | `/discrepancies` | Adjudication queue |
| POST | `/discrepancies/{id}/adjudicate` | Decide |
| GET | `/discrepancies/{id}/impact` | Affected downstream artifacts |
| GET | `/skills` | Verified-skills record |
| GET | `/patterns` | Aggregate findings |
| GET | `/review-queue` | Items awaiting review |
| GET/PUT | `/retention` | Policy view/update |
| POST | `/purge` | Scoped purge |
| GET | `/export` | Full per-user export |

Long-running operations return a job reference consumable by the existing job-status endpoints (REQ-315).

## 16. Observability

- Structured events at every stage boundary, correlated by a pipeline correlation id spanning ingest → adjudication (REQ-570).
- **Telemetry never carries evidence content or PII** (REQ-573) — enforced by emitting identifiers and counts only.
- Quality signals (REQ-572): confidence distributions, human-correction rate per stage, model divergence rate in reconciliation. Rising correction rate is the leading indicator of prompt or model regression.

## 17. Failure modes

| Failure | Behaviour |
|---|---|
| Source auth expired | Connector marked unhealthy, user notified (REQ-372), other sources continue (REQ-104) |
| Source rate-limited | Backoff with cursor preserved; no data loss (REQ-106) |
| Transcript exceeds context | Segmentation path (§10.2); never truncate silently |
| Redaction low-confidence | **Block** model call, queue for human review (REQ-485) |
| Primary model unavailable | Analysis queued, retried; partial results preserved (REQ-532) |
| Second-opinion model unavailable | Degrade to single-model, **explicitly labelled** (REQ-217) |
| Correlation ambiguous | Present unlinked with suggestions; never guess (REQ-161) |
| Graph projection drift | Rebuild from relational source of truth |
| Purge partially fails | Purge is transactional per outcome; failure leaves record marked and retries (REQ-465) |

## 18. Security

- Encryption at rest via adapter-native mechanisms; in transit by default (REQ-480).
- `access_log` written on every read of evidence content, including internal reads by workers (REQ-481).
- `model_call_log` written by the redaction gateway, recording content reference, model, environment, token counts and cost (REQ-482).
- Secrets only via `ISecretStore` (REQ-492) — no environment-variable credentials for per-user tokens.
- Connector configuration prefers provider settings that contractually exclude training use (REQ-490); where a provider cannot guarantee this, it is surfaced in the connector UI rather than silently accepted.

## 19. Traceability to the validation scenario

The §15 Employer A scenario in the requirements maps onto this design as follows:

| Validation step | Design element |
|---|---|
| V-1 ingest both transcripts + mail | Krisp and Gmail connectors, ingestion, dedupe |
| V-2 classify ATS rejection | `classification.py`, automated-vs-human distinction |
| V-3 correlate to one posting | Multi-signal correlation, requisition id `R-50446` as strong signal |
| V-4 extract closing feedback as primary cause | `FeedbackExtractor` → `CauseSynthesiser` |
| V-5 unanswered stack questions | `QuestionCoverage` |
| V-6 quantify redirection | `QuestionCoverage` redirect counting |
| V-7 three discrepancies | `TechnologyLedger` → `claims.py` |
| V-8 two record errors, one over-claim, impact list | Direction classification incl. suspected-record-error; adjudication impact query |
| V-9 comp collision | `NonTechnicalFactors` over the recruiter-screen transcript |
| V-10 earlier-stage concern | `CrossStageContext` |
| V-11 what went well | `StrengthFinder` |
| V-12 mismatch vs preparation failure | `CauseSynthesiser` explicit judgement |
| V-13 convergent second opinion | §10.3 |
| V-14 durable postmortem | §12 |

## 20. Design decisions

| ID | Decision | Alternatives rejected | Consequence |
|---|---|---|---|
| **DD-01** | Hybrid relational + graph, relational authoritative, graph a rebuildable projection | Graph-only (deletion cascade and audit become hard); relational-only (loses provenance traversal) | Two stores to keep consistent; mitigated by treating graph as derived |
| **DD-02** | Extend existing backend + workers | New dedicated service (more isolation, more surface); backend-only (analysis competes with interactive requests) | Reuses queue, jobs and auth; IRI load shares the workers service |
| **DD-03** | Deterministic pseudonymisation with a local vault | Simple masking (loses cross-document identity reasoning); tiered (deferred, but supported by config) | Vault becomes sensitive state requiring its own protection |
| **DD-04** | ✅ **RESOLVED 2026-09-03 (Mike): option (a).** `local` defaults to **single-model analysis with explicit degradation labelling** (REQ-217). A cloud second opinion is available as an **explicit per-user opt-in**. | Cloud second opinion always-on in local (breaks REQ-438/REQ-552); amending the requirements; RTX 5090 model-swap | REQ-438 and REQ-552 are **preserved by default**. The UI MUST state clearly when an analysis is single-model. Opt-in cost is attributed per user (REQ-406) and bounded by quota (REQ-407). |
| **DD-05** | Analysis decomposed into discrete analysers, not one prompt | Monolithic analysis prompt (simpler, cheaper, far less testable) | More orchestration; enables per-analyser regression testing and partial resume |
| **DD-06** | Reconciliation is deterministic, not model-driven | LLM reconciler (fluent, but adds a third opinion masquerading as arbitration) | Divergence surfaces rather than resolves |
| **DD-07** | Postmortem composed from structured findings, not model-generated prose | Model-generated document (more fluent, non-deterministic, expensive to version) | Rendering is deterministic and cheap; prose quality depends on finding quality |
| **DD-09** | **IRI consumes CloudLift's real adapters via `cloudlift.bridge.*`, and does NOT extend the resume-optimizer's app-level shims.** | Extending `backend/cloudlift_*_adapter.py` per provider (the status quo) | Gets all 12 contracts across three validated environments for free, plus tenant isolation. Requires the resume-optimizer to take a dependency on the CloudLift package. The comment that motivated the shims (module identity split) is **obsolete** — verified fixed. |
| **DD-10** | **Graph projection is asynchronous and eventually consistent.** | Synchronous write-then-read projection | Forced by Cosmos Gremlin not being read-your-writes (§14.1). **Measured 2026-09-04: writes 2164 ms, first visible 562 ms after write.** Reinforces DD-01 — relational authoritative, graph rebuildable. No read path may depend on a just-written vertex. |
| **DD-11** | **`CLOUDLIFT_ENV` is the single environment variable**, passed explicitly to `AdapterResolver(env=...)` rather than relying on CloudLift's implicit settings lookup | Renaming to `CLOUDLIFT_ENVIRONMENT` across `./ro` and the shims; supporting both names | IRI's environment selection cannot drift from `./ro`'s. Zero change to either codebase. Resolves OI-9. |
| **DD-12** | **One IRI user = one CloudLift tenant (UUID v4)** | Organisation-as-tenant with user-scoping layered above | REQ-402 isolation is enforced by CloudLift per-adapter (per-tenant schema/graph) with fail-closed default, rather than by IRI's own query code. Costs one Postgres schema and one Gremlin graph per user — **does not scale to thousands of users**; revisit rather than stretch. Resolves OI-11. |
| **DD-13** | **`azure` uses single-model analysis by default**, second opinion opt-in via a second Azure OpenAI deployment, **never cross-cloud** | Deploying a second family by default (cost); permitting cross-cloud fallback (breaks containment silently) | Only `aws` offers a second opinion by default. Honest about each environment's real capability. Resolves OI-12. |
| **DD-14** | **Retention: raw evidence 24 months, derived analysis indefinite** | 90 days (strongest privacy, loses re-analysis); 12 months; no auto-expiry | Maximum re-analysis flexibility and pattern depth across a multi-year search. Accepts the largest third-party data footprint of the options considered — mitigated by encryption, access logging and on-demand purge. Resolves OI-3. |
| **DD-15** | **Self-hosted models on the user's own hardware are INSIDE the trust boundary and receive unredacted content. Cloud model calls are redacted and fail closed.** | Redact for every model including local (Rev 1.0–1.2 position); human review of every low-confidence span; human pre-flight per source | Content sent to the local GPU never leaves the machine, so redaction protects nothing there while degrading analysis quality. **Amends P-3.** Creates two gateway paths — the fail-closed guarantee now applies to the cloud path only. **Forces the parity suite to force-enable redaction in `local`** (§9.2). Resolves OI-4. |
| **DD-16** | **OAuth apps stay unverified, capped at ~100 users** | Full Google restricted-scope assessment + Microsoft publisher verification; Google-only verification; single-user | Avoids weeks of review and possible third-party audit cost. Users see an unverified-app warning at consent. **Hard ceiling of ~100 users** — this, not DD-12's schema-per-tenant cost, is the first scaling wall IRI will hit. Resolves OI-5. |
| **DD-17** | **On adjudication, re-run only the claim-discrepancy findings**, not the full analysis | Auto re-run everything affected (cost on every adjudication); flag stale and do nothing | Targeted and cheap — the discrepancy section is precisely what a corrected skills record invalidates. Root-cause findings are left intact unless explicitly re-requested. **Analyses whose root-cause reasoning cited the changed claim are flagged stale** so the user can choose. Resolves OI-6. |
| **DD-18** | **Verified-skills migration is LLM-extracted but human-adjudicated; nothing imports as `verified`** | Bulk auto-import of the existing memory corpus | The corpus is known to contain errors — on 2026-09-03 two of three flagged discrepancies turned out to be *the record being wrong*, not the candidate over-claiming. Auto-import would launder those errors into an authoritative store. Resolves OI-2. |
| **DD-19** | **Backfill by re-ingesting from original sources and diffing against the human postmortem — never by importing the postmortem prose as findings** | Importing existing postmortems as structured findings | The diff *is* the validation scenario (§15) and seeds the regression corpus. Importing prose would make the system agree with itself and prove nothing. Resolves OI-7. |
| **DD-20** | **Regression corpus is gated on failure-mode coverage, not on a count of labelled outcomes** | A fixed threshold (e.g. "20 labelled outcomes before release") | Three existing cases already span the three evidence classes. A count is a proxy; coverage is the thing. Every human adjudication is a labelling event, so the corpus grows itself. Resolves OI-8. |
| **DD-21** | **No read path in any environment may assume a just-written vector segment is searchable, and no purge check may assert deletion immediately.** | Treating the vector index as strongly consistent, as Qdrant/Arango behave locally | **Measured 2026-09-04:** Azure AI Search visibility lag 529–986 ms on write, and deletes are eventually consistent too. This generalises DD-10 beyond the graph. §10.2 retrieval must tolerate a not-yet-indexed segment, and the S6 purge negative test (REQ-593) must poll to a deadline rather than assert once. |
| **DD-22** | **IRI declares its edge-collection set at design time; tenant provisioning creates one Cosmos container per edge collection per tenant.** | Creating edge collections lazily on first write, as local ArangoDB allows | **Measured 2026-09-04:** `upsert_edge` maps `edge_collection` to a Cosmos container `t_<tenant>_<collection>`; a missing container returns 404, never auto-creates. Provisioning therefore belongs to tenant creation (§5.2 / plan S0.2), not to the graph code path. Also a per-tenant resource multiplier against DD-16's ~100-user ceiling. |
| **DD-23** | **Metadata may be CARRIED in the vector index, but any metadata IRI needs to FILTER on is joined from the relational store.** | Carrying metadata in the vector index and filtering on it there | **Amended 2026-09-05** after CloudLift fixed the divergence this decision was written around. Originally: the AI Search index exposed only `id`/`content`/`embedding` and *rejected* unknown properties, so metadata could not travel with the vector at all. CloudLift has since added a `metadata_json` field; the adapter serialises anything outside the declared schema into it and restores it on read, verified live with nested dicts and ints. Parity returned to PARITY. **What survives the amendment:** `metadata_json` is deliberately **not filterable** — filtering on a serialised blob would be a portability guarantee Azure cannot keep. So carrying metadata is now free and portable; *querying* it is not. IRI keeps the relational store authoritative for anything it filters, ranks or joins on (DD-01), and may now attach descriptive metadata to vectors for provenance without a second lookup. |
| **DD-24** | **IRI consumes CloudLift's AZ-061 parity suite for adapter behaviour, and owns parity only at the finding level.** | IRI building and maintaining its own three-way adapter parity suite | AZ-061 exists and is validated (10/12 in parity, 0 divergences). Duplicating it would re-test CloudLift's layer and drift from it. **IRI's remaining parity obligation is what AZ-061 deliberately normalises away** — it discards identifiers, timestamps, metadata casing and ANN scores by design — plus the layer above adapters entirely: same primary cause, same discrepancy set and directions, same evidence cited by source location, same classification and correlation. Note the ANN-score normalisation in particular: if IRI ever ranks or thresholds on retrieval score, that is IRI's to verify, not AZ-061's. |
| **DD-25** | **IRI pins its LLM endpoint: analysis calls go through CloudLift's `ILLMInference` adapter, never through the FTAL harness.** | Reusing the harness for analysis, as the rest of the app does | The harness routes to `claude-haiku-4-5-20251001` on local-inference failure **unconditionally** — verified in `agent_task_queue_execution.py` ~585, with no flag, config check or opt-in. Under DD-15 that silently ships unredacted transcripts off-host, and the trigger (local inference unavailable) occurred three times on 2026-09-04. **The pin costs nothing to implement:** CloudLift's `LocalVLLMAdapter` already posts directly to `localhost:8021` and raises `AdapterError` on failure with no fallback path, so DD-09 delivers the required behaviour by construction. What it costs is *enforcement* — `tests/test_iri_llm_endpoint_pinning.py` fails if a harness call is reintroduced into IRI, and separately if CloudLift ever adds a fallback to `LocalVLLMAdapter`. The harness remains in use for **code generation**, where the trust boundary does not apply. Confirmed with the harness maintainer; nothing breaks on their side. |
| **DD-26** | **One graph container per tenant on Azure; edge type is a property, not a container.** | Six containers per tenant, one per edge collection, mirroring local ArangoDB | DD-22 established that Cosmos Gremlin containers must be pre-provisioned. Six per tenant against DD-16's ~100-user ceiling is **600 containers**, each carrying provisioned throughput — a cost and provisioning burden out of proportion to the benefit. Collapsing to one container per tenant, discriminated by an edge-type property, drops that to 100. **Accepted costs:** some Gremlin traversal efficiency, and a deliberate shape divergence from local ArangoDB — the parity suite must compare *behaviour*, not container topology (which AZ-061 already normalises). Revisit if traversal latency becomes a measured problem rather than a theoretical one. |
| **DD-27** | **CloudLift's Terraform creates the Azure graph container; IRI's provisioner only verifies it and refuses to activate a tenant without it.** | IRI creating containers via `provider_specific`, or waiting on `register_collection` | `register_collection` is on the `IGraphDatabase` contract but absent from `CosmosGremlinAdapter` (OI-13), so provisioning through the bridge is not currently possible. Container creation is **infrastructure**, and CloudLift already owns the Azure stack definition — putting Cosmos-specific creation code in IRI would violate P-1 and hand IRI ownership of Cosmos API drift. **DD-26 makes this a small ask:** one container per tenant rather than six. IRI's provisioner verifies existence and leaves the tenant in `provisioning` status if absent (S0.2 §4), so a missing container is a visible, repairable state rather than a runtime 404 during analysis. |
| **DD-08** | `IEvidenceSource` is not a CloudLift adapter | Modelling sources as adapters (implies per-cloud implementations that should not exist) | Clear separation between cloud-varying and user-varying integrations |

### DD-04 resolution — DECIDED 2026-09-03

**Option (a) selected by Mike.** Local defaults to single-model analysis, explicitly labelled as degraded per REQ-217; the cloud second opinion is a per-user opt-in.

Design consequences:
- REQ-438 and REQ-552 hold by default — `local` remains fully functional with no cloud dependency or cost.
- The reconciliation stage (§10.3) is **skipped** in default local operation; single-model findings carry the lower confidence grade defined in REQ-214.
- The UI and every generated postmortem MUST carry a visible single-model indicator (REQ-334 applies: machine-generated content must be distinguishable, and analysis provenance is part of that).
- Opt-in second opinion inherits per-user cost attribution (REQ-406) and quota enforcement (REQ-407) through the redaction gateway choke point (§13).
- Model routing (§10.4) for local becomes: primary = vLLM; second opinion = **unset by default**, cloud reference when opted in.

## 21. Open items — ALL RESOLVED as of Revision 1.3 (2026-09-04)

**All thirteen open items are closed.** Nine were resolved by decision (DD-11 to DD-20), two by verification against the CloudLift source (OI-1, OI-13), one by scoping (OI-10) and one by measurement (OI-2). The design carries no unresolved questions into implementation planning.

⚠ **Two decisions that should be revisited on a trigger rather than forgotten:**
- **DD-16 — the ~100-user OAuth ceiling is IRI's first scaling wall.** It binds sooner than DD-12's per-tenant schema cost. When a second real cohort appears, revisit app registration before revisiting tenancy.
- **DD-15 — the local trust boundary holds only while the local model runs on hardware the user owns.** If local inference ever moves to rented or shared GPU, the boundary moves with it and DD-15 must be re-decided, not inherited.

| ID | Item |
|---|---|
| ~~**OI-1**~~ | ✅ **RESOLVED 2026-09-04.** Azure is complete: 12 adapters implemented in `core/bridge/azure/`, registered via `defaults.py`, `azure` is first-class in `settings.py`, and the CoE records the mapping as `validated` with 12/12 live round trips in westus3. Platform adapters are consumed directly via `cloudlift.bridge.*` (DD-09); no per-shim Azure implementations are required. Revision 1.0's finding was correct on 2026-09-03 — the maintainer confirms that on that date the Azure target registered **nothing** — and was overtaken by work completed 2026-09-04. |
| ~~**OI-9**~~ | ✅ **RESOLVED 2026-09-04 — DD-11.** `CLOUDLIFT_ENV` is authoritative; IRI passes it explicitly to `AdapterResolver(env=...)`, which the resolver supports and documents. No codebase change needed. |
| ~~**OI-10**~~ | ✅ **RESOLVED — scope defined.** IRI's parity suite runs the OI-8 regression corpus in `local`, `aws` and `azure` and asserts **structural** equivalence: same primary cause identified, same discrepancy set with the same directions, same evidence cited **by source location** (not verbatim quote — models phrase differently), same outcome classification and correlation. It does **not** assert token-identical prose. **It forces redaction on in `local`** (DD-15/§9.2) so all three environments compare on equivalent input. It runs against the live Azure dev stack while that exists, and against recorded fixtures otherwise (REQ-590). It is independent of CloudLift's unbuilt AZ-061 — that would prove the *adapters* behave alike; this proves *IRI* does. |
| ~~**OI-11**~~ | ✅ **RESOLVED 2026-09-04 — DD-12.** One IRI user = one CloudLift tenant. Isolation is enforced by CloudLift per-adapter with a fail-closed default. Scale ceiling acknowledged. |
| ~~**OI-12**~~ | ✅ **RESOLVED 2026-09-04 — DD-13.** Azure adopts the DD-04 single-model default with opt-in second opinion via a second Azure OpenAI deployment; never cross-cloud. |
| ~~**OI-13**~~ | ✅ **RESOLVED — verified in source 2026-09-04, and it lands favourably.** `CosmosGremlinAdapter` implements `upsert_edge`, `list_edges`, `delete_edge`, `traverse`, `supports_graph`, `supports_weighted_edges`, `max_traversal_depth`, `supports_aql`, `supports_transactions`, `provider_specific`, `close`. **All four operations §6.3 needs — `upsert_edge`, `list_edges`, `delete_edge`, `traverse` — are present.** Absent from the contract's 17 members: `execute_aql`, `register_collection`, `named_graph_operation` (all ArangoDB-specific, and P-1 forbids IRI depending on provider-specific query languages anyway), `supports_feature`, and `begin/commit/abort_transaction`. **The transaction gap does not affect IRI** — DD-01 makes the relational store authoritative and DD-10 makes the graph an asynchronous, eventually-consistent projection, so graph transactions are not required. ~~The one real loss is `supports_feature`.~~ **Withdrawn 2026-09-04:** the live `CosmosGremlinAdapter` *does* expose `supports_feature`; the source read missed it. There is no remaining capability-probing gap. All four required operations were additionally exercised against the live service, not merely found in source. |
| ~~**OI-2**~~ | ✅ **RESOLVED — DD-18.** **Volume measured: 69 memory files, ~52,000 words.** Claims are concentrated in 10 `reference_*` files (~6,600 words, of which `reference_verified_tech_stack.md` is 2,732) but also scattered across ~50 `project_*` files that each record what was claimed and deliberately not claimed on one resume. **Approach:** LLM-assisted extraction into structured claims, seeded from `reference_verified_tech_stack.md` as the highest-density source, then **every claim human-adjudicated before it becomes authoritative**. **Provenance recovery is partial** — memory carries dates and engagement references inconsistently. Where provenance cannot be recovered the claim enters as `unverified` pending adjudication, **never as `verified`**. Migration is a one-off bootstrap, not a recurring sync; after it, the structured record is the system of record and the markdown is archive. |
| ~~**OI-3**~~ | ✅ **RESOLVED — DD-14.** Raw evidence **24 months**, derived analysis **indefinite**. Both are per-user configurable (REQ-486/487 already require configurability); these are the defaults. |
| ~~**OI-4**~~ | ✅ **RESOLVED — DD-15.** No human pre-flight. Self-hosted models are inside the trust boundary and receive unredacted content; cloud calls are redacted and fail closed. Residual cloud-path risk is bounded by conservative detection, the outbound vault-value scan and complete model-call logging — **not eliminated**, and §9.2 says so. |
| ~~**OI-5**~~ | ✅ **RESOLVED — DD-16.** Unverified apps, ~100-user ceiling, consent-screen warning accepted. **This is IRI's first scaling wall** and should be the trigger to revisit, ahead of DD-12's per-tenant schema cost. |
| **OI-6** | Whether analyses auto-invalidate and re-run when the verified-skills record changes (a corrected record can falsify a prior discrepancy finding). |
| **OI-7** | Backfill approach for outcomes already analysed manually, including Employer A. |
| ~~**OI-8**~~ | ✅ **RESOLVED — DD-20.** **Gate on coverage, not count.** Required before release: (a) at least one labelled outcome per evidence class — full-transcript post-interview, document-only resume-stage, email-only — which the three backfill cases already satisfy; (b) a unit fixture per analyser (§10.1), including negative fixtures for `StrengthFinder` (must not invent positives) and `CauseSynthesiser` (must return "insufficient evidence" rather than infer); (c) at least one case exercising each discrepancy direction — over-claim, under-claim, **and suspected record error**, all three of which the Employer A case supplies. The corpus then grows automatically, since every human adjudication is a labelling event. |
