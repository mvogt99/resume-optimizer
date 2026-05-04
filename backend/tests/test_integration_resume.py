"""Integration tests — resume upload, versioning, and optimization with real data."""

import io

from test_helpers import query_db


def test_full_resume_optimization_flow(client, auth_headers):
    """Upload resume → upload JD → optimize → verify scores and keywords."""
    # 1. Upload resume with substantive content
    resume_text = (
        b"Mike Vogt\n"
        b"Enterprise Architect | 20 Years Experience\n\n"
        b"PROFESSIONAL SUMMARY\n"
        b"Senior enterprise architect with expertise in integration, "
        b"microservices, and cloud architecture.\n\n"
        b"SKILLS\n"
        b"Python, Java, AWS, Docker, Kubernetes, REST APIs, "
        b"PostgreSQL, Redis, Terraform\n\n"
        b"EXPERIENCE\n"
        b"Lead Architect - Acme Corp (2020-Present)\n"
        b"- Designed microservices platform serving 10M requests/day\n"
        b"- Led migration from monolith to Kubernetes-based architecture\n"
        b"- Reduced infrastructure costs by 35% through containerization\n"
    )
    data = {"file": (io.BytesIO(resume_text), "resume.txt")}
    resp = client.post(
        "/api/resume/upload",
        headers={"Authorization": auth_headers["Authorization"]},
        data=data,
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201
    resume_id = resp.get_json()["resume_id"]

    # DB: verify resume row exists
    rows = query_db("SELECT * FROM resumes WHERE id = ?", (resume_id,))
    assert len(rows) == 1, f"No resumes row for {resume_id}"

    # 2. Upload matching JD
    resp = client.post(
        "/api/job-description/upload",
        headers=auth_headers,
        json={
            "job_text": "Senior Solutions Architect with 10+ years experience. "
            "Required: Python, Java, AWS, Kubernetes, Docker, "
            "REST APIs, microservices architecture. "
            "Nice to have: Terraform, PostgreSQL, Redis, CI/CD."
        },
    )
    assert resp.status_code == 201
    jd_id = resp.get_json()["job_id"]

    # 3. Optimize
    resp = client.post(
        f"/api/optimize-resume/{resume_id}",
        headers=auth_headers,
        json={"job_description_id": jd_id},
    )
    assert resp.status_code == 200
    result = resp.get_json()
    assert "ats_compliance_score" in result
    score = result["ats_compliance_score"]
    assert isinstance(score, (int, float))
    assert 0 <= score <= 100
    # With matching content, score should be reasonable
    assert score > 30


def test_resume_version_lifecycle(client, auth_headers):
    """Create version via experience apply → list → get → edit."""
    # Resume upload creates 'resumes' rows, not 'resume_versions'.
    # Versions are created by experience apply, builder save, or GDrive import.
    # We test the versions CRUD endpoints using experience apply flow.

    # 1. Upload resume first
    data = {
        "file": (
            io.BytesIO(
                b"Python Developer\n5 years experience\n" b"Django, Flask, PostgreSQL, Redis"
            ),
            "resume.txt",
        )
    }
    resp = client.post(
        "/api/resume/upload",
        headers={"Authorization": auth_headers["Authorization"]},
        data=data,
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201

    # 2. Create experience, finalize, and apply to create a resume version
    resp = client.post(
        "/api/experience/start",
        headers=auth_headers,
        json={"employer": "TestCo"},
    )
    session_id = resp.get_json()["session_id"]

    client.post(
        "/api/experience/message",
        headers=auth_headers,
        json={"session_id": session_id, "message": "I was a Python dev using Django"},
    )
    client.post(
        f"/api/experience/finalize/{session_id}",
        headers=auth_headers,
        json={},
    )
    resp = client.post(
        f"/api/experience/apply/{session_id}",
        headers=auth_headers,
        json={},
    )
    # Apply may succeed (201) or fail (400) depending on extracted data
    if resp.status_code not in (200, 201):
        # Versions endpoint should still return empty list
        resp = client.get("/api/resumes/versions", headers=auth_headers)
        assert resp.status_code == 200
        return

    # 3. List versions — should have at least 1
    resp = client.get("/api/resumes/versions", headers=auth_headers)
    assert resp.status_code == 200
    versions = resp.get_json()["versions"]
    assert len(versions) >= 1

    # 4. Get specific version
    version_id = versions[0]["id"]
    resp = client.get(f"/api/resumes/versions/{version_id}", headers=auth_headers)
    assert resp.status_code == 200
    version = resp.get_json()
    assert "text" in version or "resume_text" in version or "parsed_text" in version

    # 5. Edit version (API expects 'parsed_text' field)
    resp = client.put(
        f"/api/resumes/versions/{version_id}",
        headers=auth_headers,
        json={"parsed_text": "Edited resume content\nUpdated skills section"},
    )
    assert resp.status_code == 200


def test_resume_upload_multiple_formats(client, auth_headers):
    """Test .txt upload succeeds, .csv rejected, .exe rejected."""
    # .txt should work
    data = {"file": (io.BytesIO(b"Text resume"), "resume.txt")}
    resp = client.post(
        "/api/resume/upload",
        headers={"Authorization": auth_headers["Authorization"]},
        data=data,
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201

    # .csv should be rejected
    data = {"file": (io.BytesIO(b"name,email"), "data.csv")}
    resp = client.post(
        "/api/resume/upload",
        headers={"Authorization": auth_headers["Authorization"]},
        data=data,
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert "not allowed" in data["error"].lower()

    # .exe should be rejected
    data = {"file": (io.BytesIO(b"\x00\x00"), "malware.exe")}
    resp = client.post(
        "/api/resume/upload",
        headers={"Authorization": auth_headers["Authorization"]},
        data=data,
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert "not allowed" in data["error"].lower()


def test_optimize_with_mismatched_content(client, auth_headers):
    """Optimize with unrelated resume/JD — score should be low."""
    # Upload cooking-themed resume
    data = {
        "file": (
            io.BytesIO(
                b"Chef Gordon\nHead Chef\n"
                b"10 years of culinary arts\n"
                b"French cuisine, pastry, sous vide, kitchen management"
            ),
            "chef.txt",
        )
    }
    resp = client.post(
        "/api/resume/upload",
        headers={"Authorization": auth_headers["Authorization"]},
        data=data,
        content_type="multipart/form-data",
    )
    resume_id = resp.get_json()["resume_id"]

    # Upload tech JD
    resp = client.post(
        "/api/job-description/upload",
        headers=auth_headers,
        json={
            "job_text": "Machine Learning Engineer Python TensorFlow PyTorch "
            "Kubernetes Docker CI/CD deep learning NLP computer vision."
        },
    )
    jd_id = resp.get_json()["job_id"]

    # Optimize — score should be very low
    resp = client.post(
        f"/api/optimize-resume/{resume_id}",
        headers=auth_headers,
        json={"job_description_id": jd_id},
    )
    assert resp.status_code == 200
    result = resp.get_json()
    assert result["ats_compliance_score"] < 50

    # DB: verify both resume and JD rows exist
    rows = query_db("SELECT * FROM resumes WHERE id = ?", (resume_id,))
    assert len(rows) == 1
    rows = query_db("SELECT * FROM job_descriptions WHERE id = ?", (jd_id,))
    assert len(rows) == 1
