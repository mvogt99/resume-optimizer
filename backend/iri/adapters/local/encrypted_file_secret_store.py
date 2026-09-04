import os
import json
import base64
import threading
from datetime import datetime, timezone
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken
from iri.contracts.secret_store import (
    ISecretStore,
    SecretMetadata,
    SecretNotFoundError,
    UnauthorizedError,
    BackendError,
)

class EncryptedFileSecretStore:
    def __init__(self, store_dir: Path = None, fernet_key_env: str = "FERNET_KEY"):
        self.store_dir = store_dir or Path.home() / ".local" / "iri" / "secrets"
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.store_dir.chmod(0o700)
        fernet_key = os.getenv(fernet_key_env)
        if not fernet_key:
            raise BackendError("Fernet key not found in environment variable.")
        try:
            self.cipher = Fernet(fernet_key)
        except ValueError:
            raise BackendError("Invalid Fernet key format.")
        self.lock = threading.Lock()

    def _encode_identifier(self, identifier: str) -> str:
        return base64.urlsafe_b64encode(identifier.encode()).decode().rstrip('=')

    def _decode_identifier(self, encoded_identifier: str) -> str:
        return base64.urlsafe_b64decode(encoded_identifier + '==').decode()

    def _get_user_directory(self, user_id: str) -> Path:
        encoded_user_id = self._encode_identifier(user_id)
        user_dir = self.store_dir / encoded_user_id
        if not user_dir.is_relative_to(self.store_dir):
            raise UnauthorizedError("Invalid user ID.")
        return user_dir

    def _get_secret_path(self, user_id: str, secret_name: str) -> Path:
        user_dir = self._get_user_directory(user_id)
        encoded_secret_name = self._encode_identifier(secret_name)
        return user_dir / f"{encoded_secret_name}.enc"

    def store_secret(self, user_id: str, secret_name: str, secret_value: str) -> None:
        with self.lock:
            secret_path = self._get_secret_path(user_id, secret_name)
            user_dir = secret_path.parent
            user_dir.mkdir(parents=True, exist_ok=True)
            created_at = datetime.now(timezone.utc)
            last_changed_at = created_at
            if secret_path.exists():
                with secret_path.open('r') as f:
                    existing_metadata = json.loads(f.readline())
                    created_at = datetime.fromisoformat(existing_metadata['created_at'])
            metadata = SecretMetadata(
                name=secret_name,
                created_at=created_at,
                last_changed_at=last_changed_at,
            )
            encrypted_value = self.cipher.encrypt(secret_value.encode())
            temp_path = secret_path.with_name(f"{secret_path.name}.tmp")
            try:
                with temp_path.open('wb') as f:
                    f.write(json.dumps({'name': metadata.name, 'created_at': metadata.created_at.isoformat(), 'last_changed_at': metadata.last_changed_at.isoformat()}).encode())
                    f.write(b'\n')
                    f.write(encrypted_value)
                    f.flush()
                    os.fsync(f.fileno())
                temp_path.rename(secret_path)
            except Exception:
                temp_path.unlink(missing_ok=True)
                raise BackendError("Failed to store secret.")

    def retrieve_secret(self, user_id: str, secret_name: str) -> str:
        with self.lock:
            secret_path = self._get_secret_path(user_id, secret_name)
            if not secret_path.exists():
                raise SecretNotFoundError(f"Secret '{secret_name}' not found.")
            with secret_path.open('rb') as f:
                f.readline()  # Skip metadata
                encrypted_value = f.read()
            try:
                return self.cipher.decrypt(encrypted_value).decode()
            except InvalidToken:
                raise BackendError("Failed to decrypt secret.")

    def delete_secret(self, user_id: str, secret_name: str) -> None:
        with self.lock:
            secret_path = self._get_secret_path(user_id, secret_name)
            secret_path.unlink(missing_ok=True)

    def list_secrets(self, user_id: str) -> list[str]:
        with self.lock:
            user_dir = self._get_user_directory(user_id)
            if not user_dir.exists():
                return []
            return [self._decode_identifier(p.stem) for p in user_dir.glob('*.enc')]

    def get_secret_metadata(self, user_id: str, secret_name: str) -> SecretMetadata:
        with self.lock:
            secret_path = self._get_secret_path(user_id, secret_name)
            if not secret_path.exists():
                raise SecretNotFoundError(f"Secret '{secret_name}' not found.")
            with secret_path.open('r') as f:
                metadata = json.loads(f.readline())
            return SecretMetadata(
                name=metadata['name'],
                created_at=datetime.fromisoformat(metadata['created_at']),
                last_changed_at=datetime.fromisoformat(metadata['last_changed_at']),
            )

    def health_check(self) -> bool:
        try:
            test_user_id = "health_check_user"
            test_secret_name = "health_check_secret"
            test_secret_value = "test_value"
            self.store_secret(test_user_id, test_secret_name, test_secret_value)
            retrieved_value = self.retrieve_secret(test_user_id, test_secret_name)
            self.delete_secret(test_user_id, test_secret_name)
            return retrieved_value == test_secret_value
        except Exception:
            return False
