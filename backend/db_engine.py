"""Database engine: SQLite (default) and PostgreSQL (via DATABASE_URL).

When DATABASE_URL is not set or starts with 'sqlite:', the app uses its normal
raw sqlite3 path (models.py). When DATABASE_URL starts with 'postgresql://' or
'postgres://', this module returns a PostgreSQL-aware connection wrapper.

Environment variables:
    DATABASE_URL -- SQLAlchemy-compatible URL.
        SQLite example:  sqlite:///./database.db  (or unset — uses models.DB_PATH)
        Postgres example: postgresql://user:pass@localhost:5432/resume_optimizer
"""

import contextlib
import os
import re
from datetime import date, datetime
from typing import Optional, Union

# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

_POSTGRES_SCHEMES = ("postgresql://", "postgres://", "postgresql+psycopg2://")


def get_database_url() -> str | None:
    """Return DATABASE_URL from environment, or None if not set."""
    return os.environ.get("DATABASE_URL") or None


def is_postgres(url: str | None = None) -> bool:
    """Return True if the effective DATABASE_URL points to PostgreSQL."""
    url = url or get_database_url() or ""
    return any(url.startswith(scheme) for scheme in _POSTGRES_SCHEMES)


def is_sqlite(url: str | None = None) -> bool:
    """Return True when using SQLite (default when DATABASE_URL is unset)."""
    return not is_postgres(url)


# ---------------------------------------------------------------------------
# PostgreSQL connection adapter
# ---------------------------------------------------------------------------


def as_datetime(value: Optional[Union[str, datetime, date]]) -> Optional[datetime]:
    """Coerce a database timestamp into a datetime, whatever the driver returned.

    SQLite hands back TIMESTAMP columns as ISO-8601 STRINGS; psycopg2 hands back
    datetime OBJECTS. Code written against SQLite calls datetime.fromisoformat()
    on the value and raises `TypeError: fromisoformat: argument must be str`
    under PostgreSQL. This is a live failure on the PostgreSQL backend, not a
    test artefact.
    """
    if value is None:
        return None
    # datetime is a SUBCLASS of date, so it must be checked FIRST or every
    # datetime would be swallowed by the date branch below.
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        # fromisoformat rejected a trailing "Z" before Python 3.11; do not let
        # behaviour depend on the interpreter version.
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    raise TypeError(f"cannot coerce {type(value).__name__} to datetime")


