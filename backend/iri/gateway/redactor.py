"""
Redaction interface the gateway depends on, plus a null implementation for the inside-boundary case.
This file defines the contract the real redactor must satisfy and the result type the gateway branches on.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from iri.gateway.types import RedactionState


@dataclass(frozen=True)
class RedactionResult:
    """
    Represents the result of a redaction operation.
    """
    text: str
    state: RedactionState
    replacements: int
    reason: str | None = None

    @property
    def is_safe_to_send(self) -> bool:
        """
        Returns True ONLY for states NOT_REQUIRED and COMPLETE.
        PARTIAL is not a degraded success: a partially redacted transcript is more dangerous than an unredacted one
        precisely because it looks correct in a log.
        """
        return self.state in {RedactionState.NOT_REQUIRED, RedactionState.COMPLETE}


@runtime_checkable
class IRedactor(Protocol):
    """
    Protocol for a redactor. Implementers must:
    - Never raise for detection problems. A detector that errors or times out returns PARTIAL with a reason; exceptions are reserved for programming errors.
    - Fail closed on low confidence: if a span might be sensitive, redact it. A degraded analysis is recoverable, a leaked name is not.
    - Pseudonymisation must be DETERMINISTIC — the same real entity maps to the same placeholder across every document and session, or cross-document correlation becomes impossible.
    """
    def redact(self, text: str) -> RedactionResult:
        ...


class NullRedactor:
    """
    A concrete class implementing IRedactor for the inside-boundary case.
    It returns the text unchanged with state NOT_REQUIRED and zero replacements.
    THIS CLASS PERFORMS NO REDACTION AND IS CORRECT ONLY WHEN THE DESTINATION IS POSITIVELY CLASSIFIED INSIDE_BOUNDARY.
    USING IT FOR ANY OTHER DESTINATION SENDS UNREDACTED EVIDENCE TO A THIRD PARTY.
    THE GATEWAY, NOT THE CALLER, DECIDES WHEN IT APPLIES.
    """
    def redact(self, text: str) -> RedactionResult:
        return RedactionResult(text=text, state=RedactionState.NOT_REQUIRED, replacements=0)
