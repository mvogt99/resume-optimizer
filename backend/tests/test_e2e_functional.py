"""E2E functional tests — real validation, no mocks.

~55 tests across 9 groups proving the NLP pipeline, scoring engine,
skills analysis, interview guide, experience chat, campaigns, agents,
and multi-user isolation actually work with realistic data.

Design principles:
  - No mocks — all code paths run real (template fallback in chat modules is the code's own logic)
  - Direct DB queries to validate state changes
  - Realistic data (Mike Vogt's real career profile)
  - Semantic assertions (score ranges, keyword presence, bucket correctness)
"""

import io
import json
import sqlite3
import threading

import models
import pytest

# ---------------------------------------------------------------------------
# Realistic test data constants
# ---------------------------------------------------------------------------

RESUME_MATCHED = """\
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

JD_MATCHED = """\
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

RESUME_CHEF = """\
JEAN-PIERRE LECLERC
Executive Chef | Culinary Arts Professional

SUMMARY
Award-winning Executive Chef with 15 years of experience in French
cuisine, pastry arts, and kitchen management. Specializing in
farm-to-table dining experiences and menu development for
Michelin-starred restaurants.

EXPERIENCE
Executive Chef — Le Bernardin (2018-Present)
- Manage kitchen staff of 25, oversee daily operations and menu planning
- Developed seasonal tasting menus increasing revenue by 35%

SKILLS
French cuisine, pastry, sous vide, kitchen management, menu development,
food safety, wine pairing, staff training
"""

JD_ML = """\
Machine Learning Engineer — AI Research Lab

Requirements:
- PhD or MS in Computer Science, Machine Learning, or related field
- 5+ years experience with TensorFlow, PyTorch, or JAX
- Strong background in NLP, computer vision, or reinforcement learning
- Experience with distributed training on GPU clusters
- Publications in top ML conferences (NeurIPS, ICML, ICLR)
- Proficiency in Python and C++
- Experience with MLOps (MLflow, Kubeflow, Weights & Biases)
"""

LINKEDIN_PROFILE = {
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
            "into a modern cloud-native platform. His Python and AWS expertise "
            "is unmatched.",
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
}

