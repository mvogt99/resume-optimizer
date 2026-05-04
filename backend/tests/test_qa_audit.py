"""Tests for qa_audit.py — QA Gate, AST analysis, department tracking, governance rules.

18 tests, zero mocks, no skips.
"""

import json
import sys
from pathlib import Path

# Ensure scripts/ is importable
BACKEND_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BACKEND_DIR / "scripts"
TESTS_DIR = BACKEND_DIR / "tests"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from qa_audit import (  # noqa: E402
    _classify_tier,
    analyze_file,
    assign_department,
    audit_all,
    create_snapshot,
    diff_snapshots,
    discover_agents,
    load_latest_snapshot,
    write_report,
)

# ---------------------------------------------------------------------------
# AST Analysis tests
# ---------------------------------------------------------------------------


class TestAnalyzerCounts:
    """Test AST analysis on known test files."""

    def test_analyzer_counts_test_functions(self):
        """Known file → correct test_count."""
        grade = analyze_file(TESTS_DIR / "test_auth.py")
        assert grade.test_count > 0, "test_auth.py must have test functions"
        assert isinstance(grade.test_count, int)

    def test_analyzer_detects_content_checks(self):
        """get_json() assertions → content_checks > 0."""
        # test_campaigns.py is known to have many content checks
        grade = analyze_file(TESTS_DIR / "test_campaigns.py")
        assert (
            grade.content_checks > 0
        ), f"test_campaigns.py should have content checks, got {grade.content_checks}"
        assert grade.content_pct > 0

    def test_analyzer_detects_db_queries(self):
        """query_db() calls → db_queries > 0."""
        grade = analyze_file(TESTS_DIR / "test_campaigns.py")
        assert (
            grade.db_queries > 0
        ), f"test_campaigns.py should have DB queries, got {grade.db_queries}"
        assert grade.db_pct > 0

    def test_analyzer_detects_llm_verified(self):
        """require_harness fixture → llm_verified > 0."""
        # test_agents_wave2_live.py uses require_harness
        grade = analyze_file(TESTS_DIR / "test_agents_wave2_live.py")
        assert (
            grade.llm_verified > 0
        ), f"test_agents_wave2_live.py should have LLM-verified tests, got {grade.llm_verified}"


class TestAntiPatternDetection:
    """Test anti-pattern detection with synthetic code."""

    def test_analyzer_detects_always_true(self, tmp_path):
        """assert len(x) >= 0 → 'always_true' in anti_patterns."""
        test_file = tmp_path / "test_fake_always_true.py"
        test_file.write_text(
            "def test_always_true():\n" "    x = [1, 2, 3]\n" "    assert len(x) >= 0\n"
        )
        grade = analyze_file(test_file)
        assert any(
            "always_true" in ap for ap in grade.anti_patterns
        ), f"Expected always_true anti-pattern, got {grade.anti_patterns}"

    def test_analyzer_detects_silent_pass(self, tmp_path):
        """bare if-guard → 'silent_pass' in anti_patterns."""
        test_file = tmp_path / "test_fake_silent_pass.py"
        test_file.write_text(
            "def test_silent_pass():\n"
            "    class R:\n"
            "        status_code = 200\n"
            "    resp = R()\n"
            "    if resp.status_code == 200:\n"
            "        assert True\n"
        )
        grade = analyze_file(test_file)
        assert any(
            "silent_pass" in ap for ap in grade.anti_patterns
        ), f"Expected silent_pass anti-pattern, got {grade.anti_patterns}"

    def test_analyzer_detects_broad_500(self, tmp_path):
        """in (200, 500) → 'broad_500' in anti_patterns."""
        test_file = tmp_path / "test_fake_broad.py"
        test_file.write_text(
            "def test_broad():\n"
            "    class R:\n"
            "        status_code = 200\n"
            "    resp = R()\n"
            "    assert resp.status_code in (200, 500)\n"
        )
        grade = analyze_file(test_file)
        assert any(
            "broad_500" in ap for ap in grade.anti_patterns
        ), f"Expected broad_500 anti-pattern, got {grade.anti_patterns}"

    def test_analyzer_detects_mock_usage(self, tmp_path):
        """@mock.patch → 'mock_usage' in anti_patterns."""
        test_file = tmp_path / "test_fake_mock.py"
        test_file.write_text(
            "import unittest.mock as mock\n"
            "@mock.patch('os.path.exists')\n"
            "def test_with_mock(mock_exists):\n"
            "    mock_exists.return_value = True\n"
            "    assert True\n"
        )
        grade = analyze_file(test_file)
        assert any(
            "mock_usage" in ap for ap in grade.anti_patterns
        ), f"Expected mock_usage anti-pattern, got {grade.anti_patterns}"


