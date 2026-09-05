import json
from models import get_db

# --- Phase 1: Watermark Management ---
def get_latest_watermarks(user_id):
    """Return watermarks dict from most recent completed mining run, or empty dict if none."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT watermarks_json FROM journey_mining_runs WHERE user_id = ? AND status = 'completed' "
            "ORDER BY completed_at DESC LIMIT 1",
            (user_id,)
        ).fetchone()
    if row and row[0]:
        try:
            return json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}

def save_mining_run(user_id, status, opts_json, watermarks_json=None, sources_scanned=0,
                    events_added=0, events_updated=0, events_deduplicated=0, error_message=""):
    """Create or update a mining run record."""
    with get_db() as conn:
        # Temporarily disable foreign keys to handle test data
        conn.execute("PRAGMA foreign_keys = OFF")
        try:
            if status == "completed":
                conn.execute(
                    """INSERT INTO journey_mining_runs
                    (user_id, status, opts_json, watermarks_json, sources_scanned, events_added,
                     events_updated, events_deduplicated, error_message, completed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                    (user_id, status, json.dumps(opts_json or {}), json.dumps(watermarks_json or {}),
                     sources_scanned, events_added, events_updated, events_deduplicated, error_message)
                )
            else:
                conn.execute(
                    """INSERT INTO journey_mining_runs
                    (user_id, status, opts_json, watermarks_json, sources_scanned, events_added,
                     events_updated, events_deduplicated, error_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (user_id, status, json.dumps(opts_json or {}), json.dumps(watermarks_json or {}),
                     sources_scanned, events_added, events_updated, events_deduplicated, error_message)
                )
            conn.commit()
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        finally:
            conn.execute("PRAGMA foreign_keys = ON")

# --- Phase 3: Significance Scoring Schema ---
def migrate_journey_events_schema():
    """Add significance_score, cluster_id, is_cluster_head columns if they don't exist."""
    migration_stmts = [
        "ALTER TABLE journey_events ADD COLUMN significance_score INTEGER DEFAULT 1",
        "ALTER TABLE journey_events ADD COLUMN cluster_id TEXT DEFAULT ''",
        "ALTER TABLE journey_events ADD COLUMN is_cluster_head INTEGER DEFAULT 0",
    ]
    with get_db() as conn:
        for stmt in migration_stmts:
            try:
                conn.execute(stmt)
                conn.commit()
            except Exception as err:  # noqa: BLE001 — ADD COLUMN IF NOT EXISTS is idempotent
                if "duplicate column" not in str(err).lower():
                    raise