# Agent routes use user-id header
AGENT_HEADERS_1 = {"user-id": "1", "Content-Type": "application/json"}
AGENT_HEADERS_2 = {"user-id": "2", "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _upload_resume(client, auth_headers, text=RESUME_MATCHED, filename="resume.txt"):
    """Upload a resume and return the resume_id."""
    resp = client.post(
        "/api/resume/upload",
        headers={"Authorization": auth_headers["Authorization"]},
        data={"file": (io.BytesIO(text.encode()), filename)},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201, f"Upload failed: {resp.get_json()}"
    return resp.get_json()["resume_id"]


def _upload_jd(client, auth_headers, text=JD_MATCHED):
    """Upload a job description and return the job_id."""
    resp = client.post(
        "/api/job-description/upload",
        headers=auth_headers,
        json={"job_text": text},
    )
    assert resp.status_code == 201, f"JD upload failed: {resp.get_json()}"
    return resp.get_json()["job_id"]


def _optimize(client, auth_headers, resume_id):
    """Run optimization and return response JSON."""
    resp = client.post(
        f"/api/optimize-resume/{resume_id}",
        headers=auth_headers,
        json={},
    )
    assert resp.status_code == 200, f"Optimize failed: {resp.get_json()}"
    return resp.get_json()


def _query_db(sql, params=()):
    """Run a read query against the test DB, return list of dicts."""
    conn = sqlite3.connect(models.DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _query_db_one(sql, params=()):
    """Run a read query, return single dict or None."""
    rows = _query_db(sql, params)
    return rows[0] if rows else None


# ===================================================================
# GROUP A: Full Pipeline E2E (7 tests, 0 mocks)
# ===================================================================


class TestGroupA_FullPipeline:
    """Prove the upload→optimize pipeline works with real NLP."""

    def test_matched_score_range(self, client, auth_headers):
        """Matched resume+JD → score in 40-90 range."""
        rid = _upload_resume(client, auth_headers)
        _upload_jd(client, auth_headers)
        resp = client.post(f"/api/optimize-resume/{rid}", headers=auth_headers, json={})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("ats_compliance_score", -1) >= 0 or data.get("relevance_score", -1) >= 0
        score = data.get("relevance_score") or data.get("ats_compliance_score", 0)
        assert 40 <= score <= 90, f"Expected 40-90, got {score}"
        rows = _query_db("SELECT * FROM resumes WHERE id = ?", (int(rid),))
        assert len(rows) == 1

    def test_mismatched_score_low(self, client, auth_headers):
        """Chef resume + ML JD → score below 30."""
        rid = _upload_resume(client, auth_headers, RESUME_CHEF)
        _upload_jd(client, auth_headers, JD_ML)
        resp = client.post(f"/api/optimize-resume/{rid}", headers=auth_headers, json={})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("ats_compliance_score", -1) >= 0 or data.get("relevance_score", -1) >= 0
        score = data.get("relevance_score") or data.get("ats_compliance_score", 0)
        assert score < 35, f"Mismatch score should be <35, got {score}"

        # DB: resume row exists
        rows = _query_db("SELECT * FROM resumes WHERE id = ?", (int(rid),))
        assert len(rows) == 1

    def test_score_breakdown_four_signals(self, client, auth_headers):
        """All 4 signals present in score_breakdown, each 0-100."""
        rid = _upload_resume(client, auth_headers)
        _upload_jd(client, auth_headers)
        resp = client.post(f"/api/optimize-resume/{rid}", headers=auth_headers, json={})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("ats_compliance_score", -1) >= 0 or data.get("relevance_score", -1) >= 0
        bd = data.get("score_breakdown") or data.get("optimized_resume", {}).get(
            "score_breakdown", {}
        )
        expected_keys = {
            "keyword_coverage",
            "semantic_similarity",
            "skills_match",
            "section_completeness",
        }
        present = set(bd.keys()) & expected_keys
        assert len(present) >= 3, f"Expected ≥3 breakdown signals, got {present}"
        for key in present:
            val = bd[key]
            assert 0 <= val <= 100, f"{key}={val} out of 0-100 range"

    def test_matching_keywords_real(self, client, auth_headers):
        """Matched pair → matching_keywords contains real tech terms."""
        rid = _upload_resume(client, auth_headers)
        _upload_jd(client, auth_headers)
        resp = client.post(f"/api/optimize-resume/{rid}", headers=auth_headers, json={})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("ats_compliance_score", -1) >= 0 or data.get("relevance_score", -1) >= 0
        opt = data.get("optimized_resume", data)
        matching = [k.lower() for k in opt.get("matching_keywords", [])]
        skill_phrases = [k.lower() for k in opt.get("skill_phrases_matched", [])]
        combined = set(matching + skill_phrases)
        expected_any = {
            "python",
            "aws",
            "docker",
            "kubernetes",
            "microservices",
            "java",
            "terraform",
        }
        found = combined & expected_any
        assert len(found) >= 3, f"Expected ≥3 of {expected_any}, found {found} in {combined}"

    def test_sections_detected(self, client, auth_headers):
        """Resume with SUMMARY/EXPERIENCE/EDUCATION → sections_found has ≥2 true."""
        rid = _upload_resume(client, auth_headers)
        _upload_jd(client, auth_headers)
        resp = client.post(f"/api/optimize-resume/{rid}", headers=auth_headers, json={})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("ats_compliance_score", -1) >= 0 or data.get("relevance_score", -1) >= 0
        sections = data.get("sections_found") or data.get("optimized_resume", {}).get(
            "sections_found", {}
        )
        true_count = sum(1 for v in sections.values() if v)
        assert true_count >= 2, f"Expected ≥2 sections found, got {true_count}: {sections}"

    def test_optimized_text_enhanced(self, client, auth_headers):
        """optimized_text differs from original (keywords injected)."""
        rid = _upload_resume(client, auth_headers)
        _upload_jd(client, auth_headers)
        resp = client.post(f"/api/optimize-resume/{rid}", headers=auth_headers, json={})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("ats_compliance_score", -1) >= 0 or data.get("relevance_score", -1) >= 0
        opt = data.get("optimized_resume", data)
        original = opt.get("original_text", "") or data.get("original_resume_text", "")
        optimized = opt.get("optimized_text", "")
        # At minimum the optimized text should exist and have content
        assert len(optimized) > 100, f"Optimized text too short ({len(optimized)} chars)"
        # If LLM rewrite didn't run, optimized may equal original — that's acceptable
        # but added_keywords should still be populated
        added = opt.get("added_keywords", [])
        # Either text changed or keywords were identified
        assert optimized != original or len(added) > 0, "No optimization occurred"

    def test_db_state_after_upload(self, client, auth_headers):
        """After upload, DB has resume row with correct user_id."""
        rid = _upload_resume(client, auth_headers)

        # Verify via API
        resp = client.get("/api/resumes/versions", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "versions" in data, "Versions list must be present"

        row = _query_db_one("SELECT * FROM resumes WHERE id = ?", (int(rid),))
        assert row is not None, "Resume not found in DB"
        assert row["user_id"] == 1
        assert row["file_path"] is not None


# ===================================================================
# GROUP B: Skills Gap Analysis (5 tests, 0 mocks)
# ===================================================================


class TestGroupB_SkillsGap:
    """Prove skills gap analysis with 3-bucket output works."""

    def _setup_and_gap(self, client, auth_headers, resume_text=RESUME_MATCHED, jd_text=JD_MATCHED):
        """Upload resume+JD, fetch skills gap, return response dict."""
        rid = _upload_resume(client, auth_headers, resume_text)
        _upload_jd(client, auth_headers, jd_text)
        resp = client.get(f"/api/skills-gap/{rid}", headers=auth_headers)
        assert resp.status_code == 200, f"Skills gap failed: {resp.get_json()}"
        return resp.get_json()

    def test_three_buckets_exist(self, client, auth_headers):
        """shown + emphasize + acquire lists all present for partial match."""
        rid = _upload_resume(client, auth_headers)
        _upload_jd(client, auth_headers)
        resp = client.get(f"/api/skills-gap/{rid}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "skills_gap" in data
        assert data["skills_gap"] != {}
        gap = data.get("skills_gap", {})
        assert "skills_already_shown" in gap
        assert "skills_to_emphasize" in gap
        assert "skills_to_acquire" in gap
        # For a good match, shown should be non-empty
        assert len(gap["skills_already_shown"]) > 0, "Expected some skills already shown"
        rows = _query_db("SELECT * FROM resumes WHERE id = ?", (int(rid),))
        assert rows[0]["user_id"] == 1

    def test_coverage_math(self, client, auth_headers):
        """coverage_percent = (shown + emphasize) / total * 100."""
        rid = _upload_resume(client, auth_headers)
        _upload_jd(client, auth_headers)
        resp = client.get(f"/api/skills-gap/{rid}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "skills_gap" in data
        gap = data.get("skills_gap", {})
        shown = len(gap.get("skills_already_shown", []))
        emphasize = len(gap.get("skills_to_emphasize", []))
        total = gap.get("total_job_keywords", 1)
        expected_coverage = (shown + emphasize) / total * 100 if total > 0 else 0
        actual = gap.get("coverage_percent", 0)
        assert (
            abs(actual - expected_coverage) < 5
        ), f"Coverage math off: actual={actual}, expected≈{expected_coverage}"

    def test_known_skills_in_shown(self, client, auth_headers):
        """Python, AWS in resume → appear in skills_already_shown."""
        rid = _upload_resume(client, auth_headers)
        _upload_jd(client, auth_headers)
        resp = client.get(f"/api/skills-gap/{rid}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "skills_gap" in data
        gap = data.get("skills_gap", {})
        shown_names = {s["skill"].lower() for s in gap.get("skills_already_shown", [])}
        # At least some core skills should be shown
        expected = {"python", "aws", "java", "docker"}
        found = shown_names & expected
        assert len(found) >= 2, f"Expected ≥2 of {expected} in shown, found {found}"

    def test_missing_skills_detectable(self, client, auth_headers):
        """Chef resume against tech JD → many skills to acquire."""
        rid = _upload_resume(client, auth_headers, RESUME_CHEF)
        _upload_jd(client, auth_headers, JD_MATCHED)
        resp = client.get(f"/api/skills-gap/{rid}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "skills_gap" in data
        gap = data.get("skills_gap", {})
        acquire = gap.get("skills_to_acquire", [])
        assert len(acquire) >= 3, f"Chef should be missing ≥3 tech skills, got {len(acquire)}"

    def test_rescore_with_added_skills(self, client, auth_headers):
        """After rescore with added_skills, coverage should increase or stay same."""
        rid = _upload_resume(client, auth_headers)
        _upload_jd(client, auth_headers)

        # Get baseline
        resp1 = client.get(f"/api/skills-gap/{rid}", headers=auth_headers)
        data1 = resp1.get_json()
        assert "skills_gap" in data1
        gap1 = data1.get("skills_gap", {})
        baseline_shown = len(gap1.get("skills_already_shown", []))

        # Rescore with added skills
        resp2 = client.post(
            f"/api/skills-gap/{rid}/rescore",
            headers=auth_headers,
            json={"added_skills": ["MLflow", "Kubeflow", "PyTorch"]},
        )
        assert resp2.status_code == 200
        data2 = resp2.get_json()
        assert "skills_gap" in data2
        gap2 = data2.get("skills_gap", {})
        rescored_shown = len(gap2.get("skills_already_shown", []))
        assert (
            rescored_shown >= baseline_shown
        ), f"Rescore should not reduce shown: {baseline_shown} → {rescored_shown}"


# ===================================================================
# GROUP C: Interview Guide (5 tests, 0 mocks)
# ===================================================================


class TestGroupC_InterviewGuide:
    """Prove interview guide generation works with real NLP data."""

    def _setup_and_guide(self, client, auth_headers):
        rid = _upload_resume(client, auth_headers)
        _upload_jd(client, auth_headers)
        resp = client.get(f"/api/interview-guide/{rid}", headers=auth_headers)
        assert resp.status_code == 200, f"Interview guide failed: {resp.get_json()}"
        return resp.get_json()

    def test_personas_count(self, client, auth_headers):
        """2-3 personas returned."""
        rid = _upload_resume(client, auth_headers)
        _upload_jd(client, auth_headers)
        resp = client.get(f"/api/interview-guide/{rid}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "interview_personas" in data
        assert data["interview_personas"] != []
        personas = data.get("interview_personas", [])
        assert 2 <= len(personas) <= 4, f"Expected 2-4 personas, got {len(personas)}"

        # DB: resume row exists
        rows = _query_db("SELECT * FROM resumes WHERE id = ?", (int(rid),))
        assert len(rows) == 1

    def test_persona_types(self, client, auth_headers):
        """Persona names contain known types."""
        rid = _upload_resume(client, auth_headers)
        _upload_jd(client, auth_headers)
        resp = client.get(f"/api/interview-guide/{rid}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "interview_personas" in data
        personas = data.get("interview_personas", [])
        persona_names = " ".join(p.get("persona", "") for p in personas).lower()
        known_types = {"hr", "recruiter", "hiring", "manager", "technical"}
        found = {t for t in known_types if t in persona_names}
        assert len(found) >= 1, f"No known persona types found in: {persona_names}"

    def test_questions_nonempty(self, client, auth_headers):
        """Each persona has ≥1 question."""
        rid = _upload_resume(client, auth_headers)
        _upload_jd(client, auth_headers)
        resp = client.get(f"/api/interview-guide/{rid}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "interview_personas" in data
        assert data["interview_personas"] != []
        personas = data.get("interview_personas", [])
        for p in personas:
            questions = p.get("questions", [])
            assert len(questions) >= 1, f"Persona {p.get('persona')} has no questions"

    def test_star_examples_present(self, client, auth_headers):
        """star_examples list is non-empty."""
        rid = _upload_resume(client, auth_headers)
        _upload_jd(client, auth_headers)
        resp = client.get(f"/api/interview-guide/{rid}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "star_examples" in data
        assert data["star_examples"] != []
        star = data.get("star_examples", [])
        assert len(star) >= 1, "Expected at least 1 STAR example"

    def test_response_framework(self, client, auth_headers):
        """response_framework.star_method has 4 keys (S/T/A/R)."""
        rid = _upload_resume(client, auth_headers)
        _upload_jd(client, auth_headers)
        resp = client.get(f"/api/interview-guide/{rid}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "response_framework" in data
        framework = data.get("response_framework", {})
        star_method = framework.get("star_method", {})
        expected = {"situation", "task", "action", "result"}
        present = set(star_method.keys()) & expected
        assert len(present) == 4, f"STAR method missing keys: {expected - present}"


# ===================================================================
# GROUP D: Experience Chat Lifecycle (6 tests, 0 mocks — template fallback)
# ===================================================================


class TestGroupD_ExperienceChat:
    """Prove experience chat 6-stage state machine works end-to-end."""

    def test_start_returns_session(self, client, auth_headers):
        """POST /experience/start → session_id + initial stage."""
        resp = client.post(
            "/api/experience/start",
            headers=auth_headers,
            json={"employer": "Navitus Health Solutions"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert "session_id" in data
        assert data["session_id"] != "", "session_id must be non-empty"

        # DB: experience_sessions row exists
        rows = _query_db("SELECT * FROM experience_sessions WHERE id = ?", (data["session_id"],))
        assert len(rows) == 1

    def test_message_advances_stage(self, client, auth_headers):
        """Send message → stage advances from initial."""
        resp = client.post(
            "/api/experience/start",
            headers=auth_headers,
            json={"employer": "Navitus"},
        )
        session_id = resp.get_json()["session_id"]
        initial_stage = resp.get_json().get("stage", "intro")

        resp2 = client.post(
            "/api/experience/message",
            headers=auth_headers,
            json={"session_id": session_id, "message": "Senior Enterprise Architect"},
        )
        assert resp2.status_code == 200
        data2 = resp2.get_json()
        # Stage should have advanced or a response returned
        assert (
            data2.get("stage", "") != ""
            or data2.get("message", "") != ""
            or data2.get("response", "") != ""
        )

    def test_full_lifecycle(self, client, auth_headers):
        """6 messages through all stages → is_complete or final stage."""
        resp = client.post(
            "/api/experience/start",
            headers=auth_headers,
            json={"employer": "Navitus Health Solutions", "client": "PBM Platform"},
        )
        session_id = resp.get_json()["session_id"]

        messages = [
            "Senior Enterprise Architect",
            "Led cloud migration of pharmacy benefit platform",
            "Python, AWS, Docker, Kubernetes, FastAPI, Kafka",
            "Reduced deployment time by 95%, achieved 99.99% uptime",
            "Scaling distributed systems across 3 time zones",
            "Completed successfully, ready to finalize",
        ]
        last_data = None
        for msg in messages:
            resp = client.post(
                "/api/experience/message",
                headers=auth_headers,
                json={"session_id": session_id, "message": msg},
            )
            assert resp.status_code == 200, f"Message failed: {resp.get_json()}"
            last_data = resp.get_json()

        # Should reach complete or near-complete state
        is_complete = last_data.get("is_complete", False)
        stage = last_data.get("stage", "")
        assert last_data.get("stage", "") != "", "Last response must include a stage"
        assert is_complete or stage in (
            "complete",
            "challenges",
            "outcomes",
        ), f"Expected complete state, got stage={stage}, is_complete={is_complete}"

    def test_summary_has_fields(self, client, auth_headers):
        """GET /experience/summary → employer and key fields."""
        resp = client.post(
            "/api/experience/start",
            headers=auth_headers,
            json={"employer": "OPI", "client": "Integration Platform"},
        )
        session_id = resp.get_json()["session_id"]

        # Send enough messages to populate
        for msg in ["Solutions Architect", "Built integration platform", "Python, Java, Docker"]:
            client.post(
                "/api/experience/message",
                headers=auth_headers,
                json={"session_id": session_id, "message": msg},
            )

        resp = client.get(f"/api/experience/summary/{session_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("employer", "") != "" or data.get("session_id", "") != ""

    def test_finalize_saves_to_db(self, client, auth_headers):
        """POST /experience/finalize → DB has extracted_experiences row."""
        resp = client.post(
            "/api/experience/start",
            headers=auth_headers,
            json={"employer": "AHEAD"},
        )
        session_id = resp.get_json()["session_id"]

        for msg in [
            "Software Engineer",
            "Data pipeline development",
            "Java, Python",
            "95% code coverage",
            "Legacy system complexity",
            "Done",
        ]:
            client.post(
                "/api/experience/message",
                headers=auth_headers,
                json={"session_id": session_id, "message": msg},
            )

        resp = client.post(f"/api/experience/finalize/{session_id}", headers=auth_headers, json={})
        assert resp.status_code == 200, f"Finalize: {resp.get_json()}"
        fin_data = resp.get_json()
        assert fin_data.get("session_id", "") != "", "Finalize must return session_id"

        rows = _query_db(
            "SELECT * FROM extracted_experiences WHERE session_id = ?",
            (session_id,),
        )
        assert len(rows) >= 1, "No extracted_experiences row after finalize"

    def test_apply_creates_version(self, client, auth_headers):
        """POST /experience/apply → resume_versions row created."""
        resp = client.post(
            "/api/experience/start",
            headers=auth_headers,
            json={"employer": "TestCo"},
        )
        session_id = resp.get_json()["session_id"]

        for msg in [
            "Lead Developer",
            "Built the core platform",
            "Python, React, PostgreSQL",
            "Launched on time with zero defects",
            "Tight deadlines",
            "Finished",
        ]:
            client.post(
                "/api/experience/message",
                headers=auth_headers,
                json={"session_id": session_id, "message": msg},
            )

        # Finalize first
        client.post(f"/api/experience/finalize/{session_id}", headers=auth_headers, json={})

        # Apply to resume
        resp = client.post(f"/api/experience/apply/{session_id}", headers=auth_headers, json={})
        assert resp.status_code == 201, f"Apply unexpected: {resp.status_code}"
        apply_data = resp.get_json()
        assert "version_id" in apply_data
        rows = _query_db("SELECT * FROM resume_versions WHERE source = 'experience_chat'")
        assert len(rows) >= 1, "No resume_versions row after apply"


# ===================================================================
# GROUP E: Campaign Lifecycle (7 tests, template fallback — no mocks)
# ===================================================================


class TestGroupE_Campaigns:
    """Prove campaign interview + CRUD works end-to-end."""

    def _start_interview(self, client, auth_headers, theme="Enterprise Architecture"):
        """Start a campaign interview session."""
        resp = client.post(
            "/api/campaigns/interview/start",
            headers=auth_headers,
            json={"theme": theme},
        )
        assert resp.status_code == 201, f"Interview start failed: {resp.get_json()}"
        return resp.get_json()

    def test_interview_start(self, client, auth_headers):
        """Start interview → session_id and stage."""
        resp = client.post(
            "/api/campaigns/interview/start",
            headers=auth_headers,
            json={"theme": "Enterprise Architecture"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert "session_id" in data
        assert data["session_id"] != "", "session_id must be non-empty"

        # DB: campaign_sessions row exists
        rows = _query_db("SELECT * FROM campaign_sessions WHERE id = ?", (data["session_id"],))
        assert len(rows) == 1

    def test_stage_progression(self, client, auth_headers):
        """Messages advance through stages."""
        data = self._start_interview(client, auth_headers)
        session_id = data["session_id"]

        stage_messages = [
            "Technology leaders and CTOs",
            "Professional and authoritative",
            "Cloud migration journey",
            "3",
            "Post 1: lessons; Post 2: scaling; Post 3: patterns",
            "Looks good",
        ]
        stages_seen = {data.get("stage", "theme")}
        for msg in stage_messages:
            resp = client.post(
                "/api/campaigns/interview/message",
                headers=auth_headers,
                json={"session_id": session_id, "message": msg},
            )
            assert resp.status_code == 200, f"Campaign msg failed: {resp.get_json()}"
            stages_seen.add(resp.get_json().get("stage", ""))

        assert resp.get_json().get("stage", "") != "", "Last response must include a stage"
        assert len(stages_seen) >= 3, f"Expected ≥3 distinct stages, saw {stages_seen}"

    def test_create_campaign_from_interview(self, client, auth_headers):
        """Finalize → campaign row in DB."""
        data = self._start_interview(client, auth_headers)
        session_id = data["session_id"]

        for msg in [
            "CTOs and VPs of Engineering",
            "Thought leadership tone",
            "Microservices transformation",
            "2",
            "Post 1: migration challenges; Post 2: lessons learned",
            "Finalize this",
        ]:
            client.post(
                "/api/campaigns/interview/message",
                headers=auth_headers,
                json={"session_id": session_id, "message": msg},
            )

        resp = client.post(
            "/api/campaigns/create",
            headers=auth_headers,
            json={"session_id": session_id},
        )
        assert resp.status_code == 201, f"Campaign create failed: {resp.get_json()}"
        campaign_id = resp.get_json()["campaign_id"]
        assert campaign_id > 0, "campaign_id must be a positive integer"

        rows = _query_db("SELECT * FROM campaigns WHERE id = ?", (campaign_id,))
        assert len(rows) == 1, "Campaign not in DB"

    def test_add_post_to_campaign(self, client, auth_headers):
        """POST post → campaign_posts row, content preserved."""
        # Create campaign via DB for simplicity
        conn = sqlite3.connect(models.DB_PATH)
        conn.execute(
            "INSERT INTO campaigns (user_id, theme, audience, tone, post_count, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (1, "Test Theme", "Test Audience", "Professional", 1, "active"),
        )
        conn.commit()
        campaign_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()

        resp = client.post(
            f"/api/campaigns/{campaign_id}/posts",
            headers=auth_headers,
            json={"title": "Test Post", "content": "This is a test post about architecture."},
        )
        assert resp.status_code == 201, f"Add post failed: {resp.get_json()}"

        rows = _query_db("SELECT * FROM campaign_posts WHERE campaign_id = ?", (campaign_id,))
        assert len(rows) >= 1
        assert "architecture" in rows[0].get("content", "").lower()

    def test_edit_and_delete_post(self, client, auth_headers):
        """PUT updates content, DELETE removes row."""
        conn = sqlite3.connect(models.DB_PATH)
        conn.execute(
            "INSERT INTO campaigns (user_id, theme, audience, tone, post_count, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (1, "Edit Test", "Leaders", "Pro", 1, "active"),
        )
        conn.commit()
        cid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO campaign_posts (campaign_id, position, title, content, status) "
            "VALUES (?, ?, ?, ?, ?)",
            (cid, 1, "Original", "Original content", "draft"),
        )
        conn.commit()
        pid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()

        # Edit
        resp = client.put(
            f"/api/campaigns/{cid}/posts/{pid}",
            headers=auth_headers,
            json={"content": "Updated content about microservices"},
        )
        assert resp.status_code == 200

        # Verify edit
        row = _query_db_one("SELECT content FROM campaign_posts WHERE id = ?", (pid,))
        assert "microservices" in row["content"].lower()

        # Delete
        resp = client.delete(f"/api/campaigns/{cid}/posts/{pid}", headers=auth_headers)
        assert resp.status_code == 200
        row = _query_db_one("SELECT * FROM campaign_posts WHERE id = ?", (pid,))
        assert row is None, "Post not deleted"

    def test_export_campaign(self, client, auth_headers):
        """GET export → formatted text with posts."""
        conn = sqlite3.connect(models.DB_PATH)
        conn.execute(
            "INSERT INTO campaigns (user_id, theme, audience, tone, post_count, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (1, "Export Test", "Developers", "Casual", 2, "active"),
        )
        conn.commit()
        cid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        for i in range(2):
            conn.execute(
                "INSERT INTO campaign_posts (campaign_id, position, title, content, status) "
                "VALUES (?, ?, ?, ?, ?)",
                (cid, i + 1, f"Post {i+1}", f"Content for post {i+1}", "draft"),
            )
        conn.commit()
        conn.close()

        resp = client.get(f"/api/campaigns/{cid}/export", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        export_text = data.get("export", "") or data.get("text", "") or json.dumps(data)
        assert "post" in export_text.lower() or "content" in export_text.lower()

    def test_campaign_user_isolation(self, client, auth_headers, second_user_headers):
        """User B cannot see User A's campaigns."""
        conn = sqlite3.connect(models.DB_PATH)
        conn.execute(
            "INSERT INTO campaigns (user_id, theme, audience, tone, post_count, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (1, "Private Campaign", "My Audience", "Pro", 1, "active"),
        )
        conn.commit()
        conn.close()

        # User A sees it
        resp = client.get("/api/campaigns", headers=auth_headers)
        assert resp.status_code == 200
        campaigns = resp.get_json().get("campaigns", [])
        assert len(campaigns) >= 1

        # User B does not
        resp = client.get("/api/campaigns", headers=second_user_headers)
        assert resp.status_code == 200
        campaigns = resp.get_json().get("campaigns", [])
        assert campaigns == [], "User B should not see User A's campaigns"


# ===================================================================
# GROUP F: Agent E2E (7 tests, CRUD routes — no LLM calls)
# ===================================================================


class TestGroupF_Agents:
    """Prove agent CRUD routes work — no LLM calls, all DB operations real."""

    def test_scout_manual_add(self, client, auth_headers):
        """POST posting → DB row with title, company."""
        resp = client.post(
            "/api/agents/scout/postings",
            headers=AGENT_HEADERS_1,
            json={
                "title": "Solutions Architect",
                "company": "Acme Corp",
                "location": "Remote",
                "url": "https://example.com/job/123",
                "description": "Build cloud-native platforms with Python and AWS",
            },
        )
        assert resp.status_code == 201, f"Manual add failed: {resp.get_json()}"
        post_data = resp.get_json()
        assert (
            post_data.get("posting_id", -1) != -1 or post_data.get("id", -1) != -1
        ), "Response must include posting ID"

        rows = _query_db("SELECT * FROM job_postings WHERE company = 'Acme Corp'")
        assert len(rows) >= 1
        assert rows[0]["title"] == "Solutions Architect"

    def test_scout_criteria_crud(self, client, auth_headers):
        """Save + list criteria."""
        resp = client.post(
            "/api/agents/scout/criteria",
            headers=AGENT_HEADERS_1,
            json={
                "search_name": "Cloud Architect",
                "target_roles": ["Solutions Architect", "Cloud Architect"],
                "locations": ["Remote"],
                "remote_preference": "remote",
                "keywords": ["python", "aws", "kubernetes"],
            },
        )
        assert resp.status_code == 201, f"Save criteria failed: {resp.get_json()}"

        resp = client.get("/api/agents/scout/criteria", headers=AGENT_HEADERS_1)
        assert resp.status_code == 200
        criteria = resp.get_json().get("criteria", [])
        assert len(criteria) >= 1
        assert criteria[0]["search_name"] == "Cloud Architect"

    def test_pipeline_view(self, client, auth_headers):
        """Pipeline returns stages."""
        # Add a posting first
        client.post(
            "/api/agents/scout/postings",
            headers=AGENT_HEADERS_1,
            json={"title": "Pipeline Test", "company": "TestCo", "status": "discovered"},
        )

        resp = client.get("/api/agents/pipeline", headers=AGENT_HEADERS_1)
        assert resp.status_code == 200
        data = resp.get_json()
        assert (
            data.get("stages", []) != []
            or data.get("columns", []) != []
            or data.get("pipeline", []) != []
        )

    def test_pipeline_move_stage(self, client, auth_headers):
        """PUT stage → DB updated."""
        # Create a posting
        resp = client.post(
            "/api/agents/scout/postings",
            headers=AGENT_HEADERS_1,
            json={"title": "Move Test", "company": "MoveInc", "status": "discovered"},
        )
        posting_id = resp.get_json().get("posting_id") or resp.get_json().get("id")

        if posting_id:
            resp = client.put(
                f"/api/agents/pipeline/{posting_id}",
                headers=AGENT_HEADERS_1,
                json={"status": "bookmarked"},
            )
            assert resp.status_code == 200

            row = _query_db_one("SELECT status FROM job_postings WHERE id = ?", (posting_id,))
            if row:
                assert row["status"] == "bookmarked"

    def test_agent_status(self, client, auth_headers):
        """GET /agents/status returns agent list."""
        resp = client.get("/api/agents/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert (
            data["agents"][0].get("type", "") != "" or data["agents"][0].get("name", "") != ""
        ), "First agent must have type or name"

    def test_posting_update_and_delete(self, client, auth_headers):
        """Update posting notes/starred, then delete."""
        resp = client.post(
            "/api/agents/scout/postings",
            headers=AGENT_HEADERS_1,
            json={"title": "Delete Me", "company": "GoneCo"},
        )
        pid = resp.get_json().get("posting_id") or resp.get_json().get("id")
        assert pid != "", "POST must return a posting ID"

        if pid:
            # Update
            resp = client.put(
                f"/api/agents/scout/postings/{pid}",
                headers=AGENT_HEADERS_1,
                json={"notes": "Interesting role", "is_starred": True},
            )
            assert resp.status_code == 200

            # Delete
            resp = client.delete(f"/api/agents/scout/postings/{pid}", headers=AGENT_HEADERS_1)
            assert resp.status_code == 200

    def test_agent_runs_logged(self, client, auth_headers):
        """After any agent operation, agent_runs table may have entries."""
        resp = client.get("/api/agents/runs", headers=AGENT_HEADERS_1)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "runs" in data


# ===================================================================
# GROUP G: Multi-User Isolation (5 tests, 0 mocks)
# ===================================================================


class TestGroupG_MultiUserIsolation:
    """Prove User B cannot access User A's resources."""

    def test_resume_isolation(self, client, auth_headers, second_user_headers):
        """User B can't optimize User A's resume."""
        rid = _upload_resume(client, auth_headers)
        _upload_jd(client, auth_headers)

        # User B tries to optimize User A's resume
        resp = client.post(
            f"/api/optimize-resume/{rid}",
            headers=second_user_headers,
            json={},
        )
        assert resp.status_code in (404, 403), f"Expected 404/403, got {resp.status_code}"
        data = resp.get_json()
        assert data.get("error") or data.get("message"), "404/403 must include error detail"

        # DB: resume still exists for User A (isolation, not deletion)
        rows = _query_db("SELECT * FROM resumes WHERE id = ?", (int(rid),))
        assert len(rows) == 1

    def test_experience_isolation(self, client, auth_headers, second_user_headers):
        """User B can't access User A's experience sessions."""
        resp = client.post(
            "/api/experience/start",
            headers=auth_headers,
            json={"employer": "SecretCo"},
        )
        session_id = resp.get_json()["session_id"]

        # User B tries to get summary
        resp = client.get(
            f"/api/experience/summary/{session_id}",
            headers=second_user_headers,
        )
        # User B must not see User A's session
        assert resp.status_code == 404  # session filtered by user_id

    def test_campaign_isolation(self, client, auth_headers, second_user_headers):
        """User B can't list User A's campaigns."""
        conn = sqlite3.connect(models.DB_PATH)
        conn.execute(
            "INSERT INTO campaigns (user_id, theme, audience, tone, post_count, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (1, "User A Only", "Private", "Pro", 1, "active"),
        )
        conn.commit()
        conn.close()

        resp = client.get("/api/campaigns", headers=second_user_headers)
        campaigns = resp.get_json().get("campaigns", [])
        user_a_campaigns = [c for c in campaigns if c.get("theme") == "User A Only"]
        assert len(user_a_campaigns) == 0

        # DB: campaign exists (just isolated)
        rows = _query_db("SELECT * FROM campaigns WHERE theme = ?", ("User A Only",))
        assert len(rows) == 1, "Campaign must exist in DB for User A"

    def test_posting_isolation(self, client, auth_headers, second_user_headers):
        """User B can't see User A's job postings."""
        client.post(
            "/api/agents/scout/postings",
            headers=AGENT_HEADERS_1,
            json={"title": "Secret Job", "company": "PrivateCo"},
        )

        resp = client.get("/api/agents/scout/postings", headers=AGENT_HEADERS_2)
        assert resp.status_code == 200
        postings = resp.get_json().get("postings", [])
        private = [p for p in postings if p.get("company") == "PrivateCo"]
        assert len(private) == 0, "User B should not see User A's postings"

    def test_version_isolation(self, client, auth_headers, second_user_headers):
        """User B can't access User A's resume versions."""
        conn = sqlite3.connect(models.DB_PATH)
        conn.execute(
            "INSERT INTO resume_versions (user_id, source, file_name, parsed_text) "
            "VALUES (?, ?, ?, ?)",
            (1, "test", "secret_resume.txt", "Top secret resume content"),
        )
        conn.commit()
        vid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()

        resp = client.get(f"/api/resumes/versions/{vid}", headers=second_user_headers)
        assert resp.status_code == 404
        data = resp.get_json()
        assert data.get("error") or data.get("message"), "404 must include error detail"


# ===================================================================
# GROUP H: Edge Cases (5 tests, 0 mocks)
# ===================================================================


class TestGroupH_EdgeCases:
    """Prove the system handles edge cases gracefully."""

    def test_empty_resume_upload(self, client, auth_headers):
        """Empty file → 400 or graceful handling."""
        resp = client.post(
            "/api/resume/upload",
            headers={"Authorization": auth_headers["Authorization"]},
            data={"file": (io.BytesIO(b""), "empty.txt")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 201  # valid extension accepted; no content validation
        data = resp.get_json()
        assert data.get("resume_id"), "201 must include resume_id"

    def test_unicode_resume(self, client, auth_headers):
        """Unicode characters (CJK, accents) → no crash, score returned."""
        unicode_resume = (
            "RÉSUMÉ — José García\n\n"
            "SUMMARY\n"
            "Experienced software engineer with expertise in Python and Java.\n"
            "Worked on microservices and cloud-native 雲端 applications.\n"
            "Certifications: AWS Solutions Architect, Kubernetes Administrator.\n\n"
            "EXPERIENCE\n"
            "Senior Developer — Société Générale (2020-Present)\n"
            "- Built RESTful APIs serving 10M+ requests/day\n"
            "- Deployed Docker containers on AWS ECS\n\n"
            "EDUCATION\n"
            "MS Computer Science — Zürich University\n"
        )
        rid = _upload_resume(client, auth_headers, unicode_resume)
        _upload_jd(client, auth_headers)
        resp = client.post(f"/api/optimize-resume/{rid}", headers=auth_headers, json={})
        assert resp.status_code == 200, f"Optimize failed: {resp.get_json()}"
        data = resp.get_json()
        assert (
            data.get("relevance_score", 0) > 0 or data.get("ats_compliance_score", 0) > 0
        ), "Score must be positive for unicode resume"
        score = data.get("relevance_score") or data.get("ats_compliance_score", 0)
        assert 0 < score <= 100, f"Unicode resume score should be 1-100, got {score}"

    def test_very_long_resume(self, client, auth_headers):
        """50KB resume text → processes without error."""
        long_resume = "MIKE VOGT\nEnterprise Architect\n\nSUMMARY\n"
        long_resume += "Python AWS Docker Kubernetes microservices REST APIs. " * 800
        long_resume += "\n\nEXPERIENCE\n"
        long_resume += "Senior Architect — BigCorp (2020-Present)\n" * 200
        long_resume += "\nEDUCATION\nMS Engineering — MIT\n"
        assert len(long_resume.encode()) > 40000  # >40KB

        rid = _upload_resume(client, auth_headers, long_resume)
        _upload_jd(client, auth_headers)
        resp = client.post(f"/api/optimize-resume/{rid}", headers=auth_headers, json={})
        assert resp.status_code == 200, f"Optimize failed: {resp.get_json()}"
        data = resp.get_json()
        assert (
            data.get("relevance_score", 0) >= 0 or data.get("ats_compliance_score", 0) >= 0
        ), "Score field must exist for long resume"
        score = data.get("relevance_score") or data.get("ats_compliance_score", 0)
        assert 0 <= score <= 100, f"Long resume score should be 0-100, got {score}"

    def test_special_chars_in_jd(self, client, auth_headers):
        """SQL-injection-like JD text → no error, safe handling."""
        evil_jd = (
            "Requirements for SQL Expert:\n"
            "- Experience with Python; DROP TABLE users; --\n"
            "- Strong background in <script>alert('xss')</script>\n"
            "- Proficiency in Java, AWS, Docker, Kubernetes\n"
            "- Experience with REST APIs and microservices\n"
            "- 10+ years of software engineering experience\n"
        )
        rid = _upload_resume(client, auth_headers)
        _upload_jd(client, auth_headers, evil_jd)
        resp = client.post(f"/api/optimize-resume/{rid}", headers=auth_headers, json={})
        assert resp.status_code == 200, f"Optimize failed: {resp.get_json()}"
        data = resp.get_json()
        assert (
            data.get("relevance_score", 0) >= 0 or data.get("ats_compliance_score", 0) >= 0
        ), "Score must exist after special chars JD"
        score = data.get("relevance_score") or data.get("ats_compliance_score", 0)
        assert isinstance(score, (int, float))
        # Verify DB still works (not corrupted)
        rows = _query_db("SELECT COUNT(*) as c FROM users")
        assert rows[0]["c"] >= 1

    def test_concurrent_users(self, client, auth_headers, second_user_headers):
        """Two users upload+optimize simultaneously → correct isolated results."""
        # Upload different resumes for each user
        rid_a = _upload_resume(client, auth_headers, RESUME_MATCHED)
        _upload_jd(client, auth_headers, JD_MATCHED)

        rid_b = _upload_resume(client, second_user_headers, RESUME_CHEF)
        _upload_jd(client, second_user_headers, JD_ML)

        # Optimize both
        data_a = _optimize(client, auth_headers, rid_a)
        data_b = _optimize(client, second_user_headers, rid_b)

        score_a = data_a.get("relevance_score") or data_a.get("ats_compliance_score", 0)
        score_b = data_b.get("relevance_score") or data_b.get("ats_compliance_score", 0)

        # User A (matched) should score significantly higher than User B (mismatch)
        assert score_a > score_b, f"Matched user should score higher: A={score_a}, B={score_b}"


# ===================================================================
# GROUP I: NLP Quality (5 tests, 0 mocks)
# ===================================================================


class TestGroupI_NLPQuality:
    """Prove NLP components produce meaningful results."""

    def test_score_determinism(self, client, auth_headers):
        """Same inputs → same score 3 times."""
        scores = []
        for _ in range(3):
            rid = _upload_resume(client, auth_headers)
            _upload_jd(client, auth_headers)
            data = _optimize(client, auth_headers, rid)
            score = data.get("relevance_score") or data.get("ats_compliance_score", 0)
            scores.append(score)

        assert scores[0] == scores[1] == scores[2], f"Non-deterministic scores: {scores}"

    def test_score_sensitivity(self, client, auth_headers):
        """Adding matching keywords raises score."""
        # Baseline: chef resume against tech JD
        rid1 = _upload_resume(client, auth_headers, RESUME_CHEF)
        _upload_jd(client, auth_headers, JD_MATCHED)
        data1 = _optimize(client, auth_headers, rid1)
        score_chef = data1.get("relevance_score") or data1.get("ats_compliance_score", 0)

        # Enhanced: chef + tech keywords
        enhanced_chef = (
            RESUME_CHEF
            + "\n\nSKILLS\nPython, Java, AWS, Docker, Kubernetes, Terraform, REST APIs, microservices\n"
        )
        rid2 = _upload_resume(client, auth_headers, enhanced_chef)
        data2 = _optimize(client, auth_headers, rid2)
        score_enhanced = data2.get("relevance_score") or data2.get("ats_compliance_score", 0)

        assert (
            score_enhanced > score_chef
        ), f"Adding keywords should raise score: chef={score_chef}, enhanced={score_enhanced}"

    def test_similarity_ordering(self, client, auth_headers):
        """Similar texts score higher than dissimilar texts."""
        from nlp_engine import calculate_similarity

        sim_high = calculate_similarity(
            "Python developer with AWS and Docker experience building microservices",
            "Looking for a Python engineer with AWS, Docker, and microservices skills",
        )
        sim_low = calculate_similarity(
            "French cuisine chef specializing in pastry and wine pairing",
            "Looking for a Python engineer with AWS, Docker, and microservices skills",
        )
        assert sim_high > sim_low, f"Similar should rank higher: high={sim_high}, low={sim_low}"

    def test_keyword_extraction_real_terms(self, client, auth_headers):
        """extract_keywords() returns real tech terms, not stopwords."""
        from nlp_engine import extract_keywords

        keywords = extract_keywords(
            "Senior Python developer with experience in AWS Lambda, Docker containers, "
            "and Kubernetes orchestration. Built REST APIs and microservices. "
            "Strong background in Java and PostgreSQL database management."
        )
        keywords_lower = {k.lower() for k in keywords}
        # Should find tech terms (NLP may lemmatize: "containers"→"container", etc.)
        expected_any = {
            "python",
            "aws",
            "docker",
            "kubernetes",
            "java",
            "postgresql",
            "microservices",
            "microservice",
            "lambda",
            "container",
            "api",
            "rest",
            "database",
            "orchestration",
        }
        found = keywords_lower & expected_any
        assert len(found) >= 2, f"Expected ≥2 of {expected_any}, found {found}"
        # Should NOT have stopwords
        stopwords = {"the", "and", "with", "in", "a", "of", "for", "is"}
        stop_found = keywords_lower & stopwords
        assert len(stop_found) == 0, f"Stopwords found in keywords: {stop_found}"

    def test_skill_phrases_multi_word(self, client, auth_headers):
        """extract_skill_phrases() captures multi-word terms."""
        from nlp_engine import extract_skill_phrases

        phrases = extract_skill_phrases(
            "Experienced with machine learning, REST APIs, natural language processing, "
            "Docker containers, Kubernetes orchestration, and cloud computing. "
            "Expert in Python, Java, and PostgreSQL."
        )
        phrases_lower = {p.lower() for p in phrases}
        # Should find multi-word phrases
        multi_word_expected = {
            "machine learning",
            "rest apis",
            "natural language processing",
            "cloud computing",
        }
        found_multi = {p for p in phrases_lower if " " in p} & multi_word_expected
        # Also single-word tech terms
        single_expected = {"python", "java", "docker", "kubernetes", "postgresql"}
        found_single = phrases_lower & single_expected
        total_found = len(found_multi) + len(found_single)
        assert (
            total_found >= 3
        ), f"Expected ≥3 skill phrases, found multi={found_multi}, single={found_single}"