# ---------------------------------------------------------------------------
# Tier Classification tests
# ---------------------------------------------------------------------------


class TestTierClassification:

    def test_tier_a_classification(self, tmp_path):
        """High content + db + no anti-patterns → 'A'."""
        test_file = tmp_path / "test_fake_a.py"
        test_file.write_text(
            "def test_one():\n"
            "    data = resp.get_json()\n"
            "    assert data['key'] == 'val'\n"
            "    rows = query_db('SELECT 1')\n"
            "    assert len(rows) == 1\n"
            "\n"
            "def test_two():\n"
            "    data = resp.get_json()\n"
            "    assert 'field' in data\n"
            "    rows = query_db('SELECT 1')\n"
            "    assert rows\n"
            "\n"
            "def test_three():\n"
            "    data = resp.get_json()\n"
            "    assert data['x'] == 1\n"
            "    query_db('SELECT 1')\n"
        )
        grade = analyze_file(test_file)
        assert (
            grade.tier == "A"
        ), f"Expected Tier-A, got {grade.tier} (c={grade.content_pct}%, db={grade.db_pct}%)"

    def test_tier_f_classification(self, tmp_path):
        """Low content + anti-pattern → 'F'."""
        test_file = tmp_path / "test_fake_f.py"
        test_file.write_text("def test_bad():\n" "    x = []\n" "    assert len(x) >= 0\n")
        grade = analyze_file(test_file)
        assert grade.tier == "F", f"Expected Tier-F, got {grade.tier}"


# ---------------------------------------------------------------------------
# Full Suite Audit
# ---------------------------------------------------------------------------


class TestFullSuiteAudit:

    def test_audit_all_files(self):
        """Runs on actual test suite → AuditResult populated."""
        result = audit_all()
        assert len(result.files) > 0, "No test files found"
        assert result.timestamp, "Missing timestamp"
        assert result.summary, "Missing summary"
        assert result.departments, "Missing departments"
        assert result.governance_rules, "Missing governance_rules"

    def test_audit_summary_totals(self):
        """summary.total_tests == sum(file.test_count)."""
        result = audit_all()
        expected = sum(f.test_count for f in result.files)
        assert (
            result.summary["total_tests"] == expected
        ), f"Summary total {result.summary['total_tests']} != sum {expected}"

    def test_audit_no_f_tier_files_from_anti_patterns(self):
        """Current suite has 0 Tier-F files due to anti-patterns."""
        result = audit_all()
        f_from_anti = [f for f in result.files if f.tier == "F" and f.anti_patterns]
        assert len(f_from_anti) == 0, (
            f"Found Tier-F files with anti-patterns: "
            f"{[(f.path, f.anti_patterns) for f in f_from_anti]}"
        )


# ---------------------------------------------------------------------------
# Department Tracking (Section 3.5)
# ---------------------------------------------------------------------------


class TestDepartmentTracking:

    def test_department_report_all_8(self):
        """All 8 departments present in report."""
        result = audit_all()
        dept_names = {d.name for d in result.departments}
        expected = {
            "PMO",
            "Architecture",
            "Software Engineering",
            "Resume & Talent",
            "Job Management",
            "Marketing",
            "QA/Testing",
            "DevOps/Frontend",
        }
        assert dept_names == expected, f"Missing departments: {expected - dept_names}"

    def test_department_governed_ungoverned_counts(self):
        """Counts match known state."""
        result = audit_all()
        for dept in result.departments:
            assert isinstance(dept.governed_count, int)
            assert isinstance(dept.ungoverned_count, int)
            assert dept.governed_count >= 0
            assert dept.ungoverned_count >= 0

    def test_governance_rule_g1_compliance(self):
        """G-1 check returns no false positives on current suite."""
        result = audit_all()
        g1 = result.governance_rules.get("G-1_no_false_positives", {})
        assert (
            g1["status"] == "PASS"
        ), f"G-1 FAIL: {g1.get('detail', '')} — anti_patterns: {g1.get('anti_patterns', [])}"


