"""Tests for resume optimizer claim recording to gateway."""

import httpx
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

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

    @pytest.mark.asyncio
    async def test_record_claim_posts_to_gateway(self, monkeypatch, claim_data):
        """A valid claim is POSTed to the gateway endpoint with the claim id in the body."""
        from agents.claim_recorder import GATEWAY_URL, record_claim_async

        monkeypatch.setitem(sys.modules, "redis", None)

        fake_client = AsyncMock()
        fake_client.post.return_value = MagicMock(status_code=202, text="")
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=fake_client)
        ctx.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr("agents.claim_recorder.httpx.AsyncClient", MagicMock(return_value=ctx))

        await record_claim_async(**claim_data)

        assert fake_client.post.await_count == 1
        assert fake_client.post.await_args[0][0] == GATEWAY_URL
        # The gateway payload is {"source": ..., "claims": [{... "job_id": claim_id}]},
        # so the id travels as job_id inside the claims list, not at the top level.
        body = fake_client.post.await_args[1]["json"]
        assert body["source"] == claim_data["source"]
        assert body["claims"][0]["job_id"] == claim_data["claim_id"]

    @pytest.mark.asyncio
    async def test_record_claim_queues_when_gateway_errors(self, monkeypatch, claim_data):
        """A claim is not lost when the gateway is unreachable."""
        from agents.claim_recorder import record_claim_async

        monkeypatch.setitem(sys.modules, "redis", None)
        fake_client = AsyncMock()
        fake_client.post.side_effect = Exception("connection refused")
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=fake_client)
        ctx.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr("agents.claim_recorder.httpx.AsyncClient", MagicMock(return_value=ctx))
        queued = MagicMock()
        monkeypatch.setattr("agents.claim_recorder._queue_to_sqlite", queued)

        await record_claim_async(**claim_data)

        assert queued.call_count == 1
        assert queued.call_args[0][0] == claim_data["claim_id"]

    @pytest.mark.asyncio
    async def test_record_claim_treats_non_2xx_as_failure(self, monkeypatch, claim_data):
        """A 500 is failure, so the claim stays queued rather than counting as sent."""
        from agents.claim_recorder import record_claim_async

        monkeypatch.setitem(sys.modules, "redis", None)
        fake_client = AsyncMock()
        fake_client.post.return_value = MagicMock(status_code=500, text="boom")
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=fake_client)
        ctx.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr("agents.claim_recorder.httpx.AsyncClient", MagicMock(return_value=ctx))
        queued = MagicMock()
        monkeypatch.setattr("agents.claim_recorder._queue_to_sqlite", queued)

        await record_claim_async(**claim_data)

        assert fake_client.post.await_count >= 1
        assert queued.call_count == 1

    @pytest.mark.asyncio
    async def test_record_claim_rejects_empty_user_id(self, monkeypatch, claim_data):
        """An invalid claim is rejected outright, neither sent nor queued."""
        from agents.claim_recorder import record_claim_async

        monkeypatch.setitem(sys.modules, "redis", None)
        fake_client = AsyncMock()
        fake_client.post.return_value = MagicMock(status_code=202, text="")
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=fake_client)
        ctx.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr("agents.claim_recorder.httpx.AsyncClient", MagicMock(return_value=ctx))
        queued = MagicMock()
        monkeypatch.setattr("agents.claim_recorder._queue_to_sqlite", queued)

        claim_data["user_id"] = ""
        await record_claim_async(**claim_data)

        assert fake_client.post.await_count == 0
        assert queued.call_count == 0

    def test_record_claim_builds_payload(self, claim_data):
        """The gateway payload shape: the id is carried as job_id INSIDE the
        claims list, and metadata is serialised as a JSON string, not a dict.

        Supersedes six earlier tests that drove a synchronous httpx.post which
        this module has not had since it moved to an async client with an
        outbox; they patched a name that does not exist, never awaited the
        coroutine, and one asserted only `assert True`.
        """
        from agents.claim_recorder import build_claim_payload

        payload = build_claim_payload(**claim_data)
        assert payload["source"] == claim_data["source"]
        assert len(payload["claims"]) == 1
        claim = payload["claims"][0]
        assert claim["job_id"] == claim_data["claim_id"]
        assert claim["task_type"] == claim_data["task_type"]
        # Pinned explicitly: a caller expecting a dict here would mis-handle it.
        assert isinstance(claim["metadata"], str)
        assert json.loads(claim["metadata"])["job_title"] == claim_data["metadata"]["job_title"]



class TestClaimRecordingIntegration:
    """Integration with agents."""

    def test_base_agent_records_after_scoring(self):
        """After FTAL scoring, agent fires claim record."""
        # This test is structural — we can't easily mock the full LLM flow
        # but we validate that base_agent imports and exposes the recorder
        from agents.base_agent import BaseCareerAgent

        assert hasattr(BaseCareerAgent, "_record_claim")

    @patch("agents.claim_recorder.httpx.post")
    def test_job_scout_agent_records_on_score(self, mock_post):
        """Job scout records claim when posting is scored."""
        # Structural test: verify job_scout can call recorder
        from agents.job_scout import JobScoutAgent

        assert hasattr(JobScoutAgent, "_record_claim")
