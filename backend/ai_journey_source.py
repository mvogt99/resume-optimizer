"""W6: AI platform metrics as a journey source for JourneyMiner.

Mines agent_runs (acceptance stats, per-agent usage), and the FTAL harness
stats endpoint, then emits structured journey events that represent the user's
evolving competency with AI-assisted career tooling.

Called by JourneyMiner._mine_ai_platform_metrics() as the 7th enrichment source.
"""

from __future__ import annotations

import datetime
import logging
import os
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_HARNESS_STATS_URL = os.environ.get("HARNESS_STATS_URL", "http://localhost:8000/api/harness/stats")

# Minimum agent runs before we emit an adoption event (avoid noise for 1-2 test runs)
_MIN_RUNS_FOR_EVENT = 3


def collect_agent_run_events(user_id: int) -> List[Dict[str, Any]]:
    """Mine agent_runs table and return journey events.

    Each agent type with enough runs gets one adoption event capturing:
    - First and most recent usage date
    - Total runs, pass rate, average FTAL gap
    - Whether acceptance verification is passing
    """
    events: List[Dict[str, Any]] = []
    try:
        from models import get_db

        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT
                    agent_type,
                    COUNT(*) AS total_runs,
                    MIN(created_at) AS first_used,
                    MAX(created_at) AS last_used,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
                    AVG(CASE WHEN ftal_gap IS NOT NULL THEN ftal_gap ELSE NULL END) AS avg_gap,
                    SUM(CASE WHEN acceptance_passed = 1 THEN 1 ELSE 0 END) AS accept_pass,
                    COUNT(acceptance_passed) AS accept_total,
                    AVG(duration_ms) AS avg_duration_ms
                FROM agent_runs
                WHERE user_id = ?
                GROUP BY agent_type
                ORDER BY first_used ASC
                """,
                (user_id,),
            ).fetchall()
    except Exception as exc:
        logger.warning("[AIJourneySource] Failed to query agent_runs: %s", exc)
        return events

    for row in rows:
        total = row["total_runs"] or 0
        if total < _MIN_RUNS_FOR_EVENT:
            continue

        agent_type = row["agent_type"] or "unknown"
        avg_gap = round(row["avg_gap"], 1) if row["avg_gap"] is not None else None
        pass_rate = (
            round(row["accept_pass"] / row["accept_total"] * 100, 1)
            if row["accept_total"]
            else None
        )
        success_rate = (
            round(row["completed"] / total * 100, 1) if total else None
        )
        avg_ms = int(row["avg_duration_ms"]) if row["avg_duration_ms"] else None

        description_parts = [
            f"Used {agent_type.replace('_', ' ').title()} agent {total} times",
        ]
        if avg_gap is not None:
            quality = "high" if avg_gap < 30 else ("medium" if avg_gap < 60 else "low")
            description_parts.append(f"average FTAL gap {avg_gap} ({quality} quality)")
        if pass_rate is not None:
            description_parts.append(f"acceptance pass rate {pass_rate}%")

        events.append(
            {
                "source_type": "ai_platform_agent",
                "category": "ai_tooling",
                "title": f"AI Career Agent: {agent_type.replace('_', ' ').title()} Adoption",
                "description": "; ".join(description_parts) + ".",
                "event_date": str(row["first_used"] or "")[:10],
                "last_active": str(row["last_used"] or "")[:10],
                "metadata": {
                    "agent_type": agent_type,
                    "total_runs": total,
                    "completed_runs": row["completed"],
                    "success_rate_pct": success_rate,
                    "avg_ftal_gap": avg_gap,
                    "acceptance_pass_rate_pct": pass_rate,
                    "avg_duration_ms": avg_ms,
                    "source_system": "resume_optimizer_agent_runs",
                },
            }
        )

    return events


def collect_ftal_harness_events() -> List[Dict[str, Any]]:
    """Probe the gateway harness stats endpoint and emit a summary event.

    Non-blocking — if the harness is offline, returns empty list.
    """
    events: List[Dict[str, Any]] = []
    try:
        import httpx as _http

        resp = _http.get(_HARNESS_STATS_URL, timeout=3)
        if resp.status_code != 200:
            return events
        stats = resp.json()
    except Exception as exc:
        logger.debug("[AIJourneySource] Harness stats unavailable: %s", exc)
        return events

    total = stats.get("total_runs", 0)
    if total < _MIN_RUNS_FOR_EVENT:
        return events

    pass_rate = stats.get("pass_rate_pct") or stats.get("pass_rate")
    avg_gap = stats.get("avg_gap")

    description = f"RTX 5090 FTAL harness processed {total} delegated tasks"
    if pass_rate is not None:
        description += f", {pass_rate}% pass rate (gap < 30)"
    if avg_gap is not None:
        description += f", average gap {avg_gap}"

    events.append(
        {
            "source_type": "ftal_harness_stats",
            "category": "ai_tooling",
            "title": "FTAL Harness: RTX 5090 Delegation Activity",
            "description": description + ".",
            "event_date": datetime.date.today().isoformat(),  # no date in stats; use today
            "metadata": {
                "total_harness_runs": total,
                "pass_rate_pct": pass_rate,
                "avg_gap": avg_gap,
                "source_system": "ftal_harness",
                "raw_stats": stats,
            },
        }
    )
    return events


def collect_all(user_id: int) -> List[Dict[str, Any]]:
    """Collect all AI platform journey events for a user."""
    events = collect_agent_run_events(user_id)
    events += collect_ftal_harness_events()
    return events
