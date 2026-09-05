# S0.2 — Tenant Provisioning Specification

> **Date:** 2026-09-05 · **Status:** Specification, ready for implementation
> **Implements:** DD-12 (one IRI user = one CloudLift tenant), **DD-22** (edge collections pre-provisioned per tenant), DD-10 (graph is an async projection)
> **Plan ref:** `PLAN_Interview_Rejection_Intelligence_2026-09-04.md` S0.2
> Written without GPU access; the executable provisioning code is delegated separately.

---

## 1. Why this exists

In `local`, ArangoDB creates a collection on first write. **Azure does not.** The S0.4 spike proved it: `upsert_edge(edge_collection="iri_spike", ...)` resolved to a Cosmos container `t_<tenant>_iri_spike` that did not exist, and returned a flat **404** rather than auto-creating.

So the set of edge collections cannot be discovered at runtime. It must be **declared**, and a container created per collection per tenant at tenant-creation time. That is provisioning work, not graph-code work, and it belongs here.

---

## 2. The declared edge-collection set (DD-22)

From design §6.3. **This list is the contract.** Writing to an edge collection not on it is a programming error, not a provisioning gap.

| Edge collection | From → To | Purpose |
|---|---|---|
| `EVIDENCED_BY` | Outcome → EvidenceItem | Which transcript or email supports a finding |
| `CLAIMED_IN` | Skill → Engagement | Where a claim was made |
| `REFUTED_BY` | Skill → EvidenceItem | Evidence contradicting a claim |
| `PARTICIPATED_IN` | Person → Outcome | Interviewer/recruiter across processes |
| `APPLIED_TO` | Person → Employer | Application linkage |
| `CO_OCCURS_WITH` | Skill → Skill | Skills appearing together in rejected applications |

Implementation note: this belongs in one module-level constant, e.g. `IRI_EDGE_COLLECTIONS`, imported by both the provisioner and the graph-writing code so they cannot drift. Any write path should assert membership before calling `upsert_edge`.

**Cost consequence — RESOLVED by DD-26.** Six containers per tenant against DD-16's ~100-user ceiling would be **600 Cosmos containers**, each with provisioned throughput. **Azure therefore uses ONE container per tenant, with edge type stored as a property** rather than encoded in the container. 600 → 100.

The six names above remain the logical contract — write paths still assert membership, and `local` ArangoDB may keep six physical collections. Only the Azure *physical* shape collapses. The parity suite compares behaviour, not container topology.

---

## 3. Tenant record schema

Relational, in the IRI Postgres schema. DD-01 keeps relational authoritative; the graph is a rebuildable projection (DD-10).

```sql
CREATE TABLE iri_tenant (
    tenant_id        UUID PRIMARY KEY,
    app_user_id      INTEGER NOT NULL UNIQUE,      -- resume-optimizer users.id (DD-12: 1:1)
    cloudlift_env    TEXT    NOT NULL,             -- 'local' | 'aws' | 'azure' (DD-11)
    status           TEXT    NOT NULL DEFAULT 'provisioning',
                                                   -- provisioning | active | suspended | purging
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    activated_at     TIMESTAMPTZ,
    CONSTRAINT iri_tenant_status_valid
        CHECK (status IN ('provisioning','active','suspended','purging')),
    CONSTRAINT iri_tenant_env_valid
        CHECK (cloudlift_env IN ('local','aws','azure'))
);

-- One row per (tenant, resource) actually provisioned. The provisioner is
-- idempotent BECAUSE of this table: it reconciles desired against recorded.
CREATE TABLE iri_tenant_resource (
    tenant_id        UUID NOT NULL REFERENCES iri_tenant(tenant_id) ON DELETE CASCADE,
    resource_kind    TEXT NOT NULL,                -- 'edge_collection' | 'secret_scope' | 'vector_scope'
    resource_name    TEXT NOT NULL,                -- e.g. 'EVIDENCED_BY'
    provider_ref     TEXT,                         -- provider-side identifier, if any
    provisioned_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, resource_kind, resource_name)
);

CREATE INDEX iri_tenant_resource_by_tenant ON iri_tenant_resource (tenant_id);
```

