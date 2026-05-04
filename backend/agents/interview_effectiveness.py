"""CT-9: Interview coaching effectiveness tracking with deferred PF confidence.

Ports V5's deferred confidence pattern to interview coaching:
  1. After scoring answer → confidence_pending=True (don't boost PF immediately)
  2. Track coaching_effectiveness = answer_score[n+1] - answer_score[n] across session
  3. Session end: effectiveness > 0 → confirm PF boost (+0.05); <= 0 → penalize (-0.05)
  4. effectiveness < 0 for 3+ consecutive sessions → flag prompts for teaching regen

Non-blocking: errors logged at DEBUG, never raised. Integrates with PersonaForge.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class InterviewEffectivenessTracker:
    """Track per-session coaching effectiveness and deferred PF feedback."""

    def __init__(self, session_id: str, user_id: int, persona: str = "hiring_manager"):
        """Initialize effectiveness tracker for a session.

        Args:
            session_id: Unique interview session ID.
            user_id: User conducting the interview.
            persona: Interviewer persona (hiring_manager, technical, etc.).
        """
        self.session_id = session_id
        self.user_id = user_id
        self.persona = persona
        self.answer_scores: List[float] = []
        self.confidence_pending = True
        self.is_completed = False

    def record_answer_score(self, score: float) -> None:
        """Record an answer score for effectiveness computation.

        Args:
            score: Answer quality score (0.0 to 10.0).
        """
        if not isinstance(score, (int, float)):
            logger.debug("[CT-9] Invalid score type: %s", type(score))
            return
        self.answer_scores.append(float(score))

    def compute_effectiveness(self) -> Optional[float]:
        """Compute coaching effectiveness as score improvement within session.

        Returns:
            Effectiveness = (final_score - initial_score) / initial_score if initial > 0
            None if insufficient data (<2 answers).
        """
        if len(self.answer_scores) < 2:
            return None

        initial = self.answer_scores[0]
        final = self.answer_scores[-1]

        if initial <= 0:
            return None

        return (final - initial) / initial

    def complete_session(self) -> Dict[str, Any]:
        """Finalize session and return effectiveness verdict + PF action.

        Returns:
            {
                "session_id": str,
                "effectiveness": float | None,
                "pf_action": "boost" | "penalize" | "none",
                "pf_magnitude": float,
                "teaching_flag": bool,
                "message": str,
            }
        """
        self.is_completed = True
        effectiveness = self.compute_effectiveness()

        result: Dict[str, Any] = {
            "session_id": self.session_id,
            "effectiveness": effectiveness,
            "pf_action": "none",
            "pf_magnitude": 0.0,
            "teaching_flag": False,
            "message": "Session incomplete — insufficient answers.",
        }

        if effectiveness is None:
            return result

        # Determine PF action based on effectiveness
        if effectiveness > 0:
            result["pf_action"] = "boost"
            result["pf_magnitude"] = 0.05
            result["message"] = (
                f"Coaching effective (effectiveness={effectiveness:.2%}). "
                "Applying +0.05 PF confidence boost."
            )
        else:
            result["pf_action"] = "penalize"
            result["pf_magnitude"] = -0.05
            result["message"] = (
                f"Coaching ineffective (effectiveness={effectiveness:.2%}). "
                "Applying -0.05 PF confidence penalty."
            )
            result["teaching_flag"] = True  # Flag for teaching regen

        logger.info(
            "[CT-9] Session %s completed: effectiveness=%.2f, action=%s",
            self.session_id[:12],
            effectiveness if effectiveness is not None else 0,
            result["pf_action"],
        )

        return result

    async def apply_pf_feedback(
        self, pf_memory_ids: List[str]
    ) -> None:
        """Apply deferred PF confidence adjustment.

        Args:
            pf_memory_ids: PersonaForge memory IDs to adjust.
        """
        if not self.is_completed:
            logger.debug("[CT-9] Session not completed — skipping PF feedback")
            return

        result = self.complete_session()
        action = result.get("pf_action")

        if action == "none" or not pf_memory_ids:
            return

        try:
            from app.services.personaforge_client import get_personaforge_client

            client = get_personaforge_client()
            verified_pass = action == "boost"
            magnitude = abs(result.get("pf_magnitude", 0.05))

            await client.apply_verified_feedback(
                pf_memory_ids, verified_pass=verified_pass, gap=int(magnitude * 100)
            )

            logger.info(
                "[CT-9] Applied PF %s to %d memories for session %s",
                action,
                len(pf_memory_ids),
                self.session_id[:12],
            )
        except Exception as exc:
            logger.debug("[CT-9] PF feedback failed (non-blocking): %s", exc)


# Global session trackers (in-memory for now, could persist to DB)
_trackers: Dict[str, InterviewEffectivenessTracker] = {}


def get_tracker(session_id: str) -> Optional[InterviewEffectivenessTracker]:
    """Retrieve an active session tracker."""
    return _trackers.get(session_id)


def create_tracker(
    session_id: str, user_id: int, persona: str = "hiring_manager"
) -> InterviewEffectivenessTracker:
    """Create and register a new session tracker."""
    tracker = InterviewEffectivenessTracker(session_id, user_id, persona)
    _trackers[session_id] = tracker
    return tracker


def get_or_create_tracker(
    session_id: str, user_id: int = 0, persona: str = "hiring_manager"
) -> InterviewEffectivenessTracker:
    """Get existing tracker or create one if absent."""
    tracker = _trackers.get(session_id)
    if tracker is None:
        tracker = create_tracker(session_id, user_id, persona)
    return tracker


def remove_tracker(session_id: str) -> None:
    """Remove a completed session tracker."""
    _trackers.pop(session_id, None)
