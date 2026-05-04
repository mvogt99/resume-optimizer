"""Builder routes — sources, start, preview, interview, compile, edit, save."""

import json
import os
import uuid

import linkedin_cache
from auth import require_auth
from flask import Blueprint, current_app, g, jsonify, request
from models import Resume, ResumeVersion, get_db

builder_bp = Blueprint("builder", __name__)


@builder_bp.route("/api/builder/sources", methods=["GET"])
@require_auth
def builder_get_sources():
    from resume_builder import get_resume_builder

    builder = get_resume_builder()
    sources = builder.get_available_sources(g.user_id)

    # Fall back to get_profile() if get_raw() cache is stale/empty
    raw = linkedin_cache.get_raw(g.user_id) or linkedin_cache.get_profile(g.user_id)
    if not raw:
        # Last resort: read directly from DB and warm the cache
        with get_db() as conn:
            row = conn.execute(
                "SELECT profile_json, raw_json FROM linkedin_profiles WHERE user_id=?",
                (int(g.user_id),),
            ).fetchone()
            if row:
                profile_data = json.loads(row["profile_json"] or "{}")
                raw_data = json.loads(row["raw_json"] or "{}")
                if profile_data or raw_data:
                    linkedin_cache.set_profile(g.user_id, profile_data, raw_data or profile_data)
                    raw = raw_data or profile_data

    if raw:
        # Support both key naming conventions (archive format and parser format)
        skills = raw.get("skills_and_endorsements", raw.get("skills", []))
        exp = (
            raw.get("previous_jobs", [])
            + ([raw["current_job"]] if raw.get("current_job") else [])
            + raw.get("additional_positions", [])
            + raw.get("experience", [])
        )
        recs = raw.get("recommendations_received", raw.get("recommendations", []))
        sources["linkedin"]["available"] = True
        sources["linkedin"]["skills_count"] = len(skills)
        sources["linkedin"]["experience_count"] = len(exp)
        sources["linkedin"]["recommendations_count"] = len(recs)

    return jsonify(sources), 200


@builder_bp.route("/api/builder/start", methods=["POST"])
@require_auth
def builder_start():
    from resume_builder import get_resume_builder

    data = request.get_json() or {}
    base_version_id = data.get("base_version_id")
    job_text = data.get("job_text", "")
    selected_sources = data.get("sources", [])

    if not job_text or len(job_text) < 50:
        return jsonify({"error": "Job description must be at least 50 characters"}), 400

    builder = get_resume_builder()
    session_id = builder.create_session(g.user_id, base_version_id, job_text)
    builder.update_session(session_id, sources_json=json.dumps(selected_sources))

    return (
        jsonify(
            {
                "session_id": session_id,
                "status": "draft",
                "message": "Builder session created",
            }
        ),
        201,
    )


def _load_builder_sources(builder, session, user_id):
    """Load selected source data for a builder session."""
    selected = json.loads(session["sources_json"]) if session["sources_json"] != "{}" else []
    if isinstance(selected, dict):
        selected = list(selected.keys())

    sources_data = {}
    raw = linkedin_cache.get_raw(user_id)

    if "linkedin" in selected:
        sources_data["linkedin"] = builder.load_linkedin_profile(raw)
    if "projects" in selected:
        sources_data["projects"] = builder.load_project_insights()
    if "journey" in selected:
        sources_data["journey"] = builder.load_journey_data()
    if "experiences" in selected:
        sources_data["experiences"] = builder.load_experiences()

    return sources_data, selected


