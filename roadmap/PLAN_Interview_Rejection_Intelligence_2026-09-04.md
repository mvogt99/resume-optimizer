# Implementation Plan — Interview & Rejection Intelligence (IRI)
## Resume Optimizer — Phase 18

> **Version:** 1.6 · **Date:** 2026-09-05 · **Status:** In progress — S0.5 COMPLETE (both adapters green, 75 tests); gateway, Azure adapter and provisioner remain
> **Implements:** `DESIGN_Interview_Rejection_Intelligence_2026-09-03.md` (Rev 1.6, 24 decisions, 0 open items)
> **Spike results:** `IRI_S0_Azure_Spike_Findings_2026-09-04.md`
> **Satisfies:** `REQUIREMENTS_Interview_Rejection_Intelligence_2026-09-03.md` (171 requirements)
> **CoE-cited:** `local-to-azure-service-mapping`, `cloudlift-deployment-plane`, `bridge-adapter-interface-pattern`, `multi-tenant-saas`

---

## 1. Planning assumptions

Stated rather than asked, because the design carries no open questions. **Each names what changes if it is wrong.**

| # | Assumption | If wrong |
|---|---|---|
| A-1 | **Code generation is delegated to the RTX 5090 via the FTAL harness** per the machine-wide rule; the human role is specification, review and adjudication. | If code is hand-written instead, per-stage effort rises but sequencing is unchanged. |
| A-2 | **One developer**, working in sequence, not a team in parallel. Stages are therefore ordered by dependency and risk, not packed for concurrency. | With a second developer, S3 and S4 can run in parallel after S2; nothing else forks cleanly. |
| A-3 | **No fixed delivery date.** Stages are sized relative to each other, not in calendar time. | A date forces cutting scope — §8 names what to cut, in order. |
| A-4 | The **Azure dev stack will be torn down** before this work completes (AZ-092 is open and Mike has asked for teardown). | See §3 — this is the sharpest scheduling constraint in the plan. |
| A-5 | Existing `batch_jobs`, tracker and auth remain in place and are extended, not replaced (design C-02). | A tracker rewrite would front-load S5. |

---

## 2. Strategy

**Two principles govern the ordering.**

**Risk first, breadth second.** The four genuinely uncertain things are redaction correctness, analysis quality, cross-environment parity, and skills-record migration fidelity. Three of the four are proven in **S1**, a deliberately narrow end-to-end slice, before any breadth is built.

**One vertical slice before any horizontal layer.** S1 carries a single source through a single analysis to a single postmortem in one environment. It is not a prototype to be discarded — it is the production path, narrowed. Everything after it widens that path.

```
S0 ── S1 ────────── S2 ── S3 ── S4 ── S5 ── S6 ── S7
foundation  slice   skills  ingest  detect  analyse  claims  scale
            ▲                                  ▲
            proves redaction,                  proves parity
            analysis, storage                  across 3 envs
```

---

## 3. Azure: the window closed, and the spike caught it

**Resolved.** The S0.4 spike ran against the live dev stack on 2026-09-04, hours before teardown. **The stack is now destroyed** — 42/42 complete, zero resources, zero spend. Everything the design needed from live Azure was measured in time; nothing is blocked.

**To verify anything against Azure from here** (~25 min, ~$160/mo while up):

```bash
scripts/azure_deploy.sh dev
.venv/bin/python scripts/azure_create_search_index.py   # Terraform cannot create the index
scripts/azure_az091_run.sh                              # 12 live round trips
scripts/azure_smoke_run.sh --env azure
scripts/azure_parity_run.sh --environments local,azure
```

**Three constraints this places on IRI's own Azure work:**

