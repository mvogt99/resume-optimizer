"""Tests for pmo_state.py — PMO Orchestrator, session state, quality ratchet.

15 tests, zero mocks, no skips.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BACKEND_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pmo_state  # noqa: E402


@pytest.fixture(autouse=True)
def _use_temp_state(tmp_path, monkeypatch):
    """Redirect STATE_FILE to a temp file so tests don't modify real state."""
    temp_state = tmp_path / "SESSION_STATE.json"
    # Seed with a minimal valid state
    temp_state.write_text(
        json.dumps(
            {
                "last_updated": "2026-03-07T00:00:00",
                "current_phase": 2,
                "current_phase_name": "Phase 2: Test Phase",
                "phase_status": {
                    "phase_1": "APPROVED",
                    "phase_2": "COMPLETE",
                    "phase_3": "PENDING",
                },
                "quality_metrics": {
                    "tests_total": 400,
                    "tests_passed": 400,
                    "tests_failed": 0,
                    "overall_grade": "B",
                    "tier_a_files": 24,
                    "tier_f_files": 0,
                    "total_test_files": 31,
                },
                "grade_history": [
                    {"date": "2026-03-06", "grade": "C+", "tests": 362, "notes": "Baseline"},
                    {"date": "2026-03-07", "grade": "B", "tests": 400, "notes": "Phase 2 complete"},
                ],
                "delegation_economics": {},
                "governance_gaps": {"qa_audit_py": "NOT BUILT"},
                "blockers": [],
                "next_action": "Build governance tools",
            }
        )
    )
    monkeypatch.setattr(pmo_state, "STATE_FILE", temp_state)


# ---------------------------------------------------------------------------
# State I/O
# ---------------------------------------------------------------------------


class TestStateIO:

    def test_read_state(self):
        """Returns dict with all required keys."""
        state = pmo_state.read_state()
        assert isinstance(state, dict)
        assert "current_phase" in state
        assert "phase_status" in state
        assert "quality_metrics" in state

    def test_read_state_has_quality_metrics(self):
        """quality_metrics with expected fields."""
        state = pmo_state.read_state()
        metrics = state["quality_metrics"]
        assert "tests_total" in metrics
        assert "tests_passed" in metrics
        assert "overall_grade" in metrics

    def test_write_state_atomic(self):
        """Write + read back → identical content."""
        state = pmo_state.read_state()
        state["test_marker"] = "written_by_test"
        pmo_state.write_state(state)

        reread = pmo_state.read_state()
        assert reread["test_marker"] == "written_by_test"
        assert "last_updated" in reread


# ---------------------------------------------------------------------------
# Phase Management
# ---------------------------------------------------------------------------


class TestPhaseManagement:

    def test_approve_phase(self):
        """Updates phase_status field."""
        pmo_state.approve_phase("phase_3", "COMPLETE — all tests pass")
        state = pmo_state.read_state()
        assert state["phase_status"]["phase_3"] == "COMPLETE — all tests pass"

    def test_is_phase_approved(self):
        """Returns bool correctly."""
        assert pmo_state.is_phase_approved("phase_1") is True
        assert pmo_state.is_phase_approved("phase_3") is False

    def test_get_pending_phases(self):
        """Returns list of PENDING phases."""
        pending = pmo_state.get_pending_phases()
        assert "phase_3" in pending
        assert "phase_1" not in pending


# ---------------------------------------------------------------------------
# Quality Metrics + Ratchet
# ---------------------------------------------------------------------------


