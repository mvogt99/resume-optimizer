"""Alignment audit + rewrite routes (Phase D, Items 10-11).

Endpoints:
  POST /api/alignment/audit-claims   — claim auditor (Item 10)
  POST /api/alignment/apply-rewrite  — apply a rewrite suggestion (Item 11)
"""

import logging

from flask import Blueprint, g, jsonify, request

from auth import require_auth

logger = logging.getLogger(__name__)

alignment_audit_bp = Blueprint("alignment_audit", __name__)


def _get_resume_text_audit(resume_id: int, user_id: int) -> str:
    """Fetch resume text for the given user from DB."""
    try:
        from models import get_db
        from utils import process_resume
        with get_db() as conn:
            row = conn.execute(
                "SELECT file_path FROM resumes WHERE id = ? AND user_id = ?",
                (resume_id, user_id),
            ).fetchone()
            if row and row["file_path"]:
                parsed = process_resume(row["file_path"])
                return parsed.get("text", "") or ""
            row = conn.execute(
                "SELECT parsed_text FROM resume_versions WHERE id = ? AND user_id = ?",
                (resume_id, user_id),
            ).fetchone()
            if row:
                return row["parsed_text"] or ""
    except Exception as e:
        logger.warning("alignment_audit: failed to fetch resume text: %s", e)
    return ""


# ---------------------------------------------------------------------------
# Item 10: POST /api/alignment/audit-claims
# ---------------------------------------------------------------------------


@alignment_audit_bp.route("/api/alignment/audit-claims", methods=["POST"])
@require_auth
def audit_claims_endpoint():
    """Audit resume claims against candidate profile evidence.

    Request JSON:
      resume_id  int  (required)
      job_text   str  (optional — used to build candidate profile context)
      use_llm    bool (default False — skip LLM for speed)

    Response:
      {
        audits:  list[claim_audit],
        summary: {total, supported_count, unsupported_count, high_risk_count, by_claim_type}
      }
    """
    user_id = g.user_id

    body = request.get_json(silent=True) or {}
    resume_id = body.get("resume_id")
    use_llm = bool(body.get("use_llm", False))

    if not resume_id:
        return jsonify({"error": "resume_id required"}), 400

    resume_text = _get_resume_text_audit(int(resume_id), user_id)
    if not resume_text:
        return jsonify({"error": "Resume not found or access denied"}), 404

    try:
        from claim_auditor import audit_claims, summarize_audit
        from normalizer import normalize_candidate

        candidate_profile = normalize_candidate(resume_text)
        audits = audit_claims(resume_text, candidate_profile, use_llm=use_llm)
        summary = summarize_audit(audits)

        return jsonify({"audits": audits, "summary": summary})

    except Exception as e:
        logger.error("alignment audit-claims error: %s", e)
        return jsonify({"error": "Claim audit failed"}), 500


# ---------------------------------------------------------------------------
# Item 11: POST /api/alignment/apply-rewrite
# ---------------------------------------------------------------------------


@alignment_audit_bp.route("/api/alignment/apply-rewrite", methods=["POST"])
@require_auth
def apply_rewrite_endpoint():
    """Generate specific rewrite suggestions for a resume section.

    Request JSON:
      resume_id     int   (required)
      target        dict  (required) — a rewrite_target from plan_rewrites
      job_text      str   (optional) — JD context

    Response:
      {
        target_id:        str,
        original_snippet: str,   — relevant sentence(s) from resume matching the gap
        suggested_text:   str,   — concrete rewrite suggestion
        diff_hint:        str,   — human-readable "replace X with Y" hint
      }
    """
    user_id = g.user_id

    body = request.get_json(silent=True) or {}
    resume_id = body.get("resume_id")
    target = body.get("target")
    job_text = body.get("job_text", "")

    if not resume_id:
        return jsonify({"error": "resume_id required"}), 400
    if not target or not isinstance(target, dict):
        return jsonify({"error": "target (rewrite_target dict) required"}), 400

    target_id = target.get("target_id", "")
    rewrite_template = target.get("rewrite_template", "")
    description = target.get("description") or target.get("gap_description", "")
    evidence_anchor = target.get("evidence_anchor", "")

    if not rewrite_template:
        return jsonify({"error": "target.rewrite_template required"}), 400

    resume_text = _get_resume_text_audit(int(resume_id), user_id)
    if not resume_text:
        return jsonify({"error": "Resume not found or access denied"}), 404

    try:
        original_snippet = _find_relevant_snippet(resume_text, evidence_anchor)
        suggested_text = _build_suggestion(rewrite_template, resume_text, description)
        diff_hint = _build_diff_hint(original_snippet, suggested_text)

        return jsonify({
            "target_id": target_id,
            "original_snippet": original_snippet,
            "suggested_text": suggested_text,
            "diff_hint": diff_hint,
        })

    except Exception as e:
        logger.error("alignment apply-rewrite error: %s", e)
        return jsonify({"error": "Apply rewrite failed"}), 500


def _find_relevant_snippet(resume_text: str, evidence_anchor: str) -> str:
    """Return the first resume line that contains any anchor keyword."""
    if not evidence_anchor:
        return ""
    keywords = [k.strip().lower() for k in evidence_anchor.split(";") if k.strip()]
    for line in resume_text.splitlines():
        if any(kw in line.lower() for kw in keywords):
            return line.strip()
    return ""


def _build_suggestion(rewrite_template: str, resume_text: str, description: str) -> str:
    """Produce a concrete suggestion by filling in template placeholders.

    Tries LLM first; falls back to a heuristic fill.
    """
    try:
        from llm_helper import call_llm_quality
        if call_llm_quality is None:
            raise ImportError("call_llm_quality unavailable")

        prompt = (
            "Given the resume below and the rewrite template, produce a single concrete "
            "resume bullet or sentence that fills in the template. "
            "Return ONLY the final text, no explanation.\n\n"
            f"Resume (excerpt):\n{resume_text[:2000]}\n\n"
            f"Template: {rewrite_template}\n"
            f"Gap context: {description}\n"
            "Output:"
        )
        raw = call_llm_quality(prompt, task_type="generation") or ""
        raw = raw.strip().strip('"').strip()
        if raw and len(raw) > 10:
            return raw
    except Exception:
        pass

    # Heuristic fallback: strip placeholder brackets and return template as-is
    import re
    return re.sub(r"\[.*?\]", "", rewrite_template).strip(" ,")


def _build_diff_hint(original: str, suggested: str) -> str:
    if not original:
        return f'Add: "{suggested}"'
    return f'Replace: "{original[:100]}"\nWith: "{suggested[:100]}"'
