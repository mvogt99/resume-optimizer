"""QA Audit — baseline snapshots and severity enforcement (Phase 2H).

Contains classify_severity_with_baseline(), enforce_severity(),
create_snapshot(), load_latest_snapshot(), diff_snapshots().
"""

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from qa_audit_types import ROADMAP_DIR, _tier_rank

BASELINES_DIR = ROADMAP_DIR / "baselines"


def _resolve_baselines_dir(override=None):
    """Return effective baselines dir, honouring monkeypatching of qa_audit.BASELINES_DIR.

    Checks qa_audit.BASELINES_DIR at call-time so tests that do
    monkeypatch.setattr(qa_audit, 'BASELINES_DIR', ...) continue to work.
    """
    if override is not None:
        return Path(override)
    try:
        import qa_audit as _qa  # lazy — qa_audit is already loaded by call-time
        return Path(_qa.BASELINES_DIR)
    except (ImportError, AttributeError):
        return BASELINES_DIR


# ---------------------------------------------------------------------------
# Severity Enforcement (Phase 2H — G-6)
# ---------------------------------------------------------------------------


def classify_severity_with_baseline(files, baseline=None):
    """Classify issues with baseline-relative 'is_new' flag.

    Returns {sev1: [{file, issue, is_new}], sev2: [...], ...}
    'New' = not present in baseline at same or worse severity.
    """
    baseline_files = {}
    if baseline:
        for f in baseline.get("files", []):
            baseline_files[f["path"]] = f["tier"]

    issues = {"sev1": [], "sev2": [], "sev3": [], "sev4": []}

    for f in files:
        was_in_baseline = f.path in baseline_files
        old_tier = baseline_files.get(f.path)

        if f.tier == "F":
            is_new = not was_in_baseline or old_tier != "F"
            issues["sev1"].append(
                {"file": f.path, "issue": "Tier-F quality failure", "is_new": is_new}
            )

        for ap in f.anti_patterns:
            if ap.startswith("always_true"):
                is_new = not was_in_baseline
                issues["sev1"].append({"file": f.path, "issue": ap, "is_new": is_new})
            elif ap.startswith("silent_pass") or ap.startswith("mock_usage"):
                is_new = not was_in_baseline
                issues["sev2"].append({"file": f.path, "issue": ap, "is_new": is_new})
            elif ap.startswith("broad_500"):
                issues["sev3"].append(
                    {"file": f.path, "issue": ap, "is_new": not was_in_baseline}
                )

        if f.tier == "D":
            issues["sev3"].append(
                {
                    "file": f.path,
                    "issue": "Tier-D low content validation",
                    "is_new": not was_in_baseline
                    or (old_tier and _tier_rank(old_tier) < _tier_rank("D")),
                }
            )

        if f.content_pct < 50 and f.tier not in ("D", "F"):
            issues["sev4"].append(
                {
                    "file": f.path,
                    "issue": f"content_pct={f.content_pct}%",
                    "is_new": not was_in_baseline,
                }
            )

    return issues


def enforce_severity(severity_issues, log_path=None):
    """Apply enforcement rules. Returns (should_block, warnings).

    Sev-1 new issues: block=True
    Sev-2 new issues: append to governance_warnings.log
    Sev-3/4: informational only
    """
    should_block = False
    warnings = []

    # Sev-1: new issues block
    for issue in severity_issues.get("sev1", []):
        if issue.get("is_new"):
            should_block = True
            warnings.append(f"SEV-1 BLOCK: {issue['file']} — {issue['issue']}")

    # Sev-2: new issues warn + log
    sev2_warnings = []
    for issue in severity_issues.get("sev2", []):
        if issue.get("is_new"):
            msg = f"SEV-2 WARN: {issue['file']} — {issue['issue']}"
            warnings.append(msg)
            sev2_warnings.append(msg)

    # Write warnings to log if any
    if sev2_warnings and log_path:
        log_file = Path(log_path)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as f:
            for w in sev2_warnings:
                f.write(f"{datetime.now(timezone.utc).isoformat()} {w}\n")

    # Sev-3/4: informational
    for issue in severity_issues.get("sev3", []):
        warnings.append(f"SEV-3 INFO: {issue['file']} — {issue['issue']}")
    for issue in severity_issues.get("sev4", []):
        warnings.append(f"SEV-4 INFO: {issue['file']} — {issue['issue']}")

    return should_block, warnings


