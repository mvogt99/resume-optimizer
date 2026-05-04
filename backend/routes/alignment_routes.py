"""Alignment pipeline routes — Phase A+B+C: normalization, JD parsing, gap + hybrid scoring, artifacts.

Endpoints:
  POST /api/alignment/parse-jd          — parse JD into atomic requirements
  POST /api/alignment/normalize         — build normalized candidate profile
  POST /api/alignment/classify-gaps     — classify gaps between JD and candidate
  POST /api/alignment/score             — 7-dimension hybrid scoring per requirement
  POST /api/alignment/analyze           — full pipeline (normalize + parse + score + gaps)
  POST /api/alignment/artifacts         — generate artifacts from alignment analysis
  GET  /api/alignment/gaps/<resume_id>  — retrieve last gap analysis for a resume
"""

import json
import logging
import time

from flask import Blueprint, g, jsonify, request

from auth import require_auth

logger = logging.getLogger(__name__)

alignment_bp = Blueprint("alignment", __name__)


def _get_resume_text(resume_id: int, user_id: int) -> str:
    """Fetch resume text from DB by resume_id (reads file from disk)."""
    try:
        from models import get_db
        from utils import process_resume
        with get_db() as conn:
            # Check resumes table (raw upload)
            row = conn.execute(
                "SELECT file_path FROM resumes WHERE id = ? AND user_id = ?",
                (resume_id, user_id),
            ).fetchone()
            if row and row["file_path"]:
                parsed = process_resume(row["file_path"])
                return parsed.get("text", "") or ""
            # Also check resume_versions (parsed_text column exists here)
            row = conn.execute(
                "SELECT parsed_text FROM resume_versions WHERE id = ? AND user_id = ?",
                (resume_id, user_id),
            ).fetchone()
            if row:
                return row["parsed_text"] or ""
    except Exception as e:
        logger.warning("alignment: failed to fetch resume text: %s", e)
    return ""


def _save_gap_analysis(user_id: int, resume_id: int, job_id: int, result: dict) -> None:
    """Persist gap analysis + scores result to DB for later retrieval."""
    try:
        from models import get_db
        with get_db() as conn:
            conn.execute(
                "INSERT INTO alignment_analyses "
                "(user_id, resume_id, job_id, gaps_json, requirements_json, "
                "candidate_profile_json, scores_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP) "
                "ON CONFLICT(user_id, resume_id, job_id) DO UPDATE SET "
                "gaps_json=excluded.gaps_json, "
                "requirements_json=excluded.requirements_json, "
                "candidate_profile_json=excluded.candidate_profile_json, "
                "scores_json=excluded.scores_json, "
                "created_at=CURRENT_TIMESTAMP",
                (
                    user_id, resume_id, job_id,
                    json.dumps(result.get("gaps", [])),
                    json.dumps(result.get("requirements", [])),
                    json.dumps(result.get("candidate_profile", {})),
                    json.dumps(result.get("scores", [])),
                ),
            )
            conn.commit()
    except Exception as e:
        logger.warning("alignment: failed to save gap analysis: %s", e)


@alignment_bp.route("/api/alignment/parse-jd", methods=["POST"])
@require_auth
def parse_jd():
    """Parse a job description into atomic typed requirements.

    Request body:
      job_text   str  — raw job description text
      use_llm    bool — (optional) use LLM parser, default True

    Response:
      { requirements: [...], count: int, categories: {...} }
    """
    user_id = g.user_id

    body = request.get_json(silent=True) or {}
    job_text = body.get("job_text", "").strip()
    if not job_text or len(job_text) < 50:
        return jsonify({"error": "job_text required (min 50 chars)"}), 400

    use_llm = body.get("use_llm", True)

    try:
        from jd_parser import group_requirements_by_category, parse_requirements
        requirements = parse_requirements(job_text, use_llm=use_llm)
        grouped = group_requirements_by_category(requirements)
        return jsonify({
            "requirements": requirements,
            "count": len(requirements),
            "categories": {cat: len(reqs) for cat, reqs in grouped.items()},
        })
    except Exception as e:
        logger.error("alignment parse-jd error: %s", e)
        return jsonify({"error": "JD parsing failed"}), 500


@alignment_bp.route("/api/alignment/normalize", methods=["POST"])
@require_auth
def normalize_candidate():
    """Build normalized candidate profile from career data.

    Request body:
      resume_id        int  — (optional) resume to include in normalization
      target_job_title str  — (optional) role title for role-family inference

    Response:
      { candidate_profile: {...} }
    """
    user_id = g.user_id

    body = request.get_json(silent=True) or {}
    resume_id = body.get("resume_id")
    target_job_title = body.get("target_job_title", "")

    resume_text = ""
    if resume_id:
        resume_text = _get_resume_text(int(resume_id), user_id)

    try:
        from normalizer import normalize_candidate as _normalize
        profile = _normalize(
            user_id=user_id,
            resume_text=resume_text,
            target_job_title=target_job_title,
        )
        return jsonify({"candidate_profile": profile})
    except Exception as e:
        logger.error("alignment normalize error: %s", e)
        return jsonify({"error": "Normalization failed"}), 500


