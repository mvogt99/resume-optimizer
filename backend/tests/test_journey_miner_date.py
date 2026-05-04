"""Tests for journey_miner._extract_date() — date extraction with validation.

12 tests covering valid dates, invalid dates, edge cases.
Bug fix: previously accepted any 8 digits (e.g. phone numbers → 9092-36-89).
"""

import os
import sys

import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from journey_miner import _extract_date  # noqa: E402

# ---------------------------------------------------------------------------
# Valid dates
# ---------------------------------------------------------------------------


class TestValidDates:

    def test_iso_format(self):
        """Standard YYYY-MM-DD extracts correctly."""
        assert _extract_date("report_2026-03-09_final.md") == "2026-03-09"

    def test_underscore_format(self):
        """YYYY_MM_DD converts to dashes."""
        assert _extract_date("session_2026_01_15.json") == "2026-01-15"

    def test_compact_format(self):
        """YYYYMMDD splits into YYYY-MM-DD."""
        assert _extract_date("snapshot_20260309.json") == "2026-03-09"

    def test_year_boundary_low(self):
        """Year 2000 is valid."""
        assert _extract_date("legacy_2000-01-01.txt") == "2000-01-01"

    def test_year_boundary_high(self):
        """Year 2099 is valid."""
        assert _extract_date("future_2099-12-31.dat") == "2099-12-31"

    def test_first_valid_pattern_wins(self):
        """When text has multiple dates, first match (ISO) wins."""
        text = "meeting_2026-03-09_notes_20260315.md"
        assert _extract_date(text) == "2026-03-09"


# ---------------------------------------------------------------------------
# Invalid dates — must return None or skip to next pattern
# ---------------------------------------------------------------------------


class TestInvalidDates:

    def test_month_13(self):
        """Month 13 is rejected."""
        assert _extract_date("file_20261301.txt") is None

    def test_day_zero(self):
        """Day 0 is rejected."""
        assert _extract_date("file_20260100.txt") is None

    def test_day_32(self):
        """Day 32 is rejected."""
        assert _extract_date("file_20260332.txt") is None

    def test_year_1999(self):
        """Year before 2000 is rejected."""
        assert _extract_date("archive_1999-12-31.zip") is None

    def test_year_2100(self):
        """Year 2100 is rejected."""
        assert _extract_date("future_2100-01-01.log") is None

    def test_non_date_eight_digits(self):
        """Phone number or ID that happens to be 8 digits is rejected."""
        # 90923689 → 9092-36-89 — month 36 is invalid
        assert _extract_date("call_90923689_log.txt") is None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:

    def test_empty_string(self):
        """Empty string → None."""
        assert _extract_date("") is None

    def test_no_date_in_text(self):
        """Plain text with no numeric date → None."""
        assert _extract_date("meeting notes from last Tuesday") is None

    def test_partial_digits(self):
        """Fewer than 8 digits with no separator pattern → None."""
        assert _extract_date("version_12345.txt") is None

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("2025-12-31", "2025-12-31"),
            ("2026_06_15", "2026-06-15"),
            ("20260101", "2026-01-01"),
        ],
    )
    def test_parametrized_valid(self, text, expected):
        """Parametrized valid cases."""
        assert _extract_date(text) == expected
