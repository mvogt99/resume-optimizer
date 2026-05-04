"""
LLM chunking + extraction helpers.
Routes LLM calls to the local RTX 5090 ($0.00).
Uses smart model selection via gateway service — picks the best model
for each task type (coding, analysis, reasoning, planning).
Falls back to direct Qwen3-Coder-30B if gateway unreachable.
"""

import json
import logging
import re
import threading
import time
from functools import lru_cache

from smart_llm import call_direct, call_harness, call_harness_scored, call_smart

logger = logging.getLogger(__name__)

_GOVERNANCE_THRESHOLD = 30  # gap < 30 = pass


def _record_governance_outcome(task_type: str, scores: dict, model_id: str) -> None:
    """Fire-and-forget: write FTAL outcome to gateway governance_outcomes collection."""
    def _write() -> None:
        try:
            from arango import ArangoClient  # type: ignore[import]
            client = ArangoClient(hosts="http://localhost:8529")
            db = client.db("hybrid_ai", username="root", password="hybrid_ai_root")
            col = db.collection("governance_outcomes")
            gap = scores.get("gap")
            col.insert(
                {
                    "task_type": task_type,
                    "model": model_id,
                    "provider": "ro_agent",
                    "gap": gap,
                    "passed": gap is not None and gap < _GOVERNANCE_THRESHOLD,
                    "threshold": _GOVERNANCE_THRESHOLD,
                    "recorded_at": time.time(),
                    "source": "resume_optimizer",
                },
                overwrite=False,
                silent=True,
            )
        except Exception as exc:
            logger.debug("[CT1] governance_outcomes write failed (non-fatal): %s", exc)

    threading.Thread(target=_write, daemon=True).start()


def chunk_text(text, chunk_size=6000, overlap=500):
    """Split text into overlapping chunks (~1500 tokens per 6000 chars)."""
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


