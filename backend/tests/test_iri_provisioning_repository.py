"""Tenant provisioning persistence, against real PostgreSQL.

Not SQLite: this app requires Postgres, and the two defects found here were both
Postgres-specific. An INSERT that violates a unique constraint ABORTS the whole
transaction, so the original catch-then-SELECT idempotency could never work —
and that is the path the provisioner takes every time it is re-run.
"""
from __future__ import annotations

import contextlib
import os
import uuid

import pytest

from iri.provisioning.repository import IRI_PROVISIONING_DDL, TenantRepository
from iri.provisioning.tenant import TenantStatus, required_resources

psycopg2 = pytest.importorskip("psycopg2")

DSN = os.environ.get(
    "DATABASE_URL", "postgresql://gateway:gateway_secret@localhost:5433/ro_test"
)


@pytest.fixture
def repo():
    try:
        conn = psycopg2.connect(DSN)
    except Exception:  # pragma: no cover - environment dependent
        pytest.skip("PostgreSQL not reachable")

    @contextlib.contextmanager
    def factory():
        yield conn

    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS iri_tenant_resource CASCADE")
    cur.execute("DROP TABLE IF EXISTS iri_tenant CASCADE")
    for statement in IRI_PROVISIONING_DDL:
        cur.execute(statement)
    conn.commit()
    yield TenantRepository(factory)
    cur.execute("DROP TABLE IF EXISTS iri_tenant_resource CASCADE")
    cur.execute("DROP TABLE IF EXISTS iri_tenant CASCADE")
    conn.commit()
    conn.close()


def _provision_all(repo, tenant):
    for resource in required_resources(tenant.tenant_id, tenant.cloudlift_env):
        repo.record_resource(tenant.tenant_id, resource.kind, resource.name)


# --- creation ---------------------------------------------------------------


def test_a_tenant_is_never_created_active(repo):
    tenant = repo.create_tenant(10, "azure")
    assert tenant.status is TenantStatus.PROVISIONING
    assert tenant.activated_at is None


def test_create_is_idempotent(repo):
    """The provisioner must be safe to re-run; this is the path that re-runs."""
    first = repo.create_tenant(10, "azure")
    assert repo.create_tenant(10, "azure").tenant_id == first.tenant_id


def test_re_creating_does_not_reset_an_active_tenant(repo):
    tenant = repo.create_tenant(10, "azure")
    _provision_all(repo, tenant)
    repo.try_activate(tenant.tenant_id)
    assert repo.create_tenant(10, "azure").status is TenantStatus.ACTIVE


def test_tenant_id_round_trips_hyphenated(repo):
    tenant = repo.create_tenant(10, "local")
    assert "-" in str(repo.get_tenant(tenant.tenant_id).tenant_id)


# --- activation is gated ----------------------------------------------------


def test_cannot_activate_with_nothing_provisioned(repo):
    tenant = repo.create_tenant(10, "azure")
    assert repo.try_activate(tenant.tenant_id) is False


def test_cannot_activate_on_partial_provisioning(repo):
    tenant = repo.create_tenant(10, "azure")
    first = required_resources(tenant.tenant_id, "azure")[0]
    repo.record_resource(tenant.tenant_id, first.kind, first.name)
    assert repo.try_activate(tenant.tenant_id) is False


def test_partial_provisioning_stays_visibly_incomplete(repo):
    """Not a silent degradation: PROVISIONING is repairable by re-running."""
    tenant = repo.create_tenant(10, "azure")
    repo.try_activate(tenant.tenant_id)
    assert repo.get_tenant(tenant.tenant_id).status is TenantStatus.PROVISIONING


def test_activates_once_every_resource_is_recorded(repo):
    tenant = repo.create_tenant(10, "azure")
    _provision_all(repo, tenant)
    assert repo.try_activate(tenant.tenant_id) is True
    assert repo.get_tenant(tenant.tenant_id).status is TenantStatus.ACTIVE


def test_activation_is_safe_to_repeat(repo):
    tenant = repo.create_tenant(10, "azure")
    _provision_all(repo, tenant)
    repo.try_activate(tenant.tenant_id)
    assert repo.try_activate(tenant.tenant_id) is True


def test_unknown_tenant_returns_false_rather_than_raising(repo):
    assert repo.try_activate(uuid.uuid4()) is False


# --- resources --------------------------------------------------------------


def test_recording_a_resource_twice_is_a_no_op(repo):
    tenant = repo.create_tenant(10, "azure")
    required = required_resources(tenant.tenant_id, "azure")
    _provision_all(repo, tenant)
    repo.record_resource(tenant.tenant_id, required[0].kind, required[0].name)
    assert len(repo.recorded_resources(tenant.tenant_id)) == len(required)


def test_resources_carry_their_tenant(repo):
    """can_activate compares on (tenant_id, kind, name); a missing tenant_id
    would never match, stranding the tenant in PROVISIONING forever."""
    tenant = repo.create_tenant(10, "azure")
    _provision_all(repo, tenant)
    assert all(r.tenant_id == tenant.tenant_id for r in repo.recorded_resources(tenant.tenant_id))


def test_resources_are_per_tenant(repo):
    repo.create_tenant(10, "azure")
    assert repo.recorded_resources(uuid.uuid4()) == []


@pytest.mark.parametrize("env", ["local", "aws", "azure"])
def test_each_environment_can_be_provisioned(repo, env):
    tenant = repo.create_tenant(10, env)
    _provision_all(repo, tenant)
    assert repo.try_activate(tenant.tenant_id) is True
