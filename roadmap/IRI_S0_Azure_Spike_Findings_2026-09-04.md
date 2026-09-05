# S0.4 — Azure Verification Spike: Findings

> **Date:** 2026-09-04 · **Env:** `cloudlift-dev-rg` (eastus RG; services in westus3) · **Status:** Complete
> **Plan ref:** `PLAN_Interview_Rejection_Intelligence_2026-09-04.md` §3, §4 (S0.4)
> Run against the **live** dev stack before AZ-092 teardown, as the plan required.

## Verdict

The spike passes. **12/12 contracts resolve in both `local` and `azure`.** DD-10 is confirmed and now quantified. Three findings change the design; one changes how the parity suite must be written.

---

## 1. Results

| Probe | Result |
|---|---|
| Resolve 12 contracts — `local` | **12/12** (Filesystem, SQLite, ArangoDB ×3, SentenceTransformers, Redis, Artemis, LocalVLLM, DuckDB, OpenWhisk) |
| Resolve 12 contracts — `azure` | **12/12** (Blob, Postgres, Cosmos, CosmosGremlin, AI Search, AOAI Embedding, Redis, Service Bus, AOAI, CosmosLifecycle, Synapse, Functions) |
| Module identity `cloudlift.bridge` ↔ `core.bridge` | **Unified** — same module objects, `IObjectStorage` identical |
| Tenant context with no tenant set | **Fails closed** — `MissingTenantContextError` |
| `CosmosGremlinAdapter` required members | `upsert_edge`, `list_edges`, `delete_edge`, `traverse` **all present**; `supports_feature` present |
| `IEmbeddingService.embed` | **Synchronous**; `dimension` = 1536 == `len(embed())`; ~685 ms |
| Azure OpenAI `gpt-4o` round trip | **OK**, 640 ms |

### Measured latencies

| Service | Write | Visibility lag after write | Read-your-writes |
|---|---|---|---|
| **Cosmos Gremlin** | **2164 ms** | **562 ms** | **NO** |
| **Azure AI Search** | 79–399 ms | **529–986 ms** (n=3) | **NO** |

---

## 2. Findings that change the design

### F-1 — DD-10 confirmed, and it extends to AI Search *(design update needed)*
DD-10 made the graph projection asynchronous because Cosmos Gremlin is not read-your-writes. **Measured: 562 ms.** The design is correct.

**What is new:** Azure AI Search is *also* not read-your-writes (529–986 ms), and **deletes are eventually consistent too** — a deleted document still returned from `$count` for several seconds. DD-10 currently reasons only about the graph. §10.2 retrieval must not assume a just-indexed segment is searchable, and any purge verification (S6, REQ-593) must poll rather than assert immediately.

### F-2 — Gremlin edge collections must be pre-provisioned per tenant *(new constraint)*
`upsert_edge(edge_collection=...)` maps to a **Cosmos container** named `t_<tenant-uuid-underscored>_<edge_collection>`. A missing container is a **404**, not an auto-create:

```
GET .../dbs/cloudlift/colls/t_cc091cc0_..._iri_spike → NotFound (404)
```

Local ArangoDB creates collections on demand; **Azure does not.** IRI must declare its edge-collection set up front and provision a container per tenant at tenant-creation time. This is provisioning work that belongs in **S0.2 (tenant provisioning)**, not in the graph code, and it is a per-tenant cost multiplier worth noting against DD-16's ~100-user ceiling.

### F-3 — AI Search index schema is fixed: `id`, `content`, `embedding` *(new constraint)* — ✅ **FIXED UPSTREAM 2026-09-05**

> **Update:** CloudLift treated this as a genuine contract violation, not a documented quirk — `IVectorSearch.upsert()` types metadata as an open dict, and local accepted what Azure rejected. They added a `metadata_json` field to the index; the adapter now serialises anything outside the declared schema into it and restores it on read, verified live with nested dicts and ints. Parity went DIVERGE → PARITY.
>
> **What still holds:** `metadata_json` is deliberately **not filterable**, because filtering a serialised blob is a guarantee Azure cannot keep. So carrying metadata is portable; querying it is not. DD-23 was amended rather than dropped.

The original finding, for the record:
Arbitrary metadata is **rejected**, not ignored:

> `The property 'probe' does not exist on type 'search.document'`

IRI evidence metadata (source, outcome id, speaker, timestamp) **cannot ride along in the vector index on Azure.** Retrieval must return ids and join metadata from the relational store — which DD-01 already makes authoritative, so the design's grain is right, but §10.2 must state the join explicitly rather than assuming filterable vector metadata. Any `filters=` argument to `search()` is not portable against this index as provisioned.

### F-4 — Resolution success does not prove the adapter works *(changes the parity suite)*
Every Azure adapter **lazy-imports its SDK**. All 12 resolved cleanly with `gremlin_python`, `openai`, `azure-cosmos` and `azure-search-documents` absent from the venv; failures appeared only on first call.

This is good adapter design, but it means **a parity suite that asserts "12/12 resolve" proves nothing.** OI-10's suite must exercise a real round trip per contract. Sequenced early: it invalidates the cheapest possible smoke test.

---

## 3. Environment repair (unplanned, prerequisite)

The project `.venv` was **broken before this work started** — unrelated to IRI. Its interpreter pointed at `hybrid-ai-windows/applications/resume-optimizer/.python/...`, a path left behind when the project moved to `projects/`. `ro start` could not have worked.

- Rebuilt on **Python 3.14.7**; old venv preserved as `.venv.broken-2026-09-04` (delete when you're satisfied).
- `python-jobspy` makes pip backtrack to a **numpy sdist that cannot build on 3.14**. Fix: install `numpy>=2.1`/`pandas>=2.2` first, then jobspy under a constraints file. Resolved to jobspy 1.1.13. **`backend/requirements.txt` should carry a numpy floor** or this recurs on every clean build.
- Installed `cloudlift` editable from `projects/cloudlift`, plus the `azure` extras IRI needs.

## 4. Correction

An earlier probe reported AI Search as "NOT VISIBLE within 20s". That was **my probe's bug** — it called `search(vector, limit=...)` when the parameter is `top_k`, and the retry loop swallowed the `TypeError`. Signatures are uniform across local, aws and azure adapters; there is no CloudLift defect here. The corrected numbers are in §1.

## 5. Stale claim found in the codebase

`backend/cloudlift_llm_adapter.py` (and siblings) state as rationale:

> "cloudlift.bridge.* namespace suffers from module identity split (core.* vs cloudlift.*) that breaks the tenant context system"

**This is no longer true** — verified above. The alias finder returns the real `core.*` module object, so class and ContextVar identity are unified. The shims' stated reason for existing has lapsed. DD-09 already routes IRI around them; no migration of the existing shims is proposed here, but the docstrings should not be trusted as current.

## 6. Probe hygiene

All probe artifacts removed: search index returns to 0 documents; spike edges deleted. The pre-existing `az091` graph container was reused and left in place.