class _PsycopgRow(dict):
    """Dict subclass that also supports integer-index access (like sqlite3.Row)."""

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _PgCursorWrapper:
    """Wraps a psycopg2 cursor to mimic the sqlite3 cursor interface.

    Key differences handled:
    - ``?`` placeholder → ``%s``
    - ``lastrowid`` populated from RETURNING id
    - ``fetchone`` / ``fetchall`` return ``_PsycopgRow`` dicts
    """

    def __init__(self, cursor):
        self._cur = cursor
        self._last_id = None

    @staticmethod
    def _adapt_sql(sql: str) -> str:
        """Convert SQLite SQL to PostgreSQL-compatible SQL.

        Translations applied:
        - ``?`` placeholders → ``%s``
        - ``INTEGER PRIMARY KEY AUTOINCREMENT`` → ``SERIAL PRIMARY KEY``
          (handles module-level CREATE TABLE DDL not routed through db_pg_init)
        - ``ALTER TABLE t ADD COLUMN c …`` → ``ALTER TABLE t ADD COLUMN IF NOT EXISTS c …``
          (makes column additions idempotent on both PG 9.6+ and SQLite 3.37+)
        - ``last_insert_rowid()`` → ``lastval()``
          (SQLite row-id function → PostgreSQL sequence equivalent)
        - ``julianday(col)`` → ``(EXTRACT(EPOCH FROM col::timestamp) / 86400.0)``
          (SQLite date arithmetic → PostgreSQL equivalent in fractional days)
        """
        sql = re.sub(r"\?", "%s", sql)
        # SQLite AUTOINCREMENT → PostgreSQL SERIAL (DDL compatibility)
        sql = re.sub(
            r"INTEGER\s+(?:NOT\s+NULL\s+)?PRIMARY\s+KEY\s+AUTOINCREMENT",
            "SERIAL PRIMARY KEY",
            sql,
            flags=re.IGNORECASE,
        )
        # ADD COLUMN → ADD COLUMN IF NOT EXISTS (idempotent schema migrations)
        sql = re.sub(
            r"(?i)(ALTER\s+TABLE\s+\S+\s+ADD\s+COLUMN\s+)(?!IF\s+NOT\s+EXISTS\s+)",
            r"\1IF NOT EXISTS ",
            sql,
        )
        # last_insert_rowid() → lastval() (SQLite-specific row-id function)
        sql = re.sub(r"last_insert_rowid\(\)", "lastval()", sql, flags=re.IGNORECASE)
        # julianday(col) → PostgreSQL fractional-day equivalent
        sql = re.sub(
            r"julianday\((\w+)\)",
            r"(EXTRACT(EPOCH FROM \1::timestamp) / 86400.0)",
            sql,
            flags=re.IGNORECASE,
        )
        # PRAGMA table_info(t) → information_schema query returning a `name` column
        # SQLite-only introspection. The result column is aliased to `name` because
        # callers read row["name"], which is what PRAGMA table_info actually returns.
        # Only table_info is rewritten -- PRAGMA journal_mode=WAL and friends pass through.
        def _pragma_table_info(m):
            ident = m.group(2).lower()
            return (
                "SELECT column_name AS name FROM information_schema.columns "
                f"WHERE table_schema = 'public' AND table_name = '{ident}' "
                "ORDER BY ordinal_position"
            )

        sql = re.sub(
            r"""PRAGMA\s+table_info\s*\(\s*(['"`]?)([A-Za-z0-9_]+)\1\s*\)\s*;?\s*$""",
            _pragma_table_info,
            sql,
            flags=re.IGNORECASE,
        )

        # INSERT OR IGNORE INTO → INSERT INTO ... ON CONFLICT DO NOTHING
        # SQLite-only syntax; PostgreSQL rejects it with `syntax error at or near "OR"`.
        # Two steps, not one re.sub: the prefix is rewritten but the conflict clause
        # belongs at the END of the statement. Dropping the clause would turn a silent
        # no-op into a duplicate-key error, which is worse than the syntax error.
        _or_insert = re.search(r"INSERT\s+OR\s+(IGNORE|REPLACE)\s+INTO", sql, flags=re.IGNORECASE)
        if _or_insert:
            _kind = _or_insert.group(1).upper()
            sql = re.sub(
                r"INSERT\s+OR\s+(IGNORE|REPLACE)\s+INTO",
                "INSERT INTO",
                sql,
                count=1,
                flags=re.IGNORECASE,
            )
            if _kind == "IGNORE" and "ON CONFLICT" not in sql.upper():
                sql = sql.rstrip().rstrip(";").rstrip() + " ON CONFLICT DO NOTHING"
            # INSERT OR REPLACE is left as a plain INSERT: a faithful translation needs
            # ON CONFLICT DO UPDATE with the conflict target and the columns to set,
            # which cannot be inferred here. Callers needing true upsert must write it.

        # datetime('now', '-N unit') → (NOW() - INTERVAL 'N unit')
        sql = re.sub(
            r"datetime\('now',\s*'-(\d+)\s+(\w+)'\)",
            r"(NOW() - INTERVAL '\1 \2')",
            sql,
            flags=re.IGNORECASE,
        )
        return sql

    def execute(self, sql: str, params=()):
        adapted = self._adapt_sql(sql)
        # Append RETURNING id for INSERT so lastrowid works
        if adapted.strip().upper().startswith("INSERT") and "RETURNING" not in adapted.upper():
            adapted = adapted.rstrip("; ").rstrip() + " RETURNING id"
            self._cur.execute(adapted, params or ())
            row = self._cur.fetchone()
            if row:
                self._last_id = row[0]
        else:
            self._cur.execute(adapted, params or ())
        return self

    def executemany(self, sql: str, seq):
        self._cur.executemany(self._adapt_sql(sql), seq)
        return self

    @property
    def lastrowid(self):
        return self._last_id

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def description(self):
        return self._cur.description

    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        desc = self._cur.description or []
        return _PsycopgRow(zip([d[0] for d in desc], row))

    def __iter__(self):
        """Yield the remaining rows, because sqlite3 cursors are iterable.

        A great deal of code is written as `for row in conn.execute(...)`, which
        raises TypeError against a non-iterable wrapper -- a live incompatibility
        on the PostgreSQL backend, not just a test problem.

        Lazy on purpose: a result set big enough to matter is exactly the case
        where iteration is used instead of fetchall, so buffering it all first
        would defeat the point. Goes through this wrapper's own fetchone so that
        iterated rows get the same dict-like adaptation as fetched ones.
        """
        while True:
            row = self.fetchone()
            if row is None:
                break
            yield row

    def fetchall(self):
        rows = self._cur.fetchall()
        desc = self._cur.description or []
        cols = [d[0] for d in desc]
        return [_PsycopgRow(zip(cols, row)) for row in rows]


