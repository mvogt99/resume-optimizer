"""P1-B.3/B.4 tests: PersonaForge integration into base_agent _call_llm pipeline."""

import pytest
from agents.base_agent import BaseCareerAgent


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    """Block real LLM calls."""
    monkeypatch.setattr("agents.base_agent.call_llm_scored", lambda *a, **kw: (None, None))
    monkeypatch.setattr("agents.base_agent.extract_json", lambda x: None)


# ---------------------------------------------------------------------------
# P1-B.3: Persona context recall in _call_llm
# ---------------------------------------------------------------------------


class TestPersonaRecall:
    """Tests that _call_llm prepends persona context when available."""

    def test_prepends_persona_context_to_prompt(self, monkeypatch):
        """When pf_recall returns context, it is prepended to the prompt."""
        captured = {}

        def _fake_llm_scored(prompt, **kw):
            captured["prompt"] = prompt
            return ("output", {"gap": 20, "f": 30, "t": 30, "a": 20})

        monkeypatch.setattr("agents.base_agent.call_llm_scored", _fake_llm_scored)
        monkeypatch.setattr(
            "agents.base_agent.pf_recall",
            lambda ns, q: "You are a senior enterprise architect.",
        )
        # Block remember to avoid side effects
        monkeypatch.setattr("agents.base_agent.pf_remember", lambda *a, **kw: None)

        agent = BaseCareerAgent()
        agent._call_llm("Write a resume summary")

        assert "<persona_context>" in captured["prompt"]
        assert "senior enterprise architect" in captured["prompt"]
        assert "Write a resume summary" in captured["prompt"]

    def test_no_persona_context_when_recall_returns_none(self, monkeypatch):
        """When pf_recall returns None, prompt is unchanged."""
        captured = {}

        def _fake_llm_scored(prompt, **kw):
            captured["prompt"] = prompt
            return ("output", None)

        monkeypatch.setattr("agents.base_agent.call_llm_scored", _fake_llm_scored)
        monkeypatch.setattr("agents.base_agent.pf_recall", lambda ns, q: None)

        agent = BaseCareerAgent()
        agent._call_llm("Write a resume summary")

        assert "<persona_context>" not in captured["prompt"]
        assert captured["prompt"] == "Write a resume summary"

    def test_recall_uses_career_namespace(self, monkeypatch):
        """pf_recall is called with the CAREER_NAMESPACE."""
        recall_args = {}

        def _mock_recall(namespace, query):
            recall_args["namespace"] = namespace
            recall_args["query"] = query
            return None

        monkeypatch.setattr("agents.base_agent.pf_recall", _mock_recall)

        agent = BaseCareerAgent()
        agent._call_llm("Test prompt")

        assert recall_args["namespace"] == "career_profile"

    def test_recall_query_is_truncated_prompt(self, monkeypatch):
        """pf_recall receives first 200 chars of the prompt as query."""
        recall_args = {}

        def _mock_recall(namespace, query):
            recall_args["query"] = query
            return None

        monkeypatch.setattr("agents.base_agent.pf_recall", _mock_recall)

        long_prompt = "x" * 500
        agent = BaseCareerAgent()
        agent._call_llm(long_prompt)

        assert len(recall_args["query"]) == 200


# ---------------------------------------------------------------------------
# P1-B.4: Successful output stored via pf_remember
# ---------------------------------------------------------------------------


