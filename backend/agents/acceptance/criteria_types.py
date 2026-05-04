"""Data models for resume agent acceptance verification."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class AcceptanceCriterion:
    """A single testable acceptance criterion for agent output."""

    name: str
    check: Callable[[Any], bool]
    failure_hint: str


@dataclass
class CriteriaFailure:
    """A single failed criterion with its teaching hint."""

    name: str
    hint: str

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "hint": self.hint}


@dataclass
class AcceptanceResult:
    """Full result of running acceptance criteria against agent output."""

    agent_type: str
    passed: bool
    criteria_total: int
    criteria_passed: int
    failures: list[CriteriaFailure] = field(default_factory=list)
    a_score_penalty: int = 0  # 10 per failure, capped at 40

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_type": self.agent_type,
            "passed": self.passed,
            "criteria_total": self.criteria_total,
            "criteria_passed": self.criteria_passed,
            "failures": [f.to_dict() for f in self.failures],
            "a_score_penalty": self.a_score_penalty,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @property
    def failure_summary(self) -> str:
        if not self.failures:
            return ""
        lines = [f"  - {f.name}: {f.hint}" for f in self.failures]
        return "Acceptance failures:\n" + "\n".join(lines)
