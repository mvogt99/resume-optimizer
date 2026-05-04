#!/usr/bin/env python3
"""Commit Gate — Orchestrates QA Gate + Schema Gate + Regression Gate.

Implements the Commit Gate from Section 3.2 of the Quality Roadmap.

Usage:
    python scripts/commit_gate.py              # run all 3 gates, report result
    python scripts/commit_gate.py --strict     # exit 1 on any gate failure
"""

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
TESTS_DIR = BACKEND_DIR / "tests"
PROJECT_ROOT = BACKEND_DIR.parent
KNOWN_DEBT_PATH = PROJECT_ROOT / "roadmap" / "baselines" / "known_debt.json"

# Ensure backend/ is importable
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def load_known_debt():
    """Read known_debt.json → {filename: {tier, baseline_date}}."""
    if not KNOWN_DEBT_PATH.exists():
        return {}
    return json.loads(KNOWN_DEBT_PATH.read_text(encoding="utf-8"))


def update_known_debt(result=None):
    """Write current Tier-F/D files to known_debt.json with today's date."""
    if result is None:
        from qa_audit import audit_all

        result = audit_all()

    debt = {}
    for f in result.files:
        if f.tier in ("F", "D"):
            debt[f.path] = {
                "tier": f.tier,
                "baseline_date": str(date.today()),
            }

    KNOWN_DEBT_PATH.parent.mkdir(parents=True, exist_ok=True)
    KNOWN_DEBT_PATH.write_text(json.dumps(debt, indent=2), encoding="utf-8")
    return debt


def run_qa_gate():
    """Run QA Gate via qa_audit with known-debt filtering.

    Only blocks on:
    - NEW Tier-F files (not in known_debt)
    - Files that REGRESSED vs their known_debt tier
    """
    from qa_audit import audit_all, check_gate

    result = audit_all()
    passed, blockers = check_gate(result)

    # Filter blockers through known-debt exemption
    known_debt = load_known_debt()
    if not passed and known_debt:
        filtered_blockers = []
        for b in blockers:
            # Check if this blocker is about a known-debt file
            is_known = False
            for filename, debt_info in known_debt.items():
                if filename in b:
                    # Check for regression: was D in baseline, now F
                    f_grade = next((f for f in result.files if f.path == filename), None)
                    if f_grade and f_grade.tier == "F" and debt_info["tier"] == "D":
                        # Regression — keep the blocker
                        filtered_blockers.append(f"{b} (REGRESSION from {debt_info['tier']})")
                    else:
                        # Known debt at same or better tier — exempt
                        is_known = True
                    break
            if not is_known:
                filtered_blockers.append(b)

        blockers = filtered_blockers
        passed = len(blockers) == 0

    # Also run severity enforcement against baseline
    from qa_audit import classify_severity_with_baseline, enforce_severity, load_latest_snapshot

    baseline = load_latest_snapshot()
    severity_issues = classify_severity_with_baseline(result.files, baseline)
    sev_block, sev_warnings = enforce_severity(
        severity_issues,
        log_path=str(PROJECT_ROOT / "roadmap" / "governance_warnings.log"),
    )
    if sev_block:
        for w in sev_warnings:
            if w.startswith("SEV-1"):
                # Check if this SEV-1 is about a known-debt file
                is_known_sev1 = False
                for filename in known_debt:
                    if filename in w:
                        is_known_sev1 = True
                        break
                if not is_known_sev1:
                    passed = False
                    blockers.append(w)

    return {
        "passed": passed,
        "grade": result.summary.get("overall_grade", "F"),
        "tier_counts": result.summary.get("tier_counts", {}),
        "tests": result.summary.get("total_tests", 0),
        "blockers": blockers,
        "severity_warnings": sev_warnings,
    }


def run_schema_gate():
    """Run Schema Gate via schema_guard. Returns gate result dict."""
    from schema_guard import check_coverage, validate_all_schemas

    coverage = check_coverage()
    issues = validate_all_schemas()

    missing = coverage.get("missing", [])
    coverage_pct = coverage.get("coverage_pct", 0)

    # Schema gate passes if coverage >= 50% and no validation issues
    passed = coverage_pct >= 50 and not issues

    blockers = []
    if coverage_pct < 50:
        blockers.append(f"Schema coverage {coverage_pct}% < 50% threshold")
    if issues:
        blockers.append(f"Schema validation issues: {len(issues)}")

    return {
        "passed": passed,
        "coverage_pct": coverage_pct,
        "covered": coverage.get("covered", 0),
        "total": coverage.get("total", 0),
        "missing": [(m, p) for m, p in missing[:10]],  # top 10 only
        "validation_issues": issues,
        "blockers": blockers,
    }


