"""
Smart LLM client — selects the best local model for each task via gateway model selection service.

Uses:
  POST /api/models/select  — classify task → best model + swap_id
  POST /api/swap/request   — swap model into RTX 5090 slot (port 8021)
  POST 8021/v1/chat/completions — inference

Falls back to direct Qwen3-Coder-30B if gateway is unreachable.
"""

import logging
import os
import re
import time

import httpx

logger = logging.getLogger(__name__)

_http_client = httpx.Client(
    timeout=None,  # per-call timeouts set explicitly on each request
    limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
)

# Gateway model selection + swap endpoints
GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://localhost:8000")
MODEL_SELECT_URL = f"{GATEWAY_URL}/api/models/select"
SWAP_REQUEST_URL = f"{GATEWAY_URL}/api/swap/request"
SWAP_STATUS_URL = f"{GATEWAY_URL}/api/swap/status"

# Direct model endpoint (always port 8021 — single swap slot)
MODEL_URL = os.environ.get("VLLM_URL", "http://localhost:8021") + "/v1/chat/completions"
FALLBACK_MODEL_ID = "Qwen/Qwen2.5-Coder-32B-Instruct-AWQ"

# Timeouts
SELECT_TIMEOUT = 5  # model selection is fast
SWAP_TIMEOUT = 660  # 70B cold loads take ~600s
SWAP_POLL_INTERVAL = 10  # poll every 10s during swap
INFERENCE_TIMEOUT = 300  # inference call (300s for concurrent GPU load)

# FTAL harness (for RAG-context-aware calls)
HARNESS_URL = os.environ.get("HARNESS_URL", "http://localhost:8000/api/harness/run")
HARNESS_TIMEOUT = 300

# Task type mapping for resume-optimizer functions
TASK_TYPE_MAP = {
    # Analysis / reasoning tasks → DeepSeek-R1
    "resume_analysis": "analysis",
    "skills_gap": "analysis",
    "ats_diagnostic": "analysis",
    "document_classification": "analysis",
    "outcome_extraction": "analysis",
    # Conversational / interview tasks → reasoning model
    "interview": "reasoning",
    "experience_chat": "reasoning",
    "campaign_planning": "reasoning",
    "narrative_generation": "reasoning",
    # Code / structured output → Qwen3-Coder
    "json_extraction": "coding",
    "technical_extraction": "coding",
    "resume_rewrite": "coding",
    # Planning / architecture → LLaMA-70B or DeepSeek-R1
    "career_planning": "planning",
    "campaign_strategy": "planning",
}

# Cache current model to avoid unnecessary swap checks
_current_model_id = None
_current_swap_id = None


def _select_model(task_description, task_type=None):
    """Ask gateway which model is best for this task. Returns (model_id, swap_id, api_model_name) or None."""  # noqa: E501
    try:
        payload = {"task": task_description[:500]}
        if task_type:
            payload["task_type"] = task_type
        resp = _http_client.post(MODEL_SELECT_URL, json=payload, timeout=SELECT_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "model_id": data.get("model_id", ""),
                "swap_id": data.get("swap_id", ""),
                "api_model_name": data.get("api_model_name", ""),
                "endpoint_port": data.get("endpoint_port", 8021),
                "score": data.get("score", 0),
                "task_type": data.get("task_type", ""),
            }
    except Exception as e:
        logger.warning("Model selection failed: %s", e)
    return None