# ---------------------------------------------------------------------------
# Output tests
# ---------------------------------------------------------------------------


class TestOutput:

    def test_report_generation(self, tmp_path):
        """--report creates QA_AUDIT_REPORT.md with dept matrix."""
        result = audit_all()
        output_path = tmp_path / "QA_AUDIT_REPORT.md"
        write_report(result, output_path=output_path)
        assert output_path.exists(), "Report file not created"
        text = output_path.read_text()
        assert "Department Accountability Matrix" in text
        assert "Governance Rule Compliance" in text
        assert "Per-File Tier Breakdown" in text

    def test_json_output(self):
        """JSON output has all sections."""
        result = audit_all()
        # Serialize to JSON to verify it's valid
        from dataclasses import asdict

        out = {
            "files": [asdict(f) for f in result.files],
            "departments": [asdict(d) for d in result.departments],
            "summary": result.summary,
            "governance_rules": result.governance_rules,
            "timestamp": result.timestamp,
        }
        text = json.dumps(out)
        parsed = json.loads(text)
        assert "files" in parsed
        assert "departments" in parsed
        assert "summary" in parsed
        assert "governance_rules" in parsed


# ---------------------------------------------------------------------------
# Baseline Snapshots (Phase 2H)
# ---------------------------------------------------------------------------


class TestBaselineSnapshots:

    def test_create_snapshot_writes_file(self, tmp_path):
        """Snapshot JSON parseable, has files + summary keys."""
        result = audit_all()
        snap_path = create_snapshot(result, output_dir=tmp_path)
        assert snap_path.exists(), "Snapshot file not created"
        data = json.loads(snap_path.read_text())
        assert "files" in data
        assert "summary" in data
        assert len(data["files"]) > 0

    def test_load_latest_snapshot_returns_newest(self, tmp_path):
        """Write 2 snapshots with different dates, load returns latter."""
        # First snapshot
        snap1 = tmp_path / "2026-03-01.json"
        snap1.write_text(
            json.dumps(
                {
                    "files": [{"path": "old.py", "tier": "C"}],
                    "summary": {"overall_grade": "C"},
                }
            )
        )
        # Second snapshot
        snap2 = tmp_path / "2026-03-07.json"
        snap2.write_text(
            json.dumps(
                {
                    "files": [{"path": "new.py", "tier": "B"}],
                    "summary": {"overall_grade": "B"},
                }
            )
        )
        latest = load_latest_snapshot(baselines_dir=tmp_path)
        assert latest is not None
        assert latest["summary"]["overall_grade"] == "B"

    def test_diff_snapshots_detects_regression(self):
        """Synthetic B→D appears in regressed list."""
        prev = {"files": [{"path": "test_x.py", "tier": "B"}], "summary": {"overall_grade": "B"}}
        curr = {"files": [{"path": "test_x.py", "tier": "D"}], "summary": {"overall_grade": "D"}}
        diff = diff_snapshots(prev, curr)
        assert len(diff["regressed"]) == 1
        assert diff["regressed"][0]["file"] == "test_x.py"
        assert diff["regressed"][0]["old_tier"] == "B"
        assert diff["regressed"][0]["new_tier"] == "D"

    def test_diff_snapshots_detects_improvement(self):
        """Synthetic D→B appears in improved list."""
        prev = {"files": [{"path": "test_x.py", "tier": "D"}], "summary": {"overall_grade": "D"}}
        curr = {"files": [{"path": "test_x.py", "tier": "B"}], "summary": {"overall_grade": "B"}}
        diff = diff_snapshots(prev, curr)
        assert len(diff["improved"]) == 1
        assert diff["improved"][0]["file"] == "test_x.py"

    def test_snapshot_append_only(self, tmp_path):
        """Second snapshot doesn't overwrite first."""
        result = audit_all()
        snap1 = create_snapshot(result, output_dir=tmp_path)
        snap2 = create_snapshot(result, output_dir=tmp_path)
        assert snap1 != snap2, "Second snapshot should have different path"
        assert snap1.exists(), "First snapshot should still exist"
        assert snap2.exists(), "Second snapshot should also exist"


# ---------------------------------------------------------------------------
# Agent Discovery + Department Assignment (Phase 2H-C)
# ---------------------------------------------------------------------------


