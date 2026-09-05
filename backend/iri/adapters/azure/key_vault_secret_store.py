import base64
import os

from iri.contracts.secret_store import (
    ISecretStore,
    SecretMetadata,
    SecretNotFoundError,
    UnauthorizedError,
    BackendError,
    SecretStoreError,
)

# Key Vault rejects an empty secret value, but the contract requires a stored ""
# to round-trip as "" and stay distinguishable from a missing secret. Every value
# is enveloped with this character on write and stripped on read, uniformly, so
# the empty case is not a special branch. Do not remove.
ENVELOPE_CHARACTER = "\x01"


def _azure_exceptions():
    """Return (ResourceNotFoundError, HttpResponseError, ClientAuthenticationError).

    Imported lazily: this module is imported in environments with no Azure SDK,
    so a module-level `from azure.core.exceptions import ...` would make it
    unimportable there. A missing SDK surfaces as BackendError, never ImportError.
    """
    try:
        from azure.core.exceptions import (
            ClientAuthenticationError,
            HttpResponseError,
            ResourceNotFoundError,
        )
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise BackendError(
            "Azure SDK is not installed; install azure-keyvault-secrets and "
            "azure-identity to use the azure ISecretStore adapter."
        ) from exc
    return ResourceNotFoundError, HttpResponseError, ClientAuthenticationError


