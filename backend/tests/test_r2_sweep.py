"""Round 2 Gate — Backend-wide sweep tests.

Tests for Phase 3 (requests→httpx) and Phase 4 (connection leak sweep).
These tests verify the ENTIRE backend, not just assessment-scoped files.
"""

import os
import re

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Files that legitimately need `requests` (e.g., python-jobspy dependency)
REQUESTS_EXCEPTIONS = set()
# Files where get_db_connection(db_path=...) is used and try/finally is acceptable
DB_PATH_FILES = {"batch_jobs.py"}


def _get_py_files(exclude_tests=True):
    """Get all .py files in backend/, excluding tests and __pycache__."""
    files = []
    for fname in os.listdir(BACKEND_DIR):
        if not fname.endswith(".py"):
            continue
        if fname.startswith("__"):
            continue
        if exclude_tests and fname.startswith("test_"):
            continue
        files.append(fname)
    return sorted(files)


# ── Phase 3: requests→httpx sweep ─────────────────────────────────────────


def test_no_requests_import_in_backend():
    """No non-test backend file should import 'requests' (Phase 24B: httpx)."""
    violations = []
    for fname in _get_py_files():
        if fname in REQUESTS_EXCEPTIONS:
            continue
        fpath = os.path.join(BACKEND_DIR, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                # Match: import requests / from requests import / import requests as
                if re.match(r"^\s*(import requests|from requests\s)", line):
                    violations.append(f"  {fname}:{lineno}: {line.strip()}")

    if violations:
        msg = "Backend files still import 'requests' (Phase 24B mandated httpx):\n" + "\n".join(
            violations
        )
        raise AssertionError(msg)


# ── Phase 4: Connection leak sweep ────────────────────────────────────────


def _check_file_for_unsafe_connections(fpath, fname):
    """Check if a file has get_db_connection() calls outside try/finally or with."""
    with open(fpath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    unsafe = []
    for i, line in enumerate(lines):
        # Find lines that call get_db_connection()
        if "get_db_connection(" not in line:
            continue
        if line.strip().startswith("#"):
            continue
        if "def get_db_connection" in line:
            continue

        lineno = i + 1

        # Check surrounding context: look backwards for 'with' or 'try'
        # and forward for 'finally:' + 'close()'
        context_before = "".join(lines[max(0, i - 3) : i])
        context_after = "".join(lines[i : min(len(lines), i + 20)])

        in_with = "with " in context_before and "get_db(" in context_before
        # try: can be before or immediately after the connection call
        context_after_short = "".join(lines[i : min(len(lines), i + 3)])
        has_try = "try:" in context_before or "try:" in context_after_short
        in_try_finally = has_try and "finally:" in context_after and "close()" in context_after

        # Also check if the get_db_connection call itself is inside a with
        stripped = line.strip()
        if stripped.startswith("with "):
            continue

        if not in_with and not in_try_finally:
            unsafe.append((lineno, stripped))

    return unsafe


def test_no_unsafe_connections_in_backend():
    """All get_db_connection() calls must be in with/try-finally blocks."""
    all_unsafe = {}
    for fname in _get_py_files():
        fpath = os.path.join(BACKEND_DIR, fname)
        unsafe = _check_file_for_unsafe_connections(fpath, fname)
        if unsafe:
            all_unsafe[fname] = unsafe

    if all_unsafe:
        total = sum(len(v) for v in all_unsafe.values())
        msg = f"Unsafe get_db_connection() calls ({total} sites, {len(all_unsafe)} files):\n"
        for fname, sites in sorted(all_unsafe.items()):
            for lineno, text in sites:
                msg += f"  {fname}:{lineno}: {text}\n"
        raise AssertionError(msg)