# ---------------------------------------------------------------------------
# Baseline Snapshots (Phase 2H)
# ---------------------------------------------------------------------------


def create_snapshot(result=None, output_dir=None):
    """Serialize full AuditResult to roadmap/baselines/YYYY-MM-DD.json.

    Calls audit_all() if result not provided. Creates dir if needed.
    Snapshots are append-only — never modified.
    """
    if result is None:
        from qa_audit import audit_all
        result = audit_all()

    baselines = _resolve_baselines_dir(output_dir)
    baselines.mkdir(parents=True, exist_ok=True)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Append counter if file already exists (multiple snapshots per day)
    snap_path = baselines / f"{today}.json"
    counter = 1
    while snap_path.exists():
        counter += 1
        snap_path = baselines / f"{today}_{counter}.json"

    data = {
        "files": [asdict(f) for f in result.files],
        "summary": result.summary,
        "timestamp": result.timestamp,
    }
    snap_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return snap_path


def load_latest_snapshot(baselines_dir=None):
    """Scan roadmap/baselines/*.json, sort by filename (date), return latest.

    Returns None if no snapshots exist.
    """
    baselines = _resolve_baselines_dir(baselines_dir)
    if not baselines.exists():
        return None

    snapshots = sorted(baselines.glob("*.json"))
    # Exclude known_debt.json from snapshot list
    snapshots = [s for s in snapshots if s.name != "known_debt.json"]
    if not snapshots:
        return None

    latest = snapshots[-1]
    return json.loads(latest.read_text(encoding="utf-8"))


def diff_snapshots(previous, current):
    """Compare file-level tiers between two snapshots.

    Returns {improved: [{file, old_tier, new_tier}],
             regressed: [...], added: [...], removed: [...],
             grade_change: {old, new, direction}}
    """
    prev_files = {f["path"]: f["tier"] for f in previous.get("files", [])}
    curr_files = {f["path"]: f["tier"] for f in current.get("files", [])}

    improved = []
    regressed = []
    added = []
    removed = []

    # Files in both snapshots
    for path in set(prev_files) & set(curr_files):
        old_tier = prev_files[path]
        new_tier = curr_files[path]
        if _tier_rank(new_tier) < _tier_rank(old_tier):
            improved.append({"file": path, "old_tier": old_tier, "new_tier": new_tier})
        elif _tier_rank(new_tier) > _tier_rank(old_tier):
            regressed.append({"file": path, "old_tier": old_tier, "new_tier": new_tier})

    # New files
    for path in set(curr_files) - set(prev_files):
        added.append({"file": path, "tier": curr_files[path]})

    # Removed files
    for path in set(prev_files) - set(curr_files):
        removed.append({"file": path, "tier": prev_files[path]})

    # Grade change
    old_grade = previous.get("summary", {}).get("overall_grade", "F")
    new_grade = current.get("summary", {}).get("overall_grade", "F")
    if _grade_rank(new_grade) < _grade_rank(old_grade):
        direction = "IMPROVED"
    elif _grade_rank(new_grade) > _grade_rank(old_grade):
        direction = "REGRESSED"
    else:
        direction = "UNCHANGED"

    return {
        "improved": improved,
        "regressed": regressed,
        "added": added,
        "removed": removed,
        "grade_change": {"old": old_grade, "new": new_grade, "direction": direction},
    }


def _grade_rank(grade):
    """Return numeric rank for grade (lower = better). Used by diff_snapshots."""
    order = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F"]
    try:
        return order.index(grade)
    except ValueError:
        return len(order)
