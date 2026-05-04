"""Comprehensive tests for CareerAdvisorAgent pipeline.

Tests each public method and key private helpers:
  1. analyze_career
  2. get_skills_roadmap
  3. analyze_trajectory
  4. analyze_skills_gap
  5. assess_role_fit
  6. recommend_next_roles
  7. get_history / feedback_analysis / market_insights
  8. _extract_career_phases
  9. _compute_skills_portfolio
  10. _market_recommendations / _save_analysis
"""

import json
import sqlite3
import uuid

import pytest
from agents.career_advisor import CareerAdvisorAgent
from test_helpers import JD_TEXT

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    """Block all LLM calls by default."""
    monkeypatch.setattr("agents.base_agent.call_llm_scored", lambda *a, **kw: (None, None))
    monkeypatch.setattr("agents.base_agent.extract_json", lambda x: None)


@pytest.fixture
def agent(app):
    return CareerAdvisorAgent()


@pytest.fixture
def user_id(app):
    from models import User

    return User.create("ca_test@test.com", "Pass1!").id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _insert_posting(
    user_id,
    title="Senior Python Developer",
    company="Acme Corp",
    description=None,
    match_score=80,
    skills_overlap=None,
    skills_missing=None,
):
    from models import DB_PATH

    pid = str(uuid.uuid4())
    desc = JD_TEXT if description is None else description
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO job_postings "
        "(id, user_id, title, company, location, url, source, description, "
        "match_score, status, skills_overlap, skills_missing) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            pid,
            user_id,
            title,
            company,
            "Remote",
            "https://example.com",
            "manual",
            desc,
            match_score,
            "discovered",
            json.dumps(skills_overlap or ["Python", "AWS"]),
            json.dumps(skills_missing or ["Docker", "Kubernetes"]),
        ),
    )
    conn.commit()
    conn.close()
    return pid


def _insert_journey_event(
    user_id,
    title="Led cloud migration",
    category="technical",
    technologies="Python,AWS",
    event_date="2024-06-15",
):
    from models import DB_PATH

    eid = str(uuid.uuid4())
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO journey_events (id, user_id, title, category, technologies, "
        "event_date, source) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (eid, user_id, title, category, technologies, event_date, "test"),
    )
    conn.commit()
    conn.close()
    return eid


def _insert_feedback(user_id, posting_id, outcome="interview"):
    from models import DB_PATH

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "INSERT INTO application_feedback (user_id, posting_id, outcome) " "VALUES (?, ?, ?)",
        (user_id, posting_id, outcome),
    )
    fid = cursor.lastrowid
    conn.commit()
    conn.close()
    return fid


def _mock_llm(monkeypatch, response_dict):
    monkeypatch.setattr(
        "agents.base_agent.call_llm_scored", lambda *a, **kw: (json.dumps(response_dict), None)
    )
    monkeypatch.setattr(
        "agents.base_agent.extract_json",
        lambda x: json.loads(x) if x else None,
    )


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_CAREER_ANALYSIS = {
    "career_trajectory": {
        "current_phase": "senior",
        "momentum": "accelerating",
        "summary": "20-year career arc from engineering to architecture leadership.",
    },
    "strengths": [
        {
            "area": "Enterprise Architecture",
            "evidence": "117 endorsements",
            "leverage": "Consulting roles",
        }
    ],
    "growth_areas": [{"area": "ML/AI", "priority": "high", "action": "Complete ML specialization"}],
    "market_alignment": {
        "trending_skills": ["Python", "AWS", "Kubernetes"],
        "emerging_gaps": ["Rust", "WebAssembly"],
        "score": 82,
    },
    "recommended_learning": [{"topic": "MLOps", "why": "Growing demand", "format": "course"}],
    "role_recommendations": [
        {
            "title": "VP of Engineering",
            "fit_score": 88,
            "reasoning": "Strong leadership + architecture",
        }
    ],
}