class KeyVaultSecretStore:
    def __init__(self, vault_url: str | None = None, name_prefix: str | None = None):
        """
        Initialize the KeyVaultSecretStore with an optional vault URL and name prefix.
        """
        self.vault_url = vault_url or os.getenv('AZURE_KEY_VAULT_URL', 'https://default-vault.vault.azure.net/')
        self.name_prefix = name_prefix or os.getenv('AZURE_KEY_VAULT_NAME_PREFIX', 'default-prefix-')
        self._client = None

    def _get_client(self):
        """
        Lazily create and return the SecretClient.
        """
        if self._client is None:
            try:
                from azure.keyvault.secrets import SecretClient
                from azure.identity import DefaultAzureCredential
                credential = DefaultAzureCredential()
                self._client = SecretClient(vault_url=self.vault_url, credential=credential)
            except ImportError:
                raise BackendError("Azure SDK is not installed. Please install azure-keyvault-secrets and azure-identity.")
        return self._client

    def _encode_secret_name(self, user_id: str, secret_name: str) -> str:
        """Encode a (user_id, secret_name) pair into one Key Vault secret name.

        Base32 rather than base64: Key Vault permits ONLY alphanumerics and the
        hyphen, and url-safe base64 emits "_" (illegal) while standard base64
        emits "+", "/" and "=". Base32's alphabet is A-Z2-7, so it is legal, and
        it contains no hyphen -- which is what makes the hyphen safe as the
        separator. It is also uppercase, so Key Vault's case-insensitive lookup
        cannot alias two different encodings onto one name.

        Practical input ceiling: base32 expands 8/5, so roughly 37 characters
        each for user_id and secret_name before the 127-char limit is hit.
        """
        encoded_user_id = base64.b32encode(user_id.encode()).rstrip(b"=").decode()
        encoded_secret_name = base64.b32encode(secret_name.encode()).rstrip(b"=").decode()
        full_name = f"{self.name_prefix}{encoded_user_id}-{encoded_secret_name}"
        if len(full_name) > 127:
            # Never truncate: two secrets truncated to one name alias silently,
            # which presents as a caching bug and is actually data loss.
            raise BackendError(
                f"Encoded secret name would exceed Key Vault's 127-character limit "
                f"({len(full_name)}): user_id is {len(user_id)} chars, "
                f"secret_name is {len(secret_name)} chars."
            )
        return full_name

    def _decode_secret_name(self, encoded_name: str) -> tuple[str, str]:
        """Recover the original (user_id, secret_name). Exact for arbitrary UTF-8."""
        if not encoded_name.startswith(self.name_prefix):
            raise BackendError(
                f"Secret name does not carry this store's prefix: {self.name_prefix}"
            )
        try:
            encoded_user_id, encoded_secret_name = encoded_name[
                len(self.name_prefix):
            ].split("-", 1)
            user_id = base64.b32decode(
                encoded_user_id.ljust((len(encoded_user_id) + 7) // 8 * 8, "="),
                casefold=True,
            ).decode()
            secret_name = base64.b32decode(
                encoded_secret_name.ljust((len(encoded_secret_name) + 7) // 8 * 8, "="),
                casefold=True,
            ).decode()
        except (ValueError, UnicodeDecodeError, base64.binascii.Error) as exc:
            raise BackendError(f"Secret name is not decodable: {encoded_name}") from exc
        return user_id, secret_name

    def user_secret_prefix(self, user_id: str) -> str:
        """Every name for this user starts with this, and no other user's does.

        The trailing separator is load-bearing: without it, prefix("a") would
        also match user "ab".
        """
        encoded_user_id = base64.b32encode(user_id.encode()).rstrip(b"=").decode()
        return f"{self.name_prefix}{encoded_user_id}-"

    def store_secret(self, user_id: str, secret_name: str, secret_value: str) -> None:
        """Store a secret. set_secret both creates and updates, so there is no
        create-or-update branch as there is on AWS.

        The value is enveloped (see ENVELOPE_CHARACTER): Key Vault rejects an
        empty value, but the contract requires "" to be storable.
        """
        try:
            client = self._get_client()
            encoded_name = self._encode_secret_name(user_id, secret_name)
            client.set_secret(encoded_name, ENVELOPE_CHARACTER + secret_value)
        except SecretStoreError:
            raise
        except Exception as exc:
            self._translate_exception(exc)

    def delete_secret(self, user_id: str, secret_name: str) -> None:
        """Delete a secret. Idempotent: deleting an absent secret is not an error.

        Soft-delete alone leaves the name RESERVED, so a later store of the same
        name fails while the deleted version is in retention. The contract
        requires delete-then-store to work, so we wait then purge.
        """
        ResourceNotFoundError, HttpResponseError, ClientAuthenticationError = _azure_exceptions()
        try:
            client = self._get_client()
            encoded_name = self._encode_secret_name(user_id, secret_name)
            try:
                client.begin_delete_secret(encoded_name).wait()
            except ResourceNotFoundError:
                return  # already absent — idempotent
            try:
                client.purge_deleted_secret(encoded_name)
            except ResourceNotFoundError:
                return  # already purged — the delete achieved its goal
            except HttpResponseError as exc:
                if exc.status_code == 403:
                    # Distinct from UnauthorizedError: the caller IS permitted,
                    # the vault's purge protection forbids the operation.
                    raise BackendError(
                        "Purge protection is enabled on this vault and prevents "
                        "deletion. The secret name will stay reserved until the "
                        "soft-delete retention period expires."
                    ) from exc
                self._translate_exception(exc)
        except SecretStoreError:
            raise
        except Exception as exc:
            self._translate_exception(exc)

    def retrieve_secret(self, user_id: str, secret_name: str) -> str:
        """Return the stored secret string with its envelope stripped.

        A stored empty string round-trips as an empty string, which is why every
        value is enveloped: Key Vault rejects an empty value, so each value
        carries a one-character envelope that is stripped on read.
        """
        try:
            client = self._get_client()
            encoded_name = self._encode_secret_name(user_id, secret_name)
            secret = client.get_secret(encoded_name)
            # No soft-delete check belongs here: Key Vault's get_secret does not
            # return soft-deleted secrets, it 404s, which the translator already
            # maps to SecretNotFoundError. SecretProperties has no deleted_on
            # attribute at all -- reading one raises AttributeError on every
            # successful retrieval. Do not reinstate this check.
            value = secret.value
            if not value.startswith(ENVELOPE_CHARACTER):
                # Never include the value itself -- this message reaches logs.
                raise BackendError(
                    f"Stored secret {secret_name!r} lacks the envelope prefix; it "
                    "was probably written by something other than this adapter."
                )
            return value[len(ENVELOPE_CHARACTER):]
        except SecretStoreError:
            raise
        except Exception as exc:
            self._translate_exception(exc)

    def get_secret_metadata(self, user_id: str, secret_name: str) -> SecretMetadata:
        """Return metadata for one secret. Never fetches or exposes the value.

        Timestamps come from Key Vault and are already timezone-aware, so they
        are used as-is: calling .replace(tzinfo=utc) on an aware datetime would
        relabel it rather than convert it.
        """
        try:
            client = self._get_client()
            encoded_name = self._encode_secret_name(user_id, secret_name)
            properties = client.get_secret(encoded_name).properties
            created_at = properties.created_on
            last_changed_at = properties.updated_on or created_at
            return SecretMetadata(
                name=secret_name,
                created_at=created_at,
                last_changed_at=last_changed_at,
            )
        except SecretStoreError:
            raise
        except Exception as exc:
            self._translate_exception(exc)

    def list_secrets(self, user_id: str) -> list[str]:
        """
        List all secret names for a user. Filter client-side on `self.user_secret_prefix(user_id)`.
        Key Vault has no server-side prefix filter, unlike AWS.
        """
        try:
            client = self._get_client()
            prefix = self.user_secret_prefix(user_id)
            secrets = client.list_properties_of_secrets()
            secret_names = []
            for secret in secrets:
                try:
                    if secret.name.startswith(prefix):
                        _, secret_name = self._decode_secret_name(secret.name)
                        secret_names.append(secret_name)
                except BackendError:
                    # Skip undecodable names
                    continue
            return secret_names
        except SecretStoreError:
            raise
        except Exception as exc:
            self._translate_exception(exc)

    def health_check(self) -> bool:
        """Verify the client can reach the vault.

        An EMPTY vault is healthy: yielding no items is still a successful round
        trip. Do not "fix" this by requiring a result. iter() is explicit because
        the pager is only guaranteed iterable, not an iterator -- next() on it
        raises TypeError, which this method would swallow into a false unhealthy.
        """
        try:
            client = self._get_client()
            for _ in iter(client.list_properties_of_secrets()):
                break  # at most one item; this is a cheap health path
            return True
        except Exception:
            return False

    def _translate_exception(self, exc):
        """
        Translate Azure SDK exceptions into contract exceptions.
        """
        ResourceNotFoundError, HttpResponseError, ClientAuthenticationError = _azure_exceptions()
        if isinstance(exc, ResourceNotFoundError):
            raise SecretNotFoundError(f"Secret not found: {exc}")
        elif isinstance(exc, ClientAuthenticationError) or (isinstance(exc, HttpResponseError) and exc.status_code == 403):
            raise UnauthorizedError(f"Unauthorized access: {exc}")
        else:
            raise BackendError(f"Backend error: {exc}")

