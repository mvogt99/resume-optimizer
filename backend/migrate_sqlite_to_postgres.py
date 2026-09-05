"""One-time SQLite -> PostgreSQL data migration.

Backfills a Postgres database with rows from a SQLite database.db that predate
(or exceed) what's currently in Postgres. Non-destructive by design: every
insert uses ON CONFLICT (<pk>) DO NOTHING, so existing Postgres rows are never
overwritten — this only adds rows whose primary key isn't already present.

Usage:
    python migrate_sqlite_to_postgres.py --source-db /path/to/database.db \\
        --target-url postgresql://gateway:gateway_secret@localhost:5433/ro_test \\
        [--dry-run] [--tables t1,t2,...]

Table order is derived from each table's FOREIGN KEY declarations in the
live SQLite schema (topological sort) so parent rows always land before
children that reference them.
"""

import argparse
import sqlite3
import sys

import psycopg2
import psycopg2.extras

# Tables intentionally excluded from migration: local-only stores that are
# not part of the shared app schema (separate queue/cost-tracking DBs), and
# anything test/e2e-only.
EXCLUDED_TABLES = {"sqlite_sequence"}


def get_sqlite_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return [r[0] for r in rows if r[0] not in EXCLUDED_TABLES]


def get_table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def get_primary_key(conn: sqlite3.Connection, table: str) -> str | None:
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    pk_cols = [c[1] for c in cols if c[5] > 0]
    if len(pk_cols) == 1:
        return pk_cols[0]
    return None  # composite or no PK — skip conflict handling, plain insert only


def get_foreign_keys(conn: sqlite3.Connection, table: str) -> list[str]:
    rows = conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()
    return [row[2] for row in rows]  # referenced table name


def topo_sort(conn: sqlite3.Connection, tables: list[str]) -> list[str]:
    deps = {t: set(fk for fk in get_foreign_keys(conn, t) if fk in tables and fk != t) for t in tables}
    ordered: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(t: str) -> None:
        if t in visited:
            return
        if t in visiting:
            return  # cycle guard — leave partial order, both tables still migrate
        visiting.add(t)
        for dep in deps.get(t, ()):
            visit(dep)
        visiting.discard(t)
        visited.add(t)
        ordered.append(t)

    for t in tables:
        visit(t)
    return ordered


def get_postgres_columns(pg_cur, table: str) -> list[str]:
    pg_cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name=%s",
        (table,),
    )
    return [r[0] for r in pg_cur.fetchall()]


def is_serial_pk(pg_cur, table: str, pk: str) -> bool:
    pg_cur.execute(
        "SELECT column_default FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name=%s AND column_name=%s",
        (table, pk),
    )
    row = pg_cur.fetchone()
    return bool(row and row[0] and "nextval" in row[0])


def migrate_table(sq_conn, pg_conn, table: str, dry_run: bool) -> dict:
    pg_cur = pg_conn.cursor()

    pg_tables = get_postgres_columns(pg_cur, table)
    if not pg_tables:
        return {"table": table, "status": "skipped_no_pg_table", "rows": 0}

    sqlite_cols = get_table_columns(sq_conn, table)
    cols = [c for c in sqlite_cols if c in pg_tables]  # only columns both sides have
    if not cols:
        return {"table": table, "status": "skipped_no_common_columns", "rows": 0}

    pk = get_primary_key(sq_conn, table)

    sq_cur = sq_conn.cursor()
    sq_cur.execute(f"SELECT {', '.join(cols)} FROM {table}")
    rows = sq_cur.fetchall()

    if dry_run:
        return {"table": table, "status": "dry_run", "rows": len(rows)}

    if not rows:
        return {"table": table, "status": "empty_source", "rows": 0}

    col_list = ", ".join(cols)
    placeholders = ", ".join(["%s"] * len(cols))
    if pk:
        insert_sql = (
            f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) "
            f"ON CONFLICT ({pk}) DO NOTHING"
        )
    else:
        insert_sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"

    pk_idx = cols.index(pk) if pk else None
    inserted = 0
    bad_rows: list[dict] = []
    for row in rows:
        if pk_idx is not None and row[pk_idx] is None:
            bad_rows.append({"reason": "null_pk", "row_preview": str(row)[:200]})
            continue
        pg_cur.execute("SAVEPOINT row_sp")
        try:
            pg_cur.execute(insert_sql, tuple(row))
            inserted += pg_cur.rowcount
            pg_cur.execute("RELEASE SAVEPOINT row_sp")
        except Exception as exc:  # noqa: BLE001 — isolate one bad row, keep migrating the rest
            pg_cur.execute("ROLLBACK TO SAVEPOINT row_sp")
            bad_rows.append({"reason": str(exc).strip(), "row_preview": str(row)[:200]})

    if pk and is_serial_pk(pg_cur, table, pk):
        pg_cur.execute(
            f"SELECT setval(pg_get_serial_sequence('{table}', '{pk}'), "
            f"COALESCE((SELECT MAX({pk}) FROM {table}), 1))"
        )

    pg_conn.commit()
    result = {
        "table": table,
        "status": "migrated",
        "rows_in_source": len(rows),
        "rows_inserted": inserted,
        "rows_skipped_existing": len(rows) - inserted - len(bad_rows),
    }
    if bad_rows:
        result["rows_skipped_bad"] = len(bad_rows)
        result["bad_row_samples"] = bad_rows[:5]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", required=True)
    parser.add_argument("--target-url", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--tables", help="comma-separated subset of tables (default: all)")
    args = parser.parse_args()

    sq_conn = sqlite3.connect(args.source_db)
    pg_conn = psycopg2.connect(args.target_url)

    all_tables = get_sqlite_tables(sq_conn)
    if args.tables:
        wanted = set(args.tables.split(","))
        all_tables = [t for t in all_tables if t in wanted]

    ordered = topo_sort(sq_conn, all_tables)

    print(f"{'DRY RUN — ' if args.dry_run else ''}Migrating {len(ordered)} tables "
          f"from {args.source_db} -> {args.target_url}\n")

    results = []
    for table in ordered:
        try:
            result = migrate_table(sq_conn, pg_conn, table, args.dry_run)
        except Exception as exc:  # noqa: BLE001 — report and continue, don't abort the run
            pg_conn.rollback()
            result = {"table": table, "status": "error", "error": str(exc)}
        results.append(result)
        print(f"  {result['table']:<32} {result}")

    sq_conn.close()
    pg_conn.close()

    errors = [r for r in results if r["status"] == "error"]
    if errors:
        print(f"\n{len(errors)} table(s) failed — see above.")
        return 1

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
