from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID
from iri.provisioning.tenant import (
    ProvisionedResource, ResourceKind, TenantRecord, TenantStatus,
    can_activate, required_resources,
)


# DDL for provisioning tables
IRI_PROVISIONING_DDL = [
    """
    CREATE TABLE IF NOT EXISTS iri_tenant (
        tenant_id TEXT PRIMARY KEY,
        app_user_id INTEGER NOT NULL UNIQUE,
        cloudlift_env TEXT NOT NULL CHECK (cloudlift_env IN ('local', 'aws', 'azure')),
        status TEXT NOT NULL DEFAULT 'PROVISIONING' CHECK (status IN ('PROVISIONING', 'ACTIVE', 'FAILED', 'DELETED')),
        created_at TIMESTAMP NOT NULL,
        activated_at TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS iri_tenant_resource (
        tenant_id TEXT NOT NULL REFERENCES iri_tenant(tenant_id) ON DELETE CASCADE,
        kind TEXT NOT NULL,
        name TEXT NOT NULL,
        provisioned_at TIMESTAMP NOT NULL,
        PRIMARY KEY (tenant_id, kind, name)
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_iri_tenant_resource_tenant_id ON iri_tenant_resource(tenant_id);
    """
]


class TenantRepository:
    """
    Repository for tenant provisioning operations. This class is constructed with a connection factory
    to allow testing against any DB-API connection. This inversion of control is deliberate.
    """

    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

    def create_tenant(self, app_user_id: int, cloudlift_env: str) -> TenantRecord:
        with self.connection_factory() as conn:
            with conn.cursor() as cursor:
                # Insert the new tenant or do nothing if a tenant with the same app_user_id already exists
                cursor.execute(
                    """
                    INSERT INTO iri_tenant (tenant_id, app_user_id, cloudlift_env, created_at)
                    VALUES (gen_random_uuid(), %s, %s, %s)
                    ON CONFLICT (app_user_id) DO NOTHING;
                    """,
                    (app_user_id, cloudlift_env, datetime.now(timezone.utc))
                )
                # Fetch the tenant record by app_user_id
                cursor.execute(
                    """
                    SELECT tenant_id, app_user_id, cloudlift_env, status, created_at, activated_at
                    FROM iri_tenant
                    WHERE app_user_id = %s;
                    """,
                    (app_user_id,)
                )
                row = cursor.fetchone()
            conn.commit()
            return TenantRecord(
                tenant_id=UUID(row[0]),
                app_user_id=row[1],
                cloudlift_env=row[2],
                status=TenantStatus[row[3]],
                created_at=row[4],
                activated_at=row[5]
            )

    def record_resource(self, tenant_id: UUID, kind: ResourceKind, name: str) -> None:
        with self.connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO iri_tenant_resource (tenant_id, kind, name, provisioned_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (tenant_id, kind, name) DO NOTHING;
                    """,
                    (str(tenant_id), kind.name, name, datetime.now(timezone.utc))
                )
            conn.commit()

    def recorded_resources(self, tenant_id: UUID) -> list[ProvisionedResource]:
        with self.connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT kind, name, provisioned_at
                    FROM iri_tenant_resource
                    WHERE tenant_id = %s;
                    """,
                    (str(tenant_id),)
                )
                rows = cursor.fetchall()
            return [ProvisionedResource(tenant_id=tenant_id, kind=ResourceKind[row[0]], name=row[1], provisioned_at=row[2]) for row in rows]

    def try_activate(self, tenant_id: UUID) -> bool:
        with self.connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT cloudlift_env
                    FROM iri_tenant
                    WHERE tenant_id = %s;
                    """,
                    (str(tenant_id),)
                )
                row = cursor.fetchone()
                if not row:
                    return False

                cloudlift_env = row[0]
                required = required_resources(tenant_id, cloudlift_env)  # Corrected call to required_resources
                recorded = self.recorded_resources(tenant_id)

                if can_activate(required, recorded):
                    cursor.execute(
                        """
                        UPDATE iri_tenant
                        SET status = %s, activated_at = %s
                        WHERE tenant_id = %s;
                        """,
                        (TenantStatus.ACTIVE.name, datetime.now(timezone.utc), str(tenant_id))
                    )
                    conn.commit()
                    return True
                else:
                    conn.commit()
                    return False

    def get_tenant(self, tenant_id: UUID) -> TenantRecord | None:
        with self.connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT tenant_id, app_user_id, cloudlift_env, status, created_at, activated_at
                    FROM iri_tenant
                    WHERE tenant_id = %s;
                    """,
                    (str(tenant_id),)
                )
                row = cursor.fetchone()
                if row:
                    return TenantRecord(
                        tenant_id=UUID(row[0]),
                        app_user_id=row[1],
                        cloudlift_env=row[2],
                        status=TenantStatus[row[3]],
                        created_at=row[4],
                        activated_at=row[5]
                    )
                return None
