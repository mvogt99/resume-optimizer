"""The model-access choke point.

Every assertion here is about something the gateway must PREVENT, not something
it must compute. The two that matter most: a PARTIAL redaction blocks the call
rather than degrading it, and every refusal is audited — a blocked call and a
call that never happened must be distinguishable afterwards.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from iri.gateway.gateway import ModelGateway, QuotaExceededError, RedactionRequiredError
from iri.gateway.redactor import NullRedactor, RedactionResult
from iri.gateway.types import DestinationClass, RedactionState

LOCAL = "http://localhost:8021/v1"
REMOTE = "https://api.openai.com/v1"
SENSITIVE = "the candidate interviewed at Employer A"


class Sink:
    def __init__(self):
        self.rows = []

    def __call__(self, record):
        self.rows.append(record)


class StubRedactor:
    def __init__(self, state, text="REDACTED"):
        self.state, self.text = state, text

    def redact(self, text):
        return RedactionResult(
            text=self.text, state=self.state, replacements=1,
            reason=None if self.state is RedactionState.COMPLETE else "detector timed out",
        )


@pytest.fixture
def sent():
    return []


@pytest.fixture
def call(sent):
    def _call(text):
        sent.append(text)
        return "answer"
    return _call


# --- inside the boundary ----------------------------------------------------


def test_local_endpoint_sends_unredacted_text(call, sent):
    """DD-15: the user's own GPU may see unredacted evidence."""
    sink = Sink()
    ModelGateway(NullRedactor(), sink).invoke(uuid4(), LOCAL, "m", SENSITIVE, call)
    assert sent == [SENSITIVE]
    assert sink.rows[-1].destination_class is DestinationClass.INSIDE_BOUNDARY
    assert sink.rows[-1].redaction_state is RedactionState.NOT_REQUIRED


# --- outside the boundary ---------------------------------------------------


def test_remote_endpoint_sends_only_redacted_text(call, sent):
    sink = Sink()
    ModelGateway(StubRedactor(RedactionState.COMPLETE), sink).invoke(
        uuid4(), REMOTE, "m", SENSITIVE, call
    )
    assert sent == ["REDACTED"]
    assert SENSITIVE not in sent


def test_unknown_endpoint_is_redacted(call, sent):
    """Default-deny: an unparseable endpoint must not be treated as local."""
    ModelGateway(StubRedactor(RedactionState.COMPLETE), Sink()).invoke(
        uuid4(), "", "m", SENSITIVE, call
    )
    assert sent == ["REDACTED"]


# --- PARTIAL blocks; it is not a degraded success ---------------------------


@pytest.mark.parametrize("state", [RedactionState.PARTIAL, RedactionState.FAILED])
def test_unsafe_redaction_blocks_the_call(state, call, sent):
    sink = Sink()
    gateway = ModelGateway(StubRedactor(state), sink)
    with pytest.raises(RedactionRequiredError):
        gateway.invoke(uuid4(), REMOTE, "m", SENSITIVE, call)
    assert sent == [], "no model request may be made when redaction is unsafe"
    assert sink.rows[-1].success is False
    assert sink.rows[-1].redaction_state is state


def test_block_message_never_contains_the_prompt(call):
    gateway = ModelGateway(StubRedactor(RedactionState.PARTIAL), Sink())
    with pytest.raises(RedactionRequiredError) as exc:
        gateway.invoke(uuid4(), REMOTE, "m", SENSITIVE, call)
    assert "Employer A" not in str(exc.value)
    assert "candidate" not in str(exc.value)


# --- quota is a control, not a counter --------------------------------------


def test_quota_refuses_before_the_call(call, sent):
    sink = Sink()
    gateway = ModelGateway(NullRedactor(), sink, quota=1)
    tenant = uuid4()
    gateway.invoke(tenant, LOCAL, "m", "a", call)
    with pytest.raises(QuotaExceededError):
        gateway.invoke(tenant, LOCAL, "m", "b", call)
    assert len(sent) == 1, "a refused call must not reach the model"
    assert sink.rows[-1].success is False


def test_quota_is_per_tenant(call):
    gateway = ModelGateway(NullRedactor(), Sink(), quota=1)
    gateway.invoke(uuid4(), LOCAL, "m", "a", call)
    gateway.invoke(uuid4(), LOCAL, "m", "b", call)  # different tenant, must pass


# --- the audit trail is complete --------------------------------------------


def test_model_failure_is_audited_and_reraised():
    sink = Sink()

    def boom(_text):
        raise RuntimeError("model down")

    with pytest.raises(RuntimeError):
        ModelGateway(NullRedactor(), sink).invoke(uuid4(), LOCAL, "m", "x", boom)
    assert sink.rows[-1].success is False


def test_every_record_carries_identity_and_timing(call):
    sink = Sink()
    ModelGateway(NullRedactor(), sink).invoke(uuid4(), LOCAL, "m", "x", call)
    row = sink.rows[-1]
    assert row.call_id and row.latency_ms >= 0
    assert row.timestamp.tzinfo is not None
    assert row.destination_class is not None


def test_no_record_contains_prompt_text(call):
    sink = Sink()
    ModelGateway(StubRedactor(RedactionState.COMPLETE), sink).invoke(
        uuid4(), REMOTE, "m", SENSITIVE, call
    )
    assert all("Employer A" not in str(r) for r in sink.rows)
