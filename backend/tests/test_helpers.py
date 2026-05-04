"""Shared test data, helpers, and constants for resume-optimizer E2E tests.

Import this module (not conftest) from test files that need shared constants.
Fixtures remain in conftest.py and are injected by pytest automatically.
"""

import io
import os
import sqlite3
import time

import requests

# ---------------------------------------------------------------------------
# Realistic test data constants
# ---------------------------------------------------------------------------

RESUME_TEXT = """\
MIKE VOGT
Enterprise Architect | 20 Years Experience
mike.vogt@example.com | (555) 123-4567

SUMMARY
Seasoned Enterprise Architect with 20 years of experience designing and
delivering large-scale distributed systems. Expert in Python, Java, AWS,
Docker, and Kubernetes. Proven track record leading cross-functional teams
to architect microservices platforms, API gateways, and cloud-native
solutions that reduce infrastructure costs and improve reliability.

CORE COMPETENCIES
Python, Java, AWS, Docker, Kubernetes, Terraform, REST APIs, microservices,
CI/CD, PostgreSQL, Redis, Kafka, system design, technical leadership,
agile methodologies, solution architecture, cloud migration

EXPERIENCE

Senior Enterprise Architect — Navitus Health Solutions (2019-Present)
- Designed and implemented cloud-native pharmacy benefit platform on AWS
  serving 30M+ members with 99.99% uptime
- Led migration from monolithic Java application to Python/FastAPI
  microservices, reducing deployment time from 2 weeks to 2 hours
- Architected event-driven integration layer using Kafka and REST APIs
- Managed team of 12 engineers across 3 time zones

Solutions Architect — OPI (2014-2019)
- Built enterprise integration platform connecting 200+ client systems
- Implemented Docker and Kubernetes orchestration for dev/staging/prod
- Designed Terraform IaC templates reducing provisioning time by 80%
- Led API-first design initiative standardizing 50+ REST endpoints

Software Engineer — AHEAD (2006-2014)
- Developed high-throughput data processing pipelines in Java and Python
- Built automated testing frameworks achieving 95% code coverage
- Contributed to open-source monitoring tools used by 500+ organizations

EDUCATION
Master of Engineering, Systems Engineering — Stevens Institute of Technology
Bachelor of Science, Marine Engineering — United States Merchant Marine Academy
"""

JOB_DESCRIPTION = (
    JD_TEXT
) = """\
Solutions Architect — Cloud Platform Team

Requirements:
- 10+ years of experience in software architecture and engineering
- Strong proficiency in Python and Java
- Deep experience with AWS services (EC2, ECS, Lambda, S3, RDS)
- Hands-on experience with Docker and Kubernetes orchestration
- Experience with Terraform or similar infrastructure-as-code tools
- Expertise in designing and building REST APIs and microservices
- Experience with CI/CD pipelines and DevOps practices
- Strong communication and technical leadership skills
- Experience with event-driven architectures (Kafka, SQS/SNS)
- Bachelor's degree in Computer Science or related field

Nice to have:
- Experience with PostgreSQL and Redis
- Familiarity with monitoring and observability tools
- Experience leading distributed engineering teams
"""

LINKEDIN_PROFILE = {
    "full_name": "Mike Vogt",
    "headline": "Enterprise Architect | AI & Cloud Infrastructure",
    "summary": "20 years of enterprise architecture experience.",
    "current_job": {"title": "Senior Enterprise Architect", "company": "Navitus Health Solutions"},
    "skills_and_endorsements": [
        {"skill": "Enterprise Architecture", "endorsements_count": 117},
        {"skill": "Integration", "endorsements_count": 91},
        {"skill": "Python", "endorsements_count": 45},
        {"skill": "AWS", "endorsements_count": 38},
        {"skill": "Java", "endorsements_count": 35},
        {"skill": "Docker", "endorsements_count": 28},
        {"skill": "Kubernetes", "endorsements_count": 22},
        {"skill": "REST APIs", "endorsements_count": 20},
        {"skill": "Microservices", "endorsements_count": 18},
        {"skill": "Terraform", "endorsements_count": 15},
        {"skill": "Strategy", "endorsements_count": 52},
        {"skill": "Solution Architecture", "endorsements_count": 40},
        {"skill": "Cloud Computing", "endorsements_count": 30},
        {"skill": "PostgreSQL", "endorsements_count": 12},
        {"skill": "CI/CD", "endorsements_count": 10},
    ],
    "recommendations_received": [
        {
            "author_first_name": "Jane",
            "author_last_name": "Smith",
            "author_job_title": "VP Engineering",
            "text": "Mike is an exceptional architect who transformed our legacy systems "
            "into a modern cloud-native platform. His Python and AWS expertise is unmatched.",
        },
        {
            "author_first_name": "Bob",
            "author_last_name": "Chen",
            "author_job_title": "CTO",
            "text": "Working with Mike on our Kubernetes migration was transformative. "
            "His ability to design scalable microservices architectures is remarkable.",
        },
    ],
    "previous_jobs": [
        {
            "title": "Senior Enterprise Architect",
            "company": "Navitus Health Solutions",
            "description": "Led cloud migration, designed pharmacy benefit platform. "
            "KEY ACCOMPLISHMENTS: Reduced deployment time 95%, achieved 99.99% uptime.",
        },
        {
            "title": "Solutions Architect",
            "company": "OPI",
            "description": "Built integration platform. "
            "KEY ACCOMPLISHMENTS: Connected 200+ client systems, 80% faster provisioning.",
        },
    ],
    "education_history": [
        {"school": "Stevens Institute of Technology", "degree": "Master of Engineering"},
        {"school": "United States Merchant Marine Academy", "degree": "Bachelor of Science"},
    ],
}

