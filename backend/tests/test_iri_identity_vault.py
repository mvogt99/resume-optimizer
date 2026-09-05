"""The identity vault: deterministic pseudonymisation, and the outbound scan.

Redaction here is pseudonymisation rather than deletion, so the same person must
map to the same placeholder across documents and sessions — otherwise
cross-document correlation, which is the point of the whole subsystem, becomes
impossible.

`contains_any` is the outbound scan: the last check before text crosses the
trust boundary. Its failure mode is SILENCE — a broken scan reports "clean" for
text full of real names — so it is tested against every casing rather than once.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from iri.adapters.local.encrypted_file_secret_store import EncryptedFileSecretStore
from iri.gateway.identity_vault import IdentityVault


@pytest.fixture
def store(monkeypatch):
    monkeypatch.setenv("FERNET_KEY", Fernet.generate_key().decode())
    return EncryptedFileSecretStore(store_dir=Path(tempfile.mkdtemp()))


@pytest.fixture
def vault(store):
    return IdentityVault(store, "user10")


# --- determinism ------------------------------------------------------------


def test_same_entity_yields_the_same_placeholder(vault):
    assert vault.placeholder_for("Alice", "person") == vault.placeholder_for("Alice", "person")


@pytest.mark.parametrize("variant", ["alice", "ALICE", "  Alice  ", "\tAlice\n"])
def test_normalisation_does_not_create_a_second_identity(vault, variant):
    assert vault.placeholder_for(variant, "person") == vault.placeholder_for("Alice", "person")


def test_distinct_entities_get_distinct_placeholders(vault):
    assert vault.placeholder_for("Alice", "person") != vault.placeholder_for("Bob", "person")


def test_placeholder_survives_a_reload(store):
    first = IdentityVault(store, "user10").placeholder_for("Alice", "person")
    assert IdentityVault(store, "user10").placeholder_for("Alice", "person") == first


# --- the placeholder must not leak the original -----------------------------


def test_placeholder_carries_the_kind_for_readability(vault):
    assert vault.placeholder_for("Alice", "person").startswith("PERSON_")


def test_placeholder_does_not_contain_the_original(vault):
    token = vault.placeholder_for("Alice", "person").split("_", 1)[1]
    assert "alice" not in token.lower()


def test_placeholder_never_falls_back_to_the_real_value(vault):
    """A redaction path that returns the entity on a miss is a leak."""
    assert vault.placeholder_for("Charlie", "person") != "Charlie"


# --- the outbound scan ------------------------------------------------------


@pytest.mark.parametrize(
    "text", ["Alice interviewed me", "ALICE interviewed me", "alice interviewed me"]
)
def test_scan_finds_the_entity_in_any_casing(vault, text):
    vault.placeholder_for("Alice", "person")
    assert vault.contains_any(text) == ["Alice"]


def test_scan_returns_the_original_surface_form_not_the_key(vault):
    vault.placeholder_for("Alice", "person")
    assert vault.contains_any("ALICE was here") == ["Alice"]


def test_scan_reports_every_leaked_entity(vault):
    vault.placeholder_for("Alice", "person")
    vault.placeholder_for("Bob", "person")
    assert sorted(vault.contains_any("Alice met Bob")) == ["Alice", "Bob"]


def test_scan_is_empty_on_clean_text(vault):
    vault.placeholder_for("Alice", "person")
    assert vault.contains_any("nobody identifiable here") == []


def test_scan_works_after_a_reload(store):
    IdentityVault(store, "user10").placeholder_for("Alice", "person")
    assert IdentityVault(store, "user10").contains_any("Alice was here") == ["Alice"]


# --- isolation --------------------------------------------------------------


def test_vaults_are_per_user(store):
    IdentityVault(store, "user10").placeholder_for("Alice", "person")
    assert IdentityVault(store, "user11").known_entities() == []
    assert store.list_secrets("user11") == []


def test_known_entities_returns_original_forms(vault):
    vault.placeholder_for("Alice", "person")
    assert "Alice" in vault.known_entities()


# --- the vault is never eval'd ---------------------------------------------


def test_source_contains_no_eval():
    """The stored value is the most tamper-worthy structure in the system."""
    import iri.gateway.identity_vault as module

    assert "eval(" not in Path(module.__file__).read_text()
