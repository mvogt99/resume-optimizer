"""Keyword equivalency interview, rewrite engine, and persistence."""

import json
import logging
import re

from models import get_db

logger = logging.getLogger(__name__)


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
        logger.warning("LLM equiv returned non-JSON: %s", text[:200])
        return fallback


# ── Interview ────────────────────────────────────────────────────────────────

def run_equivalency_turn(
    history: list,
    current_question: str,
    user_answer: str,
    keyword_groups: list,
    resume_text: str,
    job_text: str,
    user_finished: bool = False,
) -> dict:
    """Process one turn of the keyword equivalency interview."""
    turn_count = len(history) + 1
    prior = "\n".join(
        f"Q: {h['question']}\nA: {h['answer']}" for h in history
    )

    # Figure out which keywords are already resolved
    already_resolved = set()
    for h in history:
        for r in h.get("resolved", []):
            already_resolved.add(r.get("keyword", "").lower())

    unresolved_groups = []
    for g in keyword_groups:
        unresolved = [kw for kw in g.get("keywords", [])
                      if kw.lower() not in already_resolved]
        if unresolved:
            unresolved_groups.append({"name": g["name"], "keywords": unresolved})

    all_unresolved = [kw for g in unresolved_groups for kw in g["keywords"]]

    fallback_insight = (
        "Thanks for that context. I'll use this to determine how your experience "
        "maps to the job requirements."
    )
    fallback_resolved = []

    try:
        # Interview turns are real-time conversational — skip harness overhead
        # and go direct to RTX 5090 for sub-10s responses.
        from smart_llm import call_direct

        def _call(prompt: str, max_tokens: int = 500) -> str:
            """Call RTX 5090 directly, bypassing harness for speed."""
            try:
                return call_direct(prompt, max_tokens=max_tokens) or ""
            except Exception:
                # Last-resort fallback to harness path
                from llm_helper import call_llm_quality
                return call_llm_quality(prompt, task_type="reasoning", max_tokens=max_tokens) or ""

        # ── Insight + resolve keywords from this answer ───────────────────
        resolve_prompt = f"""You are a career coach helping a user map their existing \
experience to job description keywords they appear to be "missing."

JOB DESCRIPTION (abbreviated):
{job_text[:800]}

RESUME (abbreviated):
{resume_text[:1000]}

UNRESOLVED KEYWORDS (grouped):
{json.dumps(unresolved_groups, indent=2)}

Prior Q&A:
{prior if prior else '(first turn)'}

Current question: {current_question}
User answer: {user_answer}

Based on the user's answer, determine which "missing" keywords they actually have \
equivalent experience for. Respond with ONLY valid JSON:
{{
  "insight": "<2-3 sentences: acknowledge their answer, explain which keywords their \
experience maps to, give one specific recommendation>",
  "resolved": [
    {{
      "keyword": "<the job keyword>",
      "equivalent": "<what the user actually has/used>",
      "confidence": 0.9,
      "status": "equivalent|partial|confirmed_missing"
    }}
  ]
}}

Rules:
- Only resolve keywords that the user's answer DIRECTLY addresses
- "equivalent" = user has substantially the same capability (e.g., Kinesis ≈ Kafka)
- "partial" = user has related but not identical experience
- "confirmed_missing" = user confirmed they don't have this
- Be conservative: don't resolve keywords the answer doesn't address
- confidence: 0.5-1.0 (how strong is the equivalency)"""

        raw = _call(resolve_prompt, max_tokens=500)
        parsed = _extract_json(raw, {"insight": fallback_insight, "resolved": []})
        insight = parsed.get("insight", fallback_insight)
        resolved = parsed.get("resolved", [])

        # ── Next question (if not finished) ───────────────────────────────
        next_question = None
        if not user_finished and all_unresolved:
            # Remove just-resolved keywords from unresolved
            just_resolved = {r["keyword"].lower() for r in resolved}
            remaining = [kw for kw in all_unresolved if kw.lower() not in just_resolved]

            if remaining:
                remaining_groups = []
                for g in unresolved_groups:
                    left = [kw for kw in g["keywords"] if kw.lower() not in just_resolved]
                    if left:
                        remaining_groups.append({"name": g["name"], "keywords": left})

                nq_prompt = f"""You are a career coach conducting an equivalency interview. \
The user is explaining how their experience maps to keywords from a job description.

Remaining unresolved keywords by group:
{json.dumps(remaining_groups)}

Prior conversation:
{prior}
Q: {current_question}
A: {user_answer}

Ask ONE focused question about the next most important unresolved group. \
Reference specific keywords. Be conversational. \
Reply with ONLY the question text — no preamble."""

                raw_nq = _call(nq_prompt, max_tokens=150)
                next_question = (raw_nq or "").strip()

        suggested_done = (not user_finished) and (
            turn_count >= 3 and len(all_unresolved) <= 3
        )

        return {
            "insight": insight,
            "resolved": resolved,
            "next_question": next_question,
            "suggested_done": suggested_done,
            "is_complete": user_finished or not all_unresolved,
        }

    except Exception as exc:
        logger.warning("Equivalency interview turn failed: %s", exc)
        return {
            "insight": fallback_insight,
            "resolved": fallback_resolved,
            "next_question": None if user_finished else (
                f"Tell me about your experience with: {', '.join(all_unresolved[:5])}"
            ),
            "suggested_done": False,
            "is_complete": user_finished,
        }


