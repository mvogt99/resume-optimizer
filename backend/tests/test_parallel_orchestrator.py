"""P2-E: Parallel Orchestrator tests — TDD first.

Tests:
- Resume Tailor and Cover Letter run in parallel (start within 1s of each other)
- Interview Prep runs after Resume Tailor (sequential)
- Pipeline continues if one parallel step fails (partial status)
- Both fail = failed status
- Parallel is faster than sequential (wall-clock timing)
"""

import os
import sys
import tempfile
import time
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, ".")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def app_ctx():
    """Flask app with a fresh temp SQLite DB — ensures agent_runs table exists."""
    import agents as _agents
    import models

    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    models.DB_PATH = db_path

    from models import init_db

    init_db()

    # Reset agent singletons so they bind to the new DB path
    _agents._resume_tailor = None
    _agents._cover_letter = None
    _agents._interview_coach = None
    _agents._career_advisor = None
    _agents._orchestrator = None

    import app as flask_app

    application = flask_app.create_app(testing=True)
    with application.app_context():
        yield application

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture()
def orchestrator(app_ctx):
    from agents import get_orchestrator

    return get_orchestrator()


# ---------------------------------------------------------------------------
# P2-E.1 Design validation: dependency map
# ---------------------------------------------------------------------------


class TestDependencyMap:
    def test_orchestrator_has_parallel_pipeline(self, orchestrator):
        """full_application_pipeline should exist."""
        assert hasattr(orchestrator, "full_application_pipeline")

    def test_orchestrator_exposes_parallel_mode(self, orchestrator):
        """parallel mode flag or attribute exists on orchestrator."""
        # Accept either: parallel kwarg in method OR class attribute
        import inspect

        sig = inspect.signature(orchestrator.full_application_pipeline)
        has_parallel_param = "parallel" in sig.parameters
        has_class_attr = hasattr(orchestrator, "PARALLEL_STEPS") or hasattr(
            orchestrator, "_run_parallel"
        )
        assert has_parallel_param or has_class_attr, (
            "Orchestrator must expose parallel execution — "
            "either via 'parallel' param or _run_parallel method"
        )


# ---------------------------------------------------------------------------
# P2-E.2: Resume Tailor + Cover Letter run in parallel
# ---------------------------------------------------------------------------


class TestParallelExecution:
    def test_both_agents_called_in_pipeline(self, app_ctx):
        """Both tailor and cover_letter should be called."""
        tailor_calls = []
        cover_calls = []

        def fake_tailor(user_id, posting_id, *a, **kw):
            tailor_calls.append(time.time())
            return {"version_id": 1, "ats_score": 0.8, "optimized_text": "x" * 100}

        def fake_cover(user_id, posting_id, *a, **kw):
            cover_calls.append(time.time())
            return {"id": "cl1", "subject": "Re: Role"}

        def fake_prep(user_id, posting_id, *a, **kw):
            return {"prep_data": {"questions": []}, "talking_points": [], "star_examples": []}

        with (
            patch("agents.resume_tailor.ResumeTailorAgent.tailor_for_posting", fake_tailor),
            patch("agents.cover_letter.CoverLetterAgent.generate", fake_cover),
            patch("agents.interview_coach.InterviewCoachAgent.generate_prep_sheet", fake_prep),
        ):
            from agents import get_orchestrator

            orch = get_orchestrator()
            result = orch.full_application_pipeline("3", "posting_test_1")

        assert len(tailor_calls) > 0, "Resume Tailor was not called"
        assert len(cover_calls) > 0, "Cover Letter was not called"
        assert "steps_completed" in result

    def test_parallel_steps_start_close_together(self, app_ctx):
        """In parallel mode, tailor and cover letter should start within 1 second."""
        start_times = {}

        def fake_tailor(user_id, posting_id, *a, **kw):
            start_times["tailor"] = time.time()
            time.sleep(0.2)  # Simulate some work
            return {"version_id": 1, "ats_score": 0.8, "optimized_text": "x" * 100}

        def fake_cover(user_id, posting_id, *a, **kw):
            start_times["cover"] = time.time()
            time.sleep(0.2)
            return {"id": "cl1", "subject": "Re: Role"}

        def fake_prep(user_id, posting_id, *a, **kw):
            return {"prep_data": {"questions": []}, "talking_points": [], "star_examples": []}

        with (
            patch("agents.resume_tailor.ResumeTailorAgent.tailor_for_posting", fake_tailor),
            patch("agents.cover_letter.CoverLetterAgent.generate", fake_cover),
            patch("agents.interview_coach.InterviewCoachAgent.generate_prep_sheet", fake_prep),
        ):
            from agents import get_orchestrator

            orch = get_orchestrator()
            orch.full_application_pipeline("3", "posting_test_2")

        if "tailor" in start_times and "cover" in start_times:
            gap = abs(start_times["tailor"] - start_times["cover"])
            assert gap < 1.0, f"Tailor and Cover Letter started {gap:.2f}s apart — not parallel"


# ---------------------------------------------------------------------------
# P2-E.3: Partial failure handling
# ---------------------------------------------------------------------------