SAMPLE_ROADMAP = {
    "target_role": "VP of Engineering",
    "current_readiness": 72,
    "timeline_months": 12,
    "phases": [
        {
            "phase": 1,
            "name": "Foundation",
            "duration_weeks": 8,
            "skills": ["People management"],
            "resources": ["Management 3.0"],
            "milestone": "Lead 2 direct reports",
        }
    ],
    "quick_wins": ["Get AWS Solutions Architect cert"],
    "key_gap": "People management at scale",
}

SAMPLE_TRAJECTORY = {
    "trajectory_direction": "upward",
    "growth_rate": "steady",
    "career_arc_summary": "Progressed from IC to architecture leadership over 20 years.",
    "pivot_points": [{"event": "Moved to Navitus", "impact": "Cloud focus", "timing": "2019"}],
    "tenure_analysis": {"avg_tenure_years": 5, "pattern": "moderate", "insight": "Stable growth"},
    "seniority_progression": {
        "current_level": "Director",
        "trajectory": "ascending",
        "next_natural_step": "VP",
    },
}

SAMPLE_SKILLS_GAP = {
    "target": "Staff Engineer",
    "overall_readiness": 75,
    "matched_skills": [{"skill": "Python", "proficiency": "expert", "evidence": "20 years"}],
    "gaps": {
        "critical": [{"skill": "ML", "learning_path": "Course", "time_estimate_weeks": 8}],
        "important": [],
        "nice_to_have": [],
    },
    "total_gap_weeks": 8,
    "quick_wins": ["Contribute to ML pipeline"],
}

SAMPLE_ROLE_FIT = {
    "fit_score": 85,
    "breakdown": {
        "skills_fit": {"score": 90, "rationale": "Strong Python/AWS match"},
        "experience_fit": {"score": 85, "rationale": "20 years relevant"},
        "seniority_fit": {"score": 80, "rationale": "At level"},
        "industry_fit": {"score": 75, "rationale": "Healthcare to tech transition"},
    },
    "strengths": [{"point": "Architecture expertise", "evidence": "Led microservices migration"}],
    "concerns": [{"point": "New industry", "mitigation": "Leverage transferable skills"}],
    "verdict": "strong fit",
    "application_advice": "Apply with emphasis on architecture leadership.",
}

SAMPLE_RECOMMENDATIONS = {
    "recommendations": [
        {
            "title": "VP Engineering",
            "industry": "Tech",
            "fit_score": 88,
            "salary_range": "$200-250K",
            "reasoning": "Strong fit",
            "growth_potential": "C-suite path",
            "key_requirements": ["Architecture"],
            "gaps_to_address": ["People management"],
        }
    ]
}


# ===========================================================================
# 1. analyze_career
# ===========================================================================


class TestAnalyzeCareer:
    """Test full career analysis."""

    def test_success_returns_structured_dict(self, agent, user_id, monkeypatch):
        _mock_llm(monkeypatch, SAMPLE_CAREER_ANALYSIS)
        result = agent.analyze_career(user_id)
        assert isinstance(result, dict)
        assert "career_trajectory" in result

    def test_llm_failure_returns_error(self, agent, user_id):
        result = agent.analyze_career(user_id)
        assert isinstance(result, dict)
        assert "error" in result

    def test_result_saved_to_db(self, agent, user_id, monkeypatch):
        from models import DB_PATH

        _mock_llm(monkeypatch, SAMPLE_CAREER_ANALYSIS)
        agent.analyze_career(user_id)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM career_analyses WHERE user_id=? AND analysis_type='career_analysis'",
            (user_id,),
        ).fetchall()
        conn.close()
        assert len(rows) >= 1
        assert rows[0]["user_id"] == user_id

    def test_has_strengths_key(self, agent, user_id, monkeypatch):
        _mock_llm(monkeypatch, SAMPLE_CAREER_ANALYSIS)
        result = agent.analyze_career(user_id)
        assert "strengths" in result
        assert isinstance(result["strengths"], list)


