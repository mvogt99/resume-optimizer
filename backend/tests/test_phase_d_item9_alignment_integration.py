"""Integration tests for alignment pipeline routes (Phase D, Item 9).

Covers POST /api/alignment/analyze, POST /api/alignment/artifacts,
GET /api/alignment/gaps/<resume_id>.

All pipeline modules are patched at their SOURCE module so lazy imports
inside route handlers pick up the mock (routes import from gap_classifier, etc.).

Mutation-verification targets (each guard has a test that fails when broken):
  MG1: 401 when no auth (user_id None guard in _get_user_id)
  MG2: 400 when job_text missing from /analyze
  MG3: 404 when resume_id not in DB (or wrong user) for /analyze
  MG4: 400 when job_text missing from /artifacts
  MG5: 404 when resume_id not in DB for /artifacts
  MG6: 401 when no auth for /gaps GET
  MG7: 404 when no saved analysis exists for /gaps GET
  MG8: cross-user isolation — user2 gets 404 for user1's resume/analysis
"""

import io
import json
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub data returned by mocked pipeline functions
# ---------------------------------------------------------------------------

_STUB_PROFILE = {
    "candidate_id": "test",
    "skill_inventory": [{"canonical_skill": "Python", "aliases": [], "evidence_refs": []}],
    "experience_units": [],
}

_STUB_REQUIREMENTS = [
    {
        "requirement_id": "req_001",
        "text": "Python development skills (5+ years)",
        "importance": 0.9,
        "requirement_type": "technical",
    }
]

_STUB_SCORES = [
    {
        "requirement_id": "req_001",
        "composite_score": 0.65,
        "match_type": "partial",
        "dimension_scores": {},
    }
]

_STUB_GAPS = [
    {
        "gap_id": "gap_001",
        "requirement_id": "req_001",
        "gap_type": "weak_wording",
        "severity": "medium",
        "description": "Python appears without strong context.",
        "recommended_action": "Add Python depth with quantified results.",
    }
]

_STUB_SUMMARY = {
    "overall_score": 0.65,
    "match_distribution": {"partial": 1},
}

_STUB_GAP_SUMMARY = {"total": 1, "high_priority_count": 0}

_STUB_TARGETS = [
    {
        "target_id": "abc123",
        "gap_id": "gap_001",
        "requirement_id": "req_001",
        "priority": 1,
        "gap_type": "weak_wording",
        "suggested_action": "Rephrase with quantified outcomes.",
        "evidence_anchor": "Python",
        "rewrite_template": "[Role] at [Company], improved Python coverage.",
        "severity": "medium",
        "estimated_impact": 0.15,
    }
]

_STUB_ARTIFACTS = {
    "tailored_resume": {"content": "Rewritten resume.", "word_count": 2, "error": None},
    "cover_letter": {"content": "Dear Hiring Manager...", "word_count": 3, "error": None},
}

_STUB_ARTIFACT_SUMMARY = {
    "total": 7, "generated_count": 2, "failed_count": 5, "total_word_count": 5,
}

# ---------------------------------------------------------------------------
# Test content
# ---------------------------------------------------------------------------

_RESUME_TEXT = (
    "Jane Doe\nSoftware Engineer\n\n"
    "EXPERIENCE\nEngineer — Acme (2020-Present)\n- Built Python services.\n\n"
    "SKILLS\nPython, AWS"
)