# ── Rewrite engine helpers ───────────────────────────────────────────────────


def _expand_original_text(resume_text: str, sample: str) -> str:
    """Expand a possibly-truncated LLM sample to the full section boundary."""
    if not sample or not resume_text:
        return sample
    # Try progressively shorter prefixes until we find an anchor
    for prefix_len in (min(150, len(sample)), min(100, len(sample)), min(60, len(sample))):
        if prefix_len <= 0:
            break
        prefix = sample[:prefix_len]
        idx = resume_text.find(prefix)
        if idx != -1:
            rest = resume_text[idx:]
            # Find next section boundary: 2+ newlines before a capitalised header
            boundary = re.search(
                r'\n{2,}(?=[A-Z][A-Z &/]+\n|'
                r'(?:Professional|Core|Education|Skills|Summary|Experience|'
                r'Certifications?|Projects?|Awards?)\b)',
                rest[40:],
            )
            if boundary:
                return rest[:40 + boundary.start()]
            # No boundary found (last section) — return with generous buffer
            return rest[:max(len(sample) + 300, 600)]
    return sample  # Could not anchor — return as-is; frontend falls back to prefix match


_SECTION_HEADER_RE = re.compile(r'^([A-Z][A-Za-z\s&,/()]{2,40}\n+)')


def _preserve_section_headers(rewrites: list) -> list:
    """Re-prepend section headers that the LLM may have dropped from proposed_text."""
    for rw in rewrites:
        orig = (rw.get("original_text") or "").lstrip("\n")
        prop = rw.get("proposed_text") or ""
        if not orig or not prop:
            continue
        m = _SECTION_HEADER_RE.match(orig)
        if not m:
            continue
        header = m.group(1)          # e.g. "Professional Summary\n\n"
        header_stripped = header.strip()
        # Check whether proposed_text already starts with the header
        if not prop.strip().startswith(header_stripped):
            rw["proposed_text"] = header + prop.lstrip("\n")
    return rewrites


def _deduplicate_rewrites(rewrites: list, resume_text: str) -> list:
    """Collapse multiple rewrites targeting the same section into one."""
    seen: dict[str, int] = {}   # prefix → index in merged list
    merged: list[dict] = []
    for rw in rewrites:
        anchor = (rw.get("original_text") or "")[:80]
        if anchor and anchor in seen:
            existing = merged[seen[anchor]]
            # Keep longer proposed_text; union keywords
            if len(rw.get("proposed_text", "")) > len(existing.get("proposed_text", "")):
                existing["proposed_text"] = rw["proposed_text"]
            existing.setdefault("keywords_addressed", [])
            for kw in rw.get("keywords_addressed", []):
                if kw not in existing["keywords_addressed"]:
                    existing["keywords_addressed"].append(kw)
        else:
            if anchor:
                seen[anchor] = len(merged)
            # Expand original_text so frontend can match it
            rw["original_text"] = _expand_original_text(resume_text, rw.get("original_text", ""))
            merged.append(rw)
    return merged


