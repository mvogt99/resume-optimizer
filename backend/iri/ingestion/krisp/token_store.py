from __future__ import annotations
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from iri.contracts.secret_store import ISecretStore, SecretNotFoundError

# The secret name IRI stores Krisp credentials under
SECRET_NAME = "iri_krisp_oauth"

@dataclass(frozen=True)
class KrispTokens:
    """
    This object holds LIVE CREDENTIALS. Never log it, never put it in
    an exception message, and never return it from an API response.
    """
    access_token: str
    refresh_token: str | None
    expires_at: datetime  # timezone-aware UTC
    scopes: tuple[str, ...]

    def __repr__(self) -> str:
        # Redact the token values to avoid logging sensitive information
        return f"KrispTokens(expires_at={self.expires_at}, scopes={self.scopes})"

def needs_refresh(tokens: KrispTokens, now: datetime, skew_seconds: int = 60) -> bool:
    """
    True when the token expires within `skew_seconds` of `now`, not merely when
    it has already expired. The skew prevents a race condition where a token is
    valid when checked but expired when the request lands, producing a 401.
    """
    if now.tzinfo is None or tokens.expires_at.tzinfo is None:
        raise ValueError("Both `now` and `expires_at` must be timezone-aware datetime objects.")
    return tokens.expires_at <= now + timedelta(seconds=skew_seconds)

def expiry_from_expires_in(expires_in: int, now: datetime) -> datetime:
    """
    Convert `expires_in` (a relative number of seconds) to an absolute aware UTC instant.
    Storing the relative value would be wrong the moment it is read back.
    """
    if now.tzinfo is None:
        raise ValueError("`now` must be a timezone-aware datetime object.")
    return now + timedelta(seconds=expires_in)

class KrispTokenStore:
    def __init__(self, secret_store: ISecretStore, user_id: str):
        self.secret_store = secret_store
        self.user_id = user_id

    def save(self, tokens: KrispTokens) -> None:
        """
        Serialise to JSON through ISecretStore. Store the expiry as an ISO-8601
        string and scopes as a list.
        """
        data = {
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "expires_at": tokens.expires_at.isoformat(),
            "scopes": list(tokens.scopes),
        }
        self.secret_store.store_secret(self.user_id, SECRET_NAME, json.dumps(data))

    def load(self) -> KrispTokens | None:
        """
        Return None when nothing is stored — a user who has not connected Krisp
        is a normal state, not an error. Parse the expiry back with
        datetime.fromisoformat and restore scopes as a tuple. If the stored blob
        is unparseable, raise ValueError rather than returning None: corrupt
        credentials and absent credentials need different responses.
        """
        try:
            data = self.secret_store.retrieve_secret(self.user_id, SECRET_NAME)
        except SecretNotFoundError:
            return None

        try:
            parsed_data = json.loads(data)
            return KrispTokens(
                access_token=parsed_data["access_token"],
                refresh_token=parsed_data["refresh_token"],
                expires_at=datetime.fromisoformat(parsed_data["expires_at"]),
                scopes=tuple(parsed_data["scopes"]),
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise ValueError("Stored Krisp tokens are corrupted.") from e

    def clear(self) -> None:
        """
        Idempotent, for disconnect.
        """
        try:
            self.secret_store.delete_secret(self.user_id, SECRET_NAME)
        except SecretNotFoundError:
            pass
