"""
Regression tests — Resume Interview stage progression + state machine.

Drives through all 8 stages including experience/education loops.
RTX 5090 LLM at port 8021 is live; no mocking of LLM calls.
"""

import pytest

# These tests drive a LIVE RTX 5090 at port 8021 (see the docstring above)
# and cannot pass in CI, which has no GPU and no harness. Deselected there
# via -m "not integration and not llm_required"; still run locally.
pytestmark = [pytest.mark.llm_required, pytest.mark.integration]


import time


def register_and_login(client):
    ts = int(time.time() * 1000)
    resp = client.post(
        "/api/register",
        json={
            "username": f"ri_stage_{ts}",
            "email": f"ri_s_{ts}@test.com",
            "password": "TestPass123!",
        },
    )
    assert resp.status_code == 201, resp.get_json()
    data = resp.get_json()
    return str(data["user_id"]), data.get("token", "")


def auth_headers(token, user_id):
    return {"Authorization": f"Bearer {token}", "user-id": user_id}


def start(client, uid, tok):
    resp = client.post("/api/resume-interview/start", headers=auth_headers(tok, uid))
    return resp.get_json()["session_id"]


def msg(client, sid, text, uid, tok):
    resp = client.post(
        "/api/resume-interview/message",
        json={"session_id": sid, "message": text},
        headers=auth_headers(tok, uid),
    )
    assert resp.status_code == 200
    return resp.get_json()


# ── Stage-by-stage API progression ────────────────────────────────────────────


