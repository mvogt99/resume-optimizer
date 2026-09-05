"""A fake azure.keyvault.secrets.SecretClient, faithful where it matters.

Written so the Azure adapter can run the shared ISecretStore contract suite
without a live vault. It deliberately models the three Key Vault behaviours
that actually shaped the adapter, because a fake that gets those wrong would
let exactly the bugs we care about pass:

  1. SOFT DELETE. `begin_delete_secret` does not remove the secret, it moves it
     to a deleted state where `get_secret` reports NOT FOUND but the NAME STAYS
     RESERVED. A `set_secret` on a reserved name fails until it is purged. This
     is why the adapter must wait-then-purge, and a fake that simply removed the
     entry would let a soft-delete bug through unnoticed.
  2. EMPTY VALUES ARE REJECTED, which is why every value carries an envelope.
  3. NAME RULES: alphanumerics and hyphen only, 127 characters maximum.

It is a fake, not a mock: no assertions about calls, just behaviour.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from azure.core.exceptions import HttpResponseError, ResourceNotFoundError

_LEGAL_NAME = re.compile(r"^[0-9a-zA-Z-]+$")


class _Properties:
    def __init__(self, name: str, created_on: datetime, updated_on: datetime | None):
        self.name = name
        self.created_on = created_on
        self.updated_on = updated_on


class _Secret:
    def __init__(self, name: str, value: str, props: _Properties):
        self.name = name
        self.value = value
        self.properties = props


class _DeleteOperation:
    def wait(self) -> None:
        return None


class FakeSecretClient:
    """Behavioural stand-in for SecretClient.

    purge_protection=True makes purge return 403, the condition under which the
    adapter must raise BackendError naming purge protection rather than
    UnauthorizedError.
    """

    def __init__(self, purge_protection: bool = False):
        self._live: dict[str, _Secret] = {}
        self._deleted: dict[str, _Secret] = {}  # reserved names
        self.purge_protection = purge_protection
        self._clock = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def _tick(self) -> datetime:
        self._clock += timedelta(seconds=1)
        return self._clock

    # --- the surface the adapter uses -----------------------------------

    def set_secret(self, name: str, value: str):
        if not _LEGAL_NAME.match(name):
            raise HttpResponseError(f"Illegal secret name: {name!r}")
        if len(name) > 127:
            raise HttpResponseError(f"Secret name exceeds 127 characters: {len(name)}")
        if value == "":
            raise HttpResponseError("Secret value must not be empty")
        if name in self._deleted:
            # The name is reserved by soft delete until purged.
            raise HttpResponseError(f"Secret {name!r} is in a deleted state")
        now = self._tick()
        existing = self._live.get(name)
        props = _Properties(
            name,
            created_on=existing.properties.created_on if existing else now,
            updated_on=now if existing else None,
        )
        self._live[name] = _Secret(name, value, props)
        return self._live[name]

    def get_secret(self, name: str):
        if name not in self._live:
            # Covers both never-existed and soft-deleted: Key Vault 404s on both.
            raise ResourceNotFoundError(f"Secret not found: {name}")
        return self._live[name]

    def begin_delete_secret(self, name: str):
        if name not in self._live:
            raise ResourceNotFoundError(f"Secret not found: {name}")
        self._deleted[name] = self._live.pop(name)
        return _DeleteOperation()

    def purge_deleted_secret(self, name: str) -> None:
        if self.purge_protection:
            err = HttpResponseError("Purge is not permitted on this vault")
            err.status_code = 403
            raise err
        if name not in self._deleted:
            raise ResourceNotFoundError(f"Deleted secret not found: {name}")
        del self._deleted[name]

    def list_properties_of_secrets(self):
        # Returned as a plain list: iterable but NOT an iterator, which is the
        # weaker guarantee the adapter must tolerate.
        return [s.properties for s in self._live.values()]