_JD_TEXT = (
    "Senior Software Engineer role requiring Python development, AWS experience, "
    "and strong communication skills. Candidate must have 5+ years of experience "
    "building scalable backend services."
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _upload_resume(client, headers) -> int:
    """Upload a text resume via the API and return resume_id."""
    data = {"file": (io.BytesIO(_RESUME_TEXT.encode()), "resume.txt")}
    resp = client.post(
        "/api/resume/upload",
        data=data,
        headers={k: v for k, v in headers.items() if k != "Content-Type"},
        content_type="multipart/form-data",
    )
    assert resp.status_code in (200, 201), f"Upload failed {resp.status_code}: {resp.get_data(as_text=True)}"
    return int(resp.get_json()["resume_id"])


def _get_user_id_from_headers(client, headers) -> int:
    """Re-login with test credentials and return user_id from response."""
    resp = client.post(
        "/api/login",
        json={"email": "test@test.com", "password": "Test1234!"},
        headers={"Content-Type": "application/json"},
    )
    data = resp.get_json() or {}
    return data.get("user_id") or 1


# ---------------------------------------------------------------------------
# Patch context for full_analyze pipeline
# Source-level patches — work with lazy `from X import Y` inside functions
# ---------------------------------------------------------------------------

_ANALYZE_PATCHES = [
    ("normalizer.normalize_candidate", _STUB_PROFILE),
    ("jd_parser.parse_requirements", _STUB_REQUIREMENTS),
    ("hybrid_scorer.score_all_requirements", _STUB_SCORES),
    ("hybrid_scorer.build_alignment_summary", _STUB_SUMMARY),
    ("gap_classifier.classify_gaps", _STUB_GAPS),
    ("gap_classifier.summarize_gaps", _STUB_GAP_SUMMARY),
]

_ARTIFACTS_PATCHES = _ANALYZE_PATCHES[:3] + [
    ("gap_classifier.classify_gaps", _STUB_GAPS),
    ("rewrite_planner.plan_rewrites", _STUB_TARGETS),
    ("artifact_generator.generate_artifacts", _STUB_ARTIFACTS),
    ("artifact_generator.get_artifact_summary", _STUB_ARTIFACT_SUMMARY),
]


class _PatchStack:
    """Context manager that activates a list of (target, return_value) patches."""

    def __init__(self, patches):
        self._patches = [patch(target, return_value=rv) for target, rv in patches]

    def __enter__(self):
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self._patches):
            p.stop()


# ---------------------------------------------------------------------------
# Tests: POST /api/alignment/analyze
# ---------------------------------------------------------------------------


