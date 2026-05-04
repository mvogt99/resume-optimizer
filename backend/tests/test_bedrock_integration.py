"""Live Bedrock integration tests — only run with CLOUDLIFT_ENV=aws.

Usage: CLOUDLIFT_ENV=aws AWS_REGION=us-east-1 pytest tests/test_bedrock_integration.py -v
"""
import os
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("CLOUDLIFT_ENV") != "aws",
    reason="Live Bedrock tests require CLOUDLIFT_ENV=aws",
)


def test_bedrock_analysis_returns_text():
    from cloudlift_llm_adapter import call_bedrock
    result = call_bedrock("List 3 Python web frameworks in JSON array format.", task_type="analysis", max_tokens=256)
    assert result is not None
    assert len(result) > 10


def test_bedrock_reasoning_returns_text():
    from cloudlift_llm_adapter import call_bedrock
    result = call_bedrock("In one sentence, what is the main advantage of microservices over monoliths?", task_type="reasoning", max_tokens=256)
    assert result is not None
    assert len(result) > 20


def test_smart_llm_routes_to_bedrock_in_aws_env():
    """Verify that call_direct routes to Bedrock when CLOUDLIFT_ENV=aws."""
    from smart_llm import call_direct
    result = call_direct("Return the word BRIDGED and nothing else.", max_tokens=50)
    assert result is not None
    assert len(result) > 0
