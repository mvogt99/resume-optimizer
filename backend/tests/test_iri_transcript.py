"""Transcript segmentation, and the citation that makes a finding checkable.

`line_number` is the point of this module. An analysis that cannot point at its
evidence is an assertion, not a finding — and a citation that is confidently
WRONG is worse than none, because it gets checked once, looks plausible, and is
trusted thereafter. Several tests here exist only to hold that line honest.

The real-transcript tests run against archived interview material under
working-docs/, which is gitignored. They skip where it is absent rather than
fail: CI must not depend on private evidence.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from iri.ingestion.transcript import (
    TranscriptTurn,
    parse_timestamp,
    parse_transcript,
    speakers,
)

SAMPLE = """# A meeting
## Preamble that belongs to no turn

**alice@example.com | 02:38**
Hello there.
This is a second paragraph of the same turn.

**Bob Smith | 01:04:16**
And my reply.

**alice@example.com | 01:05:01**
"""

REAL = Path(__file__).resolve().parents[2] / "working-docs" / "postmortems" / \
    "BCBST_TechScreen_Transcript_2026-08-18.txt"


# --- timestamps -------------------------------------------------------------


@pytest.mark.parametrize(
    "value,seconds", [("00:00", 0), ("02:38", 158), ("01:04:16", 3856), ("10:00:00", 36000)]
)
def test_both_timestamp_formats(value, seconds):
    """MM:SS and HH:MM:SS both occur in the same file."""
    assert parse_timestamp(value) == seconds


@pytest.mark.parametrize("bad", ["", "abc", "1", "1:2:3:4"])
def test_malformed_timestamp_raises(bad):
    with pytest.raises(ValueError):
        parse_timestamp(bad)


# --- structure --------------------------------------------------------------


def test_preamble_is_not_a_turn():
    turns = parse_transcript(SAMPLE)
    assert all("Preamble" not in t.text for t in turns)


def test_multi_paragraph_turns_stay_together():
    turns = parse_transcript(SAMPLE)
    assert "second paragraph" in turns[0].text


def test_empty_trailing_turn_is_dropped():
    """The last header has no body; it must not become an empty turn."""
    assert len(parse_transcript(SAMPLE)) == 2


def test_indices_are_sequential_after_drops():
    turns = parse_transcript(SAMPLE)
    assert [t.index for t in turns] == list(range(len(turns)))


def test_speakers_may_contain_dots_digits_and_at_signs():
    assert speakers(parse_transcript(SAMPLE)) == ["alice@example.com", "Bob Smith"]


def test_bold_text_inside_speech_is_not_a_header():
    """The header regex is anchored; **emphasis** mid-turn must not split it."""
    text = "**a | 01:00**\nI said **really** loudly.\n"
    turns = parse_transcript(text)
    assert len(turns) == 1 and "really" in turns[0].text


def test_no_headers_returns_empty_rather_than_raising():
    """A malformed transcript should be visibly empty, not an exception."""
    assert parse_transcript("just some prose\nwith no headers") == []


def test_turns_are_frozen():
    import dataclasses

    with pytest.raises(dataclasses.FrozenInstanceError):
        parse_transcript(SAMPLE)[0].text = "edited"


# --- citation accuracy ------------------------------------------------------


def test_line_number_points_at_the_turns_own_header():
    lines = SAMPLE.splitlines()
    for turn in parse_transcript(SAMPLE):
        header = lines[turn.line_number - 1]
        assert header.startswith("**"), f"turn {turn.index} cites a non-header line"
        assert turn.speaker in header, f"turn {turn.index} cites another speaker's header"


# --- against the real archived transcript -----------------------------------


@pytest.mark.skipif(not REAL.exists(), reason="archived transcript not present")
def test_real_transcript_segments_cleanly():
    turns = parse_transcript(REAL.read_text())
    assert len(turns) > 50
    assert len(speakers(turns)) == 2


@pytest.mark.skipif(not REAL.exists(), reason="archived transcript not present")
def test_every_real_citation_resolves_to_its_own_header():
    raw = REAL.read_text()
    lines = raw.splitlines()
    for turn in parse_transcript(raw):
        header = lines[turn.line_number - 1]
        assert header.startswith("**") and turn.speaker in header


@pytest.mark.skipif(not REAL.exists(), reason="archived transcript not present")
def test_the_known_feedback_lands_in_one_interviewer_turn():
    """S1's acceptance gate depends on this quote being locatable and attributed.

    A human found it by hand; the segmenter must put it in exactly one turn,
    spoken by the interviewer rather than the candidate.
    """
    raw = REAL.read_text()
    matches = [t for t in parse_transcript(raw) if "Hugging Face" in t.text]
    assert len(matches) == 1
    turn = matches[0]
    assert "olivia" in turn.speaker.lower(), "must be attributed to the interviewer"
    assert raw.splitlines()[turn.line_number - 1].startswith("**olivia")
