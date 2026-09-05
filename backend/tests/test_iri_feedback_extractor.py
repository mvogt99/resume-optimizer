from iri.ingestion.transcript import TranscriptTurn
from iri.analysis.types import AnalysisOutcome, ConfidenceLevel, AnalysisResult, Finding, Citation
from iri.analysis.feedback_extractor import FeedbackExtractor
import pytest


def make_turn(index: int, speaker: str, text: str) -> TranscriptTurn:
    return TranscriptTurn(
        index=index,
        speaker=speaker,
        timestamp=f"2023-10-01T12:00:{index:02}Z",
        offset_seconds=index * 10,
        line_number=index + 1,
        text=text
    )


def make_long_transcript() -> list[TranscriptTurn]:
    return [make_turn(i, "Speaker", f"Line {i}") for i in range(20)]


def test_happy_path():
    def mock_model(prompt: str) -> str:
        return '{"findings": [{"claim": "Good feedback", "turn_index": 21, "quote": "Here is the feedback", "confidence": "high"}]}'

    extractor = FeedbackExtractor(mock_model)
    transcript = make_long_transcript()
    transcript.append(make_turn(20, "Candidate", "Please provide feedback"))
    transcript.append(make_turn(21, "Interviewer", "Here is the feedback"))
    result = extractor.extract("meeting1", transcript, "Candidate")

    assert result.outcome == AnalysisOutcome.FINDINGS_PRODUCED
    assert len(result.findings) == 1
    assert result.findings[0].claim == "Good feedback"
    assert result.findings[0].citations[0].turn_index == 21
    assert result.findings[0].citations[0].timestamp == "2023-10-01T12:00:21Z"
    # the citation must point at the interviewer's ANSWER, not the candidate's request
    assert result.findings[0].citations[0].turn_index != 20


def test_fabricated_quote():
    def mock_model(prompt: str) -> str:
        return '{"findings": [{"claim": "Bad feedback", "turn_index": 19, "quote": "Not in transcript", "confidence": "high"}]}'

    extractor = FeedbackExtractor(mock_model)
    transcript = make_long_transcript()
    result = extractor.extract("meeting2", transcript, "Candidate")

    assert result.outcome == AnalysisOutcome.INSUFFICIENT_EVIDENCE
    assert len(result.findings) == 0


def test_out_of_range_citation():
    def mock_model(prompt: str) -> str:
        return '{"findings": [{"claim": "Out of range", "turn_index": 100, "quote": "Line 19", "confidence": "high"}]}'

    extractor = FeedbackExtractor(mock_model)
    transcript = make_long_transcript()
    result = extractor.extract("meeting3", transcript, "Candidate")

    assert result.outcome == AnalysisOutcome.INSUFFICIENT_EVIDENCE
    assert len(result.findings) == 0


def test_whitespace_case_tolerance():
    def mock_model(prompt: str) -> str:
        return '{"findings": [{"claim": "Whitespace and case", "turn_index": 19, "quote": "line 19", "confidence": "high"}]}'

    extractor = FeedbackExtractor(mock_model)
    transcript = make_long_transcript()
    result = extractor.extract("meeting4", transcript, "Candidate")

    assert result.outcome == AnalysisOutcome.FINDINGS_PRODUCED
    assert len(result.findings) == 1


def test_no_feedback_no_closing():
    def mock_model(prompt: str) -> str:
        return '{"findings": []}'

    extractor = FeedbackExtractor(mock_model)
    transcript = make_long_transcript()
    result = extractor.extract("meeting5", transcript, "Candidate")

    assert result.outcome == AnalysisOutcome.INSUFFICIENT_EVIDENCE
    assert len(result.reason) > 0


def test_empty_transcript():
    model_called = False

    def mock_model(prompt: str) -> str:
        nonlocal model_called
        model_called = True
        return '{"findings": []}'

    extractor = FeedbackExtractor(mock_model)
    result = extractor.extract("meeting6", [], "Candidate")

    assert not model_called
    assert result.outcome == AnalysisOutcome.INSUFFICIENT_EVIDENCE
    assert len(result.reason) > 0


