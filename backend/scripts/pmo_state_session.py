"""PMO Orchestrator — Session governance and honest assessment.

Contains generate_honest_assessment(), session_start(), _check_persistent_sev1(),
session_end(), and _generate_diff_assessment().

Split from pmo_state.py (>500 lines). Imports state helpers from pmo_state.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from pmo_state import (
    SCRIPT_DIR,
    _add_grade_history,
    _grade_rank,
    check_quality_ratchet,
    get_blockers,
    get_pending_phases,
    read_state,
    write_state,
)


# ---------------------------------------------------------------------------
# Honest Assessment (Section 3.6 Mechanism 3)
# ---------------------------------------------------------------------------


def generate_honest_assessment(previous_state, current_state):
    """Generate Honest Assessment comparing previous vs current state.

    Returns markdown matching Section 3.6 Mechanism 3 template.
    """
    prev_metrics = previous_state.get("quality_metrics", {})
    curr_metrics = current_state.get("quality_metrics", {})

    prev_grade = prev_metrics.get("overall_grade", "F")
    curr_grade = curr_metrics.get("overall_grade", "F")
    prev_tests = prev_metrics.get("tests_total", 0)
    curr_tests = curr_metrics.get("tests_total", 0)

    grade_change = _grade_rank(prev_grade) - _grade_rank(curr_grade)
    if grade_change > 0:
        grade_direction = "IMPROVED"
    elif grade_change < 0:
        grade_direction = "DEGRADED"
    else:
        grade_direction = "UNCHANGED"

    lines = [
        "# Session Honest Assessment",
        "",
        f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        "",
        "## Grade Progression",
        "",
        f"- Previous: **{prev_grade}** ({prev_tests} tests)",
        f"- Current:  **{curr_grade}** ({curr_tests} tests)",
        f"- Direction: **{grade_direction}**",
        "",
        "## What Actually Improved",
        "",
    ]

    test_delta = curr_tests - prev_tests
    if test_delta > 0:
        lines.append(f"- {test_delta} tests added")
    elif test_delta < 0:
        lines.append(f"- {abs(test_delta)} tests removed (cleanup)")
    else:
        lines.append("- No test count change")

    prev_tier_a = prev_metrics.get("tier_a_files", 0)
    curr_tier_a = curr_metrics.get("tier_a_files", 0)
    if curr_tier_a > prev_tier_a:
        lines.append(f"- Tier-A files: {prev_tier_a} → {curr_tier_a}")

    lines.extend(["", "## What Still Needs Work", ""])

    curr_tier_f = curr_metrics.get("tier_f_files", 0)
    if curr_tier_f > 0:
        lines.append(f"- {curr_tier_f} Tier-F files remain")

    gaps = current_state.get("governance_gaps", {})
    for gap_name, gap_status in gaps.items():
        if "NOT BUILT" in str(gap_status).upper():
            lines.append(f"- {gap_name}: {gap_status}")

    pending = []
    for name, status in current_state.get("phase_status", {}).items():
        if "PENDING" in str(status).upper():
            pending.append(name)
    if pending:
        lines.append(f"- Pending phases: {', '.join(pending)}")

    lines.extend([
        "",
        "## Quality Ratchet Status",
        "",
        "- Ratchet check: "
        + ("PASS" if grade_direction != "DEGRADED" else "FAIL — grade dropped!"),
    ])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Workflow 4: Session Governance (Section 3.4)
# ---------------------------------------------------------------------------


def session_start():
    """SESSION START block from Workflow 4.

    Reads state, checks for persistent Sev-1 issues (across 2 snapshots),
    returns status summary for user presentation.
    """
    state = read_state()
    metrics = state.get("quality_metrics", {})
    grade = metrics.get("overall_grade", "F")
    tests = metrics.get("tests_total", 0)
    phase = state.get("current_phase_name", "Unknown")

    pending = get_pending_phases()
    blockers = get_blockers()

    lines = [
        "=== Session Start ===",
        f"Phase: {phase}",
        f"Grade: {grade} | Tests: {tests}",
        f"Tier-A: {metrics.get('tier_a_files', 0)} | Tier-F: {metrics.get('tier_f_files', 0)}",
    ]

    # Check for persistent Sev-1 issues across snapshots
    persistent_blockers = _check_persistent_sev1()
    if persistent_blockers:
        lines.append("PERSISTENT SEV-1 BLOCKERS:")
        for pb in persistent_blockers:
            lines.append(f"  - {pb}")

    if pending:
        lines.append(f"Pending: {', '.join(pending)}")
    if blockers:
        lines.append(f"Blockers: {', '.join(blockers)}")

    next_action = state.get("next_action", "")
    if next_action:
        lines.append(f"Next: {next_action}")

    return "\n".join(lines)


def _check_persistent_sev1():
    """Check latest 2 snapshots for persistent Sev-1 issues.

    Returns list of persistent blocker descriptions.
    """
    try:
        sys.path.insert(0, str(SCRIPT_DIR))
        from qa_audit_snapshots import _resolve_baselines_dir
    except ImportError:
        return []

    baselines = _resolve_baselines_dir()
    if not baselines.exists():
        return []

    snapshots = sorted(baselines.glob("*.json"))
    snapshots = [s for s in snapshots if s.name != "known_debt.json"]
    if len(snapshots) < 2:
        return []

    import json as _json

    snap1 = _json.loads(snapshots[-2].read_text(encoding="utf-8"))
    snap2 = _json.loads(snapshots[-1].read_text(encoding="utf-8"))

    # Find Tier-F files present in BOTH snapshots
    f_files_1 = {f["path"] for f in snap1.get("files", []) if f.get("tier") == "F"}
    f_files_2 = {f["path"] for f in snap2.get("files", []) if f.get("tier") == "F"}
    persistent = f_files_1 & f_files_2

    return [f"{f}: Tier-F in 2 consecutive snapshots" for f in sorted(persistent)]


def session_end(qa_result_dict=None):
    """SESSION END block from Workflow 4.

    1. Runs qa_audit to get computed grade (single source of truth)
    2. Creates baseline snapshot
    3. Checks quality ratchet — refuses to update if grade would drop
    4. Generates diff-based honest assessment
    5. Updates state only on ratchet pass

    Returns dict with {assessment, updated, ratchet_violation (if any)}.
    """
    previous_state = read_state()

    # 1. Run qa_audit to get computed grade
    sys.path.insert(0, str(SCRIPT_DIR))
    from qa_audit import audit_all
    from qa_audit_snapshots import create_snapshot, diff_snapshots, load_latest_snapshot

    if qa_result_dict is None:
        result = audit_all()
        qa_result_dict = {
            "summary": result.summary,
            "files": [{"path": f.path, "tier": f.tier} for f in result.files],
        }
    else:
        result = None  # caller provided pre-computed result

    summary = qa_result_dict.get("summary", {})
    computed_grade = summary.get("overall_grade", "F")

    # 2. Create baseline snapshot
    if result is not None:
        snap_path = create_snapshot(result)
    else:
        snap_path = create_snapshot()

    # 3. Check quality ratchet
    ratchet_ok = check_quality_ratchet(computed_grade)

    if not ratchet_ok:
        current_grade = read_state().get("quality_metrics", {}).get("overall_grade", "F")
        return {
            "assessment": "",
            "updated": False,
            "ratchet_violation": f"{current_grade} → {computed_grade} would downgrade",
            "snapshot": str(snap_path),
        }

    # 4. Update state with new metrics
    state = read_state()
    state["quality_metrics"]["tests_total"] = summary.get("total_tests", 0)
    state["quality_metrics"]["overall_grade"] = computed_grade
    state["quality_metrics"]["tier_a_files"] = summary.get("tier_counts", {}).get("A", 0)
    state["quality_metrics"]["tier_f_files"] = summary.get("tier_counts", {}).get("F", 0)
    state["quality_metrics"]["total_test_files"] = summary.get("total_files", 0)
    state["quality_metrics"]["content_pct"] = summary.get("content_pct", 0)
    state["quality_metrics"]["db_pct"] = summary.get("db_pct", 0)

    # Add grade history (only via session_end)
    _add_grade_history(
        state, computed_grade, summary.get("total_tests", 0), "session_end computed grade"
    )
    write_state(state)

    # 5. Generate diff-based honest assessment
    current_snapshot = {
        "files": qa_result_dict.get("files", []),
        "summary": summary,
    }
    previous_snapshot = load_latest_snapshot()

    if previous_snapshot:
        diff = diff_snapshots(previous_snapshot, current_snapshot)
        assessment = _generate_diff_assessment(current_snapshot, previous_snapshot, diff)
    else:
        current_state = read_state()
        assessment = generate_honest_assessment(previous_state, current_state)

    # Write assessment to roadmap/assessments/
    # Re-read PROJECT_ROOT from pmo_state at call-time (supports monkeypatching)
    import pmo_state as _pm
    _project_root = _pm.PROJECT_ROOT
    assessments_dir = _project_root / "roadmap" / "assessments"
    assessments_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    assessment_path = assessments_dir / f"{today}.md"
    assessment_path.write_text(assessment, encoding="utf-8")

    # Also write to legacy location — but only if it doesn't already exist
    legacy_path = _project_root / "roadmap" / "HONEST_ASSESSMENT.md"
    if not legacy_path.exists():
        legacy_path.write_text(assessment, encoding="utf-8")

    return {
        "assessment": assessment,
        "updated": True,
        "ratchet_violation": None,
        "snapshot": str(snap_path),
    }


def _generate_diff_assessment(current_snapshot, previous_snapshot, diff):
    """Generate diff-based honest assessment from snapshot comparison."""
    lines = [
        "# Session Honest Assessment (Diff-Based)",
        "",
        f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        "",
    ]

    # Grade change
    gc = diff["grade_change"]
    lines.extend([
        "## Grade Change",
        "",
        f"- Previous: **{gc['old']}**",
        f"- Current:  **{gc['new']}**",
        f"- Direction: **{gc['direction']}**",
        "",
    ])

    if diff["improved"]:
        lines.append("## Files Improved")
        lines.append("")
        for item in diff["improved"]:
            lines.append(f"- {item['file']}: {item['old_tier']} → {item['new_tier']}")
        lines.append("")

    if diff["regressed"]:
        lines.append("## Files Regressed")
        lines.append("")
        for item in diff["regressed"]:
            lines.append(f"- {item['file']}: {item['old_tier']} → {item['new_tier']}")
        lines.append("")

    if diff["added"]:
        lines.append("## New Files")
        lines.append("")
        for item in diff["added"]:
            lines.append(f"- {item['file']}: Tier-{item['tier']}")
        lines.append("")

    if diff["removed"]:
        lines.append("## Removed Files")
        lines.append("")
        for item in diff["removed"]:
            lines.append(f"- {item['file']}: was Tier-{item['tier']}")
        lines.append("")

    lines.extend([
        "## Claims vs Evidence",
        "",
        "All grades computed by qa_audit.py — no manual overrides.",
        "",
    ])

    return "\n".join(lines)
