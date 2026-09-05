from __future__ import annotations
import json
from typing import List, Tuple, Callable
from iri.ingestion.transcript import TranscriptTurn
from iri.analysis.types import Citation, ConfidenceLevel, Finding, AnalysisOutcome, AnalysisResult

# Module-level constants
FEEDBACK_REQUEST_PHRASES = [
    "feedback",
    "how did i do",
    "what could i have done better",
    "where could i have done better",
    "gone into more detail",
    "covered more completely",
    "more complete job",
]
MAX_TURNS_AFTER_REQUEST = 3
CLOSING_SECTION_LENGTH = 10
CATEGORY_FEEDBACK = "interview_feedback"


class InvalidModelResponse(Exception):
    """The model's response could not be used.

    Raised rather than returning no findings, because "the model returned
    garbage" and "the model correctly found nothing" are different facts. The
    caller turns this into the ANALYSIS_FAILED outcome, keeping it distinct
    from INSUFFICIENT_EVIDENCE. Messages here never carry transcript text,
    prompts or completions: they are logged and displayed, and that text is
    unredacted personal data.
    """

class FeedbackExtractor:
    """Surfaces explicit interviewer feedback, with a verified citation for each finding.

    Not a dataclass: ANALYSER_NAME is a CLASS attribute shared by every instance,
    not per-instance state, and the constructor takes exactly one argument.
    """

    ANALYSER_NAME = "FeedbackExtractor"

    def __init__(self, model_call: Callable[[str], str]) -> None:
        """`model_call` is injected so the analyser stays testable and so the
        caller can route the call through the redaction gateway. This class must
        never construct a model client or read configuration itself."""
        self._model_call = model_call

    def extract(self, meeting_id: str, transcript: List[TranscriptTurn], candidate_label: str) -> AnalysisResult:
        selected_turns = self._select_relevant_turns(transcript, candidate_label)
        if not selected_turns:
            return AnalysisResult(
                analyser_name=self.ANALYSER_NAME,
                meeting_id=meeting_id,
                outcome=AnalysisOutcome.INSUFFICIENT_EVIDENCE,
                reason="No feedback request and no closing section in the transcript."
            )

        prompt = self._build_prompt(selected_turns)
        try:
            response = self._model_call(prompt)
            findings = self._parse_and_verify_findings(response, selected_turns, meeting_id)
        except Exception as e:
            return AnalysisResult(
                analyser_name=self.ANALYSER_NAME,
                meeting_id=meeting_id,
                outcome=AnalysisOutcome.ANALYSIS_FAILED,
                reason=f"Model call failed with exception: {type(e).__name__}"
            )

        if not findings:
            return AnalysisResult(
                analyser_name=self.ANALYSER_NAME,
                meeting_id=meeting_id,
                outcome=AnalysisOutcome.INSUFFICIENT_EVIDENCE,
                reason="No valid findings found in the model response."
            )

        return AnalysisResult(
            analyser_name=self.ANALYSER_NAME,
            meeting_id=meeting_id,
            outcome=AnalysisOutcome.FINDINGS_PRODUCED,
            findings=findings
        )

    def _select_relevant_turns(self, transcript: List[TranscriptTurn], candidate_label: str) -> List[TranscriptTurn]:
        selected_turns = set()
        feedback_requests = (turn for turn in transcript if turn.speaker == candidate_label and any(phrase in turn.text.lower() for phrase in FEEDBACK_REQUEST_PHRASES))

        for request_turn in feedback_requests:
            selected_turns.add(request_turn)
            for i in range(1, MAX_TURNS_AFTER_REQUEST + 1):
                if request_turn.index + i < len(transcript):
                    selected_turns.add(transcript[request_turn.index + i])

        # Add the final stretch of the meeting
        selected_turns.update(transcript[-CLOSING_SECTION_LENGTH:])

        return sorted(selected_turns, key=lambda turn: turn.index)

    def _build_prompt(self, selected_turns: List[TranscriptTurn]) -> str:
        turns_text = "\n".join(f"Turn {turn.index} ({turn.speaker} at {turn.timestamp}): {turn.text}" for turn in selected_turns)
        return (
            f"Given the following transcript excerpt:\n"
            f"{turns_text}\n"
            f"Identify any explicit feedback the interviewer gave about the candidate's performance. "
            f"Return JSON only: an object with key 'findings' holding a list, each element having 'claim', 'turn_index', 'quote' copied verbatim from that turn, and 'confidence' of high, medium or low. "
            f"If the evidence supports no finding, return an empty list."
        )

    def _parse_and_verify_findings(self, response: str, selected_turns: List[TranscriptTurn], meeting_id: str) -> Tuple[Finding, ...]:
        """Turn the raw completion into findings whose citations have been CHECKED.

        The model's citation is untrustworthy until verified. A quote that does
        not appear in the turn it cites means the model fabricated it, and a
        finding resting on a fabricated quote is worse than no finding at all:
        it looks specific, gets checked once, and is trusted thereafter. So a
        finding whose quote or turn index does not verify is dropped.

        Bad data in ONE element is not a malfunction of this component, so such
        an element is skipped. A response that is not usable JSON at all IS a
        malfunction, so that raises.
        """
        text = response.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            # Drop the opening fence line whatever language tag it carries, and
            # a closing fence if present. Done by line, not by character offset:
            # counting characters is what made the previous version cut a byte
            # off the JSON whenever the fence was followed by a single newline.
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines[1:])

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise InvalidModelResponse("model response was not valid JSON") from exc
        if not isinstance(parsed, dict):
            raise InvalidModelResponse("model response was not a JSON object")
        findings_data = parsed.get("findings", [])
        if not isinstance(findings_data, list):
            raise InvalidModelResponse("model response field 'findings' was not a list")

        turns_by_index = {turn.index: turn for turn in selected_turns}
        findings: List[Finding] = []

        for element in findings_data:
            if not isinstance(element, dict):
                continue
            claim = element.get("claim")
            quote = element.get("quote")
            turn_index = element.get("turn_index")
            confidence = element.get("confidence")

            if not isinstance(claim, str) or not claim.strip():
                continue
            if not isinstance(quote, str) or not quote.strip():
                continue
            # bool is a subclass of int, so it must be rejected explicitly
            if not isinstance(turn_index, int) or isinstance(turn_index, bool):
                continue
            if not isinstance(confidence, str):
                continue
            try:
                level = ConfidenceLevel(confidence.strip().lower())
            except ValueError:
                continue

            # A model will happily cite a turn it was never shown.
            turn = turns_by_index.get(turn_index)
            if turn is None or not self._verify_quote(quote, turn.text):
                continue

            citation = Citation(meeting_id=meeting_id, turn_index=turn_index, timestamp=turn.timestamp, quote=quote)
            findings.append(Finding(claim=claim, citations=(citation,), confidence=level, category=CATEGORY_FEEDBACK))

        findings.sort(key=lambda f: f.citations[0].turn_index)
        return tuple(findings)

    def _verify_quote(self, quote: str, turn_text: str) -> bool:
        # Collapse whitespace and ignore case for comparison
        return " ".join(quote.split()).lower() in " ".join(turn_text.split()).lower()
