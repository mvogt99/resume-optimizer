import contextlib
import json
import logging
import sqlite3
import threading
import uuid

from db_engine import get_database_url, get_pg_connection, get_pg_connection_raw, is_postgres
from werkzeug.security import check_password_hash, generate_password_hash

DB_PATH = "database.db"


def get_db_connection(db_path: str | None = None):
    """Return a configured database connection.

    When DATABASE_URL points to PostgreSQL, returns a _PgConnWrapper
    (psycopg2-backed, sqlite3-compatible interface).
    Otherwise returns a raw sqlite3 Connection with WAL mode and busy_timeout.
    Caller is responsible for calling conn.close().
    Use get_db() context manager instead when possible.
    """
    if is_postgres():
        return get_pg_connection_raw()

    path = db_path or DB_PATH
    conn = sqlite3.connect(path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


@contextlib.contextmanager
def get_db():
    """Context manager for database connections.

    Uses PostgreSQL when DATABASE_URL is set to a postgresql:// URL;
    otherwise falls back to SQLite using DB_PATH.
    WAL-mode PRAGMAs are only applied for SQLite connections.
    """
    if is_postgres():
        with get_pg_connection() as conn:
            yield conn
        return

    # --- SQLite path (default) ---
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Initialize the database — delegates DDL to models_schema1/models_schema2 submodules."""
    db_url = get_database_url()
    if is_postgres(db_url):
        from db_pg_init import pg_init_db

        pg_init_db(db_url)
        return

    from models_schema1 import _init_schema_part1
    from models_schema2 import (
        _init_schema_final,
        _init_schema_part2,
        _init_schema_part3,
        _run_migrations,
    )

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    cursor = conn.cursor()
    _init_schema_part1(cursor)
    _init_schema_part2(cursor)
    _run_migrations(cursor)
    _init_schema_part3(cursor)
    _init_schema_final(cursor)
    conn.commit()
    conn.close()


_logger = logging.getLogger(__name__)


def log_audit_event(
    user_id, event_type, resource_type=None, resource_id=None, details=None
):
    """Fire-and-forget audit event logger.

    Inserts into audit_events via a daemon thread — caller never blocks.
    Never raises: exceptions are logged at DEBUG level only.
    """
    def _write():
        try:
            with get_db() as conn:
                conn.execute(
                    "INSERT INTO audit_events "
                    "(user_id, event_type, resource_type, resource_id, details_json) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        user_id,
                        event_type,
                        resource_type,
                        resource_id,
                        json.dumps(details) if details else None,
                    ),
                )
                conn.commit()
        except Exception as exc:
            _logger.debug("[C1] audit_events write failed (non-fatal): %s", exc)

    threading.Thread(target=_write, daemon=True).start()


# Initialize database when module is imported
init_db()

# Backward compatibility — existing `from models import X` imports still work
from models_classes import *  # noqa: F401, F403
from models_journey import (  # noqa: F401
    get_latest_watermarks,
    migrate_journey_events_schema,
    save_mining_run,
)

# Run journey schema migrations after helpers are imported
migrate_journey_events_schema()