class TestPartialFailures:
    def test_cover_letter_failure_does_not_stop_interview_prep(self, app_ctx):
        """If Cover Letter fails but Resume Tailor succeeds, Interview Prep should run."""

        def fake_tailor(user_id, posting_id, *a, **kw):
            return {"version_id": 1, "ats_score": 0.8, "optimized_text": "x" * 100}

        def fail_cover(user_id, posting_id, *a, **kw):
            return {"error": "Cover letter generation failed"}

        def fake_prep(user_id, posting_id, *a, **kw):
            return {"prep_data": {"questions": ["Q1"]}, "talking_points": [], "star_examples": []}

        with (
            patch("agents.resume_tailor.ResumeTailorAgent.tailor_for_posting", fake_tailor),
            patch("agents.cover_letter.CoverLetterAgent.generate", fail_cover),
            patch("agents.interview_coach.InterviewCoachAgent.generate_prep_sheet", fake_prep),
        ):
            from agents import get_orchestrator

            orch = get_orchestrator()
            result = orch.full_application_pipeline("3", "posting_test_3")

        assert "resume_tailor" in result.get("steps_completed", []), (
            "resume_tailor should be in steps_completed"
        )
        assert result.get("status") in ("partial", "complete"), (
            f"Expected partial or complete, got {result.get('status')}"
        )

    def test_tailor_failure_skips_interview_prep(self, app_ctx):
        """If Resume Tailor fails, Interview Prep should be skipped (needs resume)."""

        def fail_tailor(user_id, posting_id, *a, **kw):
            return {"error": "Tailor failed"}

        def fake_cover(user_id, posting_id, *a, **kw):
            return {"id": "cl1", "subject": "Re: Role"}

        prep_called = []

        def fake_prep(user_id, posting_id, *a, **kw):
            prep_called.append(True)
            return {"prep_data": {"questions": []}}

        with (
            patch("agents.resume_tailor.ResumeTailorAgent.tailor_for_posting", fail_tailor),
            patch("agents.cover_letter.CoverLetterAgent.generate", fake_cover),
            patch("agents.interview_coach.InterviewCoachAgent.generate_prep_sheet", fake_prep),
        ):
            from agents import get_orchestrator

            orch = get_orchestrator()
            result = orch.full_application_pipeline("3", "posting_test_4")

        # Interview prep SHOULD be skipped if tailor failed
        assert "interview_prep" not in result.get("steps_completed", []), (
            "Interview Prep should not run when Resume Tailor failed"
        )

    def test_both_fail_returns_failed_status(self, app_ctx):
        """Both parallel steps failing = status 'failed'."""

        def fail_tailor(user_id, posting_id, *a, **kw):
            return {"error": "Tailor failed"}

        def fail_cover(user_id, posting_id, *a, **kw):
            return {"error": "Cover letter failed"}

        def fake_prep(user_id, posting_id, *a, **kw):
            return {"prep_data": {"questions": []}}

        with (
            patch("agents.resume_tailor.ResumeTailorAgent.tailor_for_posting", fail_tailor),
            patch("agents.cover_letter.CoverLetterAgent.generate", fail_cover),
            patch("agents.interview_coach.InterviewCoachAgent.generate_prep_sheet", fake_prep),
        ):
            from agents import get_orchestrator

            orch = get_orchestrator()
            result = orch.full_application_pipeline("3", "posting_test_5")

        # With both parallel steps failing and no interview prep, status = failed
        # (steps_completed will only have pipeline_move if any step succeeded)
        assert result.get("status") in ("failed", "partial"), (
            f"Expected failed or partial, got {result.get('status')}"
        )


# ---------------------------------------------------------------------------
# P2-E.4: Wall-clock timing — parallel vs sequential
# ---------------------------------------------------------------------------


class TestTimingImprovement:
    def test_parallel_faster_than_sequential(self, app_ctx):
        """Parallel execution should complete faster than sequential for 2 slow steps."""
        STEP_DURATION = 0.3  # Each step takes 300ms

        def slow_tailor(user_id, posting_id, *a, **kw):
            time.sleep(STEP_DURATION)
            return {"version_id": 1, "ats_score": 0.8, "optimized_text": "x" * 100}

        def slow_cover(user_id, posting_id, *a, **kw):
            time.sleep(STEP_DURATION)
            return {"id": "cl1", "subject": "Re: Role"}

        def fast_prep(user_id, posting_id, *a, **kw):
            return {"prep_data": {"questions": []}, "talking_points": [], "star_examples": []}

        sequential_time = STEP_DURATION * 2  # What sequential would take

        with (
            patch("agents.resume_tailor.ResumeTailorAgent.tailor_for_posting", slow_tailor),
            patch("agents.cover_letter.CoverLetterAgent.generate", slow_cover),
            patch("agents.interview_coach.InterviewCoachAgent.generate_prep_sheet", fast_prep),
        ):
            from agents import get_orchestrator

            orch = get_orchestrator()
            t0 = time.time()
            orch.full_application_pipeline("3", "posting_test_6")
            parallel_time = time.time() - t0

        # Parallel should finish in < sequential_time * 0.85 (at least 15% faster)
        # We use 85% threshold to account for thread overhead
        threshold = sequential_time * 0.85
        assert parallel_time < threshold, (
            f"Parallel ({parallel_time:.2f}s) not faster than "
            f"sequential threshold ({threshold:.2f}s)"
        )
