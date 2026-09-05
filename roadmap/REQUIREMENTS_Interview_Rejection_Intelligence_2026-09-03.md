# Requirements — Interview & Rejection Intelligence (IRI)
## Resume Optimizer — Phase 18

> **Document type:** Requirements specification. **This is not a design.** No architecture, schema, component boundaries, or technology selections beyond those already constrained by the existing CloudLift adapter contract.
> **Version:** 1.0 · **Date:** 2026-09-03 · **Status:** Draft for review
> **Author:** Claude (with the candidate) · **Requested by:** the candidate

---

## 1. Purpose

Add the capability to **automatically ingest, correlate, and forensically analyse job-search outcome evidence** — meeting transcripts and email — so that the reasons behind rejections and advancements are captured systematically rather than reconstructed by hand.

The system must run identically under all three CloudLift environments: **local**, **aws**, and **azure**.

## 2. Background and motivating case

On 2026-09-03 a rejection arrived from Employer A for a senior engineering role. Manual analysis reconstructed the cause by pulling the Krisp transcript of the technical screen, the complete Gmail thread, and cross-referencing both against a verified-skills record.

That manual analysis established the target capability. It found:

- The **interviewer had stated the rejection reason aloud** in the final minutes of the screen, in response to the candidate asking for feedback.
- A **capability mismatch** between the employer's stack and the candidate's demonstrated depth.
- **Three claim discrepancies** against the verified-skills record — two of which turned out to be *under-claims* (the record was wrong) and one a genuine *over-claim*.
- Contributing secondary factors: a compensation band collision and a pre-flagged overqualification concern, both visible in an earlier recruiter-screen transcript.

The manual effort took roughly an hour and was only possible because a recording existed. **The purpose of this feature is to make that analysis automatic, consistent, and cumulative.** Section 15 uses this case as the validation scenario.

## 3. Glossary

| Term | Definition |
|---|---|
| **IRI** | Interview & Rejection Intelligence — the capability specified by this document |
| **Source connector** | An integration that retrieves evidence from an external system (Krisp, Gmail, MS365, upload) |
| **Evidence item** | A single normalised artifact — one transcript, one email message, one uploaded file |
| **Outcome event** | A detected, classified occurrence in a candidate's pipeline (rejection, advancement, ghosting, offer, withdrawal) |
| **Correlation** | Linking evidence items and outcome events to a tracked job posting/application |
| **Forensic analysis** | LLM-driven root-cause analysis of an outcome, producing ranked causes with quoted evidence |
| **Second opinion** | An independent model's analysis of the same evidence, produced without sight of the first |
| **Reconciliation** | Comparing primary and second-opinion analyses; surfacing agreement, divergence, and confidence |
| **Verified-skills record** | The authoritative store of what the candidate can genuinely claim, with provenance |
| **Claim discrepancy** | A difference between what a candidate stated in an interview and the verified-skills record — an over-claim or an under-claim |
| **Postmortem artifact** | The durable written analysis produced for a single outcome |
| **CloudLift environment** | `local` \| `aws` \| `azure` — selected by `CLOUDLIFT_ENV` |

## 4. Stakeholders

| Stakeholder | Interest |
|---|---|
| Candidate (primary user) | Understand why outcomes happened; correct false claims; improve future performance |
| Application owner/operator | Run the system across environments at predictable cost |
| Third parties in recordings | Interviewers and recruiters whose voices and words are captured — have privacy interests they did not opt into |

## 5. Scope

### 5.1 In scope
- Source connectors for Krisp, Gmail, Microsoft 365 (Outlook mail + Teams transcripts), and manual upload
- Detection and classification of outcome events
- Correlation of evidence and outcomes to tracked postings
- Full forensic analysis with independent second opinion and reconciliation
- Claim-discrepancy detection against the verified-skills record
- Tracker updates, postmortem artifact generation, and cross-outcome pattern aggregation
- Human review and approval workflow
- Multi-user operation with per-user credentials and data isolation
- Parity across `local`, `aws`, `azure`

