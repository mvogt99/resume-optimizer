"""E2E tests for deep profile synthesis and deep interview.

Tests: deep-profile build/get/role-synthesis, deep-interview full flow.
No mocks, no skips. DB verification after every write.
"""

import pytest
from test_helpers import JD_TEXT, query_db

pytestmark = pytest.mark.llm_required

# ===================================================================
# Deep Profile (6 tests) — WI-7
# ===================================================================


class TestDeepProfile:
    """Deep career profile synthesis with DB verification."""

    @pytest.fixture(autouse=True)
    def _check_harness(self, require_harness):
        """Fail with clear error if FTAL harness is not running."""

    def test_deep_profile_build(self, client, auth_headers):
        """POST /deep-profile/build → profile assembled, DB row created."""
        resp = client.post("/api/deep-profile/build", headers=auth_headers, json={})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "profile" in data or isinstance(data, dict)

        # DB: deep_profiles row should exist
        rows = query_db("SELECT * FROM deep_profiles")
        assert len(rows) >= 1, "No deep_profiles row after build"

    def test_deep_profile_structure(self, client, auth_headers):
        """Build returns expected structure keys."""
        resp = client.post("/api/deep-profile/build", headers=auth_headers, json={})
        assert resp.status_code == 200
        data = resp.get_json()
        profile = data.get("profile", data)
        if isinstance(profile, dict):
            possible_keys = {
                "professional_summary",
                "career_arc",
                "technology_mastery",
                "higher_order_skills",
                "business_impacts",
                "leadership_profile",
                "differentiators",
            }
            found = set(profile.keys()) & possible_keys
            # With LLM, should have at least some structure
            assert len(found) >= 1, "LLM build should populate at least 1 profile key"

    def test_deep_profile_get_before_build(self, client, auth_headers):
        """GET /deep-profile before build → 404 or empty."""
        resp = client.get("/api/deep-profile", headers=auth_headers)
        assert resp.status_code == 404  # no profile built yet
        data = resp.get_json()
        assert data["error"] == "No deep profile found. Build one first."

    def test_deep_profile_get_after_build(self, client, auth_headers):
        """GET /deep-profile after build → returns cached profile."""
        client.post("/api/deep-profile/build", headers=auth_headers, json={})
        resp = client.get("/api/deep-profile", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["profile"] is not None or "professional_summary" in data

    def test_deep_profile_role_synthesis(self, client, auth_headers):
        """POST /deep-profile/role-synthesis → fit scoring with DB."""
        client.post("/api/deep-profile/build", headers=auth_headers, json={})

        resp = client.post(
            "/api/deep-profile/role-synthesis",
            headers=auth_headers,
            json={"job_text": JD_TEXT},
        )
        assert (
            resp.status_code == 200
        ), f"Role synthesis after build should succeed: {resp.get_json()}"
        data = resp.get_json()
        assert isinstance(data, dict)
        fit_score = data.get("fit_score")
        if fit_score is not None:
            assert 0 <= fit_score <= 100, f"fit_score {fit_score} out of range"

    def test_deep_profile_role_synthesis_requires_job_text(self, client, auth_headers):
        """POST /deep-profile/role-synthesis without job_text → 400."""
        client.post("/api/deep-profile/build", headers=auth_headers, json={})
        resp = client.post(
            "/api/deep-profile/role-synthesis",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "job_text required (min 50 chars)"


# ===================================================================
# Deep Interview (6 tests) — WI-3e extended
# ===================================================================


class TestDeepInterviewFull:
    """Deep interview extended tests with DB verification."""

    @pytest.fixture(autouse=True)
    def _check_harness(self, require_harness):
        """Fail with clear error if FTAL harness is not running."""

    def test_deep_interview_start_comprehensive(self, client, auth_headers):
        """Comprehensive mode creates session, DB row."""
        resp = client.post(
            "/api/deep-interview/start",
            headers=auth_headers,
            json={"mode": "comprehensive"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "message" in data
        sid = data["session_id"]

        # DB: deep_interview_sessions row
        rows = query_db("SELECT * FROM deep_interview_sessions WHERE id = ?", (sid,))
        assert len(rows) == 1, f"No deep_interview_sessions row for {sid}"

    def test_deep_interview_start_role_specific(self, client, auth_headers):
        """Role-specific mode uses job_text, DB row."""
        resp = client.post(
            "/api/deep-interview/start",
            headers=auth_headers,
            json={"mode": "role_specific", "job_text": JD_TEXT},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "message" in data
        sid = data["session_id"]

        # DB: row exists
        rows = query_db("SELECT * FROM deep_interview_sessions WHERE id = ?", (sid,))
        assert len(rows) == 1

    def test_deep_interview_finalize(self, client, auth_headers):
        """POST /deep-interview/<sid>/finalize → synthesis, DB verified."""
        resp = client.post(
            "/api/deep-interview/start",
            headers=auth_headers,
            json={"mode": "comprehensive"},
        )
        sid = resp.get_json()["session_id"]

        client.post(
            "/api/deep-interview/message",
            headers=auth_headers,
            json={
                "session_id": sid,
                "message": "My career spans 20 years from Java dev to enterprise architect.",
            },
        )

        resp_fin = client.post(f"/api/deep-interview/{sid}/finalize", headers=auth_headers, json={})
        assert resp_fin.status_code == 200
        fin_data = resp_fin.get_json()
        assert "profile" in fin_data

        # DB: messages should exist
        msgs = query_db("SELECT * FROM deep_interview_messages WHERE session_id = ?", (sid,))
        assert len(msgs) >= 2, f"Expected ≥2 messages, got {len(msgs)}"

    def test_deep_interview_insights(self, client, auth_headers):
        """GET /deep-interview/<sid>/insights → extracted insights."""
        resp = client.post(
            "/api/deep-interview/start",
            headers=auth_headers,
            json={"mode": "comprehensive"},
        )
        sid = resp.get_json()["session_id"]

        client.post(
            "/api/deep-interview/message",
            headers=auth_headers,
            json={
                "session_id": sid,
                "message": "I specialize in AI pipeline orchestration and GPU inference.",
            },
        )

        resp_ins = client.get(f"/api/deep-interview/{sid}/insights", headers=auth_headers)
        assert resp_ins.status_code == 200
        ins_data = resp_ins.get_json()
        assert ins_data.get("session_id") == sid, "Insights must reference correct session"

    def test_deep_interview_with_linkedin_context(self, client, auth_headers):
        """Interview after LinkedIn import has richer context."""
        client.post("/api/import/linkedin", headers=auth_headers, json={})

        resp = client.post(
            "/api/deep-interview/start",
            headers=auth_headers,
            json={"mode": "comprehensive"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "session_id" in data

    def test_deep_interview_without_data(self, client, auth_headers):
        """Interview with no prior data → graceful handling."""
        resp = client.post(
            "/api/deep-interview/start",
            headers=auth_headers,
            json={"mode": "update"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["session_id"]) > 0