class TestPatternRemember:
    """Tests that successful FTAL outputs are stored in PersonaForge."""

    def test_stores_pattern_on_ftal_pass(self, monkeypatch):
        """When gap < 30, output pattern is stored via pf_remember."""
        remember_calls = []

        def _fake_llm_scored(prompt, **kw):
            return ("Great STAR bullet here", {"gap": 15, "f": 30, "t": 30, "a": 25})

        monkeypatch.setattr("agents.base_agent.call_llm_scored", _fake_llm_scored)
        monkeypatch.setattr("agents.base_agent.pf_recall", lambda ns, q: None)
        monkeypatch.setattr(
            "agents.base_agent.pf_remember",
            lambda ns, content, meta: remember_calls.append((ns, content, meta)),
        )

        agent = BaseCareerAgent()
        agent._call_llm("Write a bullet")

        assert len(remember_calls) == 1
        ns, content, meta = remember_calls[0]
        assert ns == "career_profile"
        assert "Great STAR bullet" in content
        assert meta["category"] == "pattern"
        assert meta["gap"] == 15

    def test_no_store_on_ftal_fail(self, monkeypatch):
        """When gap >= 30, output is NOT stored."""
        remember_calls = []

        def _fake_llm_scored(prompt, **kw):
            return ("Bad output", {"gap": 45, "f": 20, "t": 20, "a": 15})

        monkeypatch.setattr("agents.base_agent.call_llm_scored", _fake_llm_scored)
        monkeypatch.setattr("agents.base_agent.pf_recall", lambda ns, q: None)
        monkeypatch.setattr(
            "agents.base_agent.pf_remember",
            lambda ns, content, meta: remember_calls.append((ns, content, meta)),
        )

        agent = BaseCareerAgent()
        agent._call_llm("Write a bullet")

        assert len(remember_calls) == 0

    def test_no_store_when_scores_none(self, monkeypatch):
        """When harness is unreachable (scores=None), no store."""
        remember_calls = []

        def _fake_llm_scored(prompt, **kw):
            return ("Some text", None)

        monkeypatch.setattr("agents.base_agent.call_llm_scored", _fake_llm_scored)
        monkeypatch.setattr("agents.base_agent.pf_recall", lambda ns, q: None)
        monkeypatch.setattr(
            "agents.base_agent.pf_remember",
            lambda ns, content, meta: remember_calls.append((ns, content, meta)),
        )

        agent = BaseCareerAgent()
        agent._call_llm("Write a bullet")

        assert len(remember_calls) == 0

    def test_no_store_when_text_none(self, monkeypatch):
        """When LLM returns no text, no store."""
        remember_calls = []

        def _fake_llm_scored(prompt, **kw):
            return (None, {"gap": 10})

        monkeypatch.setattr("agents.base_agent.call_llm_scored", _fake_llm_scored)
        monkeypatch.setattr("agents.base_agent.pf_recall", lambda ns, q: None)
        monkeypatch.setattr(
            "agents.base_agent.pf_remember",
            lambda ns, content, meta: remember_calls.append((ns, content, meta)),
        )

        agent = BaseCareerAgent()
        agent._call_llm("Write a bullet")

        assert len(remember_calls) == 0

    def test_agent_type_in_metadata(self, monkeypatch):
        """Stored pattern metadata includes the agent type."""
        remember_calls = []

        def _fake_llm_scored(prompt, **kw):
            return ("output", {"gap": 10, "f": 30, "t": 30, "a": 30})

        monkeypatch.setattr("agents.base_agent.call_llm_scored", _fake_llm_scored)
        monkeypatch.setattr("agents.base_agent.pf_recall", lambda ns, q: None)
        monkeypatch.setattr(
            "agents.base_agent.pf_remember",
            lambda ns, content, meta: remember_calls.append((ns, content, meta)),
        )

        class TestAgent(BaseCareerAgent):
            agent_type = "cover_letter"

        agent = TestAgent()
        agent._call_llm("Write a letter")

        assert remember_calls[0][2]["agent_type"] == "cover_letter"

    def test_confidence_scales_with_gap(self, monkeypatch):
        """Lower gap → higher confidence in stored pattern."""
        remember_calls = []

        def _fake_llm_scored(prompt, **kw):
            return ("output", {"gap": 5, "f": 30, "t": 30, "a": 35})

        monkeypatch.setattr("agents.base_agent.call_llm_scored", _fake_llm_scored)
        monkeypatch.setattr("agents.base_agent.pf_recall", lambda ns, q: None)
        monkeypatch.setattr(
            "agents.base_agent.pf_remember",
            lambda ns, content, meta: remember_calls.append((ns, content, meta)),
        )

        agent = BaseCareerAgent()
        agent._call_llm("Write a bullet")

        confidence = remember_calls[0][2]["confidence"]
        assert confidence >= 0.9  # gap=5 → confidence=0.95


# ---------------------------------------------------------------------------
# Integration: recall + remember work together
# ---------------------------------------------------------------------------


class TestRecallRememberFlow:
    """End-to-end: persona context is recalled, output is generated and stored."""

    def test_full_flow(self, monkeypatch):
        recall_called = {"count": 0}
        remember_calls = []

        def _mock_recall(ns, q):
            recall_called["count"] += 1
            return "You are an enterprise architect with 22 years of experience."

        def _fake_llm_scored(prompt, **kw):
            # Verify persona context was prepended
            assert "enterprise architect" in prompt
            return ("Optimized output", {"gap": 18, "f": 28, "t": 28, "a": 26})

        monkeypatch.setattr("agents.base_agent.pf_recall", _mock_recall)
        monkeypatch.setattr("agents.base_agent.call_llm_scored", _fake_llm_scored)
        monkeypatch.setattr(
            "agents.base_agent.pf_remember",
            lambda ns, content, meta: remember_calls.append((ns, content, meta)),
        )

        agent = BaseCareerAgent()
        result = agent._call_llm("Write a professional summary")

        assert result == "Optimized output"
        assert recall_called["count"] == 1
        assert len(remember_calls) == 1
        assert "Optimized output" in remember_calls[0][1]