### 5.2 Out of scope
- Recording or transcribing meetings (the system consumes transcripts; it does not create them)
- Real-time or in-interview assistance
- Automated outbound communication to employers or recruiters
- Automatic modification of resumes or the verified-skills record without human approval
- Building the Azure adapter set (assumed to exist — see 6.1)
- Applicant tracking on the employer side

## 6. Assumptions

| ID | Assumption |
|---|---|
| A-01 | **The CloudLift Azure adapter set already exists** and provides parity with the local and aws sets across all adapter types. This feature consumes it; it does not build it. |
| A-02 | The existing tracker (job postings with status, notes, and dates) is the system of record for applications and will be extended rather than replaced. |
| A-03 | A verified-skills record exists or will be established as a first-class, queryable store with provenance per claim. Today this information lives in unstructured project memory. |
| A-04 | Users have, or can grant, the necessary OAuth scopes to their own Krisp, Google, and Microsoft accounts. |
| A-05 | Transcript quality is imperfect — speaker attribution errors and mis-transcribed technical terms are expected and must be tolerated. |
| A-06 | Existing background-job infrastructure can be extended for scheduled and queued work. |

---

## 7. Functional requirements

### 7.1 Source connectors

| ID | Requirement | Priority |
|---|---|---|
| REQ-100 | The system SHALL ingest meeting transcripts, summaries, participant lists, timestamps and durations from **Krisp**. | MUST |
| REQ-101 | The system SHALL ingest email messages, threads, senders, recipients, timestamps and attachments from **Gmail**. | MUST |
| REQ-102 | The system SHALL ingest email from **Microsoft 365 / Outlook** and meeting transcripts from **Microsoft Teams**. | MUST |
| REQ-103 | The system SHALL accept **manual upload or paste** of a transcript or email that automated sources did not capture, and treat it identically downstream. | MUST |
| REQ-104 | Each connector SHALL be independently enableable per user; absence or failure of one connector SHALL NOT prevent others from operating. | MUST |
| REQ-105 | Connectors SHALL retrieve incrementally, processing only items not previously ingested, using a durable per-user, per-source high-water mark. | MUST |
| REQ-106 | The system SHALL tolerate and report source-side failures — auth expiry, rate limiting, service outage, oversized payloads — without data loss or duplicate processing. | MUST |
| REQ-107 | The system SHALL record, for every evidence item, its source system, native identifier, retrieval timestamp, and a content hash. | MUST |
| REQ-108 | Where a source imposes size limits that prevent whole-item retrieval, the system SHALL retrieve in parts and reassemble, or record an explicit partial-retrieval state. | SHOULD |

### 7.2 Ingestion and normalisation

| ID | Requirement | Priority |
|---|---|---|
| REQ-120 | All evidence items SHALL be normalised into a single internal representation regardless of source. | MUST |
| REQ-121 | Normalisation SHALL preserve verbatim content; paraphrase or lossy summarisation of source material at ingestion is prohibited. | MUST |
| REQ-122 | For transcripts, the system SHALL preserve speaker attribution and per-utterance timestamps where the source provides them. | MUST |
| REQ-123 | The system SHALL deduplicate evidence items by content hash and native identifier. | MUST |
| REQ-124 | The system SHALL flag evidence items whose speaker attribution appears unreliable (e.g. all utterances attributed to one speaker in a multi-party meeting). | SHOULD |
| REQ-125 | The system SHALL retain the original unmodified payload alongside the normalised form, subject to the retention rules in §11. | MUST |

### 7.3 Outcome detection and classification

| ID | Requirement | Priority |
|---|---|---|
| REQ-140 | The system SHALL detect and classify outcome events including at minimum: **rejection**, **advancement to next stage**, **interview scheduled**, **interview held**, **offer**, **withdrawal**, and **no response / stalled**. | MUST |
| REQ-141 | Detection SHALL identify **automated ATS rejections** (template mail from no-reply addresses) and **human rejections** separately, as they carry different diagnostic weight. | MUST |
| REQ-142 | The system SHALL detect **stalling** — an application with a completed interview and no subsequent contact beyond a configurable threshold. | MUST |
| REQ-143 | Every classification SHALL carry a confidence value and the specific evidence that produced it. | MUST |
| REQ-144 | Classifications below a configurable confidence threshold SHALL be routed for human confirmation rather than applied automatically. | MUST |
| REQ-145 | The system SHALL NOT classify an outcome on the basis of absence of evidence alone, except for the explicit stalling case in REQ-142. | MUST |

