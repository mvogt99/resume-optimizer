"""CT-10: Resume effectiveness audit — correlate resume versions with application outcomes.

Scheduled task (daily or on-demand via `/audit`):
  1. Query `app_tracker`: applications submitted, interview callbacks, rejections
  2. Correlate with `resume_versions`: which version used per application
  3. Compute `effectiveness = interview_callbacks / applications_sent` per version
  4. If effectiveness < 10% across 5+ applications → flag version, recommend re-tailoring
  5. Store in `ro_resume_effectiveness` ArangoDB collection

Non-blocking: errors logged at DEBUG, never raised.
"""

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Thresholds
MIN_APPLICATIONS = 5
LOW_EFFECTIVENESS_THRESHOLD = 0.10  # 10% callback rate


async def run_effectiveness_audit(user_id: int) -> Dict[str, Any]:
    """Execute resume effectiveness audit for a user.

    Args:
        user_id: User to audit.

    Returns:
        {
            "audit_timestamp": float,
            "user_id": int,
            "versions_analyzed": int,
            "flagged_versions": [
                {
                    "version_id": str,
                    "effectiveness": float,
                    "applications_sent": int,
                    "callbacks": int,
                    "recommendation": str,
                }
            ],
            "error": str | None,
        }
    """
    try:
        return await _audit_user_resumes(user_id)
    except Exception as exc:
        logger.debug("[CT-10] Effectiveness audit failed: %s", exc)
        return {
            "audit_timestamp": time.time(),
            "user_id": user_id,
            "versions_analyzed": 0,
            "flagged_versions": [],
            "error": str(exc),
        }


async def _audit_user_resumes(user_id: int) -> Dict[str, Any]:
    """Inner audit implementation — application correlation + flagging."""
    from agents.app_tracker import AppTracker

    tracker = AppTracker(user_id)

    # 1. Fetch all applications for the user
    applications = await _get_user_applications(user_id)
    if not applications:
        return {
            "audit_timestamp": time.time(),
            "user_id": user_id,
            "versions_analyzed": 0,
            "flagged_versions": [],
        }

    # 2. Correlate with resume versions
    version_stats = _correlate_with_resume_versions(applications)

    # 3. Compute effectiveness and flag low performers
    flagged = []
    for version_id, stats in version_stats.items():
        if stats["applications"] < MIN_APPLICATIONS:
            continue  # Skip versions with insufficient data

        effectiveness = stats["callbacks"] / stats["applications"]
        if effectiveness < LOW_EFFECTIVENESS_THRESHOLD:
            flagged.append(
                {
                    "version_id": version_id,
                    "effectiveness": round(effectiveness, 4),
                    "applications_sent": stats["applications"],
                    "callbacks": stats["callbacks"],
                    "recommendation": (
                        "Consider re-tailoring: low interview callback rate. "
                        "Review ATS compatibility, keyword density, and format."
                    ),
                }
            )

    # 4. Store results in ArangoDB
    if flagged:
        await _store_audit_results(user_id, flagged)

    return {
        "audit_timestamp": time.time(),
        "user_id": user_id,
        "versions_analyzed": len(version_stats),
        "flagged_versions": flagged,
    }


async def _get_user_applications(user_id: int) -> List[Dict[str, Any]]:
    """Query app_tracker: submitted applications with outcome data."""
    try:
        from models import db_context, ApplicationStage

        with db_context() as db:
            # Query the application tracker pipeline
            # Assumes app_tracker has submitted applications with stage tracking
            query = """
                SELECT id, resume_version_id, stage, feedback
                FROM application_stage
                WHERE user_id = ? AND stage IN ('applied', 'interviewing', 'rejected', 'offer')
            """
            cursor = db.execute(query, (user_id,))
            return [dict(row) for row in cursor.fetchall()]
    except Exception as exc:
        logger.debug("[CT-10] Application fetch failed: %s", exc)
        return []


def _correlate_with_resume_versions(
    applications: List[Dict[str, Any]],
) -> Dict[str, Dict[str, int]]:
    """Correlate applications with resume versions and compute stats.

    Returns:
        {
            "version_id": {
                "applications": int,
                "callbacks": int,  # (interviewing, offer) count
            }
        }
    """
    version_stats: Dict[str, Dict[str, int]] = {}

    for app in applications:
        version_id = app.get("resume_version_id") or "unknown"
        stage = app.get("stage", "").lower()

        if version_id not in version_stats:
            version_stats[version_id] = {"applications": 0, "callbacks": 0}

        version_stats[version_id]["applications"] += 1

        # Callback = interview request or offer
        if stage in ("interviewing", "offer"):
            version_stats[version_id]["callbacks"] += 1

    return version_stats


async def _store_audit_results(
    user_id: int, flagged_versions: List[Dict[str, Any]]
) -> None:
    """Persist audit results to ArangoDB ro_resume_effectiveness collection."""
    try:
        from arango_client import get_graph_client

        arango = get_graph_client()
        doc = {
            "user_id": user_id,
            "audit_timestamp": time.time(),
            "flagged_versions": flagged_versions,
            "collection": "ro_resume_effectiveness",
        }
        arango.insert_or_update("ro_resume_effectiveness", doc)

        logger.info(
            "[CT-10] Audit results stored for user %d (%d flagged versions)",
            user_id,
            len(flagged_versions),
        )
    except Exception as exc:
        logger.debug("[CT-10] ArangoDB store failed (non-blocking): %s", exc)
