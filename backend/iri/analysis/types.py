"""
Shared result types for the IRI analysis engine.

These are pure declarations used by every analyser. They exist to make one
guarantee structural rather than conventional: a finding that cannot point at
its evidence is an assertion, not a finding, and the type system should refuse
to represent it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Tuple


class ConfidenceLevel(Enum):
    """
    Three levels is the right granularity. Finer scales invite false precision:
    a model cannot reliably distinguish 0.7 from 0.8 confidence, and presenting
    it as though it can misleads the reader.
    """
    HIGH = 'high'
    MEDIUM = 'medium'
    LOW = 'low'


@dataclass(frozen=True)
class Citation:
    """
    Locates evidence by MEETING IDENTIFIER, TURN INDEX and TIMESTAMP.

    Deliberately NOT by line number. The same meeting fetched live and fetched
    from the archive carries different line numbering, so a line-based citation
    silently drifts and ends up pointing at the wrong speaker. A confidently
    wrong citation is worse than none: it gets checked once, looks plausible,
    and is trusted thereafter.

    `quote` carries the exact span the finding rests on so that the quote can
    be checked against the cited turn -- which is what makes a model-produced
    citation verifiable rather than merely decorative.
    """
    meeting_id: str
    turn_index: int
    timestamp: str
    quote: str

    def __post_init__(self) -> None:
        if self.turn_index < 0:
            raise ValueError("turn_index must be non-negative")
        if not self.quote:
            raise ValueError("quote must not be empty")


@dataclass(frozen=True)
class Finding:
    """
    A single analytical claim and the evidence under it.

    `citations` is a tuple rather than a list because a frozen dataclass whose
    field is mutable is only shallowly frozen, and a finding whose evidence can
    be edited after construction defeats the point of freezing it.
    """
    claim: str
    citations: Tuple[Citation, ...]
    confidence: ConfidenceLevel
    category: str

    def __post_init__(self) -> None:
        if not self.citations:
            raise ValueError("citations must not be empty: a finding without evidence is an assertion")


class AnalysisOutcome(Enum):
    """
    The three outcomes an analyser run can have, kept explicitly distinct.

    INSUFFICIENT_EVIDENCE is a legitimate, expected answer -- the analyser ran
    correctly and the evidence genuinely supports nothing -- and must never be
    confusable with ANALYSIS_FAILED, where the run itself did not complete.
    """
    FINDINGS_PRODUCED = 'findings_produced'
    INSUFFICIENT_EVIDENCE = 'insufficient_evidence'
    ANALYSIS_FAILED = 'analysis_failed'


@dataclass(frozen=True)
class AnalysisResult:
    """
    An analyser's whole result.

    The outcome is an explicit enum rather than something inferred from whether
    `findings` is empty, because an empty collection would have to mean both
    "found nothing" and "failed" -- the precise ambiguity this type exists to
    prevent. __post_init__ enforces the correspondence in BOTH directions so an
    inconsistent result cannot be constructed at all.
    """
    analyser_name: str
    meeting_id: str
    outcome: AnalysisOutcome
    findings: Tuple[Finding, ...] = field(default_factory=tuple)
    reason: str = ''

    def __post_init__(self) -> None:
        if self.outcome is AnalysisOutcome.FINDINGS_PRODUCED:
            if not self.findings:
                raise ValueError("findings must not be empty when outcome is FINDINGS_PRODUCED")
        else:
            # The reverse direction matters as much as the forward one: a result
            # reporting INSUFFICIENT_EVIDENCE while carrying findings would be
            # read one way by a caller checking the outcome and the other way by
            # a caller iterating the findings.
            if self.findings:
                raise ValueError(
                    f"findings must be empty when outcome is {self.outcome.name}"
                )
            if not self.reason:
                raise ValueError(f"reason is required when outcome is {self.outcome.name}")

    @property
    def has_findings(self) -> bool:
        return self.outcome is AnalysisOutcome.FINDINGS_PRODUCED

    @property
    def is_insufficient_evidence(self) -> bool:
        return self.outcome is AnalysisOutcome.INSUFFICIENT_EVIDENCE

    @property
    def has_failed(self) -> bool:
        return self.outcome is AnalysisOutcome.ANALYSIS_FAILED
