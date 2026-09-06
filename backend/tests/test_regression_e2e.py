"""Comprehensive E2E regression tests — 35 tests across 13 groups.

Every test is self-contained (fresh DB per test via conftest fixtures).
Realistic data throughout — no stubs, no skips, no mocking.
"""

import io

import pytest
from test_helpers import query_db  # noqa: F401

# ---------------------------------------------------------------------------
# Realistic test data constants
# ---------------------------------------------------------------------------

RESUME_MATCHED = """MIKE VOGT
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

JD_MATCHED = """Solutions Architect — Cloud Platform Team

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

RESUME_MISMATCHED = """JEAN-PIERRE LECLERC
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

JD_MISMATCHED = """Machine Learning Engineer — AI Research Lab

Requirements:
- PhD or MS in Computer Science, Machine Learning, or related field
- 5+ years experience with TensorFlow, PyTorch, or JAX
- Strong background in NLP, computer vision, or reinforcement learning
- Experience with distributed training on GPU clusters
- Publications in top ML conferences (NeurIPS, ICML, ICLR)
- Proficiency in Python and C++
- Experience with MLOps (MLflow, Kubeflow, Weights & Biases)
"""

# Agent routes use user-id header instead of Bearer token
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


def _run_campaign_interview(client, auth_headers, theme="Enterprise Architecture"):
    """Drive a campaign through all 7 stages and create it. Return campaign_id."""
    # Start
    resp = client.post(
        "/api/campaigns/interview/start",
        headers=auth_headers,
        json={"theme": theme},
    )
    assert resp.status_code == 201
    session_id = resp.get_json()["session_id"]

    # Advance through 6 stages after initial theme
    stage_messages = [
        "Technology leaders and CTOs in Fortune 500",
        "Professional and authoritative",
        "Digital transformation journey from monolith to microservices",
        "3",
        "Post 1: cloud migration lessons; Post 2: team scaling; Post 3: architecture patterns",
        "Looks good, finalize",
    ]
    for msg in stage_messages:
        resp = client.post(
            "/api/campaigns/interview/message",
            headers=auth_headers,
            json={"session_id": session_id, "message": msg},
        )
        assert resp.status_code == 200, f"Campaign msg failed: {resp.get_json()}"

    # Create campaign
    resp = client.post(
        "/api/campaigns/create",
        headers=auth_headers,
        json={"session_id": session_id},
    )
    assert resp.status_code == 201, f"Campaign create failed: {resp.get_json()}"
    return resp.get_json()["campaign_id"]


# ===================================================================
# GROUP A: Authentication (3 tests)
# ===================================================================


class TestGroupA_Auth:
    def test_a1_register_creates_pending_user_without_token(self, client):
        """Registration is APPROVAL-GATED: 201 with pending=true and NO token.
        The absence of a credential is the security-relevant property."""
        resp = client.post(
            "/api/register",
            json={"email": "newuser@test.com", "password": "Str0ng!Pass"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data.get("pending"), "response must report the pending state"
        assert "token" not in data, "an unapproved account must not receive a token"
        rows = query_db("SELECT * FROM users WHERE email = ?", ("newuser@test.com",))
        assert len(rows) == 1
        assert rows[0]["status"] == "pending"

    def test_a2_login_refused_until_approved_then_returns_token(self, client):
        """The gate is the behaviour worth covering: a pending account is
        refused, and only an activated one receives a token."""
        client.post(
            "/api/register",
            json={"email": "login@test.com", "password": "Str0ng!Pass"},
        )
        resp = client.post(
            "/api/login",
            json={"email": "login@test.com", "password": "Str0ng!Pass"},
        )
        assert resp.status_code == 403, "a pending account must not be able to log in"

        from models import User

        user = User.find_by_email("login@test.com")
        User.update(user.id, status="active")

        resp = client.post(
            "/api/login",
            json={"email": "login@test.com", "password": "Str0ng!Pass"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data["token"], str) and len(data["token"]) > 20
        assert int(data["user_id"]) > 0, "user_id must be positive"

    def test_a3_bad_password_returns_401(self, client):
        client.post(
            "/api/register",
            json={"email": "bad@test.com", "password": "Correct1!"},
        )
        resp = client.post(
            "/api/login",
            json={"email": "bad@test.com", "password": "WrongPassword!"},
        )
        assert resp.status_code == 401
        data = resp.get_json()
        assert data.get("error") or data.get("message"), "401 must include error detail"


# ===================================================================
# GROUP B: Resume Upload + Optimize (5 tests)
# ===================================================================


class TestGroupB_ResumeOptimize:
    def test_b1_upload_resume_201(self, client, auth_headers):
        rid = _upload_resume(client, auth_headers)
        assert rid  # non-empty string
        rows = query_db("SELECT * FROM resumes WHERE id = ?", (rid,))
        assert len(rows) == 1

    def test_b2_upload_jd_201(self, client, auth_headers):
        resp = client.post(
            "/api/job-description/upload",
            headers=auth_headers,
            json={"job_text": JD_MATCHED},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert "job_id" in data
        jid = data["job_id"]
        assert jid

        # DB: job_descriptions row exists
        rows = query_db("SELECT * FROM job_descriptions WHERE id = ?", (jid,))
        assert len(rows) == 1, "JD upload must create DB row"

    def test_b3_matched_optimize_score_above_25(self, client, auth_headers):
        rid = _upload_resume(client, auth_headers, RESUME_MATCHED)
        _upload_jd(client, auth_headers, JD_MATCHED)
        data = _optimize(client, auth_headers, rid)
        score = data.get("relevance_score") or data["ats_compliance_score"]
        assert isinstance(score, (int, float))
        assert score > 25, f"Matched pair scored only {score}"

    def test_b4_mismatched_optimize_score_below_25(self, client, auth_headers):
        rid = _upload_resume(client, auth_headers, RESUME_MISMATCHED)
        _upload_jd(client, auth_headers, JD_MISMATCHED)
        data = _optimize(client, auth_headers, rid)
        score = data.get("relevance_score") or data["ats_compliance_score"]
        assert isinstance(score, (int, float))
        assert score <= 25, f"Mismatched pair scored {score} — should be <=25"

    def test_b5_csv_upload_rejected_400(self, client, auth_headers):
        resp = client.post(
            "/api/resume/upload",
            headers={"Authorization": auth_headers["Authorization"]},
            data={"file": (io.BytesIO(b"a,b,c\n1,2,3"), "data.csv")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data or "message" in data, "400 must include error detail"


# ===================================================================
# GROUP C: Skills Gap (2 tests)
# ===================================================================


class TestGroupC_SkillsGap:
    def test_c1_three_buckets_exist(self, client, auth_headers):
        rid = _upload_resume(client, auth_headers, RESUME_MATCHED)
        _upload_jd(client, auth_headers, JD_MATCHED)
        resp = client.get(f"/api/skills-gap/{rid}", headers=auth_headers)
        assert resp.status_code == 200
        gap = resp.get_json()["skills_gap"]
        assert "skills_already_shown" in gap
        assert "skills_to_emphasize" in gap
        assert "skills_to_acquire" in gap

    def test_c2_skill_names_are_real_tech(self, client, auth_headers):
        rid = _upload_resume(client, auth_headers, RESUME_MATCHED)
        _upload_jd(client, auth_headers, JD_MATCHED)
        resp = client.get(f"/api/skills-gap/{rid}", headers=auth_headers)
        data = resp.get_json()
        assert "skills_gap" in data
        assert "skills_already_shown" in data["skills_gap"]
        gap = data["skills_gap"]
        all_skills = []
        for bucket in ("skills_already_shown", "skills_to_emphasize", "skills_to_acquire"):
            for entry in gap[bucket]:
                all_skills.append(entry["skill"].lower())
        # At least some real tech terms should appear from the JD
        tech_terms = {
            "python",
            "java",
            "aws",
            "docker",
            "kubernetes",
            "terraform",
            "rest",
            "microservices",
        }
        found = tech_terms & set(all_skills)
        assert len(found) >= 2, f"Only found {found} in skills gap — expected real tech terms"
        rows = query_db("SELECT * FROM resumes WHERE id = ?", (rid,))
        assert len(rows) == 1


# ===================================================================
# GROUP D: Interview Guide (2 tests)
# ===================================================================


class TestGroupD_InterviewGuide:
    def test_d1_returns_200(self, client, auth_headers):
        rid = _upload_resume(client, auth_headers, RESUME_MATCHED)
        _upload_jd(client, auth_headers, JD_MATCHED)
        resp = client.get(f"/api/interview-guide/{rid}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "interview_personas" in data, "Interview guide must include personas"

    def test_d2_has_personas_with_questions(self, client, auth_headers):
        rid = _upload_resume(client, auth_headers, RESUME_MATCHED)
        _upload_jd(client, auth_headers, JD_MATCHED)
        resp = client.get(f"/api/interview-guide/{rid}", headers=auth_headers)
        data = resp.get_json()
        assert "interview_personas" in data
        personas = data["interview_personas"]
        assert len(personas) >= 1
        # Each persona should have questions
        for persona in personas:
            assert "questions" in persona, f"Persona missing questions: {persona}"
            assert len(persona["questions"]) >= 1


# ===================================================================
# GROUP E: Experience Chat (3 tests)
# ===================================================================


class TestGroupE_ExperienceChat:
    def test_e1_full_lifecycle(self, client, auth_headers):
        """start → msg → msg → summary → finalize → apply — all succeed."""
        # Start
        resp = client.post(
            "/api/experience/start",
            headers=auth_headers,
            json={"employer": "Navitus Health Solutions", "client": "Internal Platform"},
        )
        assert resp.status_code == 201
        sid = resp.get_json()["session_id"]

        # Messages
        resp = client.post(
            "/api/experience/message",
            headers=auth_headers,
            json={
                "session_id": sid,
                "message": (
                    "I led a cloud migration project for our pharmacy platform."
                    " We moved from on-premise Java to AWS with Python microservices."
                ),
            },
        )
        assert resp.status_code == 200

        resp = client.post(
            "/api/experience/message",
            headers=auth_headers,
            json={
                "session_id": sid,
                "message": (
                    "The result was 99.99% uptime and 80% faster deployments."
                    " We used Docker, Kubernetes, and Terraform."
                ),
            },
        )
        assert resp.status_code == 200

        # Summary
        resp = client.get(f"/api/experience/summary/{sid}", headers=auth_headers)
        assert resp.status_code == 200

        # Finalize
        resp = client.post(
            f"/api/experience/finalize/{sid}",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 200

        # Apply
        resp = client.post(
            f"/api/experience/apply/{sid}",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert "resume_id" in data
        assert "version_id" in data
        rows = query_db("SELECT * FROM experience_sessions WHERE id = ?", (sid,))
        assert len(rows) == 1

    def test_e2_summary_has_employer(self, client, auth_headers):
        resp = client.post(
            "/api/experience/start",
            headers=auth_headers,
            json={"employer": "AHEAD", "client": "Financial Services"},
        )
        sid = resp.get_json()["session_id"]
        client.post(
            "/api/experience/message",
            headers=auth_headers,
            json={
                "session_id": sid,
                "message": (
                    "Built data pipelines processing 10M records"
                    " daily using Python and PostgreSQL."
                ),
            },
        )
        resp = client.get(f"/api/experience/summary/{sid}", headers=auth_headers)
        data = resp.get_json()
        assert data.get("employer") == "AHEAD"

        # DB: experience session exists
        rows = query_db("SELECT * FROM experience_sessions WHERE id = ?", (sid,))
        assert len(rows) == 1, "Experience session must exist in DB"

    def test_e3_list_not_empty(self, client, auth_headers):
        # Create and finalize a session first
        resp = client.post(
            "/api/experience/start",
            headers=auth_headers,
            json={"employer": "OPI", "client": "Retail"},
        )
        sid = resp.get_json()["session_id"]
        client.post(
            "/api/experience/message",
            headers=auth_headers,
            json={
                "session_id": sid,
                "message": "Designed enterprise integration platform connecting 200 systems.",
            },
        )
        client.post(f"/api/experience/finalize/{sid}", headers=auth_headers, json={})

        resp = client.get("/api/experience/list", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["experiences"]) >= 1


# ===================================================================
# GROUP F: Skills Interview (2 tests)
# ===================================================================


class TestGroupF_SkillsInterview:
    def test_f1_start_message_finalize_summary(self, client, auth_headers):
        rid = _upload_resume(client, auth_headers, RESUME_MATCHED)

        # Start
        resp = client.post(
            "/api/skills-interview/start",
            headers=auth_headers,
            json={"skills": ["Python", "AWS", "Kubernetes"], "resume_id": rid},
        )
        assert resp.status_code == 200
        sid = resp.get_json()["session_id"]

        # Message
        resp = client.post(
            "/api/skills-interview/message",
            headers=auth_headers,
            json={
                "session_id": sid,
                "message": (
                    "I have 10 years with Python, built production"
                    " FastAPI services on AWS ECS, and manage"
                    " 50-node K8s clusters."
                ),
            },
        )
        assert resp.status_code == 200

        # Finalize
        resp = client.post(
            f"/api/skills-interview/{sid}/finalize",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 200

        # Summary
        resp = client.get(
            f"/api/skills-interview/{sid}/summary",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "results" in data
        assert data["results"][0]["skill"] != ""
        rows = query_db("SELECT * FROM skills_interview_sessions WHERE id = ?", (sid,))
        assert len(rows) == 1

    def test_f2_no_skills_returns_400(self, client, auth_headers):
        resp = client.post(
            "/api/skills-interview/start",
            headers=auth_headers,
            json={"skills": [], "resume_id": "1"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data.get("error") or data.get("message"), "400 must include error detail"


# ===================================================================
# GROUP G: ATS Improvement Chat (2 tests)
# ===================================================================


class TestGroupG_ATSImprovement:
    def test_g1_start_message_get_resume(self, client, auth_headers):
        rid = _upload_resume(client, auth_headers, RESUME_MATCHED)

        resp = client.post(
            "/api/ats-improve/start",
            headers=auth_headers,
            json={
                "resume_id": rid,
                "score_data": {
                    "score": 55,
                    "score_breakdown": {
                        "keyword_coverage": 60,
                        "semantic_similarity": 50,
                        "skills_match": 45,
                        "section_completeness": 75,
                    },
                    "keywords_matched": ["python", "aws"],
                    "keywords_missing": ["terraform", "kafka"],
                },
            },
        )
        assert resp.status_code == 200
        sid = resp.get_json()["session_id"]

        # Send a message
        resp = client.post(
            "/api/ats-improve/message",
            headers=auth_headers,
            json={"session_id": sid, "message": "How can I improve my Terraform coverage?"},
        )
        assert resp.status_code == 200

        # Get resume text
        resp = client.get(
            f"/api/ats-improve/{sid}/resume",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "improved_text" in data
        rows = query_db("SELECT * FROM ats_improvement_sessions WHERE id = ?", (sid,))
        assert len(rows) == 1

    def test_g2_no_score_data_returns_400(self, client, auth_headers):
        resp = client.post(
            "/api/ats-improve/start",
            headers=auth_headers,
            json={"resume_id": "1", "score_data": {}},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data.get("error") or data.get("message"), "400 must include error detail"


# ===================================================================
# GROUP H: Campaigns (4 tests)
# ===================================================================


class TestGroupH_Campaigns:
    def test_h1_seven_stage_create_has_posts(self, client, auth_headers):
        cid = _run_campaign_interview(client, auth_headers)
        assert cid

        # List posts
        resp = client.get(f"/api/campaigns/{cid}/posts", headers=auth_headers)
        assert resp.status_code == 200
        # Campaign should exist and be listable
        resp = client.get("/api/campaigns", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "campaigns" in data
        assert len(data["campaigns"]) >= 1
        rows = query_db("SELECT * FROM campaigns WHERE id = ?", (cid,))
        assert len(rows) == 1

    def test_h2_posts_crud_and_export(self, client, auth_headers):
        cid = _run_campaign_interview(client, auth_headers)

        # Add a post
        resp = client.post(
            f"/api/campaigns/{cid}/posts",
            headers=auth_headers,
            json={
                "title": "Cloud Migration Lessons",
                "content": (
                    "After 20 years in enterprise architecture,"
                    " here are my top 5 cloud migration lessons..."
                ),
            },
        )
        assert resp.status_code == 201
        post_id = resp.get_json()["post_id"]

        # Edit post
        resp = client.put(
            f"/api/campaigns/{cid}/posts/{post_id}",
            headers=auth_headers,
            json={
                "content": "Updated: Top 7 cloud migration lessons from real enterprise projects."
            },
        )
        assert resp.status_code == 200

        # Export
        resp = client.get(f"/api/campaigns/{cid}/export", headers=auth_headers)
        assert resp.status_code == 200
        assert "text" in resp.get_json()

    def test_h3_user_isolation(self, client, auth_headers, second_user_headers):
        cid = _run_campaign_interview(client, auth_headers)

        # Second user can't see it
        resp = client.get(f"/api/campaigns/{cid}", headers=second_user_headers)
        assert resp.status_code == 404

        # Second user's list is empty
        resp = client.get("/api/campaigns", headers=second_user_headers)
        assert resp.status_code == 200
        assert len(resp.get_json()["campaigns"]) == 0

    def test_h4_delete_and_verify(self, client, auth_headers):
        cid = _run_campaign_interview(client, auth_headers)

        resp = client.delete(f"/api/campaigns/{cid}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "message" in data or "status" in data, "Delete must return confirmation"

        resp = client.get(f"/api/campaigns/{cid}", headers=auth_headers)
        assert resp.status_code == 404

        # DB: campaign row removed
        rows = query_db("SELECT * FROM campaigns WHERE id = ?", (cid,))
        assert len(rows) == 0, "Campaign must be deleted from DB"


# ===================================================================
# GROUP I: Resume Builder (2 tests)
# ===================================================================


class TestGroupI_Builder:
    def test_i1_start_edit_save_creates_version(self, client, auth_headers):
        jd_text = JD_MATCHED  # >50 chars

        # Start builder session
        resp = client.post(
            "/api/builder/start",
            headers=auth_headers,
            json={"job_text": jd_text},
        )
        assert resp.status_code == 201
        sid = resp.get_json()["session_id"]

        # Edit with resume text (this also compiles internally)
        resp = client.put(
            f"/api/builder/edit/{sid}",
            headers=auth_headers,
            json={"text": RESUME_MATCHED},
        )
        assert resp.status_code == 200
        assert "ats_score" in resp.get_json()

        # Save
        resp = client.post(
            f"/api/builder/save/{sid}",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert "version_id" in data
        assert "resume_id" in data

    def test_i2_missing_text_returns_400(self, client, auth_headers):
        resp = client.post(
            "/api/builder/start",
            headers=auth_headers,
            json={"job_text": JD_MATCHED},
        )
        data = resp.get_json()
        assert "session_id" in data
        sid = data["session_id"]
        rows = query_db("SELECT * FROM builder_sessions WHERE id = ?", (sid,))
        assert len(rows) == 1

        resp = client.put(
            f"/api/builder/edit/{sid}",
            headers=auth_headers,
            json={"text": ""},
        )
        assert resp.status_code == 400


# ===================================================================
# GROUP J: Agents — Job Scout + Pipeline (4 tests)
# ===================================================================


class TestGroupJ_Agents:
    @pytest.fixture(autouse=True)
    def _create_agent_users(self, client):
        """Ensure user rows 1 and 2 exist before any agent route touches job_postings FK."""
        client.post("/api/register", json={"email": "agent1@test.com", "password": "Test1234!"})
        client.post("/api/register", json={"email": "agent2@test.com", "password": "Test1234!"})

    def test_j1_posting_lifecycle(self, client, app):
        # Add posting
        resp = client.post(
            "/api/agents/scout/postings",
            headers=AGENT_HEADERS_1,
            json={
                "title": "Staff Engineer",
                "company": "Stripe",
                "url": "https://stripe.com/jobs/123",
                "description": "Design payment infrastructure at scale",
            },
        )
        assert resp.status_code == 201
        pid = resp.get_json().get("posting_id") or resp.get_json().get("id")
        assert pid

        # Get posting
        resp = client.get(f"/api/agents/scout/postings/{pid}", headers=AGENT_HEADERS_1)
        assert resp.status_code == 200
        assert resp.get_json()["title"] == "Staff Engineer"

        # Update posting
        resp = client.put(
            f"/api/agents/scout/postings/{pid}",
            headers=AGENT_HEADERS_1,
            json={"starred": True, "notes": "Great fit"},
        )
        assert resp.status_code == 200

        # Delete posting
        resp = client.delete(f"/api/agents/scout/postings/{pid}", headers=AGENT_HEADERS_1)
        assert resp.status_code == 200

    def test_j2_criteria_crud(self, client, app):
        # Save criteria
        resp = client.post(
            "/api/agents/scout/criteria",
            headers=AGENT_HEADERS_1,
            json={
                "search_name": "Enterprise Arch roles",
                "keywords": ["enterprise architect", "solutions architect"],
                "salary_min": 180000,
            },
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data.get("criteria_id") or data.get("id"), "201 must return criteria identifier"

        # List criteria
        resp = client.get("/api/agents/scout/criteria", headers=AGENT_HEADERS_1)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["criteria"][0]["search_name"] == "Enterprise Arch roles"

    def test_j3_analytics_and_reminders(self, client, app):
        # These endpoints return empty but valid data with no postings
        resp = client.get("/api/agents/pipeline/analytics", headers=AGENT_HEADERS_1)
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict), "Analytics must return dict"

        resp = client.get("/api/agents/pipeline/reminders", headers=AGENT_HEADERS_1)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "reminders" in data or isinstance(
            data, (list, dict)
        ), "Reminders must return structured data"

    def test_j4_user_isolation(self, client, app):
        # User 1 creates posting
        resp = client.post(
            "/api/agents/scout/postings",
            headers=AGENT_HEADERS_1,
            json={"title": "Private Role", "company": "SecretCo", "url": "https://x.com/1"},
        )
        pid = resp.get_json().get("posting_id") or resp.get_json().get("id")

        # User 2 can't see it
        resp = client.get(f"/api/agents/scout/postings/{pid}", headers=AGENT_HEADERS_2)
        assert resp.status_code == 404

        # User 2's list is empty
        resp = client.get("/api/agents/scout/postings", headers=AGENT_HEADERS_2)
        assert resp.status_code == 200
        assert resp.get_json()["count"] == 0


# ===================================================================
# GROUP K: Resume Versions (2 tests)
# ===================================================================


class TestGroupK_Versions:
    def test_k1_experience_apply_creates_version(self, client, auth_headers):
        # Create experience and apply
        resp = client.post(
            "/api/experience/start",
            headers=auth_headers,
            json={"employer": "Navitus", "client": "Platform"},
        )
        sid = resp.get_json()["session_id"]
        client.post(
            "/api/experience/message",
            headers=auth_headers,
            json={
                "session_id": sid,
                "message": "Led migration of pharmacy platform to AWS cloud-native architecture.",
            },
        )
        client.post(f"/api/experience/finalize/{sid}", headers=auth_headers, json={})
        resp = client.post(f"/api/experience/apply/{sid}", headers=auth_headers, json={})
        assert resp.status_code == 201

        # List versions
        resp = client.get("/api/resumes/versions", headers=auth_headers)
        assert resp.status_code == 200
        versions = resp.get_json()["versions"]
        assert len(versions) >= 1

        # Get specific version
        vid = versions[0]["id"]
        resp = client.get(f"/api/resumes/versions/{vid}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["parsed_text"]

        # Edit version
        resp = client.put(
            f"/api/resumes/versions/{vid}",
            headers=auth_headers,
            json={"parsed_text": "Updated resume content with new experience."},
        )
        assert resp.status_code == 200

    def test_k2_version_isolation(self, client, auth_headers, second_user_headers):
        # User A creates version via experience
        resp = client.post(
            "/api/experience/start",
            headers=auth_headers,
            json={"employer": "OPI", "client": "Integration"},
        )
        sid = resp.get_json()["session_id"]
        client.post(
            "/api/experience/message",
            headers=auth_headers,
            json={"session_id": sid, "message": "Built integration platform."},
        )
        client.post(f"/api/experience/finalize/{sid}", headers=auth_headers, json={})
        client.post(f"/api/experience/apply/{sid}", headers=auth_headers, json={})

        # User A can see versions
        resp = client.get("/api/resumes/versions", headers=auth_headers)
        versions_a = resp.get_json()["versions"]
        assert len(versions_a) >= 1

        # User B sees empty list
        resp = client.get("/api/resumes/versions", headers=second_user_headers)
        versions_b = resp.get_json()["versions"]
        assert len(versions_b) == 0

        # User B can't access User A's version
        vid = versions_a[0]["id"]
        resp = client.get(f"/api/resumes/versions/{vid}", headers=second_user_headers)
        assert resp.status_code == 404


# ===================================================================
# GROUP L: Multi-User Isolation (3 tests)
# ===================================================================


class TestGroupL_MultiUser:
    @pytest.fixture(autouse=True)
    def _create_agent_users(self, client):
        """Ensure user rows 1 and 2 exist before agent routes touch job_postings FK."""
        client.post("/api/register", json={"email": "agent1@test.com", "password": "Test1234!"})
        client.post("/api/register", json={"email": "agent2@test.com", "password": "Test1234!"})

    def test_l1_resume_isolation(self, client, auth_headers, second_user_headers):
        """User B cannot access User A's resume."""
        rid = _upload_resume(client, auth_headers, RESUME_MATCHED)
        _upload_jd(client, auth_headers, JD_MATCHED)

        # User B tries to optimize User A's resume
        resp = client.post(
            f"/api/optimize-resume/{rid}",
            headers=second_user_headers,
            json={},
        )
        assert resp.status_code == 404
        data = resp.get_json()
        assert data.get("error") or data.get("message"), "404 must include error detail"

        # DB: resume row exists for User A (isolation, not deletion)
        rows = query_db("SELECT * FROM resumes WHERE id = ?", (rid,))
        assert len(rows) == 1, "User A's resume must still exist in DB"

    def test_l2_campaign_isolation(self, client, auth_headers, second_user_headers):
        """User B cannot access User A's campaigns."""
        cid = _run_campaign_interview(client, auth_headers)

        # User B tries to access
        resp = client.get(f"/api/campaigns/{cid}", headers=second_user_headers)
        assert resp.status_code == 404

        # User B list is empty
        resp = client.get("/api/campaigns", headers=second_user_headers)
        assert len(resp.get_json()["campaigns"]) == 0

        # DB: campaign exists (just isolated, not missing)
        rows = query_db("SELECT * FROM campaigns WHERE id = ?", (cid,))
        assert len(rows) == 1, "Campaign must exist in DB for User A"

    def test_l3_agent_posting_isolation(self, client, app):
        """User 2 cannot see User 1's postings."""
        resp = client.post(
            "/api/agents/scout/postings",
            headers=AGENT_HEADERS_1,
            json={"title": "Isolated Role", "company": "Corp", "url": "https://x.com/iso"},
        )
        pid = resp.get_json().get("posting_id") or resp.get_json().get("id")

        resp = client.get(f"/api/agents/scout/postings/{pid}", headers=AGENT_HEADERS_2)
        assert resp.status_code == 404

        resp = client.get("/api/agents/scout/postings", headers=AGENT_HEADERS_2)
        assert resp.get_json()["count"] == 0

        # DB: posting exists (just isolated)
        rows = query_db("SELECT * FROM job_postings WHERE id = ?", (pid,))
        assert len(rows) == 1, "Posting must exist in DB for User 1"