def smart_sample_chunks(text, max_chunks=10, chunk_size=6000, overlap=500):
    """Sample representative chunks from a large document.

    Strategy: first 2 + last 2 + evenly spaced middle.
    Returns (sampled_chunks, total_chunk_count) for coverage metadata.
    """
    all_chunks = chunk_text(text, chunk_size, overlap)
    total = len(all_chunks)
    if total <= max_chunks:
        return all_chunks, total

    sampled = all_chunks[:2]
    middle = all_chunks[2:-2]
    remaining = max_chunks - 4
    if middle and remaining > 0:
        step = max(1, len(middle) // remaining)
        sampled.extend(middle[::step][:remaining])
    sampled.extend(all_chunks[-2:])
    return sampled, total


def call_llm_direct(task, max_tokens=4096, temperature=0.3):
    """Call currently loaded model directly. Best for structured JSON extraction."""
    return call_direct(task, max_tokens=max_tokens, temperature=temperature)


def call_llm(task, task_type="coding", max_tokens=4096):
    """Smart LLM call — selects best model for the task type."""
    return call_smart(
        task,
        task_type=task_type,
        max_tokens=max_tokens,
        temperature=0.3,
    )


def call_llm_harness(task, task_type="coding", max_tokens=4096):
    """POST to FTAL harness. Use for tasks that benefit from RAG context."""
    return call_harness(task, task_type=task_type, max_tokens=max_tokens)


def call_llm_scored(task, task_type="reasoning", max_tokens=4096, skip_rag=True):
    """Call FTAL harness and return (result, ftal_scores).

    ftal_scores is a dict with keys: f, t, a, gap.
    Falls back to call_direct() if harness is unreachable OR if gap >= 30.
    When falling back on gap >= 30, returns (direct_text, original_scores)
    so callers still get scores for logging.
    Use for quality-sensitive tasks (narrative generation, career synthesis, coaching).
    """
    text, scores = call_harness_scored(task, task_type=task_type, max_tokens=max_tokens, skip_rag=skip_rag)
    if text is None:
        # Harness unreachable — fall back to direct inference, no scoring
        text = call_direct(task, max_tokens=max_tokens)
        return text, None
    # Gap-threshold fallback: harness output unreliable at gap >= 30
    if scores:
        gap = scores.get("gap")
        model_id = scores.get("model_id", "unknown")
        if gap is not None:
            _record_governance_outcome(task_type, scores, model_id)
        if gap is not None and gap >= _QUALITY_FALLBACK_THRESHOLD:
            logger.info(
                "[FTAL] gap=%d >= %d — falling back to call_direct()",
                gap,
                _QUALITY_FALLBACK_THRESHOLD,
            )
            direct_text = call_direct(task, max_tokens=max_tokens)
            # Set sentinel unconditionally so call_llm_quality() never issues a
            # second call_direct() for this request, even if direct failed here.
            # If direct failed, fall back to the harness text as best available.
            new_scores = scores.copy()
            new_scores["_fell_back"] = True
            return direct_text or text, new_scores
    return text, scores


_QUALITY_FALLBACK_THRESHOLD = 30


def _strip_think_tags(text: str) -> str:
    """Remove <think>...</think> reasoning blocks emitted by Qwen3/DeepSeek thinking models."""
    if text and "<think>" in text:
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return text


def call_llm_quality(task, task_type="reasoning", max_tokens=4096, max_attempts=2, skip_rag=True):
    """Quality-gated LLM call — drop-in replacement for call_llm() at quality-sensitive sites.

    Routes through FTAL harness (skip_rag=True by default). If the harness returns a result with
    gap >= 30 (FTAL fail), falls back to call_direct() which produces better output
    for career content tasks. Logs gap for monitoring.

    Retries up to max_attempts times when text is None (harness unreachable).
    Does NOT retry on gap failures — those go straight to call_direct() fallback.
    """
    for attempt in range(max_attempts):
        text, scores = call_llm_scored(task, task_type=task_type, max_tokens=max_tokens, skip_rag=skip_rag)
        if text is None:
            if attempt < max_attempts - 1:
                time.sleep(2)
                continue
            return None  # all attempts exhausted with text=None
        if scores:
            # Sentinel: call_llm_scored already fell back — skip second call_direct()
            if scores.get("_fell_back"):
                return _strip_think_tags(text)
            gap = scores.get("gap")
            if gap is not None:
                level = logging.WARNING if gap >= _QUALITY_FALLBACK_THRESHOLD else logging.DEBUG
                logger.log(
                    level,
                    "[FTAL] gap=%d f=%s t=%s a=%s",
                    gap,
                    scores.get("f"),
                    scores.get("t"),
                    scores.get("a"),
                )
                if gap >= _QUALITY_FALLBACK_THRESHOLD:
                    logger.info("[FTAL] gap=%d >= threshold — falling back to call_direct()", gap)
                    return call_direct(task, max_tokens=max_tokens)
        return _strip_think_tags(text)


def extract_json(text):
    """3-tier JSON extraction: fenced json -> fenced code -> brace substring."""
    if not text:
        return None

    # Tier 1: fenced ```json blocks
    match = re.search(r"```json\s*([\s\S]*?)```", text)
    if match:
        try:  # noqa: SIM105
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Tier 2: any fenced code block
    match = re.search(r"```\s*([\s\S]*?)```", text)
    if match:
        try:  # noqa: SIM105
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Tier 3: brace substring
    first_brace = text.find("{")
    first_bracket = text.find("[")
    if first_brace == -1 and first_bracket == -1:
        return None

    # Try object
    if first_brace >= 0:
        last_brace = text.rfind("}")
        if last_brace > first_brace:
            try:  # noqa: SIM105
                return json.loads(text[first_brace : last_brace + 1])
            except json.JSONDecodeError:
                pass

    # Try array
    if first_bracket >= 0:
        last_bracket = text.rfind("]")
        if last_bracket > first_bracket:
            try:  # noqa: SIM105
                return json.loads(text[first_bracket : last_bracket + 1])
            except json.JSONDecodeError:
                pass

    return None


def analyze_with_context(
    text, prompt_template, context_summary, task_type="reasoning", max_tokens=4096
):
    """Like analyze_with_chunking() but prepends cross-document context to each chunk prompt."""
    chunks = chunk_text(text)
    all_items = []

    context_block = (
        "=== CROSS-DOCUMENT CONTEXT ===\n"
        f"{context_summary}\n"
        "=== END CONTEXT ===\n\n"
        "Use this context to understand how this document relates to the broader project. "
        "Now analyze the following chunk:\n\n"
    )

    for i, chunk in enumerate(chunks):
        prompt = context_block + prompt_template.format(
            chunk=chunk,
            chunk_num=i + 1,
            total_chunks=len(chunks),
        )
        raw = call_llm(prompt, task_type=task_type, max_tokens=max_tokens)
        if raw:
            parsed = extract_json(raw)
            if isinstance(parsed, list):
                all_items.extend(parsed)
            elif isinstance(parsed, dict):
                all_items.append(parsed)

    return all_items


def analyze_with_chunking(text, prompt_template, task_type="reasoning", max_tokens=4096):
    """Chunk text, analyze each chunk with LLM, collect JSON results."""
    chunks = chunk_text(text)
    all_items = []

    for i, chunk in enumerate(chunks):
        prompt = prompt_template.format(
            chunk=chunk,
            chunk_num=i + 1,
            total_chunks=len(chunks),
        )
        raw = call_llm(prompt, task_type=task_type, max_tokens=max_tokens)
        if raw:
            parsed = extract_json(raw)
            if isinstance(parsed, list):
                all_items.extend(parsed)
            elif isinstance(parsed, dict):
                all_items.append(parsed)

    return all_items


def merge_extracted_items(items_list, key_field):
    """Deduplicate extracted items by a key field, keeping the richest entry."""
    seen = {}
    for item in items_list:
        if not isinstance(item, dict):
            continue
        key = (item.get(key_field) or "").lower().strip()
        if not key:
            continue
        if key not in seen or len(json.dumps(item)) > len(json.dumps(seen[key])):
            seen[key] = item
    return list(seen.values())


@lru_cache(maxsize=128)
def call_llm_quality_cached(task: str, task_type: str = "reasoning", max_tokens: int = 4096) -> str:
    """Cached variant of call_llm_quality for deterministic prompts only.

    Uses LRU cache (maxsize=128) to avoid redundant GPU calls for identical inputs.
    Opt-in: use ONLY for prompts where the same input always yields the same output
    (e.g. skill extraction templates). Do NOT use for user-specific or time-sensitive prompts.
    """
    return call_llm_quality(task, task_type=task_type, max_tokens=max_tokens)


def synthesize_narrative(context, prompt, max_tokens=2048):
    """Generate narrative text from context. Returns raw string."""
    full_prompt = f"{prompt}\n\nContext:\n{context}"
    return call_llm_quality(full_prompt, task_type="reasoning", max_tokens=max_tokens) or ""
