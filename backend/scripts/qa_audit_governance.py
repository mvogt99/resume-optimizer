"""QA Audit — governance rule checking (G-1 through G-6).

Contains _check_governance_rules() and supporting helpers.
Imported by qa_audit (main) via audit_all().
"""

from qa_audit_types import DEPARTMENT_MAP


# ---------------------------------------------------------------------------
# Governance Rules (Section 3.3 G-1 through G-6)
# ---------------------------------------------------------------------------


def _check_governance_rules(files):
    """Check compliance with governance rules G-1 through G-6."""
    all_anti = []
    for f in files:
        all_anti.extend(f.anti_patterns)

    severity_issues = _classify_severity(files)

    return {
        "G-1_no_false_positives": {
            "status": "PASS" if not all_anti else "FAIL",
            "detail": (
                f"{len(all_anti)} anti-patterns found" if all_anti else "No anti-patterns detected"
            ),
            "anti_patterns": all_anti,
        },
        "G-2_honest_reporting": {
            "status": "PASS",
            "detail": "Honest Assessment generated on request",
        },
        "G-3_quality_ratchet": {
            "status": "INFORMATIONAL",
            "detail": "Enforced by pmo_state.py — compare via session-end",
        },
        "G-4_test_code_symmetry": {
            "status": "INFORMATIONAL",
            "detail": "Flag commits with production changes but no test changes",
        },
        "G-5_agent_evaluation": {
            "status": _g5_status(files),
            "detail": _g5_detail(files),
        },
        "G-6_escalation_protocol": {
            "status": "PASS" if not severity_issues.get("sev1") else "FAIL",
            "severity_1": severity_issues.get("sev1", []),
            "severity_2": severity_issues.get("sev2", []),
            "severity_3": severity_issues.get("sev3", []),
            "severity_4": severity_issues.get("sev4", []),
        },
    }


def _g5_status(files):
    """Rule G-5: Agent Evaluation Standard — are all agents tested?"""
    for dept_info in DEPARTMENT_MAP.values():
        for _agent in dept_info["agents"]:
            has_coverage = any(tf in {f.path for f in files} for tf in dept_info["test_files"])
            if not has_coverage:
                return "PARTIAL"
    return "PASS"


def _g5_detail(files):
    """Generate detail string for G-5."""
    file_names = {f.path for f in files}
    uncovered = []
    for dept_name, dept_info in DEPARTMENT_MAP.items():
        for agent in dept_info["agents"]:
            if not any(tf in file_names for tf in dept_info["test_files"]):
                uncovered.append(f"{agent} ({dept_name})")
    if uncovered:
        return f"Agents without test coverage: {', '.join(uncovered)}"
    return "All agents have test coverage"


def _classify_severity(files):
    """Classify issues by severity per G-6 escalation protocol."""
    issues = {"sev1": [], "sev2": [], "sev3": [], "sev4": []}

    for f in files:
        if f.tier == "F":
            issues["sev1"].append(f"{f.path}: Tier-F (critical quality failure)")
        for ap in f.anti_patterns:
            if ap.startswith("always_true"):
                issues["sev1"].append(f"{f.path}: {ap}")
            elif ap.startswith("mock_usage") or ap.startswith("silent_pass"):
                issues["sev2"].append(f"{f.path}: {ap}")
            elif ap.startswith("broad_500"):
                issues["sev3"].append(f"{f.path}: {ap}")
        if f.tier == "D":
            issues["sev3"].append(f"{f.path}: Tier-D (low content validation)")
        if f.content_pct < 50 and f.tier not in ("D", "F"):
            issues["sev4"].append(f"{f.path}: content_pct={f.content_pct}% (below 50%)")

    return issues
