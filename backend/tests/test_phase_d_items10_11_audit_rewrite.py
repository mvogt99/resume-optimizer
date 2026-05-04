"""Integration + unit tests for alignment audit and rewrite routes (Phase D, Items 10-11).

Items:
  10 — POST /api/alignment/audit-claims
  11 — POST /api/alignment/apply-rewrite

Mutation-verification targets:
  MA1: 401 when unauthenticated (audit-claims)
  MA2: 400 when resume_id missing (audit-claims)
  MA3: 404 when resume not found / wrong user (audit-claims)
  MR1: 401 when unauthenticated (apply-rewrite)
  MR2: 400 when resume_id missing (apply-rewrite)
  MR3: 400 when target missing (apply-rewrite)
  MR4: 404 when resume not found (apply-rewrite)
"""

import io
import json
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

_RESUME_TEXT = (
    "Jane Doe\nSoftware Engineer\n\n"
    "EXPERIENCE\nEngineer — Acme (2020-Present)\n"
    "- Built Python services processing 1M events/day.\n"
    "- Led cross-functional team of 8 engineers.\n\n"
    "SKILLS\nPython, AWS, Kafka"
)

_STUB_PROFILE = {
    "candidate_id": "test",
    "skill_inventory": [{"canonical_skill": "Python", "aliases": [], "evidence_refs": ["proj1"]}],
    "experience_units": [],
}

_STUB_AUDITS = [
    {
        "audit_id": "aud001",
        "claim_text": "Built Python services processing 1M events/day.",
        "claim_type": "quantified_metric",
        "is_supported": True,
        "evidence_refs": ["proj1"],
        "risk_level": "low",
        "confidence": 0.9,
        "suggested_revision": "Claim is well-supported — no revision needed.",
    },
    {
        "audit_id": "aud002",
        "claim_text": "Led cross-functional team of 8 engineers.",
        "claim_type": "role_scope",
        "is_supported": False,
        "evidence_refs": [],
        "risk_level": "high",
        "confidence": 0.1,
        "suggested_revision": "Verify this claim and add supporting evidence.",
    },
]

_STUB_AUDIT_SUMMARY = {
    "total": 2,
    "supported_count": 1,
    "unsupported_count": 1,
    "high_risk_count": 1,
    "by_claim_type": {"quantified_metric": 1, "role_scope": 1},
}

_STUB_REWRITE_TARGET = {
    "target_id": "tgt001",
    "gap_id": "gap_001",
    "requirement_id": "req_001",
    "priority": 1,
    "gap_type": "weak_wording",
    "suggested_action": "Rephrase Python usage with quantified outcomes.",
    "evidence_anchor": "Python",
    "rewrite_template": "[Role] at [Company], improved Python platform coverage.",
    "severity": "medium",
    "estimated_impact": 0.15,
}

_APPLY_REWRITE_URL = "/api/alignment/apply-rewrite"
_AUDIT_CLAIMS_URL = "/api/alignment/audit-claims"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _upload_resume(client, headers) -> int:
    data = {"file": (io.BytesIO(_RESUME_TEXT.encode()), "resume.txt")}
    resp = client.post(
        "/api/resume/upload",
        data=data,
        headers={k: v for k, v in headers.items() if k != "Content-Type"},
        content_type="multipart/form-data",
    )
    assert resp.status_code in (200, 201), f"Upload failed: {resp.get_data(as_text=True)}"
    return int(resp.get_json()["resume_id"])


# ---------------------------------------------------------------------------
# Tests: POST /api/alignment/audit-claims  (Item 10)
# ---------------------------------------------------------------------------