# ── Rewrite engine ───────────────────────────────────────────────────────────


def _get_user_edits(original: str, current: str) -> list[tuple[str, str]]:
    """Return pairs of (original_line, user_edited_line) for lines the user changed."""
    if not original or not current or original.strip() == current.strip():
        return []
    orig_lines = original.strip().splitlines()
    curr_lines = current.strip().splitlines()
    orig_set = set(orig_lines)
    curr_set = set(curr_lines)
    removed = [l for l in orig_lines if l.strip() and l not in curr_set]
    added = [l for l in curr_lines if l.strip() and l not in orig_set]
    paired = []
    used_added = set()
    for r in removed:
        r_words = set(r.lower().split())
        if not r_words:
            continue
        best_a, best_overlap = None, 0.0
        for i, a in enumerate(added):
            if i in used_added:
                continue
            a_words = set(a.lower().split())
            if not a_words:
                continue
            overlap = len(r_words & a_words) / max(len(r_words), len(a_words))
            if overlap >= 0.25 and overlap > best_overlap:
                best_a, best_overlap = i, overlap
        if best_a is not None:
            paired.append((r.strip(), added[best_a].strip()))
            used_added.add(best_a)
    return paired[:20]


def _reapply_user_edits(proposed: str, edit_pairs: list[tuple[str, str]]) -> str:
    """Re-apply user edits that the LLM reverted in its proposed_text."""
    if not edit_pairs or not proposed:
        return proposed
    result = proposed
    for orig_line, user_line in edit_pairs:
        if orig_line in result and user_line not in result:
            result = result.replace(orig_line, user_line, 1)
    return result


def generate_rewrites(
    resolved_keywords: list,
    resume_text: str,
    job_text: str,
    original_text: str = "",
) -> dict:
    """Generate section-by-section resume rewrites incorporating equivalencies.

    original_text: pre-edit resume text — edits are deterministically re-applied
    after LLM generation to prevent the LLM from reverting user corrections.
    """
    equivalents = [r for r in resolved_keywords
                   if r.get("status") in ("equivalent", "partial")]

    if not equivalents:
        return {"rewrites": []}

    # Skip keywords whose JD term is already present verbatim in the current resume —
    # either the user typed it manually or a prior rewrite already added it.
    # This prevents re-suggesting changes the user already made.
    resume_lower = resume_text.lower()
    equivalents = [
        r for r in equivalents
        if (r.get("keyword") or "").lower().strip() not in resume_lower
    ]
    if not equivalents:
        return {"rewrites": []}

    fallback = {"rewrites": [{
        "section": "Full Resume",
        "original_text": resume_text[:500],
        "proposed_text": resume_text[:500],
        "keywords_addressed": [r["keyword"] for r in equivalents],
    }]}

    try:
        from smart_llm import call_direct

        equiv_summary = "\n".join(
            f"- {r['keyword']} → user has: {r['equivalent']} "
            f"(confidence: {r.get('confidence', 0.8)}, status: {r['status']})"
            for r in equivalents
        )

        # Note keywords already in resume via equivalent phrase — LLM should not
        # undo those sections, only add the JD keyword as a cross-reference qualifier.
        already_in_resume = [
            r for r in equivalents
            if (r.get("equivalent") or "").lower().strip() in resume_lower
        ]
        already_note = ""
        if already_in_resume:
            already_note = (
                "\nNOTE: The following equivalent phrases ARE already present in the "
                "resume. For these, just add the JD keyword as a parenthetical qualifier "
                "(e.g., 'event streaming (Kafka-compatible)') — do NOT rewrite the whole section:\n"
                + "\n".join(f"  - {r['equivalent']} (JD term: {r['keyword']})" for r in already_in_resume)
            )

        # Detect user edits for deterministic post-processing (re-applied after LLM)
        edit_pairs = _get_user_edits(original_text, resume_text) if original_text else []

        prompt = f"""You are an expert resume editor. Rewrite sections of this resume \
to naturally incorporate equivalent terminology for job description keywords.

JOB DESCRIPTION (abbreviated):
{job_text[:1000]}

EQUIVALENCY MAPPINGS (from user interview):
{equiv_summary}{already_note}

CURRENT RESUME:
{resume_text}

For each resume section that can be improved, provide the original text and \
a proposed rewrite that naturally weaves in the job description keywords \
alongside the user's actual terminology.

Respond with ONLY valid JSON:
{{
  "rewrites": [
    {{
      "section": "<section name, e.g., 'Professional Summary', 'AHEAD Experience'>",
      "original_text": "<the original text from the resume for this section — copy it verbatim, do not shorten>",
      "proposed_text": "<rewritten version with equivalency terms woven in>",
      "keywords_addressed": ["<keyword1>", "<keyword2>"]
    }}
  ]
}}

Rules:
- Only include sections where a meaningful change is possible
- Keep the user's real experience as the anchor — add job keywords as qualifiers
  (e.g., "Kinesis/Kafka-compatible event streaming" not "Kafka experience")
- Do NOT fabricate experience — only bridge terminology
- CRITICAL: produce at most ONE rewrite per section — if multiple keywords apply
  to the same section, combine ALL changes into that single proposed_text
- 2-5 rewrites max, one per section
- Each rewrite should address 1-4 keywords
- original_text MUST be COMPLETE verbatim text of that section — do not truncate
- PRESERVE ALL user customizations: company names, role titles, details."""

        raw = call_direct(prompt, max_tokens=4096) or ""
        result = _extract_json(raw, fallback)
        # Post-process: expand truncated originals + merge duplicates + restore headers
        if result.get("rewrites"):
            result["rewrites"] = _deduplicate_rewrites(result["rewrites"], resume_text)
            result["rewrites"] = _preserve_section_headers(result["rewrites"])
            # Deterministic: re-apply user edits the LLM may have reverted
            if edit_pairs:
                for rw in result["rewrites"]:
                    if rw.get("proposed_text"):
                        rw["proposed_text"] = _reapply_user_edits(
                            rw["proposed_text"], edit_pairs
                        )
        return result

    except Exception as exc:
        logger.warning("Rewrite generation failed: %s", exc)
        return fallback