@alignment_bp.route("/api/alignment/classify-gaps", methods=["POST"])
@require_auth
def classify_gaps():
    """Classify gaps between requirements and candidate profile.

    Request body:
      requirements       list — from parse-jd
      candidate_profile  dict — from normalize (optional; built on-the-fly if absent)
      resume_id          int  — resume to classify against
      use_llm            bool — use LLM refinement, default True

    Response:
      { gaps: [...], summary: {...} }
    """
    user_id = g.user_id

    body = request.get_json(silent=True) or {}
    requirements = body.get("requirements", [])
    candidate_profile = body.get("candidate_profile") or {}
    resume_id = body.get("resume_id")
    use_llm = body.get("use_llm", True)

    if not requirements:
        return jsonify({"error": "requirements list required"}), 400

    resume_text = ""
    if resume_id:
        resume_text = _get_resume_text(int(resume_id), user_id)

    # Build candidate profile if not provided
    if not candidate_profile:
        try:
            from normalizer import normalize_candidate as _normalize
            candidate_profile = _normalize(
                user_id=user_id,
                resume_text=resume_text,
            )
        except Exception as e:
            logger.warning("alignment: inline normalization failed: %s", e)

    try:
        from gap_classifier import classify_gaps as _classify, summarize_gaps
        gaps = _classify(
            requirements=requirements,
            candidate_profile=candidate_profile,
            resume_text=resume_text,
            use_llm=use_llm,
        )
        summary = summarize_gaps(gaps)
        return jsonify({"gaps": gaps, "summary": summary})
    except Exception as e:
        logger.error("alignment classify-gaps error: %s", e)
        return jsonify({"error": "Gap classification failed"}), 500


@alignment_bp.route("/api/alignment/score", methods=["POST"])
@require_auth
def score_alignment():
    """Score JD requirements against candidate profile using 7-dimension hybrid model.

    Request body:
      requirements       list — from parse-jd
      candidate_profile  dict — from normalize (optional; built on-the-fly if absent)
      resume_id          int  — resume to score against

    Response:
      { scores: [...], summary: {...} }
    """
    user_id = g.user_id

    body = request.get_json(silent=True) or {}
    requirements = body.get("requirements", [])
    candidate_profile = body.get("candidate_profile") or {}
    resume_id = body.get("resume_id")

    if not requirements:
        return jsonify({"error": "requirements list required"}), 400

    resume_text = ""
    if resume_id:
        resume_text = _get_resume_text(int(resume_id), user_id)

    if not candidate_profile:
        try:
            from normalizer import normalize_candidate as _normalize
            candidate_profile = _normalize(user_id=user_id, resume_text=resume_text)
        except Exception as e:
            logger.warning("alignment score: inline normalization failed: %s", e)

    try:
        from hybrid_scorer import build_alignment_summary, score_all_requirements
        scores = score_all_requirements(requirements, candidate_profile, resume_text)
        summary = build_alignment_summary(requirements, scores, [])
        return jsonify({"scores": scores, "summary": summary})
    except Exception as e:
        logger.error("alignment score error: %s", e)
        return jsonify({"error": "Scoring failed"}), 500


@alignment_bp.route("/api/alignment/analyze", methods=["POST"])
@require_auth
def full_analyze():
    """Full Phase A pipeline: normalize + parse JD + classify gaps.

    Request body:
      resume_id         int  — resume to analyze
      job_id            int  — (optional) job description ID
      job_text          str  — raw JD text (required if job_id not provided)
      target_job_title  str  — (optional) role title
      save_result       bool — persist result to DB, default True

    Response:
      {
        candidate_profile: {...},
        requirements: [...],
        gaps: [...],
        summary: {...},
        duration_ms: int
      }
    """
    user_id = g.user_id

    body = request.get_json(silent=True) or {}
    resume_id = body.get("resume_id")
    job_id = body.get("job_id")
    job_text = body.get("job_text", "").strip()
    target_job_title = body.get("target_job_title", "")
    save_result = body.get("save_result", True)

    if not resume_id:
        return jsonify({"error": "resume_id required"}), 400

    if not job_text and not job_id:
        return jsonify({"error": "job_text or job_id required"}), 400

    # Fetch job text from DB if job_id provided
    if not job_text and job_id:
        try:
            from models import get_db
            with get_db() as conn:
                row = conn.execute(
                    "SELECT description FROM job_descriptions WHERE id = ? AND user_id = ?",
                    (job_id, user_id),
                ).fetchone()
                if row:
                    job_text = row["description"] or ""
        except Exception as e:
            logger.warning("alignment: failed to fetch JD: %s", e)

    if not job_text or len(job_text) < 50:
        return jsonify({"error": "Could not retrieve valid job description text"}), 400

    t_start = time.time()
    resume_text = _get_resume_text(int(resume_id), user_id)
    if not resume_text:
        return jsonify({"error": "Resume not found or access denied"}), 404

    try:
        from gap_classifier import classify_gaps as _classify, summarize_gaps
        from hybrid_scorer import build_alignment_summary, score_all_requirements
        from jd_parser import parse_requirements
        from normalizer import normalize_candidate as _normalize

        # Step 1: Normalize candidate
        candidate_profile = _normalize(
            user_id=user_id,
            resume_text=resume_text,
            target_job_title=target_job_title,
        )

        # Step 2: Parse JD requirements
        requirements = parse_requirements(job_text)

        # Step 3: Hybrid scoring (Phase B)
        scores = score_all_requirements(requirements, candidate_profile, resume_text)

        # Step 4: Classify gaps
        gaps = _classify(
            requirements=requirements,
            candidate_profile=candidate_profile,
            resume_text=resume_text,
        )
        summary = build_alignment_summary(requirements, scores, gaps)
        gap_summary = summarize_gaps(gaps)

        result = {
            "candidate_profile": candidate_profile,
            "requirements": requirements,
            "scores": scores,
            "gaps": gaps,
            "summary": summary,
            "gap_summary": gap_summary,
            "duration_ms": int((time.time() - t_start) * 1000),
        }

        # Persist
        if save_result and job_id:
            _save_gap_analysis(user_id, int(resume_id), int(job_id), result)

        return jsonify(result)

    except Exception as e:
        logger.error("alignment full-analyze error: %s", e)
        return jsonify({"error": "Analysis pipeline failed"}), 500