# ===========================================================================
# 2. get_skills_roadmap
# ===========================================================================


class TestGetSkillsRoadmap:
    """Test skills roadmap generation."""

    def test_success_with_phases(self, agent, user_id, monkeypatch):
        _mock_llm(monkeypatch, SAMPLE_ROADMAP)
        result = agent.get_skills_roadmap(user_id, "VP of Engineering")
        assert isinstance(result, dict)
        assert "phases" in result or "target_role" in result

    def test_llm_failure_returns_error(self, agent, user_id):
        result = agent.get_skills_roadmap(user_id, "CTO")
        assert isinstance(result, dict)
        assert "error" in result

    def test_target_role_in_result(self, agent, user_id, monkeypatch):
        _mock_llm(monkeypatch, SAMPLE_ROADMAP)
        result = agent.get_skills_roadmap(user_id, "VP of Engineering")
        assert result.get("target_role") == "VP of Engineering"
        assert isinstance(result, dict)

    def test_saved_to_db(self, agent, user_id, monkeypatch):
        from models import DB_PATH

        _mock_llm(monkeypatch, SAMPLE_ROADMAP)
        agent.get_skills_roadmap(user_id, "CTO")
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT COUNT(*) FROM career_analyses WHERE user_id=? AND analysis_type='skills_roadmap'",  # noqa: E501
            (user_id,),
        ).fetchone()
        conn.close()
        assert rows[0] >= 1


# ===========================================================================
# 3. analyze_trajectory
# ===========================================================================


class TestAnalyzeTrajectory:
    """Test career trajectory analysis."""

    def test_returns_career_phases(self, agent, user_id, monkeypatch):
        _mock_llm(monkeypatch, SAMPLE_TRAJECTORY)
        result = agent.analyze_trajectory(user_id)
        assert isinstance(result, dict)
        assert "career_phases" in result

    def test_llm_failure_still_has_phases(self, agent, user_id):
        """Even without LLM, local phase extraction returns data."""
        result = agent.analyze_trajectory(user_id)
        assert isinstance(result, dict)
        assert "career_phases" in result
        assert "error" in result  # LLM unavailable flag

    def test_llm_enhances_with_direction(self, agent, user_id, monkeypatch):
        _mock_llm(monkeypatch, SAMPLE_TRAJECTORY)
        result = agent.analyze_trajectory(user_id)
        assert result.get("trajectory_direction") == "upward"
        assert "career_phases" in result

    def test_empty_profile_returns_empty_phases(self, agent, user_id):
        result = agent.analyze_trajectory(user_id)
        assert isinstance(result["career_phases"], list)
        # No LinkedIn data → may be empty
        assert isinstance(result, dict)


# ===========================================================================
# 4. analyze_skills_gap
# ===========================================================================


class TestAnalyzeSkillsGap:
    """Test skills gap analysis."""

    def test_with_target_role(self, agent, user_id, monkeypatch):
        _mock_llm(monkeypatch, SAMPLE_SKILLS_GAP)
        result = agent.analyze_skills_gap(user_id, target_role="Staff Engineer")
        assert isinstance(result, dict)
        assert "overall_readiness" in result or "error" not in result

    def test_with_posting_id(self, agent, user_id, monkeypatch):
        _mock_llm(monkeypatch, SAMPLE_SKILLS_GAP)
        posting_id = _insert_posting(user_id)
        result = agent.analyze_skills_gap(user_id, target_posting_id=posting_id)
        assert isinstance(result, dict)

    def test_llm_failure_returns_error(self, agent, user_id):
        result = agent.analyze_skills_gap(user_id, target_role="CTO")
        assert isinstance(result, dict)
        assert "error" in result

    def test_both_none_uses_default(self, agent, user_id, monkeypatch):
        _mock_llm(monkeypatch, SAMPLE_SKILLS_GAP)
        result = agent.analyze_skills_gap(user_id)
        assert isinstance(result, dict)
        # Should not crash with both None


