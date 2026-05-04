#!/usr/bin/env python3
"""QA Gate — AST-based test quality auditor with department tracking.

Implements Section 3.6 Mechanism 1 from the Quality Roadmap.
Uses Python ast module to parse test files without importing them.

Usage:
    python scripts/qa_audit.py                        # full audit with department report
    python scripts/qa_audit.py --file tests/test_X.py # single file
    python scripts/qa_audit.py --json                  # JSON output
    python scripts/qa_audit.py --report                # write roadmap/QA_AUDIT_REPORT.md
    python scripts/qa_audit.py --departments           # department accountability matrix only
    python scripts/qa_audit.py --gate                  # exit 1 if any gate fails
    python scripts/qa_audit.py --honest-assessment     # generate honest assessment

Split modules:
    qa_audit_types.py      — data classes, constants, DEPARTMENT_MAP, _tier_rank
    qa_audit_classifier.py — TestFileAnalyzer, assertion quality helpers, _check_mock_usage
    qa_audit_analyzer.py   — analyze_file(), _classify_tier()
    qa_audit_governance.py — _check_governance_rules() and G-1..G-6 helpers
    qa_audit_reporting.py  — generate_honest_assessment(), write_report(), check_gate(),
                             discover_agents(), assign_department(), compute_department_criteria()
    qa_audit_snapshots.py  — classify_severity_with_baseline(), enforce_severity(),
                             create_snapshot(), load_latest_snapshot(), diff_snapshots()
"""

import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from qa_audit_analyzer import analyze_file, _classify_tier
from qa_audit_governance import _check_governance_rules
from qa_audit_reporting import (
    assign_department,
    check_gate,
    compute_department_criteria,
    discover_agents,
    generate_honest_assessment,
    write_report,
)
from qa_audit_snapshots import (
    BASELINES_DIR,
    classify_severity_with_baseline,
    create_snapshot,
    diff_snapshots,
    enforce_severity,
    load_latest_snapshot,
)
from qa_audit_types import (
    DEPARTMENT_MAP,
    QUALITY_WEIGHTS,
    ROADMAP_DIR,
    SCRIPT_DIR,
    BACKEND_DIR,
    TESTS_DIR,
    AuditResult,
    DepartmentReport,
    FileGrade,
    _tier_rank,
)

# ---------------------------------------------------------------------------
# Full audit
# ---------------------------------------------------------------------------


