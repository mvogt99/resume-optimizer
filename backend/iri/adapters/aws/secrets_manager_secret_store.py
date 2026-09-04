from iri.contracts.secret_store import ISecretStore, SecretMetadata, SecretNotFoundError, UnauthorizedError, BackendError
import os


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
        raise NotImplementedError

    def _decode_secret_name(self, secret_name: str) -> tuple[str, str]:
        """Decode a Secrets Manager secret name into a user_id and secret_name."""
        raise NotImplementedError

    def user_secret_prefix(self, user_id: str) -> str:
        """Return the name prefix identifying all secrets belonging to one user."""
        raise NotImplementedError

    def retrieve_secret(self, user_id: str, secret_name: str) -> str:
        """Retrieve a secret value by user_id and secret_name."""
        raise NotImplementedError

    def store_secret(self, user_id: str, secret_name: str, secret_value: str) -> None:
        """Set a secret value by user_id and secret_name."""
        raise NotImplementedError

    def get_secret_metadata(self, user_id: str, secret_name: str) -> SecretMetadata:
        """Retrieve metadata for a secret by user_id and secret_name."""
        raise NotImplementedError

    def delete_secret(self, user_id: str, secret_name: str) -> None:
        """Delete a secret by user_id and secret_name."""
        raise NotImplementedError

    def list_secrets(self, user_id: str) -> list[str]:
        """List all secret names for a given user_id."""
        raise NotImplementedError

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
