"""Flask Blueprint for resume recommendation endpoints."""

from flask import Blueprint, request, jsonify, g
from auth import require_auth
from resume_recommender import compare_resumes
from models import ResumeRecommendation

recommender_bp = Blueprint("recommender", __name__, url_prefix="/api/resumes")


@recommender_bp.route("/compare", methods=["POST"])
@require_auth
def compare_resumes_endpoint():
    """POST /api/resumes/compare — Score multiple resumes against a job description.

    Request body:
        {
            "resume_ids": [int, ...] (optional),
            "resume_version_ids": [int, ...] (optional),
            "job_description_text": str (min 50 chars)
        }

    Response (200):
        {
            "recommendation_id": uuid,
            "rankings": [
                {
                    "resume_id": int,
                    "resume_version_id": int | null,
                    "filename": str,
                    "source": str,
                    "score": int (0-100),
                    "score_breakdown": {
                        "keyword_coverage": float,
                        "semantic_similarity": float,
                        "skills_match": float,
                        "section_completeness": float
                    },
                    "matching_keywords": [str, ...],
                    "missing_keywords": [str, ...],
                    "rank": int (1-based)
                },
                ...
            ],
            "recommended_resume_id": int,
            "recommended_version_id": int | null
        }

    Errors:
        400 — missing/empty resume_ids and resume_version_ids
        400 — job_description_text empty or < 50 chars
        401 — missing user-id header
        403 — resume owned by different user
        404 — resume ID not found
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        resume_ids = data.get("resume_ids", []) or []
        resume_version_ids = data.get("resume_version_ids", []) or []
        job_text = data.get("job_description_text", "").strip()
        skip_rationale = bool(data.get("skip_rationale", False))

        # Validate
        if not resume_ids and not resume_version_ids:
            return jsonify({"error": "Must provide resume_ids or resume_version_ids"}), 400

        if not job_text or len(job_text) < 50:
            return jsonify({"error": "job_description_text must be at least 50 characters"}), 400

        # Call orchestration function
        result = compare_resumes(resume_ids, resume_version_ids, job_text, g.user_id,
                                 skip_rationale=skip_rationale)
        return jsonify(result), 200

    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@recommender_bp.route("/recommendations", methods=["GET"])
@require_auth
def list_recommendations():
    """GET /api/resumes/recommendations — List all recommendations for user."""
    try:
        recommendations = ResumeRecommendation.get_all_for_user(g.user_id)
        recs_list = []
        for rec in recommendations:
            # Handle created_at: may be datetime or string from DB
            created_at = rec.created_at
            if hasattr(created_at, 'isoformat'):
                created_at = created_at.isoformat()
            # else it's already a string from DB

            recs_list.append({
                "recommendation_id": rec.id,
                "job_description_text": rec.job_description_text,
                "recommended_resume_id": rec.recommended_resume_id,
                "recommended_version_id": rec.recommended_version_id,
                "user_chosen_resume_id": rec.user_chosen_resume_id,
                "user_chosen_version_id": rec.user_chosen_version_id,
                "session_id": rec.session_id,
                "created_at": created_at
            })

        return jsonify({"recommendations": recs_list}), 200
    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@recommender_bp.route("/recommendations/<recommendation_id>", methods=["GET"])
@require_auth
def get_recommendation(recommendation_id):
    """GET /api/resumes/recommendations/{id} — Retrieve a saved recommendation."""
    try:
        rec = ResumeRecommendation.get_by_id(recommendation_id, g.user_id)
        if not rec:
            return jsonify({"error": "Recommendation not found"}), 404

        # Handle created_at: it may be a datetime or string from DB
        created_at = rec.created_at
        if hasattr(created_at, 'isoformat'):
            created_at = created_at.isoformat()
        # else it's already a string from DB

        return jsonify({
            "recommendation_id": rec.id,
            "job_description_text": rec.job_description_text,
            "resume_scores_json": rec.resume_scores_json,
            "rationale": rec.rationale,
            "recommended_resume_id": rec.recommended_resume_id,
            "recommended_version_id": rec.recommended_version_id,
            "user_chosen_resume_id": rec.user_chosen_resume_id,
            "user_chosen_version_id": rec.user_chosen_version_id,
            "session_id": rec.session_id,
            "created_at": created_at
        }), 200
    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@recommender_bp.route("/recommendations/<recommendation_id>/select", methods=["POST"])
@require_auth
def select_recommendation(recommendation_id):
    """POST /api/resumes/recommendations/{id}/select — Record user selection and create session.

    Request body:
        {
            "resume_id": int (optional),
            "resume_version_id": int (optional)
        }

    Response (200):
        {
            "recommendation_id": uuid,
            "user_chosen_resume_id": int | null,
            "user_chosen_version_id": int | null,
            "session_id": uuid
        }

    Errors:
        400 — missing resume_id and resume_version_id
        404 — recommendation not found
    """
    try:
        # Get recommendation
        rec = ResumeRecommendation.get_by_id(recommendation_id, g.user_id)
        if not rec:
            return jsonify({"error": "Recommendation not found"}), 404

        data = request.get_json() or {}
        resume_id = data.get("resume_id")
        resume_version_id = data.get("resume_version_id")

        if not resume_id and not resume_version_id:
            return jsonify({"error": "Must provide resume_id or resume_version_id"}), 400

        # Create session linked to this recommendation
        from models import JobSession
        session = JobSession.create(
            user_id=g.user_id,
            session_name=f"Recommendation {recommendation_id[:8]}",
            resume_id=resume_id,
            resume_version_id=resume_version_id,
            job_description_text=rec.job_description_text,
        )

        # Record selection in recommendation
        rec.select(resume_id, resume_version_id, session.id)

        # Link recommendation to session
        JobSession.update(session.id, recommendation_id=recommendation_id)

        # Normalize IDs to int for consistent API responses
        chosen_resume_id = int(resume_id) if resume_id is not None else None
        chosen_version_id = int(resume_version_id) if resume_version_id is not None else None

        return jsonify({
            "recommendation_id": rec.id,
            "user_chosen_resume_id": chosen_resume_id,
            "user_chosen_version_id": chosen_version_id,
            "session_id": session.id
        }), 200

    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
