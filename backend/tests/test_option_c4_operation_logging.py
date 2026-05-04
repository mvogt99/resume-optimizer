"""Option C4: Operation logging in journey_scorer.py and journey_dedup.py.

Tests verify:
  - score_event() emits a DEBUG log containing the title and score
  - classify_event() emits a DEBUG log containing the classification result
  - merge_duplicates() emits INFO log with merge counts
  - merge_duplicates() emits WARNING before DELETE
  - merge_duplicates() calls log_audit_event for each merge
Mutations: remove each log/audit call → the corresponding test must fail.
"""

import logging
from contextlib import contextmanager
from unittest.mock import MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# journey_scorer tests
# ---------------------------------------------------------------------------


def test_score_event_emits_debug_log(caplog):
    """score_event() logs at DEBUG with title and score in the message."""
    from journey_scorer import score_event

    source = {"title": "feat: add pipeline", "source_type": "git_commit", "full_text": ""}
    with caplog.at_level(logging.DEBUG, logger="journey_scorer"):
        result = score_event(source)

    assert result >= 1
    assert any(
        "score_event" in r.message and "feat: add pipeline" in r.message
        for r in caplog.records
    ), f"Expected DEBUG log with title. Records: {[r.message for r in caplog.records]}"


def test_classify_event_emits_debug_log(caplog):
    """classify_event() logs at DEBUG with the classification result."""
    from journey_scorer import classify_event

    source = {"title": "feat: new feature", "source_type": "git_commit", "classification": ""}
    with caplog.at_level(logging.DEBUG, logger="journey_scorer"):
        result = classify_event(source)

    assert result == "achievement"
    assert any(
        "classify_event" in r.message and "achievement" in r.message
        for r in caplog.records
    ), f"Expected DEBUG log with result. Records: {[r.message for r in caplog.records]}"


# ---------------------------------------------------------------------------
# journey_dedup tests — use mock DB to avoid real DB dependency
# ---------------------------------------------------------------------------


@contextmanager
def _mock_db_with_sources():
    """Context manager that yields a mock connection returning two test sources."""
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [
        {"id": 10, "title": "source A", "significance_score": 3},
        {"id": 20, "title": "source B", "significance_score": 2},
    ]
    yield conn


def test_merge_duplicates_logs_info(caplog):
    """merge_duplicates() emits INFO with merge count when pairs are provided."""
    from journey_dedup import merge_duplicates

    with patch("journey_dedup.get_db", _mock_db_with_sources), \
         patch("journey_dedup.log_audit_event"):
        with caplog.at_level(logging.INFO, logger="journey_dedup"):
            merge_duplicates(user_id=1, duplicates=[(10, 20)])

    assert any(
        "merge_duplicates" in r.message and "1" in r.message
        for r in caplog.records
    ), f"Expected INFO merge log. Records: {[r.message for r in caplog.records]}"


def test_merge_duplicates_logs_warning_before_delete(caplog):
    """merge_duplicates() emits WARNING naming source_id being deleted."""
    from journey_dedup import merge_duplicates

    with patch("journey_dedup.get_db", _mock_db_with_sources), \
         patch("journey_dedup.log_audit_event"):
        with caplog.at_level(logging.WARNING, logger="journey_dedup"):
            merge_duplicates(user_id=1, duplicates=[(10, 20)])

    assert any(
        "Deleting" in r.message and "20" in r.message
        for r in caplog.records
    ), f"Expected WARNING with source_id. Records: {[r.message for r in caplog.records]}"


def test_merge_duplicates_calls_audit_event():
    """merge_duplicates() calls log_audit_event once per merged pair."""
    from journey_dedup import merge_duplicates

    with patch("journey_dedup.get_db", _mock_db_with_sources), \
         patch("journey_dedup.log_audit_event") as mock_audit:
        merge_duplicates(user_id=1, duplicates=[(10, 20)])

    assert mock_audit.call_count == 1
    args = mock_audit.call_args[0]
    assert args[0] == 1                         # user_id
    assert args[1] == "journey_source_merged"   # event_type
    assert args[2] == "journey_source"          # resource_type
    assert args[3] == "20"                      # resource_id (the removed one)
