"""Synchronous PersonaForge client for resume-optimizer backend.

Provides fire-and-forget recall/remember/feedback against the PersonaForge
API at http://localhost:8090. All failures are logged and return None —
PersonaForge is never on the critical path.

Usage:
    from personaforge_client import pf_recall, pf_remember, pf_feedback

    context = pf_recall("career_profile", "write a resume summary")
    if context:
        prompt = f"<persona>\\n{context}\\n</persona>\\n\\n{task}"

    pf_remember("career_profile", "STAR bullet resonated well", {"gap": 22})
    pf_feedback("pass", 0.88)
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PF_URL: str = os.environ.get("PF_URL", "http://localhost:8090")
PF_TIMEOUT: float = float(os.environ.get("PF_TIMEOUT", "5.0"))
PF_USER_ID: str = os.environ.get("PF_USER_ID", "resume-optimizer")

CAREER_NAMESPACE: str = "career_profile"

_CACHE_TTL: float = 60.0  # seconds

# ---------------------------------------------------------------------------
# Internal TTL cache: key → (value, timestamp)
# ---------------------------------------------------------------------------

_recall_cache: dict[str, tuple[str | None, float]] = {}


def _make_cache_key(namespace: str, query: str) -> str:
    content = f"{namespace}:{query[:200]}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def pf_recall(namespace: str, query: str) -> str | None:
    """Retrieve compiled persona context from PersonaForge.

    Returns context string if PersonaForge has relevant memories, else None.
    Results are cached for 60s — subsequent calls with the same namespace/query
    within the TTL window return the cached value without an HTTP round-trip.
    Never raises — all errors return None.
    """
    cache_key = _make_cache_key(namespace, query)
    cached = _recall_cache.get(cache_key)
    if cached is not None:
        value, ts = cached
        if (time.monotonic() - ts) < _CACHE_TTL:
            logger.debug("[PersonaForge] Cache hit for namespace=%s", namespace)
            return value

    payload: dict[str, Any] = {
        "user_id": PF_USER_ID,
        "namespace": namespace,
        "query_text": query[:1000],
        "task_type": "reasoning",
        "token_budget": 512,
    }

    try:
        resp = httpx.post(
            f"{PF_URL}/api/v1/mcp/delegate",
            json=payload,
            timeout=PF_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except httpx.ConnectError:
        logger.warning("[PersonaForge] Cannot connect to %s — skipping recall", PF_URL)
        return None
    except httpx.TimeoutException:
        logger.warning("[PersonaForge] Timeout after %.1fs — skipping recall", PF_TIMEOUT)
        return None
    except httpx.HTTPStatusError as exc:
        logger.warning("[PersonaForge] HTTP error on recall: %s", exc)
        return None
    except Exception as exc:
        logger.warning("[PersonaForge] Unexpected recall error: %s", exc)
        return None

    context = (data.get("context") or {}).get("compiled_context") or ""
    value = context.strip() or None
    _recall_cache[cache_key] = (value, time.monotonic())

    if value:
        logger.info("[PersonaForge] Got %d chars of persona context", len(value))
    else:
        logger.debug("[PersonaForge] No relevant context for namespace=%s", namespace)

    return value


def pf_remember(namespace: str, content: str, metadata: dict[str, Any]) -> None:
    """Store a learning/memory in PersonaForge. Fire-and-forget — never raises."""
    payload: dict[str, Any] = {
        "user_id": PF_USER_ID,
        "namespace": namespace,
        "content": content,
        "task_type": "reasoning",
        "confidence": metadata.get("confidence", 0.8),
        "style_tags": metadata.get("style_tags", ["career_output"]),
        "metadata": metadata,
    }

    try:
        resp = httpx.post(
            f"{PF_URL}/api/v1/memory",
            json=payload,
            timeout=PF_TIMEOUT,
        )
        resp.raise_for_status()
        logger.info("[PersonaForge] Stored memory in namespace=%s", namespace)
    except Exception as exc:
        logger.debug("[PersonaForge] pf_remember failed (non-blocking): %s", exc)

    return None


def pf_feedback(outcome: str, confidence: float) -> None:
    """Send FTAL outcome feedback to PersonaForge. Fire-and-forget — never raises."""
    payload: dict[str, Any] = {
        "user_id": PF_USER_ID,
        "outcome": outcome,
        "confidence": confidence,
    }

    try:
        resp = httpx.post(
            f"{PF_URL}/api/v1/feedback/ftal-outcome",
            json=payload,
            timeout=PF_TIMEOUT,
        )
        resp.raise_for_status()
        logger.debug(
            "[PersonaForge] Feedback sent: outcome=%s confidence=%.2f", outcome, confidence
        )
    except Exception as exc:
        logger.debug("[PersonaForge] pf_feedback failed (non-blocking): %s", exc)

    return None