class TestAuditClaims:
    """Integration tests for POST /api/alignment/audit-claims."""

    def _post(self, client, headers, body):
        return client.post(_AUDIT_CLAIMS_URL, json=body, headers=headers)

    # MA1: auth guard
    def test_unauthenticated_returns_401(self, client):
        """No auth → 401 (MA1). Mutation: remove guard → 400/500."""
        resp = self._post(client, {}, {"resume_id": 1})
        assert resp.status_code == 401

    # MA2: resume_id required
    def test_missing_resume_id_returns_400(self, client, auth_headers):
        """No resume_id → 400 (MA2)."""
        resp = self._post(client, auth_headers, {})
        assert resp.status_code == 400
        assert "resume_id" in resp.get_json().get("error", "").lower()

    # MA3: resume existence guard
    def test_missing_resume_returns_404(self, client, auth_headers):
        """resume_id not in DB → 404 (MA3)."""
        resp = self._post(client, auth_headers, {"resume_id": 99999})
        assert resp.status_code == 404

    # Happy path: returns audits + summary
    def test_happy_path_returns_audits_and_summary(self, client, auth_headers):
        """Mocked pipeline → 200 with audits list and summary dict."""
        resume_id = _upload_resume(client, auth_headers)

        with patch("normalizer.normalize_candidate", return_value=_STUB_PROFILE), \
             patch("claim_auditor.audit_claims", return_value=_STUB_AUDITS), \
             patch("claim_auditor.summarize_audit", return_value=_STUB_AUDIT_SUMMARY):
            resp = self._post(client, auth_headers, {"resume_id": resume_id})

        assert resp.status_code == 200
        data = resp.get_json()
        assert "audits" in data
        assert "summary" in data
        assert isinstance(data["audits"], list)
        assert isinstance(data["summary"], dict)

    def test_happy_path_audits_have_required_keys(self, client, auth_headers):
        """Each audit has required fields."""
        resume_id = _upload_resume(client, auth_headers)

        with patch("normalizer.normalize_candidate", return_value=_STUB_PROFILE), \
             patch("claim_auditor.audit_claims", return_value=_STUB_AUDITS), \
             patch("claim_auditor.summarize_audit", return_value=_STUB_AUDIT_SUMMARY):
            resp = self._post(client, auth_headers, {"resume_id": resume_id})

        audits = resp.get_json()["audits"]
        required = {"audit_id", "claim_text", "claim_type", "is_supported",
                    "evidence_refs", "risk_level", "confidence", "suggested_revision"}
        for audit in audits:
            missing = required - audit.keys()
            assert not missing, f"Audit missing keys: {missing}"

    def test_summary_has_required_keys(self, client, auth_headers):
        """Summary has total, supported_count, unsupported_count, high_risk_count, by_claim_type."""
        resume_id = _upload_resume(client, auth_headers)

        with patch("normalizer.normalize_candidate", return_value=_STUB_PROFILE), \
             patch("claim_auditor.audit_claims", return_value=_STUB_AUDITS), \
             patch("claim_auditor.summarize_audit", return_value=_STUB_AUDIT_SUMMARY):
            resp = self._post(client, auth_headers, {"resume_id": resume_id})

        summary = resp.get_json()["summary"]
        for key in ("total", "supported_count", "unsupported_count", "high_risk_count", "by_claim_type"):
            assert key in summary, f"Summary missing key: {key}"

    def test_use_llm_false_is_default(self, client, auth_headers):
        """use_llm defaults to False — audit_claims called with use_llm=False."""
        resume_id = _upload_resume(client, auth_headers)

        with patch("normalizer.normalize_candidate", return_value=_STUB_PROFILE) as _, \
             patch("claim_auditor.audit_claims", return_value=[]) as mock_audit, \
             patch("claim_auditor.summarize_audit", return_value={"total": 0, "supported_count": 0,
                    "unsupported_count": 0, "high_risk_count": 0, "by_claim_type": {}}):
            self._post(client, auth_headers, {"resume_id": resume_id})
            call_kwargs = mock_audit.call_args
            # use_llm is the 3rd positional arg or kwarg
            assert call_kwargs is not None
            # Should be called with use_llm=False (default)
            use_llm_val = call_kwargs.kwargs.get("use_llm", True)
            if use_llm_val is True:
                # It might be positional
                args = call_kwargs.args
                use_llm_val = args[2] if len(args) > 2 else True
            assert use_llm_val is False, "use_llm should default to False"

    # MA3 cross-user variant
    def test_cross_user_cannot_audit_other_users_resume(
        self, client, auth_headers, second_user_headers
    ):
        """User2 gets 404 for user1's resume (MA3 cross-user)."""
        resume_id = _upload_resume(client, auth_headers)
        resp = self._post(client, second_user_headers, {"resume_id": resume_id})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests: POST /api/alignment/apply-rewrite  (Item 11)
# ---------------------------------------------------------------------------


