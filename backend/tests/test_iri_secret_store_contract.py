"""Contract acceptance suite for ISecretStore implementations.

One suite, run against every adapter. An adapter that passes this file
satisfies the contract; an adapter that does not, does not — regardless of
what its own unit tests say.

Written BEFORE the AWS and Azure implementations exist, deliberately. The
local adapter should pass today; the others should fail until implemented.
That asymmetry is the point: this file is the target, not a description of
what was built.

Adapters are discovered lazily so that a missing cloud SDK skips that
adapter rather than erroring the whole suite.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from iri.contracts.secret_store import (
    ISecretStore,
    SecretMetadata,
    SecretNotFoundError,
)

# --- adapter fixtures -------------------------------------------------------


def _local_store():
    from cryptography.fernet import Fernet
    from iri.adapters.local.encrypted_file_secret_store import EncryptedFileSecretStore

    os.environ["FERNET_KEY"] = Fernet.generate_key().decode()
    return EncryptedFileSecretStore(store_dir=Path(tempfile.mkdtemp()))


def _aws_store():
    boto3 = pytest.importorskip("boto3")
    moto = pytest.importorskip("moto")
    from iri.adapters.aws.secrets_manager_secret_store import SecretsManagerSecretStore

    mock = moto.mock_aws()
    mock.start()
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
    store = SecretsManagerSecretStore(region="us-east-1", name_prefix="iri-test")
    store._moto_mock = mock  # keep alive for the test's duration
    return store


ADAPTERS = {"local": _local_store, "aws": _aws_store}

# Both adapters are implemented and must pass the full contract. The AWS
# params were xfail while the adapter was a skeleton; that marker is removed
# so a regression fails loudly rather than being absorbed as an expected miss.
_ADAPTER_PARAMS = [pytest.param("local"), pytest.param("aws")]


@pytest.fixture(params=_ADAPTER_PARAMS)
def store(request):
    s = ADAPTERS[request.param]()
    yield s
    mock = getattr(s, "_moto_mock", None)
    if mock is not None:
        mock.stop()


# --- conformance ------------------------------------------------------------


def test_conforms_to_protocol(store):
    assert isinstance(store, ISecretStore)


# --- the missing-vs-empty distinction, the contract's central promise --------


def test_store_then_retrieve_round_trips(store):
    store.store_secret("user10", "krisp_token", "abc123")
    assert store.retrieve_secret("user10", "krisp_token") == "abc123"


def test_stored_empty_string_returns_empty_string(store):
    store.store_secret("user10", "blank", "")
    assert store.retrieve_secret("user10", "blank") == ""


def test_missing_secret_raises_not_found(store):
    with pytest.raises(SecretNotFoundError):
        store.retrieve_secret("user10", "never_stored")


def test_empty_is_distinguishable_from_missing(store):
    """The reason the contract raises instead of returning None."""
    store.store_secret("user10", "blank", "")
    assert store.retrieve_secret("user10", "blank") == ""
    with pytest.raises(SecretNotFoundError):
        store.retrieve_secret("user10", "absent")


# --- overwrite semantics ----------------------------------------------------


def test_store_overwrites_value(store):
    store.store_secret("user10", "tok", "first")
    store.store_secret("user10", "tok", "second")
    assert store.retrieve_secret("user10", "tok") == "second"


def test_refresh_preserves_created_at_and_advances_changed_at(store):
    """A token refresh must not look like a brand-new secret."""
    store.store_secret("user10", "tok", "first")
    before = store.get_secret_metadata("user10", "tok")
    store.store_secret("user10", "tok", "second")
    after = store.get_secret_metadata("user10", "tok")
    assert after.created_at == before.created_at, "created_at must be preserved"
    assert after.last_changed_at >= before.last_changed_at


def test_metadata_shape(store):
    store.store_secret("user10", "tok", "v")
    md = store.get_secret_metadata("user10", "tok")
    assert isinstance(md, SecretMetadata)
    assert md.name == "tok"


def test_metadata_missing_raises_not_found(store):
    with pytest.raises(SecretNotFoundError):
        store.get_secret_metadata("user10", "absent")


# --- delete -----------------------------------------------------------------


def test_delete_removes(store):
    store.store_secret("user10", "tok", "v")
    store.delete_secret("user10", "tok")
    with pytest.raises(SecretNotFoundError):
        store.retrieve_secret("user10", "tok")


def test_delete_is_idempotent(store):
    store.delete_secret("user10", "was_never_there")  # must not raise


# --- listing ----------------------------------------------------------------


def test_list_returns_original_names(store):
    store.store_secret("user10", "krisp_token", "a")
    store.store_secret("user10", "gmail_refresh", "b")
    assert sorted(store.list_secrets("user10")) == ["gmail_refresh", "krisp_token"]


def test_list_is_empty_for_unknown_user(store):
    assert store.list_secrets("nobody_here") == []


def test_list_never_returns_values(store):
    store.store_secret("user10", "tok", "SUPER-SECRET-VALUE")
    assert "SUPER-SECRET-VALUE" not in "".join(store.list_secrets("user10"))


# --- isolation: the failure this contract most needs to prevent -------------


def test_users_are_isolated(store):
    store.store_secret("user10", "tok", "TEN")
    store.store_secret("user11", "tok", "ELEVEN")
    assert store.retrieve_secret("user10", "tok") == "TEN"
    assert store.retrieve_secret("user11", "tok") == "ELEVEN"


def test_list_does_not_leak_across_users(store):
    store.store_secret("user10", "only_tens", "a")
    store.store_secret("user11", "only_elevens", "b")
    assert store.list_secrets("user10") == ["only_tens"]
    assert store.list_secrets("user11") == ["only_elevens"]


@pytest.mark.parametrize(
    "user_a,name_a,user_b,name_b",
    [
        ("a", "b/c", "a/b", "c"),      # the classic separator collision
        ("a", "b_c", "a_b", "c"),
        ("a", "b-c", "a-b", "c"),
        ("x", "", "", "x"),
    ],
)
def test_identifier_pairs_cannot_collide(store, user_a, name_a, user_b, name_b):
    """Two different (user, name) pairs must never address the same secret.

    A collision means one user reads or overwrites another's credential.
    """
    store.store_secret(user_a, name_a, "VALUE-A")
    store.store_secret(user_b, name_b, "VALUE-B")
    assert store.retrieve_secret(user_a, name_a) == "VALUE-A"
    assert store.retrieve_secret(user_b, name_b) == "VALUE-B"


def test_user_prefix_is_unambiguous(store):
    """user 'a' must not see secrets belonging to user 'ab'."""
    store.store_secret("a", "tok", "SHORT")
    store.store_secret("ab", "tok", "LONGER")
    assert store.list_secrets("a") == ["tok"]
    assert store.retrieve_secret("a", "tok") == "SHORT"
    assert store.retrieve_secret("ab", "tok") == "LONGER"


@pytest.mark.parametrize(
    "hostile",
    ["..", "../..", "../../etc/passwd", "/etc/passwd", "..\\..", "user10/../user11"],
)
def test_hostile_user_ids_cannot_reach_another_user(store, hostile):
    store.store_secret("user10", "tok", "LEGITIMATE")
    try:
        store.store_secret(hostile, "tok", "HOSTILE")
    except Exception:
        pass  # rejecting is acceptable; silently escaping is not
    assert store.retrieve_secret("user10", "tok") == "LEGITIMATE"


# --- round-tripping awkward identifiers ------------------------------------


@pytest.mark.parametrize(
    "secret_name",
    ["with space", "with/slash", "with.dot", "with+plus", "naïve_unicode", "a" * 64],
)
def test_awkward_secret_names_round_trip(store, secret_name):
    store.store_secret("user10", secret_name, "V")
    assert store.retrieve_secret("user10", secret_name) == "V"
    assert secret_name in store.list_secrets("user10")


# --- health -----------------------------------------------------------------


def test_health_check_returns_bool(store):
    assert isinstance(store.health_check(), bool)


# --- leakage ----------------------------------------------------------------


def test_secret_value_never_appears_in_exception_messages(store):
    """A traceback must never carry the credential."""
    store.store_secret("user10", "tok", "LEAKY-VALUE-XYZ")
    try:
        store.retrieve_secret("user10", "does_not_exist")
    except SecretNotFoundError as exc:
        assert "LEAKY-VALUE-XYZ" not in str(exc)
