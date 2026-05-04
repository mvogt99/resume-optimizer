"""Acceptance enforcement: retry budget and teaching text generation.

The enforcement layer sits above the verifier. On acceptance failure it:
1. Builds a teaching message describing what went wrong and why.
2. Optionally enriches that teaching via RTX 5090 (call_direct) for specific
   retry instructions grounded in the actual failed output.
3. Tells the caller whether a retry is warranted.
4. Provides retry context (teaching) to inject into the next attempt's LLM prompt.

The actual re-invocation of the agent method is done by the route handler
(agents_routes.py) — enforcement only decides whether to retry and what to say.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .criteria_types import AcceptanceResult

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 2  # 1 original + 1 retry

# Max tokens for LLM-enriched teaching — keep it short so it doesn't bloat the retry prompt
_LLM_TEACHING_MAX_TOKENS = 300


def should_retry(acceptance: AcceptanceResult, attempt: int) -> bool:
    """Return True if the caller should retry the agent call.

    Retry only when:
    - Acceptance failed
    - We have not yet exhausted MAX_ATTEMPTS
    """
    return not acceptance.passed and attempt < MAX_ATTEMPTS - 1


def _build_rule_based_teaching(
    acceptance: AcceptanceResult, context: dict[str, Any] | None = None
) -> str:
    """Build the static rule-based teaching text. Always available, no LLM required."""
    lines = [
        f"[Acceptance Teaching] {acceptance.agent_type} failed "
        f"{len(acceptance.failures)}/{acceptance.criteria_total} criteria.",
        "",
        "Failed criteria:",
    ]
    for f in acceptance.failures:
        lines.append(f"  [{f.name}]")
        lines.append(f"    {f.hint}")

    lines += [
        "",
        "Remediation guidance:",
        "  - Verify the LLM returned a complete, well-structured JSON response.",
        "  - Confirm all placeholder substitution ran before returning the result.",
        "  - Check that the database write succeeded (version_id / session_id populated).",
        "  - If ats_score is 0, the ATS scorer may have received empty keyword input.",
    ]

    if context:
        ctx_str = ", ".join(f"{k}={v}" for k, v in context.items())
        lines.append(f"\nContext: {ctx_str}")

    return "\n".join(lines)


def _enrich_teaching_with_llm(
    acceptance: AcceptanceResult,
    rule_based: str,
    output: Any,
) -> str | None:
    """Call RTX 5090 (call_direct, port 8021) to generate specific retry instructions.

    Returns enriched teaching string, or None if the call fails or times out.
    Best-effort only — callers must fall back to rule_based on None.
    """
    try:
        from smart_llm import call_direct
    except ImportError:
        return None

    failures_text = "\n".join(
        f"  - {f.name}: {f.hint}" for f in acceptance.failures
    )

    # Truncate the actual output so it fits in a short prompt
    try:
        output_preview = json.dumps(output, default=str)[:600]
    except Exception:
        output_preview = str(output)[:600]

    prompt = (
        "You are a quality control system for an AI career assistant. "
        "An agent produced output that failed acceptance checks. "
        "Write ONLY specific, actionable retry instructions "
        "(maximum 3 bullet points, maximum 80 words total). "
        "Do NOT repeat the problem — state exactly what the model must do differently.\n\n"
        f"Agent: {acceptance.agent_type}\n"
        f"Failed checks:\n{failures_text}\n\n"
        f"Actual output received:\n{output_preview}\n\n"
        "Retry instructions:"
    )

    try:
        enriched = call_direct(prompt, max_tokens=_LLM_TEACHING_MAX_TOKENS, temperature=0.2)
        if enriched and isinstance(enriched, str) and len(enriched.strip()) > 20:
            return enriched.strip()
    except Exception as exc:
        logger.debug("[Enforcement] LLM teaching enrichment failed: %s", exc)

    return None


def build_failure_teaching(
    acceptance: AcceptanceResult,
    context: dict[str, Any] | None = None,
    output: Any = None,
) -> str:
    """Build a teaching string for logging and retry context.

    When ``output`` is provided, attempts to enrich the teaching via RTX 5090
    (call_direct, port 8021) with specific, output-grounded retry instructions.
    Falls back to rule-based teaching if LLM is unavailable or times out.

    Args:
        acceptance: The failed AcceptanceResult.
        context:    Optional dict with extra context (posting_id, user_id, etc.)
        output:     The actual agent output dict, for LLM-grounded enrichment.

    Returns:
        Human-readable teaching string describing failures and corrective actions.
    """
    if acceptance.passed:
        return ""

    rule_based = _build_rule_based_teaching(acceptance, context)

    # Only attempt LLM enrichment when we have actual output to analyze
    if output is not None:
        enriched = _enrich_teaching_with_llm(acceptance, rule_based, output)
        if enriched:
            return (
                f"{rule_based}\n\n"
                f"--- RTX 5090 Targeted Instructions ---\n{enriched}"
            )

    return rule_based


def record_acceptance(
    run_id: str,
    acceptance: AcceptanceResult,
    attempt: int,
    teaching: str,
) -> None:
    """Log acceptance result at structured level for observability.

    Does not write to DB — the route handler updates agent_runs directly.
    """
    status = "PASS" if acceptance.passed else "FAIL"
    logger.info(
        "[Enforcement] run_id=%s agent=%s attempt=%d/%d status=%s "
        "criteria=%d/%d penalty=%d",
        run_id,
        acceptance.agent_type,
        attempt + 1,
        MAX_ATTEMPTS,
        status,
        acceptance.criteria_passed,
        acceptance.criteria_total,
        acceptance.a_score_penalty,
    )
    if teaching:
        logger.debug("[Enforcement] Teaching:\n%s", teaching)