class TestAlignmentAnalyze:
    """Integration tests for POST /api/alignment/analyze."""

    URL = "/api/alignment/analyze"

    def _post(self, client, headers, body):
        return client.post(self.URL, json=body, headers=headers)

    # ---- MG1: auth guard ----

    def test_unauthenticated_returns_401(self, client):
        """No auth → 401. Mutation: remove user_id None check → would return 400/500."""
        resp = self._post(client, {}, {"resume_id": 1, "job_text": _JD_TEXT})
        assert resp.status_code == 401

    # ---- MG2: job_text guard ----

    def test_missing_job_text_returns_400(self, client, auth_headers):
        """No job_text → 400. Mutation: remove guard → 404/500 with empty text."""
        resume_id = _upload_resume(client, auth_headers)
        resp = self._post(client, auth_headers, {"resume_id": resume_id})
        assert resp.status_code == 400
        error = resp.get_json().get("error", "").lower()
        assert "job_text" in error or "job_id" in error

    # ---- MG3: resume existence guard ----

    def test_missing_resume_returns_404(self, client, auth_headers):
        """resume_id not in DB → 404. Mutation: remove guard → pipeline runs with empty text."""
        resp = self._post(
            client, auth_headers, {"resume_id": 99999, "job_text": _JD_TEXT}
        )
        assert resp.status_code == 404

    def test_missing_resume_id_returns_400(self, client, auth_headers):
        """No resume_id in body → 400."""
        resp = self._post(client, auth_headers, {"job_text": _JD_TEXT})
        assert resp.status_code == 400

    # ---- MG3 variant: short job_text guard ----

    def test_short_job_text_returns_400(self, client, auth_headers):
        """job_text < 50 chars → 400."""
        resume_id = _upload_resume(client, auth_headers)
        resp = self._post(client, auth_headers, {"resume_id": resume_id, "job_text": "too short"})
        assert resp.status_code == 400

    # ---- Happy path ----

    def test_happy_path_returns_required_keys(self, client, auth_headers):
        """Mocked pipeline → 200 with all required response keys."""
        resume_id = _upload_resume(client, auth_headers)

        with _PatchStack(_ANALYZE_PATCHES):
            resp = self._post(
                client, auth_headers,
                {"resume_id": resume_id, "job_text": _JD_TEXT, "save_result": False},
            )

        assert resp.status_code == 200
        data = resp.get_json()
        required = {"candidate_profile", "requirements", "scores", "gaps", "summary", "gap_summary", "duration_ms"}
        missing = required - data.keys()
        assert not missing, f"Missing keys in response: {missing}"

    def test_happy_path_gaps_is_list(self, client, auth_headers):
        """gaps field is a list."""
        resume_id = _upload_resume(client, auth_headers)
        with _PatchStack(_ANALYZE_PATCHES):
            resp = self._post(
                client, auth_headers,
                {"resume_id": resume_id, "job_text": _JD_TEXT, "save_result": False},
            )
        assert isinstance(resp.get_json()["gaps"], list)

    def test_happy_path_duration_ms_is_positive_int(self, client, auth_headers):
        """duration_ms is a positive integer."""
        resume_id = _upload_resume(client, auth_headers)
        with _PatchStack(_ANALYZE_PATCHES):
            resp = self._post(
                client, auth_headers,
                {"resume_id": resume_id, "job_text": _JD_TEXT, "save_result": False},
            )
        dur = resp.get_json()["duration_ms"]
        assert isinstance(dur, int) and dur >= 0

    # ---- MG8: cross-user isolation ----

    def test_cross_user_cannot_analyze_other_users_resume(
        self, client, auth_headers, second_user_headers
    ):
        """User2 gets 404 when analyzing user1's resume_id (MG8)."""
        resume_id = _upload_resume(client, auth_headers)  # owned by user1
        resp = self._post(
            client, second_user_headers,
            {"resume_id": resume_id, "job_text": _JD_TEXT},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests: POST /api/alignment/artifacts
# ---------------------------------------------------------------------------


class TestAlignmentArtifacts:
    """Integration tests for POST /api/alignment/artifacts."""

    URL = "/api/alignment/artifacts"

    def _post(self, client, headers, body):
        return client.post(self.URL, json=body, headers=headers)

    # ---- MG1 (artifacts): auth guard ----

    def test_unauthenticated_returns_401(self, client):
        """No auth → 401 (MG1 for artifacts)."""
        resp = self._post(client, {}, {"resume_id": 1, "job_text": _JD_TEXT})
        assert resp.status_code == 401

    # ---- MG4: job_text guard ----

    def test_missing_job_text_returns_400(self, client, auth_headers):
        """No job_text → 400 (MG4)."""
        resume_id = _upload_resume(client, auth_headers)
        resp = self._post(client, auth_headers, {"resume_id": resume_id})
        assert resp.status_code == 400

    # ---- MG5: resume existence guard ----

    def test_missing_resume_returns_404(self, client, auth_headers):
        """resume_id not in DB → 404 (MG5)."""
        resp = self._post(client, auth_headers, {"resume_id": 99999, "job_text": _JD_TEXT})
        assert resp.status_code == 404

    def test_missing_resume_id_returns_400(self, client, auth_headers):
        """No resume_id → 400."""
        resp = self._post(client, auth_headers, {"job_text": _JD_TEXT})
        assert resp.status_code == 400

    # ---- Happy path ----

    def test_happy_path_returns_artifacts_and_summary(self, client, auth_headers):
        """Mocked pipeline → 200 with artifacts dict and summary."""
        resume_id = _upload_resume(client, auth_headers)
        with _PatchStack(_ARTIFACTS_PATCHES):
            resp = self._post(
                client, auth_headers,
                {"resume_id": resume_id, "job_text": _JD_TEXT},
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "artifacts" in data and "summary" in data
        assert isinstance(data["artifacts"], dict)
        assert isinstance(data["summary"], dict)

    def test_happy_path_artifacts_has_at_least_one_document(self, client, auth_headers):
        """Artifacts dict is non-empty."""
        resume_id = _upload_resume(client, auth_headers)
        with _PatchStack(_ARTIFACTS_PATCHES):
            resp = self._post(
                client, auth_headers,
                {"resume_id": resume_id, "job_text": _JD_TEXT},
            )
        assert len(resp.get_json()["artifacts"]) > 0

    def test_artifact_subset_parameter_accepted(self, client, auth_headers):
        """artifacts=[tailored_resume] is accepted and doesn't cause error."""
        resume_id = _upload_resume(client, auth_headers)
        with _PatchStack(_ARTIFACTS_PATCHES):
            resp = self._post(
                client, auth_headers,
                {"resume_id": resume_id, "job_text": _JD_TEXT, "artifacts": ["tailored_resume"]},
            )
        assert resp.status_code == 200

    # ---- MG8: cross-user isolation ----

    def test_cross_user_cannot_generate_artifacts_for_other_resume(
        self, client, auth_headers, second_user_headers
    ):
        """User2 gets 404 for user1's resume_id (MG8 artifacts)."""
        resume_id = _upload_resume(client, auth_headers)
        resp = self._post(
            client, second_user_headers,
            {"resume_id": resume_id, "job_text": _JD_TEXT},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests: GET /api/alignment/gaps/<resume_id>
# ---------------------------------------------------------------------------


class TestGetGapAnalysis:
    """Integration tests for GET /api/alignment/gaps/<resume_id>."""

    def _get(self, client, headers, resume_id, **qs):
        url = f"/api/alignment/gaps/{resume_id}"
        if qs:
            url += "?" + "&".join(f"{k}={v}" for k, v in qs.items())
        return client.get(url, headers=headers)

    def _seed_analysis(self, client, auth_headers, resume_id):
        """Insert a pre-built gap analysis record, return user_id used."""
        from models import get_db

        login = client.post(
            "/api/login", json={"email": "test@test.com", "password": "Test1234!"},
            headers={"Content-Type": "application/json"},
        )
        user_id = (login.get_json() or {}).get("user_id") or 1

        with get_db() as conn:
            conn.execute(
                "INSERT INTO alignment_analyses "
                "(user_id, resume_id, job_id, gaps_json, requirements_json, "
                "candidate_profile_json, scores_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                (
                    user_id, resume_id, 0,
                    json.dumps(_STUB_GAPS),
                    json.dumps(_STUB_REQUIREMENTS),
                    json.dumps(_STUB_PROFILE),
                    json.dumps(_STUB_SCORES),
                ),
            )
            conn.commit()
        return user_id

    # ---- MG6: auth guard ----

    def test_unauthenticated_returns_401(self, client):
        """No auth → 401 (MG6)."""
        resp = self._get(client, {}, 1)
        assert resp.status_code == 401

    # ---- MG7: no-analysis guard ----

    def test_no_saved_analysis_returns_404(self, client, auth_headers):
        """No prior analysis in DB → 404 (MG7)."""
        resume_id = _upload_resume(client, auth_headers)
        resp = self._get(client, auth_headers, resume_id)
        assert resp.status_code == 404

    # ---- Happy path ----

    def test_retrieves_saved_analysis_gaps(self, client, auth_headers):
        """Seeded analysis is returned with correct gaps (MG7 inverse)."""
        resume_id = _upload_resume(client, auth_headers)
        self._seed_analysis(client, auth_headers, resume_id)

        resp = self._get(client, auth_headers, resume_id)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["gaps"][0]["gap_id"] == "gap_001"

    def test_retrieves_saved_analysis_has_required_keys(self, client, auth_headers):
        """Response has gaps, requirements, scores, candidate_profile, created_at."""
        resume_id = _upload_resume(client, auth_headers)
        self._seed_analysis(client, auth_headers, resume_id)

        resp = self._get(client, auth_headers, resume_id)
        assert resp.status_code == 200
        data = resp.get_json()
        for key in ("gaps", "requirements", "scores", "candidate_profile", "created_at"):
            assert key in data, f"Missing key: {key}"

    def test_job_id_filter_returns_404_when_no_match(self, client, auth_headers):
        """job_id=99999 filter → 404 when no match."""
        resume_id = _upload_resume(client, auth_headers)
        self._seed_analysis(client, auth_headers, resume_id)
        resp = self._get(client, auth_headers, resume_id, job_id=99999)
        assert resp.status_code == 404

    # ---- MG8: cross-user isolation ----

    def test_cross_user_cannot_retrieve_other_users_analysis(
        self, client, auth_headers, second_user_headers
    ):
        """User2 gets 404 for user1's saved analysis (MG8 for GET)."""
        resume_id = _upload_resume(client, auth_headers)
        self._seed_analysis(client, auth_headers, resume_id)
        # User2 queries the same resume_id — their user_id doesn't match
        resp = self._get(client, second_user_headers, resume_id)
        assert resp.status_code == 404