**`app_user_id` is UNIQUE** — that constraint *is* DD-12. One IRI user maps to exactly one CloudLift tenant, enforced by the database rather than by convention.

**`status` starts at `provisioning`, not `active`.** A tenant whose containers are half-created must not accept evidence. Only the provisioner promotes it to `active`, and only after every declared resource is recorded.

---

## 4. Provisioning sequence

Idempotent and re-runnable. Re-running against a fully provisioned tenant is a no-op that returns success.

1. Insert `iri_tenant` with `status='provisioning'`. A unique-violation on `app_user_id` means the tenant already exists — reconcile, do not error.
2. Bind `explicit_tenant(tenant_id)` for everything that follows. **No provisioning step may run outside a tenant context** — `MissingTenantContextError` is the desired behaviour if one tries.
3. Resolve `IGraphDatabase` via `AdapterResolver(env=CLOUDLIFT_ENV)`.
4. For each name in `IRI_EDGE_COLLECTIONS`, ensure the backing collection exists (§5), then record it in `iri_tenant_resource`.
5. Ensure the secret scope exists for `ISecretStore` (no-op for the local adapter, which creates the user directory on write).
6. Only when every declared resource is recorded, set `status='active'` and `activated_at`.

**Failure leaves the tenant in `provisioning`.** That is correct: partial provisioning must be visibly incomplete rather than silently degraded. Re-running the provisioner is the repair path.

---

## 5. Per-environment behaviour

| Env | Edge collections | Notes |
|---|---|---|
| `local` | ArangoDB creates on first write | Provisioner still **records** each one, so `iri_tenant_resource` is environment-independent and parity comparisons line up |
| `aws` | Depends on the resolved `IGraphDatabase` adapter | Verify behaviour before assuming it matches either sibling — see §7 |
| `azure` | **Must be created explicitly.** One Cosmos container per edge collection, named `t_<tenant-uuid-underscored>_<EDGE>` | Absent container = 404, never auto-create (S0.4 finding F-2) |

**Do not branch on `CLOUDLIFT_ENV` inside the provisioner.** Ask the adapter to ensure the collection and let the adapter be right for its environment. Branching on environment name in application code is the anti-pattern the bridge exists to prevent (design P-1).

**RESOLVED by DD-27: option (b).** `register_collection` is on the contract but absent from `CosmosGremlinAdapter`, so bridge-based provisioning is not available. **CloudLift's Terraform creates the per-tenant graph container; IRI's provisioner verifies it exists and refuses to promote the tenant to `active` if it does not.** Container creation is infrastructure and CloudLift owns the Azure stack definition; Cosmos-specific creation code in IRI would violate P-1.

DD-26 makes this a one-container-per-tenant ask rather than six. Raised with the CloudLift session.

---

## 6. Teardown

Purging a tenant (S6 retention, REQ-593) must cascade:
1. Set `status='purging'` first, so nothing new is accepted mid-purge.
2. Delete evidence and derived rows (relational cascade handles `iri_tenant_resource`).
3. Delete the per-tenant graph containers and vector scope.
4. Delete secrets via `ISecretStore.delete_secret` for every name `list_secrets` returns.
5. Delete the `iri_tenant` row last.

**The purge verification must poll, not assert once** (DD-21): Azure deletes are eventually consistent — a deleted AI Search document still counted for several seconds in the S0.4 spike.

⚠ **Azure PITR does not survive a stack destroy** (design Rev 1.6). Tenant teardown and environment teardown are different operations, and neither implies recoverability of the other.

---

## 7. Open question for implementation

**AWS `IGraphDatabase` collection semantics are unverified.** The S0.4 spike covered `local` and `azure` only. Before implementing step 4, confirm whether the AWS-resolved graph adapter auto-creates like ArangoDB or requires pre-creation like Cosmos Gremlin. Assuming either way is how F-2 was nearly missed in Azure.

---

## 8. What this does NOT cover

Provisioning does not create the evidence tables, the vector index, or the relational IRI schema — those are migrations, shared across tenants, and run once per environment rather than once per tenant.
