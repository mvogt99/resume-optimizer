"""Persistent user corrections — Fix A (persistence) + Fix B (fuzzy matching).

Corrections survive session boundaries and are applied after every LLM generation.
Schema: resume_corrections(id, user_id, resume_id, old_text, new_text, created_at, is_active)
  - resume_id NULL  → applies to ALL resumes for this user
  - resume_id SET   → applies only to that specific resume (default for new corrections)
"""

import re
from typing import Optional

from models import get_db

# ---------------------------------------------------------------------------
# Stop-words filtered during token overlap comparison
# ---------------------------------------------------------------------------
_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "are", "was", "were",
    "has", "have", "been", "not", "but", "its", "our", "your", "their", "they",
    "will", "can", "may", "also", "into", "more", "than", "each", "all", "any",
    "both", "few", "most", "other", "some", "which", "while", "when", "where",
    "who", "how", "what", "such", "upon", "over", "under", "above", "below",
    "across", "through", "about", "those", "these", "then", "than",
}

_FUZZY_THRESHOLD = 0.70


def init_corrections_table() -> None:
    """Create resume_corrections table if it doesn't exist."""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS resume_corrections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                resume_id TEXT DEFAULT NULL,
                old_text TEXT NOT NULL,
                new_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            );
            CREATE INDEX IF NOT EXISTS idx_rc_user ON resume_corrections(user_id, is_active);
        """)


init_corrections_table()


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def save_correction(
    user_id: int,
    old_text: str,
    new_text: str,
    resume_id: Optional[str] = None,
) -> int:
    """Persist a correction. Returns new row id."""
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO resume_corrections (user_id, resume_id, old_text, new_text) "
            "VALUES (?, ?, ?, ?)",
            (user_id, resume_id, old_text.strip(), new_text.strip()),
        )
        conn.commit()
        return cur.lastrowid


def get_corrections(
    user_id: int,
    resume_id: Optional[str] = None,
) -> list[dict]:
    """Return active corrections for user, filtered by resume scope.

    When resume_id is given: returns corrections where this resume matches OR
    resume_id is NULL (global for this user).
    When resume_id is None: returns all active corrections for the user.
    """
    with get_db() as conn:
        if resume_id is not None:
            rows = conn.execute(
                "SELECT * FROM resume_corrections "
                "WHERE user_id = ? AND is_active = 1 "
                "AND (resume_id = ? OR resume_id IS NULL) "
                "ORDER BY id",
                (user_id, resume_id),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM resume_corrections "
                "WHERE user_id = ? AND is_active = 1 ORDER BY id",
                (user_id,),
            ).fetchall()
    return [dict(r) for r in rows]


def delete_correction(correction_id: int, user_id: int) -> bool:
    """Soft-delete a correction (set is_active=0). Returns True if a row was updated."""
    with get_db() as conn:
        cur = conn.execute(
            "UPDATE resume_corrections SET is_active = 0 "
            "WHERE id = ? AND user_id = ?",
            (correction_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Apply corrections to text
# ---------------------------------------------------------------------------

def apply_corrections(
    text: str,
    user_id: int,
    resume_id: Optional[str] = None,
) -> tuple[str, list[dict], list[dict]]:
    """Apply all active corrections for this user/resume to text.

    Returns:
        (corrected_text, applied_list, failed_list)
        applied_list — corrections that matched and were applied
        failed_list  — corrections that could not be matched
    """
    corrections = get_corrections(user_id, resume_id=resume_id)
    applied, failed = [], []
    result = text
    for c in corrections:
        old, new = c["old_text"], c["new_text"]
        # 1. Exact match
        if old in result:
            result = result.replace(old, new, 1)
            applied.append(c)
            continue
        # 2. Fuzzy match (Fix B)
        fuzzy_result = _fuzzy_apply(result, old, new, threshold=_FUZZY_THRESHOLD)
        if fuzzy_result is not None:
            result = fuzzy_result
            applied.append(c)
        else:
            failed.append(c)
    return result, applied, failed


# ---------------------------------------------------------------------------
# Fuzzy matching internals (Fix B)
# ---------------------------------------------------------------------------

def _tokenize_for_match(text: str) -> set:
    """Extract significant tokens (length ≥ 3, not stopwords)."""
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9\-']*", text.lower())
    return {t for t in tokens if len(t) >= 3 and t not in _STOPWORDS}


def _token_overlap(a: str, b: str) -> float:
    """Jaccard token overlap between two text fragments."""
    ta, tb = _tokenize_for_match(a), _tokenize_for_match(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _token_containment(needle: str, haystack: str) -> float:
    """Fraction of needle's tokens that appear in haystack.

    Better than Jaccard for line-matching: a correction phrase in a long line
    scores 1.0 even when the line has many unrelated words.
    """
    tn = _tokenize_for_match(needle)
    th = _tokenize_for_match(haystack)
    if not tn:
        return 0.0
    return len(tn & th) / len(tn)


def _fuzzy_apply(
    text: str,
    old_text: str,
    new_text: str,
    threshold: float = _FUZZY_THRESHOLD,
) -> Optional[str]:
    """Find the line in text with highest token overlap to old_text.

    If similarity >= threshold, apply the correction to that line:
    - If old_text appears verbatim in the line: substring replace
    - Otherwise: replace the overlapping token span within the line
    Returns the corrected text, or None if no line meets the threshold.
    """
    lines = text.split("\n")
    best_score = 0.0
    best_idx = -1
    for i, line in enumerate(lines):
        # Use containment: what fraction of old_text tokens appear in this line?
        # Jaccard penalises long lines; containment does not.
        score = _token_containment(old_text, line)
        if score > best_score:
            best_score = score
            best_idx = i
    if best_score < threshold or best_idx < 0:
        return None
    target_line = lines[best_idx]
    # Try exact substring first
    if old_text in target_line:
        lines[best_idx] = target_line.replace(old_text, new_text, 1)
        return "\n".join(lines)
    # Partial: find the longest contiguous span of old_text tokens in the line
    # and replace that span with new_text
    replaced = _replace_token_span(target_line, old_text, new_text)
    lines[best_idx] = replaced
    return "\n".join(lines)


def _replace_token_span(line: str, old_text: str, new_text: str) -> str:
    """Replace the token-overlapping span in line with new_text.

    Finds the start/end positions of old_text tokens within line and
    substitutes new_text for that span. Falls back to appending if span
    is too ambiguous.
    """
    old_tokens = _tokenize_for_match(old_text)
    words = re.split(r"(\s+)", line)  # preserve whitespace
    # Find index range in words that overlaps most with old_tokens
    best_start, best_end, best_count = 0, len(words), 0
    window_size = max(4, len(old_text.split()))
    for start in range(0, len(words), 2):  # step 2: skip whitespace tokens
        end = min(start + window_size * 2, len(words))
        span_text = "".join(words[start:end])
        overlap = len(_tokenize_for_match(span_text) & old_tokens)
        if overlap > best_count:
            best_count = overlap
            best_start, best_end = start, end
    if best_count == 0:
        return line
    prefix = "".join(words[:best_start])
    suffix = "".join(words[best_end:])
    return prefix + new_text + suffix
