"""Live Smart LLM quality tests — no mocks, no skips.

8 tests calling real RTX 5090 via smart_llm.call_direct() and verifying
response quality with semantic assertions. Tests FAIL (not skip) if LLM
is unavailable — LLM must be running.
"""

import json
import os
import sys

import pytest
import requests

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import smart_llm  # noqa: E402


def _require_rtx5090():
    """Fail (not skip) if RTX 5090 is unreachable."""
    try:
        r = requests.get("http://localhost:8021/v1/models", timeout=5)
        if r.status_code != 200:
            pytest.fail("RTX 5090 at port 8021 returned non-200. Start model before running tests.")
    except Exception as e:
        pytest.fail(f"RTX 5090 at port 8021 unreachable: {e}. Start model before running tests.")


# Fail fast at module level — all 8 tests need LLM
_require_rtx5090()


# ===================================================================
# Live LLM Quality (8 tests — no mocks, no skips)
# ===================================================================


class TestLiveLLMQuality:
    """8 tests verifying LLM output quality with semantic assertions."""

    def test_coding_response(self):
        """Coding prompt → response contains function definition + return."""
        result = smart_llm.call_direct(
            "Write a Python function that checks if a number is prime. "
            "Return only the function code, no explanation.",
            max_tokens=512,
        )
        assert result is not None, "LLM returned None"
        assert "def" in result, f"Expected function def in: {result[:200]}"
        assert "return" in result.lower(), f"Expected return statement in: {result[:200]}"

    def test_factual_answer(self):
        """Factual question → correct one-word answer."""
        result = smart_llm.call_direct(
            "What is the capital of France? Reply in one word only.",
            max_tokens=32,
        )
        assert result is not None, "LLM returned None"
        assert "paris" in result.lower(), f"Expected 'Paris', got: {result!r}"

    def test_code_review_finds_bug(self):
        """Code review → identifies index/bounds error."""
        result = smart_llm.call_direct(
            "Find the bug in this Python code:\n"
            "```python\n"
            "arr = [1, 2, 3, 4, 5]\n"
            "for i in range(len(arr)):\n"
            "    print(arr[i+1])\n"
            "```\n"
            "Explain the bug briefly.",
            max_tokens=256,
        )
        assert result is not None, "LLM returned None"
        result_lower = result.lower()
        assert any(
            term in result_lower
            for term in ["index", "bound", "off-by-one", "out of range", "indexerror", "overflow"]
        ), f"Should mention index/bounds error, got: {result[:300]}"

    def test_json_output(self):
        """JSON generation → parseable JSON with correct values."""
        result = smart_llm.call_direct(
            "Return a JSON object with exactly two keys: 'name' and 'age'. "
            "Set name to 'Alice' and age to 30. "
            "Return ONLY the JSON, no markdown fences, no explanation.",
            max_tokens=64,
        )
        assert result is not None, "LLM returned None"
        # Strip markdown fences if present
        cleaned = result.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [line for line in lines if not line.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()
        parsed = json.loads(cleaned)
        assert parsed["name"] == "Alice", f"Expected name='Alice', got {parsed.get('name')}"
        assert parsed["age"] == 30, f"Expected age=30, got {parsed.get('age')}"

    def test_empty_prompt_no_crash(self):
        """Empty prompt → returns string or None, no crash."""
        result = smart_llm.call_direct("", max_tokens=64)
        assert result is None or isinstance(result, str)

    def test_long_context_references_details(self):
        """500-word project description → response references specific details."""
        long_prompt = (
            "I am working on a project called 'PharmacyBenefitHub' which is a cloud-native "
            "pharmacy benefit management platform built with Python FastAPI and deployed on AWS "
            "using ECS Fargate. The system processes 30 million member eligibility checks per "
            "month through a microservices architecture with 12 services communicating via "
            "Apache Kafka event streams. The database layer uses PostgreSQL for transactional "
            "data and Redis for caching formulary lookups. We recently migrated from a "
            "monolithic Java Spring application to this microservices architecture, reducing "
            "deployment time from 2 weeks to 2 hours. The team consists of 12 engineers across "
            "3 time zones. Our CI/CD pipeline uses GitHub Actions with automated testing, "
            "security scanning via Snyk, and blue-green deployments. Key challenges include "
            "maintaining data consistency across services, managing schema migrations without "
            "downtime, and optimizing Kafka consumer lag during peak enrollment periods. "
            "The observability stack includes Datadog for metrics, PagerDuty for alerting, "
            "and OpenTelemetry for distributed tracing. We use Terraform for infrastructure "
            "as code and have 95% test coverage. The annual infrastructure cost is $2.4M and "
            "we are targeting a 30% reduction through right-sizing and reserved instances. "
            "Please summarize the key technical decisions and their business impact."
        )
        result = smart_llm.call_direct(long_prompt, max_tokens=1024)
        assert result is not None, "LLM returned None"
        result_lower = result.lower()
        hits = sum(
            1
            for term in ["fastapi", "kafka", "postgresql", "microservice", "pharmacy", "aws"]
            if term in result_lower
        )
        assert (
            hits >= 2
        ), f"Response should reference project details (found {hits}/6 terms): {result[:300]}"

    def test_reasoning_explains_algorithm(self):
        """Algorithm explanation → mentions pivot or partition, >100 chars."""
        result = smart_llm.call_direct(
            "Explain how quicksort works, step by step.",
            max_tokens=512,
        )
        assert result is not None, "LLM returned None"
        assert len(result) > 100, f"Explanation too short ({len(result)} chars)"
        result_lower = result.lower()
        assert any(
            term in result_lower for term in ["pivot", "partition", "divide"]
        ), f"Should mention pivot/partition/divide, got: {result[:300]}"

    def test_summarization_preserves_key_items(self):
        """Summarize 10 skills to top 3 → output mentions ≥2 input skills."""
        skills = [
            "Python",
            "AWS",
            "Docker",
            "Kubernetes",
            "Terraform",
            "PostgreSQL",
            "Redis",
            "Kafka",
            "FastAPI",
            "Microservices",
        ]
        result = smart_llm.call_direct(
            f"Here are 10 technical skills: {', '.join(skills)}. "
            "Summarize the top 3 most important skills for a cloud architect role. "
            "Reply with just the 3 skill names.",
            max_tokens=128,
        )
        assert result is not None, "LLM returned None"
        result_lower = result.lower()
        found = sum(1 for s in skills if s.lower() in result_lower)
        assert found >= 2, f"Expected ≥2 of the input skills in summary, found {found}: {result!r}"
