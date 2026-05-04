"""Unit tests for generate_rewrites helpers: _expand_original_text, _deduplicate_rewrites.

Mutation targets:
  MH1: _expand_original_text returns sample unchanged when sample IS in resume
  MH2: _expand_original_text uses prefix match when sample is truncated
  MH3: _expand_original_text stops at section boundary
  MH4: _expand_original_text returns original sample when anchor not found
  MH5: _deduplicate_rewrites keeps single rewrite unchanged
  MH6: _deduplicate_rewrites merges duplicates — keeps longest proposed_text
  MH7: _deduplicate_rewrites unions keywords_addressed on merge
  MH8: _deduplicate_rewrites calls _expand_original_text on first occurrence
"""

import pytest

from keyword_equivalency import _deduplicate_rewrites, _expand_original_text


# ---------------------------------------------------------------------------
# Sample resume with recognisable section boundaries
# ---------------------------------------------------------------------------

_RESUME = (
    "Professional Summary\n"
    "Principal Data Platform Architect with 20+ years of experience.\n"
    "Deep expertise in healthcare data platforms and HIPAA compliance.\n\n"
    "Professional Experience\n"
    "Lead architect designing cloud-native, event-driven data platforms for healthcare clients.\n"
    "End-to-end platform architecture from data ingestion through consumption.\n"
    "* Architected operational data platform on AWS supporting claims processing.\n\n"
    "Core Competencies\n"
    "* Data Platform Architecture\n"
    "* Streaming Architecture & Real-Time Data Processing\n"
)

_EXPERIENCE_FULL = (
    "Lead architect designing cloud-native, event-driven data platforms for healthcare clients.\n"
    "End-to-end platform architecture from data ingestion through consumption.\n"
    "* Architected operational data platform on AWS supporting claims processing.\n"
)

_EXPERIENCE_TRUNCATED = (
    "Lead architect designing cloud-native, event-driven data platforms for healthcare clients.\n"
    "End-to-end platform architecture from data ingestion through consumptio"  # cut off
)


# ---------------------------------------------------------------------------
# _expand_original_text
# ---------------------------------------------------------------------------


class TestExpandOriginalText:
    # MH1: function always expands to section boundary — even complete sample
    def test_complete_sample_anchored_to_section(self):
        """Even a complete sample is anchored; result starts with sample prefix (MH1).

        The function always finds the section boundary rather than relying on
        the sample being a substring. A "truncated" sample where the cut-off is
        still a substring (e.g. 'consumptio' inside 'consumption') must NOT be
        returned as-is — that would cause a partial replace on the frontend.
        """
        result = _expand_original_text(_RESUME, _EXPERIENCE_TRUNCATED)
        # Must anchor to the same location in the resume
        assert result.startswith(_EXPERIENCE_TRUNCATED[:80])

    # MH2: prefix match expands truncated sample to full section
    def test_truncated_sample_expanded_via_prefix(self):
        """Truncated original_text is expanded to full section text (MH2)."""
        result = _expand_original_text(_RESUME, _EXPERIENCE_TRUNCATED)
        # Must be longer — includes everything up to section boundary
        assert len(result) > len(_EXPERIENCE_TRUNCATED)

    # MH3: stops at section boundary
    def test_expansion_stops_at_section_boundary(self):
        """Expanded text must not bleed into the next section header (MH3)."""
        result = _expand_original_text(_RESUME, _EXPERIENCE_TRUNCATED)
        assert "Core Competencies" not in result

    # MH4: anchor not found — return original
    def test_anchor_not_found_returns_original(self):
        """When sample has no match in resume, return sample unchanged (MH4)."""
        unknown = "This text does not appear anywhere in the resume at all."
        result = _expand_original_text(_RESUME, unknown)
        assert result == unknown

    def test_empty_sample_returns_empty(self):
        """Empty sample returns empty."""
        assert _expand_original_text(_RESUME, "") == ""

    def test_empty_resume_returns_sample(self):
        """Empty resume returns sample unchanged."""
        assert _expand_original_text("", "some text") == "some text"


# ---------------------------------------------------------------------------
# _deduplicate_rewrites
# ---------------------------------------------------------------------------


def _rw(section, original, proposed, keywords):
    return {
        "section": section,
        "original_text": original,
        "proposed_text": proposed,
        "keywords_addressed": keywords,
    }


class TestDeduplicateRewrites:
    # MH5: single rewrite unchanged
    def test_single_rewrite_unchanged(self):
        """One rewrite passes through without modification (MH5)."""
        rws = [_rw("Summary", "Original summary text.", "Proposed summary.", ["kw1"])]
        result = _deduplicate_rewrites(rws, "Original summary text.")
        assert len(result) == 1
        assert result[0]["proposed_text"] == "Proposed summary."

    # MH6: duplicates merged, longest proposed_text wins
    def test_duplicates_merged_longest_proposed_wins(self):
        """Two rewrites with same original_text prefix are merged; longer proposed wins (MH6)."""
        original = "Lead architect designing cloud-native platforms. End-to-end platform."
        rw1 = _rw("Experience", original, "Short proposed.", ["kw1"])
        rw2 = _rw("Experience", original, "Much longer proposed text incorporating more keywords.", ["kw2"])
        result = _deduplicate_rewrites([rw1, rw2], original)
        assert len(result) == 1
        assert "longer proposed text" in result[0]["proposed_text"]

    # MH7: keywords_addressed unioned on merge
    def test_duplicates_keywords_unioned(self):
        """Merged rewrite has union of both rewrites' keywords_addressed (MH7)."""
        original = "Lead architect designing cloud-native platforms. End-to-end platform."
        rw1 = _rw("Experience", original, "Proposed A.", ["kwA", "kwB"])
        rw2 = _rw("Experience", original, "Longer proposed B text here.", ["kwC"])
        result = _deduplicate_rewrites([rw1, rw2], original)
        kws = result[0]["keywords_addressed"]
        assert "kwA" in kws
        assert "kwB" in kws
        assert "kwC" in kws

    # MH8: _deduplicate_rewrites calls _expand_original_text
    def test_truncated_original_expanded_on_first_occurrence(self):
        """_deduplicate_rewrites expands truncated original_text via _expand_original_text (MH8).

        "consumptio" is a substring of "consumption" so the naive approach returns
        it unchanged. _expand_original_text must expand to the full section boundary.
        """
        truncated = _EXPERIENCE_TRUNCATED
        rw = _rw("Experience", truncated, "Proposed text.", ["kw1"])
        result = _deduplicate_rewrites([rw], _RESUME)
        expanded = result[0]["original_text"]
        # Expanded must anchor to same location and be longer than truncated
        assert expanded.startswith(truncated[:80])
        assert len(expanded) > len(truncated)

    def test_different_sections_not_merged(self):
        """Rewrites for different sections are kept separate."""
        rw1 = _rw("Summary", "Summary text here.", "Proposed summary.", ["kw1"])
        rw2 = _rw("Experience", "Experience text here.", "Proposed exp.", ["kw2"])
        result = _deduplicate_rewrites([rw1, rw2], "Summary text here.\nExperience text here.")
        assert len(result) == 2

    def test_empty_list_returns_empty(self):
        """Empty input returns empty list."""
        assert _deduplicate_rewrites([], _RESUME) == []
