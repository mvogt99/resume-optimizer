"""CloudLift LLM bridge adapter for resume-optimizer — thin shim.

Routes LLM calls to the appropriate provider based on CLOUDLIFT_ENV:
  local: RTX 5090 vLLM (port 8021) — dev, no AWS required
  aws:   AWS Bedrock (Claude) — test and prod

Uses cloudlift pattern: no cloud SDK imports at module level; boto3 imported
lazily inside call_bedrock() only when CLOUDLIFT_ENV=aws.

NOTE: cloudlift BedrockAdapter not used here — cloudlift.bridge.* namespace
suffers from module identity split (core.* vs cloudlift.*) that breaks the
tenant context system in single-tenant apps. This shim uses boto3 directly
following cloudlift's lazy-import pattern, which is equivalent and simpler.

Task type → Bedrock model mapping:
  analysis/coding   → Claude Haiku (fast, cheap: structured extraction, classification)
  reasoning/planning → Claude Haiku (Sonnet not available in target region)
"""
from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)

CLOUDLIFT_ENV = os.environ.get("CLOUDLIFT_ENV", "local")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

BEDROCK_MODEL_MAP: dict[str, str] = {
    "analysis":  "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "coding":    "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "reasoning": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "planning":  "us.anthropic.claude-haiku-4-5-20251001-v1:0",
}
DEFAULT_BEDROCK_MODEL = "us.anthropic.claude-haiku-4-5-20251001-v1:0"


def is_aws() -> bool:
    """Return True when running in test or prod AWS environment."""
    return CLOUDLIFT_ENV == "aws"


def call_bedrock(prompt: str, task_type: str = "analysis", max_tokens: int = 4096) -> str | None:
    """Invoke AWS Bedrock (Claude) for the given prompt.

    Uses lazy boto3 import per cloudlift pattern — no cloud SDK at module level.
    Returns the response text or None on failure.
    """
    try:
        import boto3  # noqa: PLC0415 — lazy import, cloudlift pattern

        model_id = BEDROCK_MODEL_MAP.get(task_type, DEFAULT_BEDROCK_MODEL)
        client = boto3.client("bedrock-runtime", region_name=AWS_REGION)

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        })

        response = client.invoke_model(
            modelId=model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )

        result = json.loads(response["body"].read())
        content_blocks = result.get("content", [])
        text = content_blocks[0].get("text", "") if content_blocks else ""

        usage = result.get("usage", {})
        logger.info(
            "[bedrock] model=%s task_type=%s tokens_in=%d tokens_out=%d",
            model_id,
            task_type,
            usage.get("input_tokens", 0),
            usage.get("output_tokens", 0),
        )
        return text or None

    except Exception as exc:
        logger.error("[bedrock] call failed: %s", exc)
        return None