### 7.4 Correlation

| ID | Requirement | Priority |
|---|---|---|
| REQ-160 | The system SHALL correlate evidence items and outcome events to a tracked posting using available signals — employer name, requisition identifier, role title, participant identities, sender domain, and temporal proximity. | MUST |
| REQ-161 | Correlation SHALL produce a confidence value; low-confidence correlations SHALL be presented for human confirmation. | MUST |
| REQ-162 | The system SHALL support **many-to-one** correlation: multiple evidence items (recruiter screen, technical screen, mail thread) linked to one application. | MUST |
| REQ-163 | The system SHALL detect and surface the case where evidence correlates to **no known posting**, and offer to create one. | MUST |
| REQ-164 | The system SHALL handle **multiple concurrent applications to the same employer** without mis-assigning evidence between them. | MUST |
| REQ-165 | A user SHALL be able to manually create, correct, or break any correlation, and corrections SHALL persist against future re-processing. | MUST |

### 7.5 Forensic analysis

| ID | Requirement | Priority |
|---|---|---|
| REQ-180 | For each outcome event, the system SHALL produce a forensic analysis identifying the **primary cause** and **ranked contributing factors**. | MUST |
| REQ-181 | Every asserted cause SHALL be supported by **verbatim quoted evidence** with a reference to its source item and location. | MUST |
| REQ-182 | The analysis SHALL specifically detect and extract **explicit interviewer feedback**, including feedback given in response to a candidate's request for it. | MUST |
| REQ-183 | The analysis SHALL identify **questions the candidate failed to answer directly**, including instances where an interviewer re-asked, rephrased, or redirected. | MUST |
| REQ-184 | The analysis SHALL quantify interviewer redirection frequency as a signal of interview control. | SHOULD |
| REQ-185 | The analysis SHALL identify **technologies, tools, and frameworks named by each party**, and distinguish those the candidate claimed from those the employer requested. | MUST |
| REQ-186 | The analysis SHALL identify **what the candidate did well**, evidenced, and SHALL NOT fabricate positives where none are evidenced. | MUST |
| REQ-187 | The analysis SHALL distinguish **capability mismatch** from **preparation or performance failure** and state which it judges the outcome to be. | MUST |
| REQ-188 | The analysis SHALL incorporate evidence from **earlier stages** of the same application where available (e.g. concerns a recruiter raised before the technical screen). | MUST |
| REQ-189 | The analysis SHALL identify **non-technical contributing factors** where evidenced — compensation band collisions, level or seniority mismatch, geography, timing. | MUST |
| REQ-190 | The analysis SHALL produce **specific, actionable guidance** for future interviews, derived from the evidence rather than generic advice. | MUST |
| REQ-191 | Where the evidence does not support a confident conclusion, the analysis SHALL say so explicitly rather than assert one. | MUST |

### 7.6 Second opinion and reconciliation

| ID | Requirement | Priority |
|---|---|---|
| REQ-210 | The system SHALL obtain an **independent second-opinion analysis** of the same evidence from a different model. | MUST |
| REQ-211 | The second-opinion model SHALL NOT be shown the primary analysis before producing its own. | MUST |
| REQ-212 | The degree of independence — different vendor, different model from the same vendor, or different deployment — SHALL be **configurable per CloudLift environment**. | MUST |
| REQ-213 | The system SHALL produce a **reconciliation** identifying where the two analyses agree, where they diverge, and the material consequence of any divergence. | MUST |
| REQ-214 | Convergent conclusions SHALL be marked as higher confidence than single-model conclusions. | MUST |
| REQ-215 | Divergence SHALL be surfaced to the user rather than silently resolved by preferring one model. | MUST |
| REQ-216 | The system SHALL record which models produced each analysis, with version or deployment identifiers, for auditability. | MUST |
| REQ-217 | The system SHALL degrade gracefully to a single-model analysis, clearly labelled as such, if no independent model is available. | SHOULD |