@alignment_bp.route("/api/alignment/gaps/<int:resume_id>", methods=["GET"])
@require_auth
def get_gap_analysis(resume_id: int):
    """Retrieve last saved gap analysis for a resume.

    Query params:
      job_id  int  — (optional) filter by job description
    """
    user_id = g.user_id

    job_id = request.args.get("job_id", type=int)

    try:
        from models import get_db
        with get_db() as conn:
            if job_id:
                row = conn.execute(
                    "SELECT gaps_json, requirements_json, candidate_profile_json, "
                    "created_at FROM alignment_analyses "
                    "WHERE user_id = ? AND resume_id = ? AND job_id = ? "
                    "ORDER BY created_at DESC LIMIT 1",
                    (user_id, resume_id, job_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT gaps_json, requirements_json, candidate_profile_json, "
                    "created_at FROM alignment_analyses "
                    "WHERE user_id = ? AND resume_id = ? "
                    "ORDER BY created_at DESC LIMIT 1",
                    (user_id, resume_id),
                ).fetchone()

        if not row:
            return jsonify({"error": "No gap analysis found"}), 404

        gaps = json.loads(row["gaps_json"] or "[]")
        requirements = json.loads(row["requirements_json"] or "[]")
        scores_raw = row["scores_json"] if "scores_json" in row.keys() else "[]"
        scores = json.loads(scores_raw or "[]")

        return jsonify({
            "gaps": gaps,
            "requirements": requirements,
            "scores": scores,
            "candidate_profile": json.loads(row["candidate_profile_json"] or "{}"),
            "created_at": row["created_at"],
        })
    except Exception as e:
        logger.error("alignment get-gaps error: %s", e)
        return jsonify({"error": "Failed to retrieve gap analysis"}), 500


@alignment_bp.route("/api/alignment/artifacts", methods=["POST"])
@require_auth
def generate_artifacts_endpoint():
    """Generate output artifacts from an alignment analysis.

    Request JSON:
      resume_id (int, required)
      job_description_text (str, required)
      artifacts (list[str], optional) — subset of 7 artifact types to generate
    """
    user_id = g.user_id

    data = request.get_json(silent=True) or {}
    resume_id = data.get("resume_id")
    jd_text = data.get("job_text") or data.get("job_description_text", "")
    requested_artifacts = data.get("artifacts")

    if not resume_id:
        return jsonify({"error": "resume_id required"}), 400
    if not jd_text:
        return jsonify({"error": "job_text required"}), 400

    try:
        from artifact_generator import generate_artifacts, get_artifact_summary
        from gap_classifier import classify_gaps
        from hybrid_scorer import score_all_requirements
        from jd_parser import parse_requirements
        from normalizer import normalize_candidate
        from rewrite_planner import plan_rewrites
    except ImportError as e:
        return jsonify({"error": f"Pipeline module unavailable: {e}"}), 500

    resume_text = _get_resume_text(resume_id, user_id)
    if not resume_text:
        return jsonify({"error": "Resume not found or access denied"}), 404

    try:
        candidate_profile = normalize_candidate(resume_text)
        requirements = parse_requirements(jd_text)
        scores = score_all_requirements(requirements, candidate_profile, resume_text)
        gaps = classify_gaps(requirements, candidate_profile, resume_text)
        rewrite_targets = plan_rewrites(gaps, scores, candidate_profile, resume_text)

        artifacts = generate_artifacts(
            candidate_profile, requirements, scores, gaps,
            rewrite_targets, resume_text, requested_artifacts,
        )
        summary = get_artifact_summary(artifacts)

        return jsonify({
            "artifacts": artifacts,
            "summary": summary,
        })
    except Exception as e:
        logger.error("alignment artifacts error: %s", e)
        return jsonify({"error": "Artifact generation failed"}), 500
