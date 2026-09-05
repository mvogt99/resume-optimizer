"""Entity redaction: three detectors, because NER alone provably is not enough.

Measured on spaCy en_core_web_sm with the sentence used throughout this file:
it returned ORG "BlueCross BlueShield" (truncated), GPE "Tennessee", GPE
"c@bcbst.com" -- an EMAIL read as a place -- and CARDINAL "555", a fragment of a
phone number. It MISSED the person's name entirely.

That measurement is why structured identifiers are matched by deterministic
regex rather than left to NER, why GPE and CARDINAL are ignored, and why the
identity vault is consulted first: it is the only detector that improves with
use.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from iri.adapters.local.encrypted_file_secret_store import EncryptedFileSecretStore
from iri.gateway.entity_redactor import EntityRedactor, _is_placeholder
from iri.gateway.identity_vault import IdentityVault
from iri.gateway.redactor import IRedactor
from iri.gateway.types import RedactionState

SAMPLE = (
    "Cailin at BlueCross BlueShield of Tennessee emailed me from "
    "c@bcbst.com on 555-123-4567. See https://bcbst.com/x"
)


@pytest.fixture
def vault(monkeypatch):
    monkeypatch.setenv("FERNET_KEY", Fernet.generate_key().decode())
    store = EncryptedFileSecretStore(store_dir=Path(tempfile.mkdtemp()))
    return IdentityVault(store, "user10")


@pytest.fixture
def redactor(vault):
    return EntityRedactor(vault)


def test_satisfies_the_redactor_contract(redactor):
    assert isinstance(redactor, IRedactor)


# --- structured identifiers must never survive ------------------------------


@pytest.mark.parametrize(
    "identifier", ["c@bcbst.com", "555-123-4567", "https://bcbst.com/x"]
)
def test_structured_identifiers_are_always_removed(redactor, identifier):
    """Regex, not NER: spaCy read this email as a place and this phone as a number."""
    assert identifier not in redactor.redact(SAMPLE).text


def test_email_keeps_its_own_kind(redactor):
    """Regression: NER once re-claimed the placeholder and relabelled it EMPLOYER_."""
    assert "EMAIL_" in redactor.redact(SAMPLE).text


# --- the vault improves the redactor over time ------------------------------


def test_a_name_ner_misses_is_caught_once_the_vault_knows_it(redactor, vault):
    assert "Cailin" in redactor.redact(SAMPLE).text, "spaCy misses this name"
    vault.placeholder_for("Cailin", "interviewer")
    assert "Cailin" not in redactor.redact(SAMPLE).text


def test_redaction_is_deterministic(redactor):
    assert redactor.redact(SAMPLE).text == redactor.redact(SAMPLE).text


def test_redacting_twice_is_stable(redactor):
    once = redactor.redact(SAMPLE).text
    assert redactor.redact(once).text == once


# --- placeholders must not be re-processed ----------------------------------


@pytest.mark.parametrize(
    "span,expected",
    [
        ("PERSON_1a2b3c4d", True),
        ("EMAIL_36ff263b", True),
        ("EMPLOYER_4c976003", True),
        ("PERSON_1a2b3c4d and more", False),  # anchored: whole span only
        ("Alice", False),
        ("PERSON_XYZ", False),
    ],
)
def test_placeholder_detection_is_anchored(span, expected):
    assert _is_placeholder(span) is expected


def test_vault_is_not_polluted_with_placeholders(redactor, vault):
    """A polluted vault makes the outbound scan report redacted text as leaking."""
    redactor.redact(SAMPLE)
    assert not [e for e in vault.known_entities() if _is_placeholder(e)]


# --- state reporting --------------------------------------------------------


def test_successful_redaction_reports_complete(redactor):
    result = redactor.redact(SAMPLE)
    assert result.state is RedactionState.COMPLETE
    assert result.reason is None
    assert result.replacements > 0


def test_ner_failure_reports_partial_not_complete(redactor, monkeypatch):
    """A swallowed detector failure would look like success with a silent gap."""
    def boom(_self, _text):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(EntityRedactor, "_replace_named_entities", boom)
    result = redactor.redact(SAMPLE)
    assert result.state is RedactionState.PARTIAL
    assert result.reason


def test_reason_never_contains_the_text(redactor, monkeypatch):
    def boom(_self, _text):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(EntityRedactor, "_replace_named_entities", boom)
    reason = redactor.redact(SAMPLE).reason or ""
    assert "Cailin" not in reason and "bcbst" not in reason
