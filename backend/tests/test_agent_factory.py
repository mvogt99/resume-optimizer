"""Test the agent factory (agents/__init__.py) — singleton getters and dispatch."""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import agents
from agents.app_tracker import ApplicationTrackerAgent
from agents.career_advisor import CareerAdvisorAgent
from agents.cover_letter import CoverLetterAgent
from agents.interview_coach import InterviewCoachAgent
from agents.job_scout import JobScoutAgent
from agents.resume_tailor import ResumeTailorAgent


class TestFactoryGetters:
    def test_get_job_scout_returns_correct_type(self):
        scout = agents.get_job_scout()
        assert isinstance(scout, JobScoutAgent)
        assert scout.agent_type == "job_scout"

    def test_get_app_tracker_returns_correct_type(self):
        tracker = agents.get_app_tracker()
        assert isinstance(tracker, ApplicationTrackerAgent)
        assert tracker.agent_type == "app_tracker"

    def test_get_career_advisor_returns_correct_type(self):
        advisor = agents.get_career_advisor()
        assert isinstance(advisor, CareerAdvisorAgent)
        assert advisor.agent_type == "career_advisor"

    def test_get_interview_coach_returns_correct_type(self):
        coach = agents.get_interview_coach()
        assert isinstance(coach, InterviewCoachAgent)
        assert coach.agent_type == "interview_coach"

    def test_get_cover_letter_returns_correct_type(self):
        cl = agents.get_cover_letter()
        assert isinstance(cl, CoverLetterAgent)
        assert cl.agent_type == "cover_letter"

    def test_get_resume_tailor_returns_correct_type(self):
        tailor = agents.get_resume_tailor()
        assert isinstance(tailor, ResumeTailorAgent)
        assert tailor.agent_type == "resume_tailor"


class TestStringDispatch:
    def test_get_agent_job_scout(self):
        agent = agents.get_agent("job_scout")
        assert isinstance(agent, JobScoutAgent)

    def test_get_agent_app_tracker(self):
        agent = agents.get_agent("app_tracker")
        assert isinstance(agent, ApplicationTrackerAgent)

    def test_get_agent_invalid_raises(self):
        try:
            agents.get_agent("invalid_type")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Unknown agent type" in str(e)
            assert "invalid_type" in str(e)


class TestSingletonBehavior:
    def test_job_scout_singleton(self):
        s1 = agents.get_job_scout()
        s2 = agents.get_job_scout()
        assert s1 is s2, "get_job_scout should return same instance"

    def test_app_tracker_singleton(self):
        t1 = agents.get_app_tracker()
        t2 = agents.get_app_tracker()
        assert t1 is t2, "get_app_tracker should return same instance"