def run_regression_gate():
    """Run Regression Gate via pytest. Returns gate result dict."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(TESTS_DIR), "-q", "--tb=line", "-x"],
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(BACKEND_DIR),
        )
        output = result.stdout + result.stderr

        # Parse pytest output for pass/fail counts
        failures = 0
        warnings = 0
        passed_count = 0

        for line in output.split("\n"):
            if "passed" in line and ("failed" in line or "warning" in line or "passed" in line):
                # e.g. "400 passed, 3 warnings in 120.5s"
                import re

                m = re.search(r"(\d+) passed", line)
                if m:
                    passed_count = int(m.group(1))
                m = re.search(r"(\d+) failed", line)
                if m:
                    failures = int(m.group(1))
                m = re.search(r"(\d+) warning", line)
                if m:
                    warnings = int(m.group(1))

        return {
            "passed": result.returncode == 0,
            "failures": failures,
            "warnings": warnings,
            "tests_passed": passed_count,
            "returncode": result.returncode,
            "blockers": [f"{failures} test failures"] if failures > 0 else [],
        }
    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "failures": -1,
            "warnings": 0,
            "tests_passed": 0,
            "returncode": -1,
            "blockers": ["Regression tests timed out (600s)"],
        }
    except Exception as e:
        return {
            "passed": False,
            "failures": -1,
            "warnings": 0,
            "tests_passed": 0,
            "returncode": -1,
            "blockers": [f"Regression gate error: {e}"],
        }


def check_test_code_symmetry(changed_files=None):
    """Git-based test-code symmetry check.

    Auto-derives prod→test mapping from naming conventions:
      backend/X.py → backend/tests/test_X.py
      backend/agents/X.py → backend/tests/test_agents.py
    Loads manual overrides from backend/scripts/prod_test_map.json.
    Returns {warnings: [...], production_changed: [...], test_changed: [...]}
    """
    # Load manual overrides
    map_path = SCRIPT_DIR / "prod_test_map.json"
    manual_map = {}
    if map_path.exists():
        manual_map = json.loads(map_path.read_text(encoding="utf-8"))

    # Get changed files from git if not provided
    if changed_files is None:
        try:
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(PROJECT_ROOT),
            )
            changed_files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
        except Exception:
            changed_files = []

    # Separate into production and test files (relative to resume-optimizer)
    prod_changed = []
    test_changed = []
    for f in changed_files:
        # Normalize to be relative to backend/
        basename = Path(f).name
        if basename.startswith("test_"):
            test_changed.append(basename)
        elif f.endswith(".py") and "scripts/" not in f and "schemas/" not in f:
            prod_changed.append(basename)

    warnings = []
    for prod_file in prod_changed:
        # Check manual map first
        expected_tests = manual_map.get(prod_file, [])
        if not expected_tests:
            # Auto-derive: X.py → test_X.py
            stem = Path(prod_file).stem
            expected_tests = [f"test_{stem}.py"]

        # Check if any expected test was also changed
        has_test = any(t in test_changed for t in expected_tests)
        if not has_test:
            warnings.append(
                f"WARNING: {prod_file} changed but no test file changed "
                f"(expected: {', '.join(expected_tests)})"
            )

    return {
        "warnings": warnings,
        "production_changed": prod_changed,
        "test_changed": test_changed,
    }


def run_commit_gate():
    """Run QA Gate + Schema Gate + Regression Gate. Return combined result."""
    qa = run_qa_gate()
    schema = run_schema_gate()
    regression = run_regression_gate()

    all_blockers = qa["blockers"] + schema["blockers"] + regression["blockers"]
    overall = "PASS" if (qa["passed"] and schema["passed"] and regression["passed"]) else "FAIL"

    return {
        "qa_gate": qa,
        "schema_gate": schema,
        "regression_gate": regression,
        "overall": overall,
        "blockers": all_blockers,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    args = sys.argv[1:]

    # Update known debt baseline
    if "--update-baseline" in args:
        debt = update_known_debt()
        print(f"Known debt updated: {len(debt)} files")
        for filename, info in debt.items():
            print(f"  {filename}: Tier-{info['tier']} (baselined {info['baseline_date']})")
        return

    quick_mode = "--quick" in args
    skip_regression = "--no-regression" in args or quick_mode

    print("=== Commit Gate ===\n")

    print("Running QA Gate...")
    qa = run_qa_gate()
    status = "PASS" if qa["passed"] else "FAIL"
    print(f"  QA Gate: {status} (grade={qa['grade']}, tests={qa['tests']})")
    for b in qa["blockers"]:
        print(f"    BLOCKER: {b}")

    print("\nRunning Schema Gate...")
    schema = run_schema_gate()
    status = "PASS" if schema["passed"] else "FAIL"
    print(
        f"  Schema Gate: {status} (coverage={schema['coverage_pct']}% "
        f"[{schema['covered']}/{schema['total']}])"
    )
    for b in schema["blockers"]:
        print(f"    BLOCKER: {b}")

    if skip_regression:
        regression = {
            "passed": True,
            "failures": 0,
            "warnings": 0,
            "tests_passed": 0,
            "blockers": [],
        }
        if quick_mode:
            print("\nRegression Gate: SKIPPED (--quick mode)")
        else:
            print("\nRegression Gate: SKIPPED (--no-regression)")
    else:
        print("\nRunning Regression Gate (pytest)...")
        regression = run_regression_gate()
        status = "PASS" if regression["passed"] else "FAIL"
        print(
            f"  Regression Gate: {status} "
            f"(passed={regression.get('tests_passed', 0)}, "
            f"failures={regression['failures']})"
        )
        for b in regression["blockers"]:
            print(f"    BLOCKER: {b}")

    # Symmetry check (warning only, never blocks)
    print("\nRunning Symmetry Gate...")
    symmetry = check_test_code_symmetry()
    if symmetry["warnings"]:
        for w in symmetry["warnings"]:
            print(f"  {w}")
    else:
        print("  Symmetry Gate: OK (no warnings)")

    all_blockers = qa["blockers"] + schema["blockers"] + regression["blockers"]
    overall = "PASS" if (qa["passed"] and schema["passed"] and regression["passed"]) else "FAIL"

    print(f"\n{'='*40}")
    print(f"COMMIT GATE: {overall}")
    if all_blockers:
        print(f"Blockers ({len(all_blockers)}):")
        for b in all_blockers:
            print(f"  - {b}")

    if "--strict" in args and overall == "FAIL":
        sys.exit(1)


if __name__ == "__main__":
    main()
