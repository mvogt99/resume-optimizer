import json
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database.db")


def dedup_client_projects(conn):
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT client_name, GROUP_CONCAT(id ORDER BY id DESC) as ids
        FROM client_projects
        GROUP BY client_name
        HAVING COUNT(*) > 1
    """
    )
    results = cursor.fetchall()
    deletions = {}
    for client_name, ids in results:
        id_list = list(map(int, ids.split(",")))
        kept_id = id_list[0]
        deleted_ids = id_list[1:]
        deletions[client_name] = {"kept_id": kept_id, "deleted_ids": deleted_ids}
        for delete_id in deleted_ids:
            cursor.execute("DELETE FROM client_projects WHERE id = ?", (delete_id,))
    return deletions


def clean_journey_events(conn):
    cursor = conn.cursor()
    cursor.execute(
        """
        DELETE FROM journey_events
        WHERE LOWER(title) LIKE "session%"
           OR LOWER(title) LIKE "archive%"
           OR LOWER(title) IN (
               "---", "..", "teaching", "learnings",
               "notes", "todo", "misc", "summary"
           )
           OR LENGTH(title) < 5
    """
    )
    deleted_count = cursor.rowcount
    return {"deleted_count": deleted_count}


def insert_milestone_events(conn):
    cursor = conn.cursor()
    milestones = [
        (
            "FTAL-Governed Career Intelligence",
            "Implemented FTAL harness workflow governing all AI-generated career content"
            " — quality gates, gap scoring, teaching doc generation on failure",
        ),
        (
            "PersonaForge Career Memory Integration",
            "Integrated PersonaForge semantic memory into resume optimization pipeline"
            " — persistent career context across sessions",
        ),
        (
            "10,475-Event Career Knowledge Graph",
            "Built and validated ArangoDB career knowledge graph with 10,475 events"
            " — technologies, clients, milestones, narratives all connected",
        ),
        (
            "Six-Agent Career Intelligence System",
            "Deployed 6-agent career intelligence system running on local RTX 5090 at zero cost",
        ),
    ]
    inserted = []
    skipped = []
    for title, description in milestones:
        cursor.execute(
            "SELECT id FROM journey_events WHERE title = ? AND event_date = ?",
            (title, "2026-03-27"),
        )
        if cursor.fetchone() is None:
            cursor.execute(
                """INSERT INTO journey_events
                   (user_id, category, event_date, title, description,
                    source_ids, technologies, metrics, confidence)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (1, "achievement", "2026-03-27", title, description, "[]", "[]", "{}", 1.0),
            )
            inserted.append(title)
        else:
            skipped.append(title)
    return {"inserted": inserted, "skipped": skipped}


def run_migration(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    try:
        dedup_clients = dedup_client_projects(conn)
        cleaned_events = clean_journey_events(conn)
        inserted_milestones = insert_milestone_events(conn)
        conn.commit()
    finally:
        conn.close()
    return {
        "dedup_clients": dedup_clients,
        "cleaned_events": cleaned_events,
        "inserted_milestones": inserted_milestones,
    }


if __name__ == "__main__":
    print(json.dumps(run_migration(), indent=2))
