from iri.contracts.secret_store import ISecretStore, SecretMetadata, SecretNotFoundError, UnauthorizedError, BackendError
import base64
import os

from botocore.exceptions import ClientError


# Every stored value is prefixed with this character. Secrets Manager rejects
# an empty SecretString (min length 1), but the contract requires a stored ""
# to round-trip as "". Enveloping every value keeps one uniform code path, so
# the empty case is not exercised only by the empty test. Do not remove this.
_ENVELOPE = "\x01"


class SecretsManagerSecretStore:
    def __init__(self, region: str | None = None, name_prefix: str | None = None):
        # Default region and name prefix can be set via environment variables or sensible defaults
        self.region = region or os.getenv('AWS_REGION', 'us-east-1')
        self.name_prefix = name_prefix or os.getenv('SECRET_NAME_PREFIX', 'default-prefix')
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client('secretsmanager', region_name=self.region)
            except ImportError:
                raise BackendError("boto3 is not installed. Please install it to use this feature.")
        return self._client

    def _encode_secret_name(self, user_id: str, secret_name: str) -> str:
        """Encode a user_id and secret_name into a single Secrets Manager secret name."""
        encoded_user_id = base64.urlsafe_b64encode(user_id.encode()).rstrip(b'=').decode()
        encoded_secret_name = base64.urlsafe_b64encode(secret_name.encode()).rstrip(b'=').decode()
        # "@" is the separator because it is NOT in the url-safe base64 alphabet,
        # which emits "-" and "_". Using either of those would let an encoded part
        # contain the separator and split inside itself. Verified by fuzzing.
        return f"{self.name_prefix}-{encoded_user_id}@{encoded_secret_name}"

    def _decode_secret_name(self, secret_name: str) -> tuple[str, str]:
        """Decode a Secrets Manager secret name into a user_id and secret_name."""
        if not secret_name.startswith(f"{self.name_prefix}-"):
            raise BackendError("Secret name does not have the expected prefix.")
        encoded_parts = secret_name[len(self.name_prefix) + 1:].split('@', 1)
        if len(encoded_parts) != 2:
            raise BackendError("Secret name does not have the expected format.")
        encoded_user_id, encoded_secret_name = encoded_parts
        user_id = base64.urlsafe_b64decode(
            encoded_user_id + '=' * (-len(encoded_user_id) % 4)
        ).decode()
        secret_name = base64.urlsafe_b64decode(
            encoded_secret_name + '=' * (-len(encoded_secret_name) % 4)
        ).decode()
        return user_id, secret_name

    def user_secret_prefix(self, user_id: str) -> str:
        """Return the name prefix identifying all secrets belonging to one user.

        The trailing separator is load-bearing: without it, prefix("a") would
        also match user "ab".
        """
        encoded_user_id = base64.urlsafe_b64encode(user_id.encode()).rstrip(b'=').decode()
        return f"{self.name_prefix}-{encoded_user_id}@"

    def retrieve_secret(self, user_id: str, secret_name: str) -> str:
        """Return the stored secret string, stripping the envelope.

        Checks SecretString PRESENCE, not truthiness: a stored empty string is a
        legitimate value and must never be mistaken for absence.
        """
        encoded_name = self._encode_secret_name(user_id, secret_name)
        try:
            response = self.client.get_secret_value(SecretId=encoded_name)
        except ClientError as exc:
            raise self._translate_client_error(exc) from exc
        if "SecretString" not in response:
            raise SecretNotFoundError(f"Secret has no string value: {secret_name}")
        stored = response["SecretString"]
        if not stored.startswith(_ENVELOPE):
            raise BackendError(
                "Stored secret is malformed: missing envelope. It was probably "
                "written by something other than this adapter."
            )
        return stored[len(_ENVELOPE):]

    def store_secret(self, user_id: str, secret_name: str, secret_value: str) -> None:
        """Store a secret, creating it or updating it as required.

        The value is enveloped (see _ENVELOPE): Secrets Manager rejects an empty
        SecretString, but the contract requires "" to be storable.
        """
        encoded_name = self._encode_secret_name(user_id, secret_name)
        enveloped = _ENVELOPE + secret_value
        try:
            self.client.create_secret(Name=encoded_name, SecretString=enveloped)
        except self.client.exceptions.ResourceExistsException:
            try:
                self.client.put_secret_value(
                    SecretId=encoded_name, SecretString=enveloped
                )
            except ClientError as exc:
                raise self._translate_client_error(exc) from exc
        except ClientError as exc:
            raise self._translate_client_error(exc) from exc

    def get_secret_metadata(self, user_id: str, secret_name: str) -> SecretMetadata:
        """Return metadata for one secret. Never fetches or exposes the value.

        Timestamps come from Secrets Manager itself rather than being stored in
        the secret, so an overwrite cannot lose the original creation time.
        """
        encoded_name = self._encode_secret_name(user_id, secret_name)
        try:
            response = self.client.describe_secret(SecretId=encoded_name)
        except ClientError as exc:
            raise self._translate_client_error(exc) from exc

        created_at = response.get("CreatedDate")
        # `or` rather than a .get default: the key may be present and null.
        last_changed_at = response.get("LastChangedDate") or created_at
        return SecretMetadata(
            name=secret_name,
            created_at=created_at,
            last_changed_at=last_changed_at,
        )

    def delete_secret(self, user_id: str, secret_name: str) -> None:
        """Delete a secret. Idempotent: deleting an absent secret is not an error.

        ForceDeleteWithoutRecovery is required — Secrets Manager otherwise
        SCHEDULES deletion and keeps the name reserved, so a subsequent store
        of the same secret would fail in a way that looks like corruption.
        """
        encoded_name = self._encode_secret_name(user_id, secret_name)
        try:
            self.client.delete_secret(
                SecretId=encoded_name, ForceDeleteWithoutRecovery=True
            )
        except self.client.exceptions.ResourceNotFoundException:
            return
        except ClientError as exc:
            raise self._translate_client_error(exc) from exc

    def list_secrets(self, user_id: str) -> list[str]:
        """Return this user's original secret names. Never values.

        Paginated: a first-page-only implementation truncates silently once a
        user has enough secrets, and passes small tests while doing so.
        """
        prefix = self.user_secret_prefix(user_id)
        paginator = self.client.get_paginator("list_secrets")
        secret_names: list[str] = []
        try:
            for page in paginator.paginate(
                Filters=[{"Key": "name", "Values": [prefix]}]
            ):
                for secret in page.get("SecretList", []):
                    try:
                        _, original = self._decode_secret_name(secret["Name"])
                    except BackendError:
                        continue  # not ours; one foreign name must not break the listing
                    secret_names.append(original)
        except ClientError as exc:
            raise self._translate_client_error(exc) from exc
        return secret_names

    def health_check(self) -> bool:
        """Verify the client can reach Secrets Manager."""
        try:
            self.client.list_secrets(MaxResults=1)
            return True
        except Exception:
            return False

    def _translate_client_error(self, error) -> Exception:
        """Translate a botocore ClientError into the right contract exception."""
        error_code = error.response['Error']['Code']
        if error_code == 'ResourceNotFoundException':
            return SecretNotFoundError(f"Secret not found: {error}")
        elif error_code in ['AccessDeniedException', 'UnauthorizedOperation']:
            return UnauthorizedError(f"Unauthorized access: {error}")
        else:
            return BackendError(f"Backend error: {error}")