# ── Persistence ──────────────────────────────────────────────────────────────


def save_equivalencies(user_id: int, resolved: list) -> int:
    """Persist resolved keyword equivalencies. Returns count saved."""
    saved = 0
    equivalents = [r for r in resolved
                   if r.get("status") in ("equivalent", "partial")
                   and r.get("keyword") and r.get("equivalent")]

    with get_db() as conn:
        for r in equivalents:
            conn.execute(
                "INSERT INTO keyword_equivalencies "
                "(user_id, job_keyword, equivalent_phrase, confidence, status) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(user_id, job_keyword) DO UPDATE SET "
                "equivalent_phrase=excluded.equivalent_phrase, "
                "confidence=excluded.confidence, "
                "status=excluded.status, "
                "updated_at=CURRENT_TIMESTAMP",
                (
                    user_id,
                    r["keyword"].strip(),
                    r["equivalent"].strip(),
                    r.get("confidence", 0.8),
                    r.get("status", "equivalent"),
                ),
            )
            saved += 1
        conn.commit()
    return saved


def get_equivalencies(user_id: int) -> list:
    """Retrieve all persisted equivalencies for a user. Returns list of dicts."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT job_keyword, equivalent_phrase, confidence, status, "
            "created_at, updated_at "
            "FROM keyword_equivalencies WHERE user_id = ? "
            "ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
    return [
        {
            "job_keyword": r["job_keyword"],
            "equivalent_phrase": r["equivalent_phrase"],
            "confidence": r["confidence"],
            "status": r["status"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]


def delete_equivalency(user_id: int, job_keyword: str) -> bool:
    """Remove a single persisted equivalency."""
    with get_db() as conn:
        cursor = conn.execute(
            "DELETE FROM keyword_equivalencies WHERE user_id = ? AND job_keyword = ?",
            (user_id, job_keyword),
        )
        conn.commit()
    return cursor.rowcount > 0
