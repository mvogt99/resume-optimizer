"""Tenant provisioning types, and the name that must not drift.

Azure's Cosmos Gremlin returns a flat 404 for a container that does not exist —
the same response as for a container addressed by the wrong name. So a naming
mismatch between IRI's provisioner and CloudLift's adapter is invisible until an
analysis fails in production, and then it looks like missing infrastructure
rather than a wrong string.

test_container_name_agrees_with_the_adapter exists to make that divergence fail
the build instead.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from iri.provisioning.tenant import (
    IRI_EDGE_COLLECTIONS,
    ProvisionedResource,
    ResourceKind,
    TenantRecord,
    TenantStatus,
    azure_graph_container_name,
    can_activate,
    required_resources,
)

TENANT = UUID("cc091cc0-91cc-4091-cc09-1cc091cc091c")


# --- the declared edge set --------------------------------------------------


def test_edge_collections_are_declared_not_discovered():
    """Cosmos 404s rather than auto-creating, so the set cannot be found at runtime."""
    assert IRI_EDGE_COLLECTIONS == frozenset(
        {
            "EVIDENCED_BY", "CLAIMED_IN", "REFUTED_BY",
            "PARTICIPATED_IN", "APPLIED_TO", "CO_OCCURS_WITH",
        }
    )
    assert isinstance(IRI_EDGE_COLLECTIONS, frozenset), "must not be mutable"


# --- the container name -----------------------------------------------------


def test_container_name_has_the_exact_expected_form():
    assert (
        azure_graph_container_name(TENANT)
        == "t_cc091cc0_91cc_4091_cc09_1cc091cc091c_iri"
    )


def test_container_name_replaces_hyphens_rather_than_stripping_them():
    """uuid.hex strips hyphens; that produced a name that 404s silently."""
    name = azure_graph_container_name(TENANT)
    assert "cc091cc091cc" not in name, "hyphens were stripped, not replaced"
    assert name.count("_") == 6


def test_container_name_agrees_with_the_adapter():
    """IRI and CloudLift derive this name independently. Pin them together.

    If CloudLift changes its prefix format, this fails here rather than as a 404
    in Azure that reads as absent infrastructure.
    """
    adapter = pytest.importorskip("cloudlift.bridge.azure.cosmos_gremlin_adapter")
    source = __import__("pathlib").Path(adapter.__file__).read_text()
    assert 't_{str(tenant_id).replace(\'-\', \'_\')}_' in source, (
        "CosmosGremlinAdapter's naming changed — reconcile "
        "azure_graph_container_name with it before this drifts into a 404"
    )
    # The adapter appends the edge collection to that prefix; IRI uses "iri".
    expected = f"t_{str(TENANT).replace('-', '_')}_" + "iri"
    assert azure_graph_container_name(TENANT) == expected


# --- required resources -----------------------------------------------------


def test_azure_requires_the_per_tenant_container():
    resources = required_resources(TENANT, "azure")
    names = {r.name for r in resources if r.kind is ResourceKind.EDGE_COLLECTION}
    assert names == {azure_graph_container_name(TENANT)}


def test_non_azure_uses_the_generic_collection_name():
    for env in ("local", "aws"):
        names = {
            r.name
            for r in required_resources(TENANT, env)
            if r.kind is ResourceKind.EDGE_COLLECTION
        }
        assert names == {"iri_edges"}


@pytest.mark.parametrize("env", ["local", "aws", "azure"])
def test_every_environment_requires_a_secret_scope(env):
    kinds = {r.kind for r in required_resources(TENANT, env)}
    assert ResourceKind.SECRET_SCOPE in kinds


@pytest.mark.parametrize("env", ["local", "aws", "azure"])
def test_provisioned_timestamps_are_timezone_aware(env):
    assert all(r.provisioned_at.tzinfo is not None for r in required_resources(TENANT, env))


# --- activation is gated ----------------------------------------------------


def test_cannot_activate_with_nothing_provisioned():
    assert can_activate(required_resources(TENANT, "azure"), []) is False


def test_cannot_activate_on_partial_provisioning():
    """Partial provisioning must be VISIBLY incomplete, not silently degraded."""
    required = required_resources(TENANT, "azure")
    assert can_activate(required, required[:1]) is False


def test_can_activate_when_everything_is_recorded():
    required = required_resources(TENANT, "azure")
    assert can_activate(required, list(required)) is True


def test_activation_ignores_timestamps():
    required = required_resources(TENANT, "azure")
    stale = [
        dataclasses.replace(r, provisioned_at=datetime(2020, 1, 1, tzinfo=timezone.utc))
        for r in required
    ]
    assert can_activate(required, stale) is True


# --- records ----------------------------------------------------------------


def test_a_tenant_starts_provisioning_never_active():
    record = TenantRecord(
        tenant_id=uuid4(), app_user_id=10, cloudlift_env="local",
        status=TenantStatus.PROVISIONING,
        created_at=datetime.now(timezone.utc), activated_at=None,
    )
    assert record.status is TenantStatus.PROVISIONING
    assert record.activated_at is None


def test_records_are_frozen():
    assert TenantRecord.__dataclass_params__.frozen
    assert ProvisionedResource.__dataclass_params__.frozen
