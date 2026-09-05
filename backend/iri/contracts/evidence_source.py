"""
Contracts for evidence sources, representing external SaaS systems that are
reached identically from every environment. These sources vary by USER, not by
cloud, which is why this is a plain contract and NOT a CloudLift bridge adapter.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Protocol, runtime_checkable

class EvidenceKind(Enum):
    TRANSCRIPT = 'TRANSCRIPT'
    EMAIL = 'EMAIL'
    DOCUMENT = 'DOCUMENT'

@dataclass(frozen=True)
class RawEvidence:
    """
    Holds UNREDACTED text and must never be persisted or transmitted without
    passing the redaction gateway first. The `source_id` must be stable across
    fetches: it is what makes ingestion idempotent, and a source that regenerates
    ids on every poll will duplicate everything.
    """
    source_id: str
    kind: EvidenceKind
    occurred_at: datetime
    fetched_at: datetime
    title: str
    body: str
    participants: List[str]
    metadata: Dict[str, str]

@dataclass(frozen=True)
class SourceHealth:
    connected: bool
    reason: Optional[str]
    checked_at: datetime

@dataclass(frozen=True)
class ConnectionState:
    """
    No token is stored here; credentials live in ISecretStore and this object
    carries only the fact of a connection.
    """
    user_id: str
    connected: bool
    cursor: Optional[str]
    expires_at: Optional[datetime]

@runtime_checkable
class IEvidenceSource(Protocol):
    @property
    def name(self) -> str:
        ...

    def authorize_url(self, user_id: str) -> str:
        ...

    def complete_authorization(self, user_id: str, code: str) -> ConnectionState:
        ...

    def refresh(self, user_id: str) -> ConnectionState:
        ...

    def revoke(self, user_id: str) -> None:
        ...

    def health(self, user_id: str) -> SourceHealth:
        ...

    def fetch_since(self, user_id: str, cursor: Optional[str], limit: int) -> tuple[List[RawEvidence], Optional[str]]:
        """
        Return items in a stable order and a NEXT cursor, or None when caught up.
        Idempotent: fetching from the same cursor twice returns the same items.
        Callers deduplicate on source_id, but a source that renumbers defeats that.
        Never raise for an expired credential — report it through `health`, so a
        disconnected source degrades visibly rather than crashing a batch.
        """
        ...