class TestApplyRewrite:
    """Integration tests for POST /api/alignment/apply-rewrite."""

    def _post(self, client, headers, body):
        return client.post(_APPLY_REWRITE_URL, json=body, headers=headers)

    # MR1: auth guard
    def test_unauthenticated_returns_401(self, client):
        """No auth → 401 (MR1)."""
        resp = self._post(client, {}, {"resume_id": 1, "target": _STUB_REWRITE_TARGET})
        assert resp.status_code == 401

    # MR2: resume_id required
    def test_missing_resume_id_returns_400(self, client, auth_headers):
        """No resume_id → 400 (MR2)."""
        resp = self._post(client, auth_headers, {"target": _STUB_REWRITE_TARGET})
        assert resp.status_code == 400
        assert "resume_id" in resp.get_json().get("error", "").lower()

    # MR3: target required
    def test_missing_target_returns_400(self, client, auth_headers):
        """No target → 400 (MR3)."""
        resume_id = _upload_resume(client, auth_headers)
        resp = self._post(client, auth_headers, {"resume_id": resume_id})
        assert resp.status_code == 400
        assert "target" in resp.get_json().get("error", "").lower()

    def test_non_dict_target_returns_400(self, client, auth_headers):
        """target must be a dict → 400 (MR3 variant)."""
        resume_id = _upload_resume(client, auth_headers)
        resp = self._post(client, auth_headers, {"resume_id": resume_id, "target": "not-a-dict"})
        assert resp.status_code == 400

    def test_missing_rewrite_template_returns_400(self, client, auth_headers):
        """target without rewrite_template → 400."""
        resume_id = _upload_resume(client, auth_headers)
        resp = self._post(client, auth_headers, {
            "resume_id": resume_id,
            "target": {"target_id": "x", "gap_type": "weak_wording"},
        })
        assert resp.status_code == 400

    # MR4: resume existence guard
    def test_missing_resume_returns_404(self, client, auth_headers):
        """resume_id not in DB → 404 (MR4)."""
        resp = self._post(client, auth_headers, {
            "resume_id": 99999,
            "target": _STUB_REWRITE_TARGET,
        })
        assert resp.status_code == 404

    # Happy path: returns required keys
    def test_happy_path_returns_required_keys(self, client, auth_headers):
        """Valid request → 200 with target_id, original_snippet, suggested_text, diff_hint."""
        resume_id = _upload_resume(client, auth_headers)
        resp = self._post(client, auth_headers, {
            "resume_id": resume_id,
            "target": _STUB_REWRITE_TARGET,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        for key in ("target_id", "original_snippet", "suggested_text", "diff_hint"):
            assert key in data, f"Missing key: {key}"

    def test_happy_path_target_id_matches(self, client, auth_headers):
        """target_id in response matches target_id sent."""
        resume_id = _upload_resume(client, auth_headers)
        resp = self._post(client, auth_headers, {
            "resume_id": resume_id,
            "target": _STUB_REWRITE_TARGET,
        })
        assert resp.status_code == 200
        assert resp.get_json()["target_id"] == _STUB_REWRITE_TARGET["target_id"]

    def test_happy_path_suggested_text_is_nonempty(self, client, auth_headers):
        """suggested_text is a non-empty string."""
        resume_id = _upload_resume(client, auth_headers)
        resp = self._post(client, auth_headers, {
            "resume_id": resume_id,
            "target": _STUB_REWRITE_TARGET,
        })
        assert resp.status_code == 200
        assert len(resp.get_json()["suggested_text"]) > 0

    def test_happy_path_diff_hint_references_suggested_text(self, client, auth_headers):
        """diff_hint contains some part of suggested_text."""
        resume_id = _upload_resume(client, auth_headers)
        resp = self._post(client, auth_headers, {
            "resume_id": resume_id,
            "target": _STUB_REWRITE_TARGET,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        # diff_hint should reference suggested_text
        assert data["suggested_text"][:30] in data["diff_hint"] or \
               "Add:" in data["diff_hint"] or "Replace:" in data["diff_hint"]

    # MR4 cross-user variant
    def test_cross_user_cannot_apply_rewrite_to_other_resume(
        self, client, auth_headers, second_user_headers
    ):
        """User2 gets 404 for user1's resume (MR4 cross-user)."""
        resume_id = _upload_resume(client, auth_headers)
        resp = self._post(client, second_user_headers, {
            "resume_id": resume_id,
            "target": _STUB_REWRITE_TARGET,
        })
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Unit tests: _find_relevant_snippet, _build_suggestion, _build_diff_hint
# ---------------------------------------------------------------------------


class TestRewriteHelpers:
    """Unit tests for helper functions in alignment_audit_routes."""

    def test_find_relevant_snippet_matches_keyword(self):
        from routes.alignment_audit_routes import _find_relevant_snippet
        snippet = _find_relevant_snippet(
            "Led Python team.\nBuilt Kafka pipelines.", "Python"
        )
        assert "Python" in snippet

    def test_find_relevant_snippet_no_match_returns_empty(self):
        from routes.alignment_audit_routes import _find_relevant_snippet
        snippet = _find_relevant_snippet("Led Python team.", "Rust")
        assert snippet == ""

    def test_find_relevant_snippet_handles_semicolon_anchors(self):
        from routes.alignment_audit_routes import _find_relevant_snippet
        snippet = _find_relevant_snippet(
            "Led Python team.\nBuilt Kafka pipelines.", "Python; Kafka"
        )
        # Should find the first matching line
        assert len(snippet) > 0

    def test_build_diff_hint_no_original_starts_with_add(self):
        from routes.alignment_audit_routes import _build_diff_hint
        hint = _build_diff_hint("", "New bullet text")
        assert hint.startswith("Add:")

    def test_build_diff_hint_with_original_starts_with_replace(self):
        from routes.alignment_audit_routes import _build_diff_hint
        hint = _build_diff_hint("Old text here", "New improved text")
        assert hint.startswith("Replace:")

    def test_build_suggestion_fallback_strips_brackets(self):
        """When LLM unavailable, heuristic strips [placeholder] brackets."""
        from routes.alignment_audit_routes import _build_suggestion
        with patch("llm_helper.call_llm_quality", return_value=""):
            result = _build_suggestion(
                "[Role] at [Company], improved Python coverage.", "", ""
            )
        # Brackets should be removed in fallback
        assert "[Role]" not in result
        assert "[Company]" not in result
        assert "improved Python coverage" in result
