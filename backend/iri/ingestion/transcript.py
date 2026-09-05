from __future__ import annotations
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TranscriptTurn:
    """
    Represents a turn in a meeting transcript.

    index: int
        0-based position in the transcript.
    speaker: str
        Exactly as written, not normalised.
    timestamp: str
        As written, e.g. "02:38" or "01:04:16".
    offset_seconds: int
        The timestamp converted to seconds.
    line_number: int
        1-based line of the HEADER in the source file. This exists so a finding
        can be cited back to an exact place in the source. An analysis that
        cannot point at its evidence is an assertion, not a finding.
    text: str
        The turn's text, stripped.
    """
    index: int
    speaker: str
    timestamp: str
    offset_seconds: int
    line_number: int
    text: str


def parse_transcript(raw: str) -> list[TranscriptTurn]:
    """Split a transcript into speaker turns, preserving citation locations.

    A header is a whole line of the form ``**<speaker> | <timestamp>**``; the
    text runs to the next header or end of file. Preamble before the first
    header is skipped, and turns empty after stripping are dropped.

    Text with no headers returns an EMPTY LIST rather than raising: a malformed
    transcript should be visibly empty in a batch, not an exception.

    `line_number` is captured when the header is MATCHED, not when the turn is
    appended -- a turn is only appended once the NEXT header appears, so reading
    the counter then would cite the following speaker's header. A confidently
    wrong citation is worse than none: it gets checked once, looks plausible,
    and is trusted thereafter.
    """
    header_pattern = re.compile(r"^\*\*(.*?) \| (.*?)\*\*$")
    turns: list[TranscriptTurn] = []
    speaker: str | None = None
    timestamp: str | None = None
    header_line = 0
    body: list[str] = []

    def flush() -> None:
        if speaker is None or timestamp is None:
            return
        text = "\n".join(body).strip()
        if not text:
            return
        turns.append(
            TranscriptTurn(
                index=len(turns),
                speaker=speaker,
                timestamp=timestamp,
                offset_seconds=parse_timestamp(timestamp),
                line_number=header_line,
                text=text,
            )
        )

    for line_number, line in enumerate(raw.splitlines(), start=1):
        match = header_pattern.match(line)
        if match:
            flush()
            speaker, timestamp = match.group(1), match.group(2)
            header_line = line_number
            body = []
        elif speaker is not None:
            body.append(line)

    flush()
    return turns

def parse_timestamp(value: str) -> int:
    """
    Converts "MM:SS" or "HH:MM:SS" to seconds. Raises ValueError on anything else.
    """
    parts = value.split(':')
    if len(parts) == 2:
        minutes, seconds = map(int, parts)
        return minutes * 60 + seconds
    elif len(parts) == 3:
        hours, minutes, seconds = map(int, parts)
        return hours * 3600 + minutes * 60 + seconds
    else:
        raise ValueError(f"Invalid timestamp format: {value}")


def speakers(turns: list[TranscriptTurn]) -> list[str]:
    """
    Returns the distinct speakers, in order of first appearance.
    """
    seen_speakers = set()
    result = []
    for turn in turns:
        if turn.speaker not in seen_speakers:
            seen_speakers.add(turn.speaker)
            result.append(turn.speaker)
    return result
