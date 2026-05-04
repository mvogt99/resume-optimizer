"""Semantic grouping of keywords from a job description.

Groups a flat list of missing/matching keywords into meaningful categories
using LLM analysis of the job description context. Users can rename groups
and move keywords between them.
"""

import json
import logging
import re

logger = logging.getLogger(__name__)

# Minimum token length for overlap matching (skip "a", "of", "in", etc.)
_MIN_TOKEN_LEN = 3

# Common filler words that shouldn't drive equivalency matching
_MATCH_STOPWORDS = frozenset({
    "and", "the", "for", "with", "from", "into", "that", "this", "what",
    "how", "who", "are", "was", "were", "has", "have", "been", "being",
    "can", "will", "may", "not", "all", "any", "each", "but", "its",
    "our", "their", "your", "more", "most", "also", "such", "than",
    "other", "well", "both", "over", "only", "through", "between",
    "about", "using", "based", "including", "across",
})


def _tokenize_for_match(phrase: str) -> set:
    """Split a phrase into significant lowercase tokens for overlap matching."""
    tokens = set(re.findall(r"[a-z][a-z0-9+#.-]+", phrase.lower()))
    return {t for t in tokens if len(t) >= _MIN_TOKEN_LEN and t not in _MATCH_STOPWORDS}


def match_keyword_to_equivalencies(keyword: str, equiv_map: dict) -> dict | None:
    """Match a keyword against an equivalency map using token overlap.

    First tries exact match, then falls back to token overlap.
    A match requires that every significant token in the keyword appears
    in at least one equivalency key, OR the keyword is a substring of a key.

    Args:
        keyword: The NLP-extracted keyword to match.
        equiv_map: dict mapping lowercase job_keyword → equivalency dict.

    Returns:
        The matching equivalency dict, or None.
    """
    kw_lower = keyword.lower().strip()

    # 1. Exact match (fast path)
    if kw_lower in equiv_map:
        return equiv_map[kw_lower]

    # 2. Substring match: keyword appears inside an equivalency key
    #    e.g., "architectural" matches "architectural ownership"
    for eq_key, eq_val in equiv_map.items():
        if kw_lower in eq_key or eq_key in kw_lower:
            return eq_val

    # 3. Token overlap: keyword tokens are a subset of equivalency key tokens
    kw_tokens = _tokenize_for_match(kw_lower)
    if not kw_tokens:
        return None

    best_match = None
    best_overlap = 0

    for eq_key, eq_val in equiv_map.items():
        eq_tokens = _tokenize_for_match(eq_key)
        if not eq_tokens:
            continue
        overlap = kw_tokens & eq_tokens
        if not overlap:
            continue
        # Require: all kw tokens found in eq key, OR all eq tokens found in kw
        # This prevents "data" matching "data governance" AND "data pipeline"
        kw_coverage = len(overlap) / len(kw_tokens)
        eq_coverage = len(overlap) / len(eq_tokens)
        if kw_coverage >= 1.0 or eq_coverage >= 1.0:
            # Perfect subset — strong match
            score = len(overlap) * 2
        elif kw_coverage >= 0.5 and len(overlap) >= 2:
            # Partial but significant overlap (at least 2 tokens, 50%+ coverage)
            score = len(overlap)
        else:
            continue

        if score > best_overlap:
            best_overlap = score
            best_match = eq_val

    return best_match

# Group names whose contents describe the employer, not required candidate skills.
# Groups whose names contain any of these words/phrases get flagged as employer groups.
_EMPLOYER_GROUP_SIGNALS = frozenset({
    "benefit", "benefits", "perk", "perks", "culture", "diversity", "inclusion",
    "compensation", "salary", "equity", "401", "insurance", "vacation", "pto",
    "remote", "hybrid", "office", "work environment", "equal opportunity",
    "work-life", "work life",
})


def _is_employer_group(name: str) -> bool:
    """Return True if the group name indicates an employer-description group."""
    low = name.lower()
    return any(sig in low for sig in _EMPLOYER_GROUP_SIGNALS)


def _extract_json(text: str, fallback: dict) -> dict:
    """Parse JSON from LLM response, stripping markdown fences if present."""
    if not text:
        return fallback
    cleaned = text.strip()
    for fence in ("```json", "```"):
        if fence in cleaned:
            start = cleaned.find(fence) + len(fence)
            end = cleaned.find("```", start)
            if end > start:
                cleaned = cleaned[start:end].strip()
                break
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        logger.warning("LLM grouping returned non-JSON: %s", text[:200])
        return fallback


