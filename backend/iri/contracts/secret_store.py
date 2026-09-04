"""
This module defines the ISecretStore interface for storing per-user secrets.
Implementations must be safe to call concurrently and must not cache secret values
in module-level state. Azure Key Vault names are globally unique, and soft-delete
reserves a deleted name for a retention period, so a deleted-and-recreated environment
may be unable to reuse a vault name. This is a guideline for whoever provisions the vault.
"""

from __future__ import annotations
from typing import Protocol, runtime_checkable
from dataclasses import dataclass
from datetime import datetime

class SecretStoreError(Exception):
    """Base class for all exceptions raised by the secret store. Implementations should raise only subclasses of this type."""

class SecretNotFoundError(SecretStoreError):
    """Raised when a requested secret is not found in the store. This makes 'the secret is absent' distinguishable from 'the secret is present and its value is the empty string'."""

class UnauthorizedError(SecretStoreError):
    """Raised when the caller is not authorized to act on the named user's secrets. This is the guard against one user's tokens being served to another, which is the failure this contract most needs to prevent."""

class BackendError(SecretStoreError):
    """Raised when the underlying store is unreachable or fails the operation for an infrastructural reason — network failure, service outage, permission misconfiguration at the vault or secrets-manager level. This is distinguished from UnauthorizedError: UnauthorizedError means the caller may not do this, BackendError means the store could not do it."""

@dataclass(frozen=True)
class SecretMetadata:
    """
    Metadata about a stored secret, including its name, creation time, and last change time.
    This dataclass never carries the secret value.
    """
    name: str
    created_at: datetime
    last_changed_at: datetime

@runtime_checkable
class ISecretStore(Protocol):
    def store_secret(self, user_id: str, secret_name: str, secret_value: str) -> None:
        """
        Store a secret value for a user under a name, overwriting any existing value for that same user and name.

        :param user_id: The unique identifier for the user.
        :param secret_name: The name under which the secret is stored.
        :param secret_value: The secret value to store.
        :raises ValueError: If the secret name violates the backend's naming rules.
        :raises UnauthorizedError: If the caller is not authorized to store secrets for the user.
        :raises BackendError: If the backend store is unreachable or fails to store the secret.
        """
        ...

    def retrieve_secret(self, user_id: str, secret_name: str) -> str:
        """
        Retrieve a secret value for a user by name.

        :param user_id: The unique identifier for the user.
        :param secret_name: The name of the secret to retrieve.
        :return: The secret value.
        :raises SecretNotFoundError: If the secret is not found.
        :raises UnauthorizedError: If the caller is not authorized to retrieve secrets for the user.
        :raises BackendError: If the backend store is unreachable or fails to retrieve the secret.
        """
        ...

    def delete_secret(self, user_id: str, secret_name: str) -> None:
        """
        Delete a secret for a user by name. This operation is idempotent.

        :param user_id: The unique identifier for the user.
        :param secret_name: The name of the secret to delete.
        :raises UnauthorizedError: If the caller is not authorized to delete secrets for the user.
        :raises BackendError: If the backend store is unreachable or fails to delete the secret.
        """
        ...

    def list_secrets(self, user_id: str) -> list[str]:
        """
        List the names of secrets held for one user, never the values.

        :param user_id: The unique identifier for the user.
        :return: A list of secret names.
        :raises UnauthorizedError: If the caller is not authorized to list secrets for the user.
        :raises BackendError: If the backend store is unreachable or fails to list the secrets.
        """
        ...

    def get_secret_metadata(self, user_id: str, secret_name: str) -> SecretMetadata:
        """
        Get the metadata for one named secret.

        :param user_id: The unique identifier for the user.
        :param secret_name: The name of the secret to retrieve metadata for.
        :return: Metadata about the secret.
        :raises SecretNotFoundError: If the secret is not found.
        :raises UnauthorizedError: If the caller is not authorized to retrieve metadata for the secret.
        :raises BackendError: If the backend store is unreachable or fails to retrieve the metadata.
        """
        ...

    def health_check(self) -> bool:
        """
        Perform a lightweight health or reachability check for the store itself.

        :return: True if the store is healthy and reachable, False otherwise.
        """
        ...
