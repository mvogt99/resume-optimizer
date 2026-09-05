from __future__ import annotations
import hashlib
import json
from iri.contracts.secret_store import ISecretStore, SecretNotFoundError

class IdentityVault:
    """
    Redaction is pseudonymisation, not deletion: the same person must map to the
    same placeholder across documents and sessions, or cross-document correlation
    becomes impossible. The vault's contents NEVER leave this process; it is read
    locally only. Never put a real entity in an exception message or log line.
    The placeholder is hash-derived so it cannot leak the original via a prefix,
    suffix, initial or length.
    Pseudonymisation is bounded, not absolute: a placeholder that always co-occurs
    with the same distinctive context can still be re-identified.
    """

    def __init__(self, secret_store: ISecretStore, user_id: str) -> None:
        self.secret_store = secret_store
        self.user_id = user_id
        self.secret_name = "iri_identity_vault"
        self.vault: dict[str, dict[str, str]] = {}
        self._load_vault()

    def _load_vault(self) -> None:
        try:
            vault_data = self.secret_store.retrieve_secret(self.user_id, self.secret_name)
            self.vault = json.loads(vault_data)
        except SecretNotFoundError:
            self.vault = {}

    def _save_vault(self) -> None:
        self.secret_store.store_secret(self.user_id, self.secret_name, json.dumps(self.vault))

    def _normalise(self, entity: str) -> str:
        return entity.strip().lower()

    def placeholder_for(self, entity: str, kind: str) -> str:
        normalised_entity = self._normalise(entity)
        if normalised_entity not in self.vault:
            placeholder = f"{kind.upper()}_{hashlib.sha256(normalised_entity.encode()).hexdigest()[:8]}"
            self.vault[normalised_entity] = {"placeholder": placeholder, "original": entity}
            self._save_vault()
        return self.vault[normalised_entity]["placeholder"]

    def known_entities(self) -> list[str]:
        return [entry["original"] for entry in self.vault.values()]

    def contains_any(self, text: str) -> list[str]:
        """
        Returns the ORIGINAL surface forms present in `text`, matched case-insensitively.
        Returns an empty list when none are present.
        Preserves each original exactly as stored — do not return the normalised key.
        This is the outbound scan and its failure mode is silence.
        """
        found_entities = []
        lower_text = text.lower()
        for normalised, entry in self.vault.items():
            if entry["original"].lower() in lower_text:
                found_entities.append(entry["original"])
        return found_entities

    def placeholder_count(self) -> int:
        return len(self.vault)
