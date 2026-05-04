"""Routes for Expert AI comparison and guided comparison interview."""

import json
import logging

from auth import require_auth
from expert_comparison import compare_with_expert, generate_merged_resume, run_interview_turn
from flask import Blueprint, g, jsonify, request
from models import JobDescription, ResumeVersion

logger = logging.getLogger(__name__)

expert_compare_bp = Blueprint("expert_compare", __name__)


@expert_compare_bp.route("/api/resume/expert-compare", methods=["POST"])
@require_auth
def run_expert_comparison():
    """POST /api/resume/expert-compare — compare our AI version vs. expert AI version."""
    try:
        data = request.get_json(silent=True) or {}
        our_text = (data.get("our_version_text") or "").strip()
        expert_text = (data.get("expert_version_text") or "").strip()
        job_text = (data.get("job_description") or "").strip()

        if not our_text:
            return jsonify({"error": "our_version_text is required"}), 400
        if not expert_text:
            return jsonify({"error": "expert_version_text is required"}), 400
        if len(expert_text) < 50:
            return jsonify({"error": "expert_version_text is too short (min 50 chars)"}), 400

        if not job_text:
            job_desc = JobDescription.get_latest_for_user(g.user_id)
            if job_desc:
                job_text = job_desc.text

        if not job_text or len(job_text) < 20:
            return jsonify({
                "error": "No job description available. Please provide one or submit a job "
                         "description in the optimizer first."
            }), 400

        result = compare_with_expert(our_text, expert_text, job_text)
        return jsonify(result), 200

    except Exception as exc:
        logger.exception("Expert comparison endpoint failed: %s", exc)
        return jsonify({"error": f"Comparison failed: {exc}"}), 500


@expert_compare_bp.route("/api/resume/expert-compare/interview", methods=["POST"])
@require_auth
def expert_interview_turn():
    """POST /api/resume/expert-compare/interview — one turn of the open-ended interview.

    Stateless: full history is passed on each call.

    Body (JSON):
      history:          list[{question, answer}]
      current_question: str
      user_answer:      str
      user_finished:    bool — true when user clicks 'Finish & Generate'
      context: {job_text, disagreements, recommendation}

    Response (200):
      {insight, next_question, suggested_done, is_complete}
    """
    try:
        data = request.get_json(silent=True) or {}
        history = data.get("history") or []
        current_question = (data.get("current_question") or "").strip()
        user_answer = (data.get("user_answer") or "").strip()
        user_finished = bool(data.get("user_finished", False))
        context = data.get("context") or {}

        if not current_question:
            return jsonify({"error": "current_question is required"}), 400
        if not user_answer:
            return jsonify({"error": "user_answer is required"}), 400

        if not context.get("job_text"):
            job_desc = JobDescription.get_latest_for_user(g.user_id)
            if job_desc:
                context = {**context, "job_text": job_desc.text}

        result = run_interview_turn(
            history=history,
            current_question=current_question,
            user_answer=user_answer,
            context=context,
            user_finished=user_finished,
        )
        return jsonify(result), 200

    except Exception as exc:
        logger.exception("Expert interview turn failed: %s", exc)
        return jsonify({"error": f"Interview failed: {exc}"}), 500


@expert_compare_bp.route("/api/resume/expert-compare/merge", methods=["POST"])
@require_auth
def merge_resumes():
    """POST /api/resume/expert-compare/merge — synthesize personalized merged resume.

    Body (JSON):
      our_text:          str — our AI version
      expert_text:       str — expert / LinkedIn AI version
      interview_history: list[{question, answer}]
      job_description:   str (optional — falls back to latest saved)

    Response (200):
      {merged_text, decisions: [{section, choice, reason}]}
    """
    try:
        data = request.get_json(silent=True) or {}
        our_text = (data.get("our_text") or "").strip()
        expert_text = (data.get("expert_text") or "").strip()
        interview_history = data.get("interview_history") or []
        job_text = (data.get("job_description") or "").strip()

        if not our_text:
            return jsonify({"error": "our_text is required"}), 400
        if not expert_text:
            return jsonify({"error": "expert_text is required"}), 400

        if not job_text:
            job_desc = JobDescription.get_latest_for_user(g.user_id)
            if job_desc:
                job_text = job_desc.text

        # Pull LinkedIn profile context
        linkedin_summary = ""
        try:
            import linkedin_cache
            profile = linkedin_cache.get_profile(g.user_id)
            if profile:
                parts = []
                if profile.get("full_name"):
                    parts.append(f"Name: {profile['full_name']}")
                if profile.get("headline"):
                    parts.append(f"Headline: {profile['headline']}")
                if profile.get("summary"):
                    parts.append(f"Summary: {profile['summary'][:500]}")
                skills = profile.get("skills_and_endorsements") or profile.get("skills") or []
                if skills and isinstance(skills[0], dict):
                    top = sorted(skills, key=lambda s: s.get("endorsement_count", 0), reverse=True)
                    parts.append("Top skills: " + ", ".join(s.get("name", "") for s in top[:15]))
                elif skills:
                    parts.append("Skills: " + ", ".join(str(s) for s in skills[:15]))
                linkedin_summary = "\n".join(parts)
        except Exception as li_exc:
            logger.debug("LinkedIn profile unavailable for merge: %s", li_exc)

        # Pull knowledge graph / deep profile context
        knowledge_context = ""
        try:
            from context_enrichment import get_deep_profile_summary
            knowledge_context = get_deep_profile_summary(g.user_id, max_chars=600) or ""
        except Exception as kc_exc:
            logger.debug("Knowledge context unavailable for merge: %s", kc_exc)

        result = generate_merged_resume(
            our_text=our_text,
            expert_text=expert_text,
            interview_history=interview_history,
            job_text=job_text,
            linkedin_summary=linkedin_summary,
            knowledge_context=knowledge_context,
        )
        return jsonify(result), 200

    except Exception as exc:
        logger.exception("Merge resume endpoint failed: %s", exc)
        return jsonify({"error": f"Merge failed: {exc}"}), 500


@expert_compare_bp.route("/api/resume/expert-compare/save-merged", methods=["POST"])
@require_auth
def save_merged_resume():
    """POST /api/resume/expert-compare/save-merged — save merged resume to library.

    Body (JSON):
      text:  str — final (possibly edited) merged resume text
      label: str (optional)

    Response (201):
      {version_id, message}
    """
    try:
        data = request.get_json(silent=True) or {}
        text = (data.get("text") or "").strip()
        label = (data.get("label") or "Expert Comparison Merged").strip()

        if not text:
            return jsonify({"error": "text is required"}), 400

        version = ResumeVersion.create(
            user_id=g.user_id,
            source="expert_comparison_merge",
            source_id=None,
            file_name=f"{label}.txt",
            file_type="txt",
            parsed_text=text,
            metadata_json=json.dumps({"label": label, "source": "expert_comparison_merge"}),
        )
        return jsonify({"version_id": version.id, "message": "Merged resume saved to library."}), 201

    except Exception as exc:
        logger.exception("Save merged resume failed: %s", exc)
        return jsonify({"error": f"Save failed: {exc}"}), 500
