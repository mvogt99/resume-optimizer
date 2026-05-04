"""Acceptance verification engine for resume optimizer agents.

Runs registered criteria against agent output and returns an AcceptanceResult.
A score penalty of 10 per failure (max 40) is applied to the FTAL a_score
to signal quality degradation to the harness.
"""

from __future__ import annotations

import logging
from typing import Any

from .criteria_types import AcceptanceResult, CriteriaFailure
from .resume_criteria import CRITERIA_REGISTRY

logger = logging.getLogger(__name__)

_PENALTY_PER_FAILURE = 10
_MAX_PENALTY = 40


def verify(agent_type: str, output: Any) -> AcceptanceResult:
    """Run acceptance criteria for an agent's output.

    Args:
        agent_type: One of resume_tailor, cover_letter, interview_coach,
                    career_advisor (or any key in CRITERIA_REGISTRY).
        output:     The dict returned by the agent method.

    Returns:
        AcceptanceResult. If no criteria are registered, returns a passing
        result with zero criteria (graceful no-op for unregistered agents).
    """
    criteria = CRITERIA_REGISTRY.get(agent_type, [])

    if not criteria:
        logger.debug("[Verifier] No criteria registered for agent_type=%s", agent_type)
        return AcceptanceResult(
            agent_type=agent_type,
            passed=True,
            criteria_total=0,
            criteria_passed=0,
        )

    failures: list[CriteriaFailure] = []
    passed_count = 0

    for criterion in criteria:
        try:
            ok = criterion.check(output)
        except Exception as exc:
            logger.warning(
                "[Verifier] Criterion %s raised exception: %s", criterion.name, exc
            )
            ok = False

        if ok:
            passed_count += 1
        else:
            failures.append(CriteriaFailure(name=criterion.name, hint=criterion.failure_hint))

    penalty = min(len(failures) * _PENALTY_PER_FAILURE, _MAX_PENALTY)
    passed = len(failures) == 0

    result = AcceptanceResult(
        agent_type=agent_type,
        passed=passed,
        criteria_total=len(criteria),
        criteria_passed=passed_count,
        failures=failures,
        a_score_penalty=penalty,
    )

    if not passed:
        logger.warning(
            "[Verifier] %s FAILED %d/%d criteria — penalty=%d\n%s",
            agent_type,
            len(failures),
            len(criteria),
            penalty,
            result.failure_summary,
        )
    else:
        logger.debug(
            "[Verifier] %s passed all %d criteria", agent_type, len(criteria)
        )

    return result


def apply_penalty(ftal_scores: dict[str, Any], acceptance: AcceptanceResult) -> dict[str, Any]:
    """Return a copy of ftal_scores with a_score reduced by acceptance penalty.

    Only modifies scores when acceptance failed and a penalty applies.
    """
    if acceptance.passed or acceptance.a_score_penalty == 0:
        return ftal_scores

    scores = dict(ftal_scores)
    current_a = scores.get("a") or 0
    scores["a"] = max(0, current_a - acceptance.a_score_penalty)

    # Recalculate gap: gap = 100 - (f + t + a + l). l defaults to same as a.
    f = scores.get("f") or 0
    t = scores.get("t") or 0
    a = scores["a"]
    # l is not tracked separately in resume-optimizer — approximate as a
    scores["gap"] = max(0, 100 - (f + t + a + a))

    return scores