class TestStageProgression:
    def test_welcome_to_contact(self, client):
        uid, tok = register_and_login(client)
        sid = start(client, uid, tok)
        msg(client, sid, "Alice Thompson", uid, tok)
        data = msg(client, sid, "yes", uid, tok)
        assert data["stage"] == "contact"

    def test_contact_collects_email_phone(self, client):
        uid, tok = register_and_login(client)
        sid = start(client, uid, tok)
        msg(client, sid, "Alice Thompson", uid, tok)
        msg(client, sid, "yes", uid, tok)
        data = msg(client, sid, "alice@example.com 555-867-5309", uid, tok)
        assert data["context"]["email"] == "alice@example.com"
        assert "5309" in data["context"]["phone"]

    def test_contact_to_objective(self, client):
        uid, tok = register_and_login(client)
        sid = start(client, uid, tok)
        msg(client, sid, "Alice Thompson", uid, tok)
        msg(client, sid, "yes", uid, tok)
        msg(client, sid, "alice@example.com 555-867-5309", uid, tok)
        data = msg(client, sid, "Austin, TX", uid, tok)
        assert data["stage"] == "objective"

    def test_objective_to_experience(self, client):
        uid, tok = register_and_login(client)
        sid = start(client, uid, tok)
        msg(client, sid, "Alice Thompson", uid, tok)
        msg(client, sid, "yes", uid, tok)
        msg(client, sid, "alice@example.com 555-867-5309", uid, tok)
        msg(client, sid, "Austin, TX", uid, tok)
        msg(client, sid, "I have 5 years in elementary education teaching 3rd grade", uid, tok)
        data = msg(client, sid, "I want to find a lead teacher role in a Title I school", uid, tok)
        assert data["stage"] == "experience"

    def test_experience_loop_single_job(self, client):
        uid, tok = register_and_login(client)
        sid = start(client, uid, tok)
        msg(client, sid, "Alice Thompson", uid, tok)
        msg(client, sid, "yes", uid, tok)
        msg(client, sid, "alice@example.com 555-867-5309", uid, tok)
        msg(client, sid, "Austin, TX", uid, tok)
        msg(client, sid, "elementary education, 5 years", uid, tok)
        msg(client, sid, "I want to lead a Title I classroom", uid, tok)
        msg(client, sid, "3rd Grade Teacher", uid, tok)
        msg(client, sid, "Austin ISD", uid, tok)
        msg(client, sid, "August 2019 to June 2024", uid, tok)
        msg(
            client,
            sid,
            "Taught 28 students daily\nCreated lesson plans weekly\nLed parent conferences",
            uid,
            tok,
        )  # noqa: E501
        data = msg(client, sid, "next", uid, tok)
        exp = data["context"]["experiences"][0]
        assert exp["title"] == "3rd Grade Teacher"
        assert exp["employer"] == "Austin ISD"
        assert len(exp["duties"]) >= 1

    def test_experience_loop_two_jobs(self, client):
        uid, tok = register_and_login(client)
        sid = start(client, uid, tok)
        msg(client, sid, "Bob Nguyen", uid, tok)
        msg(client, sid, "yes", uid, tok)
        msg(client, sid, "bob@example.com 555-111-2222", uid, tok)
        msg(client, sid, "Dallas, TX", uid, tok)
        msg(client, sid, "plumbing, 8 years", uid, tok)
        msg(client, sid, "Looking for journeyman plumber position", uid, tok)
        # Job 1
        msg(client, sid, "Apprentice Plumber", uid, tok)
        msg(client, sid, "Dallas Pipe Co", uid, tok)
        msg(client, sid, "2016 to 2020", uid, tok)
        msg(
            client,
            sid,
            "Installed PVC pipes\nRepaired fixtures\nPassed safety inspections",
            uid,
            tok,
        )  # noqa: E501
        msg(client, sid, "next", uid, tok)  # exp_more → exp_another
        msg(client, sid, "yes", uid, tok)  # exp_another → add another job
        # Job 2
        msg(client, sid, "Journeyman Plumber", uid, tok)
        msg(client, sid, "Metro Plumbing LLC", uid, tok)
        msg(client, sid, "2020 to present", uid, tok)
        msg(
            client,
            sid,
            "Led a crew of 3\nManaged residential installs\nReduced rework by 20%",
            uid,
            tok,
        )  # noqa: E501
        msg(client, sid, "next", uid, tok)  # exp_more → exp_another
        data = msg(client, sid, "no", uid, tok)  # done with all jobs
        assert len(data["context"]["experiences"]) == 2
        assert data["context"]["experiences"][1]["title"] == "Journeyman Plumber"
        assert data["stage"] == "education"

    def test_education_stage_data(self, client):
        uid, tok = register_and_login(client)
        sid = start(client, uid, tok)
        msg(client, sid, "Carol White", uid, tok)
        msg(client, sid, "yes", uid, tok)
        msg(client, sid, "carol@example.com 555-333-4444", uid, tok)
        msg(client, sid, "Chicago, IL", uid, tok)
        msg(client, sid, "nursing, 3 years", uid, tok)
        msg(client, sid, "Looking for RN position", uid, tok)
        msg(client, sid, "CNA", uid, tok)
        msg(client, sid, "Rush Hospital", uid, tok)
        msg(client, sid, "2021 to 2024", uid, tok)
        msg(
            client,
            sid,
            "Assisted patients with ADLs\nTook vitals every 2 hours\nCoordinated with RN staff",
            uid,
            tok,
        )  # noqa: E501
        msg(client, sid, "next", uid, tok)
        msg(client, sid, "no", uid, tok)
        msg(client, sid, "Associate of Science in Nursing", uid, tok)
        msg(client, sid, "Loyola University Chicago", uid, tok)
        data = msg(client, sid, "2021", uid, tok)
        edu = data["context"]["education"][0]
        assert edu["degree"] == "Associate of Science in Nursing"
        assert edu["school"] == "Loyola University Chicago"
        assert edu["year"] == "2021"

    def test_skills_stage_collects_skills(self, client):
        uid, tok = register_and_login(client)
        sid = start(client, uid, tok)
        msg(client, sid, "Dan Lee", uid, tok)
        msg(client, sid, "yes", uid, tok)
        msg(client, sid, "dan@example.com 555-555-6666", uid, tok)
        msg(client, sid, "Seattle, WA", uid, tok)
        msg(client, sid, "retail, 4 years", uid, tok)
        msg(client, sid, "Looking for store manager position", uid, tok)
        msg(client, sid, "Retail Sales Associate", uid, tok)
        msg(client, sid, "Target", uid, tok)
        msg(client, sid, "June 2020 to present", uid, tok)
        duties = "Assisted 50+ customers daily\nStocked shelves\nOperated POS and handled returns"
        msg(client, sid, duties, uid, tok)
        msg(client, sid, "next", uid, tok)
        msg(client, sid, "no", uid, tok)
        msg(client, sid, "High School Diploma", uid, tok)
        msg(client, sid, "Roosevelt High", uid, tok)
        msg(client, sid, "2019", uid, tok)
        data = msg(client, sid, "no", uid, tok)
        assert data["stage"] == "skills"
        skills_resp = msg(
            client,
            sid,
            "Customer service, POS systems, inventory management, bilingual Spanish",
            uid,
            tok,
        )
        ctx = skills_resp["context"]
        all_skills = (
            ctx.get("hard_skills", []) + ctx.get("soft_skills", []) + ctx.get("certifications", [])
        )  # noqa: E501
        assert len(all_skills) >= 2

    def test_review_stage_shows_finalize_flag(self, client):
        uid, tok = register_and_login(client)
        sid = start(client, uid, tok)
        msg(client, sid, "Frank Okafor", uid, tok)
        msg(client, sid, "yes", uid, tok)
        msg(client, sid, "frank@example.com 555-999-0000", uid, tok)
        msg(client, sid, "Houston, TX", uid, tok)
        msg(client, sid, "welding, 10 years", uid, tok)
        msg(client, sid, "Looking for certified welder in oil and gas", uid, tok)
        msg(client, sid, "Pipe Welder", uid, tok)
        msg(client, sid, "Gulf Welding Inc", uid, tok)
        msg(client, sid, "2014 to 2024", uid, tok)
        duties = "TIG and MIG welding on joints\nPassed 6G certification welds\nLed safety drills"
        msg(client, sid, duties, uid, tok)
        msg(client, sid, "next", uid, tok)
        msg(client, sid, "no", uid, tok)
        msg(client, sid, "Welding Certification", uid, tok)
        msg(client, sid, "Houston Community College", uid, tok)
        msg(client, sid, "2014", uid, tok)
        msg(client, sid, "no", uid, tok)
        msg(
            client,
            sid,
            "TIG welding, MIG welding, pipeline codes, OSHA 30, blueprint reading",
            uid,
            tok,
        )  # noqa: E501
        data = msg(client, sid, "skip", uid, tok)
        assert data["stage"] == "review"
        assert data["show_finalize"] is True


