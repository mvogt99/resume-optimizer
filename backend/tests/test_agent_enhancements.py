"""Tests for Phase 13.5 agent enhancements — prep sheet, market insights, feedback analysis."""

import json

import pytest
from test_helpers import AGENT_HEADERS_1, JD_TEXT, RESUME_TEXT, query_db


class TestPrepSheet:
    def _create_posting(self, client):
        resp = client.post(
            "/api/agents/scout/postings",
            headers=AGENT_HEADERS_1,
            json={
                "title": "Senior Architect",
                "company": "TechCo",
                "description": JD_TEXT,
                "location": "Remote",
            },
        )
        data = resp.get_json()
        return data.get("id") or data.get("posting_id")

    def test_prep_sheet_returns_200(self, client, auth_headers):
        pid = self._create_posting(client)
        resp = client.post(f"/api/agents/coach/prep-sheet/{pid}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["posting_id"] == str(pid)
        assert data["title"] == "Senior Architect"
        assert data["company"] == "TechCo"
        # DB: verify posting exists
        rows = query_db("SELECT title, company FROM job_postings WHERE id = ?", (pid,))
        assert len(rows) == 1
        assert rows[0]["title"] == "Senior Architect"
        assert rows[0]["company"] == "TechCo"

    def test_prep_sheet_contains_sections(self, client, auth_headers):
        pid = self._create_posting(client)
        resp = client.post(f"/api/agents/coach/prep-sheet/{pid}", headers=auth_headers)
        data = resp.get_json()
        assert "prep_data" in data
        assert "star_examples" in data
        assert "talking_points" in data
        assert isinstance(data["star_examples"], list)
        assert isinstance(data["talking_points"], list)

    def test_prep_sheet_posting_not_found(self, client, auth_headers):
        resp = client.post("/api/agents/coach/prep-sheet/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_prep_sheet_auth_required(self, client):
        resp = client.post("/api/agents/coach/prep-sheet/1")
        assert resp.status_code == 401


class TestMarketInsights:
    def test_market_insights_empty(self, client, auth_headers):
        resp = client.get("/api/agents/advisor/market-insights", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_postings_analyzed"] == 0
        assert data["most_demanded_skills"] == []
        assert isinstance(data["recommendations"], list)

    def test_market_insights_with_data(self, client, auth_headers):
        import sqlite3

        import models

        conn = models.get_db_connection()
        conn.execute(
            "INSERT INTO job_postings (user_id, title, company, description, status, "
            "match_score, skills_missing, skills_overlap) "
            "VALUES (1, 'Dev', 'Co', 'desc', 'discovered', 80, ?, ?)",
            (json.dumps(["Python", "Docker"]), json.dumps(["Java", "SQL"])),
        )
        conn.execute(
            "INSERT INTO job_postings (user_id, title, company, description, status, "
            "match_score, skills_missing, skills_overlap) "
            "VALUES (1, 'Eng', 'Co2', 'desc', 'discovered', 70, ?, ?)",
            (json.dumps(["Python", "Kubernetes"]), json.dumps(["Java"])),
        )
        conn.commit()
        conn.close()

        # DB: verify seeded data persisted
        rows = query_db("SELECT COUNT(*) as cnt FROM job_postings WHERE user_id = 1")
        assert rows[0]["cnt"] == 2

        resp = client.get("/api/agents/advisor/market-insights", headers=auth_headers)
        data = resp.get_json()
        assert data["total_postings_analyzed"] == 2
        # Python appears in 2 postings as missing
        demanded = {s["skill"]: s["count"] for s in data["most_demanded_skills"]}
        assert demanded.get("python") == 2
        assert demanded.get("docker") == 1
        # Java appears in overlap (skills user has)
        have = {s["skill"]: s["count"] for s in data["skills_you_have"]}
        assert have.get("java") == 2

    def test_market_insights_skills_gap(self, client, auth_headers):
        import sqlite3

        import models

        conn = models.get_db_connection()
        conn.execute(
            "INSERT INTO job_postings (user_id, title, company, description, status, "
            "match_score, skills_missing, skills_overlap) "
            "VALUES (1, 'Dev', 'Co', 'desc', 'discovered', 80, ?, ?)",
            (json.dumps(["Rust", "Go"]), json.dumps(["Python"])),
        )
        conn.commit()
        conn.close()

        resp = client.get("/api/agents/advisor/market-insights", headers=auth_headers)
        data = resp.get_json()
        # Rust and Go are demanded but user doesn't have them
        assert "rust" in data["skills_gap"] or "go" in data["skills_gap"]

    def test_market_insights_auth_required(self, client):
        resp = client.get("/api/agents/advisor/market-insights")
        assert resp.status_code == 401


class TestFeedbackAnalysis:
    def test_feedback_analysis_empty(self, client, auth_headers):
        resp = client.get("/api/agents/advisor/feedback-analysis", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_applications"] == 0
        assert isinstance(data["recommendations"], list)

    def test_feedback_analysis_with_data(self, client, auth_headers):
        for outcome in ["interview", "rejected", "rejected", "ghosted", "offer"]:
            client.post(
                "/api/agents/feedback",
                headers=auth_headers,
                json={"posting_id": "test", "outcome": outcome},
            )

        # DB: verify feedback records persisted
        rows = query_db("SELECT COUNT(*) as cnt FROM application_feedback WHERE user_id = 1")
        assert rows[0]["cnt"] == 5

        resp = client.get("/api/agents/advisor/feedback-analysis", headers=auth_headers)
        data = resp.get_json()
        assert data["total_applications"] == 5
        assert data["outcome_distribution"]["interview"] == 1
        assert data["outcome_distribution"]["rejected"] == 2
        assert data["outcome_distribution"]["offer"] == 1

    def test_feedback_analysis_ghosted_warning(self, client, auth_headers):
        # Make majority ghosted
        for _ in range(6):
            client.post(
                "/api/agents/feedback",
                headers=auth_headers,
                json={"posting_id": "t", "outcome": "ghosted"},
            )
        for _ in range(2):
            client.post(
                "/api/agents/feedback",
                headers=auth_headers,
                json={"posting_id": "t", "outcome": "interview"},
            )

        resp = client.get("/api/agents/advisor/feedback-analysis", headers=auth_headers)
        data = resp.get_json()
        # Should recommend following up
        assert any("follow" in r.lower() for r in data["recommendations"])

    def test_feedback_analysis_patterns(self, client, auth_headers):
        # Create postings with different scores
        import sqlite3

        import models

        conn = models.get_db_connection()
        # High score posting that got interview
        conn.execute(
            "INSERT INTO job_postings (id, user_id, title, company, description, status, match_score) "
            "VALUES ('9001', 1, 'Good', 'Co', 'desc', 'applied', 90)"
        )
        conn.execute(
            "INSERT INTO application_feedback (user_id, posting_id, outcome) "
            "VALUES (1, 9001, 'interview')"
        )
        # Low score posting that got rejected
        conn.execute(
            "INSERT INTO job_postings (id, user_id, title, company, description, status, match_score) "
            "VALUES ('9002', 1, 'Bad', 'Co', 'desc', 'applied', 40)"
        )
        conn.execute(
            "INSERT INTO application_feedback (user_id, posting_id, outcome) "
            "VALUES (1, 9002, 'rejected')"
        )
        conn.commit()
        conn.close()

        # DB: verify seeded postings and feedback
        rows = query_db("SELECT match_score FROM job_postings WHERE id IN ('9001', '9002') ORDER BY id")
        assert len(rows) == 2
        assert rows[0]["match_score"] == 90
        assert rows[1]["match_score"] == 40
        fb_rows = query_db(
            "SELECT outcome FROM application_feedback WHERE user_id = 1 ORDER BY posting_id"
        )
        assert len(fb_rows) == 2

        resp = client.get("/api/agents/advisor/feedback-analysis", headers=auth_headers)
        data = resp.get_json()
        assert data["total_applications"] >= 2
        assert isinstance(data["success_patterns"], list)

    def test_feedback_analysis_auth_required(self, client):
        resp = client.get("/api/agents/advisor/feedback-analysis")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Salary Intelligence (Phase 17.08)
# ---------------------------------------------------------------------------


class TestSalaryInsights:
    def test_salary_empty(self, client, auth_headers):
        resp = client.get("/api/agents/advisor/salary-insights", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["salary_data_available"] is False
        assert data["postings_with_salary"] == 0
        assert "negotiation_points" in data

    def test_salary_with_data(self, client, auth_headers):
        import sqlite3
        import uuid

        import models

        conn = models.get_db_connection()
        for title, company, smin, smax in [
            ("Senior Engineer", "BigCo", 150000, 200000),
            ("Staff Engineer", "MegaCorp", 180000, 250000),
            ("Lead Developer", "StartupInc", 130000, 170000),
        ]:
            conn.execute(
                "INSERT INTO job_postings (id, user_id, title, company, description, "
                "status, match_score, salary_min, salary_max, skills_missing, skills_overlap, "
                "url, source, location) "
                "VALUES (?, 1, ?, ?, 'desc', 'discovered', 75, ?, ?, '[]', '[]', 'https://x.com', 'test', 'NYC')",
                (str(uuid.uuid4()), title, company, smin, smax),
            )
        conn.commit()
        conn.close()

        resp = client.get("/api/agents/advisor/salary-insights", headers=auth_headers)
        data = resp.get_json()
        assert data["salary_data_available"] is True
        assert data["postings_with_salary"] == 3
        assert data["overall"]["min"] == 130000
        assert data["overall"]["max"] == 250000
        assert len(data["by_role"]) >= 1
        assert len(data["top_paying"]) >= 1
        # Top paying should be Staff Engineer (250k max)
        assert data["top_paying"][0]["company"] == "MegaCorp"

    def test_salary_negotiation_points(self, client, auth_headers):
        import sqlite3
        import uuid

        import models

        conn = models.get_db_connection()
        conn.execute(
            "INSERT INTO job_postings (id, user_id, title, company, description, "
            "status, match_score, salary_min, salary_max, skills_missing, skills_overlap, "
            "url, source, location) "
            "VALUES (?, 1, 'Dev', 'Co', 'desc', 'discovered', 80, 100000, 150000, '[]', '[]', 'https://x.com', 'test', 'NYC')",
            (str(uuid.uuid4()),),
        )
        conn.commit()
        conn.close()

        resp = client.get("/api/agents/advisor/salary-insights", headers=auth_headers)
        data = resp.get_json()
        assert len(data["negotiation_points"]) >= 1
        # Should mention market median
        assert any(
            "median" in pt.lower() or "market" in pt.lower() for pt in data["negotiation_points"]
        )

    def test_salary_auth_required(self, client):
        resp = client.get("/api/agents/advisor/salary-insights")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Pipeline Checklist (Phase 17.13) — 5090-generated, expert-validated
# ---------------------------------------------------------------------------


class TestPipelineChecklist:
    """Ready-to-apply checklist per posting."""

    def _insert_posting(self, user_id=1):
        import sqlite3
        import uuid

        import models

        pid = str(uuid.uuid4())
        conn = models.get_db_connection()
        conn.execute(
            "INSERT INTO job_postings (id, user_id, title, company, description, status, "
            "match_score, skills_missing, skills_overlap, url, source, location) "
            "VALUES (?, ?, 'Dev', 'Co', 'desc', 'applied', 80, '[]', '[]', 'https://x.com', 'test', 'NYC')",
            (pid, user_id),
        )
        conn.commit()
        conn.close()
        return pid

    def test_checklist_empty(self, client, auth_headers):
        pid = self._insert_posting()
        resp = client.get(f"/api/agents/pipeline/{pid}/checklist", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["posting_id"] == pid
        assert data["title"] == "Dev"
        assert len(data["checklist"]) == 4
        # Resume, Cover Letter, Interview Prep should all be false
        non_linkedin = [c for c in data["checklist"] if c["item"] != "LinkedIn Profile"]
        assert all(c["done"] is False for c in non_linkedin)
        assert data["completion_pct"] <= 25  # at most LinkedIn cached

    def test_checklist_with_tailored_resume(self, client, auth_headers):
        import sqlite3

        import models

        pid = self._insert_posting()
        conn = models.get_db_connection()
        conn.execute(
            "INSERT INTO resume_versions (user_id, source, source_id, file_name, parsed_text, metadata_json) "
            "VALUES (1, 'agent_tailor', ?, 'Tailored', 'text', ?)",
            (pid, json.dumps({"ats_score": 82})),
        )
        conn.commit()
        conn.close()

        resp = client.get(f"/api/agents/pipeline/{pid}/checklist", headers=auth_headers)
        data = resp.get_json()
        resume_item = next(c for c in data["checklist"] if c["item"] == "Resume Tailored")
        assert resume_item["done"] is True
        assert "82" in resume_item["detail"]

    def test_checklist_not_found(self, client, auth_headers):
        resp = client.get("/api/agents/pipeline/fake-id/checklist", headers=auth_headers)
        assert resp.status_code == 404

    def test_checklist_auth_required(self, client):
        resp = client.get("/api/agents/pipeline/fake-id/checklist")
        assert resp.status_code == 401
