"""Production-grade claim recording to gateway with Redis outbox pattern.

Implements reliable delivery using Redis as an outbox queue. Claims are persisted
before being sent; failed sends are retried with exponential backoff. If Redis is
unavailable, falls back to SQLite queue.
"""

import json
import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

import httpx

logger = logging.getLogger(__name__)

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000/api/accountability/record-batch")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REQUEST_TIMEOUT = 10  # seconds
MAX_RETRIES = 3
BACKOFF_FACTOR = 2.0  # exponential backoff: 1s, 2s, 4s

# SQLite fallback queue
_SQLITE_QUEUE_PATH = Path(__file__).parent.parent.parent / ".claim_queue.db"


def _ensure_queue_db() -> None:
    """Create SQLite queue table if needed."""
    try:
        conn = sqlite3.connect(str(_SQLITE_QUEUE_PATH), timeout=5)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS claim_outbox (
                id TEXT PRIMARY KEY,
                claim_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                retry_count INTEGER DEFAULT 0,
                created_at REAL NOT NULL,
                last_retry_at REAL
            )
        """
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        logger.warning("[ClaimRecorder] Failed to initialize queue DB: %s", exc)


def build_claim_payload(
    claim_id: str,
    source: str,
    task_type: str,
    user_id: str,
    input_text: str,
    output_text: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build ClaimRecord payload for gateway record-batch endpoint.

    Gateway expects: {"claims": [{"claim": ..., "task_type": ..., ...}], "source": ...}

    Args:
        claim_id: Unique claim identifier (used as job_id)
        source: Source application (e.g., 'resume_optimizer')
        task_type: Task type (e.g., 'resume_tailor')
        user_id: User ID (stored in metadata) — raises ValueError if None
        input_text: Original text/prompt (max 500 chars preserved)
        output_text: Generated output (max 2000 chars preserved)
        metadata: Optional additional fields (job_title, company, etc.)

    Returns:
        Dictionary matching gateway /api/accountability/record-batch schema.

    Raises:
        ValueError: If user_id is None or empty.
    """
    if not user_id:
        raise ValueError("user_id is required for claim recording")

    # Truncate with validation
    claim_text = input_text[:500] if input_text else ""
    evidence_text = output_text[:2000] if output_text else ""

    if not claim_text and not evidence_text:
        logger.warning("[ClaimRecorder] claim_id=%s has no input or output text", claim_id)

    meta = metadata or {}
    meta["user_id"] = user_id
    meta["claim_id"] = claim_id

    return {
        "source": source,
        "claims": [
            {
                "claim": claim_text,
                "task_type": task_type,
                "evidence": evidence_text,
                "gap": meta.get("gap", 0),
                "job_id": claim_id,
                "metadata": json.dumps(meta),
            }
        ],
    }


async def _send_claim(payload: Dict[str, Any]) -> bool:
    """POST claim to gateway. Returns True on success (2xx).

    Args:
        payload: Claim payload from build_claim_payload().

    Returns:
        True if gateway returned 200-202, False otherwise.
    """
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(GATEWAY_URL, json=payload)
            success = response.status_code in (200, 201, 202)
            if not success:
                logger.warning(
                    "[ClaimRecorder] Gateway returned %d: %s",
                    response.status_code,
                    response.text[:200],
                )
            return success
    except httpx.TimeoutException:
        logger.debug("[ClaimRecorder] Gateway timeout (will retry)")
        return False
    except httpx.RequestError as exc:
        logger.debug("[ClaimRecorder] Network error: %s (will retry)", type(exc).__name__)
        return False
    except Exception as exc:
        logger.error("[ClaimRecorder] Unexpected error: %s", exc)
        return False


def _queue_to_sqlite(claim_id: str, payload: Dict[str, Any]) -> None:
    """Append claim to SQLite outbox queue.

    Args:
        claim_id: Claim identifier (for deduplication key).
        payload: Claim payload to queue.
    """
    _ensure_queue_db()
    outbox_id = f"{claim_id}:{uuid4().hex[:8]}"
    try:
        conn = sqlite3.connect(str(_SQLITE_QUEUE_PATH), timeout=5)
        conn.execute(
            """
            INSERT INTO claim_outbox (id, claim_id, payload, created_at)
            VALUES (?, ?, ?, ?)
        """,
            (outbox_id, claim_id, json.dumps(payload), time.time()),
        )
        conn.commit()
        conn.close()
        logger.debug("[ClaimRecorder] Queued claim %s to SQLite", claim_id)
    except Exception as exc:
        logger.error("[ClaimRecorder] Failed to queue to SQLite: %s", exc)


