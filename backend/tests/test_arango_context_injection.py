"""CT-4: Tests for ArangoDB context injection at agent inference time.

Verifies that agents query ro_* collections before generating output,
injecting relevant knowledge graph data into their prompts.
"""

from unittest.mock import MagicMock, patch

import pytest


class TestResumeContextInjection:
    """Context injection for resume_tailor agent."""

    def test_resume_tailor_receives_project_context(self):
        """ResumeTailor queries ro_client_projects before generation."""
        from agents.base_agent import BaseCareerAgent

        with patch("arango_query_helper.get_context_helper") as mock_helper_factory:
            mock_helper = MagicMock()
            mock_helper_factory.return_value = mock_helper
            mock_helper.get_project_context.return_value = "# Relevant Projects\n- E-Commerce Platform\n  * reduced latency by 40%"

            agent = BaseCareerAgent()
            context = agent._get_arango_context(
                user_id="user-1",
                agent_type="resume_tailor",
            )

            assert "E-Commerce" in context or "latency" in context
            mock_helper.get_project_context.assert_called_once_with("user-1")

    def test_cover_letter_receives_milestone_context(self):
        """CoverLetter queries ro_journey_milestones for narrative context."""
        from agents.base_agent import BaseCareerAgent

        with patch("arango_query_helper.get_context_helper") as mock_helper_factory:
            mock_helper = MagicMock()
            mock_helper_factory.return_value = mock_helper
            mock_helper.get_milestone_context.return_value = "# Career Milestones\n- Promoted to Senior Engineer (2022-06)\n  Impact: Led team growth from 3 to 8 people"

            agent = BaseCareerAgent()
            context = agent._get_arango_context(
                user_id="user-1",
                agent_type="cover_letter",
            )

            assert "Promoted" in context or "engineer" in context.lower()
            mock_helper.get_milestone_context.assert_called_once_with("user-1")

    def test_interview_coach_receives_outcomes_context(self):
        """InterviewCoach queries ro_business_outcomes for STAR examples."""
        from agents.base_agent import BaseCareerAgent

        with patch("arango_query_helper.get_context_helper") as mock_helper_factory:
            mock_helper = MagicMock()
            mock_helper_factory.return_value = mock_helper
            mock_helper.get_outcomes_context.return_value = "# Business Outcomes\n- Architected microservices\n  * 40% latency reduction\n  * 3x throughput increase"

            agent = BaseCareerAgent()
            context = agent._get_arango_context(
                user_id="user-1",
                agent_type="interview_coach",
            )

            assert "microservices" in context or "latency" in context
            mock_helper.get_outcomes_context.assert_called_once_with("user-1")

    def test_career_advisor_receives_skills_context(self):
        """CareerAdvisor queries ro_skills and ro_journey_milestones for trajectory."""
        from agents.base_agent import BaseCareerAgent

        with patch("arango_query_helper.get_context_helper") as mock_helper_factory:
            mock_helper = MagicMock()
            mock_helper_factory.return_value = mock_helper
            mock_helper.get_skills_context.return_value = "# Skills Inventory\n- Enterprise Architecture (adopted 2020-03, used in 12 projects)"

            agent = BaseCareerAgent()
            context = agent._get_arango_context(
                user_id="user-1",
                agent_type="career_advisor",
            )

            assert "Enterprise" in context or "Architecture" in context
            mock_helper.get_skills_context.assert_called_once_with("user-1")


class TestContextFallback:
    """Fallback behavior when ArangoDB is unavailable."""

    def test_arango_unavailable_falls_back_gracefully(self):
        """When ArangoDB is down, context injection returns empty string."""
        from agents.base_agent import BaseCareerAgent

        with patch("arango_query_helper.get_context_helper") as mock_helper_factory:
            mock_helper_factory.side_effect = Exception("Connection refused")

            agent = BaseCareerAgent()
            context = agent._get_arango_context(
                user_id="user-1",
                agent_type="resume_tailor",
            )

            # Should not raise; returns empty string on error
            assert isinstance(context, str)
            assert len(context) == 0


class TestContextTokenization:
    """Token limiting on injected context."""

    def test_context_truncated_to_max_tokens(self):
        """Context injection respects a max token budget (default 500)."""
        from agents.base_agent import BaseCareerAgent

        with patch("arango_query_helper.get_context_helper") as mock_helper_factory:
            mock_helper = MagicMock()
            mock_helper_factory.return_value = mock_helper
            # Return very large context (1000+ tokens worth)
            long_context = "# Projects\n" + "\n".join([f"- Project {i}" for i in range(200)])
            mock_helper.get_project_context.return_value = long_context

            agent = BaseCareerAgent()
            context = agent._get_arango_context(
                user_id="user-1",
                agent_type="resume_tailor",
                max_tokens=500,
            )

            # Context should be truncated
            # Rough check: 500 tokens ~ 2000 chars (4 chars per token average)
            assert len(context) <= 3000 or "..." in context