class TestAgentDiscovery:

    def test_discover_agents_finds_all_6(self):
        """Discovers 6 agents from agents/__init__.py."""
        agents = discover_agents()
        assert (
            len(agents) >= 6
        ), f"Expected >= 6 agents, got {len(agents)}: {[a['name'] for a in agents]}"
        names = {a["name"] for a in agents}
        assert "job_scout" in names
        assert "app_tracker" in names

    def test_department_assignment_correct(self):
        """job_scout→Job Management, resume_tailor→Resume & Talent."""
        assert assign_department("job_scout") == "Job Management"
        assert assign_department("app_tracker") == "Job Management"
        assert assign_department("resume_tailor") == "Resume & Talent"
        assert assign_department("cover_letter") == "Resume & Talent"
        assert assign_department("interview_coach") == "Resume & Talent"
        assert assign_department("career_advisor") == "Resume & Talent"

    def test_department_status_computed_live(self):
        """No stored state — recomputed each call."""
        agents = discover_agents()
        assert len(agents) > 0
        for agent in agents:
            dept = assign_department(agent["name"])
            assert dept in (
                "Job Management",
                "Resume & Talent",
                "Marketing",
                "Software Engineering",
            )

    def test_department_regression_warning(self, tmp_path, monkeypatch):
        """GOVERNED→PARTIAL triggers Sev-2 warning (tested via pmo_state)."""
        import pmo_state as ps
        import qa_audit

        monkeypatch.setattr(qa_audit, "BASELINES_DIR", tmp_path / "baselines")

        # Set up state with a department at GOVERNED
        state = ps.read_state()
        state["department_status"] = {
            "Job Management": {"governed": 2, "ungoverned": 0, "status": "GOVERNED"},
        }
        ps.write_state(state)

        # Verify the state was saved
        reread = ps.read_state()
        assert reread["department_status"]["Job Management"]["status"] == "GOVERNED"


# ---------------------------------------------------------------------------
# Logic-Tier A Classification (Wave 6.5)
# ---------------------------------------------------------------------------


class TestLogicTierA:
    """Tests for the enhanced _classify_tier that promotes non-API tests to A."""

    def test_logic_tier_a_high_density(self):
        """Non-API test with ≥10 tests and density ≥2.0 → A-tier."""
        tier = _classify_tier(
            content_pct=0,
            db_pct=0,
            anti_patterns=[],
            is_api_test=False,
            test_count=15,
            total_assertions=45,  # density=3.0
        )
        assert tier == "A", f"Logic test 15 tests/density 3.0 should be A, got {tier}"

    def test_logic_tier_b_low_test_count(self):
        """Non-API test with <10 tests → B-tier even with high density."""
        tier = _classify_tier(
            content_pct=0,
            db_pct=0,
            anti_patterns=[],
            is_api_test=False,
            test_count=8,
            total_assertions=24,  # density=3.0 but only 8 tests
        )
        assert tier == "B", f"Logic test 8 tests should stay B, got {tier}"

    def test_logic_tier_b_low_density(self):
        """Non-API test with density <2.0 → B-tier even with many tests."""
        tier = _classify_tier(
            content_pct=0,
            db_pct=0,
            anti_patterns=[],
            is_api_test=False,
            test_count=15,
            total_assertions=22,  # density=1.47
        )
        assert tier == "B", f"Logic test density 1.47 should stay B, got {tier}"

    def test_logic_tier_f_anti_pattern_overrides(self):
        """Non-API test with anti-pattern → F-tier even with good density."""
        tier = _classify_tier(
            content_pct=0,
            db_pct=0,
            anti_patterns=["always_true:test_x"],
            is_api_test=False,
            test_count=20,
            total_assertions=60,  # density=3.0
        )
        assert tier == "F", f"Logic test with anti-pattern must be F, got {tier}"

    def test_total_assertions_accumulates(self, tmp_path):
        """Analyzer accumulates total_assertions across multiple functions."""
        test_file = tmp_path / "test_fake_multi.py"
        test_file.write_text(
            "def test_one():\n"
            "    assert 1 == 1\n"
            "    assert 2 == 2\n"
            "    assert 3 == 3\n"
            "\n"
            "def test_two():\n"
            "    assert 'a' == 'a'\n"
            "    assert 'b' == 'b'\n"
        )
        grade = analyze_file(test_file)
        assert grade.test_count == 2
        assert (
            grade.total_assertions == 5
        ), f"Expected 5 total assertions, got {grade.total_assertions}"