### 7.7 Claim-discrepancy detection

| ID | Requirement | Priority |
|---|---|---|
| REQ-230 | The system SHALL extract every **technology, tool, framework, methodology, and quantified claim** the candidate asserted during an interview. | MUST |
| REQ-231 | Each extracted claim SHALL be cross-checked against the **verified-skills record**. | MUST |
| REQ-232 | The system SHALL surface **over-claims** — asserted in interview, not supported by the verified record. | MUST |
| REQ-233 | The system SHALL surface **under-claims** — genuinely held per the verified record but absent from resumes and application materials. | MUST |
| REQ-234 | The system SHALL surface **record errors** — cases where the interview evidence suggests the verified record itself is wrong. | MUST |
| REQ-235 | The system SHALL classify discrepancies by severity, distinguishing a stated past-experience claim from a forward-looking recommendation. | MUST |
| REQ-236 | The system SHALL NOT modify the verified-skills record automatically. Every change SHALL require explicit human adjudication. | MUST |
| REQ-237 | Upon adjudication, the system SHALL identify **every downstream artifact affected** by the corrected claim — resumes, cover letters, tracker notes — and surface them for update. | MUST |
| REQ-238 | Adjudications SHALL be recorded with date, decision, and rationale, and SHALL be durable. | MUST |

### 7.8 Tracker integration

| ID | Requirement | Priority |
|---|---|---|
| REQ-250 | The system SHALL update the correlated posting's **status** on confirmed outcome detection. | MUST |
| REQ-251 | The system SHALL attach a **structured outcome record** to the posting — dates, stages held, participants, and a link to the postmortem artifact. | MUST |
| REQ-252 | The system SHALL preserve existing manually entered tracker notes; automated updates SHALL append, never overwrite. | MUST |
| REQ-253 | Every automated tracker change SHALL be attributed to the system and reversible. | MUST |
| REQ-254 | Status changes SHALL require human confirmation where detection confidence is below the configured threshold (REQ-144). | MUST |

### 7.9 Postmortem artifacts

| ID | Requirement | Priority |
|---|---|---|
| REQ-270 | The system SHALL generate a **durable postmortem document** for each analysed outcome. | MUST |
| REQ-271 | The postmortem SHALL contain at minimum: outcome and date; full timeline; primary cause; ranked contributing factors; verbatim supporting evidence; what went well; claim discrepancies; the reconciled second opinion; and forward-looking guidance. | MUST |
| REQ-272 | The postmortem SHALL be stored durably and be retrievable independently of the application database. | MUST |
| REQ-273 | The postmortem SHALL be exportable in a portable document format. | MUST |
| REQ-274 | The source evidence underpinning a postmortem SHALL be archived alongside it, subject to §11 retention rules. | MUST |
| REQ-275 | Postmortems SHALL be versioned; regeneration SHALL NOT destroy a prior version. | SHOULD |

### 7.10 Pattern aggregation

| ID | Requirement | Priority |
|---|---|---|
| REQ-290 | The system SHALL aggregate findings across all analysed outcomes for a user to identify **recurring patterns**. | MUST |
| REQ-291 | Aggregation SHALL surface at minimum: recurring capability gaps; recurring claim discrepancies; stage-of-loss distribution; employer-type and industry patterns; compensation-band collisions; and geography patterns. | MUST |
| REQ-292 | The system SHALL correlate outcomes with the **resume version and shape** used, to indicate which materials convert. | SHOULD |
| REQ-293 | The system SHALL distinguish **statistically meaningful patterns from small-sample noise** and label confidence accordingly. | MUST |
| REQ-294 | Aggregate findings SHALL link back to the individual outcomes that produced them. | MUST |
| REQ-295 | The system SHALL identify **improvement or regression over time** on recurring issues. | SHOULD |