async def record_claim_async(
    claim_id: str,
    source: str,
    task_type: str,
    user_id: str,
    input_text: str,
    output_text: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Record claim to gateway with Redis outbox + SQLite fallback.

    Non-blocking: claim is persisted to Redis immediately, then sent with retries.
    If Redis unavailable, uses SQLite outbox. Callers must not await this for
    critical flow control.

    Args:
        claim_id: Unique claim identifier
        source: Source application
        task_type: Task type
        user_id: User ID (required)
        input_text: Original text
        output_text: Generated output
        metadata: Optional fields

    Raises:
        ValueError: If user_id is None or empty (validation happens in build_claim_payload).
    """
    try:
        payload = build_claim_payload(
            claim_id=claim_id,
            source=source,
            task_type=task_type,
            user_id=user_id,
            input_text=input_text,
            output_text=output_text,
            metadata=metadata,
        )
    except ValueError as exc:
        logger.error("[ClaimRecorder] Invalid claim %s: %s", claim_id, exc)
        return

    # Try to persist and send via Redis first
    try:
        import redis

        r = redis.from_url(REDIS_URL, decode_responses=True)
        queue_key = "claim_outbox"
        r.lpush(queue_key, json.dumps({"claim_id": claim_id, "payload": payload}))
        logger.debug("[ClaimRecorder] Queued claim %s to Redis", claim_id)

        # Send with retries
        for attempt in range(1, MAX_RETRIES + 1):
            success = await _send_claim(payload)
            if success:
                r.lrem(queue_key, 0, json.dumps({"claim_id": claim_id, "payload": payload}))
                logger.info("[ClaimRecorder] Sent claim %s", claim_id)
                return
            if attempt < MAX_RETRIES:
                wait_time = (BACKOFF_FACTOR ** (attempt - 1))
                logger.debug("[ClaimRecorder] Retry %d/%d in %.1fs", attempt, MAX_RETRIES, wait_time)
                await asyncio.sleep(wait_time)
        logger.warning("[ClaimRecorder] Claim %s exhausted retries, remains in Redis queue", claim_id)

    except ImportError:
        logger.debug("[ClaimRecorder] Redis unavailable, using SQLite fallback")
        _queue_to_sqlite(claim_id, payload)
        # Attempt one synchronous send; if it fails, already in queue
        success = await _send_claim(payload)
        if success:
            logger.info("[ClaimRecorder] Sent claim %s (after SQLite queue)", claim_id)
    except Exception as exc:
        logger.error("[ClaimRecorder] Unexpected error in record_claim_async: %s", exc)
        _queue_to_sqlite(claim_id, payload)


async def drain_sqlite_queue() -> None:
    """Process all pending claims in SQLite outbox queue (drain on startup).

    Called during gateway initialization to send any persisted claims
    from prior session.
    """
    if not _SQLITE_QUEUE_PATH.exists():
        return

    try:
        conn = sqlite3.connect(str(_SQLITE_QUEUE_PATH), timeout=5)
        rows = conn.execute(
            "SELECT id, payload, retry_count FROM claim_outbox ORDER BY created_at LIMIT 100"
        ).fetchall()

        for row_id, payload_json, retry_count in rows:
            if retry_count >= MAX_RETRIES:
                conn.execute("DELETE FROM claim_outbox WHERE id = ?", (row_id,))
                logger.warning("[ClaimRecorder] Abandoned claim after max retries: %s", row_id)
                continue

            try:
                payload = json.loads(payload_json)
                success = await _send_claim(payload)
                if success:
                    conn.execute("DELETE FROM claim_outbox WHERE id = ?", (row_id,))
                    logger.info("[ClaimRecorder] Drained claim %s", row_id)
                else:
                    conn.execute(
                        "UPDATE claim_outbox SET retry_count = ?, last_retry_at = ? WHERE id = ?",
                        (retry_count + 1, time.time(), row_id),
                    )
                    logger.debug("[ClaimRecorder] Requeued claim %s after drain attempt", row_id)
            except Exception as exc:
                logger.error("[ClaimRecorder] Error draining claim %s: %s", row_id, exc)
                conn.execute(
                    "UPDATE claim_outbox SET retry_count = ? WHERE id = ?",
                    (retry_count + 1, row_id),
                )

        conn.commit()
        conn.close()
    except Exception as exc:
        logger.error("[ClaimRecorder] drain_sqlite_queue failed: %s", exc)


# Import for async support
import asyncio