# ── State machine unit tests ───────────────────────────────────────────────────


class TestStageMachineUnit:
    def test_progress_info_welcome(self):
        from resume_interview_stages import progress_info

        prog = progress_info("welcome")
        assert prog["stage_index"] == 0
        assert prog["total_stages"] == 8
        assert prog["percent"] == 0

    def test_progress_info_review(self):
        from resume_interview_stages import progress_info

        prog = progress_info("review")
        assert prog["stage_index"] == 7
        assert prog["percent"] >= 85  # 7/8 stages = 87%

    def test_advance_welcome_to_contact(self):
        from resume_interview_stages import advance_stage

        ctx = {"name": "Alice", "_welcome_done": True}
        stage, sub, ei, di = advance_stage("welcome", "", "yes", ctx, 0, 0)
        assert stage == "contact"

    def test_advance_exp_title_to_employer(self):
        from resume_interview_stages import advance_stage

        ctx = {
            "experiences": [
                {"title": "Teacher", "employer": "", "start_date": "", "end_date": "", "duties": []}
            ]
        }  # noqa: E501
        stage, sub, ei, di = advance_stage("experience", "exp_title", "Teacher", ctx, 0, 0)
        assert stage == "experience"
        assert sub == "exp_employer"

    def test_advance_exp_another_yes(self):
        from resume_interview_stages import advance_stage

        exp = {
            "title": "T",
            "employer": "E",
            "start_date": "2020",
            "end_date": "2024",
            "duties": ["d1"],
        }  # noqa: E501
        ctx = {"experiences": [exp]}
        stage, sub, ei, di = advance_stage("experience", "exp_another", "yes", ctx, 0, 0)
        assert stage == "experience"
        assert sub == "exp_title"
        assert ei == 1

    def test_advance_exp_another_no_to_education(self):
        from resume_interview_stages import advance_stage

        exp = {
            "title": "T",
            "employer": "E",
            "start_date": "2020",
            "end_date": "2024",
            "duties": ["d1"],
        }  # noqa: E501
        ctx = {"experiences": [exp]}
        stage, sub, ei, di = advance_stage("experience", "exp_another", "no", ctx, 0, 0)
        assert stage == "education"

    def test_template_questions_all_stages_covered(self):
        from resume_interview_stages import get_template_response

        # Verify every stage produces a non-empty response (keys may use sub-stage names)
        ctx = {"experiences": [], "education": [], "name": "Test", "preferred_name": "Test"}
        for stage in [
            "welcome",
            "contact",
            "objective",
            "education",
            "skills",
            "optional",
            "review",
        ]:  # noqa: E501
            resp = get_template_response(stage, "", ctx, 0)
            assert (
                isinstance(resp, str) and len(resp) > 10
            ), f"No template response for stage: {stage}"  # noqa: E501
