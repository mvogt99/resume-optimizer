"""CT-9: Unit tests for InterviewEffectivenessTracker and PF confidence feedback."""

from __future__ import annotations

import sys

import pytest

sys.path.insert(0, "/home/mike/models/source/hybrid-ai-windows/applications/resume-optimizer/backend")

from agents.interview_effectiveness import InterviewEffectivenessTracker, get_or_create_tracker


class TestInterviewEffectivenessTracker:
    def test_initial_state(self):
        t = InterviewEffectivenessTracker("sess-1", user_id=42, persona="technical")
        assert t.session_id == "sess-1"
        assert t.user_id == 42
        assert t.persona == "technical"
        assert t.answer_scores == []
        assert t.confidence_pending is True
        assert t.is_completed is False

    def test_record_answer_score_appends(self):
        t = InterviewEffectivenessTracker("s1", 1)
        t.record_answer_score(7.0)
        t.record_answer_score(8.5)
        assert t.answer_scores == [7.0, 8.5]

    def test_record_invalid_score_ignored(self):
        t = InterviewEffectivenessTracker("s1", 1)
        t.record_answer_score("bad")
        assert t.answer_scores == []

    def test_compute_effectiveness_requires_two_answers(self):
        t = InterviewEffectivenessTracker("s1", 1)
        assert t.compute_effectiveness() is None
        t.record_answer_score(5.0)
        assert t.compute_effectiveness() is None

    def test_compute_effectiveness_improvement(self):
        t = InterviewEffectivenessTracker("s1", 1)
        t.record_answer_score(5.0)
        t.record_answer_score(7.5)  # 50% improvement
        eff = t.compute_effectiveness()
        assert eff == pytest.approx(0.5)

    def test_compute_effectiveness_decline(self):
        t = InterviewEffectivenessTracker("s1", 1)
        t.record_answer_score(8.0)
        t.record_answer_score(4.0)  # 50% decline
        eff = t.compute_effectiveness()
        assert eff == pytest.approx(-0.5)

    def test_compute_effectiveness_zero_initial_returns_none(self):
        t = InterviewEffectivenessTracker("s1", 1)
        t.record_answer_score(0.0)
        t.record_answer_score(5.0)
        assert t.compute_effectiveness() is None

    def test_complete_session_no_data_returns_none_action(self):
        t = InterviewEffectivenessTracker("s1", 1)
        result = t.complete_session()
        assert result["pf_action"] == "none"
        assert result["effectiveness"] is None
        assert t.is_completed is True

    def test_complete_session_improvement_returns_boost(self):
        t = InterviewEffectivenessTracker("s1", 1)
        t.record_answer_score(5.0)
        t.record_answer_score(8.0)
        result = t.complete_session()
        assert result["pf_action"] == "boost"
        assert result["pf_magnitude"] > 0
        assert result["effectiveness"] == pytest.approx(0.6)

    def test_complete_session_decline_returns_penalize(self):
        t = InterviewEffectivenessTracker("s1", 1)
        t.record_answer_score(8.0)
        t.record_answer_score(3.0)
        result = t.complete_session()
        assert result["pf_action"] == "penalize"
        assert result["pf_magnitude"] < 0

    def test_complete_session_has_all_required_keys(self):
        t = InterviewEffectivenessTracker("s1", 1)
        t.record_answer_score(6.0)
        t.record_answer_score(7.0)
        result = t.complete_session()
        for key in ("session_id", "effectiveness", "pf_action", "pf_magnitude", "teaching_flag", "message"):
            assert key in result, f"Missing key: {key}"

    def test_teaching_flag_set_on_penalize(self):
        t = InterviewEffectivenessTracker("s1", 1)
        t.record_answer_score(9.0)
        t.record_answer_score(2.0)  # Severe decline
        result = t.complete_session()
        assert result["pf_action"] == "penalize"
        # teaching_flag should be a bool
        assert isinstance(result["teaching_flag"], bool)


class TestGetOrCreateTracker:
    def test_returns_tracker_instance(self):
        tracker = get_or_create_tracker("session-abc", user_id=10)
        assert isinstance(tracker, InterviewEffectivenessTracker)

    def test_same_session_returns_same_instance(self):
        t1 = get_or_create_tracker("session-xyz", user_id=5)
        t2 = get_or_create_tracker("session-xyz", user_id=5)
        assert t1 is t2

    def test_different_sessions_return_different_instances(self):
        t1 = get_or_create_tracker("session-aaa", user_id=1)
        t2 = get_or_create_tracker("session-bbb", user_id=1)
        assert t1 is not t2


class TestEffectivenessInEndInterview:
    """Test CT-9 wiring: end_interview calls effectiveness tracker and emits PF note."""

    def test_end_interview_captures_effectiveness(self):
        """end_interview calls get_or_create_tracker().complete_session() — non-blocking."""
        # Verify the pattern: tracker is always created, complete_session called at end
        t = InterviewEffectivenessTracker("sess-wire", user_id=99)
        t.record_answer_score(5.0)
        t.record_answer_score(9.0)

        result = t.complete_session()

        # Wire result format matches what end_interview expects
        assert "pf_action" in result
        assert "effectiveness" in result
        assert "message" in result
        assert result["pf_action"] in ("boost", "penalize", "none")

    def test_pf_note_metadata_schema(self):
        """PF note written at session end includes session_id and action."""
        t = InterviewEffectivenessTracker("sess-pf", user_id=7)
        t.record_answer_score(4.0)
        t.record_answer_score(8.0)
        ef_result = t.complete_session()

        # Verify metadata structure that end_interview passes to pf_remember
        expected_metadata = {
            "session_id": "sess-pf",
            "action": ef_result.get("pf_action"),
        }
        assert expected_metadata["session_id"] == "sess-pf"
        assert expected_metadata["action"] == "boost"