def group_keywords(keywords: list, job_text: str) -> dict:
    """Group a flat list of keywords into semantic categories.

    Uses LLM to analyze the job description and create custom groups
    (e.g., 'Streaming Technologies', 'Healthcare/Compliance', etc.).

    Args:
        keywords: List of keyword strings to group.
        job_text:  Job description text for context.

    Returns:
        {
          groups: [
            {name: str, keywords: [str], description: str}
          ]
        }
    """
    if not keywords:
        return {"groups": []}

    # Fallback: single "Uncategorized" group
    fallback = {
        "groups": [{"name": "All Keywords", "keywords": keywords, "description": ""}]
    }

    if len(keywords) < 3:
        return fallback

    try:
        from llm_helper import call_llm_quality

        kw_list = ", ".join(keywords[:40])
        prompt = f"""You are a career technology analyst. Group these keywords from a job \
description into semantic categories.

JOB DESCRIPTION (abbreviated):
{job_text[:1200]}

KEYWORDS TO GROUP:
{kw_list}

Create 3-7 groups based on what makes sense for THIS specific job. Each keyword \
must appear in exactly one group. Name groups specifically to the domain \
(e.g., "Streaming & Event Processing" not just "Technologies").

Respond with ONLY valid JSON:
{{
  "groups": [
    {{
      "name": "<specific group name>",
      "keywords": ["<keyword1>", "<keyword2>"],
      "description": "<one sentence explaining why these belong together in context of this role>"
    }}
  ]
}}

Rules:
- Every keyword from the input MUST appear in exactly one group
- Do NOT add keywords that weren't in the input list
- Groups should have 2-8 keywords each
- Order groups by relevance to the job (most important first)"""

        raw = call_llm_quality(prompt, task_type="analysis", max_tokens=800)
        result = _extract_json(raw, fallback)

        groups = result.get("groups", [])
        if not groups:
            return fallback

        # Validate: every input keyword must appear somewhere
        grouped_kws = set()
        for g in groups:
            for kw in g.get("keywords", []):
                grouped_kws.add(kw.lower())

        # Add any missing keywords to an "Other" group
        missing_placement = [kw for kw in keywords if kw.lower() not in grouped_kws]
        if missing_placement:
            groups.append({
                "name": "Other",
                "keywords": missing_placement,
                "description": "Keywords not assigned to a specific category.",
            })

        # Post-process each group:
        # 1. Remove keywords whose text is identical (case-insensitive) to the group name —
        #    these are category headers extracted from the JD, not skills to gap-check.
        # 2. Flag employer-description groups so the frontend can offer a quick-exclude.
        cleaned = []
        for g in groups:
            group_name_lower = g.get("name", "").lower()
            filtered_kws = [
                kw for kw in g.get("keywords", [])
                if kw.lower().strip() != group_name_lower
            ]
            if not filtered_kws:
                continue  # entire group was just group-name echoes — drop it
            entry = {**g, "keywords": filtered_kws}
            if _is_employer_group(g.get("name", "")):
                entry["employer_group"] = True
            cleaned.append(entry)

        return {"groups": cleaned}

    except Exception as exc:
        logger.warning("Keyword grouping LLM call failed: %s", exc)
        return fallback


def build_equiv_map(equivalencies: list) -> dict:
    """Build a lowercase job_keyword → equivalency dict from a list of equivalencies."""
    equiv_map = {}
    for eq in equivalencies:
        key = (eq.get("job_keyword") or "").lower()
        if key and key not in equiv_map:
            equiv_map[key] = eq
    return equiv_map


def apply_persisted_equivalencies(
    missing_keywords: list, equivalencies: list
) -> tuple:
    """Split missing keywords using persisted equivalency mappings.

    Uses token-overlap matching so single-word NLP tokens like "architectural"
    match multi-word equivalency keys like "architectural ownership".

    Args:
        missing_keywords: List of keyword strings currently classified as missing.
        equivalencies:    List of {job_keyword, equivalent_phrase, confidence} dicts.

    Returns:
        (still_missing: list[str], auto_resolved: list[{keyword, equivalent, confidence}])
    """
    equiv_map = build_equiv_map(equivalencies)

    still_missing = []
    auto_resolved = []
    # Track which equiv keys have been used to avoid double-counting
    used_eq_keys = set()

    for kw in missing_keywords:
        match = match_keyword_to_equivalencies(kw, equiv_map)
        if match:
            matched_key = (match.get("job_keyword") or "").lower()
            # Skip not_applicable and confirmed_missing statuses
            status = match.get("status") or "equivalent"
            if status == "not_applicable":
                # Don't count as missing or resolved — just drop it
                continue
            if status == "confirmed_missing":
                still_missing.append(kw)
                continue
            auto_resolved.append({
                "keyword": kw,
                "equivalent": match.get("equivalent_phrase", ""),
                "confidence": match.get("confidence", 0.8),
            })
            used_eq_keys.add(matched_key)
        else:
            still_missing.append(kw)

    return still_missing, auto_resolved