@builder_bp.route("/api/builder/preview/<session_id>", methods=["GET"])
@require_auth
def builder_preview(session_id):
    from nlp_engine import extract_skill_phrases
    from resume_builder import get_resume_builder
    from utils import optimize_resume as _opt

    builder = get_resume_builder()
    session = builder.get_session(session_id, user_id=g.user_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    sources_data, _ = _load_builder_sources(builder, session, g.user_id)
    base = builder.load_base_resume(session.get("base_version_id"))

    result = builder.build_enriched_resume(
        job_text=session["job_text"],
        base_text=base.get("text", ""),
        sources=sources_data,
    )

    enriched_data = {
        "text": result["text"],
        "skills": extract_skill_phrases(result["text"], use_llm_fallback=False),
    }
    job_kw = extract_skill_phrases(session["job_text"], use_llm_fallback=False)
    raw = linkedin_cache.get_raw(g.user_id)
    score_result = _opt(enriched_data, job_kw, job_text=session["job_text"], linkedin_profile=raw)

    return (
        jsonify(
            {
                "session_id": session_id,
                "text": result["text"],
                "sections": {
                    k: len(v) if isinstance(v, list) else 0 for k, v in result["sections"].items()
                },
                "sections_detail": result["sections"],
                "sources_used": result["sources_used"],
                "relevance_scores": result["relevance_scores"],
                "ats_score": score_result.get("score", 0),
                "score_breakdown": score_result.get("score_breakdown", {}),
            }
        ),
        200,
    )


@builder_bp.route("/api/builder/interview/start", methods=["POST"])
@require_auth
def builder_interview_start():
    from builder_interview import get_builder_interviewer
    from nlp_engine import extract_keywords
    from resume_builder import get_resume_builder
    from skills_optimizer import analyze_skills_gap

    data = request.get_json() or {}
    builder_session_id = data.get("session_id")
    if not builder_session_id:
        return jsonify({"error": "session_id required"}), 400

    builder = get_resume_builder()
    session = builder.get_session(builder_session_id, user_id=g.user_id)
    if not session:
        return jsonify({"error": "Builder session not found"}), 404

    job_text = session["job_text"]
    base = builder.load_base_resume(session.get("base_version_id"))
    resume_data = {
        "text": base.get("text", ""),
        "skills": extract_keywords(base.get("text", ""), 30),
    }

    raw = linkedin_cache.get_raw(g.user_id)
    gap_analysis = analyze_skills_gap(resume_data, job_text, raw)

    gaps = []
    for item in gap_analysis.get("skills_to_acquire", []):
        gaps.append({"skill": item["skill"], "category": "technical"})
    for item in gap_analysis.get("skills_to_emphasize", []):
        gaps.append({"skill": item["skill"], "category": "emphasize"})

    interviewer = get_builder_interviewer()
    result = interviewer.start_session(g.user_id, builder_session_id, job_text, gaps)

    builder.update_session(builder_session_id, status="interviewing")

    return jsonify(result), 201


@builder_bp.route("/api/builder/interview/message", methods=["POST"])
@require_auth
def builder_interview_message():
    from builder_interview import get_builder_interviewer

    data = request.get_json() or {}
    session_id = data.get("session_id")
    message = data.get("message", "").strip()

    if not session_id or not message:
        return jsonify({"error": "session_id and message required"}), 400

    interviewer = get_builder_interviewer()
    result = interviewer.process_message(session_id, message, user_id=g.user_id)

    if "error" in result:
        return jsonify(result), 404
    return jsonify(result), 200


@builder_bp.route("/api/builder/interview/status/<session_id>", methods=["GET"])
@require_auth
def builder_interview_status(session_id):
    from builder_interview import get_builder_interviewer

    interviewer = get_builder_interviewer()
    result = interviewer.get_extracted_content(session_id)

    if "error" in result:
        return jsonify(result), 404
    return jsonify(result), 200


@builder_bp.route("/api/builder/compile/<session_id>", methods=["POST"])
@require_auth
def builder_compile(session_id):
    from builder_interview import get_builder_interviewer
    from resume_builder import get_resume_builder

    builder = get_resume_builder()
    session = builder.get_session(session_id, user_id=g.user_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    data = request.get_json() or {}
    interview_session_id = data.get("interview_session_id")

    sources_data, _ = _load_builder_sources(builder, session, g.user_id)
    base = builder.load_base_resume(session.get("base_version_id"))

    interview_bullets = []
    if interview_session_id:
        interviewer = get_builder_interviewer()
        interview_data = interviewer.get_extracted_content(interview_session_id)
        if interview_data.get("bullets"):
            interview_bullets = interview_data["bullets"]

    try:
        from agentic_compiler import get_agentic_compiler

        compiler = get_agentic_compiler()
        result = compiler.compile_agentic(
            job_text=session["job_text"],
            base_text=base.get("text", ""),
            sources=sources_data,
            interview_bullets=interview_bullets,
        )
    except Exception:
        result = builder.build_enriched_resume(
            job_text=session["job_text"],
            base_text=base.get("text", ""),
            sources=sources_data,
        )
        result["compilation_method"] = "mechanical_fallback"
        if interview_bullets:
            compiled = result["text"]
            compiled += "\n\nADDITIONAL EXPERIENCE (from interview):"
            for bullet in interview_bullets:
                compiled += f"\n- {bullet['text']}"
            result["text"] = compiled

    compiled_text = result["text"]
    builder.update_session(session_id, compiled_text=compiled_text, status="compiled")

    return (
        jsonify(
            {
                "session_id": session_id,
                "compiled_text": compiled_text,
                "sources_used": result.get("sources_used", []),
                "compilation_method": result.get("compilation_method", "agentic"),
                "ats_score": result.get("ats_score", 0),
                "weaknesses": result.get("weaknesses", []),
                "missing_keywords": result.get("missing_keywords", []),
                "status": "compiled",
            }
        ),
        200,
    )


@builder_bp.route("/api/builder/edit/<session_id>", methods=["PUT"])
@require_auth
def builder_edit(session_id):
    from nlp_engine import extract_skill_phrases
    from resume_builder import get_resume_builder
    from utils import optimize_resume as _opt

    builder = get_resume_builder()
    session = builder.get_session(session_id, user_id=g.user_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    data = request.get_json() or {}
    new_text = data.get("text", "")
    if not new_text:
        return jsonify({"error": "text required"}), 400

    builder.update_session(session_id, compiled_text=new_text)

    enriched_data = {
        "text": new_text,
        "skills": extract_skill_phrases(new_text, use_llm_fallback=False),
    }
    job_kw = extract_skill_phrases(session["job_text"], use_llm_fallback=False)
    raw = linkedin_cache.get_raw(g.user_id)
    score_result = _opt(enriched_data, job_kw, job_text=session["job_text"], linkedin_profile=raw)

    return (
        jsonify(
            {
                "session_id": session_id,
                "ats_score": score_result.get("score", 0),
                "score_breakdown": score_result.get("score_breakdown", {}),
                "status": "compiled",
            }
        ),
        200,
    )


@builder_bp.route("/api/builder/save/<session_id>", methods=["POST"])
@require_auth
def builder_save(session_id):
    from resume_builder import get_resume_builder

    builder = get_resume_builder()
    session = builder.get_session(session_id, user_id=g.user_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    compiled_text = session.get("compiled_text", "")
    if not compiled_text:
        return jsonify({"error": "No compiled text — compile first"}), 400

    version = ResumeVersion.create(
        user_id=g.user_id,
        source="builder",
        file_name=f"Builder Resume {session_id[:8]}",
        parsed_text=compiled_text,
        source_id=session_id,
        metadata_json=json.dumps(
            {
                "sources": json.loads(session["sources_json"]) if session["sources_json"] else [],
                "job_text_preview": session["job_text"][:200],
            }
        ),
    )

    filename = f"{uuid.uuid4()}_builder_resume.txt"
    file_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(compiled_text)

    resume = Resume.create(g.user_id, f"Builder Resume {session_id[:8]}", file_path)

    builder.update_session(session_id, status="saved")

    return (
        jsonify(
            {
                "session_id": session_id,
                "version_id": version.id,
                "resume_id": resume.id,
                "status": "saved",
                "message": "Resume saved as new version",
            }
        ),
        201,
    )


@builder_bp.route("/api/builder/import-experience/<int:experience_id>", methods=["POST"])
@require_auth
def builder_import_experience(experience_id):
    """Import a finalized experience extraction into a builder session.

    Creates a new builder session pre-populated with the experience's structured
    data (title, employer, client, bullet points, technologies). If a job_text
    is provided in the request body, the session is ready for compilation.
    """
    from resume_builder import get_resume_builder

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM extracted_experiences WHERE id = ? AND user_id = ?",
            (experience_id, g.user_id),
        ).fetchone()

    if not row:
        return jsonify({"error": "Experience not found"}), 404

    exp = dict(row)
    for jfield in (
        "responsibilities",
        "technologies",
        "accomplishments",
        "challenges",
        "bullet_points",
    ):
        if isinstance(exp.get(jfield), str):
            try:
                exp[jfield] = json.loads(exp[jfield])
            except (json.JSONDecodeError, TypeError):
                exp[jfield] = []

    # Build structured resume text from experience data
    lines = []
    title = exp.get("title", "")
    employer = exp.get("employer", "")
    client = exp.get("client", "")

    header = title
    if employer:
        header += f" | {employer}"
    if client:
        header += f" ({client})"
    lines.append(header)
    lines.append("")

    if exp.get("bullet_points"):
        for bp in exp["bullet_points"]:
            lines.append(f"- {bp}")
        lines.append("")

    if exp.get("technologies"):
        lines.append("Technologies: " + ", ".join(exp["technologies"]))
        lines.append("")

    if exp.get("responsibilities"):
        lines.append("Responsibilities:")
        for r in exp["responsibilities"]:
            lines.append(f"- {r}")
        lines.append("")

    compiled_text = "\n".join(lines)

    # Create builder session with this content
    data = request.get_json() or {}
    job_text = data.get("job_text", "")

    builder = get_resume_builder()
    session_id = builder.create_session(g.user_id, job_text=job_text)
    builder.update_session(
        session_id,
        compiled_text=compiled_text,
        sources_json=json.dumps(["experiences"]),
        status="imported",
    )

    return (
        jsonify(
            {
                "session_id": session_id,
                "experience_id": experience_id,
                "employer": employer,
                "title": title,
                "text_length": len(compiled_text),
                "bullet_count": len(exp.get("bullet_points", [])),
                "status": "imported",
                "message": f"Experience '{title} @ {employer}' imported to builder",
            }
        ),
        201,
    )
