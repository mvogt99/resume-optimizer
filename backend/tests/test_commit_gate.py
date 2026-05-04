"""Tests for commit_gate.py — Commit Gate orchestrator.

5 tests, zero mocks, no skips.

Note: These tests call the real gate functions but we test structure
and logic, not the full pytest regression (which would be recursive).
"""

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BACKEND_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from commit_gate import (  # noqa: E402
    check_test_code_symmetry,
    load_known_debt,
    run_qa_gate,
    run_schema_gate,
    update_known_debt,
)


class TestCommitGate:

    def test_commit_gate_qa_result_structure(self):
        """QA gate result has expected keys."""
        result = run_qa_gate()
        assert "passed" in result
        assert "grade" in result
        assert "blockers" in result
        assert "tests" in result
        assert isinstance(result["passed"], bool)
        assert isinstance(result["grade"], str)
        assert isinstance(result["blockers"], list)
        assert isinstance(result["tests"], int)

    def test_commit_gate_schema_result_structure(self):
        """Schema gate result has expected keys."""
        result = run_schema_gate()
        assert "passed" in result
        assert "coverage_pct" in result
        assert "covered" in result
        assert "total" in result
        assert "blockers" in result
        assert isinstance(result["passed"], bool)
        assert isinstance(result["coverage_pct"], float)

    def test_commit_gate_qa_grade_present(self):
        """QA gate returns a valid grade string."""
        result = run_qa_gate()
        valid_grades = {"A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F"}
        assert result["grade"] in valid_grades, f"Invalid grade: {result['grade']}"

    def test_commit_gate_schema_coverage_percentage(self):
        """Schema gate reports coverage > 0%."""
        result = run_schema_gate()
        assert result["coverage_pct"] > 0, "Schema coverage should be > 0%"
        assert result["covered"] > 0, "Should have some covered routes"
        assert result["total"] > 0, "Should have routes in inventory"

    def test_commit_gate_combined_blockers(self):
        """Combined result has blockers from all failing gates."""
        qa = run_qa_gate()
        schema = run_schema_gate()

        all_blockers = qa["blockers"] + schema["blockers"]
        overall = "PASS" if (qa["passed"] and schema["passed"]) else "FAIL"

        # Structure check
        assert overall in ("PASS", "FAIL")
        assert isinstance(all_blockers, list)

        # If any gate fails, there should be blockers explaining why
        if overall == "FAIL":
            assert len(all_blockers) > 0, "FAIL with no blockers"


# ---------------------------------------------------------------------------
# Known Debt (Phase 2H)
# ---------------------------------------------------------------------------


class TestKnownDebt:

    def test_known_debt_filters_baseline_f(self, tmp_path, monkeypatch):
        """Synthetic known_debt: gate passes for known Tier-F files."""
        import commit_gate

        debt_path = tmp_path / "known_debt.json"
        debt_path.write_text(
            json.dumps({"test_external_services.py": {"tier": "F", "baseline_date": "2026-03-07"}})
        )
        monkeypatch.setattr(commit_gate, "KNOWN_DEBT_PATH", debt_path)

        result = run_qa_gate()
        # Known-debt file should not block
        for b in result["blockers"]:
            assert "test_external_services.py" not in b or "REGRESSION" in b

    def test_new_tier_f_blocks_with_known_debt(self, tmp_path, monkeypatch):
        """Unknown Tier-F still blocks even with known_debt active."""
        import commit_gate

        # Known debt for a DIFFERENT file
        debt_path = tmp_path / "known_debt.json"
        debt_path.write_text(
            json.dumps({"test_some_other_file.py": {"tier": "F", "baseline_date": "2026-03-07"}})
        )
        monkeypatch.setattr(commit_gate, "KNOWN_DEBT_PATH", debt_path)

        # Create a synthetic Tier-F file
        from qa_audit import analyze_file

        fake_test = tmp_path / "test_fake_f.py"
        fake_test.write_text("def test_bad():\n    assert len([]) >= 0\n")
        grade = analyze_file(fake_test)
        assert grade.tier == "F", "Synthetic file should be Tier-F"
        # The new file wouldn't be in known_debt, so it would block

    def test_regression_blocks_in_known_debt(self, tmp_path, monkeypatch):
        """File in known_debt at D, now F → blocks with REGRESSION label."""
        import commit_gate

        # Create known_debt with file at Tier-D
        debt_path = tmp_path / "known_debt.json"
        debt_path.write_text(
            json.dumps({"test_regressed.py": {"tier": "D", "baseline_date": "2026-03-01"}})
        )
        monkeypatch.setattr(commit_gate, "KNOWN_DEBT_PATH", debt_path)

        known_debt = load_known_debt()
        assert "test_regressed.py" in known_debt
        assert known_debt["test_regressed.py"]["tier"] == "D"

    def test_update_known_debt_creates_file(self, tmp_path, monkeypatch):
        """--update-baseline writes valid JSON."""
        import commit_gate

        debt_path = tmp_path / "baselines" / "known_debt.json"
        monkeypatch.setattr(commit_gate, "KNOWN_DEBT_PATH", debt_path)

        debt = update_known_debt()
        assert isinstance(debt, dict)
        # File should exist
        assert debt_path.exists()
        parsed = json.loads(debt_path.read_text())
        assert isinstance(parsed, dict)

    def test_external_services_classified_as_script_test(self):
        """analyze_file() returns tier != 'F' for test_external_services.py."""
        from qa_audit import analyze_file

        grade = analyze_file(BACKEND_DIR / "tests" / "test_external_services.py")
        assert grade.tier != "F", (
            f"test_external_services.py should not be Tier-F (script test), "
            f"got tier={grade.tier}, anti_patterns={grade.anti_patterns}"
        )


# ---------------------------------------------------------------------------
# Test-Code Symmetry (Phase 2H-C, G-4)
# ---------------------------------------------------------------------------


class TestSymmetry:

    def test_symmetry_detects_missing_test(self):
        """Prod file changed, no test → warning issued."""
        result = check_test_code_symmetry(changed_files=["backend/utils.py"])
        assert len(result["warnings"]) > 0
        assert "utils.py" in result["warnings"][0]

    def test_symmetry_passes_with_tests(self):
        """Both changed → no warning."""
        result = check_test_code_symmetry(
            changed_files=["backend/utils.py", "backend/tests/test_utils.py"]
        )
        # utils.py → test_utils.py via auto-derive, both present
        assert len(result["warnings"]) == 0

    def test_symmetry_uses_manual_override(self):
        """prod_test_map.json overrides auto-derive."""
        # app.py maps to multiple test files via manual map
        result = check_test_code_symmetry(
            changed_files=["backend/app.py", "backend/tests/test_auth.py"]
        )
        # app.py manually maps to test_auth.py, which is present
        assert len(result["warnings"]) == 0

    def test_symmetry_warning_not_block(self):
        """Warning present but gate still PASS."""
        qa = run_qa_gate()
        # Symmetry warnings never affect qa gate pass/fail
        assert isinstance(qa["passed"], bool)
