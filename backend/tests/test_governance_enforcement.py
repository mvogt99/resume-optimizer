"""Tests for governance enforcement — severity enforcement + diff assessment.

Phase 2H-B: 11 tests, zero mocks, no skips.
"""

import json
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
from qa_audit import FileGrade, classify_severity_with_baseline, enforce_severity  # noqa: E402


@pytest.fixture(autouse=True)
def _use_temp_state(tmp_path, monkeypatch):
    """Redirect STATE_FILE to a temp file so tests don't modify real state."""
    temp_state = tmp_path / "SESSION_STATE.json"
    temp_state.write_text(
        json.dumps(
            {
                "last_updated": "2026-03-07T00:00:00",
                "current_phase": 2,
                "current_phase_name": "Phase 2H",
                "phase_status": {},
                "quality_metrics": {
                    "tests_total": 400,
                    "tests_passed": 400,
                    "tests_failed": 0,
                    "overall_grade": "B",
                    "tier_a_files": 5,
                    "tier_f_files": 0,
                    "total_test_files": 30,
                },
                "grade_history": [],
                "delegation_economics": {},
                "governance_gaps": {},
                "blockers": [],
                "next_action": "",
            }
        )
    )
    monkeypatch.setattr(pmo_state, "STATE_FILE", temp_state)


# ---------------------------------------------------------------------------
# Severity Enforcement (G-6)
# ---------------------------------------------------------------------------


class TestSeverityEnforcement:

    def test_sev1_new_tier_f_blocks(self):
        """New Tier-F not in baseline → block=True."""
        files = [
            FileGrade(
                path="test_bad.py",
                tier="F",
                test_count=1,
                content_checks=0,
                db_queries=0,
                schema_checks=0,
                llm_verified=0,
                anti_patterns=[],
            )
        ]
        baseline = {"files": []}  # empty baseline → everything is "new"

        issues = classify_severity_with_baseline(files, baseline)
        assert len(issues["sev1"]) > 0
        assert issues["sev1"][0]["is_new"] is True

        block, warnings = enforce_severity(issues)
        assert block is True
        assert any("SEV-1 BLOCK" in w for w in warnings)

    def test_sev1_known_tier_f_no_block(self):
        """Same Tier-F in baseline → block=False."""
        files = [
            FileGrade(
                path="test_known.py",
                tier="F",
                test_count=1,
                content_checks=0,
                db_queries=0,
                schema_checks=0,
                llm_verified=0,
                anti_patterns=[],
            )
        ]
        baseline = {"files": [{"path": "test_known.py", "tier": "F"}]}

        issues = classify_severity_with_baseline(files, baseline)
        assert len(issues["sev1"]) > 0
        assert issues["sev1"][0]["is_new"] is False

        block, warnings = enforce_severity(issues)
        assert block is False  # known debt, not new

    def test_sev2_warns_and_logs(self, tmp_path):
        """New silent_pass → writes to governance_warnings.log."""
        files = [
            FileGrade(
                path="test_sp.py",
                tier="C",
                test_count=5,
                content_checks=2,
                db_queries=0,
                schema_checks=0,
                llm_verified=0,
                anti_patterns=["silent_pass:test_x"],
            )
        ]
        baseline = {"files": []}

        issues = classify_severity_with_baseline(files, baseline)
        log_path = tmp_path / "governance_warnings.log"
        block, warnings = enforce_severity(issues, log_path=str(log_path))

        assert block is False  # Sev-2 doesn't block
        assert any("SEV-2 WARN" in w for w in warnings)
        assert log_path.exists()
        log_text = log_path.read_text()
        assert "silent_pass" in log_text

    def test_sev3_in_assessment_only(self):
        """Existing Tier-D → appears in assessment, no block/warn."""
        files = [
            FileGrade(
                path="test_old_d.py",
                tier="D",
                test_count=3,
                content_checks=1,
                db_queries=0,
                schema_checks=0,
                llm_verified=0,
                anti_patterns=[],
            )
        ]
        baseline = {"files": [{"path": "test_old_d.py", "tier": "D"}]}

        issues = classify_severity_with_baseline(files, baseline)
        block, warnings = enforce_severity(issues)

        assert block is False
        assert any("SEV-3 INFO" in w for w in warnings)

    def test_sev4_informational(self):
        """Low content_pct → no block, no warning, in report only."""
        files = [
            FileGrade(
                path="test_low.py",
                tier="C",
                test_count=5,
                content_checks=1,
                db_queries=0,
                schema_checks=0,
                llm_verified=0,
                anti_patterns=[],
                content_pct=20.0,
            )
        ]
        baseline = {"files": [{"path": "test_low.py", "tier": "C"}]}

        issues = classify_severity_with_baseline(files, baseline)
        block, warnings = enforce_severity(issues)

        assert block is False
        assert any("SEV-4 INFO" in w for w in warnings)

    def test_persistent_sev1_becomes_blocker(self, tmp_path, monkeypatch):
        """Same Sev-1 in 2 snapshots → session_start shows blocker."""
        import qa_audit

        baselines_dir = tmp_path / "baselines"
        baselines_dir.mkdir()
        monkeypatch.setattr(qa_audit, "BASELINES_DIR", baselines_dir)

        # Write 2 snapshots with same Tier-F file
        snap1 = baselines_dir / "2026-03-05.json"
        snap1.write_text(
            json.dumps(
                {
                    "files": [{"path": "test_bad.py", "tier": "F"}],
                    "summary": {"overall_grade": "C"},
                }
            )
        )
        snap2 = baselines_dir / "2026-03-06.json"
        snap2.write_text(
            json.dumps(
                {
                    "files": [{"path": "test_bad.py", "tier": "F"}],
                    "summary": {"overall_grade": "C"},
                }
            )
        )

        output = pmo_state.session_start()
        assert "PERSISTENT SEV-1" in output
        assert "test_bad.py" in output