### 7.11 Triggers and scheduling

| ID | Requirement | Priority |
|---|---|---|
| REQ-310 | The system SHALL support **scheduled polling** of all enabled sources on a per-user configurable cadence. | MUST |
| REQ-311 | The system SHALL support **manual on-demand scan** initiated by the user. | MUST |
| REQ-312 | The system SHALL support **event- or webhook-driven** processing where a source provides push notification. | MUST |
| REQ-313 | The system SHALL initiate targeted evidence-watching when a **tracker posting status changes** to an active state. | MUST |
| REQ-314 | Concurrent triggers for the same user and source SHALL NOT cause duplicate processing. | MUST |
| REQ-315 | Long-running analysis SHALL execute asynchronously with observable progress and SHALL NOT block interactive use. | MUST |
| REQ-316 | Failed processing SHALL be retryable without reprocessing already-completed work. | MUST |

### 7.12 Human review workflow

| ID | Requirement | Priority |
|---|---|---|
| REQ-330 | Every automated conclusion SHALL be presented for human review before it is treated as authoritative. | MUST |
| REQ-331 | The user SHALL be able to accept, edit, or reject any finding, and SHALL be able to add their own. | MUST |
| REQ-332 | Human corrections SHALL be durable and SHALL inform subsequent analyses. | MUST |
| REQ-333 | Items awaiting review SHALL be surfaced in a queue with an indication of significance. | MUST |
| REQ-334 | The system SHALL clearly distinguish machine-generated from human-confirmed content in every view and artifact. | MUST |

### 7.13 User interface

| ID | Requirement | Priority |
|---|---|---|
| REQ-350 | The UI SHALL provide a **connector management** view — connect, disconnect, view status, re-authorise. | MUST |
| REQ-351 | The UI SHALL provide an **outcome timeline** per application showing all correlated evidence in sequence. | MUST |
| REQ-352 | The UI SHALL present the postmortem with evidence quotes **navigable back to their source location**. | MUST |
| REQ-353 | The UI SHALL present the claim-discrepancy adjudication workflow. | MUST |
| REQ-354 | The UI SHALL present aggregate patterns with drill-through to contributing outcomes. | MUST |
| REQ-355 | The UI SHALL present the review queue (REQ-333). | MUST |
| REQ-356 | The UI SHALL expose retention status and purge controls (§11). | MUST |

### 7.14 Notifications

| ID | Requirement | Priority |
|---|---|---|
| REQ-370 | The system SHALL notify the user when a **new outcome is detected**. | MUST |
| REQ-371 | The system SHALL notify when an analysis **completes and awaits review**. | MUST |
| REQ-372 | The system SHALL notify on **connector failure or credential expiry**. | MUST |
| REQ-373 | Notification channels and verbosity SHALL be user-configurable. | SHOULD |

---

## 8. Multi-tenancy and identity

| ID | Requirement | Priority |
|---|---|---|
| REQ-400 | The system SHALL support multiple users within one deployment. | MUST |
| REQ-401 | Each user SHALL connect their **own** Krisp, Google and Microsoft accounts; credentials SHALL NOT be shared between users. | MUST |
| REQ-402 | All evidence, outcomes, analyses, artifacts and aggregates SHALL be **strictly isolated per user**. Cross-user access SHALL be impossible through any interface. | MUST |
| REQ-403 | Credentials and tokens SHALL be stored encrypted and SHALL never be exposed to another user or written to logs. | MUST |
| REQ-404 | Token refresh SHALL be automatic; expiry SHALL surface as an actionable notification rather than silent failure. | MUST |
| REQ-405 | A user SHALL be able to revoke a connector, which SHALL immediately stop ingestion and delete stored credentials. | MUST |
| REQ-406 | Model and processing **cost SHALL be attributable per user**. | MUST |
| REQ-407 | Per-user quotas or rate limits SHALL be enforceable to bound cost. | SHOULD |
| REQ-408 | The system SHALL support complete **per-user data export** and **per-user deletion**. | MUST |

