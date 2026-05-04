"""Shared blueprint, constants, and helpers for agents routes.

Imported by all agents_routes_*.py submodules.  app.py imports agents_bp
from the thin agents_routes.py entry-point.
"""

import contextlib
import json
import logging

from agents import (
    get_app_tracker,
    get_career_advisor,
    get_cover_letter,
    get_interview_coach,
    get_job_scout,
    get_resume_tailor,
)
from agents.acceptance import (
    MAX_ATTEMPTS,
    apply_penalty,
    build_failure_teaching,
    record_acceptance,
    should_retry,
    verify,
)
from auth import require_auth
from flask import Blueprint, g, jsonify, request
from models import get_db

from rate_limit import limiter

logger = logging.getLogger(__name__)

agents_bp = Blueprint("agents", __name__)

# Rate limit applied to every LLM-backed endpoint
_LLM_LIMIT = "10/minute"


def _persist_acceptance(user_id, agent_type, acceptance, attempts):
    """Write acceptance verdict to the most recent agent_run for this user+agent.

    The agent's own _log_run() fires before we run verification, so we UPDATE
    rather than INSERT.  We match the most recent run for this user+agent combo.

    L2: If acceptance failed, also reduce ftal_a by penalty and recalculate ftal_gap.
    Merged into a single atomic UPDATE (eliminates race between two sequential UPDATEs).
    """
    if acceptance is None:
        return
    try:
        with get_db() as conn:
            apply_penalty_flag = int(not acceptance.passed and acceptance.a_score_penalty > 0)
            penalty = acceptance.a_score_penalty if apply_penalty_flag else 0
            conn.execute(
                "UPDATE agent_runs SET "
                "  acceptance_passed = ?, "
                "  acceptance_details = ?, "
                "  acceptance_attempts = ?, "
                "  ftal_a = CASE WHEN ? THEN MAX(0, COALESCE(ftal_a, 0) - ?) ELSE ftal_a END, "
                "  ftal_gap = CASE WHEN ? THEN MIN(100, COALESCE(ftal_gap, 100) + ?) ELSE ftal_gap END "
                "WHERE id = ("
                "  SELECT id FROM agent_runs WHERE user_id = ? AND agent_type = ? "
                "  ORDER BY created_at DESC LIMIT 1"
                ")",
                (
                    1 if acceptance.passed else 0,
                    acceptance.to_json(),
                    attempts,
                    apply_penalty_flag, penalty,
                    apply_penalty_flag, penalty,
                    user_id,
                    agent_type,
                ),
            )
            conn.commit()
    except Exception as exc:
        logger.error("[Acceptance] Failed to persist to agent_runs: %s", exc)


def _delete_coach_session(session_id):
    """L1: Delete an incomplete coach session to avoid orphans on retry."""
    if not session_id:
        return
    try:
        with get_db() as conn:
            conn.execute(
                "DELETE FROM interview_coach_sessions WHERE id = ? AND is_complete = 0",
                (session_id,),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("[Coach] Failed to delete orphan session %s: %s", session_id, exc)
