"""Phase 4a: Semantic Deduplication - Find and merge duplicate sources.

Algorithm:
1. Exact match: title + source_type + user_id
2. Fuzzy match: >80% title similarity within 1-day window
3. Merge: Keep higher significance, merge metadata
"""

import logging
from datetime import datetime, timedelta
from difflib import SequenceMatcher

from models import get_db, log_audit_event
from db_engine import as_datetime

_logger = logging.getLogger(__name__)


def find_exact_duplicates(user_id: int) -> list[tuple[int, int]]:
    """Find exact duplicate sources (same title + source_type + user_id).

    Returns list of (keep_id, remove_id) tuples where keep_id has higher or equal significance.
    """
    with get_db() as conn:
        # Group by (user_id, source_type, title) in Python — avoids a
        # dialect-specific aggregate (SQLite GROUP_CONCAT vs Postgres STRING_AGG)
        rows = conn.execute(
            "SELECT id, source_type, title FROM journey_sources WHERE user_id = ?",
            (user_id,),
        ).fetchall()

    groups: dict[tuple[str, str], list[int]] = {}
    for row in rows:
        key = (row["source_type"], row["title"])
        groups.setdefault(key, []).append(row["id"])

    duplicates = []
    for ids in groups.values():
        if len(ids) >= 2:
            # Pair them (keep first, remove others)
            for remove_id in ids[1:]:
                duplicates.append((ids[0], remove_id))

    return duplicates


def find_fuzzy_duplicates(user_id: int, threshold: float = 0.8, day_window: int = 1) -> list[tuple[int, int]]:
    """Find fuzzy duplicate sources (>80% title similarity within 1-day window).

    Returns list of (keep_id, remove_id) tuples.
    """
    with get_db() as conn:
        sources = conn.execute(
            "SELECT id, title, created_at FROM journey_sources WHERE user_id = ? ORDER BY created_at",
            (user_id,)
        ).fetchall()

    duplicates = []
    processed = set()

    for i, source1 in enumerate(sources):
        if source1["id"] in processed:
            continue

        for source2 in sources[i + 1:]:
            if source2["id"] in processed:
                continue

            # Check time window
            date1 = as_datetime(source1["created_at"])
            date2 = as_datetime(source2["created_at"])
            if abs((date2 - date1).days) > day_window:
                continue

            # Check similarity
            sim = string_similarity(source1["title"], source2["title"])
            if sim >= threshold:
                duplicates.append((source1["id"], source2["id"]))
                processed.add(source2["id"])

    return duplicates


def string_similarity(s1: str, s2: str) -> float:
    """Return 0.0-1.0 similarity score."""
    if not s1 or not s2:
        return 0.0
    return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()


def merge_duplicates(user_id: int, duplicates: list[tuple[int, int]]) -> dict:
    """Merge duplicate sources, keeping higher significance one.

    Returns dict with:
      - merged_count: number of merges performed
      - removed_ids: list of source IDs that were removed
      - merged_references: {keep_id: [remove_ids]}
    """
    if not duplicates:
        return {"merged_count": 0, "removed_ids": [], "merged_references": {}}

    with get_db() as conn:
        # Get significance scores for comparison
        remove_ids = set(dup[1] for dup in duplicates)
        keep_ids = set(dup[0] for dup in duplicates)

        # Query to get data for all involved sources
        all_ids = list(remove_ids | keep_ids)
        placeholders = ",".join("?" * len(all_ids))
        sources = conn.execute(
            f"SELECT id, title, significance_score FROM journey_sources WHERE id IN ({placeholders})",
            all_ids
        ).fetchall()

        source_map = {s["id"]: s for s in sources}

    # Process merges: keep higher significance
    actual_merges = []
    removed = set()
    merged_refs = {}

    for keep_id, remove_id in duplicates:
        if remove_id in removed:
            continue

        keep_source = source_map.get(keep_id)
        remove_source = source_map.get(remove_id)

        keep_sig = keep_source["significance_score"] if keep_source else 0
        remove_sig = remove_source["significance_score"] if remove_source else 0

        # If remove has higher significance, swap
        if remove_sig > keep_sig:
            keep_id, remove_id = remove_id, keep_id

        actual_merges.append((keep_id, remove_id))
        removed.add(remove_id)

        if keep_id not in merged_refs:
            merged_refs[keep_id] = []
        merged_refs[keep_id].append(remove_id)

    _logger.info(
        "merge_duplicates: merging %d pair(s), removing %d source(s)",
        len(actual_merges),
        len(removed),
    )

    # Warn + audit before each delete
    for keep_id, remove_id in actual_merges:
        _logger.warning(
            "Deleting source_id=%d (duplicate of %d)",
            remove_id,
            keep_id,
        )
        log_audit_event(
            user_id,
            "journey_source_merged",
            "journey_source",
            str(remove_id),
            {"merged_into": keep_id},
        )

    # Delete removed sources
    if removed:
        with get_db() as conn:
            placeholders = ",".join("?" * len(removed))
            conn.execute(
                f"DELETE FROM journey_sources WHERE id IN ({placeholders})",
                list(removed)
            )
            conn.commit()

    return {
        "merged_count": len(actual_merges),
        "removed_ids": list(removed),
        "merged_references": merged_refs,
    }


def deduplicate(user_id: int, fuzzy_threshold: float = 0.8) -> dict:
    """Full deduplication pipeline: exact + fuzzy + merge.

    Returns summary dict with merge results.
    """
    # Find exact duplicates
    exact = find_exact_duplicates(user_id)

    # Find fuzzy duplicates (skip if already found as exact)
    exact_set = set()
    for keep_id, remove_id in exact:
        exact_set.add(remove_id)

    fuzzy = find_fuzzy_duplicates(user_id, threshold=fuzzy_threshold)
    fuzzy = [(k, r) for k, r in fuzzy if r not in exact_set]

    # Merge all
    all_dups = exact + fuzzy
    result = merge_duplicates(user_id, all_dups)

    result["exact_duplicates"] = len(exact)
    result["fuzzy_duplicates"] = len(fuzzy)

    return result