1. **Export before destroying.** Azure PITR is a property of the *live* resource and does not survive a destroy — unlike an AWS RDS final snapshot, which outlives its instance. A teardown leaves infrastructure recoverable and **data not**. If an Azure IRI stack ever holds real evidence, retention (S6) and teardown must not be assumed independent.
2. **Destroy-and-restore is the cost lever, not hibernation.** Hibernation saves only $16 of $160; AI Search alone is $75 and cannot be stopped, only deleted. So S7's Azure parity run should be a **deliberate, time-boxed episode** — deploy, verify, destroy — not a long-lived environment.
3. **A short-lived Azure stack cannot be cost-reconciled.** Cost Management ingests 8–24h behind creation, and a ~19h stack returned zero rows. Plan against the $159.84/mo projection; do not expect actuals to confirm it.

---

## 4. Stages

### S0 — Foundation and Azure verification
**Purpose:** make the CloudLift dependency real and prove Azure before it disappears.

| Item | Detail | Satisfies |
|---|---|---|
| ✅ S0.0 | **Unplanned:** project `.venv` was already broken (stale interpreter path from the repo move). Rebuilt on Python 3.14.7; jobspy/numpy resolution pinned. | prerequisite |
| ✅ S0.1 | CloudLift installed editable; `AdapterResolver(env=...)` wired. Module identity verified unified. | DD-09, DD-11, REQ-432 |
| S0.2 | Tenant provisioning — one user, one tenant UUID v4; bind `explicit_tenant()` at request and worker boundaries. **Plus: create one Cosmos container per declared edge collection per tenant (DD-22).** | DD-12, DD-22, REQ-400/402 |
| ✅ S0.3 | **12/12 resolve in `local`**; tenant context verified fail-closed | REQ-430 |
| ✅ S0.4 | **Azure spike complete against the live stack — 12/12 resolve in `azure`.** Produced DD-21/22/23. | REQ-430/435 |
| S0.5 | `ISecretStore` contract + local, aws, azure implementations | §5.2.1, REQ-403/492 |
| S0.6 | Redaction gateway skeleton: the single model-access choke point, with cost attribution, quota and model-call logging — routing by destination per DD-15 | DD-15, REQ-406/407/482 |

**Done when:** IRI code resolves a CloudLift adapter under an explicit tenant in `local`; the Azure spike note exists; no model call is reachable except through the gateway.

**Risk:** the CloudLift dependency may drag transitive requirements into the resume-optimizer's environment. Verify early; if it conflicts, the fallback is a thin process boundary rather than reverting to per-provider shims.

---

### S1 — Walking skeleton *(the highest-value stage in the plan)*
**Purpose:** prove the three riskiest mechanisms end to end, narrowly.

**Scope deliberately fixed at:** Krisp only · one outcome · `local` only · one analyser · no second opinion · no UI beyond a result view.

| Item | Detail |
|---|---|
| S1.1 | `IEvidenceSource` + Krisp connector — OAuth, cursor, fetch |
| S1.2 | Normalisation and object-storage persistence of one transcript |
| S1.3 | **Deterministic pseudonymisation with the identity vault** (DD-03) — the single hardest correctness problem in the system |
| S1.4 | Segmentation + vector indexing of a long transcript (§10.2) |
| S1.5 | **`FeedbackExtractor` only** — chosen because the Employer A case has a known-correct answer |
| S1.6 | Minimal postmortem render |

**Done when:** the 8/18 Employer A transcript is ingested, pseudonymised, indexed, and `FeedbackExtractor` independently surfaces the interviewer's closing feedback — **[paraphrased]* they wanted a managed, off-the-shelf reasoning model rather than a self-hosted open-weight one* — as the primary finding, with a citation to its transcript location.

**Why this test:** the answer is already known and independently documented. If the system cannot find a quote a human found in the same transcript, nothing downstream is trustworthy.

---

### S2 — Verified-skills record
**Purpose:** the prerequisite for all claim work. Nothing in S5 can start without it.

| Item | Detail | Satisfies |
|---|---|---|
| S2.1 | Relational schema for `skill_record`, `claim`, `discrepancy`, `adjudication` | DD-01, REQ-462 |
| S2.2 | Graph projection — **asynchronous, eventually consistent** | DD-10, REQ-461 |
| S2.3 | LLM-assisted extraction from the 69-file / ~52k-word memory corpus, seeded from `reference_verified_tech_stack.md` | DD-18, OI-2 |
| S2.4 | **Adjudication UI** — every migrated claim reviewed; nothing imports as `verified` | DD-18, REQ-236 |
| S2.5 | Impact query: given a changed claim, list affected resumes, letters, tracker notes | REQ-237 |

