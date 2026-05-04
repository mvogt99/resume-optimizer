"""LLM-powered semantic matching of job keywords to saved user equivalencies.

Used when exact-string matching fails: the LLM judges whether a missing keyword
and a saved equivalency cover the same underlying skill or competency.
"""

import json
import logging

logger = logging.getLogger(__name__)


def _extract_json(text: str, fallback: dict) -> dict:
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
        logger.warning("Matcher LLM returned non-JSON: %s", text[:200])
        return fallback


def suggest_semantic_matches(
    missing_keywords: list,
    saved_equivalencies: list,
    job_text: str = "",
) -> dict:
    """Semantically match missing keywords to saved equivalencies via LLM.

    Only called for keywords that did not exact-match. The LLM judges whether
    the underlying skill or competency is the same, even if terminology differs.

    Args:
        missing_keywords:   Keywords still unresolved after exact match.
        saved_equivalencies: List of {job_keyword, equivalent_phrase, confidence, status}.
        job_text:           Job description text for context (optional).

    Returns:
        {
          suggestions: [
            {
              keyword: str,           # the missing keyword
              saved_keyword: str,     # which saved equivalency matches
              equivalent_phrase: str, # the user's saved phrase
              confidence: float,      # 0.5–1.0
              rationale: str,         # one-sentence explanation
              status: str,            # from saved equivalency
            }
          ],
          unmatched: [str],           # keywords with no reasonable match
        }
    """
    if not missing_keywords or not saved_equivalencies:
        return {"suggestions": [], "unmatched": list(missing_keywords)}

    saved_list = "\n".join(
        f'- "{eq["job_keyword"]}" → {eq["equivalent_phrase"][:120]}'
        for eq in saved_equivalencies
        if eq.get("job_keyword") and eq.get("equivalent_phrase")
    )

    kw_list = "\n".join(f"- {kw}" for kw in missing_keywords)

    # Build a quick lookup so we can enrich suggestions with full saved data
    saved_map = {
        eq["job_keyword"].lower(): eq
        for eq in saved_equivalencies
        if eq.get("job_keyword")
    }

    prompt = f"""You are matching job description keywords to a user's saved professional \
equivalencies. For each missing keyword, determine if any saved equivalency covers \
the same underlying skill or competency—even if the exact wording differs.

{f'JOB DESCRIPTION CONTEXT:{chr(10)}{job_text[:500]}{chr(10)}' if job_text else ''}
MISSING KEYWORDS (need to be matched or left unmatched):
{kw_list}

SAVED EQUIVALENCIES (user's verified experience):
{saved_list}

Respond with ONLY valid JSON:
{{
  "suggestions": [
    {{
      "keyword": "<the missing keyword>",
      "saved_keyword": "<exact job_keyword from saved equivalencies>",
      "equivalent_phrase": "<the user phrase from saved>",
      "confidence": 0.8,
      "rationale": "<one sentence: why this is a semantic match>"
    }}
  ],
  "unmatched": ["<keywords with no reasonable match>"]
}}

Rules:
- Only suggest a match when the underlying competency genuinely overlaps
- confidence ≥ 0.7 = clear match; 0.5–0.69 = related but indirect
- Omit suggestions with confidence < 0.5 — put those keyword in unmatched instead
- Multiple missing keywords may map to the same saved equivalency (that is fine)
- A keyword that is irrelevant to professional qualifications (e.g. compensation,
  insurance benefits) should go in unmatched
- Do NOT fabricate equivalencies — only use phrases from SAVED EQUIVALENCIES above
- saved_keyword must be the EXACT string from the saved list above"""

    fallback = {"suggestions": [], "unmatched": list(missing_keywords)}

    try:
        from smart_llm import call_direct
        raw = call_direct(prompt, max_tokens=1500) or ""
        parsed = _extract_json(raw, fallback)

        # Enrich suggestions with saved equivalency data
        suggestions = []
        accounted = set()
        for s in parsed.get("suggestions", []):
            saved_kw = (s.get("saved_keyword") or "").lower()
            saved_entry = saved_map.get(saved_kw)
            if saved_entry:
                suggestions.append({
                    "keyword": s["keyword"],
                    "saved_keyword": s.get("saved_keyword", ""),
                    "equivalent_phrase": saved_entry.get("equivalent_phrase", s.get("equivalent_phrase", "")),
                    "confidence": float(s.get("confidence", 0.7)),
                    "rationale": s.get("rationale", ""),
                    "status": saved_entry.get("status", "equivalent"),
                })
                accounted.add(s["keyword"].lower())

        # Any keyword the LLM listed in unmatched, or didn't mention at all
        all_missing_lower = {kw.lower(): kw for kw in missing_keywords}
        for kw_lower, kw in all_missing_lower.items():
            if kw_lower not in accounted:
                pass  # handled by unmatched list below

        # Build final unmatched from LLM output + anything the LLM forgot to address
        llm_unmatched = {u.lower() for u in parsed.get("unmatched", [])}
        unmatched = [kw for kw in missing_keywords if kw.lower() in llm_unmatched or kw.lower() not in accounted]

        return {"suggestions": suggestions, "unmatched": unmatched}

    except Exception as exc:
        logger.warning("Semantic matching failed: %s", exc)
        return fallback