class TestQualityMetrics:

    def test_update_metrics(self):
        """Merges metrics correctly."""
        pmo_state.update_metrics({"tests_total": 450, "new_field": "added"})
        state = pmo_state.read_state()
        assert state["quality_metrics"]["tests_total"] == 450
        assert state["quality_metrics"]["new_field"] == "added"
        # Original fields preserved
        assert "overall_grade" in state["quality_metrics"]

    def test_add_grade_history_via_internal(self):
        """_add_grade_history appends entry (internal function, called by session_end)."""
        state = pmo_state.read_state()
        pmo_state._add_grade_history(state, "B+", 420, "Test entry")
        pmo_state.write_state(state)

        reread = pmo_state.read_state()
        history = reread["grade_history"]
        assert len(history) >= 3  # 2 seeded + 1 added
        latest = history[-1]
        assert latest["grade"] == "B+"
        assert latest["tests"] == 420
        assert latest["notes"] == "Test entry"

    def test_quality_ratchet_blocks_downgrade(self):
        """B → C returns False (Rule G-3)."""
        assert pmo_state.check_quality_ratchet("C") is False
        assert pmo_state.check_quality_ratchet("C+") is False
        assert pmo_state.check_quality_ratchet("D") is False

    def test_quality_ratchet_allows_upgrade(self):
        """B → B+ returns True."""
        assert pmo_state.check_quality_ratchet("B+") is True
        assert pmo_state.check_quality_ratchet("A") is True
        assert pmo_state.check_quality_ratchet("B") is True  # same grade


# ---------------------------------------------------------------------------
# Department Tracking
# ---------------------------------------------------------------------------


class TestDepartmentTracking:

    def test_update_department_status(self):
        """Updates governed/ungoverned counts."""
        pmo_state.update_department_status("QA/Testing", 1, 0, "GOVERNED")
        state = pmo_state.read_state()
        dept = state["department_status"]["QA/Testing"]
        assert dept["governed"] == 1
        assert dept["ungoverned"] == 0
        assert dept["status"] == "GOVERNED"

    def test_get_accountability_matrix(self):
        """Returns all 8 departments."""
        matrix = pmo_state.get_accountability_matrix()
        assert len(matrix) == 8
        names = {d["name"] for d in matrix}
        assert "PMO" in names
        assert "QA/Testing" in names
        assert "DevOps/Frontend" in names


# ---------------------------------------------------------------------------
# Honest Assessment (Section 3.6 Mechanism 3)
# ---------------------------------------------------------------------------


class TestHonestAssessment:

    def test_honest_assessment_template(self):
        """Output matches Mechanism 3 format."""
        prev = {"quality_metrics": {"overall_grade": "C+", "tests_total": 362, "tier_a_files": 10}}
        curr = {
            "quality_metrics": {"overall_grade": "B", "tests_total": 400, "tier_a_files": 24},
            "phase_status": {"phase_3": "PENDING"},
            "governance_gaps": {},
        }
        assessment = pmo_state.generate_honest_assessment(prev, curr)
        assert "Session Honest Assessment" in assessment
        assert "Grade Progression" in assessment
        assert "IMPROVED" in assessment
        assert "C+" in assessment
        assert "B" in assessment

    def test_session_start_output(self):
        """Returns status summary with grade + pending."""
        output = pmo_state.session_start()
        assert "Session Start" in output
        assert "Grade:" in output
        assert "Phase:" in output

    def test_session_end_does_not_overwrite_existing_honest_assessment(self, monkeypatch, tmp_path):
        """If HONEST_ASSESSMENT.md already exists, session_end preserves it."""
        import qa_audit

        monkeypatch.setattr(qa_audit, "BASELINES_DIR", tmp_path / "baselines")

        # Pre-create HONEST_ASSESSMENT.md with custom content
        roadmap_dir = pmo_state.PROJECT_ROOT / "roadmap"
        roadmap_dir.mkdir(parents=True, exist_ok=True)
        legacy_path = roadmap_dir / "HONEST_ASSESSMENT.md"
        legacy_path.write_text("# My Curated Assessment\nDo not overwrite.", encoding="utf-8")

        pmo_state.session_end()

        content = legacy_path.read_text(encoding="utf-8")
        assert "My Curated Assessment" in content, "Existing HONEST_ASSESSMENT.md was overwritten"

    def test_session_end_creates_honest_assessment_when_missing(self, monkeypatch, tmp_path):
        """If HONEST_ASSESSMENT.md doesn't exist, session_end creates it."""
        import qa_audit

        monkeypatch.setattr(qa_audit, "BASELINES_DIR", tmp_path / "baselines")

        # Set starting grade to "F" so ratchet passes regardless of what audit_all() returns
        state = pmo_state.read_state()
        state["quality_metrics"]["overall_grade"] = "F"
        pmo_state.write_state(state)

        # Ensure roadmap dir exists but no legacy file
        roadmap_dir = pmo_state.PROJECT_ROOT / "roadmap"
        roadmap_dir.mkdir(parents=True, exist_ok=True)
        legacy_path = roadmap_dir / "HONEST_ASSESSMENT.md"
        if legacy_path.exists():
            legacy_path.unlink()

        pmo_state.session_end()

        assert legacy_path.exists(), "HONEST_ASSESSMENT.md should be created when missing"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCLI:

    def test_cli_status(self):
        """subprocess exits 0, output has grade."""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "pmo_state.py"), "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert "Grade:" in result.stdout