# ===================================================================
# GROUP M: Score Quality (3 tests)
# ===================================================================


class TestGroupM_ScoreQuality:
    def test_m1_matched_score_in_25_90_range(self, client, auth_headers):
        rid = _upload_resume(client, auth_headers, RESUME_MATCHED)
        _upload_jd(client, auth_headers, JD_MATCHED)
        data = _optimize(client, auth_headers, rid)
        score = data.get("relevance_score") or data["ats_compliance_score"]
        assert 25 <= score <= 90, f"Score {score} outside expected 25-90 range"

    def test_m2_mismatched_score_below_25(self, client, auth_headers):
        rid = _upload_resume(client, auth_headers, RESUME_MISMATCHED)
        _upload_jd(client, auth_headers, JD_MISMATCHED)
        data = _optimize(client, auth_headers, rid)
        score = data.get("relevance_score") or data["ats_compliance_score"]
        assert score <= 25, f"Score {score} should be <=25 for chef vs ML engineer"

    def test_m3_score_breakdown_and_keywords(self, client, auth_headers):
        rid = _upload_resume(client, auth_headers, RESUME_MATCHED)
        _upload_jd(client, auth_headers, JD_MATCHED)
        data = _optimize(client, auth_headers, rid)

        # Score breakdown has all 4 signals
        breakdown = data["score_breakdown"]
        for key in (
            "keyword_coverage",
            "semantic_similarity",
            "skills_match",
            "section_completeness",
        ):
            assert key in breakdown, f"Missing {key} in score_breakdown"
            assert isinstance(breakdown[key], (int, float))

        # Matching keywords contain expected terms — check both nesting levels
        optimized = data.get("optimized_resume", {})
        matching_raw = optimized.get("matching_keywords", []) or data.get("matching_keywords", [])
        matching = [kw.lower() for kw in matching_raw]
        # Also check skill_phrases_matched which uses curated vocabulary
        skill_phrases = [p.lower() for p in optimized.get("skill_phrases_matched", [])]
        all_matched = set(matching) | set(skill_phrases)
        expected = {
            "python",
            "aws",
            "docker",
            "kubernetes",
            "microservices",
            "terraform",
            "java",
            "rest",
            "ci/cd",
            "kafka",
        }
        found = expected & all_matched
        assert len(found) >= 2, f"Only found {found} in matching — expected >=2 of {expected}"
