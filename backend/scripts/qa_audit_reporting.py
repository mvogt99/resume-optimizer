"""QA Audit — reporting, assessment, gate, and agent discovery.

Contains generate_honest_assessment(), write_report(), check_gate(),
discover_agents(), assign_department(), and compute_department_criteria().
"""

import ast
from pathlib import Path

from qa_audit_types import BACKEND_DIR, ROADMAP_DIR, _tier_rank


# ---------------------------------------------------------------------------
# Honest Assessment (Section 3.6 Mechanism 3)
# ---------------------------------------------------------------------------


def generate_honest_assessment(result):
    """Generate honest assessment from audit result."""
    s = result.summary
    lines = [
        "# Honest Assessment — QA Audit",
        "",
        f"**Date:** {result.timestamp}",
        f"**Overall Grade:** {s.get('overall_grade', 'N/A')}",
        f"**Total Tests:** {s.get('total_tests', 0)}",
        f"**Total Files:** {s.get('total_files', 0)}",
        "",
        "## What Actually Works",
        "",
    ]

    tier_a_files = [f for f in result.files if f.tier == "A"]
    if tier_a_files:
        lines.append(f"- {len(tier_a_files)} test files at Tier-A quality")
        lines.append(f"- {s.get('content_checks_total', 0)} content-validated assertions")
        lines.append(f"- {s.get('db_queries_total', 0)} DB-verified assertions")
    else:
        lines.append("- No files at Tier-A quality yet")

    lines.extend(["", "## What Doesn't Work (or Is Untested)", ""])

    tier_c_below = [f for f in result.files if f.tier in ("C", "D", "F")]
    if tier_c_below:
        for f in tier_c_below:
            lines.append(
                f"- **{f.path}**: Tier-{f.tier} (content={f.content_pct}%, db={f.db_pct}%)"
            )
    else:
        lines.append("- All files at Tier-B or above")

    lines.extend(["", "## Known Gaps", ""])

    g_rules = result.governance_rules
    for rule_name, rule_data in g_rules.items():
        status = rule_data.get("status", "UNKNOWN")
        if status not in ("PASS", "INFORMATIONAL"):
            lines.append(f"- **{rule_name}**: {status} — {rule_data.get('detail', '')}")

    # Department gaps
    ungoverned_depts = [d for d in result.departments if d.current_status == "NO GOVERNANCE"]
    if ungoverned_depts:
        lines.append("")
        lines.append("**Ungoverned departments:**")
        for d in ungoverned_depts:
            lines.append(f"- {d.name}: {d.accountability_metric}")

    lines.extend(["", "## Tier Distribution", "", "| Tier | Count |", "|------|-------|"])
    for tier in ("A", "B", "C", "D", "F"):
        count = s.get("tier_counts", {}).get(tier, 0)
        lines.append(f"| {tier} | {count} |")

    lines.extend(["", "## Recommendations", ""])
    if s.get("tier_counts", {}).get("F", 0) > 0:
        lines.append("1. **CRITICAL**: Eliminate all Tier-F files before proceeding")
    if s.get("tier_counts", {}).get("D", 0) > 0:
        lines.append("2. Upgrade Tier-D files to at least Tier-C")
    tier_b_files = [f for f in result.files if f.tier == "B"]
    if tier_b_files:
        lines.append(f"3. Upgrade {len(tier_b_files)} Tier-B files to Tier-A (add DB verification)")
    if s.get("content_pct", 0) < 60:
        lines.append(
            f"4. Increase overall content validation from {s.get('content_pct', 0)}% to >60%"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def write_report(result, output_path=None):
    """Write QA_AUDIT_REPORT.md to roadmap/."""
    output_path = Path(output_path) if output_path else ROADMAP_DIR / "QA_AUDIT_REPORT.md"
    s = result.summary

    lines = [
        "# QA Audit Report",
        "",
        f"**Generated:** {result.timestamp}",
        f"**Overall Grade:** {s.get('overall_grade', 'N/A')}",
        f"**Tests:** {s.get('total_tests', 0)} across {s.get('total_files', 0)} files",
        "",
        "## Per-File Tier Breakdown",
        "",
        "| File | Tier | Tests | Content% | DB% | Schema% | LLM | Anti-Patterns |",
        "|------|------|-------|----------|-----|---------|-----|---------------|",
    ]

    for f in sorted(result.files, key=lambda x: (_tier_rank(x.tier), x.path)):
        ap_str = ", ".join(f.anti_patterns) if f.anti_patterns else "—"
        lines.append(
            f"| {f.path} | {f.tier} | {f.test_count} | {f.content_pct}% "
            f"| {f.db_pct}% | {f.schema_pct}% | {f.llm_verified} | {ap_str} |"
        )

    lines.extend([
        "",
        "## Department Accountability Matrix",
        "",
        "| Department | # Agents | Governed | Ungoverned | Metric | Status |",
        "|-----------|----------|----------|-----------|--------|--------|",
    ])

    for d in result.departments:
        agent_count = len(d.agents) if d.agents else "—"
        gov = d.governed_count if d.agents else "—"
        ungov = d.ungoverned_count if d.agents else "—"
        lines.append(
            f"| {d.name} | {agent_count} | {gov} | {ungov} "
            f"| {d.accountability_metric} | {d.current_status} |"
        )

    lines.extend([
        "",
        "## Governance Rule Compliance",
        "",
        "| Rule | Status | Detail |",
        "|------|--------|--------|",
    ])

    for rule_name, rule_data in result.governance_rules.items():
        lines.append(
            f"| {rule_name} | {rule_data.get('status', 'UNKNOWN')} "
            f"| {rule_data.get('detail', '')} |"
        )

    lines.extend(["", "---", ""])
    lines.append(generate_honest_assessment(result))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return str(output_path)


# ---------------------------------------------------------------------------
# Gate check
# ---------------------------------------------------------------------------


def check_gate(result):
    """Check if all gates pass. Returns (passed, blockers)."""
    blockers = []

    # Check: no Tier-F files
    f_files = [f for f in result.files if f.tier == "F"]
    if f_files:
        blockers.append(f"Tier-F files: {', '.join(f.path for f in f_files)}")

    # Check: no anti-patterns
    for f in result.files:
        if f.anti_patterns:
            blockers.append(f"{f.path} has anti-patterns: {', '.join(f.anti_patterns)}")

    # Check: G-1
    g1 = result.governance_rules.get("G-1_no_false_positives", {})
    if g1.get("status") == "FAIL":
        blockers.append(f"G-1 FAIL: {g1.get('detail', '')}")

    return len(blockers) == 0, blockers


# ---------------------------------------------------------------------------
# Agent Discovery (Phase 2H — dynamic department assignment)
# ---------------------------------------------------------------------------


def discover_agents(agents_init_path=None):
    """Parse agents/__init__.py via AST. Extract get_*() factory functions.

    Returns [{name: str, factory: str, module: str}]
    """
    if agents_init_path is None:
        agents_init_path = BACKEND_DIR / "agents" / "__init__.py"

    if not Path(agents_init_path).exists():
        return []

    source = Path(agents_init_path).read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    agents = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("get_"):
            # Extract agent name from function name: get_job_scout → job_scout
            agent_name = node.name[4:]  # strip "get_"
            # Try to find the module from return statement
            module = "unknown"
            for child in ast.walk(node):
                if isinstance(child, ast.Return) and isinstance(child.value, ast.Call):
                    if isinstance(child.value.func, ast.Attribute):
                        module = child.value.func.attr
                    elif isinstance(child.value.func, ast.Name):
                        module = child.value.func.id
            agents.append({"name": agent_name, "factory": node.name, "module": module})

    return agents


def assign_department(agent_name):
    """Map an agent name to a department.

    scout/tracker/pipeline → 'Job Management'
    tailor/cover/coach/advisor/resume/interview/experience/deep/builder/ats → 'Resume & Talent'
    campaign/post → 'Marketing'
    fallback → 'Software Engineering'
    """
    name_lower = agent_name.lower()

    if any(kw in name_lower for kw in ("scout", "tracker", "pipeline")):
        return "Job Management"
    if any(
        kw in name_lower
        for kw in (
            "tailor",
            "cover",
            "coach",
            "advisor",
            "resume",
            "interview",
            "experience",
            "deep",
            "builder",
            "ats",
        )
    ):
        return "Resume & Talent"
    if any(kw in name_lower for kw in ("campaign", "post")):
        return "Marketing"
    return "Software Engineering"


def compute_department_criteria(dept_name, agents, file_grades):
    """Machine-checkable criterion per department.

    Returns {status: 'GOVERNED'/'PARTIAL'/'NO GOVERNANCE',
             criterion: str, met: bool, detail: str}
    """
    if not agents:
        return {
            "status": "NO GOVERNANCE",
            "criterion": "At least one agent with test coverage",
            "met": False,
            "detail": "No agents assigned to this department",
        }

    file_names = {f.path for f in file_grades}
    governed = 0
    ungoverned = 0

    for agent in agents:
        # Auto-derive expected test file
        test_name = f"test_{agent['name']}.py"
        alt_names = ["test_agents.py", "test_integration_agents.py"]

        has_test = test_name in file_names or any(a in file_names for a in alt_names)
        if has_test:
            governed += 1
        else:
            ungoverned += 1

    if ungoverned == 0:
        status = "GOVERNED"
    elif governed > 0:
        status = "PARTIAL"
    else:
        status = "NO GOVERNANCE"

    return {
        "status": status,
        "criterion": f"All {len(agents)} agents have test coverage",
        "met": ungoverned == 0,
        "detail": f"{governed}/{len(agents)} agents governed",
    }