class _PgConnWrapper:
    """Wraps a psycopg2 connection to expose the sqlite3-compatible interface.

    - ``execute(sql, params)`` returns a ``_PgCursorWrapper``
    - ``cursor()`` returns a ``_PgCursorWrapper``
    - ``commit()`` / ``close()`` delegate to the real connection
    - PRAGMA statements are silently ignored (SQLite-only)
    """

    def __init__(self, pg_conn):
        self._conn = pg_conn

    def _is_pragma(self, sql: str) -> bool:
        """True when a PRAGMA should be swallowed as a no-op.

        Swallowing is right only for pragmas with NO PostgreSQL equivalent --
        `journal_mode`, `busy_timeout` and friends are SQLite tuning knobs that
        mean nothing here. `table_info` is EXEMPT because _adapt_sql translates
        it into a real information_schema query; swallowing it returned an empty
        stub cursor that raised "no results to fetch" on iteration.

        If you add a translation for another pragma, exempt it here too, or the
        translation will never run.
        """
        if re.match(r"\s*PRAGMA\s+table_info\s*\(", sql, flags=re.IGNORECASE):
            return False
        return sql.strip().upper().startswith("PRAGMA")

    def execute(self, sql: str, params=()):
        if self._is_pragma(sql):
            return _PgCursorWrapper(self._conn.cursor())  # no-op stub
        wrapper = _PgCursorWrapper(self._conn.cursor())
        wrapper.execute(sql, params)
        return wrapper

    def cursor(self):
        return _PgCursorWrapper(self._conn.cursor())

    def executescript(self, script: str):
        """Execute multiple semicolon-separated SQL statements.

        Mirrors ``sqlite3.Connection.executescript`` for cross-backend
        compatibility. Like sqlite3, issues an implicit COMMIT after all
        statements so DDL is not rolled back when the connection closes.
        """
        for stmt in script.split(";"):
            stmt = stmt.strip()
            if stmt:
                self.execute(stmt)
        self._conn.commit()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


# ---------------------------------------------------------------------------
# Connection factory
# ---------------------------------------------------------------------------


def get_pg_connection_raw(url: str | None = None) -> "_PgConnWrapper":
    """Return a _PgConnWrapper that the caller must explicitly close().

    Use ``get_pg_connection()`` context manager instead when possible.
    This variant is for callers that manage the connection lifecycle manually.

    Raises:
        ValueError:  if *url* is not a PostgreSQL URL.
        ImportError: if psycopg2 is not installed.
    """
    db_url = url or get_database_url() or ""
    if not is_postgres(db_url):
        raise ValueError(f"Expected a PostgreSQL URL, got: {db_url!r}")

    try:
        import psycopg2
    except ImportError as exc:
        raise ImportError(
            "psycopg2 is required for PostgreSQL support. "
            "Install it with: pip install psycopg2-binary"
        ) from exc

    if db_url.startswith("postgres://"):
        db_url = "postgresql://" + db_url[len("postgres://") :]

    conn = psycopg2.connect(db_url)
    return _PgConnWrapper(conn)


@contextlib.contextmanager
def get_pg_connection(url: str | None = None):
    """Context manager that yields a ``_PgConnWrapper`` for a PostgreSQL URL.

    Raises ``ImportError`` if psycopg2 is not installed.
    Raises ``ValueError`` if url is not a PostgreSQL URL.
    """
    db_url = url or get_database_url() or ""
    if not is_postgres(db_url):
        raise ValueError(f"Expected a PostgreSQL URL, got: {db_url!r}")

    try:
        import psycopg2
    except ImportError as exc:
        raise ImportError(
            "psycopg2 is required for PostgreSQL support. "
            "Install it with: pip install psycopg2-binary"
        ) from exc

    # Normalise postgres:// → postgresql:// for psycopg2
    if db_url.startswith("postgres://"):
        db_url = "postgresql://" + db_url[len("postgres://") :]

    conn = psycopg2.connect(db_url)
    wrapper = _PgConnWrapper(conn)
    try:
        yield wrapper
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