---

## 9. CloudLift portability

| ID | Requirement | Priority |
|---|---|---|
| REQ-430 | All IRI functionality SHALL operate under `CLOUDLIFT_ENV` values **`local`**, **`aws`**, and **`azure`** with equivalent behaviour. | MUST |
| REQ-431 | Environment selection SHALL remain a **single configuration decision**, consistent with the existing single-flag pattern. | MUST |
| REQ-432 | All external service interaction — persistence, queueing, search, vector, graph, model inference, object storage, secrets, scheduling, notification — SHALL occur through **bridge adapters**. No application logic SHALL contain provider-specific calls. | MUST |
| REQ-433 | Any capability required by IRI that has no existing adapter SHALL be introduced **as a new adapter type**, implemented for all three environments. | MUST |
| REQ-434 | Behavioural differences between environments SHALL be limited to performance, cost and capacity — **never to features or analytical outcomes**. | MUST |
| REQ-435 | The same evidence SHALL yield materially equivalent analytical conclusions in every environment; a **parity test suite** SHALL demonstrate this. | MUST |
| REQ-436 | Source connectors are **external SaaS integrations and SHALL behave identically in all environments**; they SHALL NOT be re-implemented per cloud. | MUST |
| REQ-437 | Second-opinion model routing SHALL be configurable per environment (REQ-212) without application code change. | MUST |
| REQ-438 | The system SHALL run fully functionally in `local` with **no cloud dependency and no cloud cost**. | MUST |
| REQ-439 | Environment-specific configuration SHALL be externalised; no environment identifier SHALL be embedded in application logic. | MUST |

---

## 10. Data requirements

| ID | Requirement | Priority |
|---|---|---|
| REQ-460 | The system SHALL persist, as first-class entities: evidence items, outcome events, correlations, analyses, second opinions, reconciliations, claim discrepancies, adjudications, postmortem artifacts, and aggregate findings. | MUST |
| REQ-461 | Every derived assertion SHALL retain **lineage to the source evidence** that produced it. | MUST |
| REQ-462 | The **verified-skills record** SHALL be a queryable store where each claim carries provenance, confidence, and adjudication history. | MUST |
| REQ-463 | The system SHALL store transcripts of substantial length without truncation; retrieval SHALL support partial and streamed access. | MUST |
| REQ-464 | All records SHALL carry created and modified timestamps and the actor responsible. | MUST |
| REQ-465 | Deletion SHALL be honoured through all derived data, not only the primary record. | MUST |

---

## 11. Security, privacy and compliance

> Interview transcripts contain the words and voices of **third parties who did not opt into this system**. These requirements are not optional.

| ID | Requirement | Priority |
|---|---|---|
| REQ-480 | Evidence content SHALL be **encrypted at rest** and in transit. | MUST |
| REQ-481 | The system SHALL maintain an **access audit log** recording every read of transcript or email content, by whom, and when. | MUST |
| REQ-482 | The system SHALL log **every submission of content to a model**, recording which content, which model, which environment, and when. | MUST |
| REQ-483 | The system SHALL apply **PII redaction or masking to third-party identifiers before content is sent to any model**, and SHALL apply this most strictly for cloud-hosted models. | MUST |
| REQ-484 | Redaction SHALL be reversible **locally** so that the user can view original content, while the redacted form is what leaves the trust boundary. | MUST |
| REQ-485 | Redaction failure SHALL **block** model submission rather than fall back to sending unredacted content. | MUST |
| REQ-486 | Raw evidence SHALL be subject to a **configurable retention period**, after which it is automatically purged. | MUST |
| REQ-487 | Derived analyses and postmortems MAY be retained beyond raw evidence, with a separately configurable period. | MUST |
| REQ-488 | The user SHALL be able to **purge any evidence item, outcome, or entire application history on demand**, with cascade through derived data. | MUST |
| REQ-489 | The system SHALL surface **what is retained, for how long, and what has been sent to which model**, in the UI. | MUST |
| REQ-490 | Content SHALL NOT be used to train or fine-tune any model, and connector configuration SHALL prefer providers and settings that contractually exclude training use. | MUST |
| REQ-491 | The system SHALL warn the user where recording or retention of a meeting may carry jurisdiction-specific consent obligations. | SHOULD |
| REQ-492 | Secrets SHALL be held in an environment-appropriate secret store through an adapter; secrets SHALL never appear in source, configuration files, or logs. | MUST |

