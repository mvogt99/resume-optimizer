"""Tests for resume upload, versions, and optimization routes."""

import io

from test_helpers import query_db


def test_upload_resume_txt(client, auth_headers):
    data = {"file": (io.BytesIO(b"John Doe\nSoftware Engineer\nPython, Java, AWS"), "resume.txt")}
    resp = client.post(
        "/api/resume/upload",
        headers={"Authorization": auth_headers["Authorization"]},
        data=data,
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["resume_id"], "201 upload must return resume_id"
    resume_id = data["resume_id"]

    # DB: verify resume row exists
    rows = query_db("SELECT * FROM resumes WHERE id = ?", (resume_id,))
    assert len(rows) == 1, f"No resumes row for {resume_id}"


def test_upload_no_file(client, auth_headers):
    resp = client.post(
        "/api/resume/upload",
        headers={"Authorization": auth_headers["Authorization"]},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data, "400 must include error message"


def test_upload_bad_extension(client, auth_headers):
    data = {"file": (io.BytesIO(b"data"), "file.csv")}
    resp = client.post(
        "/api/resume/upload",
        headers={"Authorization": auth_headers["Authorization"]},
        data=data,
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data, "400 must include error message"


def test_list_versions(client, auth_headers):
    resp = client.get("/api/resumes/versions", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data["versions"], list)


def test_upload_job_description(client, auth_headers):
    resp = client.post(
        "/api/job-description/upload",
        headers=auth_headers,
        json={
            "job_text": "We are looking for a Senior Python Developer with 5+ years "
            "experience in Django, REST APIs, and AWS cloud infrastructure."
        },
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["job_id"], "201 JD upload must return job_id"
    jd_id = data["job_id"]

    # DB: verify JD row exists
    rows = query_db("SELECT * FROM job_descriptions WHERE id = ?", (jd_id,))
    assert len(rows) == 1, f"No job_descriptions row for {jd_id}"


def test_optimize_resume(client, auth_headers):
    """Upload resume + JD, then optimize."""
    # Upload resume
    data = {
        "file": (
            io.BytesIO(b"John Doe\nSoftware Engineer\n5 years Python\nDjango REST API development"),
            "resume.txt",
        )
    }
    resp = client.post(
        "/api/resume/upload",
        headers={"Authorization": auth_headers["Authorization"]},
        data=data,
        content_type="multipart/form-data",
    )
    resume_id = resp.get_json()["resume_id"]

    # Upload JD
    resp = client.post(
        "/api/job-description/upload",
        headers=auth_headers,
        json={"job_text": "Senior Python Developer with Django REST APIs AWS Docker Kubernetes."},
    )
    jd_id = resp.get_json()["job_id"]

    # Optimize
    resp = client.post(
        f"/api/optimize-resume/{resume_id}",
        headers=auth_headers,
        json={"job_description_id": jd_id},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "ats_compliance_score" in data
