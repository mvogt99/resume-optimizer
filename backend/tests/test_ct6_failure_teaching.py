"""CT-6: Unit tests for failure teaching to PersonaForge."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, "/home/mike/models/source/hybrid-ai-windows/applications/resume-optimizer/backend")

from agents.base_agent import BaseCareerAgent


class TestFailureTeaching:
    """Test that gap >= 30 triggers pf_remember with failure_teaching category."""

    def test_failure_teaching_called_on_high_gap(self, monkeypatch):
        """When gap >= 30, pf_remember is called with category='failure_teaching'."""
        agent = BaseCareerAgent()
        agent.agent_type = "resume_tailor"

        pf_remember_called = False
        call_args = None

        def mock_pf_remember(namespace, content, metadata):
            nonlocal pf_remember_called, call_args
            pf_remember_called = True
            call_args = {"namespace": namespace, "content": content, "metadata": metadata}

        # Mock pf_recall to avoid errors
        monkeypatch.setattr("agents.base_agent.pf_recall", lambda ns, query: None)
        monkeypatch.setattr("agents.base_agent.pf_remember", mock_pf_remember)

        # Mock call_llm_scored to return high gap (failure)
        def mock_llm_call(prompt, task_type="reasoning", max_tokens=4096):
            return "output text", {"f": 10, "t": 10, "a": 10, "gap": 65}

        with patch("agents.base_agent.call_llm_scored", side_effect=mock_llm_call):
            result = agent._call_llm("Test prompt", task_type="reasoning")

        assert pf_remember_called is True
        assert call_args is not None
        assert call_args["metadata"]["category"] == "failure_teaching"
        assert call_args["metadata"]["gap"] == 65
        assert "FAILED output" in call_args["content"]

    def test_no_failure_teaching_on_low_gap(self, monkeypatch):
        """When gap < 30, pf_remember is NOT called for failure teaching."""
        agent = BaseCareerAgent()
        agent.agent_type = "cover_letter"

        pf_remember_calls = []

        def mock_pf_remember(namespace, content, metadata):
            pf_remember_calls.append(metadata)

        monkeypatch.setattr("agents.base_agent.pf_recall", lambda ns, query: None)
        monkeypatch.setattr("agents.base_agent.pf_remember", mock_pf_remember)

        # Mock call_llm_scored to return low gap (success)
        def mock_llm_call(prompt, task_type="reasoning", max_tokens=4096):
            return "output text", {"f": 20, "t": 20, "a": 20, "gap": 20}

        with patch("agents.base_agent.call_llm_scored", side_effect=mock_llm_call):
            result = agent._call_llm("Test prompt", task_type="reasoning")

        # Should call pf_remember once with category='pattern' (success), not 'failure_teaching'
        assert len(pf_remember_calls) == 1
        assert pf_remember_calls[0]["category"] == "pattern"

    def test_failure_teaching_includes_metadata(self, monkeypatch):
        """Failure teaching metadata includes agent_type, task_type, gap, style_tags."""
        agent = BaseCareerAgent()
        agent.agent_type = "interview_coach"

        captured_metadata = None

        def mock_pf_remember(namespace, content, metadata):
            nonlocal captured_metadata
            captured_metadata = metadata

        monkeypatch.setattr("agents.base_agent.pf_recall", lambda ns, query: None)
        monkeypatch.setattr("agents.base_agent.pf_remember", mock_pf_remember)

        def mock_llm_call(prompt, task_type="reasoning", max_tokens=4096):
            return "output", {"f": 5, "t": 5, "a": 5, "gap": 85}

        with patch("agents.base_agent.call_llm_scored", side_effect=mock_llm_call):
            agent._call_llm("Prompt", task_type="reasoning")

        assert captured_metadata is not None
        assert captured_metadata["agent_type"] == "interview_coach"
        assert captured_metadata["task_type"] == "reasoning"
        assert captured_metadata["gap"] == 85
        assert "failure" in captured_metadata["style_tags"]

    def test_failure_teaching_survives_pf_error(self, monkeypatch):
        """If pf_remember raises, agent continues without propagating error."""
        agent = BaseCareerAgent()
        agent.agent_type = "career_advisor"

        def mock_pf_remember(*args, **kwargs):
            raise Exception("PersonaForge offline")

        monkeypatch.setattr("agents.base_agent.pf_recall", lambda ns, query: None)
        monkeypatch.setattr("agents.base_agent.pf_remember", mock_pf_remember)

        def mock_llm_call(prompt, task_type="reasoning", max_tokens=4096):
            return "output", {"gap": 50}

        with patch("agents.base_agent.call_llm_scored", side_effect=mock_llm_call):
            # Should not raise
            result = agent._call_llm("Test prompt")

        assert result == "output"
