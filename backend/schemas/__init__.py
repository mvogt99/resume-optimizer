"""Schema package — exports SCHEMAS master dict mapping (method, path_pattern) → schema.

Keys are tuples of (HTTP_METHOD, url_pattern, status_code).
Values are JSON Schema dicts (draft-07 compatible).
"""

from schemas import agents as _agents
from schemas import auth as _auth
from schemas import campaigns as _campaigns
from schemas import experience as _experience
from schemas import gdrive as _gdrive
from schemas import graph as _graph
from schemas import jobs as _jobs
from schemas import journey as _journey
from schemas import profile as _profile
from schemas import projects as _projects
from schemas import resume as _resume
from schemas import sessions as _sessions

# Master schema registry: (method, path_pattern, status_code) → schema dict
SCHEMAS = {
    # --- Auth ---
    ("POST", "/api/register", 201): _auth.REGISTER_201,
    ("POST", "/api/register", 409): _auth.REGISTER_409,
    ("POST", "/api/login", 200): _auth.LOGIN_200,
    ("POST", "/api/login", 401): _auth.LOGIN_401,
    # --- Resume ---
    ("POST", "/api/resume/upload", 201): _resume.UPLOAD_RESUME_201,
    ("POST", "/api/job-description/upload", 201): _resume.UPLOAD_JD_201,
    ("POST", "/api/optimize-resume/<resume_id>", 200): _resume.OPTIMIZE_200,
    ("GET", "/api/skills-gap/<resume_id>", 200): _resume.SKILLS_GAP_200,
    ("POST", "/api/skills-gap/<resume_id>/rescore", 200): _resume.SKILLS_GAP_200,
    ("POST", "/api/resume/from-linkedin", 201): _resume.FROM_LINKEDIN_201,
    # --- Experience ---
    ("POST", "/api/experience/start", 201): _experience.START_SESSION_201,
    ("POST", "/api/experience/message", 200): _experience.SEND_MESSAGE_200,
    ("GET", "/api/experience/summary/<session_id>", 200): _experience.SUMMARY_200,
    ("POST", "/api/experience/finalize/<session_id>", 200): _experience.FINALIZE_200,
    ("POST", "/api/experience/apply/<session_id>", 201): _experience.APPLY_201,
    ("GET", "/api/experience/list", 200): _experience.LIST_200,
    ("POST", "/api/skills-interview/start", 200): _experience.SKILLS_INTERVIEW_START_200,
    ("POST", "/api/skills-interview/message", 200): _experience.SEND_MESSAGE_200,
    (
        "GET",
        "/api/skills-interview/<session_id>/summary",
        200,
    ): _experience.SKILLS_INTERVIEW_SUMMARY_200,
    (
        "POST",
        "/api/skills-interview/<session_id>/finalize",
        200,
    ): _experience.SKILLS_INTERVIEW_SUMMARY_200,
    ("POST", "/api/ats-improve/start", 200): _experience.ATS_IMPROVE_START_200,
    ("POST", "/api/ats-improve/message", 200): _experience.SEND_MESSAGE_200,
    ("GET", "/api/ats-improve/<session_id>/resume", 200): _experience.ATS_IMPROVE_RESUME_200,
    # --- Campaigns ---
    ("POST", "/api/campaigns/interview/start", 201): _campaigns.INTERVIEW_START_201,
    ("POST", "/api/campaigns/interview/message", 200): _campaigns.INTERVIEW_MESSAGE_200,
    ("GET", "/api/campaigns/interview/<session_id>/state", 200): _campaigns.SESSION_STATE_200,
    ("POST", "/api/campaigns/create", 201): _campaigns.CREATE_CAMPAIGN_201,
    ("GET", "/api/campaigns", 200): _campaigns.LIST_CAMPAIGNS_200,
    ("GET", "/api/campaigns/<campaign_id>", 200): _campaigns.GET_CAMPAIGN_200,
    ("PUT", "/api/campaigns/<campaign_id>", 200): _campaigns.UPDATE_CAMPAIGN_200,
    ("DELETE", "/api/campaigns/<campaign_id>", 200): _campaigns.DELETE_CAMPAIGN_200,
    ("POST", "/api/campaigns/<campaign_id>/generate", 202): _campaigns.GENERATE_POSTS_202,
    ("GET", "/api/campaigns/<campaign_id>/posts", 200): _campaigns.LIST_POSTS_200,
    ("POST", "/api/campaigns/<campaign_id>/posts", 201): _campaigns.ADD_POST_201,
    ("PUT", "/api/campaigns/<campaign_id>/posts/<post_id>", 200): _campaigns.UPDATE_POST_200,
    (
        "POST",
        "/api/campaigns/<campaign_id>/posts/<post_id>/regenerate",
        200,
    ): _campaigns.UPDATE_POST_200,
    ("DELETE", "/api/campaigns/<campaign_id>/posts/<post_id>", 200): _campaigns.DELETE_POST_200,
    ("PUT", "/api/campaigns/<campaign_id>/posts/reorder", 200): _campaigns.REORDER_POSTS_200,
    ("GET", "/api/campaigns/<campaign_id>/export", 200): _campaigns.EXPORT_200,
    ("GET", "/api/campaigns/analytics", 200): _campaigns.ANALYTICS_200,
    ("POST", "/api/campaigns/<campaign_id>/update-interview", 200): _campaigns.UPDATE_INTERVIEW_200,
    # --- Projects ---
    ("GET", "/api/projects", 200): _projects.LIST_PROJECTS_200,
    ("POST", "/api/projects", 201): _projects.CREATE_PROJECT_201,
    ("POST", "/api/projects/<project_id>/analyze", 202): _projects.START_ANALYSIS_202,
    ("GET", "/api/projects/<project_id>/analysis", 200): _projects.GET_ANALYSIS_200,
    ("PUT", "/api/projects/<project_id>/analysis", 200): _projects.UPDATE_ANALYSIS_200,
    ("POST", "/api/projects/<project_id>/approve", 200): _projects.APPROVE_ANALYSIS_200,
    ("GET", "/api/projects/<project_id>/documents", 200): _projects.LIST_DOCUMENTS_200,
    ("GET", "/api/projects/folders", 200): _projects.LIST_FOLDERS_200,
    ("POST", "/api/projects/<project_id>/reanalyze", 202): _projects.REANALYZE_202,
    ("POST", "/api/projects/<project_id>/reset-status", 200): _projects.RESET_STATUS_200,
    # --- Journey ---
    ("POST", "/api/journey/mine", 202): _journey.START_MINING_202,
    ("GET", "/api/journey/timeline", 200): _journey.TIMELINE_200,
    ("GET", "/api/journey/skills", 200): _journey.SKILLS_200,
    ("GET", "/api/journey/achievements", 200): _journey.ACHIEVEMENTS_200,
    ("GET", "/api/journey/narratives", 200): _journey.NARRATIVES_200,
    ("PUT", "/api/journey/narratives", 200): _journey.UPDATE_NARRATIVES_200,
    ("POST", "/api/journey/approve", 200): _journey.APPROVE_NARRATIVES_200,
    ("GET", "/api/journey/sources", 200): _journey.SOURCES_200,
    ("POST", "/api/journey/review/start", 200): _journey.REVIEW_START_200,
    ("POST", "/api/journey/review/message", 200): _journey.REVIEW_MESSAGE_200,
    ("POST", "/api/journey/review/apply", 200): _journey.REVIEW_APPLY_200,
    # --- Profile ---
    ("POST", "/api/import/linkedin", 200): _profile.IMPORT_LINKEDIN_200,
    ("GET", "/api/profile/linkedin", 200): _profile.GET_LINKEDIN_200,
    ("POST", "/api/deep-profile/build", 200): _profile.BUILD_DEEP_PROFILE_200,
    ("GET", "/api/deep-profile", 200): _profile.GET_DEEP_PROFILE_200,
    ("POST", "/api/deep-profile/role-synthesis", 200): _profile.ROLE_SYNTHESIS_200,
    ("POST", "/api/deep-interview/start", 200): _profile.DEEP_INTERVIEW_START_200,
    ("POST", "/api/deep-interview/message", 200): _profile.DEEP_INTERVIEW_MESSAGE_200,
    ("GET", "/api/deep-interview/<session_id>/status", 200): _profile.DEEP_INTERVIEW_STATUS_200,
    (
        "POST",
        "/api/deep-interview/<session_id>/finalize",
        200,
    ): _profile.DEEP_INTERVIEW_FINALIZE_200,
    ("GET", "/api/deep-interview/<session_id>/insights", 200): _profile.DEEP_INTERVIEW_INSIGHTS_200,
    ("GET", "/api/interview-guide/<resume_id>", 200): _profile.INTERVIEW_GUIDE_200,
    # --- Builder ---
    # (builder routes exist in builder_routes.py)
    ("GET", "/api/builder/sources", 200): {"type": "object", "additionalProperties": True},
    ("POST", "/api/builder/start", 201): {
        "type": "object",
        "required": ["session_id"],
        "properties": {
            "session_id": {"type": "string"},
            "status": {"type": "string"},
            "message": {"type": "string"},
        },
        "additionalProperties": True,
    },
    ("GET", "/api/builder/preview/<session_id>", 200): {
        "type": "object",
        "additionalProperties": True,
    },
    ("POST", "/api/builder/interview/start", 201): {
        "type": "object",
        "required": ["session_id"],
        "properties": {"session_id": {"type": "string"}},
        "additionalProperties": True,
    },
    ("POST", "/api/builder/interview/message", 200): {
        "type": "object",
        "additionalProperties": True,
    },
    ("GET", "/api/builder/interview/status/<session_id>", 200): {
        "type": "object",
        "additionalProperties": True,
    },
    ("POST", "/api/builder/compile/<session_id>", 200): {
        "type": "object",
        "additionalProperties": True,
    },
    ("PUT", "/api/builder/edit/<session_id>", 200): {
        "type": "object",
        "additionalProperties": True,
    },
    ("POST", "/api/builder/save/<session_id>", 201): {
        "type": "object",
        "required": ["session_id"],
        "properties": {
            "session_id": {"type": "string"},
            "version_id": {"type": "integer"},
            "resume_id": {"type": "integer"},
        },
        "additionalProperties": True,
    },
    # --- Jobs ---
    ("GET", "/api/jobs", 200): _jobs.LIST_JOBS_200,
    ("GET", "/api/jobs/<job_id>/status", 200): _jobs.JOB_STATUS_200,
    ("POST", "/api/jobs/<job_id>/cancel", 200): _jobs.CANCEL_JOB_200,
    # --- GDrive + Versions ---
    ("GET", "/api/resumes/gdrive", 200): _gdrive.GDRIVE_LIST_200,
    ("POST", "/api/resumes/gdrive/import", 201): _gdrive.GDRIVE_IMPORT_201,
    ("GET", "/api/resumes/versions", 200): _gdrive.VERSIONS_LIST_200,
    ("GET", "/api/resumes/versions/<version_id>", 200): _gdrive.VERSION_GET_200,
    ("PUT", "/api/resumes/versions/<version_id>", 200): _gdrive.VERSION_UPDATE_200,
    ("POST", "/api/resumes/gdrive/reimport/<version_id>", 200): _gdrive.REIMPORT_200,
    # --- Graph ---
    ("GET", "/api/graph/technologies", 200): _graph.TECHNOLOGIES_200,
    ("GET", "/api/graph/clients-by-tech", 200): _graph.CLIENTS_BY_TECH_200,
    ("GET", "/api/graph/knowledge-context", 200): _graph.KNOWLEDGE_CONTEXT_200,
    # --- Sessions ---
    ("POST", "/api/sessions", 201): _sessions.CREATE_SESSION_201,
    ("GET", "/api/sessions", 200): _sessions.LIST_SESSIONS_200,
    ("GET", "/api/sessions/<session_id>", 200): _sessions.GET_SESSION_200,
    ("PUT", "/api/sessions/<session_id>", 200): _sessions.UPDATE_SESSION_200,
    ("DELETE", "/api/sessions/<session_id>", 200): _sessions.DELETE_SESSION_200,
    ("POST", "/api/sessions/<session_id>/optimize", 200): _sessions.OPTIMIZE_SESSION_200,
    # --- Agents ---
    ("POST", "/api/agents/scout/search", 202): _agents.SCOUT_SEARCH_202,
    ("GET", "/api/agents/scout/postings", 200): _agents.SCOUT_POSTINGS_200,
    ("GET", "/api/agents/scout/postings/<posting_id>", 200): _agents.SCOUT_POSTING_GET_200,
    ("PUT", "/api/agents/scout/postings/<posting_id>", 200): _agents.SCOUT_POSTING_UPDATE_200,
    ("DELETE", "/api/agents/scout/postings/<posting_id>", 200): _agents.SCOUT_POSTING_DELETE_200,
    ("POST", "/api/agents/scout/postings", 201): _agents.SCOUT_POSTING_CREATE_201,
    (
        "POST",
        "/api/agents/scout/postings/<posting_id>/rescore",
        200,
    ): _agents.SCOUT_POSTING_UPDATE_200,
    ("POST", "/api/agents/scout/criteria", 201): _agents.SCOUT_CRITERIA_SAVE_201,
    ("GET", "/api/agents/scout/criteria", 200): _agents.SCOUT_CRITERIA_LIST_200,
    ("GET", "/api/agents/pipeline", 200): _agents.PIPELINE_GET_200,
    ("PUT", "/api/agents/pipeline/<posting_id>", 200): _agents.PIPELINE_MOVE_200,
    ("GET", "/api/agents/pipeline/analytics", 200): _agents.PIPELINE_ANALYTICS_200,
    ("GET", "/api/agents/pipeline/reminders", 200): _agents.PIPELINE_REMINDERS_200,
    ("POST", "/api/agents/pipeline/<posting_id>/followup", 200): _agents.PIPELINE_FOLLOWUP_200,
    ("POST", "/api/agents/pipeline/<posting_id>/analyze", 200): _agents.PIPELINE_ANALYZE_200,
    ("GET", "/api/agents/runs", 200): _agents.AGENT_RUNS_200,
    ("GET", "/api/agents/status", 200): _agents.AGENT_STATUS_200,
    ("POST", "/api/agents/tailor/<posting_id>", 200): _agents.TAILOR_POST_200,
    ("GET", "/api/agents/tailor/<posting_id>", 200): _agents.TAILOR_GET_200,
    ("POST", "/api/agents/cover-letter/<posting_id>", 201): _agents.COVER_LETTER_CREATE_201,
    ("GET", "/api/agents/cover-letter/<posting_id>", 200): _agents.COVER_LETTER_GET_200,
    ("GET", "/api/agents/cover-letters/<letter_id>", 200): _agents.COVER_LETTER_GET_200,
    ("PUT", "/api/agents/cover-letters/<letter_id>", 200): _agents.SCOUT_POSTING_UPDATE_200,
    ("DELETE", "/api/agents/cover-letters/<letter_id>", 200): _agents.SCOUT_POSTING_DELETE_200,
    ("POST", "/api/agents/cover-letters/<letter_id>/regenerate", 200): _agents.COVER_LETTER_GET_200,
    ("POST", "/api/agents/coach/start", 201): _agents.COACH_START_201,
    ("POST", "/api/agents/coach/answer", 200): _agents.COACH_SESSION_200,
    ("GET", "/api/agents/coach/<session_id>", 200): _agents.COACH_SESSION_200,
    ("GET", "/api/agents/coach/sessions", 200): _agents.COACH_SESSIONS_200,
    ("GET", "/api/agents/coach/<session_id>/assessment", 200): _agents.COACH_SESSION_200,
    ("POST", "/api/agents/advisor/analyze", 200): _agents.ADVISOR_ANALYZE_200,
    ("POST", "/api/agents/advisor/skills-roadmap", 200): _agents.ADVISOR_ANALYZE_200,
    ("POST", "/api/agents/advisor/role-recommendations", 200): _agents.ADVISOR_ANALYZE_200,
}


def get_schema(method, path, status_code):
    """Look up schema for a route. Returns None if not found."""
    return SCHEMAS.get((method, path, status_code))


def list_covered_routes():
    """Return set of (method, path) tuples that have schemas."""
    return {(m, p) for m, p, _ in SCHEMAS.keys()}
