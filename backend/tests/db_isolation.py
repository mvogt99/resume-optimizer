"""Per-test database isolation for tests that do NOT use the `app` fixture.

conftest's `app` fixture truncates every table and reseeds the well-known users
at the start of each test, so tests that request it are isolated. Around 29 test
files never request it: they use a legacy fixture that creates a temp SQLite
file and patches models.DB_PATH, which does nothing now that the application is
PostgreSQL-only. Those tests therefore all share one database and accumulate
each other's rows.

The reason this is worth fixing centrally rather than test by test: leakage
presents as wrong COUNTS, not as an obvious error. A dedup test expecting one
duplicate pair sees two; a test expecting zero matches sees three. Every one of
those reads as a logic bug in the code under test.
"""

import pytest


@pytest.fixture(autouse=True)
def _isolate_db_for_non_app_tests(request) -> None:
    """Truncate and reseed for tests the `app` fixture does not cover."""
    if "app" in request.fixturenames:
        # `app` already truncates and reseeds; repeating it only costs time.
        return

    try:
        # Imported inside the body: conftest imports this module, so a
        # module-level import here would be circular.
        from conftest import _seed_wellknown_users, _truncate_all_pg_tables

        # Truncation first -- the seed rows have to survive it.
        _truncate_all_pg_tables()
        _seed_wellknown_users()
    except Exception:
        # An exception from an autouse fixture aborts the whole session rather
        # than failing one test; during early collection the tables may not
        # exist yet.
        return