# ---------------------------------------------------------------------------
# Phase 2H-A: Single Source Grade + Snapshots
# ---------------------------------------------------------------------------


class TestSessionEndEnhanced:

    def test_session_end_creates_snapshot(self, tmp_path, monkeypatch):
        """After session_end, baselines dir has file."""
        import qa_audit

        monkeypatch.setattr(qa_audit, "BASELINES_DIR", tmp_path / "baselines")

        result = pmo_state.session_end()
        assert isinstance(result, dict)
        snapshot_path = result.get("snapshot", "")
        assert snapshot_path, "session_end should return snapshot path"
        assert Path(snapshot_path).exists(), f"Snapshot not created at {snapshot_path}"

    def test_session_end_refuses_downgrade(self, monkeypatch, tmp_path):
        """Seed state at B, audit returns C → session_end returns updated=False."""
        import qa_audit

        monkeypatch.setattr(qa_audit, "BASELINES_DIR", tmp_path / "baselines")

        # State is seeded at grade "B" by fixture
        # Provide a qa_result that computes to a lower grade
        result = pmo_state.session_end(
            qa_result_dict={
                "summary": {
                    "total_tests": 100,
                    "total_files": 5,
                    "overall_grade": "C",
                    "tier_counts": {"A": 0, "B": 0, "C": 5, "D": 0, "F": 0},
                    "content_pct": 30,
                    "db_pct": 10,
                },
                "files": [{"path": "test_x.py", "tier": "C"}],
            }
        )
        assert result["updated"] is False
        assert result["ratchet_violation"] is not None
        assert "downgrade" in result["ratchet_violation"]

    def test_session_end_adds_grade_history_on_success(self, monkeypatch, tmp_path):
        """Successful session_end adds grade_history entry."""
        import qa_audit

        monkeypatch.setattr(qa_audit, "BASELINES_DIR", tmp_path / "baselines")

        # Provide a result at same or better grade (B → B+)
        result = pmo_state.session_end(
            qa_result_dict={
                "summary": {
                    "total_tests": 450,
                    "total_files": 30,
                    "overall_grade": "B+",
                    "tier_counts": {"A": 5, "B": 20, "C": 5, "D": 0, "F": 0},
                    "content_pct": 60,
                    "db_pct": 30,
                },
                "files": [{"path": "test_x.py", "tier": "B"}],
            }
        )
        assert result["updated"] is True

        state = pmo_state.read_state()
        assert len(state["grade_history"]) >= 3  # 2 seeded + at least 1 new
        latest = state["grade_history"][-1]
        assert latest["grade"] == "B+"

    def test_metrics_cli_rejects_grade_arg(self):
        """pmo_state.py metrics --grade A is ignored."""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "pmo_state.py"), "metrics", "--grade", "A"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "ignored" in result.stdout.lower() or "WARNING" in result.stdout
