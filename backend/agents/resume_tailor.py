"""Resume Tailor Agent — auto-customizes resume per job posting via RTX 5090."""

import json
import logging
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseCareerAgent
from agents.resume_tailor_engine import _ResumeTailorEngineMixin
from agents.resume_tailor_scoring import _ResumeTailorScoringMixin
from models import get_db

logger = logging.getLogger(__name__)


class ResumeTailorAgent(_ResumeTailorEngineMixin, _ResumeTailorScoringMixin, BaseCareerAgent):
    """Agent that analyzes job postings and tailors resumes for ATS optimization.

    Pipeline:
        1. Analyze job requirements (LLM extraction of skills, levels, keywords)
        2. Match candidate experience against requirements
        3. Generate tailored resume via LLM rewrite
        4. Score the result against ATS criteria
        5. Support iterative refinement from user feedback
    """

    agent_type = "resume_tailor"

    # Navigation — method locations:
    #   resume_tailor.py         tailor_for_posting, refine, get_tailored, get_versions
    #   resume_tailor_engine.py  _analyze_job_requirements, _fallback_job_analysis,
    #                            _match_experience, _generate_tailored_resume
    #   resume_tailor_scoring.py _fuzzy_skill_match, _score_ats_match, _apply_refinement,
    #                            _get_posting, _load_deep_profile, _build_resume_data,
    #                            _run_nlp_fallback
    #   base_agent.py            _call_llm, _log_run, _get_user_profile, _profile_summary,
    #                            _record_claim, _get_arango_context

    # ──────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────

    def tailor_for_posting(
        self,
        user_id: str,
        posting_id: str,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Tailor resume for a specific job posting. Returns optimized result.

        Args:
            user_id: The user whose resume to tailor.
            posting_id: ID of the job posting to tailor for.
            preferences: Optional dict with keys like ``tone`` (professional/conversational),
                ``emphasis`` (list of areas to highlight), ``length`` (short/standard/detailed).

        Returns:
            Dict with ``optimized_text``, ``ats_score``, ``score_breakdown``,
            ``matching_keywords``, ``added_keywords``, ``version_id``,
            ``job_requirements``, and ``experience_matches``.
        """
        posting = self._get_posting(posting_id, user_id=user_id)
        if not posting:
            return {"error": "Posting not found"}

        jd_text = posting.get("description", "")
        if not jd_text:
            return {"error": "Posting has no job description"}

        # Load latest resume
        with get_db() as conn:
            row = conn.execute(
                "SELECT id, parsed_text FROM resume_versions WHERE user_id = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (user_id,),
            ).fetchone()

        if not row or not row[1]:
            return {"error": "No resume found. Upload or import a resume first."}

        resume_text = row[1]

        # Load user profile (LinkedIn + deep profile + resume excerpt)
        profile = self._get_user_profile(user_id)
        profile_text = self._profile_summary(profile)

        # CT-4: Inject ArangoDB knowledge-graph context before LLM call
        arango_ctx = self._get_arango_context(user_id, self.agent_type)
        if arango_ctx:
            profile_text = f"{profile_text}\n\n<arango_context>\n{arango_ctx}\n</arango_context>"

        # Load deep profile for enriched context
        deep_profile_data = self._load_deep_profile(user_id)

        # P2-A: Check deep profile staleness — surface to caller
        profile_stale = False
        stale_reason = ""
        try:
            from deep_profile_staleness import check_staleness

            staleness = check_staleness(int(user_id))
            profile_stale = staleness.get("is_stale", False)
            stale_reason = staleness.get("stale_reason", "")
        except Exception as _e:
            logger.debug("Staleness check failed: %s", _e)

        # P2-C: Build success context from historical feedback outcomes
        success_context = ""
        try:
            from feedback_analyzer import build_success_context

            with get_db() as _fb_conn:
                _fb_rows = _fb_conn.execute(
                    "SELECT ats_score, outcome_type FROM application_feedback "
                    "WHERE user_id=? AND outcome_type != '' "
                    "ORDER BY transitioned_at DESC LIMIT 20",
                    (user_id,),
                ).fetchall()
            success_context = build_success_context([dict(r) for r in _fb_rows])
        except Exception as _e:
            logger.debug("Success context fetch failed: %s", _e)

        # Step 1: Analyze job requirements via LLM
        job_requirements, req_duration = self._timed(self._analyze_job_requirements, jd_text)
        if not job_requirements:
            # Fallback to NLP-only keyword extraction
            job_requirements = self._fallback_job_analysis(jd_text)

        # Step 2: Match candidate experience to requirements
        resume_data = self._build_resume_data(resume_text, user_id)
        experience_matches = self._match_experience(resume_data, job_requirements, profile)

        # Step 3: Generate tailored resume via LLM rewrite
        tailored_text, gen_duration = self._timed(
            self._generate_tailored_resume,
            resume_data,
            job_requirements,
            experience_matches,
            profile_text,
            posting,
            preferences,
            success_context,
        )

        if not tailored_text:
            # Fallback: use NLP-only optimization from utils
            tailored_text, gen_duration = self._run_nlp_fallback(
                resume_data, jd_text, user_id, deep_profile_data
            )

        if not tailored_text:
            self._log_run(
                user_id,
                f"Tailor resume for: {posting.get('title', '')}",
                {"posting_id": posting_id},
                {"error": "Optimization produced no output"},
                task_type="resume_rewrite",
                duration_ms=req_duration + gen_duration,
                status="failed",
            )
            return {"error": "Optimization failed to produce output"}

        # CT-3: Diff verification — flag cosmetic-only tailoring
        diff_result: Dict[str, Any] = {}
        try:
            import dataclasses
            from agents.resume_diff_verifier import ResumeDiffVerifier

            _diff = ResumeDiffVerifier().verify(resume_text, tailored_text, jd_text)
            diff_result = dataclasses.asdict(_diff) if dataclasses.is_dataclass(_diff) else _diff
            if not diff_result.get("meaningful_change", True):
                logger.warning(
                    "[CT-3] Cosmetic-only tailoring detected for user=%s posting=%s "
                    "(jaccard=%.2f, new_keywords=%d)",
                    user_id,
                    posting_id,
                    diff_result.get("jaccard_sim", 0),
                    diff_result.get("new_keywords", 0),
                )
        except Exception as _e:
            logger.debug("[CT-3] Diff verification failed (non-blocking): %s", _e)

        # CT-5: Cross-model verification — rubric score against JD
        cross_verify_result: Dict[str, Any] = {}
        try:
            from agents.cross_model_verifier import CrossModelVerifier

            cross_verify_result = CrossModelVerifier().verify(resume_text, tailored_text, jd_text)
            if not cross_verify_result.get("passed", True):
                logger.warning(
                    "[CT-5] Cross-model verification FAILED for user=%s posting=%s "
                    "(avg=%.1f, issues=%s)",
                    user_id,
                    posting_id,
                    cross_verify_result.get("average", 0),
                    cross_verify_result.get("issues", []),
                )
        except Exception as _e:
            logger.debug("[CT-5] Cross-model verification failed (non-blocking): %s", _e)

        # CT-1: Record claim for accountability audit
        self._record_claim(
            user_id,
            "resume_tailor",
            jd_text[:500],
            tailored_text[:500],
            metadata={
                "posting_id": posting_id,
                "diff_meaningful": diff_result.get("meaningful_change"),
                "cross_verify_passed": cross_verify_result.get("passed"),
            },
        )

        # Step 4: Score the tailored resume against ATS criteria
        ats_result = self._score_ats_match(tailored_text, job_requirements, jd_text)
        ats_score = ats_result.get("overall_score", 0)
        score_breakdown = ats_result.get("breakdown", {})

        # Collect keyword data
        matching_keywords = ats_result.get("matching_keywords", [])
        added_keywords = ats_result.get("added_keywords", [])

        # Save as resume_versions record
        from models import ResumeVersion

        title = posting.get("title", "Unknown Role")
        company = posting.get("company", "")
        file_name = f"Tailored - {title} @ {company}" if company else f"Tailored - {title}"

        version = ResumeVersion.create(
            user_id=user_id,
            source="agent_tailor",
            file_name=file_name,
            parsed_text=tailored_text,
            source_id=posting_id,
            metadata_json=json.dumps(
                {
                    "posting_id": posting_id,
                    "ats_score": ats_score,
                    "score_breakdown": score_breakdown,
                    "job_requirements": job_requirements,
                    "matching_keywords": matching_keywords[:30],
                    "added_keywords": added_keywords[:20],
                }
            ),
        )

        # P2-B: Write traceability edges to ArangoDB
        try:
            from graph_traceability import (
                extract_evidence_references,
                write_resume_version_to_graph,
            )

            evidence_refs = extract_evidence_references(tailored_text, user_id)
            write_resume_version_to_graph(
                user_id=int(user_id),
                version_id=version.id,
                source="agent_tailor",
                posting=posting,
                evidence_refs=evidence_refs,
            )
        except Exception as _e:
            logger.warning("P2-B graph traceability write failed: %s", _e)

        # Update posting with tailored version reference
        with get_db() as conn:
            conn.execute(
                "UPDATE job_postings SET tailored_version_id = ?, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = ?",
                (str(version.id), posting_id),
            )
            conn.commit()

        total_duration = req_duration + gen_duration
        self._log_run(
            user_id,
            f"Tailor resume for: {title}",
            {"posting_id": posting_id, "preferences": preferences},
            {"version_id": version.id, "ats_score": ats_score},
            task_type="resume_rewrite",
            duration_ms=total_duration,
        )

        return {
            "optimized_text": tailored_text,
            "ats_score": ats_score,
            "score_breakdown": score_breakdown,
            "matching_keywords": matching_keywords,
            "added_keywords": added_keywords,
            "version_id": version.id,
            "job_requirements": job_requirements,
            "experience_matches": experience_matches,
            "profile_stale": profile_stale,
            "stale_reason": stale_reason if profile_stale else "",
            "diff_verification": diff_result,
            "cross_model_verification": cross_verify_result,
        }

    def refine(
        self,
        user_id: str,
        posting_id: str,
        feedback: str,
    ) -> Dict[str, Any]:
        """Iteratively refine a tailored resume based on user feedback.

        Args:
            user_id: The user whose resume to refine.
            posting_id: The posting this tailored resume was created for.
            feedback: Natural-language feedback describing desired changes
                (e.g. "emphasize more leadership experience",
                "tone down the technical jargon", "add more metrics").

        Returns:
            Same shape as ``tailor_for_posting`` output, with updated text and scores.
        """
        if not feedback or not feedback.strip():
            return {"error": "Feedback is required for refinement"}

        # Load existing tailored version
        existing = self.get_tailored(posting_id, user_id=user_id)
        if not existing:
            return {"error": "No tailored resume found for this posting. Tailor first."}

        posting = self._get_posting(posting_id, user_id=user_id)
        if not posting:
            return {"error": "Posting not found"}

        jd_text = posting.get("description", "")
        current_text = existing.get("parsed_text", "")

        if not current_text:
            return {"error": "Existing tailored resume has no content"}

        # Extract stored metadata
        metadata = existing.get("metadata", {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                metadata = {}
        job_requirements = metadata.get("job_requirements", {})

        # If no stored requirements, re-analyze
        if not job_requirements and jd_text:
            job_requirements = self._analyze_job_requirements(jd_text)
            if not job_requirements:
                job_requirements = self._fallback_job_analysis(jd_text)

        # LLM refinement call
        refined_text, duration = self._timed(
            self._apply_refinement, current_text, jd_text, feedback, job_requirements
        )

        if not refined_text:
            self._log_run(
                user_id,
                f"Refine resume for: {posting.get('title', '')}",
                {"posting_id": posting_id, "feedback": feedback},
                {"error": "Refinement produced no output"},
                task_type="resume_refine",
                duration_ms=duration,
                status="failed",
            )
            return {"error": "Refinement failed — LLM returned no output"}

        # Re-score
        ats_result = self._score_ats_match(refined_text, job_requirements, jd_text)
        ats_score = ats_result.get("overall_score", 0)
        score_breakdown = ats_result.get("breakdown", {})
        matching_keywords = ats_result.get("matching_keywords", [])
        added_keywords = ats_result.get("added_keywords", [])

        # Save new version
        from models import ResumeVersion

        title = posting.get("title", "Unknown Role")
        company = posting.get("company", "")
        file_name = f"Refined - {title} @ {company}" if company else f"Refined - {title}"

        version = ResumeVersion.create(
            user_id=user_id,
            source="agent_tailor",
            file_name=file_name,
            parsed_text=refined_text,
            source_id=posting_id,
            metadata_json=json.dumps(
                {
                    "posting_id": posting_id,
                    "ats_score": ats_score,
                    "score_breakdown": score_breakdown,
                    "job_requirements": job_requirements,
                    "feedback_applied": feedback,
                    "parent_version_id": existing.get("id"),
                }
            ),
        )

        # Update posting reference to newest version
        with get_db() as conn:
            conn.execute(
                "UPDATE job_postings SET tailored_version_id = ?, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = ?",
                (str(version.id), posting_id),
            )
            conn.commit()

        self._log_run(
            user_id,
            f"Refine resume for: {title}",
            {"posting_id": posting_id, "feedback": feedback},
            {"version_id": version.id, "ats_score": ats_score},
            task_type="resume_refine",
            duration_ms=duration,
        )

        return {
            "optimized_text": refined_text,
            "ats_score": ats_score,
            "score_breakdown": score_breakdown,
            "matching_keywords": matching_keywords,
            "added_keywords": added_keywords,
            "version_id": version.id,
            "feedback_applied": feedback,
        }

    def get_tailored(self, posting_id: str, user_id: Optional[str] = None) -> Optional[Dict]:
        """Retrieve existing tailored version for a posting."""
        with get_db() as conn:
            if user_id is not None:
                row = conn.execute(
                    "SELECT tailored_version_id FROM job_postings WHERE id = ? AND user_id = ?",
                    (posting_id, user_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT tailored_version_id FROM job_postings WHERE id = ?",
                    (posting_id,),
                ).fetchone()

        if not row or not row[0]:
            return None

        version_id = row[0]
        with get_db() as conn:
            vrow = conn.execute(
                "SELECT * FROM resume_versions WHERE id = ?", (version_id,)
            ).fetchone()

        if not vrow:
            return None

        d = dict(vrow)
        if isinstance(d.get("metadata_json"), str):
            try:
                d["metadata"] = json.loads(d["metadata_json"])
            except (json.JSONDecodeError, TypeError):
                d["metadata"] = {}
        return d

    def get_versions(self, user_id: str, posting_id: str) -> List[Dict]:
        """List all tailored versions for a posting (refinement history).

        Args:
            user_id: The user to filter by.
            posting_id: The posting whose tailored versions to list.

        Returns:
            List of version dicts, newest first.
        """
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM resume_versions "
                "WHERE user_id = ? AND source = 'agent_tailor' AND source_id = ? "
                "ORDER BY created_at DESC",
                (user_id, posting_id),
            ).fetchall()

        versions = []
        for row in rows:
            d = dict(row)
            if isinstance(d.get("metadata_json"), str):
                try:
                    d["metadata"] = json.loads(d["metadata_json"])
                except (json.JSONDecodeError, TypeError):
                    d["metadata"] = {}
            versions.append(d)
        return versions
