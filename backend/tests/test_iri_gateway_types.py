"""Gateway value types and endpoint classification.

The classifier decides whether redaction is mandatory, so its failure mode must
be over-redaction. Most of the cases below are spoofing forms that a substring
check would classify as local — they are the reason the classifier parses the
URL rather than searching it.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from iri.gateway.classifier import classify_endpoint
from iri.gateway.types import (
    DestinationClass,
    ModelCallRecord,
    RedactionState,
    is_redaction_required,
)


def _record(**over):
    base = dict(
        call_id="c1", tenant_id=uuid4(), timestamp=datetime.now(timezone.utc),
        destination_class=DestinationClass.OUTSIDE_BOUNDARY,
        resolved_endpoint="https://example", model_id="m",
        prompt_token_count=1, completion_token_count=2, latency_ms=3,
        success=True, redaction_state=RedactionState.COMPLETE,
    )
    return ModelCallRecord(**{**base, **over})


# --- types ------------------------------------------------------------------


def test_destination_class_has_exactly_three_members():
    assert {d.name for d in DestinationClass} == {
        "INSIDE_BOUNDARY", "OUTSIDE_BOUNDARY", "UNKNOWN"
    }


def test_redaction_state_is_four_valued_not_boolean():
    """A boolean records whether redaction RAN, which passes partial success."""
    assert {r.name for r in RedactionState} == {
        "NOT_REQUIRED", "COMPLETE", "PARTIAL", "FAILED"
    }


def test_call_record_carries_no_prompt_or_completion_text():
    names = {f.name for f in dataclasses.fields(ModelCallRecord)}
    assert not names & {"prompt", "completion", "text", "content", "body", "messages"}


def test_call_record_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        _record().model_id = "other"


def test_tenant_is_a_uuid_not_a_string():
    """String-typed identity is how one tenant's audit trail merges with another's."""
    assert isinstance(_record().tenant_id, UUID)


def test_timestamp_is_timezone_aware():
    assert _record().timestamp.tzinfo is not None


# --- the default-deny rule --------------------------------------------------


@pytest.mark.parametrize(
    "destination,required",
    [
        (DestinationClass.INSIDE_BOUNDARY, False),
        (DestinationClass.OUTSIDE_BOUNDARY, True),
        (DestinationClass.UNKNOWN, True),  # default-deny
    ],
)
def test_redaction_requirement(destination, required):
    assert is_redaction_required(destination) is required


# --- classification ---------------------------------------------------------


@pytest.mark.parametrize(
    "endpoint",
    [
        "localhost:8021",                 # scheme-less
        "http://localhost:8021/v1",
        "HTTP://LOCALHOST:8021",          # case
        "http://localhost./",             # trailing dot
        "http://127.0.0.1:8021",
        "http://[::1]:8021",              # IPv6 loopback
        "http://[::ffff:127.0.0.1]:8021", # IPv4-mapped
    ],
)
def test_loopback_is_inside_the_boundary(endpoint):
    assert classify_endpoint(endpoint) is DestinationClass.INSIDE_BOUNDARY


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://localhost.evil.com/",          # contains "localhost"
        "http://notlocalhost/",                # contains "localhost"
        "http://user@localhost:1@evil.com/",   # userinfo posing as host
        "http://evil.com/?target=localhost",   # "localhost" in the query
        "http://10.0.0.5/",                    # private != this host
        "http://192.168.1.10/",
        "http://172.16.0.1/",
        "http://169.254.169.254/",             # link-local metadata endpoint
        "https://api.openai.com/v1",
        "https://x.openai.azure.com/",
    ],
)
def test_everything_else_is_outside_the_boundary(endpoint):
    assert classify_endpoint(endpoint) is DestinationClass.OUTSIDE_BOUNDARY


@pytest.mark.parametrize("endpoint", ["", "   ", "://", "http://"])
def test_unparseable_is_unknown_and_therefore_redacted(endpoint):
    result = classify_endpoint(endpoint)
    assert result is DestinationClass.UNKNOWN
    assert is_redaction_required(result) is True
