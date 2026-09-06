"""CT-9: Tests for interview coaching effectiveness and deferred PF confidence."""


import pytest


@pytest.fixture
def tracker():
    """Create an InterviewEffectivenessTracker for testing."""
    from agents.interview_effectiveness import InterviewEffectivenessTracker

    return InterviewEffectivenessTracker(
        session_id="session-test-001", user_id=1, persona="hiring_manager"
    )


class TestInterviewEffectiveness:
    """Tests for effectiveness metric computation."""

    def test_answer_score_improvement_boosts_confidence(self, tracker):
        """Score improvement [5.0 → 7.0] should compute effectiveness=0.40 and boost."""
        tracker.record_answer_score(5.0)
        tracker.record_answer_score(7.0)
        result = tracker.complete_session()

        assert result["pf_action"] == "boost"
        assert result["pf_magnitude"] == 0.05
        assert result["teaching_flag"] is False
        assert result["effectiveness"] == pytest.approx(0.40, abs=0.01)

    def test_answer_score_decline_penalizes_confidence(self, tracker):
        """Score decline [7.0 → 5.0] should compute effectiveness < 0 and penalize."""
        tracker.record_answer_score(7.0)
        tracker.record_answer_score(5.0)
        result = tracker.complete_session()

        assert result["pf_action"] == "penalize"
        assert result["pf_magnitude"] == -0.05
        assert result["teaching_flag"] is True
        assert result["effectiveness"] == pytest.approx(-0.286, abs=0.01)

    def test_effectiveness_metric_computed_correctly(self, tracker):
        """Multiple score sequences should compute effectiveness correctly."""
        # Test case: [6, 8, 10] → 0.667
        tracker.record_answer_score(6.0)
        tracker.record_answer_score(8.0)
        tracker.record_answer_score(10.0)
        effectiveness = tracker.compute_effectiveness()
        assert effectiveness == pytest.approx((10 - 6) / 6, abs=0.01)

    def test_insufficient_data_returns_none(self, tracker):
        """Single answer should return None (need >= 2 for metric)."""
        tracker.record_answer_score(5.0)
        effectiveness = tracker.compute_effectiveness()
        assert effectiveness is None

    def test_confidence_deferred_until_session_end(self, tracker):
        """Tracker should defer verdict until complete_session() called."""
        tracker.record_answer_score(5.0)
        tracker.record_answer_score(7.0)

        assert tracker.is_completed is False
        result = tracker.complete_session()

        assert tracker.is_completed is True
        assert "pf_action" in result
        assert "effectiveness" in result
        assert "session_id" in result
        assert result["session_id"] == "session-test-001"


class TestPFIntegration:
    """Tests for PersonaForge feedback integration."""

    def test_pf_boost_applied_on_positive_effectiveness(self):
        """Positive effectiveness should set pf_action=boost with magnitude=0.05."""
        from agents.interview_effectiveness import InterviewEffectivenessTracker

        tracker = InterviewEffectivenessTracker(
            session_id="session-pf-001", user_id=1, persona="hiring_manager"
        )
        tracker.record_answer_score(5.0)
        tracker.record_answer_score(7.5)
        result = tracker.complete_session()

        assert result["pf_action"] == "boost"
        assert result["pf_magnitude"] == 0.05

    @pytest.mark.asyncio
    async def test_pf_unavailable_handled_gracefully(self):
        """PersonaForge client exception should be logged, not raised."""
        from agents.interview_effectiveness import InterviewEffectivenessTracker

        tracker = InterviewEffectivenessTracker(
            session_id="session-pf-error", user_id=1, persona="hiring_manager"
        )
        tracker.record_answer_score(7.0)
        tracker.record_answer_score(5.0)
        tracker.is_completed = True

        # Should handle gracefully even if PF not available
        # (No exception should be raised)
        result = tracker.complete_session()
        assert result["pf_action"] == "penalize"

    @pytest.mark.asyncio
    async def test_pf_not_applied_if_session_not_completed(self):
        """apply_pf_feedback() should skip if is_completed=False."""
        from agents.interview_effectiveness import InterviewEffectivenessTracker

        tracker = InterviewEffectivenessTracker(
            session_id="session-incomplete", user_id=1, persona="hiring_manager"
        )
        tracker.record_answer_score(5.0)
        tracker.record_answer_score(7.0)

        # is_completed is False, so apply_pf_feedback should exit early
        assert tracker.is_completed is False
        # Calling it should be safe and not raise
        await tracker.apply_pf_feedback(pf_memory_ids=["mem-001"])


class TestTrackerManagement:
    """Tests for global tracker registry."""

    def test_create_and_retrieve_tracker(self):
        """create_tracker() should register and get_tracker() should retrieve."""
        from agents.interview_effectiveness import (
            create_tracker,
            get_tracker,
            remove_tracker,
        )

        tracker = create_tracker("sess-mgmt-001", user_id=1, persona="technical")
        assert tracker is not None
        assert tracker.session_id == "sess-mgmt-001"

        retrieved = get_tracker("sess-mgmt-001")
        assert retrieved is tracker

        remove_tracker("sess-mgmt-001")
        assert get_tracker("sess-mgmt-001") is None
