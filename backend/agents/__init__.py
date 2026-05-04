"""Phase 8+15: Agentic AI career assistant agents + orchestrator."""

from agents.app_tracker import ApplicationTrackerAgent
from agents.career_advisor import CareerAdvisorAgent
from agents.cover_letter import CoverLetterAgent
from agents.interview_coach import InterviewCoachAgent
from agents.job_scout import JobScoutAgent
from agents.orchestrator import OrchestratorAgent
from agents.resume_tailor import ResumeTailorAgent

_job_scout = None
_app_tracker = None
_resume_tailor = None
_cover_letter = None
_interview_coach = None
_career_advisor = None
_orchestrator = None


def get_job_scout():
    global _job_scout
    if _job_scout is None:
        _job_scout = JobScoutAgent()
    return _job_scout


def get_app_tracker():
    global _app_tracker
    if _app_tracker is None:
        _app_tracker = ApplicationTrackerAgent()
    return _app_tracker


def get_resume_tailor():
    global _resume_tailor
    if _resume_tailor is None:
        _resume_tailor = ResumeTailorAgent()
    return _resume_tailor


def get_cover_letter():
    global _cover_letter
    if _cover_letter is None:
        _cover_letter = CoverLetterAgent()
    return _cover_letter


def get_interview_coach():
    global _interview_coach
    if _interview_coach is None:
        _interview_coach = InterviewCoachAgent()
    return _interview_coach


def get_career_advisor():
    global _career_advisor
    if _career_advisor is None:
        _career_advisor = CareerAdvisorAgent()
    return _career_advisor


def get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = OrchestratorAgent()
    return _orchestrator


def get_agent(agent_type):
    """Factory to get agent by type string."""
    agents = {
        "job_scout": get_job_scout,
        "app_tracker": get_app_tracker,
        "resume_tailor": get_resume_tailor,
        "cover_letter": get_cover_letter,
        "interview_coach": get_interview_coach,
        "career_advisor": get_career_advisor,
        "orchestrator": get_orchestrator,
    }
    factory = agents.get(agent_type)
    if factory:
        return factory()
    raise ValueError(f"Unknown agent type: {agent_type}")