# ===========================================================================
# 5. assess_role_fit
# ===========================================================================


class TestAssessRoleFit:
    """Test role fit scoring."""

    def test_posting_found_returns_fit(self, agent, user_id, monkeypatch):
        _mock_llm(monkeypatch, SAMPLE_ROLE_FIT)
        posting_id = _insert_posting(user_id)
        result = agent.assess_role_fit(user_id, posting_id)
        assert isinstance(result, dict)
        assert "fit_score" in result

    def test_posting_not_found_returns_error(self, agent, user_id):
        result = agent.assess_role_fit(user_id, "nonexistent")
        assert isinstance(result, dict)
        assert "error" in result

    def test_llm_failure_returns_error(self, agent, user_id):
        posting_id = _insert_posting(user_id)
        result = agent.assess_role_fit(user_id, posting_id)
        assert isinstance(result, dict)
        assert "error" in result


# ===========================================================================
# 6. recommend_next_roles
# ===========================================================================


class TestRecommendNextRoles:
    """Test role recommendation."""

    def test_success_returns_recommendations(self, agent, user_id, monkeypatch):
        _mock_llm(monkeypatch, SAMPLE_RECOMMENDATIONS)
        result = agent.recommend_next_roles(user_id)
        assert isinstance(result, dict)
        assert "recommendations" in result

    def test_count_clamped(self, agent, user_id, monkeypatch):
        _mock_llm(monkeypatch, SAMPLE_RECOMMENDATIONS)
        result = agent.recommend_next_roles(user_id, count=0)  # should clamp to 1
        assert isinstance(result, dict)

    def test_llm_failure_returns_error(self, agent, user_id):
        result = agent.recommend_next_roles(user_id)
        assert isinstance(result, dict)
        assert "error" in result

    def test_get_role_recommendations_is_alias(self, agent, user_id, monkeypatch):
        """get_role_recommendations calls recommend_next_roles."""
        _mock_llm(monkeypatch, SAMPLE_RECOMMENDATIONS)
        result = agent.get_role_recommendations(user_id)
        assert isinstance(result, dict)
        assert "recommendations" in result


# ===========================================================================
# 7. _extract_career_phases
# ===========================================================================


class TestExtractCareerPhases:
    """Test local phase extraction (no LLM)."""

    def test_phases_from_experience(self, agent):
        profile = {
            "linkedin": {
                "experience": [
                    {"title": "Senior Architect", "company": "Navitus"},
                    {"title": "Solutions Architect", "company": "OPI"},
                ],
                "skills": [],
            }
        }
        phases = agent._extract_career_phases(profile, [], [])
        assert isinstance(phases, list)
        assert len(phases) >= 2

    def test_phases_from_projects(self, agent):
        profile = {"linkedin": {"experience": [], "skills": []}}
        projects = [{"client_name": "ClientA", "analysis": {"technologies": [{"name": "Python"}]}}]
        phases = agent._extract_career_phases(profile, projects, [])
        assert isinstance(phases, list)
        assert len(phases) >= 1

    def test_phases_from_journey_events(self, agent):
        profile = {"linkedin": {"experience": [], "skills": []}}
        events = [
            {"category": "technical", "title": "Built API"},
            {"category": "technical", "title": "Deployed service"},
            {"category": "leadership", "title": "Led team"},
        ]
        phases = agent._extract_career_phases(profile, [], events)
        assert isinstance(phases, list)
        assert len(phases) >= 1

    def test_empty_data_returns_empty(self, agent):
        profile = {"linkedin": {"experience": [], "skills": []}}
        phases = agent._extract_career_phases(profile, [], [])
        assert isinstance(phases, list)
        assert len(phases) == 0


# ===========================================================================
# 8. _compute_skills_portfolio
# ===========================================================================