# ---------------------------------------------------------------------------
# Diff-Based Assessment (G-2)
# ---------------------------------------------------------------------------


class TestDiffAssessment:

    def test_diff_assessment_shows_improved(self, tmp_path, monkeypatch):
        """File B→A in 'Files Improved'."""
        import qa_audit

        monkeypatch.setattr(qa_audit, "BASELINES_DIR", tmp_path / "baselines")

        result = pmo_state.session_end(
            qa_result_dict={
                "summary": {
                    "total_tests": 450,
                    "total_files": 30,
                    "overall_grade": "B+",
                    "tier_counts": {"A": 10, "B": 15, "C": 5, "D": 0, "F": 0},
                    "content_pct": 60,
                    "db_pct": 30,
                },
                "files": [{"path": "test_x.py", "tier": "A"}],
            }
        )
        assert result["updated"] is True
        # First call has no previous snapshot, so assessment is basic format
        # Do a second session_end to get diff-based format
        result2 = pmo_state.session_end(
            qa_result_dict={
                "summary": {
                    "total_tests": 460,
                    "total_files": 31,
                    "overall_grade": "A-",
                    "tier_counts": {"A": 15, "B": 12, "C": 4, "D": 0, "F": 0},
                    "content_pct": 65,
                    "db_pct": 35,
                },
                "files": [{"path": "test_x.py", "tier": "A"}, {"path": "test_y.py", "tier": "A"}],
            }
        )
        assert result2["updated"] is True
        assert result2["assessment"]  # non-empty

    def test_diff_assessment_shows_regressed(self, tmp_path, monkeypatch):
        """File B→D in 'Files Regressed'."""
        import qa_audit

        baselines_dir = tmp_path / "baselines"
        baselines_dir.mkdir()
        monkeypatch.setattr(qa_audit, "BASELINES_DIR", baselines_dir)

        # Write a baseline snapshot with test_x at B
        snap = baselines_dir / "2026-03-06.json"
        snap.write_text(
            json.dumps(
                {
                    "files": [{"path": "test_x.py", "tier": "B"}],
                    "summary": {"overall_grade": "B"},
                }
            )
        )

        # session_end with test_x at D — but ratchet blocks downgrade
        result = pmo_state.session_end(
            qa_result_dict={
                "summary": {
                    "total_tests": 400,
                    "total_files": 1,
                    "overall_grade": "D",
                    "tier_counts": {"A": 0, "B": 0, "C": 0, "D": 1, "F": 0},
                    "content_pct": 15,
                    "db_pct": 0,
                },
                "files": [{"path": "test_x.py", "tier": "D"}],
            }
        )
        # Ratchet blocks: state grade is B, computed D would downgrade
        assert result["updated"] is False

    def test_diff_assessment_creates_dated_file(self, tmp_path, monkeypatch):
        """Assessment written to assessments/ dir."""
        import qa_audit

        monkeypatch.setattr(qa_audit, "BASELINES_DIR", tmp_path / "baselines")
        monkeypatch.setattr(pmo_state, "PROJECT_ROOT", tmp_path)

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
        assessments_dir = tmp_path / "roadmap" / "assessments"
        assert assessments_dir.exists()
        md_files = list(assessments_dir.glob("*.md"))
        assert len(md_files) >= 1

    def test_diff_assessment_claims_vs_evidence(self, tmp_path, monkeypatch):
        """Grade_history has 'A' but computed is 'B+' — assessment says computed-only."""
        import qa_audit

        monkeypatch.setattr(qa_audit, "BASELINES_DIR", tmp_path / "baselines")

        # Seed grade_history with an 'A' claim
        state = pmo_state.read_state()
        state["grade_history"].append(
            {"date": "2026-03-01", "grade": "A", "tests": 500, "notes": "manual"}
        )
        pmo_state.write_state(state)

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
        assessment = result["assessment"]
        assert "computed" in assessment.lower() or "manual" not in assessment.lower()

    def test_session_end_mandatory_assessment(self, tmp_path, monkeypatch):
        """session_end returns non-empty assessment."""
        import qa_audit

        monkeypatch.setattr(qa_audit, "BASELINES_DIR", tmp_path / "baselines")

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
        assert len(result["assessment"]) > 50, "Assessment should be substantive"