---

## 12. Non-functional requirements

### 12.1 Performance and capacity
| ID | Requirement | Priority |
|---|---|---|
| REQ-510 | Interactive views SHALL respond within 2 seconds for a user with 500 applications and 2,000 evidence items. | SHOULD |
| REQ-511 | A full forensic analysis with second opinion SHALL complete within 15 minutes of being queued under normal load. | SHOULD |
| REQ-512 | The system SHALL process a single transcript of at least 3 hours' duration without failure. | MUST |
| REQ-513 | Scheduled scans SHALL complete within their cadence interval; overrun SHALL be detected and reported. | MUST |

### 12.2 Reliability
| ID | Requirement | Priority |
|---|---|---|
| REQ-530 | Ingestion SHALL be idempotent; repeated processing SHALL NOT duplicate evidence, outcomes, or artifacts. | MUST |
| REQ-531 | Failure of any single source, model, or analysis stage SHALL NOT corrupt existing data or block unrelated work. | MUST |
| REQ-532 | Partial analysis results SHALL be preserved and resumable rather than discarded on failure. | SHOULD |
| REQ-533 | The system SHALL remain usable for review of existing analyses when all external sources are unavailable. | MUST |

### 12.3 Cost
| ID | Requirement | Priority |
|---|---|---|
| REQ-550 | Model invocation cost SHALL be recorded per analysis and attributable per user (REQ-406). | MUST |
| REQ-551 | The system SHALL enforce configurable spend ceilings and SHALL degrade or defer rather than exceed them. | MUST |
| REQ-552 | The `local` environment SHALL incur no external model cost. | MUST |
| REQ-553 | Re-analysis of unchanged evidence SHALL be avoided unless explicitly requested. | MUST |

### 12.4 Observability
| ID | Requirement | Priority |
|---|---|---|
| REQ-570 | Every processing stage SHALL emit structured, correlatable telemetry. | MUST |
| REQ-571 | The system SHALL expose health status per connector, per user. | MUST |
| REQ-572 | Analysis quality signals — confidence distribution, human-correction rate, model divergence rate — SHALL be measurable over time. | SHOULD |
| REQ-573 | Telemetry SHALL NOT contain evidence content or PII. | MUST |

### 12.5 Testability
| ID | Requirement | Priority |
|---|---|---|
| REQ-590 | The system SHALL be testable end to end without live external accounts, using recorded fixtures. | MUST |
| REQ-591 | A **parity suite** SHALL verify equivalent behaviour across all three environments (REQ-435). | MUST |
| REQ-592 | Analysis quality SHALL be regression-tested against a curated corpus of known outcomes with expected conclusions. | MUST |
| REQ-593 | Privacy controls — redaction, retention, purge, isolation — SHALL each have explicit negative tests proving the control fails closed. | MUST |

---

## 13. Constraints

| ID | Constraint |
|---|---|
| C-01 | Must integrate with the existing CloudLift bridge-adapter pattern and its single-flag environment selection. |
| C-02 | Must extend the existing tracker and background-job infrastructure rather than duplicate them. |
| C-03 | Source connectors depend on third-party APIs whose quotas, availability and terms are outside the system's control. |
| C-04 | Transcript availability depends on meetings having been recorded; the system cannot analyse what was never captured. |
| C-05 | Analysis quality is bounded by transcript fidelity (A-05). |

---

## 14. Acceptance criteria

The capability is complete when all MUST requirements are satisfied and:

