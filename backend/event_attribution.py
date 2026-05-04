"""Event Attribution: Track which client/project each journey event came from."""

import json
from models import get_db


def add_event_attribution(user_id: int, source_id: int, client_project_id: int = None, workdir_category: str = None) -> None:
    """Associate a journey event with its source client/project and workdir category.

    Args:
        user_id: User ID
        source_id: journey_sources.id
        client_project_id: client_projects.id (nullable)
        workdir_category: workdir directory classification (reports|tasks|teaching|docs|etc)
    """
    if not source_id:
        return

    with get_db() as conn:
        conn.execute(
            "INSERT INTO event_attribution (user_id, source_id, client_project_id, workdir_category) "
            "VALUES (?, ?, ?, ?) ON CONFLICT(source_id) DO UPDATE SET "
            "client_project_id=excluded.client_project_id, workdir_category=excluded.workdir_category",
            (user_id, source_id, client_project_id, workdir_category)
        )
        conn.commit()


def get_event_attribution(source_id: int) -> dict:
    """Retrieve attribution for a source.

    Returns dict with:
      - source_id
      - client_project_id (nullable)
      - workdir_category (nullable)
    """
    with get_db() as conn:
        row = conn.execute(
            "SELECT source_id, client_project_id, workdir_category FROM event_attribution WHERE source_id = ?",
            (source_id,)
        ).fetchone()

    if row:
        return dict(row)
    return {"source_id": source_id, "client_project_id": None, "workdir_category": None}


def get_events_by_client(user_id: int, client_project_id: int) -> list:
    """Get all journey events attributed to a specific client project.

    Returns list of source_ids
    """
    with get_db() as conn:
        rows = conn.execute(
            "SELECT source_id FROM event_attribution WHERE user_id = ? AND client_project_id = ?",
            (user_id, client_project_id)
        ).fetchall()

    return [row["source_id"] for row in rows]


def get_events_by_category(user_id: int, workdir_category: str) -> list:
    """Get all journey events from a specific workdir category (reports, tasks, etc).

    Returns list of source_ids
    """
    with get_db() as conn:
        rows = conn.execute(
            "SELECT source_id FROM event_attribution WHERE user_id = ? AND workdir_category = ?",
            (user_id, workdir_category)
        ).fetchall()

    return [row["source_id"] for row in rows]


def get_attribution_summary(user_id: int) -> dict:
    """Get summary of attributions by client and category.

    Returns:
      - by_client: {client_id: count}
      - by_category: {category: count}
      - unattributed: count (null client AND null category)
    """
    with get_db() as conn:
        # By client
        client_rows = conn.execute(
            "SELECT client_project_id, COUNT(*) as count FROM event_attribution "
            "WHERE user_id = ? AND client_project_id IS NOT NULL "
            "GROUP BY client_project_id",
            (user_id,)
        ).fetchall()

        # By category
        category_rows = conn.execute(
            "SELECT workdir_category, COUNT(*) as count FROM event_attribution "
            "WHERE user_id = ? AND workdir_category IS NOT NULL "
            "GROUP BY workdir_category",
            (user_id,)
        ).fetchall()

        # Unattributed
        unattr_row = conn.execute(
            "SELECT COUNT(*) as count FROM event_attribution "
            "WHERE user_id = ? AND client_project_id IS NULL AND workdir_category IS NULL",
            (user_id,)
        ).fetchone()

    return {
        "by_client": {str(r["client_project_id"]): r["count"] for r in client_rows},
        "by_category": {r["workdir_category"]: r["count"] for r in category_rows},
        "unattributed": unattr_row["count"] if unattr_row else 0,
    }