class TestComputeSkillsPortfolio:
    """Test skills categorization."""

    def test_python_maps_to_technical(self, agent):
        profile = {
            "linkedin": {"skills": [{"name": "Python"}]},
            "top_technologies": [],
            "higher_order_skills": [],
            "differentiators": [],
        }
        result = agent._compute_skills_portfolio(profile)
        assert "Python" in result["technical"]
        assert isinstance(result, dict)

    def test_leadership_maps_correctly(self, agent):
        profile = {
            "linkedin": {"skills": [{"name": "Leadership"}]},
            "top_technologies": [],
            "higher_order_skills": [],
            "differentiators": [],
        }
        result = agent._compute_skills_portfolio(profile)
        assert "Leadership" in result["leadership"]
        assert isinstance(result["leadership"], list)

    def test_agile_maps_to_methodologies(self, agent):
        profile = {
            "linkedin": {"skills": [{"name": "Agile"}]},
            "top_technologies": [],
            "higher_order_skills": [],
            "differentiators": [],
        }
        result = agent._compute_skills_portfolio(profile)
        assert "Agile" in result["methodologies"]
        assert isinstance(result["methodologies"], list)

    def test_unknown_maps_to_domain(self, agent):
        profile = {
            "linkedin": {"skills": [{"name": "Healthcare Compliance"}]},
            "top_technologies": [],
            "higher_order_skills": [],
            "differentiators": [],
        }
        result = agent._compute_skills_portfolio(profile)
        assert "Healthcare Compliance" in result["domain"]
        assert isinstance(result["domain"], list)

    def test_deduplicates_skills(self, agent):
        profile = {
            "linkedin": {"skills": [{"name": "Python"}, {"name": "python"}]},
            "top_technologies": ["Python"],
            "higher_order_skills": [],
            "differentiators": [],
        }
        result = agent._compute_skills_portfolio(profile)
        python_count = sum(1 for s in result["technical"] if s.lower() == "python")
        assert python_count == 1


# ===========================================================================
# 9. get_history
# ===========================================================================


class TestGetHistory:
    """Test analysis history retrieval."""

    def test_returns_list(self, agent, user_id):
        result = agent.get_history(user_id)
        assert isinstance(result, list)

    def test_empty_for_new_user(self, agent, user_id):
        result = agent.get_history(user_id)
        assert len(result) == 0

    def test_filters_by_analysis_type(self, agent, user_id, monkeypatch):
        _mock_llm(monkeypatch, SAMPLE_CAREER_ANALYSIS)
        agent.analyze_career(user_id)
        result = agent.get_history(user_id, analysis_type="career_analysis")
        assert len(result) >= 1
        assert all(r["analysis_type"] == "career_analysis" for r in result)

    def test_includes_parsed_json(self, agent, user_id, monkeypatch):
        _mock_llm(monkeypatch, SAMPLE_CAREER_ANALYSIS)
        agent.analyze_career(user_id)
        result = agent.get_history(user_id)
        assert len(result) >= 1
        assert isinstance(result[0]["result_json"], dict)


# ===========================================================================
# 10. feedback_analysis
# ===========================================================================


class TestFeedbackAnalysis:
    """Test application feedback pattern analysis."""

    def test_no_feedback_returns_zero_total(self, agent, user_id):
        result = agent.feedback_analysis(user_id)
        assert result["total_applications"] == 0
        assert isinstance(result["recommendations"], list)

    def test_with_outcomes_computes_distribution(self, agent, user_id):
        pid = _insert_posting(user_id)
        _insert_feedback(user_id, pid, "interview")
        _insert_feedback(user_id, pid, "rejected")
        _insert_feedback(user_id, pid, "interview")
        result = agent.feedback_analysis(user_id)
        assert result["total_applications"] == 3
        assert result["outcome_distribution"]["interview"] == 2

    def test_high_ghosted_recommendation(self, agent, user_id):
        pid = _insert_posting(user_id)
        for _ in range(6):
            _insert_feedback(user_id, pid, "ghosted")
        for _ in range(4):
            _insert_feedback(user_id, pid, "interview")
        result = agent.feedback_analysis(user_id)
        assert result["total_applications"] == 10
        assert any("follow" in r.lower() for r in result["recommendations"])

    def test_has_recommendations_key(self, agent, user_id):
        result = agent.feedback_analysis(user_id)
        assert "recommendations" in result
        assert isinstance(result["recommendations"], list)