def audit_all(test_dir=None):
    """Run audit on all test files. Returns AuditResult."""
    test_dir = Path(test_dir) if test_dir else TESTS_DIR
    test_files = sorted(test_dir.glob("test_*.py"))

    files = []
    for tf in test_files:
        grade = analyze_file(tf)
        if grade.test_count > 0:  # skip empty/helper files
            files.append(grade)

    departments = _build_department_reports(files)
    governance = _check_governance_rules(files)
    summary = _build_summary(files)

    return AuditResult(
        files=files,
        departments=departments,
        summary=summary,
        governance_rules=governance,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def _build_summary(files):
    """Build summary dict from file grades."""
    tier_counts = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    total_tests = 0
    total_content = 0
    total_db = 0
    total_schema = 0
    total_llm = 0

    total_quality_content = 0.0
    for f in files:
        tier_counts[f.tier] = tier_counts.get(f.tier, 0) + 1
        total_tests += f.test_count
        total_content += f.content_checks
        total_quality_content += (f.quality_content_pct / 100.0) * f.test_count
        total_db += f.db_queries
        total_schema += f.schema_checks
        total_llm += f.llm_verified

    overall = _compute_overall_grade(tier_counts, files)

    return {
        "total_files": len(files),
        "total_tests": total_tests,
        "tier_counts": tier_counts,
        "overall_grade": overall,
        "content_checks_total": total_content,
        "db_queries_total": total_db,
        "schema_checks_total": total_schema,
        "llm_verified_total": total_llm,
        "content_pct": round((total_content / max(total_tests, 1)) * 100, 1),
        "quality_content_pct": round((total_quality_content / max(total_tests, 1)) * 100, 1),
        "db_pct": round((total_db / max(total_tests, 1)) * 100, 1),
    }


def _compute_overall_grade(tier_counts, files):
    """Compute overall quality grade using weighted scoring (A=4, B=3, C=2, D=1, F=0)."""
    if not files:
        return "F"

    total = len(files)
    weights = {"A": 4, "B": 3, "C": 2, "D": 1, "F": 0}
    score = sum(weights.get(f.tier, 0) for f in files) / total

    if score >= 3.8:
        return "A+"
    if score >= 3.5:
        return "A"
    if score >= 3.2:
        return "A-"
    if score >= 2.9:
        return "B+"
    if score >= 2.6:
        return "B"
    if score >= 2.3:
        return "B-"
    if score >= 2.0:
        return "C+"
    if score >= 1.7:
        return "C"
    if score >= 1.4:
        return "C-"
    if score >= 1.0:
        return "D+"
    if score >= 0.5:
        return "D"
    return "F"


def _build_department_reports(files):
    """Build department accountability reports."""
    file_grades = {f.path: f for f in files}

    reports = []
    for dept_name, dept_info in DEPARTMENT_MAP.items():
        agents_list = []
        governed = 0
        ungoverned = 0

        for agent_name in dept_info["agents"]:
            has_test = False
            best_tier = "F"
            for tf_name in dept_info["test_files"]:
                if tf_name in file_grades:
                    has_test = True
                    grade = file_grades[tf_name]
                    if _tier_rank(grade.tier) < _tier_rank(best_tier):
                        best_tier = grade.tier
            status = "GOVERNED" if has_test else "UNGOVERNED"
            if has_test:
                governed += 1
            else:
                ungoverned += 1
            agents_list.append(
                {
                    "name": agent_name,
                    "status": status,
                    "test_file": dept_info["test_files"][0] if dept_info["test_files"] else "none",
                    "tier": best_tier if has_test else "N/A",
                }
            )

        # Determine department status
        if not dept_info["agents"]:
            dept_status = _get_tool_dept_status(dept_name, file_grades)
        elif ungoverned == 0 and governed > 0:
            dept_status = "GOVERNED"
        elif governed > 0:
            dept_status = "PARTIAL"
        else:
            dept_status = "NO GOVERNANCE"

        reports.append(
            DepartmentReport(
                name=dept_name,
                agents=agents_list,
                governed_count=governed,
                ungoverned_count=ungoverned,
                accountability_metric=dept_info["metric"],
                current_status=dept_status,
            )
        )

    return reports


def _get_tool_dept_status(dept_name, file_grades):
    """Determine status for tool-based departments."""
    if dept_name == "PMO":
        pmo_exists = (SCRIPT_DIR / "pmo_state.py").exists()
        return "GOVERNED" if pmo_exists else "NO GOVERNANCE"
    if dept_name == "Architecture":
        schemas_exist = (BACKEND_DIR / "schemas" / "__init__.py").exists()
        return "GOVERNED" if schemas_exist else "NO GOVERNANCE"
    if dept_name == "QA/Testing":
        qa_exists = (SCRIPT_DIR / "qa_audit.py").exists()
        return "GOVERNED" if qa_exists else "NO GOVERNANCE"
    if dept_name == "DevOps/Frontend":
        test_file = "test_frontend_governance.py"
        if any(test_file in str(fg) for fg in file_grades):
            return "GOVERNED"
        return "NO GOVERNANCE"
    return "NO GOVERNANCE"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    args = sys.argv[1:]

    if "--file" in args:
        idx = args.index("--file")
        filepath = args[idx + 1] if idx + 1 < len(args) else None
        if not filepath:
            print("Error: --file requires a path argument")
            sys.exit(1)
        grade = analyze_file(filepath)
        print(json.dumps(asdict(grade), indent=2))
        return

    result = audit_all()

    if "--json" in args:
        out = {
            "files": [asdict(f) for f in result.files],
            "departments": [asdict(d) for d in result.departments],
            "summary": result.summary,
            "governance_rules": result.governance_rules,
            "timestamp": result.timestamp,
        }
        print(json.dumps(out, indent=2))
        return

    if "--departments" in args:
        print("\n=== Department Accountability Matrix ===\n")
        for d in result.departments:
            agent_str = f"{d.governed_count}G/{d.ungoverned_count}U" if d.agents else "—"
            print(f"  {d.name:<25} {d.current_status:<15} {agent_str:<8} {d.accountability_metric}")
        return

    if "--honest-assessment" in args:
        print(generate_honest_assessment(result))
        return

    if "--report" in args:
        path = write_report(result)
        print(f"Report written to {path}")
        _print_summary(result)
        return

    if "--snapshot" in args:
        snap_path = create_snapshot(result)
        print(f"Snapshot written to {snap_path}")
        previous = load_latest_snapshot()
        if previous:
            current_data = {
                "files": [asdict(f) for f in result.files],
                "summary": result.summary,
            }
            diff = diff_snapshots(previous, current_data)
            if diff["improved"]:
                print(f"  Improved: {len(diff['improved'])} files")
            if diff["regressed"]:
                print(f"  Regressed: {len(diff['regressed'])} files")
            gc = diff["grade_change"]
            print(f"  Grade: {gc['old']} → {gc['new']} ({gc['direction']})")
        _print_summary(result)
        return

    if "--gate" in args:
        passed, blockers = check_gate(result)
        if passed:
            print("QA Gate: PASS")
            sys.exit(0)
        else:
            print("QA Gate: FAIL")
            for b in blockers:
                print(f"  BLOCKER: {b}")
            sys.exit(1)

    # Default: full audit output
    _print_summary(result)


def _print_summary(result):
    """Print human-readable audit summary."""
    s = result.summary
    print("\n=== QA Audit Summary ===")
    print(f"Grade: {s.get('overall_grade', 'N/A')}")
    print(f"Files: {s.get('total_files', 0)} | Tests: {s.get('total_tests', 0)}")
    qcp = s.get("quality_content_pct", s.get("content_pct", 0))
    print(
        f"Content-validated: {s.get('content_pct', 0)}% (quality-adjusted: {qcp}%) | DB-verified: {s.get('db_pct', 0)}%"
    )
    print(
        f"Tiers: A={s['tier_counts']['A']} B={s['tier_counts']['B']} "
        f"C={s['tier_counts']['C']} D={s['tier_counts']['D']} F={s['tier_counts']['F']}"
    )

    print("\n=== Departments ===")
    for d in result.departments:
        print(f"  {d.name:<25} {d.current_status}")

    print("\n=== Governance Rules ===")
    for rule_name, rule_data in result.governance_rules.items():
        print(f"  {rule_name}: {rule_data.get('status', 'UNKNOWN')}")

    passed, blockers = check_gate(result)
    print(f"\n{'GATE: PASS' if passed else 'GATE: FAIL'}")
    for b in blockers:
        print(f"  BLOCKER: {b}")


if __name__ == "__main__":
    main()