def test_model_exception():
    def mock_model(prompt: str) -> str:
        raise Exception("Model broke")

    extractor = FeedbackExtractor(mock_model)
    transcript = make_long_transcript()
    result = extractor.extract("meeting7", transcript, "Candidate")

    assert result.outcome == AnalysisOutcome.ANALYSIS_FAILED
    assert len(result.reason) > 0


def test_non_json_response():
    def mock_model(prompt: str) -> str:
        return "Not JSON"

    extractor = FeedbackExtractor(mock_model)
    transcript = make_long_transcript()
    result = extractor.extract("meeting8", transcript, "Candidate")

    assert result.outcome == AnalysisOutcome.ANALYSIS_FAILED
    assert result.outcome != AnalysisOutcome.INSUFFICIENT_EVIDENCE


def test_markdown_code_fence():
    def mock_model(prompt: str) -> str:
        return "```json\n{\"findings\": [{\"claim\": \"Fenced feedback\", \"turn_index\": 19, \"quote\": \"Line 19\", \"confidence\": \"high\"}]}\n```"

    extractor = FeedbackExtractor(mock_model)
    transcript = make_long_transcript()
    transcript.append(make_turn(20, "Candidate", "Please provide feedback"))
    transcript.append(make_turn(21, "Interviewer", "Here is the feedback"))
    result = extractor.extract("meeting9", transcript, "Candidate")

    assert result.outcome == AnalysisOutcome.FINDINGS_PRODUCED
    assert len(result.findings) == 1


def test_leak_guard():
    """The reason is logged and displayed; transcript text and exception detail
    are unredacted personal data, so only the exception TYPE may appear."""
    def mock_model(prompt: str) -> str:
        raise RuntimeError("Model broke with SENTINELWORD")

    extractor = FeedbackExtractor(mock_model)
    transcript = make_long_transcript()
    transcript[19] = make_turn(19, "Interviewer", "Sensitive feedback with SENTINELWORD")
    result = extractor.extract("meeting10", transcript, "Candidate")

    assert result.outcome == AnalysisOutcome.ANALYSIS_FAILED
    assert len(result.reason) > 0
    assert "SENTINELWORD" not in result.reason


def test_bare_markdown_code_fence():
    def mock_model(prompt: str) -> str:
        return "```\n{\"findings\": [{\"claim\": \"Bare fenced feedback\", \"turn_index\": 21, \"quote\": \"Here is the feedback\", \"confidence\": \"high\"}]}\n```"

    extractor = FeedbackExtractor(mock_model)
    transcript = make_long_transcript()
    transcript.append(make_turn(20, "Candidate", "Please provide feedback"))
    transcript.append(make_turn(21, "Interviewer", "Here is the feedback"))
    result = extractor.extract("meeting13", transcript, "Candidate")

    assert result.outcome == AnalysisOutcome.FINDINGS_PRODUCED
    assert len(result.findings) == 1


def test_multiple_findings_ordered():
    def mock_model(prompt: str) -> str:
        return '{"findings": [{"claim": "Feedback 2", "turn_index": 18, "quote": "Line 18", "confidence": "high"}, {"claim": "Feedback 1", "turn_index": 17, "quote": "Line 17", "confidence": "high"}]}'

    extractor = FeedbackExtractor(mock_model)
    transcript = make_long_transcript()
    result = extractor.extract("meeting11", transcript, "Candidate")

    assert result.outcome == AnalysisOutcome.FINDINGS_PRODUCED
    assert len(result.findings) == 2
    assert result.findings[0].claim == "Feedback 1"
    assert result.findings[1].claim == "Feedback 2"


def test_single_malformed_element():
    def mock_model(prompt: str) -> str:
        return '{"findings": [{"claim": "Good feedback", "turn_index": 19, "quote": "Line 19", "confidence": "high"}, {"turn_index": 18, "quote": "Line 18", "confidence": "high"}]}'

    extractor = FeedbackExtractor(mock_model)
    transcript = make_long_transcript()
    result = extractor.extract("meeting12", transcript, "Candidate")

    assert result.outcome == AnalysisOutcome.FINDINGS_PRODUCED
    assert len(result.findings) == 1
    assert result.findings[0].claim == "Good feedback"
