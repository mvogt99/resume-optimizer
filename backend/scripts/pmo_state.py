#!/usr/bin/env python3
"""PMO Orchestrator — Session state persistence and phase management.

Implements Section 3.2 PMO Orchestrator Layer and Section 3.6 Mechanism 2.

Usage:
    python scripts/pmo_state.py status                # present current state
    python scripts/pmo_state.py approve <phase> <msg> # approve a phase
    python scripts/pmo_state.py metrics --tests-total N --tests-passed N --grade G
    python scripts/pmo_state.py history <grade> <tests> <notes>
    python scripts/pmo_state.py departments            # show accountability matrix
    python scripts/pmo_state.py honest-assessment       # generate assessment vs previous
    python scripts/pmo_state.py session-end             # full session end workflow

Split module:
    pmo_state_session.py — generate_honest_assessment(), session_start(),
                           _check_persistent_sev1(), session_end(),
                           _generate_diff_assessment()
"""

import contextlib
import json
import os
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
STATE_FILE = PROJECT_ROOT / "roadmap" / "SESSION_STATE.json"

# Valid grade ordering (best to worst)
GRADE_ORDER = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F"]


# ---------------------------------------------------------------------------
# State I/O
# ---------------------------------------------------------------------------


def read_state():
    """Read SESSION_STATE.json and return as dict."""
    if not STATE_FILE.exists():
        return _default_state()
    text = STATE_FILE.read_text(encoding="utf-8")
    return json.loads(text)


def write_state(state):
    """Write state to SESSION_STATE.json atomically (write tmp → rename)."""
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=str(STATE_FILE.parent), suffix=".tmp", prefix="state_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
            f.write("\n")
        os.replace(tmp_path, str(STATE_FILE))
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    return state


def _default_state():
    """Return a default state structure."""
    return {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "current_phase": 0,
        "current_phase_name": "Initial",
        "phase_status": {},
        "quality_metrics": {
            "tests_total": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "overall_grade": "F",
            "tier_a_files": 0,
            "tier_f_files": 0,
            "total_test_files": 0,
        },
        "grade_history": [],
        "delegation_economics": {},
        "governance_gaps": {},
        "blockers": [],
        "next_action": "",
    }


# ---------------------------------------------------------------------------
# Phase Management (Section 3.2)
# ---------------------------------------------------------------------------


def get_current_phase():
    """Return (phase_number, phase_name) tuple."""
    state = read_state()
    return state.get("current_phase", 0), state.get("current_phase_name", "Unknown")


def approve_phase(phase_name, status):
    """Update a phase status. Returns updated state."""
    state = read_state()
    if "phase_status" not in state:
        state["phase_status"] = {}
    state["phase_status"][phase_name] = status
    return write_state(state)


def is_phase_approved(phase_name):
    """Check if a phase has been approved/completed."""
    state = read_state()
    status = state.get("phase_status", {}).get(phase_name, "")
    return any(kw in status.upper() for kw in ("APPROVED", "COMPLETE"))


def get_pending_phases():
    """Return list of phase names that are PENDING."""
    state = read_state()
    pending = []
    for name, status in state.get("phase_status", {}).items():
        if "PENDING" in str(status).upper():
            pending.append(name)
    return pending


# ---------------------------------------------------------------------------
# Quality Metrics
# ---------------------------------------------------------------------------


def update_metrics(metrics):
    """Merge metrics into quality_metrics. Returns updated state."""
    state = read_state()
    if "quality_metrics" not in state:
        state["quality_metrics"] = {}
    state["quality_metrics"].update(metrics)
    return write_state(state)


def _add_grade_history(state, grade, tests, notes):
    """Append a grade history entry with today's date. Internal only — called by session_end().

    Mutates state dict in-place. Caller is responsible for write_state().
    """
    if "grade_history" not in state:
        state["grade_history"] = []

    state["grade_history"].append(
        {
            "date": str(date.today()),
            "grade": grade,
            "tests": tests,
            "notes": notes,
        }
    )


def check_quality_ratchet(new_grade):
    """Rule G-3: Quality Ratchet — returns False if grade would drop.

    Returns True if the new grade is equal to or better than current.
    """
    state = read_state()
    current_grade = state.get("quality_metrics", {}).get("overall_grade", "F")
    return _grade_rank(new_grade) <= _grade_rank(current_grade)


def _grade_rank(grade):
    """Return numeric rank for grade (lower = better)."""
    try:
        return GRADE_ORDER.index(grade)
    except ValueError:
        return len(GRADE_ORDER)  # Unknown grades rank worst


# ---------------------------------------------------------------------------
# Department Tracking (Section 3.5)
# ---------------------------------------------------------------------------


def update_department_status(dept_name, governed, ungoverned, status):
    """Update a department's governance counts. Returns updated state."""
    state = read_state()
    if "department_status" not in state:
        state["department_status"] = {}

    state["department_status"][dept_name] = {
        "governed": governed,
        "ungoverned": ungoverned,
        "status": status,
        "updated": str(date.today()),
    }
    return write_state(state)


def get_accountability_matrix():
    """Return list of department dicts from state."""
    state = read_state()
    dept_status = state.get("department_status", {})

    from qa_audit_types import DEPARTMENT_MAP

    matrix = []
    for dept_name, dept_info in DEPARTMENT_MAP.items():
        stored = dept_status.get(dept_name, {})
        matrix.append(
            {
                "name": dept_name,
                "agents": len(dept_info["agents"]),
                "governed": stored.get("governed", 0),
                "ungoverned": stored.get("ungoverned", len(dept_info["agents"])),
                "metric": dept_info["metric"],
                "status": stored.get("status", "UNKNOWN"),
            }
        )
    return matrix


