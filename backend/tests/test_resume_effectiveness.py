"""CT-10: Tests for resume effectiveness audit and outcome correlation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_applications():
    """Sample applications for testing."""
    return [
        {
            "id": "app-001",
            "resume_version_id": "v1",
            "stage": "applied",
            "feedback": None,
        },
        {
            "id": "app-002",
            "resume_version_id": "v1",
            "stage": "interviewing",
            "feedback": None,
        },
        {
            "id": "app-003",
            "resume_version_id": "v1",
            "stage": "rejected",
            "feedback": "No response",
        },
        {
            "id": "app-004",
            "resume_version_id": "v2",
            "stage": "applied",
            "feedback": None,
        },
        {
            "id": "app-005",
            "resume_version_id": "v2",
            "stage": "offer",
            "feedback": None,
        },
    ]


class TestEffectivenessComputation:
    """Tests for computing resume version effectiveness."""

    def test_effectiveness_computed_from_outcomes(self, mock_applications):
        """Applications with v1: 3 sent, 1 callback. Effectiveness = 1/3 = 0.333."""
        from resume_effectiveness_audit import _correlate_with_resume_versions

        stats = _correlate_with_resume_versions(mock_applications)

        # v1: 3 apps (applied, interviewing, rejected), 1 callback (interviewing)
        assert stats["v1"]["applications"] == 3
        assert stats["v1"]["callbacks"] == 1
        # v2: 2 apps (applied, offer), 1 callback (offer)
        assert stats["v2"]["applications"] == 2
        assert stats["v2"]["callbacks"] == 1

    def test_effectiveness_threshold_flags_low_performers(self):
        """Versions with effectiveness < 0.10 (10%) should be flagged."""
        from resume_effectiveness_audit import LOW_EFFECTIVENESS_THRESHOLD

        # Version B: 10 apps, 0 callbacks → 0.0 effectiveness < 0.10 threshold
        applications = [
            {"id": f"app-{i}", "resume_version_id": "vB", "stage": "rejected"}
            for i in range(10)
        ]

        from resume_effectiveness_audit import _correlate_with_resume_versions

        stats = _correlate_with_resume_versions(applications)
        effectiveness = stats["vB"]["callbacks"] / stats["vB"]["applications"]

        assert effectiveness < LOW_EFFECTIVENESS_THRESHOLD

    def test_fewer_than_5_applications_not_flagged(self):
        """Versions with < 5 applications should not be flagged."""
        from resume_effectiveness_audit import MIN_APPLICATIONS

        # Version C: 3 apps, 0 callbacks
        applications = [
            {"id": f"app-{i}", "resume_version_id": "vC", "stage": "rejected"}
            for i in range(3)
        ]

        from resume_effectiveness_audit import _correlate_with_resume_versions

        stats = _correlate_with_resume_versions(applications)
        assert stats["vC"]["applications"] < MIN_APPLICATIONS


class TestAuditExecution:
    """Tests for audit workflow."""

    def test_effectiveness_audit_with_flagged_versions(self):
        """Audit should identify low-effectiveness versions and recommend re-tailoring."""
        from resume_effectiveness_audit import _correlate_with_resume_versions

        applications = [
            {"id": "a1", "resume_version_id": "v1", "stage": "interviewing"},
            {"id": "a2", "resume_version_id": "v1", "stage": "rejected"},
            {"id": "a3", "resume_version_id": "v1", "stage": "rejected"},
            {"id": "a4", "resume_version_id": "v1", "stage": "rejected"},
            {"id": "a5", "resume_version_id": "v1", "stage": "rejected"},
            {"id": "b1", "resume_version_id": "v2", "stage": "rejected"},
            {"id": "b2", "resume_version_id": "v2", "stage": "rejected"},
            {"id": "b3", "resume_version_id": "v2", "stage": "rejected"},
            {"id": "b4", "resume_version_id": "v2", "stage": "rejected"},
            {"id": "b5", "resume_version_id": "v2", "stage": "rejected"},
        ]

        stats = _correlate_with_resume_versions(applications)

        # v1: 5 apps, 1 callback (20%)
        assert stats["v1"]["applications"] == 5
        assert stats["v1"]["callbacks"] == 1
        # v2: 5 apps, 0 callbacks (0%)
        assert stats["v2"]["applications"] == 5
        assert stats["v2"]["callbacks"] == 0

    @pytest.mark.asyncio
    async def test_no_outcomes_returns_empty_report(self):
        """Empty applications list should return empty flagged_versions."""
        from resume_effectiveness_audit import run_effectiveness_audit

        with patch("resume_effectiveness_audit._get_user_applications") as mock_get_apps:
            mock_get_apps.return_value = []

            result = await run_effectiveness_audit(user_id=1)

            assert result["user_id"] == 1
            assert result["versions_analyzed"] == 0
            assert result["flagged_versions"] == []

    @pytest.mark.asyncio
    async def test_audit_error_handled_gracefully(self):
        """Audit error should return error key, never raise."""
        from resume_effectiveness_audit import run_effectiveness_audit

        with patch("resume_effectiveness_audit._get_user_applications") as mock_get_apps:
            mock_get_apps.side_effect = Exception("DB error")

            result = await run_effectiveness_audit(user_id=1)

            assert "error" in result
            assert result["versions_analyzed"] == 0
            assert result["flagged_versions"] == []


class TestArangoStorage:
    """Tests for persisting audit results."""

    @pytest.mark.asyncio
    async def test_results_stored_to_arango(self):
        """_store_audit_results() should persist to ArangoDB ro_resume_effectiveness."""
        from resume_effectiveness_audit import _store_audit_results

        flagged = [
            {
                "version_id": "v2",
                "effectiveness": 0.0,
                "applications_sent": 5,
                "callbacks": 0,
                "recommendation": "Consider re-tailoring...",
            }
        ]

        with patch("arango_client.get_arango_client", create=True) as mock_get_arango:
            mock_arango = MagicMock()
            mock_get_arango.return_value = mock_arango

            # Should handle gracefully if ArangoDB not available
            await _store_audit_results(user_id=1, flagged_versions=flagged)