**Done when:** the corpus is migrated with every claim adjudicated, and the record correctly holds **Cosmos DB = verified, KQL = verified, LangChain = refuted** — the three claims settled by hand on 2026-09-03.

**Risk — the one to watch.** Extraction fidelity is unmeasurable in advance. Mitigation: adjudicate in priority order (technologies appearing on recent resumes first) so that a partial migration is still useful, and treat unmigrated claims as `unverified` rather than absent.

---

### S3 — Ingestion breadth
Gmail, MS365/Teams, manual upload · incremental cursors · dedupe · `IScheduler` + all four triggers · connector health and failure notification.
**Done when:** all four sources ingest incrementally, a revoked token surfaces as an actionable notification, and re-running a scan produces zero duplicates.

---

### S4 — Detection, correlation, tracker
Outcome classification incl. automated-vs-human rejection · stalling detection · multi-signal correlation with sticky human overrides · tracker updates that append and never overwrite · review queue.
**Done when:** the Employer B rejection is classified as an automated ATS rejection, correlated to the right posting, and the tracker updates only after human confirmation.

---

### S5 — Analysis engine and claims
The remaining seven analysers · second opinion + deterministic reconciliation · claim extraction and three-direction discrepancy detection · adjudication with impact surfacing · full postmortem composition.
**Done when:** the Employer A case independently produces the primary cause, the redirect count, and all three discrepancies **with correct directions** — two record-errors and one over-claim.

---

### S6 — Aggregation, notification, retention
Pattern aggregation with small-sample guarding · `INotifier` × 3 environments · retention worker at DD-14 defaults (raw 24 months, analysis indefinite) · cascade purge · export.
**Done when:** purge cascades through derived data and its negative test proves the control fails closed.

---

### S7 — Parity, corpus, backfill
**Reduced by DD-24.** CloudLift's AZ-061 parity suite is built and validated (10/12 in parity, 0 divergences local vs azure), so IRI no longer builds adapter-level parity — it runs `scripts/azure_parity_run.sh` and owns only:
- **finding-level parity** — same primary cause, same discrepancy set and directions, same evidence by source location, same classification and correlation, across all three environments **with redaction force-enabled in `local`** (DD-15);
- **anything AZ-061 normalises away** — identifiers, timestamps, metadata casing and **ANN scores**. The last matters if IRI ever ranks or thresholds on retrieval score (§10.2);
- regression corpus per DD-20 coverage gates · backfill of Employer A, Employer B and Employer C by re-ingest-and-diff.
**Done when:** all three environments produce structurally equivalent findings, and the three backfilled outcomes match their human postmortems on primary cause and discrepancy set.

✅ **Adapter-level foundation as of 2026-09-05: 11 of 12 contracts in three-way parity, 0 divergences.** Both gaps IRI depended on are closed — `IGraphDatabase` gained an AWS arm (the "Neptune is VPC-only" premise was wrong and unverified; public endpoints exist since engine 1.4.6.x) and `IVectorSearch` gained an Azure arm (westus2/southcentralus have `basic` AI Search capacity). S7's finding-level equivalence now rests on a genuinely verified foundation for every contract IRI uses.

⚠ **`IFunctionExecution` is the exception, and it is BLOCKED rather than pending** — OpenWhisk's standalone image ships a Docker client older than this host's daemon accepts. IRI must not assume local function execution is available.

---

## 5. Dependencies

```
S0 ──► S1 ──► S3 ──► S4 ──► S5 ──► S6 ──► S7
 │             ▲             ▲              ▲
 └──► S2 ──────┘─────────────┘──────────────┘
      (skills record: blocks S5 claims, feeds S7)
```

