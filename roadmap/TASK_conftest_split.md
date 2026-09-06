# Queued: split backend/tests/conftest.py into three modules

**Status:** queued — do NOT start until CI is green.
**Why queued:** pure refactoring, no behavioural benefit. Its only payoff is
unblocking FTAL delegation against conftest, and a working alternative already
exists (small sibling modules; `tests/db_isolation.py` is the proof). Doing it
while driving the failure count down means a broad change to the file every test
depends on — and both regressions on 2026-09-05/06 came from broad changes.

## The problem it solves

conftest.py is 667 lines. The FTAL harness injects the target file's full source,
and three delegations against conftest in a row returned nothing or timed out.
The identical task against a 1-line new file succeeded on the first attempt.
Empirical ceiling: `db_engine.py` at 388 lines still works.

## Verified facts (tested, not assumed)

1. `pytest_plugins` DOES work in a non-root conftest on pytest 9.0.2 — verified
   in a scratch repo. The widespread belief that it errors in non-root conftest
   since pytest 4 did not hold here. It is available, but see the choice below.
2. Lines 10–18 insert `backend/` and `tests/` into sys.path and are LOAD-BEARING.
   Every sibling import must run after them; that is what the existing
   `# noqa: E402` markers are for.
3. Seven test files do `from conftest import ensure_user`, and
   `tests/db_isolation.py` imports `_truncate_all_pg_tables` and
   `_seed_wellknown_users` back out of conftest.
4. `tests/__init__.py` exists, so `tests/` is a package.
5. Baseline to preserve: **146 fixtures** visible via `pytest tests/ --fixtures`.

## Chosen mechanism: plain imports, NOT pytest_plugins

Fixtures imported into the conftest namespace are discovered as module
attributes, autouse included. Already proven here: db_isolation's autouse
fixture fires (test_journey_phase4_dedup went 8 failures -> 11/11).

pytest_plugins is rejected despite working, because a hard collection error
there fails the ENTIRE suite — a failure mode already caused once this session
by deleting modules two test files still imported (2652 passing -> 0).

## The split

| Module | Contents | ~lines |
|---|---|---|
| `tests/db_support.py` | `_patch_db_path`, `_truncate_all_pg_tables`, `ensure_user`, `_seed_wellknown_users`, `app`, `client`, `_register_and_activate`, `auth_headers`, `second_user_headers` | 290 |
| `tests/fixtures_guards.py` | `_isolate_journey_workdir`, `_clear_login_rate_limiter`, `_block_llm_calls`, `_block_personaforge`, `report_skipped_infrastructure` | 130 |
| `tests/fixtures_domain.py` | `test_helpers` re-exports, `require_harness`, `resume_and_jd`, `linkedin_imported`, `optimized_resume`, `posting_id`, all `sample_*` fixtures | 230 |
| `tests/conftest.py` | sys.path block + re-export imports only | ~40 |

All land under 300 lines, inside the harness's working range.

## Two details that will bite

- Import order is mandatory: the sys.path block stays at the TOP of conftest,
  above the three imports, with `# noqa: E402`.
- `ensure_user` MUST be re-exported from conftest
  (`from db_support import ensure_user  # noqa: F401`) or seven files break.
  Then point `db_isolation.py` at `db_support` instead of conftest, which
  REMOVES the existing circular import and lets it drop its in-function import.

## Verification

1. `pytest tests/ --fixtures` must still list **146** fixtures. A fixture going
   missing is the real risk and would otherwise surface as scattered, unrelated-
   looking errors rather than as an obvious failure.
2. Full suite compared against the count at the time of the split.
3. Confirm an autouse guard still fires — e.g. test_journey_phase4_dedup stays
   11/11, which depends on DB isolation actually running.
