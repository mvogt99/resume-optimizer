"""Tests for analytics dashboard routes (Phase 13.4)."""

import json

import pytest
from test_helpers import AGENT_HEADERS_1, JD_TEXT, RESUME_TEXT, query_db


class TestAnalyticsOverview:
    def test_overview_empty(self, client, auth_headers):
        resp = client.get("/api/analytics/overview", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_postings"] == 0
        assert data["total_applications"] == 0
        assert data["average_match_score"] == 0
        assert data["response_rate"] == 0
        assert data["active_campaigns"] == 0
        assert data["agent_runs"] == 0
        assert isinstance(data["total_postings"], int)
        assert isinstance(data["response_rate"], (int, float))

    def test_overview_with_postings(self, client, auth_headers):
        # Create postings via scout
        client.post(
            "/api/agents/scout/postings",
            headers=AGENT_HEADERS_1,
            json={"title": "Dev", "company": "Co", "description": JD_TEXT, "location": "Remote"},
        )
        client.post(
            "/api/agents/scout/postings",
            headers=AGENT_HEADERS_1,
            json={"title": "Eng", "company": "Co2", "description": JD_TEXT, "location": "NYC"},
        )
        # DB: verify postings persisted
        rows = query_db("SELECT title FROM job_postings WHERE user_id = 1 ORDER BY title")
        assert len(rows) >= 2
        titles = [r["title"] for r in rows]
        assert titles[0] == "Dev"
        assert titles[1] == "Eng"

        resp = client.get("/api/analytics/overview", headers=auth_headers)
        data = resp.get_json()
        assert data["total_postings"] >= 2
        assert isinstance(data["average_match_score"], (int, float))
        assert isinstance(data["response_rate"], (int, float))

    def test_overview_with_feedback(self, client, auth_headers):
        # Record some feedback
        client.post(
            "/api/agents/feedback",
            headers=auth_headers,
            json={"posting_id": "test1", "outcome": "interview"},
        )
        client.post(
            "/api/agents/feedback",
            headers=auth_headers,
            json={"posting_id": "test2", "outcome": "rejected"},
        )
        # DB: verify feedback rows
        fb = query_db("SELECT outcome FROM application_feedback WHERE user_id = 1 ORDER BY outcome")
        assert len(fb) == 2
        assert fb[0]["outcome"] == "interview"
        assert fb[1]["outcome"] == "rejected"

        resp = client.get("/api/analytics/overview", headers=auth_headers)
        data = resp.get_json()
        # response_rate = (interview+offer)/(total_feedback)*100
        assert data["response_rate"] == 50.0

    def test_overview_auth_required(self, client):
        resp = client.get("/api/analytics/overview")
        assert resp.status_code == 401


class TestAnalyticsFunnel:
    def test_funnel_empty(self, client, auth_headers):
        resp = client.get("/api/analytics/funnel", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "stages" in data
        assert "conversions" in data
        # All stages should be 0
        for stage in ["discovered", "bookmarked", "tailored", "applied"]:
            assert data["stages"][stage] == 0

    def test_funnel_conversion_rates(self, client, auth_headers):
        # Insert postings with different statuses directly
        import sqlite3

        import models

        conn = models.get_db_connection()
        for status in [
            "discovered",
            "discovered",
            "discovered",
            "bookmarked",
            "bookmarked",
            "applied",
        ]:
            conn.execute(
                "INSERT INTO job_postings (user_id, title, company, description, status, match_score) "
                "VALUES (1, 'Job', 'Co', 'desc', ?, 75)",
                (status,),
            )
        conn.commit()
        conn.close()
        # DB: verify postings seeded correctly
        rows = query_db("SELECT status FROM job_postings WHERE user_id = 1")
        assert len(rows) == 6

        resp = client.get("/api/analytics/funnel", headers=auth_headers)
        data = resp.get_json()
        assert data["stages"]["discovered"] == 3
        assert data["stages"]["bookmarked"] == 2
        assert data["stages"]["applied"] == 1
        # Conversion: discovered -> bookmarked = 2/3 = 66.7%
        conv = {c["from"]: c for c in data["conversions"]}
        assert conv["discovered"]["to"] == "bookmarked"
        assert conv["discovered"]["conversion_rate"] == 66.7

    def test_funnel_all_stages_present(self, client, auth_headers):
        resp = client.get("/api/analytics/funnel", headers=auth_headers)
        data = resp.get_json()
        expected_stages = [
            "discovered",
            "bookmarked",
            "tailored",
            "applied",
            "phone_screen",
            "interview",
            "offered",
            "accepted",
        ]
        for stage in expected_stages:
            assert stage in data["stages"]
        # Empty state: all stages should be 0
        assert data["stages"]["discovered"] == 0
        assert data["stages"]["accepted"] == 0

    def test_funnel_conversions_count(self, client, auth_headers):
        resp = client.get("/api/analytics/funnel", headers=auth_headers)
        data = resp.get_json()
        # 8 stages = 7 conversions
        assert len(data["conversions"]) == 7
        # First conversion should be discovered → bookmarked
        assert data["conversions"][0]["from"] == "discovered"
        assert data["conversions"][0]["to"] == "bookmarked"


class TestScoreTrends:
    def test_trends_empty(self, client, auth_headers):
        resp = client.get("/api/analytics/score-trends", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["trends"] == []

    def test_trends_with_data(self, client, auth_headers):
        import sqlite3

        import models

        conn = models.get_db_connection()
        conn.execute(
            "INSERT INTO job_postings (user_id, title, company, description, status, match_score, discovered_at) "
            "VALUES (1, 'Dev', 'Co', 'desc', 'discovered', 85, '2026-01-15 10:00:00')"
        )
        conn.execute(
            "INSERT INTO job_postings (user_id, title, company, description, status, match_score, discovered_at) "
            "VALUES (1, 'Eng', 'Co2', 'desc', 'discovered', 75, '2026-01-15 11:00:00')"
        )
        conn.commit()
        conn.close()
        # DB: verify postings seeded
        rows = query_db(
            "SELECT match_score FROM job_postings WHERE user_id = 1 ORDER BY match_score"
        )
        assert len(rows) == 2
        assert rows[0]["match_score"] == 75
        assert rows[1]["match_score"] == 85

        resp = client.get("/api/analytics/score-trends", headers=auth_headers)
        data = resp.get_json()
        assert len(data["trends"]) >= 1
        assert data["trends"][0]["avg_score"] == 80.0
        assert data["trends"][0]["count"] == 2


class TestSkillsDemand:
    def test_skills_empty(self, client, auth_headers):
        resp = client.get("/api/analytics/skills-demand", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["skills"] == []
        assert data["total_postings_analyzed"] == 0

    def test_skills_aggregation(self, client, auth_headers):
        import sqlite3

        import models

        conn = models.get_db_connection()
        conn.execute(
            "INSERT INTO job_postings (user_id, title, company, description, status, match_score, skills_missing) "
            "VALUES (1, 'Dev', 'Co', 'desc', 'discovered', 80, ?)",
            (json.dumps(["Python", "Docker", "Kubernetes"]),),
        )
        conn.execute(
            "INSERT INTO job_postings (user_id, title, company, description, status, match_score, skills_missing) "
            "VALUES (1, 'Eng', 'Co2', 'desc', 'discovered', 70, ?)",
            (json.dumps(["Python", "AWS"]),),
        )
        conn.commit()
        conn.close()
        # DB: verify postings with skills_missing
        rows = query_db("SELECT skills_missing FROM job_postings WHERE user_id = 1")
        assert len(rows) == 2

        resp = client.get("/api/analytics/skills-demand", headers=auth_headers)
        data = resp.get_json()
        assert data["total_postings_analyzed"] == 2
        skill_map = {s["skill"]: s["demand_count"] for s in data["skills"]}
        assert skill_map["python"] == 2
        assert skill_map["docker"] == 1
        assert skill_map["aws"] == 1

    def test_skills_top_20_limit(self, client, auth_headers):
        import sqlite3

        import models

        conn = models.get_db_connection()
        # Insert 25 unique skills
        skills = [f"skill_{i}" for i in range(25)]
        conn.execute(
            "INSERT INTO job_postings (user_id, title, company, description, status, match_score, skills_missing) "
            "VALUES (1, 'Dev', 'Co', 'desc', 'discovered', 80, ?)",
            (json.dumps(skills),),
        )
        conn.commit()
        conn.close()

        resp = client.get("/api/analytics/skills-demand", headers=auth_headers)
        data = resp.get_json()
        assert len(data["skills"]) <= 20

    def test_skills_demand_new_fields(self, client, auth_headers):
        """Phase 17.06: enhanced response includes strengths, all_skills, percentages."""
        import sqlite3

        import models

        conn = models.get_db_connection()
        conn.execute(
            "INSERT INTO job_postings (user_id, title, company, description, status, match_score, "
            "skills_missing, skills_overlap) VALUES (1, 'Dev', 'Co', 'desc', 'discovered', 80, ?, ?)",
            (json.dumps(["Docker", "Kubernetes"]), json.dumps(["Python", "Flask"])),
        )
        conn.commit()
        conn.close()

        resp = client.get("/api/analytics/skills-demand", headers=auth_headers)
        data = resp.get_json()
        assert "skills_to_learn" in data
        assert "strengths_in_demand" in data
        assert "all_skills_by_demand" in data
        # skills_to_learn should contain Docker, Kubernetes
        learn_skills = {s["skill"] for s in data["skills_to_learn"]}
        assert "docker" in learn_skills
        # strengths_in_demand should contain Python, Flask
        strength_skills = {s["skill"] for s in data["strengths_in_demand"]}
        assert "python" in strength_skills
        # all_skills should have user_has flag
        for s in data["all_skills_by_demand"]:
            assert "user_has" in s
            assert "pct_of_postings" in s

    def test_skills_demand_backwards_compatible(self, client, auth_headers):
        """Phase 17.06: 'skills' key still present for existing consumers."""
        resp = client.get("/api/analytics/skills-demand", headers=auth_headers)
        data = resp.get_json()
        assert "skills" in data


class TestScoutSkillDemand:
    """Phase 17.06: NLP-extracted skill demand from JD descriptions."""

    def test_scout_skill_demand_empty(self, client, auth_headers):
        resp = client.get("/api/agents/scout/skill-demand", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["skills"] == []
        assert data["total_postings"] == 0

    def test_scout_skill_demand_extracts_from_jd(self, client, auth_headers):
        import sqlite3
        import uuid

        import models

        conn = models.get_db_connection()
        conn.execute(
            "INSERT INTO job_postings (id, user_id, title, company, description, status, match_score, "
            "skills_missing, skills_overlap, url, source, location) "
            "VALUES (?, 1, 'Senior Dev', 'BigCo', "
            "'Python developer with experience in Docker, Kubernetes, and AWS cloud services', "
            "'discovered', 80, '[]', '[]', 'https://x.com', 'test', 'NYC')",
            (str(uuid.uuid4()),),
        )
        conn.commit()
        conn.close()

        resp = client.get("/api/agents/scout/skill-demand", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_postings"] >= 1
        skill_names = {s["skill"] for s in data["skills"]}
        # NLP should extract at least "python" from the description
        assert "python" in skill_names or any("python" in s for s in skill_names)

    def test_scout_skill_demand_has_coverage(self, client, auth_headers):
        resp = client.get("/api/agents/scout/skill-demand", headers=auth_headers)
        data = resp.get_json()
        assert "coverage_pct" in data
        assert "user_skills_count" in data

    def test_scout_skill_demand_requires_auth(self, client):
        resp = client.get("/api/agents/scout/skill-demand")
        assert resp.status_code == 401


class TestAgentUsage:
    def test_agent_usage_empty(self, client, auth_headers):
        resp = client.get("/api/analytics/agent-usage", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["agents"] == []

    def test_agent_usage_with_runs(self, client, auth_headers):
        import sqlite3

        import models

        conn = models.get_db_connection()
        conn.execute(
            "INSERT INTO agent_runs (user_id, agent_type, status, duration_ms) "
            "VALUES (1, 'scout', 'completed', 1500)"
        )
        conn.execute(
            "INSERT INTO agent_runs (user_id, agent_type, status, duration_ms) "
            "VALUES (1, 'scout', 'completed', 2500)"
        )
        conn.execute(
            "INSERT INTO agent_runs (user_id, agent_type, status, duration_ms) "
            "VALUES (1, 'scout', 'failed', 500)"
        )
        conn.execute(
            "INSERT INTO agent_runs (user_id, agent_type, status, duration_ms) "
            "VALUES (1, 'tailor', 'completed', 3000)"
        )
        conn.commit()
        conn.close()

        # DB: verify agent_runs seeded correctly
        rows = query_db(
            "SELECT agent_type, status FROM agent_runs WHERE user_id = 1 ORDER BY agent_type, status"
        )
        assert len(rows) == 4
        scout_rows = [r for r in rows if r["agent_type"] == "scout"]
        assert len(scout_rows) == 3

        resp = client.get("/api/analytics/agent-usage", headers=auth_headers)
        data = resp.get_json()
        assert len(data["agents"]) == 2
        scout = next(a for a in data["agents"] if a["agent_type"] == "scout")
        assert scout["total_runs"] == 3
        assert scout["success_count"] == 2
        assert scout["failed_count"] == 1
        assert scout["success_rate"] == 66.7
        assert scout["avg_duration_ms"] > 0


class TestFeedbackSummary:
    def test_feedback_summary_empty(self, client, auth_headers):
        resp = client.get("/api/analytics/feedback-summary", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["distribution"] == []
        assert data["total"] == 0

    def test_feedback_summary_with_data(self, client, auth_headers):
        for outcome in ["interview", "rejected", "rejected", "ghosted"]:
            client.post(
                "/api/agents/feedback",
                headers=auth_headers,
                json={"posting_id": "test", "outcome": outcome},
            )

        # DB: verify feedback persisted
        fb = query_db("SELECT COUNT(*) as cnt FROM application_feedback WHERE user_id = 1")
        assert fb[0]["cnt"] == 4

        resp = client.get("/api/analytics/feedback-summary", headers=auth_headers)
        data = resp.get_json()
        assert data["total"] == 4
        dist_map = {d["outcome"]: d for d in data["distribution"]}
        assert dist_map["rejected"]["count"] == 2
        assert dist_map["rejected"]["percentage"] == 50.0
        assert dist_map["interview"]["count"] == 1
        assert dist_map["ghosted"]["count"] == 1

    def test_feedback_summary_percentages_sum_to_100(self, client, auth_headers):
        for outcome in ["interview", "offer", "rejected", "ghosted"]:
            client.post(
                "/api/agents/feedback",
                headers=auth_headers,
                json={"posting_id": "t", "outcome": outcome},
            )

        resp = client.get("/api/analytics/feedback-summary", headers=auth_headers)
        data = resp.get_json()
        total_pct = sum(d["percentage"] for d in data["distribution"])
        assert abs(total_pct - 100.0) < 0.5  # Allow rounding


class TestFeedbackAnalysis:
    """Phase 17.05: Feedback loop — outcomes → skill correlation → insights."""

    def _seed_postings_and_feedback(self, client, auth_headers):
        """Insert postings with skills data and feedback outcomes."""
        import sqlite3
        import uuid

        import models

        conn = models.get_db_connection()
        # Posting 1: rejected, missing Docker + Kubernetes
        pid1 = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO job_postings (id, user_id, title, company, description, status, "
            "match_score, skills_missing, skills_overlap, url, source, location) "
            "VALUES (?, 1, 'DevOps Eng', 'CloudCo', 'DevOps role', 'applied', 70, ?, ?, 'https://x.com', 'test', 'NYC')",
            (pid1, json.dumps(["docker", "kubernetes"]), json.dumps(["python", "linux"])),
        )
        # Posting 2: rejected, missing Docker + AWS
        pid2 = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO job_postings (id, user_id, title, company, description, status, "
            "match_score, skills_missing, skills_overlap, url, source, location) "
            "VALUES (?, 1, 'SRE', 'InfraCo', 'SRE role', 'applied', 60, ?, ?, 'https://y.com', 'test', 'SF')",
            (pid2, json.dumps(["docker", "aws"]), json.dumps(["python"])),
        )
        # Posting 3: interview, overlap Python + Flask
        pid3 = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO job_postings (id, user_id, title, company, description, status, "
            "match_score, skills_missing, skills_overlap, url, source, location) "
            "VALUES (?, 1, 'Backend Dev', 'WebCo', 'Backend role', 'interview', 85, ?, ?, 'https://z.com', 'test', 'Remote')",
            (pid3, json.dumps([]), json.dumps(["python", "flask"])),
        )
        conn.commit()

        # Record outcomes
        conn.execute(
            "INSERT INTO application_feedback (user_id, posting_id, outcome) VALUES (1, ?, 'rejected')",
            (pid1,),
        )
        conn.execute(
            "INSERT INTO application_feedback (user_id, posting_id, outcome) VALUES (1, ?, 'rejected')",
            (pid2,),
        )
        conn.execute(
            "INSERT INTO application_feedback (user_id, posting_id, outcome) VALUES (1, ?, 'interview')",
            (pid3,),
        )
        conn.commit()
        conn.close()

    def test_feedback_analysis_empty(self, client, auth_headers):
        resp = client.get("/api/agents/feedback/analysis", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_analyzed"] == 0
        assert len(data["actionable_insights"]) >= 1

    def test_feedback_analysis_skill_correlations(self, client, auth_headers):
        self._seed_postings_and_feedback(client, auth_headers)
        resp = client.get("/api/agents/feedback/analysis", headers=auth_headers)
        data = resp.get_json()
        assert data["total_analyzed"] == 3

        # Docker should be top rejection-correlated skill (in 2 rejections)
        rejection_skills = {
            s["skill"]: s["rejection_count"] for s in data["skills_correlated_with_rejection"]
        }
        assert "docker" in rejection_skills
        assert rejection_skills["docker"] == 2

        # Python should be success-correlated (in the interview posting)
        success_skills = {
            s["skill"]: s["success_count"] for s in data["skills_correlated_with_success"]
        }
        assert "python" in success_skills

    def test_feedback_analysis_score_vs_outcome(self, client, auth_headers):
        self._seed_postings_and_feedback(client, auth_headers)
        resp = client.get("/api/agents/feedback/analysis", headers=auth_headers)
        data = resp.get_json()

        scores = data["score_vs_outcome"]
        if "rejected" in scores and "interview" in scores:
            assert scores["interview"] > scores["rejected"]

    def test_feedback_insights_enriched(self, client, auth_headers):
        """Existing insights endpoint now includes skill correlations."""
        self._seed_postings_and_feedback(client, auth_headers)
        resp = client.get("/api/agents/feedback/insights", headers=auth_headers)
        data = resp.get_json()
        # Should have the enriched fields
        assert "skills_correlated_with_rejection" in data
        assert "skills_correlated_with_success" in data

    def test_feedback_analysis_requires_auth(self, client):
        resp = client.get("/api/agents/feedback/analysis")
        assert resp.status_code == 401

    def test_skills_to_prioritize(self, client, auth_headers):
        """get_skills_to_prioritize returns skills with 2+ rejections."""
        self._seed_postings_and_feedback(client, auth_headers)
        from feedback_analyzer import get_skills_to_prioritize

        priority = get_skills_to_prioritize(1)
        # Docker appeared in 2 rejections → should be priority
        assert "docker" in priority


class TestDateRangeFiltering:
    """Test date_from/date_to query params on analytics endpoints."""

    def _seed_postings(self, client):
        import sqlite3

        import models

        conn = models.get_db_connection()
        conn.execute(
            "INSERT INTO job_postings (user_id, title, company, description, status, "
            "match_score, skills_missing, discovered_at) "
            "VALUES (1, 'Old', 'Co', 'desc', 'applied', 70, '[]', '2025-01-01')"
        )
        conn.execute(
            "INSERT INTO job_postings (user_id, title, company, description, status, "
            "match_score, skills_missing, discovered_at) "
            "VALUES (1, 'New', 'Co', 'desc', 'applied', 90, '[\"Python\"]', '2026-03-01')"
        )
        conn.commit()
        conn.close()

    def test_overview_date_from(self, client, auth_headers):
        self._seed_postings(client)
        # DB: verify both postings seeded
        rows = query_db("SELECT title FROM job_postings WHERE user_id = 1")
        assert len(rows) == 2
        resp = client.get("/api/analytics/overview?date_from=2026-01-01", headers=auth_headers)
        data = resp.get_json()
        assert data["total_postings"] == 1
        assert data["total_applications"] == 1

    def test_overview_date_to(self, client, auth_headers):
        self._seed_postings(client)
        resp = client.get("/api/analytics/overview?date_to=2025-12-31", headers=auth_headers)
        data = resp.get_json()
        assert data["total_postings"] == 1

    def test_overview_full_range(self, client, auth_headers):
        self._seed_postings(client)
        resp = client.get(
            "/api/analytics/overview?date_from=2025-01-01&date_to=2026-12-31", headers=auth_headers
        )
        data = resp.get_json()
        assert data["total_postings"] == 2

    def test_score_trends_date_filtered(self, client, auth_headers):
        self._seed_postings(client)
        # DB: verify postings exist before filtering
        rows = query_db("SELECT match_score FROM job_postings WHERE user_id = 1")
        assert len(rows) == 2
        resp = client.get("/api/analytics/score-trends?date_from=2026-01-01", headers=auth_headers)
        data = resp.get_json()
        assert len(data["trends"]) == 1
        assert data["trends"][0]["avg_score"] == 90.0

    def test_skills_demand_date_filtered(self, client, auth_headers):
        self._seed_postings(client)
        resp = client.get("/api/analytics/skills-demand?date_from=2026-01-01", headers=auth_headers)
        data = resp.get_json()
        assert data["total_postings_analyzed"] == 1
        assert any(s["skill"] == "python" for s in data["skills"])


class TestAnalyticsAuth:
    """All analytics endpoints require authentication."""

    def test_overview_no_auth(self, client):
        assert client.get("/api/analytics/overview").status_code == 401

    def test_funnel_no_auth(self, client):
        assert client.get("/api/analytics/funnel").status_code == 401

    def test_score_trends_no_auth(self, client):
        assert client.get("/api/analytics/score-trends").status_code == 401

    def test_skills_demand_no_auth(self, client):
        assert client.get("/api/analytics/skills-demand").status_code == 401

    def test_agent_usage_no_auth(self, client):
        assert client.get("/api/analytics/agent-usage").status_code == 401

    def test_feedback_summary_no_auth(self, client):
        assert client.get("/api/analytics/feedback-summary").status_code == 401


# ---------------------------------------------------------------------------
# Session Insights (Phase 17.12) — 5090-generated, expert-validated
# ---------------------------------------------------------------------------


class TestSessionInsights:
    """Cross-session optimization learning."""

    def test_insights_empty(self, client, auth_headers):
        resp = client.get("/api/sessions/insights", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_sessions"] == 0
        assert data["avg_score"] == 0
        assert data["avg_score_by_role"] == []
        assert data["top_keywords"] == []

    def test_insights_overall_stats(self, client, auth_headers):
        import sqlite3
        import uuid

        import models

        conn = models.get_db_connection()
        for name, score in [("Job A", 60), ("Job B", 70), ("Job C", 80)]:
            conn.execute(
                "INSERT INTO job_sessions (id, user_id, session_name, ats_score, "
                "optimization_result_json, status) VALUES (?, 1, ?, ?, '{}', 'optimized')",
                (str(uuid.uuid4()), name, score),
            )
        conn.commit()
        conn.close()

        resp = client.get("/api/sessions/insights", headers=auth_headers)
        data = resp.get_json()
        assert data["total_sessions"] == 3
        assert data["avg_score"] == 70.0
        assert data["max_score"] == 80
        assert data["min_score"] == 60

    def test_insights_by_role(self, client, auth_headers):
        import sqlite3
        import uuid

        import models

        conn = models.get_db_connection()
        for name, score in [
            ("Senior Engineer @ BigCo", 85),
            ("Lead Architect @ X", 75),
            ("Staff Engineer @ Y", 90),
        ]:
            conn.execute(
                "INSERT INTO job_sessions (id, user_id, session_name, ats_score, "
                "optimization_result_json, status) VALUES (?, 1, ?, ?, '{}', 'optimized')",
                (str(uuid.uuid4()), name, score),
            )
        conn.commit()
        conn.close()

        resp = client.get("/api/sessions/insights", headers=auth_headers)
        data = resp.get_json()
        role_map = {r["role"]: r for r in data["avg_score_by_role"]}
        assert "engineer" in role_map
        assert "architect" in role_map
        # Engineer has 2 sessions (85 + 90) / 2 = 87.5
        assert role_map["engineer"]["avg_score"] == 87.5
        assert role_map["engineer"]["count"] == 2

    def test_insights_top_keywords(self, client, auth_headers):
        import sqlite3
        import uuid

        import models

        conn = models.get_db_connection()
        for name in ["Job A", "Job B"]:
            opt = json.dumps({"matching_keywords": ["python", "sql", "django"]})
            conn.execute(
                "INSERT INTO job_sessions (id, user_id, session_name, ats_score, "
                "optimization_result_json, status) VALUES (?, 1, ?, 70, ?, 'optimized')",
                (str(uuid.uuid4()), name, opt),
            )
        conn.commit()
        conn.close()

        resp = client.get("/api/sessions/insights", headers=auth_headers)
        data = resp.get_json()
        keywords = [kw["keyword"] for kw in data["top_keywords"]]
        assert "python" in keywords
        assert "sql" in keywords
        # Each appears in 2 sessions
        kw_map = {kw["keyword"]: kw["count"] for kw in data["top_keywords"]}
        assert kw_map["python"] == 2

    def test_insights_auth_required(self, client):
        resp = client.get("/api/sessions/insights")
        assert resp.status_code == 401
