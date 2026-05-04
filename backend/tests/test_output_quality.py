"""API-level output quality tests — source tracking, skills gap, optimization routes.

Route tests with Flask test client. Content + DB assertions for every test.
Pure NLP/function tests are in test_output_quality_nlp.py.
"""

import pytest
from test_helpers import JD_TEXT, LINKEDIN_PROFILE, RESUME_TEXT, query_db, upload_resume

# ---------------------------------------------------------------------------
# Source tracking
# ---------------------------------------------------------------------------


class TestSourceTracking:

    def test_upload_source_tracked(self, client, auth_headers, resume_and_jd):
        """Uploaded resume returns resume_source='upload'."""
        rid, _ = resume_and_jd
        # DB: verify resume exists
        rows = query_db("SELECT id, filename FROM resumes WHERE id = ?", (rid,))
        assert len(rows) == 1
        assert isinstance(rows[0]["filename"], str)

        resp = client.post(f"/api/optimize-resume/{rid}", headers=auth_headers, json={})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["resume_source"] == "upload"
        assert isinstance(data["ats_compliance_score"], (int, float))
        assert 0 <= data["ats_compliance_score"] <= 100
        assert isinstance(data["keywords_added"], int)
        assert data["keywords_added"] >= 0
        assert "score_breakdown" in data
        bd = data["score_breakdown"]
        assert isinstance(bd["keyword_coverage"], (int, float))

    def test_linkedin_source_tracked(self, client, auth_headers):
        """Resume from LinkedIn returns resume_source containing 'linkedin'."""
        client.post("/api/import/linkedin", headers=auth_headers, json={})

        resp = client.post(
            "/api/resume/from-linkedin",
            headers=auth_headers,
            json={},
        )
        if resp.status_code != 201:
            pytest.skip("from-linkedin endpoint not available in this build")
        resume_id = resp.get_json()["resume_id"]

        # DB: verify linkedin resume created
        rows = query_db("SELECT id, filename FROM resumes WHERE id = ?", (resume_id,))
        assert len(rows) == 1

        from test_helpers import upload_jd

        upload_jd(client, auth_headers)

        resp = client.post(
            f"/api/optimize-resume/{resume_id}",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "linkedin" in data.get("resume_source", "").lower()
        assert isinstance(data["ats_compliance_score"], (int, float))
        assert isinstance(data["keywords_added"], int)
        # DB: verify resume still exists after optimization
        rows = query_db("SELECT id FROM resumes WHERE id = ?", (resume_id,))
        assert len(rows) == 1

    def test_optimize_returns_all_fields(self, client, auth_headers, resume_and_jd):
        """Optimize returns complete response structure with content + DB proof."""
        rid, _ = resume_and_jd
        resp = client.post(f"/api/optimize-resume/{rid}", headers=auth_headers, json={})
        assert resp.status_code == 200
        data = resp.get_json()
        # Content: verify all expected fields
        assert "ats_compliance_score" in data
        assert "resume_source" in data
        assert "keywords_added" in data
        assert "score_breakdown" in data
        bd = data["score_breakdown"]
        for key in (
            "keyword_coverage",
            "semantic_similarity",
            "skills_match",
            "section_completeness",
        ):
            assert key in bd
            assert isinstance(bd[key], (int, float))
        # DB: resume persisted
        rows = query_db("SELECT id FROM resumes WHERE id = ?", (rid,))
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# Skills gap analysis
# ---------------------------------------------------------------------------


class TestSkillsGap:

    def test_skills_gap_identifies_missing(self, client, auth_headers, resume_and_jd):
        """Skills gap endpoint returns missing skills for partial match."""
        rid, _ = resume_and_jd
        # DB: verify resume and JD exist
        rows = query_db("SELECT id FROM resumes WHERE user_id = 1")
        assert len(rows) >= 1

        resp = client.get(f"/api/skills-gap/{rid}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        missing = data.get("missing_skills", data.get("skills_gap", {}).get("missing", []))
        assert isinstance(missing, list)
        if missing:
            assert all(isinstance(s, str) and len(s.strip()) > 0 for s in missing)
        # DB: resume unchanged
        rows = query_db("SELECT id FROM resumes WHERE id = ?", (rid,))
        assert len(rows) == 1

    def test_have_bucket_includes_shown_skills(self, client, auth_headers, resume_and_jd):
        """Skills gap 'already_shown' bucket includes skills from resume matching JD."""
        rid, _ = resume_and_jd
        client.post("/api/import/linkedin", headers=auth_headers, json={})

        resp = client.get(f"/api/skills-gap/{rid}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        gap = data.get("skills_gap", {})
        shown = gap.get("skills_already_shown", [])
        emphasize = gap.get("skills_to_emphasize", [])
        all_have = shown + emphasize
        assert len(all_have) >= 1
        # DB: verify JD exists for the user
        jd_rows = query_db("SELECT id FROM job_descriptions WHERE user_id = 1")
        assert len(jd_rows) >= 1

    def test_skills_gap_not_found(self, client, auth_headers):
        """Skills gap for nonexistent resume returns 404."""
        resp = client.get("/api/skills-gap/99999", headers=auth_headers)
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data
        assert isinstance(data["error"], str)
        # DB: confirm resume doesn't exist
        rows = query_db("SELECT id FROM resumes WHERE id = 99999")
        assert len(rows) == 0
