"""Tests for W1: teaching text injection into BaseCareerAgent._call_llm().

Verifies that _pending_retry_teaching is prepended to the prompt once then
cleared, and that the class-level default does not bleed between instances.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch

from agents.base_agent import BaseCareerAgent


# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────

class _ConcreteAgent(BaseCareerAgent):
    """Minimal concrete subclass for testing — no DB, no LLM."""
    agent_type = "test_agent"


def _make_agent():
    return _ConcreteAgent()


# ──────────────────────────────────────────────────────────────
# _pending_retry_teaching attribute
# ──────────────────────────────────────────────────────────────

class TestPendingRetryTeachingAttribute:
    def test_default_is_empty_string(self):
        agent = _make_agent()
        assert agent._pending_retry_teaching == ""

    def test_set_and_read(self):
        agent = _make_agent()
        agent._pending_retry_teaching = "teaching text"
        assert agent._pending_retry_teaching == "teaching text"

    def test_instances_do_not_share_state(self):
        a1 = _make_agent()
        a2 = _make_agent()
        a1._pending_retry_teaching = "for a1 only"
        assert a2._pending_retry_teaching == ""

    def test_reset_to_empty(self):
        agent = _make_agent()
        agent._pending_retry_teaching = "something"
        agent._pending_retry_teaching = ""
        assert agent._pending_retry_teaching == ""


# ──────────────────────────────────────────────────────────────
# Teaching injection in _call_llm
# ──────────────────────────────────────────────────────────────

class TestTeachingInjection:
    def _call_with_teaching(self, agent, teaching, prompt="base prompt"):
        """Run _call_llm with call_llm_scored mocked to capture the prompt."""
        captured = {}

        def fake_scored(p, task_type="reasoning", max_tokens=4096):
            captured["prompt"] = p
            return ("response text", {"f": 25, "t": 25, "a": 25, "gap": 0})

        agent._pending_retry_teaching = teaching
        with patch("agents.base_agent.call_llm_scored", side_effect=fake_scored):
            with patch("agents.base_agent.pf_recall", return_value=None):
                with patch("agents.base_agent.pf_remember"):
                    agent._call_llm(prompt)

        return captured.get("prompt", "")

    def test_teaching_prepended_when_set(self):
        agent = _make_agent()
        result_prompt = self._call_with_teaching(agent, "TEACHING: do X", prompt="do the task")
        assert "<retry_context>" in result_prompt
        assert "TEACHING: do X" in result_prompt
        assert "do the task" in result_prompt

    def test_teaching_before_base_prompt(self):
        agent = _make_agent()
        result_prompt = self._call_with_teaching(agent, "FIX THIS", prompt="original task")
        teaching_pos = result_prompt.index("FIX THIS")
        task_pos = result_prompt.index("original task")
        assert teaching_pos < task_pos

    def test_teaching_consumed_on_first_call(self):
        agent = _make_agent()
        self._call_with_teaching(agent, "TEACHING", prompt="first call")
        assert agent._pending_retry_teaching == ""

    def test_second_call_has_no_teaching(self):
        agent = _make_agent()
        self._call_with_teaching(agent, "TEACHING", prompt="first call")
        second_prompt = self._call_with_teaching(agent, "", prompt="second call")
        assert "<retry_context>" not in second_prompt

    def test_no_teaching_no_wrapper(self):
        agent = _make_agent()
        result_prompt = self._call_with_teaching(agent, "", prompt="clean prompt")
        assert "<retry_context>" not in result_prompt
        assert "clean prompt" in result_prompt

    def test_teaching_uses_retry_context_tag(self):
        agent = _make_agent()
        result_prompt = self._call_with_teaching(agent, "hint text", prompt="task")
        assert "<retry_context>" in result_prompt
        assert "</retry_context>" in result_prompt


# ──────────────────────────────────────────────────────────────
# Teaching does not affect other methods
# ──────────────────────────────────────────────────────────────

class TestTeachingDoesNotLeakToOtherMethods:
    def test_teaching_not_in_call_llm_json_second_call(self):
        """After a call_llm with teaching, subsequent call_llm_json has no teaching."""
        agent = _make_agent()
        captured = {}

        def fake_scored(p, task_type="reasoning", max_tokens=4096):
            captured.setdefault("calls", []).append(p)
            return ("response text", {"f": 25, "t": 25, "a": 25, "gap": 0})

        def fake_extract(raw):
            return {"key": "value"}

        agent._pending_retry_teaching = "TEACHING"
        with patch("agents.base_agent.call_llm_scored", side_effect=fake_scored):
            with patch("agents.base_agent.pf_recall", return_value=None):
                with patch("agents.base_agent.pf_remember"):
                    with patch("agents.base_agent.extract_json", side_effect=fake_extract):
                        agent._call_llm("first")
                        agent._call_llm_json("second")

        # Second prompt must NOT contain retry_context tag
        assert len(captured["calls"]) == 2
        assert "<retry_context>" not in captured["calls"][1]
