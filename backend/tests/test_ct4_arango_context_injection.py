"""CT-4: Unit tests for ArangoDB knowledge context injection into LLM prompts."""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, "/home/mike/models/source/hybrid-ai-windows/applications/resume-optimizer/backend")

from agents.base_agent import BaseCareerAgent


class TestArangoContextInjection:
    """Test that _get_arango_context prepends knowledge graph data to prompts."""

    def test_get_arango_context_called_by_call_llm(self, monkeypatch):
        """_call_llm invokes _get_arango_context before LLM call."""
        agent = BaseCareerAgent()
        agent.agent_type = "resume_tailor"
        agent._current_user_id = "test_user_123"

        arango_ctx_called = False
        arango_ctx_result = "Test context: user has 3 projects in ArangoDB"

        original_get_ctx = agent._get_arango_context

        def mock_get_ctx(user_id, agent_type, max_tokens=500):
            nonlocal arango_ctx_called
            arango_ctx_called = True
            assert user_id == "test_user_123"
            assert agent_type == "resume_tailor"
            return arango_ctx_result

        monkeypatch.setattr(agent, "_get_arango_context", mock_get_ctx)

        # Mock the actual LLM call
        with patch("agents.base_agent.call_llm_scored", return_value=("output", {})):
            agent._call_llm("Test prompt", task_type="reasoning")

        assert arango_ctx_called is True

    def test_arango_context_prepended_to_prompt(self, monkeypatch):
        """Context is prepended to prompt when non-empty."""
        agent = BaseCareerAgent()
        agent.agent_type = "resume_tailor"
        agent._current_user_id = "user_456"

        ctx_value = "Context: 5 projects with AWS, Kubernetes"

        monkeypatch.setattr(agent, "_get_arango_context", lambda *a, **k: ctx_value)

        captured_prompt = None

        def capture_llm(prompt, task_type="reasoning", max_tokens=4096):
            nonlocal captured_prompt
            captured_prompt = prompt
            return "result", {}

        with patch("agents.base_agent.call_llm_scored", side_effect=capture_llm):
            agent._call_llm("Original prompt", task_type="reasoning")

        assert captured_prompt is not None
        assert "<knowledge_context>" in captured_prompt
        assert ctx_value in captured_prompt
        assert "Original prompt" in captured_prompt

    def test_empty_context_not_prepended(self, monkeypatch):
        """Empty context string doesn't add XML wrapper."""
        agent = BaseCareerAgent()
        agent.agent_type = "resume_tailor"
        agent._current_user_id = "user_789"

        monkeypatch.setattr(agent, "_get_arango_context", lambda *a, **k: "")

        captured_prompt = None

        def capture_llm(prompt, task_type="reasoning", max_tokens=4096):
            nonlocal captured_prompt
            captured_prompt = prompt
            return "result", {}

        with patch("agents.base_agent.call_llm_scored", side_effect=capture_llm):
            agent._call_llm("Test prompt", task_type="reasoning")

        assert "<knowledge_context>" not in captured_prompt
        assert captured_prompt == "Test prompt"

    def test_arango_error_gracefully_degraded(self, monkeypatch):
        """If _get_arango_context raises, agent continues with empty context."""
        agent = BaseCareerAgent()
        agent.agent_type = "cover_letter"
        agent._current_user_id = "user_err"

        def raise_error(*args, **kwargs):
            raise Exception("ArangoDB offline")

        monkeypatch.setattr(agent, "_get_arango_context", raise_error)

        captured_prompt = None

        def capture_llm(prompt, task_type="reasoning", max_tokens=4096):
            nonlocal captured_prompt
            captured_prompt = prompt
            return "result", {}

        # Should not raise — error is caught internally
        with patch("agents.base_agent.call_llm_scored", side_effect=capture_llm):
            result = agent._call_llm("Test prompt")

        # Agent still works, prompt is unchanged
        assert captured_prompt == "Test prompt"
        assert result == "result"