def _ensure_model_loaded(swap_id):
    """Swap the model if needed. Returns True if model is ready."""
    global _current_swap_id

    if not swap_id:
        return True  # No swap needed

    # Check if already loaded
    if _current_swap_id == swap_id:
        return True

    try:
        # Check current swap status from gateway
        status_resp = _http_client.get(SWAP_STATUS_URL, timeout=SELECT_TIMEOUT)
        if status_resp.status_code == 200:
            status = status_resp.json()
            if status.get("current_swap_id") == swap_id:
                _current_swap_id = swap_id
                return True
            if status.get("swap_in_progress"):
                # Wait for ongoing swap to complete
                return _wait_for_swap(swap_id)
    except Exception:
        pass

    # Request swap
    try:
        resp = _http_client.post(
            SWAP_REQUEST_URL,
            json={"model_id": swap_id},
            timeout=min(SWAP_TIMEOUT, 30),  # Initial request timeout is short
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success"):
                _current_swap_id = swap_id
                return True
            if data.get("swapped") is False and "already" in str(data.get("error", "")).lower():
                _current_swap_id = swap_id
                return True
        # If the swap was accepted but takes time, poll
        return _wait_for_swap(swap_id)
    except httpx.TimeoutException:
        # Swap initiated but takes long — poll
        return _wait_for_swap(swap_id)
    except Exception as e:
        logger.warning("Swap request failed: %s", e)
        return False


def _wait_for_swap(target_swap_id, max_wait=SWAP_TIMEOUT):
    """Poll swap status until target model is loaded."""
    global _current_swap_id
    start = time.time()
    while time.time() - start < max_wait:
        try:
            resp = _http_client.get(SWAP_STATUS_URL, timeout=SELECT_TIMEOUT)
            if resp.status_code == 200:
                status = resp.json()
                if status.get("current_swap_id") == target_swap_id and not status.get(
                    "swap_in_progress"
                ):
                    _current_swap_id = target_swap_id
                    return True
        except Exception:
            pass
        time.sleep(SWAP_POLL_INTERVAL)
    logger.warning("Swap to %s timed out after %ss", target_swap_id, max_wait)
    return False


def call_smart(prompt, task_type=None, task_hint=None, max_tokens=2048, temperature=0.3):
    """Smart LLM call — selects best model, swaps if needed, calls inference.

    Args:
        prompt: The prompt to send
        task_type: One of TASK_TYPE_MAP keys or gateway task types (coding, analysis, reasoning, planning)  # noqa: E501
        task_hint: Short task description for model selection (defaults to first 200 chars of prompt)  # noqa: E501
        max_tokens: Max tokens for response
        temperature: Sampling temperature

    Returns:
        str or None — model response with thinking tags stripped
    """
    # Resolve task type
    resolved_type = TASK_TYPE_MAP.get(task_type, task_type) if task_type else None
    hint = task_hint or prompt[:200]

    # Try model selection
    selection = _select_model(hint, resolved_type)
    model_id = FALLBACK_MODEL_ID

    if selection:
        swap_id = selection.get("swap_id", "")
        api_model = selection.get("api_model_name", "")

        if swap_id:
            loaded = _ensure_model_loaded(swap_id)
            if loaded and api_model:
                model_id = api_model

    # Call inference
    return _call_inference(prompt, model_id, max_tokens, temperature, task_type=resolved_type)


def _get_loaded_model_id():
    """Return the model ID currently loaded in vLLM, falling back to FALLBACK_MODEL_ID."""
    try:
        resp = _http_client.get("http://localhost:8021/v1/models", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get("data", [])
            if models:
                return models[0]["id"]
    except Exception:
        pass
    return FALLBACK_MODEL_ID


def call_direct(prompt, max_tokens=4096, temperature=0.3):
    """Direct call to currently loaded model (no selection, no swap).
    Use for structured JSON extraction where the current model is fine."""
    # Bridge: route to AWS Bedrock when CLOUDLIFT_ENV=aws
    from cloudlift_llm_adapter import call_bedrock, is_aws  # noqa: PLC0415
    if is_aws():
        return call_bedrock(prompt, task_type="analysis", max_tokens=max_tokens)
    return _call_inference(prompt, _get_loaded_model_id(), max_tokens, temperature)


def call_harness(task, task_type="coding", max_tokens=4096):
    """Call FTAL harness for RAG-context-aware tasks."""
    # In AWS environment, harness is not available — use Bedrock directly
    from cloudlift_llm_adapter import call_bedrock, is_aws  # noqa: PLC0415
    if is_aws():
        return call_bedrock(task, task_type=task_type, max_tokens=max_tokens)
    try:
        resp = _http_client.post(
            HARNESS_URL,
            json={"task": task, "task_type": task_type, "max_tokens": max_tokens},
            timeout=HARNESS_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("output") or data.get("result", "")
        logger.warning("Harness returned %s", resp.status_code)
        return None
    except Exception as e:
        logger.error("Harness call failed: %s", e)
        return None


def call_harness_scored(task, task_type="reasoning", max_tokens=4096, skip_rag=True):
    """Call FTAL harness and return (result, ftal_scores).

    ftal_scores dict keys: f, t, a, gap.
    Reads from top-level ftal_f/ftal_t/ftal_a/ftal_gap keys (harness response
    format), with fallback to nested ftal_score object.
    Returns (result, None) when harness is unreachable — caller should fall
    back to call_direct() if a non-None result is needed.
    """
    # In AWS environment, harness is not available — use Bedrock directly
    from cloudlift_llm_adapter import call_bedrock, is_aws  # noqa: PLC0415
    if is_aws():
        text = call_bedrock(task, task_type=task_type, max_tokens=max_tokens)
        return text, None  # No FTAL scores available via Bedrock
    try:
        resp = _http_client.post(
            HARNESS_URL,
            json={
                "task": task,
                "task_type": task_type,
                "max_tokens": max_tokens,
                "skip_rag": skip_rag,
            },
            timeout=HARNESS_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            text = data.get("output") or data.get("result", "")
            # Harness returns scores as top-level ftal_* keys.
            # Use 'is not None' checks — 0 is a valid score.
            raw_nested = data.get("ftal_score") or {}

            def _pick(top_key, nested_key):
                v = data.get(top_key)
                return v if v is not None else raw_nested.get(nested_key)

            scores = {
                "f": _pick("ftal_f", "f_score"),
                "t": _pick("ftal_t", "t_score"),
                "a": _pick("ftal_a", "a_score"),
                "gap": _pick("ftal_gap", "gap"),
                "model_id": data.get("model_id") or data.get("swap_id") or "unknown",
            }
            return text, scores
        logger.warning("Harness scored returned %s", resp.status_code)
        return None, None
    except Exception as e:
        logger.error("Harness scored call failed: %s", e)
        return None, None


def _call_inference(prompt, model_id, max_tokens, temperature, task_type=None):
    """Raw inference call to the model on port 8021.

    Falls back to FTAL harness if direct inference fails, giving
    the gateway a chance to route through an available model.
    """
    # Bridge: route to AWS Bedrock when CLOUDLIFT_ENV=aws
    from cloudlift_llm_adapter import call_bedrock, is_aws  # noqa: PLC0415
    if is_aws():
        return call_bedrock(prompt, task_type=task_type or "coding", max_tokens=max_tokens)
    try:
        resp = _http_client.post(
            MODEL_URL,
            json={
                "model": model_id,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=INFERENCE_TIMEOUT,
        )
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            # Strip thinking tags (Qwen3 and DeepSeek both use these)
            if "<think>" in content:
                content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            return content
        logger.warning("Inference returned %s", resp.status_code)
    except Exception as e:
        logger.warning("Direct inference failed: %s — trying harness", e)

    # Fallback: try FTAL harness (gateway can route to any available model)
    try:
        resp = _http_client.post(
            HARNESS_URL,
            json={
                "task": prompt,
                "task_type": "coding",
                "max_tokens": max_tokens,
            },
            timeout=HARNESS_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            content = data.get("output") or data.get("result", "")
            if content:
                logger.info("Harness fallback succeeded")
                return content
    except Exception as e2:
        logger.error("Harness fallback also failed: %s", e2)
    return None


def get_current_model():
    """Return info about the currently loaded model."""
    try:
        resp = _http_client.get(SWAP_STATUS_URL, timeout=SELECT_TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {"current_swap_id": _current_swap_id, "swap_in_progress": False}
