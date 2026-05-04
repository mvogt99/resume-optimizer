"""Round 2 Gate — HIGH severity issue tests.

H1: Resource leaks — get_db_connection() without try/finally or context manager
H2: requests still imported in agents_routes_system.py (Phase 24B mandated httpx)
"""

import ast
import os
import re

# ── H1: Connection leak detection ──────────────────────────────────────────

# Assessment-scoped files that must use safe DB patterns
H1_FILES = [
    "agents_routes_system.py",
    "agents_routes_common.py",
    "agents_routes_pipeline.py",
    "agents_routes_advisor.py",
    "journey_miner_review_mixin.py",
    "journey_miner_timeline_mixin.py",
    "ai_journey_source.py",
]

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _find_unsafe_get_db_connection(filepath):
    """Return list of (line_number, line_text) for get_db_connection() calls
    that are NOT inside a try/finally or with statement.

    Strategy: parse the AST, find all calls to get_db_connection(), and check
    whether they are inside a With or Try node with a finally clause.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    unsafe = []
    lines = source.splitlines()

    # Walk AST: find all Assign nodes where value is a Call to get_db_connection
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value if isinstance(node, ast.Assign) else node.value
        if value is None:
            continue
        if not isinstance(value, ast.Call):
            continue

        # Check if the call is to get_db_connection
        func = value.func
        func_name = ""
        if isinstance(func, ast.Name):
            func_name = func.id
        elif isinstance(func, ast.Attribute):
            func_name = func.attr

        if func_name != "get_db_connection":
            continue

        lineno = node.lineno

        # Walk up the AST to check if this is inside a With or Try/finally
        safe = _is_inside_safe_block(tree, lineno)
        if not safe:
            unsafe.append((lineno, lines[lineno - 1].strip()))

    return unsafe


def _is_inside_safe_block(tree, target_lineno):
    """Check if a line is inside a 'with' statement or try/finally block."""

    class SafeBlockChecker(ast.NodeVisitor):
        def __init__(self):
            self.safe = False
            self._in_safe = False

        def visit_With(self, node):
            old = self._in_safe
            self._in_safe = True
            self.generic_visit(node)
            self._in_safe = old

        def visit_Try(self, node):
            # Only safe if there's a finally clause that calls .close()
            has_finally_close = False
            for stmt in node.finalbody:
                src = ast.dump(stmt)
                if "close" in src:
                    has_finally_close = True
                    break

            old = self._in_safe
            if has_finally_close:
                self._in_safe = True
            self.generic_visit(node)
            self._in_safe = old

        def visit_Assign(self, node):
            if node.lineno == target_lineno and self._in_safe:
                self.safe = True
            self.generic_visit(node)

        def visit_AnnAssign(self, node):
            if node.lineno == target_lineno and self._in_safe:
                self.safe = True
            self.generic_visit(node)

    checker = SafeBlockChecker()
    checker.visit(tree)
    return checker.safe


def test_h1_no_unsafe_db_connections_in_assessment_files():
    """H1: All get_db_connection() calls in assessment files must be in
    a context manager (with) or try/finally block."""
    all_unsafe = {}
    for fname in H1_FILES:
        fpath = os.path.join(BACKEND_DIR, fname)
        if not os.path.exists(fpath):
            continue
        unsafe = _find_unsafe_get_db_connection(fpath)
        if unsafe:
            all_unsafe[fname] = unsafe

    if all_unsafe:
        msg = "Unsafe get_db_connection() calls (no with/try-finally):\n"
        for fname, sites in all_unsafe.items():
            for lineno, text in sites:
                msg += f"  {fname}:{lineno}: {text}\n"
        assert False, msg


# ── H2: requests import detection ──────────────────────────────────────────


def test_h2_no_requests_import_in_system_routes():
    """H2: agents_routes_system.py must use httpx, not requests."""
    fpath = os.path.join(BACKEND_DIR, "agents_routes_system.py")
    with open(fpath, "r", encoding="utf-8") as f:
        source = f.read()

    assert "import requests" not in source, (
        "agents_routes_system.py still imports 'requests'. "
        "Phase 24B mandated httpx migration."
    )
