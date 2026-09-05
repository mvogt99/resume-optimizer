import contextlib
import json
import logging
import threading
import uuid

from db_engine import get_database_url, get_pg_connection, get_pg_connection_raw, is_postgres
from werkzeug.security import check_password_hash, generate_password_hash

# Retained for backward-compat imports (`from models import DB_PATH`) in code
# that hasn't been touched since the Postgres migration. No longer used by
# any connection path in this module — Postgres (DATABASE_URL) is required.
DB_PATH = "database.db"


def get_db_connection(db_path: str | None = None):
    """Return a _PgConnWrapper (psycopg2-backed) database connection.

    Caller is responsible for calling conn.close().
    Use get_db() context manager instead when possible.
    ``db_path`` is accepted for backward-compat call sites and ignored.
    """
    return get_pg_connection_raw()


@contextlib.contextmanager
def get_db():
    """Context manager yielding a PostgreSQL connection (DATABASE_URL required)."""
    with get_pg_connection() as conn:
        yield conn


def init_db():
    """Initialize the database — delegates DDL to db_pg_init.pg_init_db()."""
    db_url = get_database_url()
    if not is_postgres(db_url):
        raise RuntimeError(
            "DATABASE_URL must be set to a postgresql:// URL — SQLite is no longer "
            "a supported database backend for this app."
        )

    from db_pg_init import pg_init_db

    pg_init_db(db_url)


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