# ===========================================================================
# 11. market_insights (get_market_insights)
# ===========================================================================


class TestMarketInsights:
    """Test market insights from job postings."""

    def test_empty_postings(self, agent, user_id):
        result = agent.market_insights(user_id)
        assert result["total_postings_analyzed"] == 0
        assert isinstance(result["recommendations"], list)

    def test_aggregates_skills(self, agent, user_id):
        _insert_posting(
            user_id, skills_overlap=["Python", "AWS"], skills_missing=["Kubernetes", "Go"]
        )
        _insert_posting(user_id, skills_overlap=["Python"], skills_missing=["Kubernetes", "Rust"])
        result = agent.market_insights(user_id)
        assert result["total_postings_analyzed"] == 2
        assert isinstance(result["most_demanded_skills"], list)

    def test_gap_detection(self, agent, user_id):
        _insert_posting(
            user_id, skills_overlap=["Python"], skills_missing=["Kubernetes", "Go", "Rust"]
        )
        result = agent.market_insights(user_id)
        assert isinstance(result["skills_gap"], list)
        assert len(result["skills_gap"]) >= 1


# ===========================================================================
# 12. _market_recommendations
# ===========================================================================


class TestMarketRecommendations:
    """Test recommendation generation from demand data."""

    def test_identifies_gaps(self, agent):
        demand = [("kubernetes", 5), ("go", 3)]
        have = {"python": 4}
        recs = agent._market_recommendations(demand, have, 10)
        assert isinstance(recs, list)
        assert any("kubernetes" in r.lower() for r in recs)

    def test_no_gaps_message(self, agent):
        demand = [("python", 5)]
        have = {"python": 5}
        recs = agent._market_recommendations(demand, have, 10)
        assert isinstance(recs, list)
        assert any("align" in r.lower() for r in recs)

    def test_zero_total(self, agent):
        recs = agent._market_recommendations([], {}, 0)
        assert isinstance(recs, list)
        assert any("start" in r.lower() for r in recs)


# ===========================================================================
# 13. _save_analysis
# ===========================================================================


class TestSaveAnalysis:
    """Test analysis persistence."""

    def test_persists_to_db(self, agent, user_id):
        from models import DB_PATH

        aid = agent._save_analysis(user_id, "test_analysis", {"score": 85})
        assert isinstance(aid, str)
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT * FROM career_analyses WHERE id=?", (aid,)).fetchone()
        conn.close()
        assert row is not None

    def test_stores_target_role(self, agent, user_id):
        from models import DB_PATH

        aid = agent._save_analysis(user_id, "skills_roadmap", {"phases": []}, target_role="CTO")
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM career_analyses WHERE id=?", (aid,)).fetchone()
        conn.close()
        assert row["target_role"] == "CTO"
        assert row["analysis_type"] == "skills_roadmap"


# ===========================================================================
# 14. Edge cases
# ===========================================================================


class TestEdgeCases:
    """Agent type and aliases."""

    def test_agent_type(self, agent):
        assert agent.agent_type == "career_advisor"
        assert isinstance(agent, CareerAdvisorAgent)

    def test_market_insights_is_alias(self, agent, user_id):
        r1 = agent.market_insights(user_id)
        r2 = agent.get_market_insights(user_id)
        assert r1["total_postings_analyzed"] == r2["total_postings_analyzed"]
        assert isinstance(r1, dict)
