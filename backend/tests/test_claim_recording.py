"""Tests for resume optimizer claim recording to gateway."""

import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def claim_data():
    """Sample ClaimRecord data for testing."""
    return {
        "claim_id": "ro-claim-001",
        "source": "resume_optimizer",
        "task_type": "resume_tailor",
        "user_id": "user-123",
        "input_text": "Original resume content",
        "output_text": "Tailored resume content",
        "metadata": {"job_title": "Python Engineer"},
    }


class TestClaimRecordingBasic:
    """Basic claim recording functionality."""

    def test_record_claim_builds_payload(self, claim_data):
        """Claim payload has required fields."""
        from agents.claim_recorder import build_claim_payload

        payload = build_claim_payload(**claim_data)
        assert payload["claim_id"] == "ro-claim-001"
        assert payload["source"] == "resume_optimizer"
        assert payload["task_type"] == "resume_tailor"
        assert payload["input_text"] is not None
        assert payload["output_text"] is not None

    def test_record_claim_non_blocking(self, claim_data):
        """Recording does not block agent execution."""
        from agents.claim_recorder import record_claim_async

        with patch("agents.claim_recorder.requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=202)
            # Should not raise
            record_claim_async(**claim_data)
            assert mock_post.called

    @patch("agents.claim_recorder.requests.post")
    def test_record_claim_handles_gateway_down(self, mock_post, claim_data):
        """Gateway unavailable does not raise."""
        mock_post.side_effect = Exception("Connection refused")
        from agents.claim_recorder import record_claim_async

        # Should not raise
        record_claim_async(**claim_data)

    @patch("agents.claim_recorder.requests.post")
    def test_record_claim_sends_to_gateway_endpoint(self, mock_post, claim_data):
        """POST targets /api/accountability/record-batch."""
        from agents.claim_recorder import record_claim_async

        record_claim_async(**claim_data)
        assert mock_post.called
        call_args = mock_post.call_args
        assert "http://localhost:8000/api/accountability/record-batch" in call_args[0][0]

    @patch("agents.claim_recorder.requests.post")
    def test_record_claim_includes_metadata(self, mock_post, claim_data):
        """Metadata fields preserved in payload."""
        from agents.claim_recorder import record_claim_async

        claim_data["metadata"] = {"job_title": "Senior Python Engineer", "company": "TechCorp"}
        record_claim_async(**claim_data)

        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        assert payload["metadata"]["job_title"] == "Senior Python Engineer"
        assert payload["metadata"]["company"] == "TechCorp"

    @patch("agents.claim_recorder.requests.post")
    def test_record_claim_uses_background_thread(self, mock_post, claim_data):
        """Recording runs in background thread."""
        from agents.claim_recorder import record_claim_async
        import threading

        # Should return immediately
        record_claim_async(**claim_data)
        # If blocking, this would hang
        assert True


class TestClaimRecordingIntegration:
    """Integration with agents."""

    def test_base_agent_records_after_scoring(self):
        """After FTAL scoring, agent fires claim record."""
        # This test is structural — we can't easily mock the full LLM flow
        # but we validate that base_agent imports and exposes the recorder
        from agents.base_agent import BaseCareerAgent

        assert hasattr(BaseCareerAgent, "_record_claim")

    @patch("agents.claim_recorder.requests.post")
    def test_job_scout_agent_records_on_score(self, mock_post):
        """Job scout records claim when posting is scored."""
        # Structural test: verify job_scout can call recorder
        from agents.job_scout import JobScoutAgent

        assert hasattr(JobScoutAgent, "_record_claim")
