"""Tests for pre-commit hook + commit_gate --quick mode.

4 tests, zero mocks, no skips.
"""

import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BACKEND_DIR / "scripts"
PROJECT_ROOT = BACKEND_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class TestQuickMode:

    def test_commit_gate_quick_skips_regression(self):
        """--quick doesn't run pytest subprocess."""
        # Quick mode sets skip_regression=True, so regression gate should not run.
        # We verify by checking that the main() function treats --quick same as
        # --no-regression. Test by running commit_gate with --quick and capturing output.
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "commit_gate.py"), "--quick"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(BACKEND_DIR),
        )
        assert (
            "SKIPPED (--quick mode)" in result.stdout
        ), f"Expected '--quick mode' skip message, got:\n{result.stdout[-500:]}"
        # Should NOT contain "Running Regression Gate (pytest)"
        assert "Running Regression Gate (pytest)" not in result.stdout

    def test_commit_gate_quick_runs_qa_and_schema(self):
        """QA + schema results present in quick mode."""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "commit_gate.py"), "--quick"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(BACKEND_DIR),
        )
        assert "QA Gate:" in result.stdout
        assert "Schema Gate:" in result.stdout
        assert "Symmetry Gate:" in result.stdout


class TestPreCommitScript:

    def test_pre_commit_script_exists(self):
        """.githooks/pre-commit exists and is executable."""
        hook = PROJECT_ROOT / ".githooks" / "pre-commit"
        assert hook.exists(), f"Pre-commit hook not found at {hook}"
        assert hook.stat().st_mode & 0o111, "Pre-commit hook is not executable"

    def test_pre_commit_script_valid_bash(self):
        """bash -n syntax check passes."""
        hook = PROJECT_ROOT / ".githooks" / "pre-commit"
        result = subprocess.run(
            ["bash", "-n", str(hook)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"Bash syntax error in pre-commit hook:\n{result.stderr}"
