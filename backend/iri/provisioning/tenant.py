from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID


class TenantStatus(Enum):
    """A tenant starts at PROVISIONING, never ACTIVE. A tenant whose resources are half-created
    must not accept evidence, and only the provisioner promotes it once every declared resource
    is recorded. Partial provisioning must be VISIBLY incomplete rather than silently degraded."""
    PROVISIONING = "PROVISIONING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    PURGING = "PURGING"


IRI_EDGE_COLLECTIONS = frozenset({
    "EVIDENCED_BY", "CLAIMED_IN", "REFUTED_BY", "PARTICIPATED_IN", "APPLIED_TO", "CO_OCCURS_WITH"
})
# This list IS the contract: Azure's Cosmos Gremlin returns 404 for a collection that does not exist
# rather than creating it, unlike local ArangoDB which creates on demand. So the set cannot be
# discovered at runtime and must be declared. Writing to a collection not on this list is a programming error.


class ResourceKind(Enum):
    EDGE_COLLECTION = "EDGE_COLLECTION"
    SECRET_SCOPE = "SECRET_SCOPE"
    VECTOR_SCOPE = "VECTOR_SCOPE"


@dataclass(frozen=True)
class TenantRecord:
    """app_user_id is UNIQUE and this uniqueness IS the one-user-one-tenant rule, enforced by the database
    rather than by convention."""
    tenant_id: UUID
    app_user_id: int
    cloudlift_env: str
    status: TenantStatus
    created_at: datetime
    activated_at: datetime | None


@dataclass(frozen=True)
class ProvisionedResource:
    tenant_id: UUID
    kind: ResourceKind
    name: str
    provisioned_at: datetime


def azure_graph_container_name(tenant_id: UUID) -> str:
    """The Cosmos container name for one tenant's graph.

    Azure uses ONE container per tenant with the edge type stored as a property,
    not six. Six per tenant against a ~100-user ceiling would be 600 Cosmos
    containers, each carrying provisioned throughput.

    THE EXACT FORM IS LOAD-BEARING. CosmosGremlinAdapter builds the same name
    independently (`f"t_{str(tenant_id).replace('-', '_')}_"` + collection), and
    a mismatch does not raise a configuration error -- Cosmos returns a flat 404,
    identical to the response for a container that was never created. Two
    derivations that can disagree is the defect; the agreement test in
    tests/test_iri_provisioning.py pins them together so a divergence fails the
    build instead of surfacing as a missing container in Azure.

    Note `str(tenant_id)`, not `tenant_id.hex`: hex STRIPS the hyphens rather
    than replacing them, producing a name that is wrong in exactly the way that
    404s silently.
    """
    return f"t_{str(tenant_id).replace('-', '_')}_iri"
def required_resources(tenant_id: UUID, cloudlift_env: str) -> list[ProvisionedResource]:
    """Return the resources that must exist before a tenant may be promoted to ACTIVE, stamped with a timezone-aware
    UTC `provisioned_at`. For every environment this includes one SECRET_SCOPE and one EDGE_COLLECTION. The
    EDGE_COLLECTION name is `azure_graph_container_name(tenant_id)` when cloudlift_env == "azure", and the literal
    "iri_edges" otherwise. Environment-specific naming lives here rather than in the graph code path, because
    provisioning is infrastructure."""
    edge_collection_name = azure_graph_container_name(tenant_id) if cloudlift_env == "azure" else "iri_edges"
    return [
        ProvisionedResource(tenant_id, ResourceKind.SECRET_SCOPE, f"tenant_{tenant_id.hex}_secrets", datetime.now(timezone.utc)),
        ProvisionedResource(tenant_id, ResourceKind.EDGE_COLLECTION, edge_collection_name, datetime.now(timezone.utc))
    ]


def can_activate(required: list[ProvisionedResource], recorded: list[ProvisionedResource]) -> bool:
    """True only if every required resource appears in recorded, compared on (tenant_id, kind, name) and ignoring
    timestamps. A missing resource leaves the tenant in PROVISIONING, which is a visible, repairable state, rather
    than surfacing later as a runtime 404 during analysis."""
    required_set = {(r.tenant_id, r.kind, r.name) for r in required}
    recorded_set = {(r.tenant_id, r.kind, r.name) for r in recorded}
    return required_set.issubset(recorded_set)