# ---------------------------------------------------------------------------
# Delegation Economics
# ---------------------------------------------------------------------------


def update_delegation_economics(phase, ftal, cloud, savings, note):
    """Update delegation economics for a phase. Returns updated state."""
    state = read_state()
    if "delegation_economics" not in state:
        state["delegation_economics"] = {}
    if "per_phase" not in state["delegation_economics"]:
        state["delegation_economics"]["per_phase"] = {}

    state["delegation_economics"]["per_phase"][phase] = {
        "ftal_requests": ftal,
        "cloud_requests": cloud,
        "savings_usd": savings,
        "note": note,
    }

    total_ftal = sum(
        p.get("ftal_requests", 0) for p in state["delegation_economics"]["per_phase"].values()
    )
    total_cloud = sum(
        p.get("cloud_requests", 0) for p in state["delegation_economics"]["per_phase"].values()
    )
    total_savings = sum(
        p.get("savings_usd", 0) for p in state["delegation_economics"]["per_phase"].values()
    )
    state["delegation_economics"]["total_ftal_requests"] = total_ftal
    state["delegation_economics"]["total_cloud_codegen_requests"] = total_cloud
    state["delegation_economics"]["estimated_savings_usd"] = round(total_savings, 2)
    if total_ftal + total_cloud > 0:
        state["delegation_economics"]["delegation_ratio_pct"] = round(
            total_ftal / (total_ftal + total_cloud) * 100, 1
        )

    return write_state(state)


# ---------------------------------------------------------------------------
# Governance Gaps
# ---------------------------------------------------------------------------


def update_governance_gaps(gaps):
    """Update governance gaps dict. Returns updated state."""
    state = read_state()
    if "governance_gaps" not in state:
        state["governance_gaps"] = {}
    state["governance_gaps"].update(gaps)
    return write_state(state)


def get_blockers():
    """Return list of current blockers."""
    state = read_state()
    return state.get("blockers", [])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: pmo_state.py <command> [args]")
        print(
            "Commands: status, approve, metrics, history, "
            "departments, honest-assessment, session-end"
        )
        sys.exit(1)

    command = args[0]

    # Session/assessment commands — lazy import to avoid circular dependency
    if command == "status":
        from pmo_state_session import session_start
        print(session_start())

    elif command == "approve":
        if len(args) < 3:
            print("Usage: pmo_state.py approve <phase_name> <status_message>")
            sys.exit(1)
        phase_name = args[1]
        status_msg = " ".join(args[2:])
        approve_phase(phase_name, status_msg)
        print(f"Phase '{phase_name}' updated: {status_msg}")

    elif command == "metrics":
        # Parse --key value pairs (grade is EXCLUDED — computed only by qa_audit)
        metrics = {}
        i = 1
        while i < len(args):
            if args[i].startswith("--"):
                key = args[i][2:].replace("-", "_")
                if key in ("grade", "overall_grade"):
                    print(f"WARNING: --{key} ignored — grade is computed-only by qa_audit.py")
                    i += 2
                    continue
                if i + 1 < len(args):
                    val = args[i + 1]
                    try:
                        val = int(val)
                    except ValueError:
                        with contextlib.suppress(ValueError):
                            val = float(val)
                    metrics[key] = val
                    i += 2
                else:
                    i += 1
            else:
                i += 1
        if metrics:
            update_metrics(metrics)
            print(f"Metrics updated: {json.dumps(metrics)}")
        else:
            print("No metrics provided. Use --key value pairs (--grade is blocked).")

    elif command == "history":
        print("Grade history is managed by session-end. Use 'pmo_state.py session-end' instead.")

    elif command == "departments":
        try:
            matrix = get_accountability_matrix()
            print("\n=== Department Accountability Matrix ===\n")
            for d in matrix:
                print(
                    f"  {d['name']:<25} {d['status']:<15} "
                    f"G={d['governed']} U={d['ungoverned']}  {d['metric']}"
                )
        except ImportError:
            print("Cannot import qa_audit_types.py — run from backend/ directory")

    elif command == "honest-assessment":
        from pmo_state_session import generate_honest_assessment
        state = read_state()
        history = state.get("grade_history", [])
        if len(history) >= 2:
            prev = {
                "quality_metrics": {
                    "overall_grade": history[-2]["grade"],
                    "tests_total": history[-2]["tests"],
                }
            }
        else:
            prev = {"quality_metrics": {"overall_grade": "F", "tests_total": 0}}
        assessment = generate_honest_assessment(prev, state)
        print(assessment)

    elif command == "session-end":
        from pmo_state_session import session_end
        result = session_end()
        if isinstance(result, dict):
            if result.get("updated"):
                print(result["assessment"])
                print(f"\nSnapshot: {result['snapshot']}")
            else:
                print(f"Session end BLOCKED: {result.get('ratchet_violation', 'unknown')}")
                print(f"Snapshot: {result['snapshot']}")
        else:
            print(result)

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# Backward-compat lazy re-exports — session functions split to pmo_state_session.
# Uses __getattr__ so the import of pmo_state_session is deferred until first
# access, which avoids circular import at module load time.
# ---------------------------------------------------------------------------
_SESSION_ATTRS = frozenset({"generate_honest_assessment", "session_end", "session_start"})


def __getattr__(name):
    if name in _SESSION_ATTRS:
        from pmo_state_session import (  # noqa: PLC0415
            generate_honest_assessment,
            session_end,
            session_start,
        )
        _cache = {
            "generate_honest_assessment": generate_honest_assessment,
            "session_end": session_end,
            "session_start": session_start,
        }
        # Cache into module globals so subsequent accesses are O(1)
        globals().update(_cache)
        return _cache[name]
    raise AttributeError(f"module 'pmo_state' has no attribute {name!r}")
