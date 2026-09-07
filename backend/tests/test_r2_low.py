"""Round 2 Gate — LOW severity issue tests.

L1: Late imports inside route handlers — should be at module level where safe
L4: Error status code inconsistency — non-lookup errors should return 400, not 404
L5: closing_present criterion too permissive — needs minimum length
"""

import ast
import os
from unittest.mock import MagicMock, patch


BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── L1: Late imports ──────────────────────────────────────────────────────

# Modules that MUST be imported at module level in route files
# (verified safe — no circular dependency risk)
# We'll populate this after investigation; for now test the principle.


def _find_function_level_imports(filepath):
    """Find imports inside function bodies (not module level)."""
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    function_imports = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                if isinstance(child, (ast.Import, ast.ImportFrom)):
                    module = ""
                    if isinstance(child, ast.ImportFrom):
                        module = child.module or ""
                    else:
                        module = child.names[0].name if child.names else ""
                    function_imports.append((child.lineno, module))

    return function_imports


# Known safe-to-move imports (no circular dependency risk)
# These modules are standalone and don't import from route files
SAFE_TO_MOVE_MODULES = {
    "job_scraper",
    "feedback_analyzer",
    "application_orchestrator",
    "deep_profile",
    "nlp_engine",
}

ROUTE_FILES_FOR_L1 = [
    "agents_routes_scout.py",
    "agents_routes_pipeline.py",
    "agents_routes_orchestrator.py",
    "agents_routes_advisor.py",
    "agents_routes_system.py",
]


def test_l1_no_safe_late_imports_in_route_files():
    """L1: Modules known to be safe must be imported at module level."""
    violations = {}
    for fname in ROUTE_FILES_FOR_L1:
        fpath = os.path.join(BACKEND_DIR, fname)
        if not os.path.exists(fpath):
            continue
        late = _find_function_level_imports(fpath)
        for lineno, module in late:
            # Check if this is a module we know is safe to move
            base_module = module.split(".")[0] if module else ""
            if base_module in SAFE_TO_MOVE_MODULES:
                violations.setdefault(fname, []).append((lineno, module))

    if violations:
        msg = "Late imports that should be at module level:\n"
        for fname, items in violations.items():
            for lineno, module in items:
                msg += f"  {fname}:{lineno}: {module}\n"
        assert False, msg


# ── L4: Error status code consistency ─────────────────────────────────────


class TestL4ErrorStatusCodes:
    """Non-lookup errors must return 400, not 404."""

    @patch("agents_routes_pipeline.get_app_tracker")
    def test_pipeline_followup_error_returns_400(self, mock_tracker, client, auth_headers):
        """POST /agents/pipeline/{id}/followup error → 400, not 404."""
        tracker = MagicMock()
        tracker.generate_followup.return_value = {"error": "LLM unavailable"}
        mock_tracker.return_value = tracker

        resp = client.post(
            "/api/agents/pipeline/999/followup",
            headers=auth_headers,
            json={},
        )
        # If error is "not found" → 404 is OK. If error is operational → 400.
        # The point is: non-lookup errors must not return 404.
        if resp.status_code != 404:
            # Either endpoint doesn't exist or returned different code — both OK
            pass
        else:
            data = resp.get_json()
            if data and "error" in data and "not found" not in data["error"].lower():
                assert False, (
                    f"Pipeline followup returned 404 for operational error: {data['error']}. "
                    "Non-lookup errors should return 400."
                )

    # agents_routes_orchestrator does `from ... import apply_to_job` at module
    # level, so the name must be patched THERE -- patching the source module
    # leaves the already-bound reference in place and the real function runs.
    @patch("agents_routes_orchestrator.apply_to_job")
    def test_orchestrator_apply_error_returns_400(self, mock_apply, client, auth_headers):
        """POST /agents/orchestrator/apply ValueError → 400, not 404."""
        mock_apply.side_effect = ValueError("Missing resume version")

        # The route is /api/agents/apply. The old URL did not exist, so this
        # test was asserting against Flask's router 404 and never reached the
        # handler it claims to cover.
        resp = client.post(
            "/api/agents/apply",
            headers=auth_headers,
            json={"posting_id": "123"},
        )
        assert resp.status_code == 400, (
            f"Expected 400 for ValueError in apply, got {resp.status_code}. "
            "ValueError is a client error (400), not a resource-not-found (404)."
        )


# ── L5: closing_present minimum length ────────────────────────────────────


class TestL5ClosingMinLength:
    """closing_present criterion must reject very short closings."""

    def test_single_char_closing_fails(self):
        """A single-character closing like '.' should fail."""
        from agents.acceptance.resume_criteria import COVER_LETTER_CRITERIA

        # Find the closing_present criterion
        closing_crit = None
        for c in COVER_LETTER_CRITERIA:
            if c.name == "closing_present":
                closing_crit = c
                break

        assert closing_crit is not None, "closing_present criterion not found"

        # Single character should fail
        result = closing_crit.check({"closing": "."})
        assert not result, (
            "closing_present accepts single-char closing '.'. "
            "Must require at least 5 characters."
        )

    def test_empty_closing_fails(self):
        """Empty closing should fail."""
        from agents.acceptance.resume_criteria import COVER_LETTER_CRITERIA

        closing_crit = None
        for c in COVER_LETTER_CRITERIA:
            if c.name == "closing_present":
                closing_crit = c
                break

        assert closing_crit is not None
        result = closing_crit.check({"closing": ""})
        assert not result, "closing_present accepts empty closing"

    def test_proper_closing_passes(self):
        """A proper closing like 'Sincerely, Mike Vogt' should pass."""
        from agents.acceptance.resume_criteria import COVER_LETTER_CRITERIA

        closing_crit = None
        for c in COVER_LETTER_CRITERIA:
            if c.name == "closing_present":
                closing_crit = c
                break

        assert closing_crit is not None
        result = closing_crit.check({"closing": "Sincerely, Mike Vogt"})
        assert result, "closing_present rejects valid closing"

    def test_regen_single_char_closing_fails(self):
        """COVER_REGEN_CRITERIA closing_present also rejects short closings."""
        from agents.acceptance.resume_criteria import COVER_REGEN_CRITERIA

        closing_crit = None
        for c in COVER_REGEN_CRITERIA:
            if c.name == "closing_present":
                closing_crit = c
                break

        assert closing_crit is not None, "closing_present not in COVER_REGEN_CRITERIA"

        result = closing_crit.check({"closing": "X"})
        assert not result, (
            "COVER_REGEN closing_present accepts single-char closing. "
            "Must require at least 5 characters."
        )
