"""Phase 15: Multi-agent orchestrator — chains agents for end-to-end workflows."""

import concurrent.futures
import json
import logging
import time

from agents.acceptance import verify
from agents.base_agent import BaseCareerAgent
from models import get_db

logger = logging.getLogger(__name__)


class OrchestratorAgent(BaseCareerAgent):
    agent_type = "orchestrator"

    def _run_parallel(self, tasks):
        """Run a list of (callable, args, kwargs) tuples concurrently.

        Returns list of (result, duration_ms) tuples in submission order.
        Exceptions from individual tasks are re-raised by the caller via
        future.result(), so callers must handle them per-task.
        """
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(tasks)) as executor:
            futures = [
                executor.submit(self._timed, fn, *args, **kwargs) for fn, args, kwargs in tasks
            ]
            return futures  # Caller resolves each future individually

    def full_application_pipeline(self, user_id, posting_id):
        """Chain agents: tailor + cover letter in parallel, then interview prep."""
        from agents import get_cover_letter, get_interview_coach, get_resume_tailor

        steps_completed = []
        errors = []
        result = {
            "posting_id": posting_id,
            "steps_completed": steps_completed,
            "tailored_resume": None,
            "cover_letter": None,
            "prep_sheet": None,
            "status": "complete",
            "errors": errors,
        }

        start = time.time()

        tailor = get_resume_tailor()
        cover = get_cover_letter()

        # Steps 1 + 2: Resume Tailor and Cover Letter run in parallel
        tailor_result = None
        cover_result = None
        tailor_dur = 0
        cover_dur = 0

        futures = self._run_parallel(
            [
                (tailor.tailor_for_posting, (user_id, posting_id), {}),
                (cover.generate, (user_id, posting_id), {}),
            ]
        )
        tailor_future, cover_future = futures

        try:
            tailor_result, tailor_dur = tailor_future.result(timeout=120)
        except Exception as e:
            logger.error("Resume tailor failed: %s", e)
            errors.append({"step": "resume_tailor", "error": str(e)})

        try:
            cover_result, cover_dur = cover_future.result(timeout=120)
        except Exception as e:
            logger.error("Cover letter failed: %s", e)
            errors.append({"step": "cover_letter", "error": str(e)})

        # Process tailor result
        if tailor_result is not None:
            if "error" not in tailor_result:
                tailor_accept = verify("resume_tailor", tailor_result)
                if not tailor_accept.passed:
                    logger.warning(
                        "[Orchestrator] resume_tailor acceptance FAILED: %s",
                        tailor_accept.failure_summary,
                    )
                result["tailored_resume"] = {
                    "version_id": tailor_result.get("version_id"),
                    "ats_score": tailor_result.get("ats_score", tailor_result.get("score")),
                    "acceptance_passed": tailor_accept.passed,
                }
                steps_completed.append("resume_tailor")
                self._log_run(
                    user_id,
                    "Tailor resume",
                    {"posting_id": posting_id},
                    tailor_result,
                    task_type="resume_tailor",
                    duration_ms=tailor_dur,
                    acceptance_result=tailor_accept,
                )
            else:
                errors.append(
                    {"step": "resume_tailor", "error": tailor_result.get("error", "Unknown")}
                )

        # Process cover letter result
        if cover_result is not None:
            if "error" not in cover_result:
                cover_accept = verify("cover_letter", cover_result)
                if not cover_accept.passed:
                    logger.warning(
                        "[Orchestrator] cover_letter acceptance FAILED: %s",
                        cover_accept.failure_summary,
                    )
                result["cover_letter"] = {
                    "id": cover_result.get("id"),
                    "subject": cover_result.get("subject", ""),
                    "acceptance_passed": cover_accept.passed,
                }
                steps_completed.append("cover_letter")
                self._log_run(
                    user_id,
                    "Generate cover letter",
                    {"posting_id": posting_id},
                    cover_result,
                    task_type="cover_letter",
                    duration_ms=cover_dur,
                    acceptance_result=cover_accept,
                )
            else:
                errors.append(
                    {"step": "cover_letter", "error": cover_result.get("error", "Unknown")}
                )

        # Step 3: Interview Prep — sequential, depends on Resume Tailor output
        if "resume_tailor" in steps_completed:
            try:
                coach = get_interview_coach()
                prep_result, dur = self._timed(coach.generate_prep_sheet, user_id, posting_id)
                if prep_result and "error" not in prep_result:
                    prep_data = prep_result.get("prep_data", {})
                    result["prep_sheet"] = {
                        "questions": prep_data.get("questions", prep_result.get("questions", [])),
                        "talking_points": prep_result.get("talking_points", []),
                        "star_examples": prep_result.get("star_examples", []),
                    }
                    steps_completed.append("interview_prep")
                    self._log_run(
                        user_id,
                        "Generate prep sheet",
                        {"posting_id": posting_id},
                        prep_result,
                        task_type="interview_prep",
                        duration_ms=dur,
                    )
                else:
                    errors.append(
                        {
                            "step": "interview_prep",
                            "error": prep_result.get("error", "Unknown"),
                        }
                    )
            except Exception as e:
                logger.error("Interview prep failed: %s", e)
                errors.append({"step": "interview_prep", "error": str(e)})

        # Step 4: Move to pipeline "applied" stage
        if steps_completed:  # At least one step succeeded
            try:
                with get_db() as conn:
                    conn.execute(
                        "UPDATE job_postings SET status = 'applied',"
                        " updated_at = CURRENT_TIMESTAMP"
                        " WHERE id = ? AND status NOT IN ('applied', 'offered', 'accepted')",
                        (posting_id,),
                    )
                    conn.commit()
                steps_completed.append("pipeline_move")
            except Exception as e:
                logger.error("Pipeline move failed: %s", e)
                errors.append({"step": "pipeline_move", "error": str(e)})

        total_ms = int((time.time() - start) * 1000)
        if errors and not steps_completed:
            result["status"] = "failed"
        elif errors:
            result["status"] = "partial"

        self._log_run(
            user_id,
            "Full application pipeline",
            {"posting_id": posting_id},
            {"steps": steps_completed, "errors": [e["step"] for e in errors]},
            task_type="orchestrator",
            duration_ms=total_ms,
            status=result["status"],
        )

        return result

    def career_deep_dive(self, user_id, posting_id=None):
        """Chain career advisor analysis steps."""
        from agents import get_career_advisor

        advisor = get_career_advisor()
        errors = []
        result = {"career_analysis": None, "role_recommendations": None, "skills_roadmap": None}

        try:
            analysis, dur = self._timed(advisor.analyze_career, user_id)
            if analysis and "error" not in analysis:
                analysis_accept = verify("career_advisor", analysis)
                if not analysis_accept.passed:
                    logger.warning(
                        "[Orchestrator] career_advisor acceptance FAILED: %s",
                        analysis_accept.failure_summary,
                    )
                result["career_analysis"] = analysis
            else:
                errors.append(
                    {"step": "analyze_career", "error": (analysis or {}).get("error", "Unknown")}
                )
        except Exception as e:
            errors.append({"step": "analyze_career", "error": str(e)})

        try:
            recs, dur = self._timed(advisor.get_role_recommendations, user_id)
            if recs and "error" not in recs:
                recs_accept = verify("advisor_roles", recs)
                if not recs_accept.passed:
                    logger.warning(
                        "[Orchestrator] advisor_roles acceptance FAILED: %s",
                        recs_accept.failure_summary,
                    )
                result["role_recommendations"] = recs
            else:
                errors.append(
                    {"step": "role_recommendations", "error": (recs or {}).get("error", "Unknown")}
                )
        except Exception as e:
            errors.append({"step": "role_recommendations", "error": str(e)})

        if posting_id:
            try:
                # Get target role from posting
                with get_db() as conn:
                    row = conn.execute(
                        "SELECT title FROM job_postings WHERE id = ?", (posting_id,)
                    ).fetchone()
                if row:
                    roadmap, dur = self._timed(advisor.get_skills_roadmap, user_id, row[0])
                    if roadmap and "error" not in roadmap:
                        result["skills_roadmap"] = roadmap
            except Exception as e:
                errors.append({"step": "skills_roadmap", "error": str(e)})

        result["errors"] = errors
        result["status"] = (
            "failed"
            if errors
            and not any(
                result[k] for k in ("career_analysis", "role_recommendations", "skills_roadmap")
            )
            else ("partial" if errors else "complete")
        )
        return result

    def get_workflow_status(self, user_id):
        """Get recent orchestrator workflow runs and their step completion."""
        with get_db() as conn:
            rows = conn.execute(
                "SELECT id, task_description, output_json, status, duration_ms, created_at "
                "FROM agent_runs WHERE user_id = ? AND agent_type = 'orchestrator' "
                "ORDER BY created_at DESC LIMIT 20",
                (user_id,),
            ).fetchall()

        runs = []
        for r in rows:
            output = json.loads(r["output_json"] or "{}")
            runs.append(
                {
                    "run_id": r["id"],
                    "task": r["task_description"],
                    "steps_completed": output.get("steps", []),
                    "errors": output.get("errors", []),
                    "status": r["status"],
                    "duration_ms": r["duration_ms"],
                    "created_at": r["created_at"],
                }
            )
        return {"runs": runs, "total": len(runs)}
