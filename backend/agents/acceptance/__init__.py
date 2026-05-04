"""Acceptance verification for resume optimizer agents."""

from .criteria_types import AcceptanceCriterion, AcceptanceResult, CriteriaFailure
from .enforcement import MAX_ATTEMPTS, build_failure_teaching, record_acceptance, should_retry
from .resume_criteria import CRITERIA_REGISTRY
from .resume_verifier import apply_penalty, verify

__all__ = [
    "AcceptanceCriterion",
    "AcceptanceResult",
    "CriteriaFailure",
    "CRITERIA_REGISTRY",
    "MAX_ATTEMPTS",
    "apply_penalty",
    "build_failure_teaching",
    "record_acceptance",
    "should_retry",
    "verify",
]