1. A user connects Krisp, Gmail and MS365, and evidence is ingested without manual intervention.
2. A rejection email is detected, classified, and correlated to the correct posting with the tracker updated after human confirmation.
3. A forensic analysis is produced with primary cause, ranked factors, and verbatim quoted evidence traceable to source.
4. An independent second opinion is produced without sight of the first, and a reconciliation identifies agreement and divergence.
5. Claim discrepancies are surfaced in both directions — over-claims and under-claims — and adjudication updates the verified record and identifies affected downstream artifacts.
6. A durable, exportable postmortem artifact is generated and retrievable.
7. Aggregate patterns are produced across at least ten outcomes with drill-through and confidence labelling.
8. All of the above behave equivalently under `local`, `aws` and `azure`, demonstrated by the parity suite.
9. Privacy controls pass their negative tests: redaction fails closed, retention purges, deletion cascades, cross-user access is impossible.
10. The system operates in `local` with no cloud dependency or cost.

---

## 15. Validation scenario — the Employer A case

The system SHALL be validated by reprocessing the 2026-09-03 Employer A rejection from original sources and reproducing the manual analysis. Specifically, it SHALL:

| # | Expected outcome | Requirements exercised |
|---|---|---|
| V-1 | Ingest both Krisp transcripts and the full Gmail thread | REQ-100, 101, 105, 120 |
| V-2 | Classify the Workday message as an automated ATS rejection | REQ-140, 141 |
| V-3 | Correlate both transcripts and all mail to the single Employer A posting | REQ-160, 162 |
| V-4 | Extract the interviewer's closing feedback — the RAG-depth and off-the-shelf-reasoning-model comments — and identify it as the primary cause | REQ-182, 180, 181 |
| V-5 | Identify that the candidate could not name a PDF library or an Azure agent platform when asked repeatedly | REQ-183, 185 |
| V-6 | Quantify interviewer redirection across the technical portion | REQ-184 |
| V-7 | Flag three claim discrepancies — Cosmos DB, KQL, LangChain/LangGraph — against the verified record | REQ-230, 231, 232 |
| V-8 | On adjudication, record Cosmos DB and KQL as **record errors** (under-claims) and LangChain as an **over-claim**, and identify affected resumes | REQ-233, 234, 236, 237 |
| V-9 | Surface the compensation collision ($200K cap vs $200–210K stated) from the recruiter-screen transcript | REQ-188, 189 |
| V-10 | Surface the recruiter's pre-flagged overqualification concern from the earlier stage | REQ-188 |
| V-11 | Identify what went well — the human-in-the-loop triage design and externally-composed agent workflows | REQ-186 |
| V-12 | Judge the outcome a capability mismatch rather than a preparation failure | REQ-187 |
| V-13 | Produce a second opinion that independently converges, and reconcile the two | REQ-210, 211, 213, 214 |
| V-14 | Generate a durable postmortem equivalent in substance to the manual one | REQ-270, 271, 272 |

---

## 16. Open questions for design

These are deliberately unresolved here and belong to design:

| # | Question |
|---|---|
| Q-01 | Where does the verified-skills record live, and how is the existing unstructured project memory migrated into it? |
| Q-02 | What is the concrete redaction technique, and how is reversibility (REQ-484) achieved without weakening the control? |
| Q-03 | Which new adapter types are required (object storage, secrets, scheduler, notification), and what are their contracts? |
| Q-04 | How is analytical parity across environments measured objectively when models differ (REQ-435)? |
| Q-05 | What are the default retention periods, and are they per-user configurable or system-wide? |
| Q-06 | How are Krisp, Google and Microsoft OAuth applications registered and managed for multi-user use? |
| Q-07 | What is the chunking strategy for transcripts exceeding model context, and how is analytical coherence preserved across chunks? |
| Q-08 | How does pattern aggregation avoid over-fitting to a small number of outcomes (REQ-293)? |
| Q-09 | Should analyses be automatically re-run when the verified-skills record changes, given prior conclusions may be invalidated? |
| Q-10 | What is the migration path for outcomes already analysed manually, including the Employer A case? |
