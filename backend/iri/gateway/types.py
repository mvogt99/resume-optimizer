"""
Value types for the model-access gateway: the single choke point every LLM call in this subsystem passes through.
This file holds only types — no I/O, no logging, no network, no provider SDKs.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

class DestinationClass(Enum):
    """
    Enumerates the possible locations of a model endpoint.
    UNKNOWN is treated exactly as OUTSIDE_BOUNDARY at every decision point.
    A misconfiguration must cause over-redaction, never under-redaction.
    """
    INSIDE_BOUNDARY = "inside_boundary"  # Model running on hardware the user controls; may see unredacted evidence.
    OUTSIDE_BOUNDARY = "outside_boundary"  # Any hosted or third-party endpoint; redaction is mandatory.
    UNKNOWN = "unknown"  # Anything not positively identified as inside.

class RedactionState(Enum):
    """
    Enumerates the possible states of redaction for a model call.
    This is an enum and not a boolean because a boolean records whether redaction *ran*, which catches total failure but silently passes partial success.
    A partially redacted transcript is the more dangerous artifact precisely because it looks correct in a log.
    PARTIAL BLOCKS an outside-boundary call — it is not a warning and not a degraded success.
    """
    NOT_REQUIRED = "not_required"  # Destination is inside the boundary.
    COMPLETE = "complete"  # Every detector ran, every detected span was replaced, the outbound scan was clean.
    PARTIAL = "partial"  # A detector errored, timed out, or returned low confidence on a span.
    FAILED = "failed"  # Redaction could not be attempted.

@dataclass(frozen=True)
class ModelCallRecord:
    """
    Audit record written for every call regardless of destination.
    This record MUST NEVER contain prompt or completion text — counts and identifiers only.
    The destination class field is the artifact that answers "did anything unredacted ever leave this machine?", a question that cannot be reconstructed later if it is not recorded at the time.

    The timestamp must be timezone-aware. A naive datetime is a bug, not a
    default-to-UTC: it compares wrongly against aware values rather than failing.
    """
    call_id: str
    tenant_id: UUID
    timestamp: datetime
    destination_class: DestinationClass
    resolved_endpoint: str
    model_id: str
    prompt_token_count: int
    completion_token_count: int
    latency_ms: int
    success: bool
    redaction_state: RedactionState

def is_redaction_required(destination: DestinationClass) -> bool:
    """
    Returns True for anything that is not INSIDE_BOUNDARY.
    Adding a new DestinationClass member later defaults to requiring redaction rather than skipping it.
    """
    return destination is not DestinationClass.INSIDE_BOUNDARY
