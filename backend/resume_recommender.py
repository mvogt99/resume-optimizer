"""Multi-resume comparison and ranking orchestration.

Reuses score_resume() from Phase 1. Handles resume loading, scoring,
ranking, and persistence to resume_recommendations table.
"""

import uuid
from datetime import datetime
from resume_scorer import score_resume
from models import Resume, ResumeVersion, ResumeRecommendation
from utils import process_resume


def _batch_semantic_scores(texts, job_text):
    """Pre-compute semantic similarity for all resume texts against job_text in one batch.

    Returns list[float] (0-100 scaled) in same order as texts.
    Falls back to per-call calculate_similarity if model unavailable.
    """
    from nlp_engine import _get_st_model
    model = _get_st_model()
    if model is None or not job_text:
        return [0.0] * len(texts)
    try:
        import numpy as np
        all_texts = [job_text] + texts
        embeddings = model.encode(all_texts)
        job_emb = embeddings[0]
        scores = []
        for r_emb in embeddings[1:]:
            denom = (np.linalg.norm(job_emb) * np.linalg.norm(r_emb)) + 1e-10
            cos_sim = float(np.dot(job_emb, r_emb) / denom)
            scores.append(max(0.0, cos_sim) * 100)
        return scores
    except Exception:
        return [0.0] * len(texts)


def compare_resumes(resume_ids, resume_version_ids, job_text, user_id, linkedin_profile=None, skip_rationale=False):
    """Score multiple resumes against a job description and rank them.

    Args:
        resume_ids: list[int] — resume IDs to compare
        resume_version_ids: list[int] — resume version IDs to compare (alternative to resume_ids)
        job_text: str — job description text (min 50 chars)
        user_id: int — authenticated user ID
        linkedin_profile: dict (optional) — LinkedIn data for skills weighting

    Returns:
        dict with keys:
          - recommendation_id: UUID (persisted to DB)
          - rankings: list[dict] — sorted by score descending
          - recommended_resume_id: int (highest score resume's ID)
          - recommended_version_id: int (highest score version's ID, if applicable)

    Raises:
        ValueError: if inputs invalid
        PermissionError: if user doesn't own resume
    """
    # Validate inputs
    if not job_text or len(job_text.strip()) < 50:
        raise ValueError("job_description_text must be at least 50 characters")

    if not resume_ids and not resume_version_ids:
        raise ValueError("Must provide either resume_ids or resume_version_ids")

    # Load all resumes/versions
    resumes_to_score = []

    if resume_ids:
        for resume_id in resume_ids:
            resume = Resume.get_by_id(resume_id)
            if not resume:
                raise FileNotFoundError(f"Resume {resume_id} not found")
            if resume.user_id != user_id:
                raise PermissionError(f"Resume {resume_id} not owned by user")
            # Read resume file content
            try:
                resume_data = process_resume(resume.file_path)
                resume_text = resume_data.get("text", "")
            except Exception:
                resume_text = ""
            resumes_to_score.append({
                "resume_id": resume.id,
                "resume_version_id": None,
                "filename": resume.filename,
                "source": "upload",
                "text": resume_text
            })

    if resume_version_ids:
        for version_id in resume_version_ids:
            version = ResumeVersion.get_by_id(version_id)
            if not version:
                raise FileNotFoundError(f"Resume version {version_id} not found")
            if version.user_id != user_id:
                raise PermissionError(f"Resume version {version_id} not owned by user")
            resumes_to_score.append({
                "resume_id": None,
                "resume_version_id": version.id,
                "filename": version.file_name,
                "source": version.source or "upload",
                "text": version.parsed_text
            })

    # Extract job keywords for scoring
    from nlp_engine import extract_skill_phrases
    job_keywords = extract_skill_phrases(job_text) or []
    if not job_keywords:
        # Fallback: split job text into words
        job_keywords = job_text.split()[:20]

    # Pre-compute all semantic similarities in one batched model.encode() call
    resume_texts = [r["text"] for r in resumes_to_score]
    semantic_scores = _batch_semantic_scores(resume_texts, job_text)

    # Score each resume (semantic similarity pre-computed, no redundant model calls)
    rankings = []
    for idx, resume_data in enumerate(resumes_to_score):
        resume_dict = {
            "text": resume_data["text"],
            "skills": [],
            "experience": [],
            "education": []
        }

        score_result = score_resume(
            resume_dict, job_keywords, job_text, linkedin_profile,
            precomputed_semantic=semantic_scores[idx]
        )

        # Ensure IDs are integers
        resume_id = resume_data["resume_id"]
        resume_version_id = resume_data["resume_version_id"]
        if isinstance(resume_id, str):
            try:
                resume_id = int(resume_id)
            except (ValueError, TypeError):
                pass
        if isinstance(resume_version_id, str):
            try:
                resume_version_id = int(resume_version_id)
            except (ValueError, TypeError):
                pass

        rankings.append({
            "resume_id": resume_id,
            "resume_version_id": resume_version_id,
            "filename": resume_data["filename"],
            "source": resume_data["source"],
            "score": score_result["score"],
            "score_breakdown": score_result["score_breakdown"],
            "matching_keywords": score_result["matching_keywords"],
            "missing_keywords": score_result["missing_keywords"],
            "rank": None  # Will set after sorting
        })

    # Sort by score descending
    rankings.sort(key=lambda r: r["score"], reverse=True)

    # Assign ranks (1-based)
    for idx, ranking in enumerate(rankings):
        ranking["rank"] = idx + 1

    # Persist to database
    recommendation_id = str(uuid.uuid4())
    top_ranked = rankings[0] if rankings else None

    # Generate rationale (LLM or template fallback) before persisting
    from recommendation_rationale import generate_rationale, template_rationale
    if skip_rationale:
        rationale = template_rationale(rankings)
    else:
        rationale = generate_rationale(rankings, job_text, timeout=30)

    import json as _json
    recommendation = ResumeRecommendation(
        id=recommendation_id,
        user_id=user_id,
        job_description_text=job_text,
        resume_scores_json=_json.dumps(rankings),
        recommended_resume_id=top_ranked["resume_id"] if top_ranked else None,
        recommended_version_id=top_ranked["resume_version_id"] if top_ranked else None,
        rationale=rationale,
        created_at=datetime.utcnow()
    )
    recommendation.save()

    # Ensure resume IDs are integers for consistency
    recommended_resume_id = top_ranked["resume_id"] if top_ranked else None
    recommended_version_id = top_ranked["resume_version_id"] if top_ranked else None
    if isinstance(recommended_resume_id, str):
        try:
            recommended_resume_id = int(recommended_resume_id)
        except (ValueError, TypeError):
            pass
    if isinstance(recommended_version_id, str):
        try:
            recommended_version_id = int(recommended_version_id)
        except (ValueError, TypeError):
            pass

    return {
        "recommendation_id": recommendation_id,
        "rankings": rankings,
        "recommended_resume_id": recommended_resume_id,
        "recommended_version_id": recommended_version_id,
        "rationale": rationale
    }
