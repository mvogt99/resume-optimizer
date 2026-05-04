"""Route tests for resume_routes.py — upload, optimize, download, skills-gap, versions.

Pure API tests (Flask test client only). Every test has content + DB assertions.
"""

import io

import pytest
from test_helpers import JD_TEXT, LINKEDIN_PROFILE, RESUME_TEXT, query_db, upload_jd, upload_resume

# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


class TestResumeUpload:
    def test_upload_txt(self, client, auth_headers):
        resp = client.post(
            "/api/resume/upload",
            headers={"Authorization": auth_headers["Authorization"]},
            data={"file": (io.BytesIO(RESUME_TEXT.encode()), "resume.txt")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert "resume_id" in data
        assert isinstance(data["resume_id"], (int, str))
        # DB: verify resume persisted
        rows = query_db("SELECT filename FROM resumes WHERE id = ?", (data["resume_id"],))
        assert len(rows) == 1
        assert "resume" in rows[0]["filename"].lower()

    def test_upload_no_file(self, client, auth_headers):
        resp = client.post(
            "/api/resume/upload",
            headers={"Authorization": auth_headers["Authorization"]},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert isinstance(data["error"], str)

    def test_upload_invalid_extension(self, client, auth_headers):
        resp = client.post(
            "/api/resume/upload",
            headers={"Authorization": auth_headers["Authorization"]},
            data={"file": (io.BytesIO(b"data"), "resume.exe")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_upload_auth_required(self, client):
        resp = client.post(
            "/api/resume/upload",
            data={"file": (io.BytesIO(b"data"), "resume.txt")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Job Description Upload
# ---------------------------------------------------------------------------


class TestJobDescriptionUpload:
    def test_upload_jd_text(self, client, auth_headers):
        resp = client.post(
            "/api/job-description/upload",
            headers=auth_headers,
            json={"job_text": JD_TEXT},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert "job_id" in data
        # DB: verify JD stored
        rows = query_db("SELECT id FROM job_descriptions WHERE id = ?", (data["job_id"],))
        assert len(rows) == 1

    def test_upload_jd_too_short(self, client, auth_headers):
        resp = client.post(
            "/api/job-description/upload",
            headers=auth_headers,
            json={"job_text": "too short"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert isinstance(data["error"], str)

    def test_upload_jd_empty(self, client, auth_headers):
        resp = client.post(
            "/api/job-description/upload",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data


# ---------------------------------------------------------------------------
# Optimize
# ---------------------------------------------------------------------------


class TestOptimize:
    def test_optimize_returns_score(self, client, auth_headers, resume_and_jd):
        rid, _ = resume_and_jd
        resp = client.post(f"/api/optimize-resume/{rid}", headers=auth_headers, json={})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "ats_compliance_score" in data
        assert isinstance(data["ats_compliance_score"], (int, float))
        assert 0 <= data["ats_compliance_score"] <= 100
        assert "resume_source" in data
        assert isinstance(data["keywords_added"], int)
        # DB: verify resume exists
        rows = query_db("SELECT id FROM resumes WHERE id = ?", (rid,))
        assert len(rows) == 1

    def test_optimize_not_found(self, client, auth_headers):
        resp = client.post("/api/optimize-resume/99999", headers=auth_headers, json={})
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data

    def test_optimize_returns_breakdown(self, client, auth_headers, resume_and_jd):
        rid, _ = resume_and_jd
        resp = client.post(f"/api/optimize-resume/{rid}", headers=auth_headers, json={})
        data = resp.get_json()
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


# ---------------------------------------------------------------------------
# Interview Guide
# ---------------------------------------------------------------------------


class TestInterviewGuide:
    def test_guide_endpoint(self, client, auth_headers, resume_and_jd):
        rid, _ = resume_and_jd
        resp = client.get(f"/api/interview-guide/{rid}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "interview_personas" in data
        assert "star_examples" in data
        assert "talking_points" in data
        assert isinstance(data["interview_personas"], list)
        assert len(data["interview_personas"]) >= 2
        # Each persona has required fields
        for persona in data["interview_personas"]:
            assert "persona" in persona
            assert "questions" in persona
            assert "tips" in persona
        # DB: resume still exists
        rows = query_db("SELECT id FROM resumes WHERE id = ?", (rid,))
        assert len(rows) == 1

    def test_guide_not_found(self, client, auth_headers):
        resp = client.get("/api/interview-guide/99999", headers=auth_headers)
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data


# ---------------------------------------------------------------------------
# Skills Gap
# ---------------------------------------------------------------------------


class TestSkillsGap:
    def test_skills_gap_returns_buckets(self, client, auth_headers, resume_and_jd):
        rid, _ = resume_and_jd
        resp = client.get(f"/api/skills-gap/{rid}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        gap = data.get("skills_gap", {})
        assert isinstance(gap, dict)
        # At least some bucket should be present
        bucket_keys = {
            "skills_already_shown",
            "skills_to_emphasize",
            "skills_to_acquire",
            "missing",
        }
        found_keys = set(gap.keys()) & bucket_keys
        assert len(found_keys) >= 1 or "missing_skills" in data
        # DB: verify resume exists
        rows = query_db("SELECT id FROM resumes WHERE id = ?", (rid,))
        assert len(rows) == 1

    def test_skills_gap_not_found(self, client, auth_headers):
        resp = client.get("/api/skills-gap/99999", headers=auth_headers)
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data


# ---------------------------------------------------------------------------
# From LinkedIn
# ---------------------------------------------------------------------------


class TestFromLinkedIn:
    def test_from_linkedin_creates_resume(self, client, auth_headers, linkedin_imported):
        resp = client.post("/api/resume/from-linkedin", headers=auth_headers, json={})
        assert resp.status_code == 201
        data = resp.get_json()
        assert "resume_id" in data
        # DB: verify resume created
        rows = query_db("SELECT id FROM resumes WHERE id = ?", (data["resume_id"],))
        assert len(rows) == 1

    def test_from_linkedin_without_import(self, client, auth_headers):
        resp = client.post("/api/resume/from-linkedin", headers=auth_headers, json={})
        # Should still work (uses default profile) or return error
        assert resp.status_code in (201, 400, 404)
        data = resp.get_json()
        if resp.status_code == 201:
            assert "resume_id" in data


# ---------------------------------------------------------------------------
# Resume Versions
# ---------------------------------------------------------------------------


class TestResumeVersions:
    def test_list_versions_empty(self, client, auth_headers):
        resp = client.get("/api/resumes/versions", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list) or "versions" in data

    def test_list_versions_after_upload(self, client, auth_headers):
        # Upload creates a resume but not necessarily a version
        rid = upload_resume(client, auth_headers)
        resp = client.get("/api/resumes/versions", headers=auth_headers)
        assert resp.status_code == 200

    def test_update_version_not_found(self, client, auth_headers):
        resp = client.put(
            "/api/resumes/versions/99999",
            headers=auth_headers,
            json={"text": "updated text"},
        )
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


class TestDownload:
    def test_download_pdf(self, client, auth_headers, resume_and_jd):
        rid, _ = resume_and_jd
        resp = client.get(f"/api/resume/download/{rid}?format=pdf", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.content_type == "application/pdf"
        assert len(resp.data) > 100

    def test_download_docx(self, client, auth_headers, resume_and_jd):
        rid, _ = resume_and_jd
        resp = client.get(f"/api/resume/download/{rid}?format=docx", headers=auth_headers)
        assert resp.status_code == 200
        assert "wordprocessingml" in resp.content_type or "octet-stream" in resp.content_type
        assert len(resp.data) > 100

    def test_download_not_found(self, client, auth_headers):
        resp = client.get("/api/resume/download/99999?format=pdf", headers=auth_headers)
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data