**Hard blocks:** S0.5 `ISecretStore` blocks every connector · S0.6 gateway blocks every model call · S2 blocks all S5 claim work · S1's redaction blocks any cloud model call anywhere.
**Not blocking:** S2 can run alongside S1 and S3 — it touches no evidence path.

---

## 6. Verification

| Stage | Primary evidence |
|---|---|
| S0 | 12 contracts resolve per environment; Azure spike note with measured latencies |
| S1 | Employer A feedback quote found with correct citation |
| S2 | Three known claims land with correct status |
| S3 | Zero duplicates on re-scan; revoked token notifies |
| S4 | Employer B classified and correlated correctly |
| S5 | Employer A cause + three discrepancy directions |
| S6 | Purge cascade negative test fails closed |
| S7 | AZ-061 green, plus IRI finding-level equivalence across three environments. **Each contract must be exercised by a real round trip, not by resolution alone** (spike F-4: adapters lazy-import SDKs, so all 12 resolve cleanly with the SDKs absent) — AZ-061 already works this way. |

**Standing:** every privacy control gets an explicit negative test proving it fails closed (REQ-593) — redaction blocking on low confidence, cross-tenant query raising `MissingTenantContextError`, purge cascading, retention expiring.

---

## 7. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| ~~Azure stack torn down before S0.4~~ | **Retired** | **S0.4 ran 2026-09-04 against the live stack.** Azure findings are now measured, not assumed; teardown no longer blocks the plan. Re-deploy only if S7 parity needs it. |
| **Redaction misses an entity** | High | Conservative detection, outbound vault scan, full logging. **Bounded and recorded, not eliminated** — design §9.2 says so plainly |
| **Analysis quality below human baseline** | High | S1 gates on a known-correct answer; per-analyser fixtures; human review before anything is authoritative |
| **Skills migration infidelity** | Medium-high | Priority-ordered adjudication; `unverified` default; never auto-`verified` |
| CloudLift dependency conflicts | Medium | Verified in S0.1; fallback is a process boundary |
| **`IMessageQueue` receive: 3 defects across 2 of 3 adapters** | **High** | Local Artemis had TWO (`int()` on the boolean `redelivered` header; MULTICAST routing discarding sends made before a subscriber attached). AWS SqsAdapter had ONE (an event loop created in the polling thread and never run). **Azure Service Bus had none** — verified, not assumed. All fixed upstream and all three now in the three-way parity set. **S3/S4 must prove RECEIVE, not publish** — publish succeeded in every broken case. *The count is stated per-ADAPTER deliberately: an earlier report of "three adapters" was a miscount, and a rule that overstates its evidence gets relaxed the moment someone checks.* |
| Gremlin/AI Search lag worse than assumed | Medium | Measured in S0.4 before DD-10 is built on |
| Model cost overrun | Medium | Gateway enforces quotas from S0.6 — before any analyser exists |
| OAuth consent friction | Low | DD-16 accepts the warning screen and ~100-user ceiling |

---

## 8. If scope must be cut

In order, first to go:

1. **S6 aggregation** — needs volume to be meaningful; defer until outcomes accumulate.
2. **MS365/Teams connector** — Krisp and Gmail cover the current evidence base entirely.
3. **Second opinion** — DD-04/DD-13 already make single-model the default in two of three environments.
4. **Graph projection** — DD-01 makes relational authoritative; the graph is an optimisation.
5. **Azure environment** — `local` and `aws` deliver full function; Azure is portability proof. (Adapter parity itself is no longer IRI's to cut — DD-24 moves it to CloudLift's AZ-061.)

**Never cut:** the redaction gateway, tenant isolation, human adjudication before authority, or the privacy negative tests. Those are not features.

---

## 9. Out of scope

CloudLift's unbuilt Azure items (AZ-061/062/070/080/081/082) · the `ISecretStore`/`IScheduler`/`INotifier` contracts being upstreamed into CloudLift — IRI defines them locally, and contributing them back is a separate conversation with that maintainer · resume-optimizer's existing `cloudlift_*_adapter.py` shims, which IRI bypasses (DD-09) and which are left alone rather than migrated.