# Agent routes use user-id header (not JWT)
AGENT_HEADERS_1 = {"user-id": "1", "Content-Type": "application/json"}
AGENT_HEADERS_2 = {"user-id": "2", "Content-Type": "application/json"}

# ---------------------------------------------------------------------------
# LLM / FTAL harness availability
# ---------------------------------------------------------------------------

HARNESS_URL = "http://localhost:8000/api/harness/run"
HARNESS_AVAILABLE = False
try:
    _r = requests.get("http://localhost:8000/health", timeout=3)
    HARNESS_AVAILABLE = _r.status_code == 200
except Exception:
    pass


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def upload_resume(client, headers, text=None, filename="resume.txt"):
    """Upload a resume and return the resume_id."""
    text = text or RESUME_TEXT
    resp = client.post(
        "/api/resume/upload",
        headers={"Authorization": headers["Authorization"]},
        data={"file": (io.BytesIO(text.encode()), filename)},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201, f"Upload failed: {resp.get_json()}"
    return resp.get_json()["resume_id"]


def upload_jd(client, headers, text=None):
    """Upload a job description and return the job_id."""
    text = text or JD_TEXT
    resp = client.post(
        "/api/job-description/upload",
        headers=headers,
        json={"job_text": text},
    )
    assert resp.status_code == 201, f"JD upload failed: {resp.get_json()}"
    return resp.get_json()["job_id"]


def optimize(client, headers, resume_id):
    """Run optimization and return response JSON."""
    resp = client.post(f"/api/optimize-resume/{resume_id}", headers=headers, json={})
    assert resp.status_code == 200, f"Optimize failed: {resp.get_json()}"
    return resp.get_json()


def poll_job(client, headers, job_id, timeout=120, interval=2):
    """Poll GET /api/jobs/<job_id>/status until completed/failed."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(f"/api/jobs/{job_id}/status", headers=headers)
        if resp.status_code != 200:
            time.sleep(interval)
            continue
        data = resp.get_json()
        status = data.get("status", "")
        if status in ("completed", "complete", "done"):
            return data
        if status in ("failed", "error", "cancelled"):
            return data
        time.sleep(interval)
    raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")


def query_db(sql, params=()):
    """Query the test database directly. Returns list of dicts.

    Works on both SQLite (default) and PostgreSQL (when DATABASE_URL is set).
    """
    from db_engine import is_postgres

    if is_postgres():
        from models import get_db_connection

        conn = get_db_connection()
        cur = conn.execute(sql, params)
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    else:
        import models

        conn = sqlite3.connect(models.DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]


def require_harness():
    """Skip (or fail if REQUIRE_LLM_TESTS=true) when FTAL harness is unavailable."""
    import pytest

    if not HARNESS_AVAILABLE:
        if os.environ.get("REQUIRE_LLM_TESTS", "").lower() == "true":
            pytest.fail(
                "FTAL harness is NOT running at localhost:8000. "
                "REQUIRE_LLM_TESTS=true enforces hard failure."
            )
        pytest.skip(
            "FTAL harness not available at localhost:8000 — skipping LLM test. "
            "Set REQUIRE_LLM_TESTS=true to enforce."
        )


def create_posting(client, headers=None):
    """Create a manual job posting and return its id."""
    headers = headers or AGENT_HEADERS_1
    resp = client.post(
        "/api/agents/scout/postings",
        headers=headers,
        json={
            "title": "Senior Solutions Architect",
            "company": "Acme Corp",
            "description": JD_TEXT,
            "link": "https://example.com/job/123",
            "location": "Remote",
        },
    )
    assert resp.status_code == 201, f"Create posting failed: {resp.get_json()}"
    data = resp.get_json()
    return data.get("id") or data.get("posting_id")
